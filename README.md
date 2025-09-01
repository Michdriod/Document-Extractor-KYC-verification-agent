# Document Extractor & KYC Verification Agent

A production-ready Python system for intelligent document processing and KYC verification that combines OCR technology with AI-powered extraction. Features dual AI processing with OCR+Text AI (Kimi-K2) primary and Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct) fallback, plus semantic field categorization and normalization.

## 🚀 Key Features

- Dual AI Processing: OCR+Text AI (Kimi-K2) primary with Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct) fallback
- Multi-Document Support: 15+ document types including passports, IDs, licenses, and certificates
- Intelligent Field Filtering: Document-specific field extraction with relevance-based filtering
- Semantic Field Understanding: Field categorization with related/primary fields
- Field Name Normalization: Consistent naming across document types
- Production-Ready API: FastAPI with robust validation and error handling
- Modern Web Interface: Responsive UI with real-time feedback
- Debug Mode: Optional raw JSON for development/integration
- JSON Schema Validation: Type-safe outputs

## 🎯 Project Overview

This system accelerates onboarding, reduces manual review, and strengthens compliance via real-time document verification. It auto-populates form fields, flags anomalies, and supports many global identity documents.

## 📄 Supported Document Types


### Personal Identity Documents

- Social Security Cards

### Residence & Work Documents

- Residence Permits
- Work Permits
- Visas

### Additional Documents

- Corporate Documents
- Professional Licenses

Each document type features specialized field extraction optimized for its format and regulations.

## 🤖 AI Processing Pipeline

### Primary: OCR + Groq Text AI

- OCR: PaddleOCR for text extraction
- Model: moonshotai/kimi-k2-instruct
- Best for: Clear scans/photos with readable text

### Fallback: Groq Vision AI

- Model: meta-llama/llama-4-scout-17b-16e-instruct
- Best for: Complex layouts, handwriting, low-quality images

### JSON Schema Validation


## 🛠️ Setup and Installation

### Prerequisites

- Python 3.8+ (recommended: 3.9–3.11)
- Groq API key
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/Michdriod/Document-Extractor-KYC-verification-agent.git
cd Document-Extractor-KYC-verification-agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_groq_api_key_here

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Configuration

Create a .env file in the project root:

```env
# Required: Groq API Key for AI processing
GROQ_API_KEY=your_groq_api_key_here

# Application settings
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

## 📚 Docs & Examples

- API Reference: docs/API.md
- Integration Examples (curl, Python, Node): docs/INTEGRATION_EXAMPLES.md
- Field Processing: docs/field_processing.md

Interactive docs when running locally:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Web App: [http://localhost:8000](http://localhost:8000)

## 🔌 API Endpoints

### POST /api/extract

Extract text and optionally structured data from a single document.

Inputs:

- Provide one of: file upload, HTTPS url, or local path (trusted env only)

Parameters:

- file (multipart, optional): PDF, JPG, PNG, JPEG
- url (JSON/form, optional): HTTPS URL to the document (MIME-sniffed and validated)
- path (JSON/form, optional): Absolute local path (use only in secure deployments)
- structured (query): true/false (default: false) to return structured fields
- include_raw (query): true/false (default: false) to include raw JSON

Examples:

```bash
# Basic OCR extraction
curl -X POST "http://localhost:8000/api/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@passport.jpg"

# Structured extraction from file
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drivers_license.pdf"

# Structured extraction from URL (HTTPS only)
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/sample_id.png"}'

# Structured extraction from local path (trusted env only)
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"path": "/secure/input/documents/passport.jpg"}'
```

Response example (structured=true):

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
    "extraction_method": "Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct)"
  }
}
```

### POST /api/extract/enhanced

End-to-end extraction with OCR + AI and semantic enrichment.

Returns:

- documents: array of extracted documents (supports multi-page/multi-doc)
- categories: semantic grouping of fields
- primary_fields: most important fields per document type
- related_fields: helpful field relationships/suggestions
- metadata: processing details and timing

Use when you want clean, enriched data ready for forms or downstream systems.

### POST /api/analyze

Direct structured data extraction (always returns structured data).

Response Model: DocumentData

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

## 📊 DocumentData Model

The system uses a comprehensive model to capture various document types:

```python
class DocumentData(BaseModel):
    # Core identity fields (common)
    document_type: str
    surname: str
    given_names: str
    date_of_birth: Optional[str]
    document_number: str

    # Geographic and authority information
    country: Optional[str]
    nationality: Optional[str]
    issuing_authority: Optional[str]

    # Personal details
    sex: Optional[str]

    # Document validity
    date_of_issue: Optional[str]
    date_of_expiry: Optional[str]

    # Document-specific fields

    # National ID specific
    nin: Optional[str]
    id_card_type: Optional[str]

    # International Passport specific
    mrz_lines: Optional[List[str]]
    passport_type: Optional[str]

    # Driver's license specific
    license_class: Optional[str]
    vehicle_categories: Optional[List[str]]
    restrictions: Optional[str]
    endorsements: Optional[str]

    # Voter registration specific
    voting_district: Optional[str]
    voter_number: Optional[str]
    polling_unit: Optional[str]
    voter_status: Optional[str]

    # Birth certificate specific
    birth_registration_number: Optional[str]
    place_of_birth: Optional[str]
    father_name: Optional[str]
    mother_name: Optional[str]

    # Processing metadata
    extraction_method: str = "OCR"
    confidence_score: Optional[float]
```

## 🔧 Field Filtering System

The system intelligently filters fields by document type to provide clean, relevant data.

### Document-Specific Field Mappings

- International Passports: Core identity + MRZ + passport type + travel document fields
- National IDs: Core identity + NIN + card type + validity dates
- Driver's Licenses: Core identity + license class + vehicle categories + restrictions
- Voter Cards: Core identity + voting district + voter number + polling unit
- Birth Certificates: Core identity + birth registration + parental information

### Filtering Benefits

- Clean UI
- Reduced payload sizes
- Document-appropriate validation
- Easy addition of new document types

## 🚀 Development & Integration

### Debug Mode

Enable debug mode in the frontend to access raw data and logs:

1. Uncomment the debug checkbox in templates/index_new.html (around line 90–130)
2. Uncomment the debugMode property in JavaScript (around line 387)
3. Uncomment debug API logic and logging (around lines 440–476)

### Adding New Document Types

1. Update DocumentData in app/models/document_data.py
2. Update get_relevant_fields() in app/services/llm_extractor.py
3. Update prompts for new structures
4. Test with sample documents

### Frontend Customization

- File upload: Drag-and-drop with preview
- Structured extraction toggle
- Document-specific results sections
- User-friendly error handling

## 🧪 Testing

```bash
# Run tests
python -m pytest tests/ -v

# Test specific document types
python -m pytest tests/test_document_types.py -v

# Test API endpoints
python -m pytest tests/test_api.py -v
```

## 📦 Dependencies

- FastAPI
- Groq (vision + text models)
- PaddleOCR
- Pydantic
- Pillow
- python-multipart

AI Models:

- Vision: meta-llama/llama-4-scout-17b-16e-instruct (Groq)
- Text: moonshotai/kimi-k2-instruct (Groq)

See requirements.txt for full versions.

## 🔒 Security & Compliance

### Data Handling

- No Storage: Processed in memory only
- No Caching: No persistent document storage
- Secure Processing: Encrypted HTTPS to AI services
- Privacy First: No data retained after processing
- Remote URLs: HTTPS-only fetching with MIME sniffing and signature checks; no persistence

### API Security

- File type validation and size limits
- Input sanitization and validation
- CORS configuration for production

## 🌐 Production Deployment

### Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment (production)

```env
GROQ_API_KEY=your_production_groq_key
HOST=0.0.0.0
PORT=8000
DEBUG=False
WORKERS=4
```

### Health Checks

- GET /health: Basic health status
- GET /health/ready: Readiness probe (e.g., for Kubernetes)

## 📈 Performance

- OCR + Text AI: ~2–3s typical for clear docs
- Vision AI: ~3–4s for complex/low-quality images
- Stateless design and memory-efficient processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (git checkout -b feature/your-change)
3. Commit (git commit -m "Describe your change")
4. Push (git push origin feature/your-change)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8
- Add tests for new features
- Update documentation for API changes
- Test with multiple document types

## 📄 License

MIT License (see LICENSE)

## 🆘 Support & Troubleshooting

### Common Issues

1. API Key Errors: Ensure GROQ_API_KEY is set in .env
2. File Upload Failures: Check file format (PDF, JPG, PNG, JPEG)
3. Extraction Errors: Enable debug mode for detailed logs

### Getting Help

- API Documentation: docs/API.md
- Integration Examples: docs/INTEGRATION_EXAMPLES.md
- Troubleshooting: docs/TROUBLESHOOTING.md
- Issues: GitHub repository

## 📊 Quick Reference

| Feature | Status | Description |
|--------|--------|-------------|
| ✅ Vision LLM | Production | Groq meta-llama/llama-4-scout-17b-16e-instruct direct image processing |
| ✅ OCR+LLM | Production | PaddleOCR + Groq Kimi-K2 primary |
| ✅ Enhanced Endpoint | Production | /api/extract/enhanced with categorization and primary/related fields |
| ✅ Multi-Document | Production | 15+ document types supported |
| ✅ Field Filtering | Production | Document-specific relevant field extraction |
| ✅ Debug Mode | Ready | Optional raw data access |
| ✅ JSON Schema | Production | Type-safe validation and parsing |
| ✅ Web Interface | Production | Modern responsive UI |

Ready for production use with comprehensive document processing capabilities!
