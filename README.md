# Document Extractor & KYC Verification Agent

A production-ready Python system for intelligent document processing and KYC verification that combines OCR technology with AI-powered extraction. Features dual AI processing with **OCR+Text AI (Kimi-K2) primary** and **Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct) fallback** for comprehensive document analysis, along with advanced semantic field understanding and categorization.

## 🚀 Key Features

- **Dual AI Processing**: OCR+Text AI (Kimi-K2) primary with Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct) fallback
- **Multi-Document Support**: 15+ document types including international passports, IDs, licenses, and certificates
- **Intelligent Field Filtering**: Document-specific field extraction with relevance-based filtering
- **Semantic Field Understanding**: Automatic categorization of fields into meaningful groups with relationship detection
- **Field Name Normalization**: Consistent naming conventions across document types
- **Production-Ready API**: FastAPI with comprehensive error handling and validation
- **Modern Web Interface**: Responsive UI with real-time processing feedback
- **Debug Mode**: Optional raw data access for development and integration
- **JSON Schema Validation**: Type-safe data extraction with built-in validation
- **[Advanced Field Processing](docs/field_processing.md)**: Semantic field categorization and normalization

## 🎯 Project Overview

This system accelerates customer onboarding by up to 90%, reduces manual review effort, and strengthens compliance with real-time document verification. It intelligently processes various document types and auto-populates onboarding fields while flagging anomalies.

## 📄 Supported Document Types

The system can extract and process data from a wide range of identity documents:

### Personal Identity Documents
- **International Passports**: International, diplomatic, and service passports with MRZ extraction
- **National ID Cards**: Government-issued identity cards with NIN support
- **Driver's Licenses**: Various classes with vehicle categories and restrictions
- **Voter Registration Cards**: Electoral ID cards and voter slips
- **Birth Certificates**: Birth registration documents
- **Social Security Cards**: Social insurance identification

### Residence & Work Documents
- **Residence Permits**: Temporary and permanent residence cards
- **Work Permits**: Employment authorization documents
- **Visas**: Entry and stay authorization documents

### Additional Documents
- **Corporate Documents**: Business registration certificates
- **Professional Licenses**: Industry-specific certifications

Each document type features specialized field extraction optimized for its unique format and regulatory requirements.

## 🤖 AI Processing Pipeline

### Primary: OCR + Groq Text AI
- **OCR**: PaddleOCR for text extraction
- **Model**: `moonshotai/kimi-k2-instruct`
- **Capability**: Fast structured text processing from extracted OCR text
- **Advantage**: Cost-effective and efficient for most clear documents
- **Use Case**: Primary processing for all document types

### Fallback: Groq Vision AI
- **Model**: `meta-llama/llama-4-scout-17b-16e-instruct`
- **Capability**: Direct image analysis for structured data extraction
- **Advantage**: Handles poor quality images, handwritten text, and complex layouts
- **Use Case**: Fallback when OCR quality is insufficient or produces incomplete data

### JSON Schema Validation
- Built-in type compliance using Groq's JSON schema support
- Eliminates manual data cleaning and validation
- Ensures consistent, type-safe responses

## 🛠️ Setup and Installation

### Prerequisites

- Python 3.8+ (recommended: Python 3.9-3.11)
- Groq API key for AI processing
- Git for repository cloning

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

# Set up environment variables
cp .env.example .env
# Edit .env file to add your Groq API key:
# GROQ_API_KEY=your_groq_api_key_here

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# Required: Groq API Key for AI processing
GROQ_API_KEY=your_groq_api_key_here

# Optional: Alternative AI providers (for fallback)
OPENAI_API_KEY=your_openai_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_REFERER=http://localhost:8000
OPENROUTER_TITLE=Document Extractor KYC

# Application settings
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

## 📚 API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Web Interface**: http://localhost:8000

## 🔌 API Endpoints

### Document Processing

#### `POST /api/extract`

Extract text and optionally structured data from documents.

**Parameters:**
- `file` (required): Document file (PDF, JPG, PNG, JPEG)
- `structured` (query, optional): Extract structured data using AI (default: false)
- `include_raw` (query, optional): Include complete raw JSON for debugging (default: false)

**Example Requests:**

```bash
# Basic OCR extraction
curl -X POST "http://localhost:8000/api/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@passport.jpg"

# Structured data extraction
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drivers_license.pdf"

# Debug mode with raw data
curl -X POST "http://localhost:8000/api/extract?structured=true&include_raw=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@national_id.png"
```

**Response Examples:**

```json
{
  "filename": "passport.jpg",
  "ocr_results": [
    {"text": "PASSPORT", "confidence": 0.99},
    {"text": "JOHN DOE", "confidence": 0.95}
  ],
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

#### `POST /api/analyze`

Direct structured data extraction (always returns structured data).

**Response Model:** `DocumentData`

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

## 📊 DocumentData Model

The system uses a comprehensive DocumentData schema to capture various document types:

```python
class DocumentData(BaseModel):
    # Core identity fields (common to most documents)
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
    nin: Optional[str]                    # National Identification Number
    id_card_type: Optional[str]
    
    # International Passport specific
    mrz_lines: Optional[List[str]]        # Machine Readable Zone
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

The system intelligently filters fields based on document type to provide clean, relevant data:

### Document-Specific Field Mappings

- **International Passports**: Core identity + MRZ + passport type + travel document fields
- **National IDs**: Core identity + NIN + card type + validity dates
- **Driver's Licenses**: Core identity + license class + vehicle categories + restrictions
- **Voter Cards**: Core identity + voting district + voter number + polling unit
- **Birth Certificates**: Core identity + birth registration + parental information

### Filtering Benefits

- **Clean UI**: Only relevant fields displayed in frontend
- **Efficient Processing**: Reduced payload sizes
- **Type Safety**: Document-appropriate field validation
- **Extensibility**: Easy addition of new document types

## 🚀 Development & Integration

### Debug Mode

For development and third-party integration, enable debug mode in the frontend:

1. Uncomment the debug checkbox in `templates/index_new.html` (line ~90-130)
2. Uncomment the `debugMode` property in JavaScript (line ~387)
3. Uncomment debug API logic and logging (lines ~440-476)
4. Reload the page

**Debug mode provides:**

- Complete raw JSON data alongside filtered results
- Detailed console logging for API responses
- Processing method tracking (Vision vs OCR+LLM)
- Integration-friendly data access

### Adding New Document Types

1. **Update DocumentData Model**: Add document-specific fields in `app/models/document_data.py`
2. **Add Field Mapping**: Update `get_relevant_fields()` in `app/services/llm_extractor.py`
3. **Update Prompts**: Enhance AI prompts to handle new document structure
4. **Test Integration**: Verify extraction with sample documents

### Frontend Customization

The system uses Alpine.js for reactive UI components:

- **File Upload**: Drag-and-drop with preview
- **Processing Options**: Structured extraction toggle
- **Results Display**: Document-specific field sections
- **Error Handling**: User-friendly error messages

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

### Core Dependencies

- **FastAPI**: Modern web framework for APIs
- **Groq**: AI processing for vision and text models
- **PaddleOCR**: Optical Character Recognition
- **Pydantic**: Data validation and parsing
- **Pillow**: Image processing
- **python-multipart**: File upload handling

### AI Models

- **Vision**: `meta-llama/llama-4-scout-17b-16e-instruct` (Groq)
- **Text**: `moonshotai/kimi-k2-instruct` (Groq)
- **Fallback**: OpenAI/OpenRouter models (optional)

See `requirements.txt` for complete dependency list with versions.

## 🔒 Security & Compliance

### Data Handling

- **No Storage**: Documents processed in memory only
- **No Caching**: No persistent document storage
- **Secure Processing**: AI processing via encrypted HTTPS
- **Privacy First**: No document data retained after processing

### API Security

- File type validation and size limits
- Error handling without data exposure
- Input sanitization and validation
- CORS configuration for production deployment

## 🌐 Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```env
GROQ_API_KEY=your_production_groq_key
HOST=0.0.0.0
PORT=8000
DEBUG=False
WORKERS=4
```

### Health Checks

The application includes health check endpoints:

- `GET /health`: Basic health status
- `GET /health/ready`: Readiness probe for K8s

## 📈 Performance

### Processing Times

- **OCR + Text AI**: ~2-3 seconds for primary processing of clear documents
- **Vision AI**: ~3-4 seconds for fallback processing of complex/poor quality images
- **Document Types**: Consistent performance across all supported formats

### Scalability

- Stateless design for horizontal scaling
- Memory-efficient processing with automatic cleanup
- Configurable worker processes for concurrent requests

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation for API changes
- Test with multiple document types

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support & Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure GROQ_API_KEY is set in .env file
2. **File Upload Failures**: Check file format (PDF, JPG, PNG, JPEG only)
3. **Extraction Errors**: Enable debug mode for detailed error analysis

### Getting Help

- Check the [API Documentation](docs/API.md) for detailed endpoint information
- Review [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for common solutions
- Open an issue on GitHub for bugs or feature requests

---

## 📊 Quick Reference

| Feature | Status | Description |
|---------|--------|-------------|
| ✅ Vision LLM | Production | Groq meta-llama/llama-4-scout-17b-16e-instruct direct image processing |
| ✅ OCR+LLM | Production | PaddleOCR + Groq Kimi-K2 fallback |
| ✅ Multi-Document | Production | 15+ document types supported |
| ✅ Field Filtering | Production | Document-specific relevant field extraction |
| ✅ Debug Mode | Ready | Optional raw data access for development |
| ✅ JSON Schema | Production | Type-safe validation and parsing |
| ✅ Web Interface | Production | Modern responsive UI with Alpine.js |

**Ready for production use with comprehensive document processing capabilities!**
