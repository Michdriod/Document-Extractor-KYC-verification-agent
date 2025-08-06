import os
import base64
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import io
import re
from PIL import Image
import requests
from dotenv import load_dotenv
from groq import Groq

from app.models.document_data import DocumentData

# Load environment variables from .env file
load_dotenv()

# Get environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_REFERER = os.getenv("OPENROUTER_REFERER", "http://localhost:8000")
OPENROUTER_TITLE = os.getenv("OPENROUTER_TITLE", "Document Extractor KYC")

class OCRStructurer:
    """Class to structure raw OCR text into document data using LLM"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OCR structurer with API credentials"""
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable or pass it to the constructor.")
        
        # Initialize the Groq client for text processing
        self.client = Groq(api_key=self.api_key)
    
    async def structure_ocr_results(self, ocr_results: List[Dict[str, Any]]) -> DocumentData:
        """
        Structure OCR results into document data using LLM
        
        Args:
            ocr_results: List of OCR result dictionaries with text and confidence
            
        Returns:
            DocumentData object with structured information
        """
        # Extract text from OCR results
        ocr_texts = [item["text"] for item in ocr_results]
        full_text = "\n".join(ocr_texts)
        
        try:
            # Use Groq text model with JSON schema for structured output
            completion = self.client.chat.completions.create(
                model="moonshotai/kimi-k2-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert document analyzer specialized in structuring raw OCR text from various identity documents.

TASK:
Extract structured document data from OCR text and return it in the exact JSON schema format required.

DOCUMENT TYPE DETECTION:
Be very specific about document types. Use these exact classifications:
- "International Passport" (for international passports)
- "national_id_card" (for national identity cards)
- "drivers_license" (for driving licenses)
- "voter_registration_card" (for voting cards)
- "nin_slip" or "nin_card" (for National Identification Number documents)
- "residence_permit" (for residence/work permits)
- "birth_certificate" (for birth certificates)
- "work_permit" (for employment authorization)
- "social_security_card" (for social security documents)

EXTRACTION GUIDELINES:
1. FIRST: Carefully identify the exact document type from headers, titles, or document structure
2. Extract all visible fields that match the schema
3. For dates: Convert all formats to YYYY-MM-DD (e.g., "17 SEP 2023" → "2023-09-17")
4. For lists (mrz_lines, vehicle_categories): Return as proper arrays
5. Leave fields as null if not clearly present
6. Handle OCR errors intelligently (correct obvious mistakes like O/0, I/1)
7. For names: Extract surname and given_names separately when possible
8. Be specific about document types to enable proper field filtering"""
                    },
                    {
                        "role": "user",
                        "content": f"""Extract structured data from this OCR text:

{full_text}

Return the data in the exact JSON schema format."""
                    }
                ],
                temperature=0.1,
                max_completion_tokens=1024,
                top_p=0.9,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_data",
                        "schema": DocumentData.model_json_schema()
                    }
                },
                stream=False
            )
            
            # Parse the JSON response and create DocumentData directly
            response_content = completion.choices[0].message.content
            extracted_data = json.loads(response_content)
            
            # Create DocumentData object directly (schema validation handled by Groq)
            document_data = DocumentData.model_validate(extracted_data)
            document_data.extraction_method = "OCR+LLM (Groq Kimi-K2)"
            
            return document_data
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response from OCR LLM: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to structure OCR text using LLM: {str(e)}")


class VisionLLMExtractor:
    """Class to extract structured data directly from document images using Groq Vision LLM"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Vision LLM extractor with API credentials"""
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("Groq API key is required for vision models. Set GROQ_API_KEY environment variable or pass it to the constructor.")
        
        # Initialize the Groq client for vision models
        self.client = Groq(api_key=self.api_key)
    
    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 for API submission"""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    async def extract_from_image(self, image_bytes: bytes) -> DocumentData:
        """
        Extract structured document data directly from an image using Groq Vision LLM
        
        Args:
            image_bytes: Binary content of the image
            
        Returns:
            DocumentData object with structured information
        """
        # Encode image to base64
        base64_image = self._encode_image(image_bytes)
        
        try:
            # Use Groq vision model with JSON schema for structured output
            completion = self.client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Extract all structured document data from this identity document image and return it in the exact JSON schema format required.

DOCUMENT TYPE DETECTION:
Be very specific about document types. Use these exact classifications:
- "International Passport" (for international passports)
- "national_id_card" (for national identity cards) 
- "drivers_license" (for driving licenses)
- "voter_registration_card" (for voting cards)
- "nin_slip" or "nin_card" (for National Identification Number documents)
- "residence_permit" (for residence/work permits)
- "birth_certificate" (for birth certificates)
- "work_permit" (for employment authorization)
- "social_security_card" (for social security documents)

EXTRACTION REQUIREMENTS:
1. FIRST: Carefully identify the exact document type from headers, titles, logos, or document structure
2. Extract all visible text fields that match the schema
3. Standardize dates to YYYY-MM-DD format (e.g., "17 SEP 2023" → "2023-09-17")
4. Return lists as proper arrays (mrz_lines, vehicle_categories)
5. Only include clearly visible information
6. Leave fields as null if not present
7. For names: Extract surname and given_names separately when possible
8. Handle OCR-like errors intelligently (O/0, I/1, etc.)

Return the extracted data in the exact JSON schema format."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_completion_tokens=2048,
                top_p=0.9,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_data",
                        "schema": DocumentData.model_json_schema()
                    }
                },
                stream=False
            )
            
            # Parse the JSON response and create DocumentData directly
            response_content = completion.choices[0].message.content
            extracted_data = json.loads(response_content)
            
            # Create DocumentData object directly (schema validation handled by Groq)
            document_data = DocumentData.model_validate(extracted_data)
            document_data.extraction_method = "Vision LLM (Groq Llama-4-Scout)"
            
            return document_data
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response from Vision LLM: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to extract data using Vision LLM: {str(e)}")


# Integrated function for document data extraction with OCR and LLM
async def extract_data_with_fallback(
    image_bytes: bytes, 
    ocr_results: List[Dict[str, Any]]
) -> Tuple[DocumentData, Dict[str, Any]]:
    """
    Extract document data with intelligent fallback between OCR+LLM and Vision LLM
    
    FLOW:
    1. ALWAYS structure OCR results using Text LLM → JSON
    2. Assess quality of structured output
    3. If insufficient, fallback to Vision LLM → JSON
    
    Args:
        image_bytes: Binary content of the image
        ocr_results: Initial OCR results from PaddleOCR
        
    Returns:
        Tuple of (DocumentData object, filtered relevant fields dict)
    """
    
    try:
        # STEP 1: Always structure OCR output first (Primary Path)
        print("🔄 Processing with OCR + Groq LLM (Kimi-K2)...")
        ocr_structurer = OCRStructurer()
        ocr_structured_data = await ocr_structurer.structure_ocr_results(ocr_results)
        
        # STEP 2: Assess quality of OCR+LLM structured output
        if _is_sufficient_data(ocr_structured_data):
            print(f"✅ OCR + Groq LLM extraction successful! Document: {ocr_structured_data.document_type}")
            relevant_fields = get_relevant_fields(ocr_structured_data)
            return ocr_structured_data, relevant_fields
        else:
            print("⚠️  OCR + Groq LLM output insufficient. Falling back to Groq Vision...")
            
    except Exception as e:
        print(f"❌ OCR + Groq LLM failed: {str(e)}. Falling back to Groq Vision...")
    
    # STEP 3: Fallback to Vision LLM (Secondary Path)
    try:
        print("🔄 Processing with Groq Vision (Llama-4-Scout)...")
        vision_extractor = VisionLLMExtractor()
        vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
        
        print(f"✅ Groq Vision extraction successful! Document: {vision_structured_data.document_type}")
        relevant_fields = get_relevant_fields(vision_structured_data)
        return vision_structured_data, relevant_fields
        
    except Exception as e:
        raise Exception(f"❌ Both OCR+Groq and Groq Vision extraction failed: {str(e)}")


# Convenience function for simple extraction (backward compatibility)
async def extract_document_data(
    image_bytes: bytes, 
    ocr_results: List[Dict[str, Any]]
) -> DocumentData:
    """
    Simple extraction function that returns only DocumentData object
    
    Args:
        image_bytes: Binary content of the image
        ocr_results: Initial OCR results from PaddleOCR
        
    Returns:
        DocumentData object with structured information
    """
    structured_data, _ = await extract_data_with_fallback(image_bytes, ocr_results)
    return structured_data


def _is_sufficient_data(document_data: DocumentData) -> bool:
    """
    Assess if the structured document data contains sufficient information
    
    Args:
        document_data: Structured document data from OCR+LLM
        
    Returns:
        bool: True if data is sufficient, False if fallback needed
    """
    # Core required fields that most documents should have
    core_fields = [
        document_data.document_type,
        document_data.document_number,
        document_data.surname or document_data.given_names  # At least one name
    ]
    
    # Count non-empty core fields
    valid_core_fields = sum(1 for field in core_fields if field and field.strip())
    
    # Additional fields that add confidence
    additional_fields = [
        document_data.date_of_birth,
        document_data.date_of_issue,
        document_data.date_of_expiry,
        document_data.nationality,
        document_data.country,
        document_data.sex
    ]
    
    valid_additional_fields = sum(1 for field in additional_fields if field and field.strip())
    
    # Require at least 2 core fields and 2 additional fields
    return valid_core_fields >= 2 and valid_additional_fields >= 2


def get_relevant_fields(document_data: DocumentData) -> Dict[str, Any]:
    """
    Get only the relevant fields for the specific document type, removing null/irrelevant fields
    
    Args:
        document_data: Complete DocumentData object
        
    Returns:
        Dictionary with only relevant fields for the document type
    """
    # Always include core fields
    relevant_data = {
        "document_type": document_data.document_type,
        "extraction_method": document_data.extraction_method,
    }
    
    # Add non-null core identity fields
    core_identity_fields = [
        "country", "surname", "given_names", "full_name", "nationality", 
        "sex", "date_of_birth", "place_of_birth", "document_number", 
        "date_of_issue", "date_of_expiry", "issuing_authority"
    ]
    
    for field in core_identity_fields:
        value = getattr(document_data, field, None)
        if value is not None:
            relevant_data[field] = value
    
    # Add document-specific fields based on document type
    doc_type = document_data.document_type.lower() if document_data.document_type else ""
    
    if "passport" in doc_type:
        passport_fields = ["passport_type", "mrz_lines", "nin"]
        for field in passport_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
                
    elif "driver" in doc_type or "license" in doc_type:
        driver_fields = ["license_class", "vehicle_categories", "restrictions", "endorsements"]
        for field in driver_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
                
    elif "voter" in doc_type or "voting" in doc_type:
        voter_fields = ["voting_district", "voter_number", "polling_unit", "voter_status"]
        for field in voter_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
                
    elif "nin" in doc_type:
        nin_fields = ["nin", "nin_tracking_id"]
        for field in nin_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
                
    elif "national" in doc_type or "id" in doc_type:
        id_fields = ["id_card_type", "nin"]
        for field in id_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
                
    elif "birth" in doc_type:
        birth_fields = ["birth_certificate_number", "birth_registration_date", "parents_names"]
        for field in birth_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
                
    elif "permit" in doc_type or "residence" in doc_type:
        permit_fields = ["permit_type", "permit_category"]
        for field in permit_fields:
            value = getattr(document_data, field, None)
            if value is not None:
                relevant_data[field] = value
    
    # Add confidence score if available
    if document_data.confidence_score is not None:
        relevant_data["confidence_score"] = document_data.confidence_score
    
    return relevant_data