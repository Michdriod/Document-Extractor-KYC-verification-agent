"""Document processing utilities: PDF-to-image conversion and OCR orchestration using PaddleOCR."""

import io
import asyncio
import time
from typing import List, Dict, Any, Union, Tuple
from PIL import Image
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

from app.models.document_data import DocumentData
from app.services.enhanced_extractor import DocumentExtractor
from app.services.field_categorizer import categorize_fields, get_primary_fields, match_related_fields

# Initialize PaddleOCR once (it's resource-intensive)
ocr = PaddleOCR(use_angle_cls=True, lang='en')

async def process_document(file_content: bytes, file_extension: str, extract_structured: bool = False) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], List[DocumentData], List[Dict[str, Any]]]]:
    """
    Process a document file and extract text using PaddleOCR
    
    Args:
        file_content: Binary content of the uploaded file
        file_extension: File extension (pdf, jpg, jpeg, png)
        extract_structured: Whether to extract structured data using LLM fallback
        
    Returns:
        If extract_structured=False: List of dictionaries with extracted text and bounding box coordinates
        If extract_structured=True: Tuple of (OCR results, List of structured DocumentData objects, List of relevant fields dicts)
    """
    # Convert to image(s) if PDF
    images = []
    if file_extension == "pdf":
        # Run PDF conversion in a thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        images = await loop.run_in_executor(
            None, 
            lambda: convert_from_bytes(file_content, fmt="jpeg")
        )
    else:
        # For image files, just load directly
        image = Image.open(io.BytesIO(file_content))
        images = [image]
    
    # Process all images and extract text
    all_results = []
    
    for idx, img in enumerate(images):
        # Convert PIL Image to bytes for PaddleOCR
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Run OCR in a thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: ocr.ocr(img_byte_arr, cls=True)
        )
        
        # Format the results
        page_results = []
        if result and result[0]:  # PaddleOCR returns list of pages, with each page having results
            for line in result[0]:
                bbox, (text, confidence) = line
                page_results.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": bbox,
                    "page": idx + 1
                })
        
        all_results.extend(page_results)
    
    # If structured extraction is not needed, return just OCR results
    if not extract_structured:
        return all_results
    
    # For structured extraction, process ALL images/pages to handle multiple documents
    structured_documents = []
    all_relevant_fields = []
    
    if images:
        for idx, img in enumerate(images):
            try:
                # Convert each image to bytes for LLM processing
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                image_bytes = img_byte_arr.getvalue()
                
                # Get OCR results for this specific page
                page_ocr_results = [result for result in all_results if result.get("page") == idx + 1]
                
                # Skip empty pages or pages with insufficient OCR data
                if not page_ocr_results or len(page_ocr_results) < 3:
                    print(f"⏭️  Skipping page {idx + 1}: Insufficient OCR data")
                    continue
                
                print(f"🔄 Processing page {idx + 1}/{len(images)} for structured extraction...")
                
                # Start timing extraction process
                start_time = time.time()
                
                # Extract structured data with fallback to LLM for this page
                document_extractor = DocumentExtractor()
                extraction_result = await document_extractor.extract_data_with_fallback(image_bytes, page_ocr_results)
                
                # Calculate extraction time
                extraction_time_ms = int((time.time() - start_time) * 1000)
                extraction_result["metadata"]["processing_time_ms"] = extraction_time_ms
                
                # Process each document found on this page
                for doc_idx, doc in enumerate(extraction_result["documents"]):
                    if doc["extraction_status"] == "success" and doc["data"]:
                        # Convert back to DocumentData format for backward compatibility
                        doc_data = DocumentData.model_validate(doc["data"])
                        
                        # Enhance fields with categorization
                        if doc["data"].get("fields"):
                            # Categorize fields for better organization
                            categorized = categorize_fields(doc["data"]["fields"])
                            doc["data"]["categorized_fields"] = categorized
                            
                            # Get the most important fields from each category
                            primary_fields = get_primary_fields(categorized)
                            doc["data"]["primary_fields"] = primary_fields
                            
                            # Identify related fields
                            related_fields = match_related_fields(doc["data"]["fields"])
                            doc["data"]["related_fields"] = [
                                {"field1": rel[0], "field2": rel[1], "score": rel[2]} 
                                for rel in related_fields if rel[2] > 0.7
                            ]
                        
                        structured_documents.append(doc_data)
                        all_relevant_fields.append(doc["data"])
                        
                        print(f"✅ Page {idx + 1}, Document {doc_idx + 1}: Found {doc['document_type']}, {len(doc['data'].get('fields', {}))} fields, {len(doc['data'].get('categorized_fields', {}))} categories")
                    else:
                        print(f"❌ Page {idx + 1}, Document {doc_idx + 1}: Extraction failed")
                
                print(f"📄 Page {idx + 1}: Processed {len(extraction_result['documents'])} documents")
                
            except Exception as e:
                print(f"❌ Failed to process page {idx + 1}: {str(e)}")
                continue
        
        # Return OCR results, all structured documents, and all relevant fields
        return all_results, structured_documents, all_relevant_fields
    else:
        # If no images were processed, just return OCR results
        return all_results
