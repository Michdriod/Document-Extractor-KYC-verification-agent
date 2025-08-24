from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import io
import time
import traceback
from app.services.document_processor import ocr
from app.services.enhanced_extractor import DocumentExtractor
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
enhanced_router = APIRouter(tags=["Enhanced Document Processing"])

@enhanced_router.post("/extract/enhanced")
async def extract_document_enhanced(
    file: UploadFile = File(None),
    url: str = Query(None, description="URL to document (image or PDF)"),
    path: str = Query(None, description="Local file path to document")
):
    """
    Enhanced document extraction endpoint that processes multiple documents and returns
    a standardized response format with documents array and metadata.
    
    Args:
        file: The document file to process
        url: The URL to process
        path: The local path of the file to process
        
    Returns:
        JSON response with structured format containing documents array and metadata
    """
    # Determine input source
    if file:
        file_content = await file.read()
        input_source = file_content
        filename = file.filename
    elif url:
        input_source = url
        filename = url.split("/")[-1]
    elif path:
        input_source = path
        filename = path.split("/")[-1]
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": "No input provided. Please provide either file, url, or path."}
        )
    
    try:
        # Get image bytes from any input type with enhanced URL support
        try:
            print(f"Processing input source: {'URL' if url else ('File' if file else 'Path')}")
            image_bytes = get_image_bytes_from_input(input_source)
        except ValueError as url_error:
            print(f"Error processing input: {str(url_error)}")
            return JSONResponse(
                status_code=400,
                content={"detail": str(url_error)}
            )
        
        # Start overall processing timer
        start_time = time.time()
        
        # Run OCR on the image
        loop = __import__("asyncio").get_event_loop()
        ocr_result = await loop.run_in_executor(
            None,
            lambda: ocr.ocr(image_bytes, cls=True)
        )
        
        # Format OCR results
        ocr_results = []
        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                bbox, (text, confidence) = line
                ocr_results.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": bbox
                })
        
        # Initialize document extractor and process
        document_extractor = DocumentExtractor()
        extraction_result = await document_extractor.extract_data_with_fallback(image_bytes, ocr_results)
        
        # Enhance each document with field categorization
        from app.services.field_categorizer import categorize_fields, get_primary_fields, match_related_fields
        
        for doc in extraction_result["documents"]:
            if doc["extraction_status"] == "success" and doc["data"] and doc["data"].get("fields"):
                # Convert fields to dictionaries first to ensure serializable objects
                serialized_fields = convert_fields_to_dict(doc["data"]["fields"])
                doc["data"]["fields"] = serialized_fields
                
                # Categorize fields for better organization
                categorized = categorize_fields(serialized_fields)
                doc["data"]["categorized_fields"] = categorized
                
                # Get the most important fields from each category
                primary_fields = get_primary_fields(categorized)
                doc["data"]["primary_fields"] = primary_fields
                
                # Identify related fields
                related_fields = match_related_fields(serialized_fields)
                doc["data"]["related_fields"] = [
                    {"field1": rel[0], "field2": rel[1], "score": rel[2]} 
                    for rel in related_fields if rel[2] > 0.7
                ]
        
        # Add additional metadata
        extraction_result["metadata"]["filename"] = filename
        extraction_result["metadata"]["processing_time_ms"] = int((time.time() - start_time) * 1000)
        extraction_result["metadata"]["ocr_text_length"] = sum(len(item["text"]) for item in ocr_results)
        
        # Add source type information
        source_type = "file" if file else ("url" if url else "path")
        extraction_result["metadata"]["source_type"] = source_type
        if source_type == "url":
            extraction_result["metadata"]["source_url"] = url
        
        # Convert any FieldWithConfidence objects to dictionaries to ensure JSON serialization
        serializable_result = convert_fields_to_dict(extraction_result)
            
        return JSONResponse(content=serializable_result)
    
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
