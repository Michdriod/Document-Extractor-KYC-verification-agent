"""API endpoints for enhanced document processing and structured extraction."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
import time
import traceback
from urllib.parse import urlparse, unquote
from app.services.document_processor import ocr
import numpy as np
try:
    import cv2  # optional; improves decoding speed
except Exception:  # pragma: no cover
    cv2 = None
from PIL import Image
import io
from app.services.enhanced_extractor import DocumentExtractor
from app.services.llm_extractor import get_image_pages_from_input


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


def strip_ocr_artifacts(data):
    """Remove OCR line data keys from nested dict/list structures to avoid returning raw OCR."""
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
    # Determine input source and extension
    if file:
        file_content = await file.read()
        input_source = file_content
        filename = file.filename
        file_extension = file.filename.split(".")[-1].lower() if "." in file.filename else "unknown"
    elif url:
        input_source = url
        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1]) or url
        file_extension = parsed.path.split(".")[-1].lower() if "." in parsed.path else "unknown"
    elif path:
        input_source = path
        filename = path.split("/")[-1]
        file_extension = path.split(".")[-1].lower() if "." in path else "unknown"
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": "No input provided. Please provide either file, url, or path."}
        )
    
    try:
        # Start overall processing timer
        start_time = time.time()

        # Prepare pages via shared helper (handles PDF->images and images)
        try:
            page_bytes: list[bytes] = get_image_pages_from_input(file_content if file else input_source)
        except ValueError as e:
            return JSONResponse(status_code=400, content={"detail": str(e)})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"Failed to prepare pages: {e}"})

        # OCR + extraction over all pages
        all_docs = []
        total_ocr_text_len = 0
        loop = __import__('asyncio').get_event_loop()
        from app.services.field_categorizer import categorize_fields, get_primary_fields, match_related_fields

        for idx, pg_bytes in enumerate(page_bytes):
            # Make ndarray image
            cv_img = None
            if cv2 is not None:
                try:
                    np_buf = np.frombuffer(pg_bytes, dtype=np.uint8)
                    cv_img = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
                except Exception:
                    cv_img = None
            if cv_img is None:
                try:
                    pil_img = Image.open(io.BytesIO(pg_bytes)).convert('RGB')
                    cv_img = np.array(pil_img)
                except Exception:
                    return JSONResponse(status_code=400, content={"detail": "Unable to decode page image"})

            # OCR
            ocr_result = await loop.run_in_executor(None, lambda: ocr.ocr(cv_img, cls=True))
            page_ocr = []
            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    bbox, (text, confidence) = line
                    page_ocr.append({"text": text, "confidence": float(confidence), "bbox": bbox, "page": idx + 1})
            total_ocr_text_len += sum(len(it["text"]) for it in page_ocr)

            # Extract per page
            document_extractor = DocumentExtractor()
            page_extraction = await document_extractor.extract_data_with_fallback(pg_bytes, page_ocr)

            # Enrich and collect
            for doc in page_extraction.get("documents", []):
                if doc.get("extraction_status") == "success" and doc.get("data") and doc["data"].get("fields"):
                    serialized_fields = convert_fields_to_dict(doc["data"]["fields"])
                    doc["data"]["fields"] = serialized_fields
                    categorized = categorize_fields(serialized_fields)
                    doc["data"]["categorized_fields"] = categorized
                    primary_fields = get_primary_fields(categorized)
                    doc["data"]["primary_fields"] = primary_fields
                    related_fields = match_related_fields(serialized_fields)
                    doc["data"]["related_fields"] = [
                        {"field1": rel[0], "field2": rel[1], "score": rel[2]} for rel in related_fields if rel[2] > 0.7
                    ]
                all_docs.append(doc)

        # Build final response
        source_type = "file" if file else ("url" if url else "path")
        response_payload = {
            "documents": all_docs,
            "metadata": {
                "filename": filename,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "ocr_text_length": total_ocr_text_len,
                "source_type": source_type
            }
        }
        if source_type == "url":
            response_payload["metadata"]["source_url"] = url

        serializable_result = convert_fields_to_dict(response_payload)
        return JSONResponse(content=strip_ocr_artifacts(serializable_result))
    
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
