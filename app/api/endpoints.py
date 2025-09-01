"""API endpoints for basic document extraction and analysis."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import JSONResponse
import traceback
from urllib.parse import urlparse, unquote
from app.services.document_processor import process_document
from app.models.document_data import DocumentData
from app.services.llm_extractor import get_image_bytes_from_input


# Helper: convert FieldWithConfidence and other model objects to plain dicts for JSON serialization
def convert_fields_to_dict(data):
    """Recursively convert FieldWithConfidence objects to dictionaries"""
    if hasattr(data, 'to_dict'):
        return data.to_dict()
    elif isinstance(data, dict):
        return {k: convert_fields_to_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_fields_to_dict(item) for item in data]
    else:
        return data


# Helper: strip any raw OCR artifacts from payloads (never return OCR line data)
def strip_ocr_artifacts(data):
    """Remove OCR line data keys from nested dict/list structures.
    This enforces that responses never include raw OCR outputs.
    """
    OCR_KEYS = {"ocr", "ocr_text", "ocr_lines", "ocr_results", "ocr_raw", "raw_ocr", "ocr_blocks", "results"}
    if isinstance(data, dict):
        for k in list(data.keys()):
            if k in OCR_KEYS:
                data.pop(k, None)
            else:
                strip_ocr_artifacts(data[k])
    elif isinstance(data, list):
        for i in data:
            strip_ocr_artifacts(i)
    return data


# Create router
document_router = APIRouter(tags=["Document Processing"])

@document_router.post("/extract")
async def extract_document(
    request: Request,
    file: UploadFile = File(None),
    url: str = Query(None, description="URL to document (image or PDF)"),
    path: str = Query(None, description="Local file path to document"),
    structured: bool = Query(False, description="Extract structured data using LLM"),
    include_raw: bool = Query(False, description="Include complete raw JSON with all fields")
):
    """
    Extract text and optionally structured data from a document\
    Accepts file upload, URL, or local file path.
    
    Args:
        file: The document file to process
        url: The URL to process
        path: the local path of the file to process
        structured: If True, extract structured data using LLM
        include_raw: If True, include complete raw JSON alongside filtered data
        
    Returns:
        JSON response with OCR results and structured data if requested
    """
    
    # Determine input source (file > url > path). Also support JSON body for url/path.
    if file:
        file_content = await file.read()
        input_source = file_content
        filename = file.filename
        # File extension only needed for uploaded files
        file_extension = file.filename.split(".")[-1].lower()
    elif url:
        input_source = url
        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1]) or url
        # Don't validate URL extension - we'll check the content type instead
        file_extension = "unknown"
    elif path:
        input_source = path
        filename = path.split("/")[-1]
        file_extension = path.split(".")[-1].lower()
    else:
        # Try to read JSON body for url/path when no query params provided
        body_url = None
        body_path = None
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
                if isinstance(payload, dict):
                    body_url = payload.get("url")
                    body_path = payload.get("path")
        except Exception:
            body_url = body_url or None
            body_path = body_path or None

        if body_url:
            input_source = body_url
            parsed = urlparse(body_url)
            filename = unquote(parsed.path.split("/")[-1]) or body_url
            file_extension = "unknown"
        elif body_path:
            input_source = body_path
            filename = body_path.split("/")[-1]
            file_extension = body_path.split(".")[-1].lower() if "." in body_path else "unknown"
        else:
            return JSONResponse(
                status_code=400,
                content={"detail": "No input provided. Provide one of: file upload, url, or path (as query or JSON body)."}
            )
    
    try:
        # Use the utility to get image bytes from any input type with enhanced URL support
        try:
            print(f"Processing input source: {'URL' if url else ('File' if file else 'Path')}")
            image_bytes = get_image_bytes_from_input(input_source)
        except ValueError as url_error:
            print(f"Error processing input: {str(url_error)}")
            return JSONResponse(
                status_code=400,
                content={"detail": str(url_error)}
            )

        if structured:
            # Extract both raw OCR results and structured data
            ocr_results, structured_documents, all_relevant_fields = await process_document(
                image_bytes, 
                file_extension,
                extract_structured=True
            )
            
            # Handle multiple documents
            if isinstance(structured_documents, list) and len(structured_documents) > 1:
                # Multiple documents found
                response_data = {
                    "filename": file.filename if file else (url or path),
                    "multiple_documents": True,
                    "document_count": len(structured_documents),
                    # Convert all FieldWithConfidence objects to dicts recursively
                    "structured_data": [convert_fields_to_dict(fields) for fields in all_relevant_fields],
                    "documents_summary": [
                        {
                            "document_type": doc.document_type.value if doc.document_type else "Unknown",
                            "document_number": doc.document_number.value if doc.document_number else None
                        } for doc in structured_documents
                    ]
                }
                
                # Add complete raw data if requested (for development/integration)
                if include_raw:
                    response_data["raw_structured_data"] = [doc.dict() for doc in structured_documents]
                    
            else:
                # Single document (backward compatibility)
                structured_data = structured_documents[0] if structured_documents else None
                relevant_fields = all_relevant_fields[0] if all_relevant_fields else {}
                
                response_data = {
                    "filename": file.filename if file else (url or path),
                    "multiple_documents": False,
                    "document_count": 1,
                    # Convert all FieldWithConfidence objects to dicts recursively
                    "structured_data": convert_fields_to_dict(relevant_fields)
                }
                
                # Add complete raw data if requested (for development/integration)
                if include_raw:
                    response_data["raw_structured_data"] = structured_data.dict() if structured_data else {}
            
            # Ensure no raw OCR artifacts are present
            return JSONResponse(content=strip_ocr_artifacts(response_data))
        else:
            # OCR-only mode: do not return raw OCR lines; return minimal envelope
            # keeping backward compatibility of route shape (filename present)
            return JSONResponse(content={
                "filename": file.filename if file else (url or path),
                "message": "Set structured=true to receive extracted JSON fields. Raw OCR lines are not returned."
            })
    
    except ValueError as ve:
        # Handle validation errors
        print(f"Validation error: {str(ve)}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(ve)}
        )
    except Exception as e:
        # Log the error for debugging
        print(f"Error processing document: {str(e)}")
        traceback_str = traceback.format_exc()
        print(traceback_str)
        return JSONResponse(
            status_code=500, 
            content={"detail": f"Error processing document: {str(e)}"}
        )


@document_router.post("/analyze", deprecated=True)
async def analyze_document(
    request: Request,
    file: UploadFile = File(None),
    url: str = Query(None, description="URL to document (image or PDF)"),
    path: str = Query(None, description="Local file path to document")
):
    """
    Analyze a document and extract structured information
    
    This endpoint always uses the LLM-powered structured data extraction
    
    Args:
        file: The document file to analyze
        
    Returns:
        Structured document data
    """
    # Determine input source (file > url > path)
    if file:
        file_content = await file.read()
        input_source = file_content
        file_extension = file.filename.split(".")[-1].lower()
        filename = file.filename
    elif url:
        input_source = url
        file_extension = "unknown"
        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1]) or url
    elif path:
        input_source = path
        file_extension = path.split(".")[-1].lower() if "." in path else "unknown"
        filename = path.split("/")[-1]
    else:
        # Try JSON body for url/path
        body_url = None
        body_path = None
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
                if isinstance(payload, dict):
                    body_url = payload.get("url")
                    body_path = payload.get("path")
        except Exception:
            pass
        if body_url:
            input_source = body_url
            file_extension = "unknown"
            parsed = urlparse(body_url)
            filename = unquote(parsed.path.split("/")[-1]) or body_url
        elif body_path:
            input_source = body_path
            file_extension = body_path.split(".")[-1].lower() if "." in body_path else "unknown"
            filename = body_path.split("/")[-1]
        else:
            raise HTTPException(status_code=400, detail="No input provided. Provide file, url, or path (query or JSON body).")

    try:
        # Normalize input to image bytes
        image_bytes = get_image_bytes_from_input(input_source)
        # Always perform structured extraction for analysis
        _, structured_documents, _ = await process_document(
            image_bytes,
            file_extension,
            extract_structured=True
        )

        # Return the first document's JSON if available
        if structured_documents:
            payload = structured_documents[0].dict()
            return JSONResponse(content=strip_ocr_artifacts(payload))
        else:
            raise HTTPException(status_code=500, detail="No documents found in the input")
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error analyzing document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing document: {str(e)}")





# from fastapi.responses import JSONResponse
# from typing import List

# from app.services.document_processor import process_document

# # Create router
# document_router = APIRouter(tags=["Document Processing"])

# @document_router.post("/extract", response_class=JSONResponse)
# async def extract_document_text(file: UploadFile = File(...)):
#     """
#     Extract text from an uploaded document (PDF, JPG, PNG, JPEG) using OCR
#     """
#     try:
#         # Validate file extension
#         allowed_extensions = ["pdf", "jpg", "jpeg", "png"]
#         file_extension = file.filename.split(".")[-1].lower()
        
#         if file_extension not in allowed_extensions:
#             raise HTTPException(
#                 status_code=400, 
#                 detail=f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}"
#             )
        
#         # Process the document
#         file_content = await file.read()
#         ocr_results = await process_document(file_content, file_extension)
        
#         return JSONResponse(content={"results": ocr_results})
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")




