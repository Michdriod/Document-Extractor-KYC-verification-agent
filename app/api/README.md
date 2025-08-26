# API routers

This folder exposes three main routers mounted under `/api`:

- `document_router` (in `endpoints.py`) - Basic document extraction and analysis endpoints.
- `enhanced_router` (in `enhanced_endpoints.py`) - Enhanced structured extraction and document categorization.
- `url_ingest_router` (in `url_ingest_endpoints.py`) - On-the-fly HTTPS URL ingestion and MIME-sniffing.

Each router returns JSON-serializable results and uses helper functions to convert model objects to plain dictionaries before returning responses.
