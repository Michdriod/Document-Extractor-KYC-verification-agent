# API Documentation

## Document Extractor & KYC Verification Agent API

This document provides comprehensive API documentation for the Document Extractor & KYC Verification Agent, including endpoint specifications, request/response examples, and integration guidelines.

## Base URL

```
http://localhost:8000  # Development
https://your-domain.com  # Production
```

## Authentication

Currently, the API does not require authentication. For production deployments, consider implementing:

- API key authentication
- OAuth 2.0 integration
- Rate limiting per client

## Content Types & Inputs

- File uploads: `multipart/form-data`
- URL or local path ingestion: query parameters or JSON body (`url` or `path`)
- All endpoints return `application/json` responses.

---

## Endpoints

### 1) Document Extraction (single-document friendly)

Extract text and optionally structured data from documents. Accepts file upload, HTTPS URL, or local file path.

#### `POST /api/extract`

**Description:** Primary endpoint for document processing with flexible output options.

**Parameters (query/form):**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file` | File | No | - | Document file (PDF, JPG, JPEG, PNG) |
| `url` | String | No | - | HTTPS link to image or PDF (no extension required) |
| `path` | String | No | - | Local file path (for trusted/internal use only) |
| `structured` | Boolean | No | `false` | Extract structured data using AI |
| `include_raw` | Boolean | No | `false` | Include complete raw JSON data |

At least one of `file`, `url`, or `path` must be provided.

**Supported Formats:**

- PDF (`.pdf`)
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)


**Maximum File Size:** 10MB

#### Request Examples

##### Basic OCR Extraction (file)

```bash
curl -X POST "http://localhost:8000/api/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

##### Structured Data Extraction

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@passport.jpg"
```

##### Debug Mode (with Raw Data)

##### URL Ingestion (no file upload)

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/sample.pdf"}'
```

##### Local Path (internal use)

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"path": "/absolute/path/to/document.png"}'
```

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true&include_raw=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drivers_license.png"
```

#### Response Schemas

##### Basic OCR Response (`structured=false`)

```json
{
  "filename": "document.pdf",
  "message": "Set structured=true to receive extracted JSON fields. Raw OCR lines are not returned."
}
```

##### Structured Data Response (`structured=true`)

```json
{
  "filename": "passport.jpg",
  "structured_data": {
    "document_type": "International Passport",
    "given_names": "JOHN",
    "surname": "DOE",
    "document_number": "123456789",
    "date_of_birth": "1990-01-01",
    "date_of_expiry": "2030-01-01",
    "country": "USA",
    "nationality": "American",
    "passport_type": "P",
  "extraction_method": "Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct)"
  }
}
```

##### Debug Response (`include_raw=true`)

```json
{
  "filename": "national_id.png",
  "structured_data": {
    "document_type": "National ID",
    "given_names": "JANE",
    "surname": "SMITH",
    "document_number": "ID123456789",
    "nin": "12345678901",
    "extraction_method": "OCR+LLM (Kimi-K2)"
  },
  "raw_structured_data": {
    "document_type": "National ID",
    "given_names": "JANE",
    "surname": "SMITH",
    "document_number": "ID123456789",
    "nin": "12345678901",
    "date_of_birth": "1985-05-15",
    "country": "Nigeria",
    "issuing_authority": "NIMC",
    "date_of_issue": "2020-01-01",
    "date_of_expiry": null,
    "extraction_method": "OCR+LLM (Kimi-K2)",
    "confidence_score": 0.92,
    "additional_fields": "..."
  }
}
```

---

### 2) Document Analysis (always structured) — Deprecated alias

Direct structured data extraction that always returns structured data.

#### `POST /api/analyze`

**Description:** Deprecated alias for `/api/extract?structured=true`. Prefer using `/api/extract` with `structured=true` for consistency across inputs and options. Existing integrations will continue to work.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | Document file (PDF, JPG, JPEG, PNG) |

#### Request Example

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"

# or with URL
curl -X POST "http://localhost:8000/api/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/sample.png"}'
```

#### Response Schema

Returns a complete `DocumentData` object:

```json
{
  "document_type": "Driver's License",
  "given_names": "MICHAEL",
  "surname": "JOHNSON",
  "document_number": "DL789012345",
  "date_of_birth": "1988-03-22",
  "date_of_expiry": "2028-03-22",
  "country": "USA",
  "license_class": "C",
  "vehicle_categories": ["MOTORCYCLE", "PASSENGER CAR"],
  "restrictions": "CORRECTIVE LENSES",
  "extraction_method": "Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct)",
  "confidence_score": 0.94
}
```

---

### 3) Enhanced Extraction (multi-document friendly)

Processes inputs that may contain multiple documents or long multi-page files, and returns an array of documents with rich metadata and field organization.

#### `POST /api/extract/enhanced`

**Parameters (query/form):** same as `/api/extract` (`file`, `url`, `path`).
Request example (URL):

```bash
curl -X POST "http://localhost:8000/api/extract/enhanced?url=https://example.com/doc.pdf"
```

**Response (simplified):**

```json
{
  "documents": [
    {
      "extraction_status": "success",
      "data": {
        "fields": { "surname": {"value": "DOE", "confidence": 0.96 }, "document_number": {"value": "A123...", "confidence": 0.93 } },
        "categorized_fields": { "personal_information": {"surname": {"value": "DOE", "confidence": 0.96 }} },
        "primary_fields": { "full_name": {"value": "JOHN DOE", "confidence": 0.95 }, "document_number": {"value": "A123...", "confidence": 0.93 } },
        "related_fields": [ { "field1": "date_of_issue", "field2": "date_of_expiry", "score": 0.82 } ]
      }
    }
  ],
  "metadata": {
    "filename": "document.pdf",
    "processing_time_ms": 1820,
    "ocr_text_length": 1245,
    "source_type": "url|file|path",
    "source_url": "https://example.com/document.pdf"
  }
}
```

Use this endpoint when a single file may contain multiple distinct documents or when you want richer organization (categories, primary/related fields) out of the box.

---

### 4) Health Check Endpoints

#### `GET /health`

Basic health status endpoint.

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-08-05T10:30:00Z"
}
```

#### `GET /health/ready`

Readiness probe for container orchestration.

**Response:**

```json
{
  "status": "ready",
  "services": {
    "groq_api": "connected",
    "ocr_engine": "ready"
  }
}
```

---

## DocumentData Schema

Complete schema for structured document data:

```json
{
  "type": "object",
  "properties": {
    "document_type": {
      "type": "string",
      "description": "Type of document (International Passport, National ID, Driver's License, etc.)"
    },
    "given_names": {
      "type": "string",
      "description": "First/given names"
    },
    "surname": {
      "type": "string", 
      "description": "Last/family name"
    },
    "document_number": {
      "type": "string",
      "description": "Unique document identifier"
    },
    "date_of_birth": {
      "type": "string",
      "format": "date",
      "description": "Date of birth (YYYY-MM-DD)"
    },
    "country": {
      "type": "string",
      "description": "Issuing country"
    },
    "nationality": {
      "type": "string",
      "description": "Holder's nationality"
    },
    "sex": {
      "type": "string",
      "enum": ["M", "F", "Male", "Female"],
      "description": "Gender"
    },
    "date_of_issue": {
      "type": "string",
      "format": "date",
      "description": "Document issue date"
    },
    "date_of_expiry": {
      "type": "string",
      "format": "date",
      "description": "Document expiry date"
    },
    "issuing_authority": {
      "type": "string",
      "description": "Authority that issued the document"
    },
    "nin": {
      "type": "string",
      "description": "National Identification Number"
    },
    "mrz_lines": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Machine Readable Zone lines (international passports)"
    },
    "passport_type": {
      "type": "string",
      "description": "Type of international passport (P, D, S, etc.)"
    },
    "license_class": {
      "type": "string",
      "description": "Driver's license class"
    },
    "vehicle_categories": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Authorized vehicle categories"
    },
    "restrictions": {
      "type": "string",
      "description": "License restrictions"
    },
    "voting_district": {
      "type": "string",
      "description": "Electoral district"
    },
    "voter_number": {
      "type": "string",
      "description": "Voter registration number"
    },
    "extraction_method": {
      "type": "string",
      "description": "AI method used for extraction"
    },
    "confidence_score": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Extraction confidence (0-1)"
    }
  },
  "required": ["document_type", "given_names", "surname", "document_number"]
}
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Description | Typical Causes |
|------|-------------|----------------|
| 200 | Success | Request processed successfully |
| 400 | Bad Request | Invalid file format, missing required fields |
| 413 | Request Entity Too Large | File size exceeds limit (10MB) |
| 422 | Unprocessable Entity | Invalid request parameters |
| 500 | Internal Server Error | Processing error, AI service unavailable |

### Common Error Examples

#### Invalid File Format

```json
{
  "detail": "Unsupported file format. Allowed formats: pdf, jpg, jpeg, png"
}
```

#### Processing Error

```json
{
  "detail": "Error processing document: Unable to extract text from image"
}
```

#### AI Service Error

```json
{
  "detail": "Error processing document: Groq API service temporarily unavailable"
}
```

---

## Integration Guidelines

### Python Integration

```python
import requests

def extract_document(file_path, structured=True, include_raw=False):
    url = "http://localhost:8000/api/extract"
    params = {
        "structured": structured,
        "include_raw": include_raw
    }
    
    with open(file_path, 'rb') as file:
        files = {'file': file}
        response = requests.post(url, files=files, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API Error: {response.json()['detail']}")

# Usage
result = extract_document("passport.jpg", structured=True)
print(result['structured_data'])
```

### JavaScript Integration

```javascript
async function extractDocument(file, structured = true, includeRaw = false) {
    const formData = new FormData();
    formData.append('file', file);
    
    const params = new URLSearchParams({
        structured: structured,
        include_raw: includeRaw
    });
    
    try {
        const response = await fetch(`/api/extract?${params}`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Document extraction error:', error);
        throw error;
    }
}

// Usage
const fileInput = document.getElementById('file-input');
const file = fileInput.files[0];
const result = await extractDocument(file, true);
console.log(result.structured_data);
```

### Node.js Integration

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function extractDocument(filePath, structured = true, includeRaw = false) {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    
    const url = `http://localhost:8000/api/extract?structured=${structured}&include_raw=${includeRaw}`;
    
    try {
        const response = await axios.post(url, form, {
            headers: form.getHeaders()
        });
        return response.data;
    } catch (error) {
        throw new Error(`API Error: ${error.response.data.detail}`);
    }
}

// Usage
extractDocument('./document.pdf', true)
    .then(result => console.log(result.structured_data))
    .catch(error => console.error(error));
```

---

## AI Processing Details

### Primary: OCR + Text AI (Groq Kimi-K2)

- **OCR Engine**: PaddleOCR for text extraction
- **Text Model**: `moonshotai/kimi-k2-instruct`
- **Processing**: OCR text extraction followed by AI structuring
- **Strengths**: Fast, cost-effective, handles most clear documents efficiently
- **Typical Response Time**: 2-3 seconds
- **Extraction Method**: "OCR+LLM (Kimi-K2)"

### Fallback: Vision LLM (Groq meta-llama/llama-4-scout-17b-16e-instruct)

- **Model**: `meta-llama/llama-4-scout-17b-16e-instruct`
- **Processing**: Direct image analysis without OCR preprocessing
- **Strengths**: Handles complex layouts, handwritten text, poor image quality
- **Use Case**: When OCR processing is insufficient or produces incomplete data
- **Typical Response Time**: 3-4 seconds
- **Extraction Method**: "Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct)"

### JSON Schema Validation

Both AI processing methods use Groq's built-in JSON schema validation to ensure:

- **Type Safety**: All fields conform to expected data types
- **Structure Compliance**: Response matches DocumentData schema
- **No Manual Parsing**: Eliminates post-processing validation needs
- **Error Reduction**: Catches format issues at the AI level

---

## Field Filtering System

The API includes intelligent field filtering to provide clean, document-relevant data:

### Document Type Mappings

| Document Type | Key Fields | Filtered Fields |
|---------------|------------|-----------------|
| **International Passport** | Core identity, MRZ, passport type, travel info | Document-specific: mrz_lines, passport_type, country |
| **National ID** | Core identity, NIN, validity dates | Document-specific: nin, id_card_type |
| **Driver's License** | Core identity, license class, vehicle categories | Document-specific: license_class, vehicle_categories, restrictions |
| **Voter Card** | Core identity, voting information | Document-specific: voting_district, voter_number, polling_unit |
| **Birth Certificate** | Core identity, birth registration, parental info | Document-specific: birth_registration_number, place_of_birth, father_name, mother_name |

### Filtering Benefits

1. **Clean UI**: Only relevant fields displayed in frontend applications
2. **Reduced Payload**: Smaller response sizes for better performance
3. **Type Consistency**: Document-appropriate field validation
4. **Easy Integration**: Predictable field sets per document type

### Raw Data Access

For development, debugging, or comprehensive integrations, use `include_raw=true` to access:

- Complete unfiltered DocumentData object
- All extracted fields regardless of document type
- Processing metadata and confidence scores
- Full AI response for analysis

---

## Rate Limits & Performance

### Current Limits

- **Concurrent Requests**: 10 per client
- **File Size**: 10MB maximum
- **Request Timeout**: 30 seconds
- **Memory Usage**: Processed in memory, no persistent storage

### Performance Optimization

1. **Image Quality**: Higher quality images improve extraction accuracy
2. **File Format**: PDF and PNG generally perform better than JPEG
3. **File Size**: Smaller files process faster (optimize images before upload)
4. **Concurrency**: Use connection pooling for multiple requests

### Scaling Considerations

- Stateless design enables horizontal scaling
- Memory-efficient processing with automatic cleanup
- Consider implementing request queuing for high-volume scenarios
- Monitor AI service quotas and implement fallback strategies

---

## Security Considerations

### Data Privacy

- **No Storage**: Documents are processed in memory only
- **No Caching**: No persistent storage of document data
- **Automatic Cleanup**: Memory cleared after processing
- **Secure Transmission**: HTTPS encryption for all communications

### Input Validation

- File type restriction (PDF, JPG, PNG, JPEG only)
- File size limits (10MB maximum)
- Content type validation
- Error handling without data exposure

### Production Security

For production deployments, implement:

1. **Authentication**: API key or OAuth 2.0
2. **Rate Limiting**: Per-client request limits
3. **Input Sanitization**: Additional file content validation
4. **Audit Logging**: Request and response logging
5. **Network Security**: VPC/firewall restrictions
6. **Compliance**: GDPR, SOC 2, ISO 27001 considerations

---

## Troubleshooting

### Common Issues

#### 1. "Unsupported file format" Error

**Cause:** File extension not in allowed list
**Solution:** Ensure file is PDF, JPG, JPEG, or PNG format

#### 2. "Error processing document" Error

**Cause:** Various processing issues
**Solutions:**

- Check image quality and clarity
- Ensure document is properly oriented
- Try a different file format
- Enable debug mode for detailed error analysis

#### 3. Empty or Incomplete Structured Data

**Cause:** Poor image quality or unsupported document layout
**Solutions:**

- Improve image resolution and lighting
- Ensure full document is visible in image
- Check document type is supported
- Review raw OCR results for text extraction issues

#### 4. API Timeout Errors

**Cause:** Large file processing or AI service delays
**Solutions:**

- Reduce file size through compression
- Retry request after brief delay
- Check AI service status
- Consider splitting large documents

### Debug Mode Usage

Enable debug mode for detailed troubleshooting:

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true&include_raw=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@problematic_document.pdf"
```

Debug response provides:

- Complete raw extraction data
- Processing method used (Vision vs OCR+LLM)
- Confidence scores
- Full AI response for analysis

---

## Support

For additional support:

1. **Documentation**: Review this API documentation and README
2. **Issues**: Open GitHub issues for bugs or feature requests
3. **Integration Help**: Check integration examples in this document
4. **Performance**: Monitor logs and enable debug mode for analysis

---

Notes:

- Field values are typically returned as objects with `{ value, confidence }` to retain provenance.
- The API converts these to plain JSON when needed for compatibility.

Last updated: September 1, 2025
