"""Shared URL ingestion helpers used across endpoints to ensure consistent behavior.

Features:
- Stream with size limits
- Robust MIME detection (python-magic if available, fallback otherwise)
- Optional HTTPS-only enforcement (enabled for public URL-ingest endpoint)
"""

from __future__ import annotations

import io
from typing import Tuple
from urllib.parse import urlparse

import requests

try:
    import magic  # type: ignore
    HAS_PYTHON_MAGIC = True
except Exception:
    HAS_PYTHON_MAGIC = False


MIME_TO_EXT = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'application/pdf': 'pdf'
}


def safe_stream_and_detect_mime(url: str, max_size_mb: int = 50, allow_http: bool = True) -> Tuple[bytes, str]:
    """
    Safely stream document from URL and detect MIME type without persistence.

    Args:
        url: HTTP(S) URL to stream from
        max_size_mb: Maximum file size in MB to prevent abuse
        allow_http: If False, only allow HTTPS URLs (recommended for public endpoints)

    Returns:
        (file_bytes, detected_mime)

    Raises:
        ValueError or requests exceptions for invalid URL or download/mime issues
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        raise ValueError("Only HTTP/HTTPS URLs are supported")
    if not allow_http and parsed.scheme != 'https':
        raise ValueError("Only HTTPS URLs are supported for this endpoint")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36',
        'Accept': 'image/*,application/pdf,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }

    resp = requests.get(url, headers=headers, stream=True, timeout=30)
    resp.raise_for_status()

    content_length = resp.headers.get('content-length')
    if content_length and int(content_length) > max_size_mb * 1024 * 1024:
        raise ValueError(f"File too large. Maximum size: {max_size_mb}MB")

    buf = io.BytesIO()
    total = 0
    for chunk in resp.iter_content(chunk_size=8192):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_size_mb * 1024 * 1024:
            raise ValueError(f"File too large. Maximum size: {max_size_mb}MB")
        buf.write(chunk)

    data = buf.getvalue()
    if not data:
        raise ValueError("Downloaded file is empty")

    # Prefer python-magic, fallback to headers and signatures
    if HAS_PYTHON_MAGIC:
        try:
            mime = magic.from_buffer(data, mime=True)  # type: ignore
        except Exception:
            mime = resp.headers.get('content-type', 'application/octet-stream').split(';')[0]
    else:
        mime = resp.headers.get('content-type', 'application/octet-stream').split(';')[0]
        if mime == 'application/octet-stream' or not mime:
            if data.startswith(b'%PDF'):
                mime = 'application/pdf'
            elif data.startswith(b'\xff\xd8\xff'):
                mime = 'image/jpeg'
            elif data.startswith(b'\x89PNG'):
                mime = 'image/png'

    if mime not in MIME_TO_EXT:
        raise ValueError(
            f"Unsupported file type: {mime}. Supported types: {', '.join(MIME_TO_EXT.keys())}"
        )

    return data, mime


def mime_to_extension(mime: str) -> str:
    """Map MIME type to common file extension."""
    if mime not in MIME_TO_EXT:
        raise ValueError(f"Unsupported MIME type: {mime}")
    return MIME_TO_EXT[mime]
