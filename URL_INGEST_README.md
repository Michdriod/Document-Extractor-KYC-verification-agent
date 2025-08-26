# URL Ingestion Endpoint Documentation

## Overview

The new URL ingestion endpoint provides on-the-fly document processing from HTTPS URLs without file persistence. It safely streams documents, detects MIME types, normalizes them in memory, runs your existing extractor, and returns structured JSON results.

## Endpoints

### 1. Main Extraction Endpoint

**POST** `/api/extract/url-ingest`

Extract structured data from a document at an HTTPS URL.

#### Request Body (JSON):
```json
{
  "url": "https://example.com/document.pdf",
  "structured": true,
  "include_raw": false
}
```

#### Parameters:
- `url` (required): HTTPS URL to the document (PDF, PNG, JPEG only)
- `structured` (optional): Whether to extract structured data using LLM (default: true)
- `include_raw` (optional): Include raw OCR and structured data in response (default: false)

#### Response:
```json
{
  "success": true,
  "source": "url_ingest",
  "url": "https://example.com/document.pdf",
  "mime_type": "application/pdf",
  "file_extension": "pdf",
  "file_size_bytes": 45023,
  "structured_data": [...],
  "document_count": 1
}
```

### 2. Test Endpoint

**GET** `/api/extract/url-ingest/test`

Test URL accessibility and MIME type detection.

#### Parameters:
- `url` (required): HTTPS URL to test
- `dry_run` (optional): Only test download and MIME detection (default: true)

#### Response:
```json
{
  "success": true,
  "url": "https://example.com/document.pdf",
  "accessible": true,
  "mime_type": "application/pdf",
  "file_size_bytes": 45023,
  "supported": true
}
```

## Security Features

1. **HTTPS Only**: Only accepts HTTPS URLs for security
2. **Size Limits**: Maximum file size of 50MB to prevent abuse
3. **MIME Validation**: Uses python-magic for reliable MIME type detection
4. **No Persistence**: Files are processed entirely in memory, never saved to disk
5. **Timeout Protection**: 30-second timeout for downloads

## Supported File Types

- **Images**: PNG, JPEG/JPG
- **Documents**: PDF (first page extracted as image)

## Usage Examples

### Python with requests:
```python
import requests

# Basic extraction
response = requests.post("http://localhost:8000/api/extract/url-ingest", json={
    "url": "https://example.com/document.pdf",
    "structured": True
})

if response.status_code == 200:
    result = response.json()
    print(f"Extracted {result['document_count']} documents")
    print(f"File type: {result['mime_type']}")
    print(f"Structured data: {result['structured_data']}")
```

### cURL:
```bash
# Test URL accessibility
curl -X GET "http://localhost:8000/api/extract/url-ingest/test?url=https://example.com/document.pdf"

# Extract document
curl -X POST "http://localhost:8000/api/extract/url-ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/document.pdf",
    "structured": true,
    "include_raw": false
  }'
```

### JavaScript/fetch:
```javascript
// Test URL
const testResponse = await fetch('/api/extract/url-ingest/test?url=' + encodeURIComponent(documentUrl));
const testResult = await testResponse.json();

if (testResult.success && testResult.supported) {
    // Extract document
    const extractResponse = await fetch('/api/extract/url-ingest', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            url: documentUrl,
            structured: true,
            include_raw: false
        })
    });
    
    const extractResult = await extractResponse.json();
    console.log('Extraction result:', extractResult);
}
```

## Error Handling

The endpoint returns appropriate HTTP status codes:

- **200**: Success
- **400**: Bad request (invalid URL, unsupported file type, download failed)
- **413**: File too large
- **500**: Internal server error

Error responses include details:
```json
{
  "detail": "Unsupported file type: text/html. Supported types: image/jpeg, image/png, application/pdf"
}
```

## Integration with Existing Code

The URL ingestion endpoint integrates seamlessly with your existing document processing pipeline:

1. Uses your existing `process_document()` function
2. Leverages your `convert_fields_to_dict()` serialization
3. Returns the same structured data format as other endpoints
4. Applies the same field cleaning and confidence filtering

No changes to your existing code are required - this is a new, additive endpoint that runs in parallel with your current functionality.
