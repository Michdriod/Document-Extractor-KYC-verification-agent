"""FastAPI application bootstrap and router registration for the document extractor service."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn

from app.api.endpoints import document_router
from app.api.enhanced_endpoints import enhanced_router
from app.api.url_ingest_endpoints import url_ingest_router

app = FastAPI(
    title="Document Extractor & KYC Verification Agent",
    description="API for document extraction and KYC verification",
    version="0.1.0"
)

# Mount static files
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(document_router, prefix="/api")
app.include_router(enhanced_router, prefix="/api")
app.include_router(url_ingest_router, prefix="/api")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the index HTML page with URL ingest support"""
    return templates.TemplateResponse("index_new.html", {"request": request})

@app.get("/updated", response_class=HTMLResponse)
async def index_updated(request: Request):
    """Serve the updated index HTML page with URL ingest support"""
    return templates.TemplateResponse("index_new_updated.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
