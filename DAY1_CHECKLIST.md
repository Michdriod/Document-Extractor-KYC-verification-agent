# Day 1 Checklist: Document Upload + PaddleOCR Extraction

## Setup and Environment

- [ ] Create a virtual environment:
  ```bash
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  ```

- [ ] Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

- [ ] For PaddleOCR, you may need additional dependencies:
  ```bash
  # For Mac
  brew install poppler
  
  # For Ubuntu/Debian
  sudo apt-get install -y poppler-utils
  
  # For Windows, download poppler from https://github.com/oschwartz10612/poppler-windows
  # and add it to your PATH
  ```

## Implementation Tasks

- [ ] Test the FastAPI server startup:
  ```bash
  uvicorn app.main:app --reload
  ```

- [ ] Access the API documentation at http://localhost:8000/docs

- [ ] Test document upload with sample documents:
  - [ ] Create a test folder with sample documents (IDs, certificates, etc.)
  - [ ] Try uploading a PDF document
  - [ ] Try uploading a JPG/PNG document
  - [ ] Verify that OCR is correctly extracting text

- [ ] Debug any OCR issues:
  - [ ] Check if PaddleOCR is correctly installed
  - [ ] Verify PDF to image conversion is working properly
  - [ ] Adjust OCR parameters if needed

- [ ] Optimize memory usage:
  - [ ] Ensure files are processed in memory without saving to disk
  - [ ] Check for memory leaks when processing large files
  - [ ] Add proper cleanup of temporary resources

## Testing and Verification

- [ ] Run basic tests:
  ```bash
  pytest tests/
  ```

- [ ] Manually test the web UI:
  - [ ] Open http://localhost:8000/ in a browser
  - [ ] Upload documents and verify extraction
  - [ ] Check the JSON output format

## Troubleshooting

- If PaddleOCR installation fails, try:
  ```bash
  pip install paddlepaddle==2.5.0
  pip install paddleocr==2.6.1.3
  ```

- If PDF conversion fails, verify poppler is correctly installed and accessible

## Next Steps (After Day 1)

- [ ] Review extracted data quality
- [ ] Plan for Vision LLM integration (Day 2)
