from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import io
from app.services.document_processor import process_document
from app.models.document_data import DocumentData

# Create router
document_router = APIRouter(tags=["Document Processing"])

@document_router.post("/extract")
async def extract_document(
    file: UploadFile = File(...),
    structured: bool = Query(False, description="Extract structured data using LLM"),
    include_raw: bool = Query(False, description="Include complete raw JSON with all fields")
):
    """
    Extract text and optionally structured data from a document
    
    Args:
        file: The document file to process
        structured: If True, extract structured data using LLM
        include_raw: If True, include complete raw JSON alongside filtered data
        
    Returns:
        JSON response with OCR results and structured data if requested
    """
    # Validate file extension first - before any other processing
    allowed_extensions = ["pdf", "jpg", "jpeg", "png"]
    file_extension = file.filename.split(".")[-1].lower()
    
    if file_extension not in allowed_extensions:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}"}
        )
    
    try:
        # Process the document
        file_content = await file.read()
        
        if structured:
            # Extract both raw OCR results and structured data
            ocr_results, structured_data, relevant_fields = await process_document(
                file_content, 
                file_extension,
                extract_structured=True
            )
            
            # Return both OCR results and clean structured data
            response_data = {
                "filename": file.filename,
                "ocr_results": ocr_results,
                "structured_data": relevant_fields  # Clean, filtered fields for UI
            }
            
            # Add complete raw data if requested (for development/integration)
            if include_raw:
                response_data["raw_structured_data"] = structured_data.dict()
            
            return JSONResponse(content=response_data)
        else:
            # Just extract OCR results
            ocr_results = await process_document(file_content, file_extension)
            return JSONResponse(content={
                "filename": file.filename,
                "results": ocr_results
            })
    
    except Exception as e:
        # Log the error for debugging
        print(f"Error processing document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


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
        _, structured_data, relevant_fields = await process_document(
            file_content, 
            file_extension,
            extract_structured=True
        )
        
        return structured_data
        
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



