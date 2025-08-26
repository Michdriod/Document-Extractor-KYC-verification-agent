"""URL-based ingestion endpoints for streaming HTTPS documents into the extractor."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, Optional
import io
import requests
import traceback
from urllib.parse import urlparse

# Try to import python-magic, fall back to basic MIME detection if not available
try:
    import magic
    HAS_PYTHON_MAGIC = True
except ImportError:
    HAS_PYTHON_MAGIC = False
    print("⚠️ python-magic not available, using basic MIME detection")

from app.services.document_processor import process_document
from app.services.llm_extractor import get_image_bytes_from_input


class URLIngestRequest(BaseModel):
    """Request model for URL-based document ingestion"""
    url: HttpUrl
    structured: bool = True
    include_raw: bool = False


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


def safe_stream_and_detect_mime(url: str, max_size_mb: int = 50) -> tuple[bytes, str]:
    """
    Safely stream document from HTTPS URL and detect MIME type without persistence.
    
    Args:
        url: HTTPS URL to stream from
        max_size_mb: Maximum file size in MB to prevent abuse
        
    Returns:
        tuple: (file_bytes, detected_mime_type)
        
    Raises:
        ValueError: If URL is invalid, not HTTPS, or file is unsupported
        HTTPException: If download fails or file is too large
    """
    # Validate HTTPS URL
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise ValueError("Only HTTPS URLs are supported for security")
    
    # Set headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'image/*,application/pdf,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        # Stream the file with size limit
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Check content length if provided
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size: {max_size_mb}MB"
            )
        
        # Stream and collect bytes with size checking
        file_bytes = io.BytesIO()
        total_size = 0
        chunk_size = 8192
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                total_size += len(chunk)
                if total_size > max_size_mb * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {max_size_mb}MB"
                    )
                file_bytes.write(chunk)
        
        file_content = file_bytes.getvalue()
        
        if len(file_content) == 0:
            raise ValueError("Downloaded file is empty")
        
        # MIME type detection using python-magic (more reliable than HTTP headers)
        if HAS_PYTHON_MAGIC:
            try:
                detected_mime = magic.from_buffer(file_content, mime=True)
            except Exception:
                # Fallback to HTTP Content-Type header
                detected_mime = response.headers.get('content-type', 'application/octet-stream').split(';')[0]
        else:
            # Basic MIME detection from HTTP headers and file signatures
            detected_mime = response.headers.get('content-type', 'application/octet-stream').split(';')[0]
            
            # Basic file signature detection as fallback
            if detected_mime == 'application/octet-stream' or not detected_mime:
                if file_content.startswith(b'%PDF'):
                    detected_mime = 'application/pdf'
                elif file_content.startswith(b'\xff\xd8\xff'):
                    detected_mime = 'image/jpeg'
                elif file_content.startswith(b'\x89PNG'):
                    detected_mime = 'image/png'
        
        # Validate supported MIME types
        supported_mimes = {
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg', 
            'image/png': 'png',
            'application/pdf': 'pdf'
        }
        
        if detected_mime not in supported_mimes:
            raise ValueError(
                f"Unsupported file type: {detected_mime}. "
                f"Supported types: {', '.join(supported_mimes.keys())}"
            )
        
        print(f"✅ Successfully streamed {len(file_content)} bytes with MIME type: {detected_mime}")
        return file_content, detected_mime
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download document from URL: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing URL: {str(e)}"
        )


# Create router for URL ingestion
url_ingest_router = APIRouter(tags=["URL Document Ingestion"])


@url_ingest_router.post("/extract/url-ingest")
async def extract_document_from_url(request: URLIngestRequest):
    """
    On-the-fly document ingestion from HTTPS URL.
    
    Safely streams document, detects MIME type, normalizes in memory,
    runs existing extractor, and returns structured JSON result.
    
    Features:
    - HTTPS-only for security
    - MIME type detection via python-magic
    - Size limits to prevent abuse  
    - No file persistence - everything in memory
    - Integrates with existing document processor
    
    Args:
        request: URLIngestRequest with url and processing options
        
    Returns:
        JSON response with structured extraction results
    """
    try:
        # Step 1: Safe streaming and MIME detection
        print(f"🌐 Starting URL ingestion for: {request.url}")
        file_content, detected_mime = safe_stream_and_detect_mime(str(request.url))
        
        # Step 2: Map MIME type to file extension for existing processor
        mime_to_ext = {
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/png': 'png', 
            'application/pdf': 'pdf'
        }
        file_extension = mime_to_ext[detected_mime]
        
        print(f"📄 Processing {file_extension.upper()} document ({len(file_content)} bytes)")
        
        # Step 3: Run existing document processor (in-memory)
        if request.structured:
            # Use structured extraction path
            ocr_results, structured_documents, relevant_fields = await process_document(
                file_content=file_content,
                file_extension=file_extension,
                extract_structured=True
            )
            
            # Convert to JSON-serializable format
            serializable_documents = convert_fields_to_dict(structured_documents)
            serializable_relevant_fields = convert_fields_to_dict(relevant_fields)
            
            result = {
                "success": True,
                "source": "url_ingest",
                "url": str(request.url),
                "mime_type": detected_mime,
                "file_extension": file_extension,
                "file_size_bytes": len(file_content),
                "structured_data": serializable_relevant_fields,
                "document_count": len(structured_documents)
            }
            
            # Include raw data if requested
            if request.include_raw:
                result["raw_ocr"] = ocr_results
                result["raw_structured"] = serializable_documents
                
        else:
            # OCR-only extraction
            ocr_results = await process_document(
                file_content=file_content,
                file_extension=file_extension,
                extract_structured=False
            )
            
            result = {
                "success": True,
                "source": "url_ingest", 
                "url": str(request.url),
                "mime_type": detected_mime,
                "file_extension": file_extension,
                "file_size_bytes": len(file_content),
                "ocr_results": ocr_results
            }
        
        print(f"✅ URL ingestion completed successfully")
        return JSONResponse(content=result)
        
    except HTTPException as he:
        # Re-raise HTTP exceptions as-is
        raise he
    except ValueError as ve:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Handle unexpected errors
        print(f"❌ URL ingestion error: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during URL ingestion: {str(e)}"
        )


@url_ingest_router.get("/extract/url-ingest/test")
async def test_url_ingest(
    url: str = Query(..., description="HTTPS URL to test"),
    dry_run: bool = Query(True, description="Only test download and MIME detection")
):
    """
    Test endpoint for URL ingestion - validates URL accessibility and MIME type.
    
    Args:
        url: HTTPS URL to test
        dry_run: If True, only validates download and MIME (no extraction)
        
    Returns:
        JSON with URL validation results
    """
    try:
        print(f"🧪 Testing URL ingestion for: {url}")
        
        # Test streaming and MIME detection
        file_content, detected_mime = safe_stream_and_detect_mime(url, max_size_mb=10)
        
        result = {
            "success": True,
            "url": url,
            "accessible": True,
            "mime_type": detected_mime,
            "file_size_bytes": len(file_content),
            "supported": detected_mime in ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf']
        }
        
        if not dry_run and result["supported"]:
            # Quick extraction test
            mime_to_ext = {
                'image/jpeg': 'jpg', 'image/jpg': 'jpg',
                'image/png': 'png', 'application/pdf': 'pdf'
            }
            file_extension = mime_to_ext[detected_mime]
            
            ocr_results = await process_document(
                file_content=file_content,
                file_extension=file_extension, 
                extract_structured=False
            )
            
            result["test_extraction"] = {
                "ocr_text_length": sum(len(item.get("text", "")) for item in ocr_results),
                "ocr_items_count": len(ocr_results)
            }
        
        print(f"✅ URL test completed: {result}")
        return JSONResponse(content=result)
        
    except Exception as e:
        error_result = {
            "success": False,
            "url": url,
            "accessible": False,
            "error": str(e)
        }
        print(f"❌ URL test failed: {error_result}")
        return JSONResponse(content=error_result, status_code=400)
