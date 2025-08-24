from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import io
import traceback
from app.services.document_processor import process_document
from app.models.document_data import DocumentData
from app.services.llm_extractor import get_image_bytes_from_input


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


# Create router
document_router = APIRouter(tags=["Document Processing"])

@document_router.post("/extract")
async def extract_document(
    file: UploadFile = File(None),
    url: str = Query(None, description= "URL to document (image to PDF)"),
    path: str = Query(None, desription= "Local file path to document"),
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
    # Validate file extension first - before any other processing
    allowed_extensions = ["pdf", "jpg", "jpeg", "png"]
    
    # Determine input source
    if file:
        file_content = await file.read()
        input_source = file_content
        filename = file.filename
        # File extension only needed for uploaded files
        file_extension = file.filename.split(".")[-1].lower()
    elif url:
        input_source = url
        filename = url.split("/")[-1]
        # Don't validate URL extension - we'll check the content type instead
        file_extension = "unknown"
    elif path:
        input_source = path
        filename = path.split("/")[-1]
        file_extension = path.split(".")[-1].lower()
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": "No input provided. Please provide either file, url, or path."}
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
                    "ocr_results": ocr_results,
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
                    "ocr_results": ocr_results,
                    "multiple_documents": False,
                    "document_count": 1,
                    # Convert all FieldWithConfidence objects to dicts recursively
                    "structured_data": convert_fields_to_dict(relevant_fields)
                }
                
                # Add complete raw data if requested (for development/integration)
                if include_raw:
                    response_data["raw_structured_data"] = structured_data.dict() if structured_data else {}
            
            return JSONResponse(content=response_data)
        else:
            # Just extract OCR results
            ocr_results = await process_document(image_bytes, file_extension)
            return JSONResponse(content={
                "filename": file.filename if file else (url or path),
                "results": ocr_results
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


@document_router.post("/analyze", response_model=DocumentData)
async def analyze_document(file: UploadFile = File(...)):
    """
    Analyze a document and extract structured information
    
    This endpoint always uses the LLM-powered structured data extraction
    
    Args:
        file: The document file to analyze
        
    Returns:
        Structured document data
    """
    # Validate file extension
    allowed_extensions = ["pdf", "jpg", "jpeg", "png"]
    file_extension = file.filename.split(".")[-1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Process the document with structured data extraction
        file_content = await file.read()
        _, structured_documents, all_relevant_fields = await process_document(
            file_content, 
            file_extension,
            extract_structured=True
        )
        
        # Return the first document for backward compatibility with single document analysis
        if structured_documents:
            return structured_documents[0].dict()
        else:
            raise HTTPException(status_code=500, detail="No documents found in the file")
        
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



