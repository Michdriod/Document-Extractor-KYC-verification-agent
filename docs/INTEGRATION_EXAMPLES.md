# Integration Guide

This guide shows how to call the API from different environments and handle typical scenarios (file uploads, URL ingestion, multi-document extraction).

Base URL:

```text
http://localhost:8000
```

## Endpoints quick reference

- POST /api/extract — single-document friendly, returns OCR and optional structured data
- POST /api/extract/enhanced — multi-document friendly, returns documents[] + metadata
- POST /api/analyze — always structured data (DocumentData)

At least one of `file`, `url`, or `path` must be provided for /api/extract and /api/extract/enhanced.

## curl examples

Basic OCR (file):

```bash
curl -X POST "http://localhost:8000/api/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

Structured data (file):

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@passport.jpg"
```

URL ingestion (no file upload):

```bash
curl -X POST "http://localhost:8000/api/extract?structured=true" \
  -H "accept: application/json" \
  "&url=https://example.com/sample.pdf"
```

Enhanced multi-document:

```bash
curl -X POST "http://localhost:8000/api/extract/enhanced" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@multi_page.pdf"
```

## Python

```python
import requests
from typing import Optional

BASE = "http://localhost:8000"

def extract_document(
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    path: Optional[str] = None,
    structured: bool = True,
    include_raw: bool = False,
):
    params = {"structured": structured, "include_raw": include_raw}
    if file_path:
        with open(file_path, "rb") as f:
            files = {"file": f}
            r = requests.post(f"{BASE}/api/extract", params=params, files=files)
    else:
        params.update({k: v for k, v in {"url": url, "path": path}.items() if v})
        r = requests.post(f"{BASE}/api/extract", params=params)
    r.raise_for_status()
    return r.json()

print(extract_document(file_path="passport.jpg", structured=True))
```

Enhanced multi-document (Python):

```python
import requests

BASE = "http://localhost:8000"

with open("bundle.pdf", "rb") as f:
    r = requests.post(f"{BASE}/api/extract/enhanced", files={"file": f})
    r.raise_for_status()
    data = r.json()
    print(len(data.get("documents", [])), "documents")
```

## Node.js (axios)

```javascript
const fs = require('fs');
const FormData = require('form-data');
const axios = require('axios');

async function extract(filePath, structured = true, includeRaw = false) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  const url = `http://localhost:8000/api/extract?structured=${structured}&include_raw=${includeRaw}`;
  const res = await axios.post(url, form, { headers: form.getHeaders() });
  return res.data;
}

extract('./document.pdf').then(console.log).catch(console.error);
```

## Handling responses

- For /api/extract with structured=true: use `response.structured_data`
- For /api/extract without structured: you'll receive an envelope with `filename` and a message; raw OCR lines are not returned
- For /api/extract/enhanced: iterate `response.documents`, and check `data.fields`, `data.categorized_fields`, `data.primary_fields`, `data.related_fields`.

## Tips

- Use HTTPS URLs that return images or PDFs; the server MIME-sniffs and handles PDF->image automatically.
- For public deployments, avoid enabling local `path` ingestion.
- If you need raw, unfiltered structured results for debugging, set `include_raw=true` on /api/extract (does not include raw OCR lines).
