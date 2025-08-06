# Troubleshooting Guide

## Document Extractor & KYC Verification Agent

This guide helps you diagnose and resolve common issues when using the Document Extractor & KYC Verification Agent.

## Quick Diagnostics

### Check System Status

1. **API Health Check**
   ```bash
   curl http://localhost:8000/health
   ```
   Expected response: `{"status": "healthy", "timestamp": "..."}`

2. **Service Readiness**
   ```bash
   curl http://localhost:8000/health/ready
   ```
   Expected response: `{"status": "ready", "services": {"groq_api": "connected", ...}}`

3. **Environment Variables**
   ```bash
   # Check if required environment variables are set
   echo $GROQ_API_KEY
   ```

## Common Issues & Solutions

### 1. API Key Problems

#### Symptoms
- `ValueError: Groq API key is required`
- `401 Unauthorized` errors
- `Error processing document: API key invalid`

#### Solutions

**Check Environment Variables:**
```bash
# Verify .env file exists
ls -la .env

# Check if GROQ_API_KEY is set
grep GROQ_API_KEY .env
```

**Set API Key:**
```bash
# Add to .env file
echo "GROQ_API_KEY=your_actual_api_key_here" >> .env

# Restart the application
uvicorn app.main:app --reload
```

**Validate API Key:**
```bash
# Test API key with Groq directly
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.groq.com/openai/v1/models
```

### 2. File Upload Issues

#### Symptoms
- `Unsupported file format` errors
- `Request Entity Too Large` errors
- File upload fails silently

#### Solutions

**Check File Format:**
```python
# Allowed formats
ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]

# Check your file extension
import os
file_extension = os.path.splitext("your_file.pdf")[1].lower()[1:]
print(f"Extension: {file_extension}")
```

**Check File Size:**
```bash
# Check file size (should be < 10MB)
ls -lh your_document.pdf

# Compress PDF if too large
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook \
   -dNOPAUSE -dQUIET -dBATCH -sOutputFile=compressed.pdf input.pdf
```

**Test File Upload:**
```bash
# Test with curl
curl -X POST "http://localhost:8000/api/extract" \
  -F "file=@test_document.pdf" \
  -v
```

### 3. Extraction Quality Issues

#### Symptoms
- Empty or incomplete structured data
- Low confidence scores
- Missing important fields

#### Solutions

**Enable Debug Mode:**
```bash
# Get detailed extraction information
curl -X POST "http://localhost:8000/api/extract?structured=true&include_raw=true" \
  -F "file=@document.pdf"
```

**Image Quality Improvements:**
- **Resolution**: Minimum 300 DPI for scanned documents
- **Lighting**: Ensure even lighting, avoid shadows
- **Orientation**: Ensure document is right-side up
- **Clarity**: Avoid blurry or motion-blurred images

**Document Preparation:**
```python
# Example: Improve image quality with Python
from PIL import Image, ImageEnhance

def improve_image_quality(image_path):
    image = Image.open(image_path)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.2)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.1)
    
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    return image
```

### 4. AI Processing Errors

#### Symptoms
- `Groq API service temporarily unavailable`
- `Processing timeout` errors
- Inconsistent extraction results

#### Solutions

**Check AI Service Status:**
```python
# Test Groq API directly
import requests

def test_groq_api(api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers=headers
    )
    return response.status_code == 200
```

**Implement Retry Logic:**
```python
import time
import requests

def extract_with_retry(file_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            # Your extraction code here
            return extract_document(file_path)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise e
```

**Monitor Rate Limits:**
```bash
# Check response headers for rate limit info
curl -I -X POST "http://localhost:8000/api/extract" \
  -F "file=@document.pdf"
```

### 5. Performance Issues

#### Symptoms
- Slow processing times (>10 seconds)
- High memory usage
- Timeouts on large files

#### Solutions

**Optimize File Size:**
```bash
# Compress images
mogrify -quality 85 -resize 2048x2048\> *.jpg

# Optimize PDFs
pdftk input.pdf output compressed.pdf compress
```

**Monitor Resource Usage:**
```bash
# Check memory usage
ps aux | grep uvicorn

# Monitor disk space
df -h

# Check CPU usage
top -p $(pgrep -f uvicorn)
```

**Performance Testing:**
```python
import time
import requests

def benchmark_extraction(file_path, iterations=5):
    times = []
    for i in range(iterations):
        start_time = time.time()
        
        with open(file_path, 'rb') as f:
            response = requests.post(
                "http://localhost:8000/api/extract?structured=true",
                files={'file': f}
            )
        
        end_time = time.time()
        times.append(end_time - start_time)
    
    avg_time = sum(times) / len(times)
    print(f"Average processing time: {avg_time:.2f} seconds")
    return times
```

### 6. Frontend Integration Issues

#### Symptoms
- CORS errors in browser
- File upload progress not showing
- JavaScript errors in console

#### Solutions

**Enable CORS (if needed):**
```python
# In main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Frontend Debug Mode:**
```javascript
// Enable debug mode in frontend
// 1. Uncomment debug checkbox in HTML
// 2. Uncomment debugMode property in JavaScript
// 3. Check browser console for detailed logs

console.log('Debug mode enabled');
```

**Test Frontend Connection:**
```javascript
// Test API connectivity from browser
fetch('/api/extract', {
    method: 'POST',
    body: new FormData()
}).then(response => {
    console.log('API connection:', response.status);
}).catch(error => {
    console.error('Connection error:', error);
});
```

## Debugging Tools

### 1. Enable Verbose Logging

```python
# In your application
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add detailed logging to your code
logger.debug(f"Processing file: {filename}")
logger.info(f"Extraction method: {extraction_method}")
```

### 2. Request/Response Logging

```bash
# Log all requests and responses
uvicorn app.main:app --reload --log-level debug
```

### 3. Network Analysis

```bash
# Monitor network traffic
sudo tcpdump -i lo port 8000

# Check port availability
netstat -tlnp | grep :8000
```

### 4. Memory and Performance Profiling

```python
# Add memory profiling
import tracemalloc
import psutil
import os

def monitor_memory():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")

# Profile specific functions
tracemalloc.start()
# ... your code ...
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.2f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")
tracemalloc.stop()
```

## Environment-Specific Issues

### Development Environment

**Common Issues:**
- Missing dependencies
- Environment variable conflicts
- Port conflicts

**Solutions:**
```bash
# Clean install
rm -rf venv/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Check port usage
lsof -i :8000

# Reset environment
deactivate
source venv/bin/activate
```

### Production Environment

**Common Issues:**
- HTTPS/SSL certificate problems
- Load balancer configuration
- Environment variable security

**Solutions:**
```bash
# Check SSL certificates
openssl s_client -connect your-domain.com:443

# Verify environment variables are set securely
env | grep -E "(GROQ|API)" || echo "API keys not found"

# Test production endpoints
curl -k https://your-domain.com/health
```

### Docker Environment

**Common Issues:**
- Container resource limits
- Volume mounting problems
- Network connectivity

**Solutions:**
```bash
# Check container logs
docker logs container_name

# Monitor resource usage
docker stats container_name

# Test container connectivity
docker exec -it container_name curl localhost:8000/health
```

## Data Quality Issues

### Poor OCR Results

**Symptoms:**
- Garbled text in OCR results
- Missing text blocks
- Incorrect character recognition

**Solutions:**

1. **Preprocess Images:**
```python
import cv2
import numpy as np

def preprocess_image(image_path):
    image = cv2.imread(image_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply noise reduction
    denoised = cv2.medianBlur(gray, 3)
    
    # Enhance contrast
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = enhanced.apply(denoised)
    
    return enhanced
```

2. **Document Orientation:**
```python
# Check and correct orientation
from PIL import Image

def check_orientation(image_path):
    image = Image.open(image_path)
    
    # Check EXIF orientation
    if hasattr(image, '_getexif'):
        exif = image._getexif()
        if exif and 274 in exif:
            orientation = exif[274]
            # Rotate based on orientation
            if orientation == 3:
                image = image.rotate(180)
            elif orientation == 6:
                image = image.rotate(270)
            elif orientation == 8:
                image = image.rotate(90)
    
    return image
```

### Inconsistent AI Responses

**Symptoms:**
- Different results for same document
- Missing fields in structured data
- Incorrect field mappings

**Solutions:**

1. **Compare Processing Methods:**
```bash
# Test both Vision and OCR+LLM methods
curl -X POST "http://localhost:8000/api/extract?structured=true&include_raw=true" \
  -F "file=@document.pdf" > vision_result.json

# Analyze which method was used
cat vision_result.json | jq '.structured_data.extraction_method'
```

2. **Validate Against Multiple Documents:**
```python
# Test consistency across similar documents
def test_consistency(document_list):
    results = []
    for doc in document_list:
        result = extract_document(doc)
        results.append(result)
    
    # Compare field extraction rates
    field_counts = {}
    for result in results:
        for field in result['structured_data']:
            field_counts[field] = field_counts.get(field, 0) + 1
    
    return field_counts
```

## Recovery Procedures

### Service Recovery

```bash
# Restart application
pkill -f uvicorn
uvicorn app.main:app --reload

# Clear any cached data
rm -rf __pycache__/
rm -rf .pytest_cache/

# Verify service health
curl http://localhost:8000/health
```

### Data Recovery

```python
# If processing fails mid-way, implement recovery
def safe_extract_document(file_path):
    try:
        # Primary processing
        return extract_with_vision(file_path)
    except Exception as e:
        print(f"Vision processing failed: {e}")
        try:
            # Fallback processing
            return extract_with_ocr(file_path)
        except Exception as e:
            print(f"OCR processing failed: {e}")
            # Return basic file info
            return {"error": str(e), "filename": file_path}
```

## Getting Help

### Information to Provide

When reporting issues, include:

1. **System Information:**
   ```bash
   python --version
   pip list | grep -E "(fastapi|groq|paddleocr)"
   uname -a
   ```

2. **Error Details:**
   - Complete error message
   - Stack trace
   - Request/response examples

3. **File Information:**
   - File format and size
   - Document type
   - Image quality assessment

4. **Environment:**
   - Development vs Production
   - Docker vs Native
   - API key validity

### Support Channels

1. **GitHub Issues:** For bugs and feature requests
2. **Documentation:** API.md and README.md
3. **Debug Mode:** Enable for detailed error analysis
4. **Logs:** Check application logs for detailed error information

---

*Troubleshooting Guide last updated: August 5, 2025*
