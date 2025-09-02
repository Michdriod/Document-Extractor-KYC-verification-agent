# API routers

Routers mounted under `/api`:

- `document_router` (`endpoints.py`): Basic extraction and analyze endpoints. Now accepts file, URL (HTTP/HTTPS), or local path. URL inputs use a shared ingestion helper with MIME detection.
- `enhanced_router` (`enhanced_endpoints.py`): Multi-page/multi-doc extraction with categorization, primary/related fields, and metadata. Accepts file, URL, or path.
- `url_ingest_router` (`url_ingest_endpoints.py`): HTTPS-only ingestion with robust streaming, MIME sniffing, and size limits.

Key guarantees:

- No raw OCR arrays are returned in any response
- All endpoints return JSON only
- URL handling is consistent across endpoints (shared helper); `/extract/url-ingest` is strict HTTPS-only

Quick usage examples:

```bash
# Structured extraction from URL via /api/extract (JSON body)
curl -X POST "http://localhost:8000/api/extract?structured=true" \
	-H "accept: application/json" \
	-H "Content-Type: application/json" \
	-d '{"url": "https://example.com/sample.png"}'

# Enhanced extraction from URL (multi-page PDFs supported)
curl -X POST "http://localhost:8000/api/extract/enhanced?url=https://example.com/doc.pdf"

# Strict HTTPS-only ingestion path (size/MIME checks)
curl -X POST "http://localhost:8000/api/extract/url-ingest" \
	-H "Content-Type: application/json" \
	-d '{"url": "https://example.com/sample.pdf", "structured": true}'
```
