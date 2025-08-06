import io
import asyncio
from typing import List, Dict, Any, Union, Tuple
from PIL import Image
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

from app.models.document_data import DocumentData
from app.services.llm_extractor import extract_data_with_fallback

# Initialize PaddleOCR once (it's resource-intensive)
ocr = PaddleOCR(use_angle_cls=True, lang='en')

async def process_document(file_content: bytes, file_extension: str, extract_structured: bool = False) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], DocumentData]]:
    """
    Process a document file and extract text using PaddleOCR
    
    Args:
        file_content: Binary content of the uploaded file
        file_extension: File extension (pdf, jpg, jpeg, png)
        extract_structured: Whether to extract structured data using LLM fallback
        
    Returns:
        If extract_structured=False: List of dictionaries with extracted text and bounding box coordinates
        If extract_structured=True: Tuple of (OCR results, structured DocumentData)
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
    
    # For structured extraction, we'll use the first image for LLM analysis
    # We could process all pages, but for most ID documents, one page is sufficient
    if images:
        # Convert the first image to bytes for LLM processing
        img_byte_arr = io.BytesIO()
        images[0].save(img_byte_arr, format='JPEG')
        image_bytes = img_byte_arr.getvalue()
        
        # Extract structured data with fallback to LLM
        structured_data, relevant_fields = await extract_data_with_fallback(image_bytes, all_results)
        
        # Return OCR results, structured data, and relevant fields
        return all_results, structured_data, relevant_fields
    else:
        # If no images were processed, just return OCR results
        return all_results
