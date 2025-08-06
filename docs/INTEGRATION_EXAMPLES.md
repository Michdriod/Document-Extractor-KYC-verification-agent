# Integration Examples

## Document Extractor & KYC Verification Agent

This document provides practical integration examples for different programming languages and frameworks.

## Table of Contents

- [Python Integration](#python-integration)
- [JavaScript/Node.js Integration](#javascriptnodejs-integration)
- [React Frontend Integration](#react-frontend-integration)
- [PHP Integration](#php-integration)
- [Java Integration](#java-integration)
- [cURL Examples](#curl-examples)
- [Postman Collection](#postman-collection)
- [Webhook Integration](#webhook-integration)
- [Batch Processing](#batch-processing)

---

## Python Integration

### Basic Implementation

```python
import requests
import json
from typing import Optional, Dict, Any

class DocumentExtractor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def extract_document(
        self, 
        file_path: str, 
        structured: bool = True, 
        include_raw: bool = False
    ) -> Dict[str, Any]:
        """Extract data from a document file."""
        url = f"{self.base_url}/api/extract"
        params = {
            "structured": structured,
            "include_raw": include_raw
        }
        
        try:
            with open(file_path, 'rb') as file:
                files = {'file': file}
                response = self.session.post(url, files=files, params=params)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")
        except FileNotFoundError:
            raise Exception(f"File not found: {file_path}")
    
    def analyze_document(self, file_path: str) -> Dict[str, Any]:
        """Analyze document and return structured data only."""
        url = f"{self.base_url}/api/analyze"
        
        try:
            with open(file_path, 'rb') as file:
                files = {'file': file}
                response = self.session.post(url, files=files)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

# Usage Example
if __name__ == "__main__":
    extractor = DocumentExtractor()
    
    # Extract structured data
    result = extractor.extract_document("passport.jpg", structured=True)
    print("Document Type:", result['structured_data']['document_type'])
    print("Full Name:", f"{result['structured_data']['given_names']} {result['structured_data']['surname']}")
    
    # Analyze document
    analysis = extractor.analyze_document("drivers_license.pdf")
    print("License Class:", analysis.get('license_class', 'N/A'))
```

### Advanced Python Integration with Error Handling

```python
import requests
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ExtractionResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class AdvancedDocumentExtractor:
    def __init__(
        self, 
        base_url: str = "http://localhost:8000",
        max_retries: int = 3,
        timeout: int = 30
    ):
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.timeout = timeout
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def extract_with_retry(
        self, 
        file_path: str, 
        structured: bool = True,
        include_raw: bool = False
    ) -> ExtractionResult:
        """Extract document data with retry logic and error handling."""
        start_time = time.time()
        
        for attempt in range(self.max_retries):
            try:
                result = self._extract_document(file_path, structured, include_raw)
                processing_time = time.time() - start_time
                
                self.logger.info(f"Successfully processed {file_path} in {processing_time:.2f}s")
                return ExtractionResult(
                    success=True, 
                    data=result, 
                    processing_time=processing_time
                )
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {file_path}: {e}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    processing_time = time.time() - start_time
                    return ExtractionResult(
                        success=False, 
                        error=str(e), 
                        processing_time=processing_time
                    )
    
    def _extract_document(self, file_path: str, structured: bool, include_raw: bool) -> Dict[str, Any]:
        """Internal method to extract document data."""
        # Validate file
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = Path(file_path).stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise ValueError(f"File too large: {file_size} bytes")
        
        url = f"{self.base_url}/api/extract"
        params = {"structured": structured, "include_raw": include_raw}
        
        with open(file_path, 'rb') as file:
            files = {'file': file}
            response = self.session.post(url, files=files, params=params)
        
        response.raise_for_status()
        return response.json()
    
    def batch_process(self, file_paths: List[str]) -> List[ExtractionResult]:
        """Process multiple documents."""
        results = []
        
        for file_path in file_paths:
            self.logger.info(f"Processing {file_path}...")
            result = self.extract_with_retry(file_path)
            results.append(result)
        
        # Summary
        successful = sum(1 for r in results if r.success)
        self.logger.info(f"Batch processing complete: {successful}/{len(results)} successful")
        
        return results

# Usage
extractor = AdvancedDocumentExtractor()

# Single document
result = extractor.extract_with_retry("passport.jpg")
if result.success:
    print("Extraction successful!")
    print(json.dumps(result.data, indent=2))
else:
    print(f"Extraction failed: {result.error}")

# Batch processing
files = ["doc1.pdf", "doc2.jpg", "doc3.png"]
results = extractor.batch_process(files)
```

---

## JavaScript/Node.js Integration

### Basic Node.js Implementation

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

class DocumentExtractor {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.client = axios.create({
            baseURL: baseUrl,
            timeout: 30000
        });
    }

    async extractDocument(filePath, options = {}) {
        const { structured = true, includeRaw = false } = options;
        
        try {
            // Check if file exists
            if (!fs.existsSync(filePath)) {
                throw new Error(`File not found: ${filePath}`);
            }

            const form = new FormData();
            form.append('file', fs.createReadStream(filePath));

            const params = new URLSearchParams({
                structured: structured.toString(),
                include_raw: includeRaw.toString()
            });

            const response = await this.client.post(
                `/api/extract?${params}`,
                form,
                {
                    headers: {
                        ...form.getHeaders(),
                        'Content-Type': 'multipart/form-data'
                    }
                }
            );

            return response.data;
        } catch (error) {
            if (error.response) {
                throw new Error(`API Error: ${error.response.data.detail || error.message}`);
            }
            throw error;
        }
    }

    async analyzeDocument(filePath) {
        try {
            const form = new FormData();
            form.append('file', fs.createReadStream(filePath));

            const response = await this.client.post('/api/analyze', form, {
                headers: form.getHeaders()
            });

            return response.data;
        } catch (error) {
            if (error.response) {
                throw new Error(`API Error: ${error.response.data.detail || error.message}`);
            }
            throw error;
        }
    }

    async batchProcess(filePaths) {
        const results = [];
        
        for (const filePath of filePaths) {
            try {
                console.log(`Processing ${filePath}...`);
                const result = await this.extractDocument(filePath);
                results.push({ success: true, filePath, data: result });
            } catch (error) {
                console.error(`Failed to process ${filePath}:`, error.message);
                results.push({ success: false, filePath, error: error.message });
            }
        }

        return results;
    }
}

// Usage Example
(async () => {
    const extractor = new DocumentExtractor();

    try {
        // Extract structured data
        const result = await extractor.extractDocument('./passport.jpg', {
            structured: true,
            includeRaw: false
        });

        console.log('Document Type:', result.structured_data.document_type);
        console.log('Full Name:', `${result.structured_data.given_names} ${result.structured_data.surname}`);

        // Batch processing
        const files = ['doc1.pdf', 'doc2.jpg', 'doc3.png'];
        const batchResults = await extractor.batchProcess(files);
        
        const successful = batchResults.filter(r => r.success).length;
        console.log(`Processed ${successful}/${batchResults.length} documents successfully`);

    } catch (error) {
        console.error('Error:', error.message);
    }
})();
```

### Express.js Middleware Integration

```javascript
const express = require('express');
const multer = require('multer');
const FormData = require('form-data');
const axios = require('axios');

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

// Document extraction middleware
const extractDocumentData = async (req, res, next) => {
    if (!req.file) {
        return res.status(400).json({ error: 'No file uploaded' });
    }

    try {
        const form = new FormData();
        form.append('file', req.file.buffer, {
            filename: req.file.originalname,
            contentType: req.file.mimetype
        });

        const response = await axios.post(
            'http://localhost:8000/api/extract?structured=true',
            form,
            {
                headers: form.getHeaders(),
                timeout: 30000
            }
        );

        req.extractedData = response.data;
        next();
    } catch (error) {
        console.error('Document extraction error:', error.message);
        res.status(500).json({
            error: 'Document extraction failed',
            details: error.response?.data?.detail || error.message
        });
    }
};

// Routes
app.post('/upload-document', upload.single('document'), extractDocumentData, (req, res) => {
    res.json({
        message: 'Document processed successfully',
        data: req.extractedData
    });
});

app.listen(3000, () => {
    console.log('Server running on port 3000');
});
```

---

## React Frontend Integration

### React Hook for Document Processing

```jsx
import { useState, useCallback } from 'react';
import axios from 'axios';

const useDocumentExtractor = (baseUrl = 'http://localhost:8000') => {
    const [isProcessing, setIsProcessing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const extractDocument = useCallback(async (file, options = {}) => {
        const { structured = true, includeRaw = false } = options;
        
        setIsProcessing(true);
        setProgress(0);
        setError(null);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const params = new URLSearchParams({
                structured: structured.toString(),
                include_raw: includeRaw.toString()
            });

            setProgress(30);

            const response = await axios.post(
                `${baseUrl}/api/extract?${params}`,
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    },
                    onUploadProgress: (progressEvent) => {
                        const percentCompleted = Math.round(
                            (progressEvent.loaded * 100) / progressEvent.total
                        );
                        setProgress(Math.min(percentCompleted, 70));
                    }
                }
            );

            setProgress(100);
            setResult(response.data);
            
        } catch (err) {
            setError(err.response?.data?.detail || err.message);
        } finally {
            setIsProcessing(false);
        }
    }, [baseUrl]);

    const clearResults = useCallback(() => {
        setResult(null);
        setError(null);
        setProgress(0);
    }, []);

    return {
        extractDocument,
        clearResults,
        isProcessing,
        progress,
        error,
        result
    };
};

// Document Upload Component
const DocumentUploader = () => {
    const { extractDocument, clearResults, isProcessing, progress, error, result } = useDocumentExtractor();
    const [dragOver, setDragOver] = useState(false);

    const handleFileSelect = (file) => {
        if (file) {
            extractDocument(file, { structured: true });
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        handleFileSelect(file);
    };

    return (
        <div className="document-uploader">
            <div
                className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
            >
                <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={(e) => handleFileSelect(e.target.files[0])}
                    style={{ display: 'none' }}
                    id="file-input"
                />
                <label htmlFor="file-input" className="file-label">
                    {isProcessing ? 'Processing...' : 'Click or drag to upload document'}
                </label>
            </div>

            {isProcessing && (
                <div className="progress-bar">
                    <div 
                        className="progress-fill" 
                        style={{ width: `${progress}%` }}
                    />
                    <span>{progress}%</span>
                </div>
            )}

            {error && (
                <div className="error-message">
                    Error: {error}
                </div>
            )}

            {result && (
                <div className="results">
                    <h3>Extraction Results</h3>
                    <div className="document-info">
                        <p><strong>Document Type:</strong> {result.structured_data?.document_type}</p>
                        <p><strong>Name:</strong> {result.structured_data?.given_names} {result.structured_data?.surname}</p>
                        <p><strong>Document Number:</strong> {result.structured_data?.document_number}</p>
                        <p><strong>Extraction Method:</strong> {result.structured_data?.extraction_method}</p>
                    </div>
                    <button onClick={clearResults}>Clear Results</button>
                </div>
            )}
        </div>
    );
};

export default DocumentUploader;
```

---

## PHP Integration

### Basic PHP Implementation

```php
<?php

class DocumentExtractor {
    private $baseUrl;
    private $timeout;

    public function __construct($baseUrl = 'http://localhost:8000', $timeout = 30) {
        $this->baseUrl = rtrim($baseUrl, '/');
        $this->timeout = $timeout;
    }

    public function extractDocument($filePath, $structured = true, $includeRaw = false) {
        if (!file_exists($filePath)) {
            throw new Exception("File not found: $filePath");
        }

        $url = $this->baseUrl . '/api/extract';
        $params = http_build_query([
            'structured' => $structured ? 'true' : 'false',
            'include_raw' => $includeRaw ? 'true' : 'false'
        ]);

        $ch = curl_init();
        
        curl_setopt_array($ch, [
            CURLOPT_URL => $url . '?' . $params,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => [
                'file' => new CURLFile($filePath)
            ],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_HTTPHEADER => [
                'Accept: application/json'
            ]
        ]);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($error) {
            throw new Exception("cURL error: $error");
        }

        if ($httpCode !== 200) {
            $errorData = json_decode($response, true);
            $errorMessage = $errorData['detail'] ?? "HTTP $httpCode error";
            throw new Exception("API error: $errorMessage");
        }

        return json_decode($response, true);
    }

    public function analyzeDocument($filePath) {
        if (!file_exists($filePath)) {
            throw new Exception("File not found: $filePath");
        }

        $url = $this->baseUrl . '/api/analyze';

        $ch = curl_init();
        
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => [
                'file' => new CURLFile($filePath)
            ],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_HTTPHEADER => [
                'Accept: application/json'
            ]
        ]);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode !== 200) {
            $errorData = json_decode($response, true);
            $errorMessage = $errorData['detail'] ?? "HTTP $httpCode error";
            throw new Exception("API error: $errorMessage");
        }

        return json_decode($response, true);
    }

    public function batchProcess(array $filePaths) {
        $results = [];
        
        foreach ($filePaths as $filePath) {
            try {
                echo "Processing $filePath...\n";
                $result = $this->extractDocument($filePath);
                $results[] = [
                    'success' => true,
                    'file_path' => $filePath,
                    'data' => $result
                ];
            } catch (Exception $e) {
                echo "Failed to process $filePath: " . $e->getMessage() . "\n";
                $results[] = [
                    'success' => false,
                    'file_path' => $filePath,
                    'error' => $e->getMessage()
                ];
            }
        }

        return $results;
    }
}

// Usage Example
try {
    $extractor = new DocumentExtractor();
    
    // Extract structured data
    $result = $extractor->extractDocument('./passport.jpg', true);
    echo "Document Type: " . $result['structured_data']['document_type'] . "\n";
    echo "Name: " . $result['structured_data']['given_names'] . " " . 
         $result['structured_data']['surname'] . "\n";
    
    // Batch processing
    $files = ['doc1.pdf', 'doc2.jpg', 'doc3.png'];
    $batchResults = $extractor->batchProcess($files);
    
    $successful = count(array_filter($batchResults, function($r) { return $r['success']; }));
    echo "Processed $successful/" . count($batchResults) . " documents successfully\n";
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}

?>
```

---

## Java Integration

### Basic Java Implementation

```java
import java.io.*;
import java.net.http.*;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;

public class DocumentExtractor {
    private final String baseUrl;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    
    public DocumentExtractor(String baseUrl) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();
        this.objectMapper = new ObjectMapper();
    }
    
    public DocumentExtractor() {
        this("http://localhost:8000");
    }
    
    public CompletableFuture<JsonNode> extractDocument(Path filePath, boolean structured, boolean includeRaw) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                if (!Files.exists(filePath)) {
                    throw new RuntimeException("File not found: " + filePath);
                }
                
                String boundary = "----WebKitFormBoundary" + System.currentTimeMillis();
                
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                PrintWriter writer = new PrintWriter(new OutputStreamWriter(baos, "UTF-8"), true);
                
                // Add file part
                writer.append("--" + boundary).append("\r\n");
                writer.append("Content-Disposition: form-data; name=\"file\"; filename=\"" + filePath.getFileName() + "\"").append("\r\n");
                writer.append("Content-Type: application/octet-stream").append("\r\n");
                writer.append("\r\n").flush();
                
                baos.write(Files.readAllBytes(filePath));
                
                writer.append("\r\n").flush();
                writer.append("--" + boundary + "--").append("\r\n").flush();
                
                String uri = String.format("%s/api/extract?structured=%s&include_raw=%s", 
                    baseUrl, structured, includeRaw);
                
                HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(uri))
                    .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                    .POST(HttpRequest.BodyPublishers.ofByteArray(baos.toByteArray()))
                    .build();
                
                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                
                if (response.statusCode() != 200) {
                    JsonNode errorData = objectMapper.readTree(response.body());
                    String errorMessage = errorData.has("detail") ? errorData.get("detail").asText() : 
                        "HTTP " + response.statusCode() + " error";
                    throw new RuntimeException("API error: " + errorMessage);
                }
                
                return objectMapper.readTree(response.body());
                
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
    }
    
    public CompletableFuture<JsonNode> analyzeDocument(Path filePath) {
        return extractDocument(filePath, true, false);
    }
    
    public static class ExtractionResult {
        public boolean success;
        public String filePath;
        public JsonNode data;
        public String error;
        
        public ExtractionResult(boolean success, String filePath, JsonNode data, String error) {
            this.success = success;
            this.filePath = filePath;
            this.data = data;
            this.error = error;
        }
    }
    
    public List<ExtractionResult> batchProcess(List<Path> filePaths) {
        List<CompletableFuture<ExtractionResult>> futures = filePaths.stream()
            .map(filePath -> 
                extractDocument(filePath, true, false)
                    .thenApply(data -> new ExtractionResult(true, filePath.toString(), data, null))
                    .exceptionally(throwable -> new ExtractionResult(false, filePath.toString(), null, throwable.getMessage()))
            )
            .toList();
        
        return futures.stream()
            .map(CompletableFuture::join)
            .toList();
    }
    
    // Usage Example
    public static void main(String[] args) {
        DocumentExtractor extractor = new DocumentExtractor();
        
        try {
            // Extract structured data
            JsonNode result = extractor.extractDocument(Path.of("passport.jpg"), true, false).join();
            JsonNode structuredData = result.get("structured_data");
            
            System.out.println("Document Type: " + structuredData.get("document_type").asText());
            System.out.println("Name: " + structuredData.get("given_names").asText() + " " + 
                             structuredData.get("surname").asText());
            
            // Batch processing
            List<Path> files = List.of(Path.of("doc1.pdf"), Path.of("doc2.jpg"), Path.of("doc3.png"));
            List<ExtractionResult> batchResults = extractor.batchProcess(files);
            
            long successful = batchResults.stream().mapToLong(r -> r.success ? 1 : 0).sum();
            System.out.println("Processed " + successful + "/" + batchResults.size() + " documents successfully");
            
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }
}
```

---

## cURL Examples

### Basic Extraction

```bash
# Basic OCR extraction
curl -X POST "http://localhost:8000/api/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"

# Structured data extraction
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@passport.jpg"

# Debug mode with raw data
curl -X POST "http://localhost:8000/api/extract?structured=true&include_raw=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drivers_license.png"
```

### Batch Processing Script

```bash
#!/bin/bash

# Batch document processing script
DOCUMENTS_DIR="./documents"
RESULTS_DIR="./results"
API_URL="http://localhost:8000/api/extract"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Process each document
for file in "$DOCUMENTS_DIR"/*; do
    if [[ -f "$file" ]]; then
        filename=$(basename "$file")
        echo "Processing $filename..."
        
        curl -X POST "$API_URL?structured=true" \
          -H "accept: application/json" \
          -H "Content-Type: multipart/form-data" \
          -F "file=@$file" \
          -o "$RESULTS_DIR/${filename}.json" \
          --silent
        
        if [[ $? -eq 0 ]]; then
            echo "✓ Successfully processed $filename"
        else
            echo "✗ Failed to process $filename"
        fi
    fi
done

echo "Batch processing complete. Results saved to $RESULTS_DIR"
```

---

## Webhook Integration

### Webhook Server Example (Node.js)

```javascript
const express = require('express');
const multer = require('multer');
const axios = require('axios');
const FormData = require('form-data');

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

// Webhook endpoint for document processing
app.post('/webhook/process-document', upload.single('document'), async (req, res) => {
    try {
        const { callbackUrl, metadata } = req.body;
        
        if (!req.file) {
            return res.status(400).json({ error: 'No document uploaded' });
        }
        
        // Process document asynchronously
        processDocumentAsync(req.file, callbackUrl, metadata);
        
        // Immediate response
        res.json({
            status: 'accepted',
            message: 'Document processing started',
            processingId: generateProcessingId()
        });
        
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

async function processDocumentAsync(file, callbackUrl, metadata) {
    try {
        // Extract document data
        const form = new FormData();
        form.append('file', file.buffer, {
            filename: file.originalname,
            contentType: file.mimetype
        });
        
        const response = await axios.post(
            'http://localhost:8000/api/extract?structured=true',
            form,
            { headers: form.getHeaders() }
        );
        
        // Send results to callback URL
        await axios.post(callbackUrl, {
            status: 'completed',
            data: response.data,
            metadata: metadata
        });
        
    } catch (error) {
        // Send error to callback URL
        await axios.post(callbackUrl, {
            status: 'failed',
            error: error.message,
            metadata: metadata
        });
    }
}

function generateProcessingId() {
    return 'proc_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

app.listen(3001, () => {
    console.log('Webhook server running on port 3001');
});
```

---

## Batch Processing

### Python Batch Processor

```python
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Dict, Any
import json
import time

class BatchDocumentProcessor:
    def __init__(self, base_url: str = "http://localhost:8000", max_concurrent: int = 5):
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_document(self, session: aiohttp.ClientSession, file_path: Path) -> Dict[str, Any]:
        """Process a single document."""
        async with self.semaphore:
            try:
                async with aiofiles.open(file_path, 'rb') as file:
                    file_content = await file.read()
                
                data = aiohttp.FormData()
                data.add_field('file', file_content, filename=file_path.name)
                
                params = {'structured': 'true', 'include_raw': 'false'}
                
                async with session.post(
                    f"{self.base_url}/api/extract",
                    data=data,
                    params=params
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            'success': True,
                            'file_path': str(file_path),
                            'data': result
                        }
                    else:
                        error_data = await response.json()
                        return {
                            'success': False,
                            'file_path': str(file_path),
                            'error': error_data.get('detail', f'HTTP {response.status}')
                        }
                        
            except Exception as e:
                return {
                    'success': False,
                    'file_path': str(file_path),
                    'error': str(e)
                }
    
    async def process_batch(self, file_paths: List[Path], output_dir: Path = None) -> List[Dict[str, Any]]:
        """Process multiple documents concurrently."""
        if output_dir:
            output_dir.mkdir(exist_ok=True)
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            tasks = [self.process_document(session, file_path) for file_path in file_paths]
            
            # Process with progress tracking
            results = []
            for i, task in enumerate(asyncio.as_completed(tasks)):
                result = await task
                results.append(result)
                
                print(f"Processed {i+1}/{len(file_paths)}: {result['file_path']} - "
                      f"{'✓' if result['success'] else '✗'}")
                
                # Save individual result if output directory provided
                if output_dir and result['success']:
                    result_file = output_dir / f"{Path(result['file_path']).stem}_result.json"
                    async with aiofiles.open(result_file, 'w') as f:
                        await f.write(json.dumps(result['data'], indent=2))
            
            return results
    
    def generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate processing summary."""
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total - successful
        
        summary = {
            'total_documents': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'failed_files': [r['file_path'] for r in results if not r['success']]
        }
        
        return summary

# Usage Example
async def main():
    processor = BatchDocumentProcessor(max_concurrent=3)
    
    # Get all PDF and image files from a directory
    documents_dir = Path('./documents')
    file_paths = list(documents_dir.glob('*.pdf')) + \
                list(documents_dir.glob('*.jpg')) + \
                list(documents_dir.glob('*.png'))
    
    print(f"Found {len(file_paths)} documents to process")
    
    # Process documents
    start_time = time.time()
    results = await processor.process_batch(file_paths, output_dir=Path('./results'))
    end_time = time.time()
    
    # Generate summary
    summary = processor.generate_summary(results)
    
    print(f"\nProcessing Summary:")
    print(f"Total Documents: {summary['total_documents']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Processing Time: {end_time - start_time:.2f} seconds")
    
    if summary['failed_files']:
        print(f"\nFailed Files:")
        for file_path in summary['failed_files']:
            print(f"  - {file_path}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Testing Integration

### Pytest Integration Tests

```python
import pytest
import requests
import tempfile
from pathlib import Path

class TestDocumentExtractorAPI:
    BASE_URL = "http://localhost:8000"
    
    @pytest.fixture
    def sample_document(self):
        """Create a temporary test document."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            # Create a minimal PDF content for testing
            f.write(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
            return Path(f.name)
    
    def test_health_check(self):
        """Test API health endpoint."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_extract_basic_ocr(self, sample_document):
        """Test basic OCR extraction."""
        with open(sample_document, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{self.BASE_URL}/api/extract", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert 'filename' in data
        assert 'results' in data
    
    def test_extract_structured_data(self, sample_document):
        """Test structured data extraction."""
        with open(sample_document, 'rb') as f:
            files = {'file': f}
            params = {'structured': 'true'}
            response = requests.post(
                f"{self.BASE_URL}/api/extract", 
                files=files, 
                params=params
            )
        
        assert response.status_code == 200
        data = response.json()
        assert 'structured_data' in data
        assert 'ocr_results' in data
    
    def test_invalid_file_format(self):
        """Test error handling for invalid file format."""
        # Create a text file (unsupported format)
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'This is a text file')
            
        with open(f.name, 'rb') as file:
            files = {'file': file}
            response = requests.post(f"{self.BASE_URL}/api/extract", files=files)
        
        assert response.status_code == 400
        assert 'Unsupported file format' in response.json()['detail']
    
    def test_analyze_document(self, sample_document):
        """Test document analysis endpoint."""
        with open(sample_document, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{self.BASE_URL}/api/analyze", files=files)
        
        assert response.status_code == 200
        data = response.json()
        # Should contain DocumentData fields
        assert 'document_type' in data
        assert 'extraction_method' in data
```

---

*Integration Examples last updated: August 5, 2025*
