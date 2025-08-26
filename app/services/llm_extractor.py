"""LLM-assisted extraction helpers: cleaning helpers, guidelines, and utilities for structuring OCR output."""

import os
import base64
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import io
import re
import requests
from dotenv import load_dotenv
from groq import Groq
from pdf2image import convert_from_bytes

from app.models.document_data import DocumentData, FieldWithConfidence
from app.services.document_type_detector import DocumentTypeDetector
from app.services.confidence_filter import filter_low_confidence_fields
from app.services.field_verifier import verify_extracted_fields


# pdf2image.convert_from_bytes is used for PDF -> image conversion

# --- Extra fields cleaning helpers (conservative, non-invasive) ---

# Patterns for meaningful fields
_DATE_RE = re.compile(r'\b(?:\d{1,2}[/\-. ]\d{1,2}[/\-. ]\d{2,4}|\d{4}-\d{2}-\d{2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b)', re.I)
_AMOUNT_RE = re.compile(r'(\$\s?\d[\d,]*(?:\.\d+)?|€\s?\d[\d,]*(?:\.\d+)?|£\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*\s?(USD|NGN|EUR|GBP))', re.I)
_NIN_RE = re.compile(r'\b\d{6,14}\b')  # broad numeric id pattern
_MRZ_RE = re.compile(r'P\<[A-Z0-9<]{10,}|\b[A-Z0-9<]{20,}\b')
_ADDRESS_HINT_RE = re.compile(r'\b(street|st|road|rd|ave|avenue|blvd|lane|ln|drive|dr|court|ct|way|suite|ste|city|province|state|county|district)\b', re.I)
_NAME_RE = re.compile(r'^[A-Z][A-Z\s\-]{2,}$')  # uppercase name blocks typical of IDs/passports

ROLE_KEYWORDS = ['grantor', 'grantee', 'owner', 'lessee', 'landlord', 'applicant', 'tenant', 'seller', 'buyer']


def _is_english_like(s: str, min_ratio: float = 0.4) -> bool:
    if not s or not isinstance(s, str):
        return False
    letters = sum(1 for ch in s if ch.isalpha())
    total = len(s)
    if total == 0:
        return False
    return (letters / total) >= min_ratio


def _extract_role_name(s: str):
    if not s:
        return None, None
    s_clean = s.replace('“', '"').replace('”', '"')
    for kw in ROLE_KEYWORDS:
        if kw in s_clean.lower():
            # bracketed uppercase name
            m = re.search(r'\[([A-Z][A-Z\s\-\.]{2,})\]', s_clean)
            if m:
                return kw, m.group(1).strip()
            # Name before role in parentheses
            m2 = re.search(r'([A-Z][A-Z\s\-\.]{2,})[,;\)]?\s*\(.*?\b' + re.escape(kw) + r'\b', s_clean, re.I)
            if m2:
                return kw, m2.group(1).strip()
            # "Name (the Grantor)" style
            m3 = re.search(r'([A-Z][A-Z\s\-\.]{2,})\s*\(.*?\b' + re.escape(kw) + r'\b', s_clean, re.I)
            if m3:
                return kw, m3.group(1).strip()
            # fallback capitalized name
            m4 = re.search(r'([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)', s_clean)
            if m4:
                return kw, m4.group(1).strip()
    return None, None


def _normalize_field_name(k: str) -> str:
    kn = re.sub(r'[^a-zA-Z0-9_ ]', '', k).strip().lower().replace(' ', '_')
    return kn or k


def is_meaningful_field_value(value: str) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    if len(v) < 3:
        return False
    if _DATE_RE.search(v) or _AMOUNT_RE.search(v) or _NIN_RE.search(v) or _MRZ_RE.search(v):
        return True
    if _ADDRESS_HINT_RE.search(v):
        return True
    if _NAME_RE.match(v):
        return True
    if not _is_english_like(v, min_ratio=0.35):
        return False
    words = v.split()
    if any(char.isdigit() for char in v) or 1 < len(words) <= 6:
        return True
    return False


def clean_extra_fields(document: Dict[str, Any], min_confidence: float = 0.0) -> Dict[str, Any]:
    extra = document.get('extra_fields') or {}
    cleaned = {}
    role_mappings = {}

    for raw_k, fw in list(extra.items()):
        if isinstance(fw, dict):
            val = fw.get('value', '')
            conf = fw.get('confidence', 0.5)
        else:
            val = getattr(fw, 'value', '') if fw is not None else ''
            conf = getattr(fw, 'confidence', 0.5) if fw is not None else 0.5

        if not isinstance(val, str) or not val.strip():
            continue

        if conf < min_confidence:
            continue

        role, name = _extract_role_name(val)
        if role and name:
            key = f"{role}_name"
            existing = role_mappings.get(key)
            if not existing or conf > existing[1]:
                role_mappings[key] = (name, conf)
            continue

        if not is_meaningful_field_value(val):
            continue

        nk = _normalize_field_name(raw_k)
        if nk in cleaned:
            nk = nk + "_1"
        cleaned[nk] = {"value": val.strip(), "confidence": round(float(conf), 2)}

    for k, (name, conf) in role_mappings.items():
        cleaned[k] = {"value": name.strip(), "confidence": round(float(conf), 2)}

    document['extra_fields'] = cleaned
    return document

# --- end extra_fields helpers ---

UNIVERSAL_EXTRACTION_GUIDELINES = """
🎯 CORE MISSION:
Extract ONLY information that is EXPLICITLY VISIBLE in the document. Be accurate above all else.

🧠 EXTRACTION PHILOSOPHY:
1. VERIFIED CAPTURE: Extract ONLY structured information you can directly see and verify
2. INTELLIGENT FIELD MAPPING: Use standard schema fields when applicable, extra_fields for everything else  
3. DYNAMIC ADAPTATION: Adapt extraction strategy based on document type and content
4. ACCURACY FIRST: Only extract information that is explicitly visible - NEVER hallucinate fields
5. MEANINGFUL LABELING: Create descriptive field names that clearly indicate content
6. STRICT VERIFICATION: Every extracted field must be directly observable in the source document

🔧 UNIVERSAL GUIDELINES:
1. Extract ONLY fields that are explicitly present in the document - NEVER add non-existent fields
2. Use standard schema fields for common information (names, dates, document numbers, etc.)
3. Use 'extra_fields' for document-specific information that doesn't fit standard fields
4. For each extracted field, return an object with 'value'
5. Create meaningful field names in extra_fields that describe the content
6. Do not include explanations - return only the JSON structure
7. CRITICAL: Every field object MUST have both 'value' and 'confidence' properties

🔍 NON-STANDARD FIELD DETECTION:
1. Look for key-value pairs in the document (like "Field: Value" patterns)
2. Capture titled sections, headings, or labeled data
3. Extract structured information even if it doesn't fit standard fields
4. Use descriptive keys in extra_fields (e.g., "employer_name" instead of just "employer")
5. Pay special attention to document-specific fields that are critical to the document's purpose

⚠️ STRICT ANTI-HALLUCINATION REQUIREMENTS:
- ONLY extract information that you can literally see in the text or image
- NEVER infer, generate, guess, or assume any information not explicitly written
- If information is not clearly present, DO NOT include it - omit the field entirely
- Field omission is STRONGLY PREFERRED to hallucination - leave out uncertain fields
- Set low confidence scores (below 0.6) for fields where text is partially visible/unclear
- Better to extract NO fields than hallucinate even one field

🔴 CRITICAL VERIFICATION STEPS:
1. After extraction, verify each field value is DIRECTLY observable in the source document
2. Remove ANY field where you cannot point to its exact location in the document
3. For every field you extract, mentally note where exactly you see it in the document
4. If you're unsure about a field's existence or value, DO NOT include it
"""

def is_single_document(ocr_text: str) -> bool:
    """
    Determine if the OCR text represents a single document or multiple documents.
    Much smarter logic to avoid over-segmentation of single documents.
    
    Args:
        ocr_text: The raw OCR text from the document.
        
    Returns:
        bool: True if it's a single document, False if it's multiple documents.
    """
    if not ocr_text or not ocr_text.strip():
        print("📄 Empty or invalid OCR text - treating as single document")
        return True
    
    print(f"🔍 Analyzing OCR text for document boundaries (length: {len(ocr_text)} chars)")
    
    # For short texts, almost always single document
    if len(ocr_text.strip()) < 500:
        print("   📊 Short text - likely single document")
        return True
    
    # Look for clear indicators of multiple SEPARATE documents
    # These patterns indicate actual document separations, not just keywords within a document
    
    # Pattern 1: Multiple document headers/titles on separate lines
    lines = ocr_text.split('\n')
    document_header_patterns = [
        r'^\s*passport\s*$',
        r'^\s*driver.*license\s*$', 
        r'^\s*national.*id\s*$',
        r'^\s*voter.*card\s*$',
        r'^\s*birth.*certificate\s*$',
        r'^\s*land.*use.*agreement\s*$',
        r'^\s*contract\s*$',
        r'^\s*certificate\s*$'
    ]
    
    header_count = 0
    for line in lines:
        line_clean = line.strip().lower()
        for pattern in document_header_patterns:
            if re.match(pattern, line_clean):
                header_count += 1
                print(f"   🎯 Found document header: '{line.strip()}'")
                break
    
    # Pattern 2: Look for multiple complete document structures
    # Check for repeated critical combinations that indicate separate documents
    document_number_patterns = [
        r'passport\s+no[:\s]*([a-zA-Z0-9]+)',
        r'license\s+no[:\s]*([a-zA-Z0-9]+)', 
        r'id\s+no[:\s]*([a-zA-Z0-9]+)',
        r'certificate\s+no[:\s]*([a-zA-Z0-9]+)'
    ]
    
    unique_documents = set()
    for pattern in document_number_patterns:
        matches = re.findall(pattern, ocr_text.lower())
        for match in matches:
            if len(match) > 3:  # Valid document number
                unique_documents.add(match)
                print(f"   🔢 Found document number: {match}")
    
    # Pattern 3: Check for multiple name+DOB combinations (indicating different people)
    name_dob_combinations = 0
    name_patterns = [r'(surname|name)[:\s]*([a-zA-Z\s]+)', r'given\s+names?[:\s]*([a-zA-Z\s]+)']
    dob_patterns = [r'date\s+of\s+birth[:\s]*([0-9/\-\s]+)', r'dob[:\s]*([0-9/\-\s]+)']
    
    names_found = []
    dobs_found = []
    
    for pattern in name_patterns:
        matches = re.findall(pattern, ocr_text.lower())
        for match in matches:
            if isinstance(match, tuple):
                name = match[1].strip()
            else:
                name = match.strip()
            if len(name) > 3:
                names_found.append(name)
    
    for pattern in dob_patterns:
        matches = re.findall(pattern, ocr_text.lower())
        for match in matches:
            if len(match) > 5:
                dobs_found.append(match)
    
    # Decision logic
    is_single = True
    
    # Be MUCH more conservative about splitting documents
    # Only split on very strong evidence of multiple DISTINCT documents
    
    # Multiple document headers - but be smarter about repeated headers/footers
    if header_count > 2:  # Changed from >1 to >2 to be more conservative
        print(f"   📊 Multiple document headers ({header_count}) - investigating further...")
        
        # Additional check: Are these different document types or just repeated headers?
        # If it's the same header repeated (like in footers), don't split
        unique_headers = set()
        for line in lines:
            line_clean = line.strip().lower()
            for pattern in document_header_patterns:
                if re.match(pattern, line_clean):
                    unique_headers.add(line_clean)
                    break
        
        # Only split if we have multiple DIFFERENT document types
        if len(unique_headers) > 1:
            print(f"   ⚠️ Multiple different document types: {unique_headers}")
            is_single = False
        else:
            print(f"   ✅ Same document type repeated - treating as single document")
    
    # Multiple unique document numbers indicate multiple documents
    elif len(unique_documents) > 1:
        print(f"   📊 Multiple unique document numbers ({len(unique_documents)}) - likely multiple documents")
        is_single = False
    
    # Multiple name+DOB combinations for different people - be more conservative
    elif len(set(names_found)) > 2 and len(dobs_found) > 1:  # Increased threshold
        print(f"   📊 Multiple people detected - likely multiple documents")
        is_single = False
    
    # Special case: Very long text with clear document separators
    elif len(ocr_text.strip()) > 3000:  # Increased threshold
        # Look for clear document separators
        separator_patterns = [
            r'\n\s*-{5,}\s*\n',  # Longer horizontal lines
            r'\n\s*={5,}\s*\n',  # Longer equal signs
            r'\bdocument\s+\d+\s+of\s+\d\b',
            r'\bseparate\s+document\b',  # Explicit "separate document"
            r'\bnew\s+document\b'  # Explicit "new document"
        ]
        
        separator_count = 0
        for pattern in separator_patterns:
            matches = re.findall(pattern, ocr_text.lower())
            if matches:
                separator_count += len(matches)
        
        if separator_count > 1:
            print(f"   📊 Long text with clear separators ({separator_count}) - likely multiple documents")
            is_single = False
    
    # For typical single documents (passports, IDs, etc.), keywords within the document are normal
    # Don't split based on keyword count alone - this was the main issue
    
    result = "single" if is_single else "multiple"
    print(f"   ✅ Document analysis result: {result} document(s)")
    
    return is_single

def split_text_by_document(ocr_text: str) -> List[str]:
    """
    Split OCR text into segments based on document boundaries.
    Only performs segmentation if multiple documents are detected.
    
    Args:
        ocr_text: The raw OCR text from a page.
        
    Returns:
        A list of text segments, each representing a separate document.
    """
    if not ocr_text or not ocr_text.strip():
        return [ocr_text] if ocr_text else []
    
    print("🔄 Starting document segmentation analysis...")
    
    # First check if this is a single document
    if is_single_document(ocr_text):
        print("   ✅ Single document detected - no segmentation needed")
        return [ocr_text.strip()]
    
    print("   📄 Multiple documents detected - proceeding with segmentation...")
    
    # Define keywords or patterns that indicate document boundaries
    document_keywords = [
        "passport", "driver", "license", "driving license", "national id", "national identity", 
        "voter registration", "voter id", "birth certificate", "work permit", "residence permit",
        "nin", "national identification", "identity card", "id card", "social security",
        "land use agreement", "certificate", "permit", "visa", "travel document"
    ]
    
    # Additional patterns for document detection
    document_patterns = [
        r"document\s+(type|no|number)",
        r"passport\s+(no|number)",
        r"license\s+(no|number)",
        r"certificate\s+(no|number)",
        r"registration\s+(no|number)",
        r"id\s+(no|number)",
        r"card\s+(no|number)"
    ]
    
    # Split text into lines
    lines = ocr_text.split("\n")
    segments = []
    current_segment = []
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Check if this line indicates a new document
        is_new_document = False
        
        # Check keywords
        for keyword in document_keywords:
            if keyword in line_lower and len(line_lower) <= 100:  # Avoid matching in long paragraphs
                is_new_document = True
                print(f"   🎯 Found document boundary at line {i+1}: '{keyword}' in '{line[:50]}...'")
                break
        
        # Check patterns
        if not is_new_document:
            for pattern in document_patterns:
                if re.search(pattern, line_lower):
                    is_new_document = True
                    print(f"   🎯 Found pattern boundary at line {i+1}: '{pattern}' in '{line[:50]}...'")
                    break
        
        # If a new document is detected and we have content in current segment
        if is_new_document and current_segment and len("\n".join(current_segment).strip()) > 30:
            # Save the current segment
            segment_text = "\n".join(current_segment).strip()
            if segment_text:
                segments.append(segment_text)
                print(f"   📝 Saved segment {len(segments)} (length: {len(segment_text)} chars)")
            current_segment = []
        
        current_segment.append(line)
    
    # Add the last segment
    if current_segment:
        segment_text = "\n".join(current_segment).strip()
        if segment_text:
            segments.append(segment_text)
            print(f"   📝 Saved final segment {len(segments)} (length: {len(segment_text)} chars)")
    
    # If no segments were found, return the original text as a single segment
    if not segments:
        segments = [ocr_text.strip()] if ocr_text.strip() else []
        print("   ⚠️ No segments found - returning original text as single segment")
    
    # Filter out very short segments (likely noise)
    filtered_segments = [seg for seg in segments if len(seg.strip()) > 30]
    
    # Quality check: if we only have one meaningful segment, treat as single document
    if len(filtered_segments) <= 1:
        print("   ⚠️ Only one meaningful segment found - treating as single document")
        return [ocr_text.strip()]
    
    print(f"   ✅ Successfully segmented into {len(filtered_segments)} documents")
    return filtered_segments

def get_image_bytes_from_input(input_source: Union[bytes, str]) -> bytes:
    """
    Accepts image bytes, file path, or a URL (image/PDF).
    If input is a URL, downloads and returns image bytes.
    If PDF, extracts the first page as an image.
    If file path, reads and returns bytes.
    Supports HTTP(S) URLs and local file paths. (Google Drive special handling removed)
    """
    if isinstance(input_source, bytes):
        return input_source

    if isinstance(input_source, str):
        # Note: Google Drive-specific handling removed. Use standard HTTP(S) handling below.

        # Handle standard URLs
        if input_source.startswith("http"):
            print(f"🔗 Downloading from URL: {input_source[:60]}...")
            try:
                response = requests.get(input_source)
                if response.status_code != 200:
                    raise ValueError(f"Failed to download URL. Status code: {response.status_code}")
                
                content_type = response.headers.get("Content-Type", "")
                print(f"📊 Content type detected: {content_type}")
                
                # Process based on content type or file extension
                if "pdf" in content_type.lower() or input_source.lower().endswith(".pdf"):
                    # Convert first page of PDF to image bytes
                    print("📄 Converting PDF to image...")
                    try:
                        images = convert_from_bytes(response.content, first_page=1, last_page=1)
                        img_byte_arr = io.BytesIO()
                        img = images[0]
                        if img.mode == 'RGBA':
                            img = img.convert('RGB')
                        img.save(img_byte_arr, format='JPEG')
                        return img_byte_arr.getvalue()
                    except Exception as e:
                        raise ValueError(f"Error converting PDF to image: {str(e)}")
                elif any(img_type in content_type.lower() for img_type in ["image/jpeg", "image/jpg", "image/png"]):
                    # Process as image
                    print("🖼️ Processing as image from content type...")
                    return response.content
                elif input_source.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Process as image based on extension
                    print("🖼️ Processing as image from file extension...")
                    return response.content
                else:
                    # Try to detect content type based on binary signature
                    try:
                        print("🔍 Attempting to detect content type from binary data...")
                        if response.content.startswith(b'%PDF'):
                            print("📄 Detected PDF signature, converting to image...")
                            images = convert_from_bytes(response.content, first_page=1, last_page=1)
                            img_byte_arr = io.BytesIO()
                            img = images[0]
                            if img.mode == 'RGBA':
                                img = img.convert('RGB')
                            img.save(img_byte_arr, format='JPEG')
                            return img_byte_arr.getvalue()
                        elif response.content.startswith(b'\xff\xd8\xff'):
                            print("🖼️ Detected JPEG signature, processing as image...")
                            return response.content
                        elif response.content.startswith(b'\x89PNG\r\n\x1a\n'):
                            print("🖼️ Detected PNG signature, processing as image...")
                            return response.content
                        else:
                            raise ValueError(f"Unsupported file format. Content type: {content_type}")
                    except Exception as e:
                        raise ValueError(f"Failed to process content from URL: {str(e)}")
            except Exception as e:
                raise ValueError(f"Error accessing URL: {str(e)}")
                
        # Handle local file path
        elif input_source.lower().endswith(('.png', '.jpg', '.jpeg')):
            try:
                with open(input_source, "rb") as f:
                    return f.read()
            except Exception as e:
                raise ValueError(f"Error reading image file: {str(e)}")
        elif input_source.lower().endswith('.pdf'):
            try:
                with open(input_source, "rb") as f:
                    images = convert_from_bytes(f.read(), first_page=1, last_page=1)
                    img_byte_arr = io.BytesIO()
                    img = images[0]
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    img.save(img_byte_arr, format='JPEG')
                    return img_byte_arr.getvalue()
            except Exception as e:
                raise ValueError(f"Error processing PDF file: {str(e)}")
        else:
            raise ValueError("Unsupported file type or path. Please use image files (PNG, JPG, JPEG), PDF files, or valid URLs.")

    raise ValueError("Input must be image bytes, file path, or a valid URL (image or PDF)")
    
    
# Load environment variables from .env file
load_dotenv()

# Get environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class VisionLLMExtractor:
    """Class to extract document data directly from images using Vision LLM"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Vision LLM extractor with API credentials"""
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable or pass it to the constructor.")

        # Initialize the Groq client for vision processing
        self.client = Groq(api_key=self.api_key)
        
        # Initialize document type detector for intelligent extraction
        self.document_detector = DocumentTypeDetector()

    def _generate_dynamic_extraction_prompt(self, ocr_text: str) -> Tuple[str, str, Dict[str, any]]:
        """
        Generate dynamic extraction prompts based on document type detection.
        
        Args:
            ocr_text: Raw OCR text for analysis
        Returns:
            Tuple of (system_prompt, user_prompt, detection_info)
        """
        # Detect document type
        doc_type, confidence, analysis = self.document_detector.detect_document_type(ocr_text)
        extraction_strategy = self.document_detector.get_extraction_strategy(doc_type)
        print(f"📋 Detected document type: {doc_type} (confidence: {confidence:.2f})")

        # Base system prompt - universal for all documents
        base_system_prompt = f"You are an expert document analyzer specialized in comprehensive extraction of structured data from any type of document.\n\n{UNIVERSAL_EXTRACTION_GUIDELINES}"

        # Add document-type specific guidance
        if doc_type and doc_type != "unknown_document":
            doc_specific_guidance = self._get_document_specific_guidance(doc_type, extraction_strategy)
            system_prompt = f"{base_system_prompt}\n\n🎯 DOCUMENT-SPECIFIC STRATEGY:\n{doc_specific_guidance}"
        else:
            system_prompt = f"{base_system_prompt}\n\n🎯 UNIVERSAL EXTRACTION STRATEGY:\nThis appears to be a general document. Focus on extracting ALL meaningful structured information using both standard fields and comprehensive extra_fields."

        # Generate adaptive user prompt
        user_prompt = self._generate_adaptive_user_prompt(ocr_text, doc_type, extraction_strategy)

        detection_info = {
            "detected_type": doc_type,
            "confidence": confidence,
            "analysis": analysis,
            "extraction_strategy": extraction_strategy
        }

        return system_prompt, user_prompt, detection_info
    
    def _get_document_specific_guidance(self, doc_type: str, strategy: Dict[str, any]) -> str:
        """Get specific extraction guidance based on document type"""
        
        guidance_templates = {
            "land_use_restriction_agreement": """
            📋 LAND USE RESTRICTION AGREEMENT EXTRACTION:
            - Focus Fields: Extract parties (grantor, grantee), property details, restrictions, dates, duration
            - Key Extra Fields: 'grantor_name', 'grantor_address', 'grantee_name', 'grantee_address', 'property_location', 'property_description', 'restrictions_list', 'agreement_duration', 'effective_date', 'termination_conditions'
            - Look for: Party names and addresses, property location and description, specific restrictions (commercial use, building height, tree removal, etc.), duration/term of restrictions, effective dates
            """,
            
            "contract": """
            📋 CONTRACT/AGREEMENT EXTRACTION:
            - Focus Fields: Extract contracting parties, contract terms, dates, obligations
            - Key Extra Fields: 'contracting_party_1', 'contracting_party_2', 'contract_purpose', 'terms_and_conditions', 'obligations', 'payment_terms', 'duration', 'termination_clauses'
            - Look for: Party details, contract purpose, specific terms and conditions, payment obligations, duration, termination provisions
            """,
            
            "international_passport": """
            📋 PASSPORT EXTRACTION:
            - Focus Fields: surname, given_names, nationality, document_number, date_of_birth, date_of_expiry, issuing_authority
            - Key Extra Fields: 'passport_type', 'place_of_birth', 'mrz_line_1', 'mrz_line_2'
            - Look for: Personal details, document specifics, MRZ data if present
            """,
            
            "invoice": """
            📋 INVOICE EXTRACTION:
            - Focus Fields: date_of_issue, document_number
            - Key Extra Fields: 'invoice_number', 'seller_name', 'seller_address', 'buyer_name', 'buyer_address', 'items_description', 'total_amount', 'tax_amount', 'payment_terms', 'due_date'
            - Look for: Invoice details, parties involved, itemized charges, amounts, payment information
            """,
            
            "certificate": """
            📋 CERTIFICATE EXTRACTION:
            - Focus Fields: date_of_issue, issuing_authority
            - Key Extra Fields: 'certificate_type', 'recipient_name', 'achievement_description', 'institution_name', 'qualification_level', 'grade_or_score', 'certificate_number'
            - Look for: Certificate type, recipient details, achievement/qualification, issuing institution, grades/scores
            """
        }
        
        # Get specific guidance or use general approach
        return guidance_templates.get(doc_type, f"""
        📋 {doc_type.upper().replace('_', ' ')} EXTRACTION:
        - Focus Fields: {', '.join(strategy.get('focus_fields', ['date_of_issue']))}
        - Key Extra Fields: Look for document-specific meaningful content and create descriptive field names
        - Strategy: {strategy.get('extraction_priority', 'comprehensive')} extraction approach
        """)
    
    def _generate_adaptive_user_prompt(self, ocr_text: str, doc_type: str, strategy: Dict[str, any]) -> str:
        """Generate user prompt adapted to the specific document type"""
        
        base_prompt = f"""ACCURATE DOCUMENT EXTRACTION FROM OCR TEXT:

        Analyze this OCR text and extract ONLY information that is EXPLICITLY present. Prioritize accuracy over completeness.

        DETECTED DOCUMENT TYPE: {doc_type}
        EXTRACTION STRATEGY: {strategy.get('extraction_priority', 'accuracy-first')}

        OCR TEXT:
        {ocr_text}

        🎯 EXTRACTION REQUIREMENTS:

        ✅ ACCURACY-FIRST APPROACH:
        - Read every line of the OCR text carefully
        - Extract ONLY standard schema fields that have corresponding data clearly in the text
        - Use extra_fields to capture additional meaningful information that appears in the text
        - Create descriptive field names for extra_fields

        🔴 STRICT ANTI-HALLUCINATION PROTOCOL:
        - ONLY extract information that you can literally see in the OCR text above
        - For EACH field you extract, identify exactly where in the text you see it
        - NEVER infer, generate, guess, or assume any information not explicitly written
        - If information is not clearly present in the text, DO NOT include it - omit the field entirely
        - Field omission is STRONGLY PREFERRED to hallucination - leave out uncertain fields
        - Set low confidence scores (below 0.6) for fields where text is unclear
        - Better to extract NO fields than hallucinate even one field

        📋 DOCUMENT-SPECIFIC EXTRACTION FOCUS:
        """
        
        # Add document-specific extraction instructions
        if doc_type == "land_use_restriction_agreement":
            specific_instructions = """
        🏘️ LAND USE AGREEMENT FOCUS:
        - Identify and extract grantor and grantee information (names, addresses)
        - Extract property location and description details
        - Capture all restrictions mentioned (commercial use, building height, environmental, etc.)
        - Extract duration/term information and effective dates
        - Look for legal terminology and conditions
        """
        elif doc_type in ["contract", "legal_agreement"]:
            specific_instructions = """
        📝 CONTRACT/AGREEMENT FOCUS:
        - Identify all contracting parties and their details
        - Extract contract purpose and scope
        - Capture terms, conditions, and obligations
        - Extract payment terms and schedules if mentioned
        - Look for duration, termination, and renewal clauses
        """
        elif "certificate" in doc_type:
            specific_instructions = """
        🏆 CERTIFICATE FOCUS:
        - Extract recipient name and achievement details
        - Capture issuing institution/authority information
        - Look for qualification levels, grades, or scores
        - Extract dates (issue, completion, validity)
        - Capture certificate number or reference codes
        """
        elif doc_type in ["invoice", "financial_document"]:
            specific_instructions = """
        💰 FINANCIAL DOCUMENT FOCUS:
        - Extract parties involved (seller, buyer, client, vendor)
        - Capture all monetary amounts and calculations
        - Look for itemized descriptions and quantities
        - Extract payment terms and due dates
        - Capture tax information and totals
        """
        else:
            specific_instructions = """
        📄 UNIVERSAL DOCUMENT FOCUS:
        - Extract all person/entity names and contact information
        - Capture all dates, numbers, and reference codes
        - Look for addresses, locations, and geographic information
        - Extract any structured data, terms, or conditions
        - Capture document-specific content using descriptive field names
        """
        
        final_prompt = f"""{base_prompt}{specific_instructions}

        🎯 FIELD NAMING FOR EXTRA_FIELDS:
        - Use descriptive names that clearly indicate content
        - Be specific: 'property_address' not 'address', 'restriction_details' not 'restrictions'  
        - Use domain-appropriate terms based on document content

        🔍 VERIFICATION STEPS (DO THIS FOR EACH FIELD):
        1. Before including any field, verify the exact text exists in the OCR content above
        2. For each field you plan to extract, ask: "Can I find this exact text in the document?"
        3. If YES - include the field with appropriate confidence
        4. If NO - DO NOT include the field, even if you believe it should exist
        5. If PARTIAL/UNCLEAR - set confidence below 0.6 and only include exact visible text

        ✅ STRICT VALIDATION CHECKLIST:
        - Every extracted field MUST have corresponding text in the OCR - NO EXCEPTIONS
        - Field values MUST be exactly as written (or standardized dates)
        - NO information should be generated, inferred, or assumed
        - Preserve exact spelling and content from the source
        - When in doubt, OMIT the field rather than risk hallucination
        - Double-check ALL fields against the OCR text before submitting

        🎯 SUCCESS CRITERIA:
        - Accuracy: Only extract what you can verify in the OCR text
        - Zero hallucination: No fields that aren't explicitly in the text
        - Well-structured: Use appropriate field names and organize information clearly
        - Appropriate confidence: Use lower confidence for unclear fields

        Return the data in JSON format. ACCURACY IS MORE IMPORTANT THAN COMPLETENESS!"""
                
        return final_prompt

    async def extract_from_image(self, image_bytes: bytes) -> DocumentData:
        """
        Extract document data directly from image using Vision LLM

        Args:
            image_bytes: Binary content of the image

        Returns:
            DocumentData object with structured information
        """
        try:
            # Convert image bytes to base64 for API
            base64_image = base64.b64encode(image_bytes).decode('utf-8')

            # Use Groq's meta-llama/llama-4-scout-17b-16e-instruct model with Vision capability
            completion = self.client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",  # Groq's model with vision capabilities
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert document analyzer specialized in accurate extraction of structured data from any type of document.\n\nCORE MISSION:\nExtract ONLY information EXPLICITLY VISIBLE in the document. Accuracy is your absolute top priority.\n\nEXTRACTION PHILOSOPHY:\n1. VERIFIED CAPTURE: Extract ONLY structured information you can directly see and verify\n2. INTELLIGENT FIELD MAPPING: Use standard schema fields when applicable, extra_fields for everything else\n3. DYNAMIC ADAPTATION: Adapt extraction strategy based on document type and content\n4. ACCURACY FIRST: Only extract information that is explicitly visible - NEVER hallucinate fields\n5. MEANINGFUL LABELING: Create descriptive field names that clearly indicate content\n\nSTRICT GUIDELINES:\n1. Extract ONLY fields that are EXPLICITLY present in the document\n2. Use standard schema fields for common information (names, dates, document numbers, etc.)\n3. Use 'extra_fields' for document-specific information that doesn't fit standard fields\n4. For each extracted field, return an object with 'value' (the extracted text) and 'confidence' (0-1)\n5. Create meaningful field names in extra_fields that describe the content\n6. Do not include explanations - return only the JSON structure\n7. CRITICAL: Every field object MUST have both 'value' and 'confidence' properties\n\n🔴 STRICT ANTI-HALLUCINATION REQUIREMENTS:\n1. ONLY extract information you can literally see in the document\n2. NEVER infer, generate, guess, or assume any information not explicitly visible\n3. If information is not clearly present, DO NOT include it - omit the field entirely\n4. Field omission is STRONGLY PREFERRED to hallucination - leave out uncertain fields\n5. Set low confidence scores (below 0.6) for fields where text is partially visible/unclear\n6. For EVERY field you extract, mentally note where exactly you see it in the document\n7. If you're unsure about a field's existence or value, DO NOT include it\n\nREMEMBER: Accuracy is MUCH more important than completeness. Better to return fewer accurate fields than to include any hallucinated ones."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "ACCURATE DOCUMENT EXTRACTION FROM IMAGE:\n\nAnalyze this document image and extract ONLY information that is explicitly visible. Be extremely accurate and avoid hallucination.\n\nACCURACY-FIRST EXTRACTION STRATEGY:\n1. Document Understanding: Carefully examine the entire document image\n2. Document Type Detection: Identify the specific type from visible headers, titles, logos, or structure\n3. Verified Information Extraction: Extract ONLY clearly visible structured information\n4. Smart Field Mapping: Use standard schema fields when applicable, extra_fields for everything else\n5. Careful Processing: For ANY document type, look for and extract ONLY what you can verify:\n   - Personal/Entity information (names, addresses, contact details)\n   - Identification numbers (document numbers, registration numbers, codes, IDs)\n   - Dates (issue, expiry, birth, registration, effective dates)\n   - Location data (addresses, districts, regions, countries)\n   - Classification/Status information\n   - Authority/Issuing body information\n   - Document-specific content (terms, conditions, specifications, restrictions)\n   - Any other structured data CLEARLY visible in the image\n\n🔴 ANTI-HALLUCINATION PROTOCOL:\n1. For EACH field you extract, ensure you can see it clearly in the image\n2. If text is blurry, partially visible, or uncertain - set confidence below 0.6\n3. If you cannot clearly see a field in the image - DO NOT INCLUDE IT\n4. NEVER infer missing information - only extract what's explicitly visible\n5. Field omission is STRONGLY PREFERRED over hallucination\n\nKEY PRINCIPLES:\n- VERIFICATION FIRST: Only extract fields you can verify in the image\n- STRICT ACCURACY: Better to extract fewer accurate fields than many uncertain ones\n- USE DESCRIPTIVE FIELD NAMES: Create meaningful labels in extra_fields\n- PRESERVE EXACT TEXT: Use the exact text visible in the document\n- CONFIDENCE SCORING: Use lower confidence scores (0.3-0.6) for unclear text\n\nReturn ONLY valid JSON in the DocumentData schema format. Every field object must have both 'value' and 'confidence' properties. Prioritize accuracy over comprehensiveness."
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
                max_tokens=2048,  # Increased from 1024 to allow for comprehensive extraction
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_data",
                        "schema": DocumentData.model_json_schema()
                    }
                }
            )

            # Parse the JSON response and create DocumentData directly
            response_content = completion.choices[0].message.content
            
            # Log the raw response for debugging
            print(f"DEBUG: Vision LLM raw response: {response_content}")
            
            # Validate response before parsing
            if not response_content or not response_content.strip():
                raise ValueError("Empty response from Vision LLM.")
            
            extracted_data = json.loads(response_content)
            
            # Clean and validate the extracted data to ensure schema compliance
            cleaned_data = self._clean_extracted_data(extracted_data)

            # Create DocumentData object directly (schema validation handled by Groq)
            document_data = DocumentData.model_validate(cleaned_data)
            document_data.extraction_method = FieldWithConfidence(value="Vision LLM (meta-llama/llama-4-scout-17b-16e-instruct)", confidence=1.0)

            return document_data

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response from Vision LLM: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to extract data using Vision LLM: {str(e)}")

    def _clean_extracted_data(self, data: dict) -> dict:
        """
        Clean and validate extracted data to ensure schema compliance
        """
    # FieldWithConfidence is already imported at module level
        
        # Ensure all field objects have both value and confidence
        def ensure_field_format(field_data):
            if field_data is None:
                return None
            if isinstance(field_data, dict):
                if 'value' in field_data:
                    return {
                        'value': field_data['value'],
                        'confidence': field_data.get('confidence', 0.8)  # Default confidence if missing
                    }
                else:
                    # If it's a dict but not in field format, convert it
                    return {
                        'value': str(field_data),
                        'confidence': 0.7
                    }
            else:
                # If it's a direct value, wrap it in field format
                return {
                    'value': field_data,
                    'confidence': 0.7
                }
        
        # Handle list fields specially
        def ensure_list_field_format(field_data):
            if field_data is None:
                return None
            if isinstance(field_data, list):
                # If it's already a list, ensure each item is in FieldWithConfidence format
                return [ensure_field_format(item) for item in field_data]
            elif isinstance(field_data, dict) and 'value' in field_data:
                # If it's a FieldWithConfidence with a list value, convert properly
                if isinstance(field_data['value'], list):
                    confidence = field_data.get('confidence', 0.8)
                    return [{'value': item, 'confidence': confidence} for item in field_data['value']]
                else:
                    # Single item, wrap in list
                    return [field_data]
            else:
                # Direct value, wrap in field format and list
                return [ensure_field_format(field_data)]
        
        # Define which fields are lists
        list_fields = ['mrz_lines', 'vehicle_categories']
        
        # Define which fields should remain as plain values (not FieldWithConfidence)
        plain_value_fields = ['confidence_score']  # Removed 'page_number'

        # Clean all fields in the data
        cleaned = {}
        known_fields = set(DocumentData.model_fields.keys())
        
        # First, process all known fields from the schema
        for key, value in data.items():
            if key == 'extra_fields' and isinstance(value, dict):
                # Special handling for extra_fields
                cleaned[key] = {k: ensure_field_format(v) for k, v in value.items()}
            elif key in plain_value_fields:
                # These should remain as plain values
                if isinstance(value, dict) and 'value' in value:
                    # Extract the actual value if it's wrapped
                    cleaned[key] = value['value']
                else:
                    cleaned[key] = value
            elif key in list_fields:
                # Handle list fields specially
                cleaned[key] = ensure_list_field_format(value)
            elif key == 'extraction_method':
                # Ensure extraction_method is in correct format
                cleaned[key] = ensure_field_format(value)
            else:
                # All other fields should be FieldWithConfidence objects
                cleaned[key] = ensure_field_format(value)

        # Remove 'page_number' from the cleaned data if it exists
        cleaned.pop('page_number', None)
        
        # Additional debugging for cleaned data
        print(f"🧹 Cleaned data fields: {list(cleaned.keys())}")
        
        # Move any unknown fields to extra_fields
        unknown_fields = {}
        for key in list(cleaned.keys()):
            if key not in known_fields and key != 'extra_fields':
                print(f"🔄 Moving unknown field '{key}' to extra_fields")
                unknown_fields[key] = cleaned[key]
                cleaned.pop(key)
        
        # Add unknown fields to extra_fields
        if unknown_fields:
            if 'extra_fields' not in cleaned or cleaned['extra_fields'] is None:
                cleaned['extra_fields'] = {}
            cleaned['extra_fields'].update(unknown_fields)
            print(f"✅ Added {len(unknown_fields)} unknown fields to extra_fields")
        
        if 'page_number' in cleaned:
            print("⚠️ WARNING: page_number still present after cleaning!")
        else:
            print("✅ page_number successfully removed from cleaned data")

        return cleaned

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
                        "content": (
                            "You are an expert document analyzer specialized in comprehensive extraction from raw OCR text.\n\n"
                            "CORE MISSION:\n"
                            "Extract ALL meaningful information from OCR text. Be intelligent, comprehensive, and accurate.\n\n"
                            "EXTRACTION PHILOSOPHY:\n"
                            "1. MAXIMIZE INFORMATION CAPTURE: Extract ALL structured information, not just basic fields\n"
                            "2. INTELLIGENT PROCESSING: Adapt extraction strategy based on document type and content\n"
                            "3. COMPREHENSIVE COVERAGE: Use standard fields + extra_fields to capture complete document content\n"
                            "4. ACCURACY REQUIREMENT: Only extract information explicitly present in the OCR text\n\n"
                            "TASK:\n"
                            "Extract comprehensive structured document data from OCR text and return it in the exact JSON schema format required.\n\n"
                            "DOCUMENT TYPE DETECTION:\n"
                            "Be very specific about document types. Use these exact classifications:\n"
                            "- 'International Passport' (for international passports)\n"
                            "- 'national_id_card' (for national identity cards)\n"
                            "- 'drivers_license' (for driving licenses)\n"
                            "- 'voter_registration_card' (for voting cards - extract ALL visible voting information)\n"
                            "- 'nin_slip' or 'nin_card' (for National Identification Number documents)\n"
                            "- 'residence_permit' (for residence/work permits)\n"
                            "- 'birth_certificate' (for birth certificates)\n"
                            "- 'work_permit' (for employment authorization)\n"
                            "- 'social_security_card' (for social security documents)\n"
                            "- For OTHER document types: Use descriptive names like 'land_use_agreement', 'contract', 'certificate', 'invoice', etc.\n\n"
                            "STRICT EXTRACTION GUIDELINES:\n"
                            "1. FIRST: Carefully identify the exact document type from headers, titles, or document structure\n"
                            "2. INTELLIGENT FIELD EXTRACTION: Extract ALL meaningful information from the document\n"
                            "   - Standard schema fields: Use when the information matches predefined fields\n"
                            "   - Extra fields: Use for ANY additional meaningful information not covered by standard fields\n"
                            "   - IMPORTANT: Create new fields for ANY information not fitting standard fields\n"
                            "3. COMPREHENSIVE EXTRACTION: The goal is to capture ALL important document information, not just predefined fields\n"
                            "   - When you find information that doesn't fit standard fields, CREATE NEW FIELDS in the response\n"
                            "4. NO INFERENCE: Only extract fields that you can literally see in the OCR text\n"
                            "5. DYNAMIC FIELD DETECTION: For ANY document type, intelligently identify and extract:\n"
                            "   - Names, addresses, dates, numbers, codes, IDs\n"
                            "   - Document-specific information (voting details, property info, contract terms, etc.)\n"
                            "   - Organizational information (departments, authorities, agencies)\n"
                            "   - Status information, categories, classifications\n"
                            "   - Any other structured data visible in the document\n"
                            "6. INTELLIGENT LABELING: Create meaningful field names in extra_fields that describe the content\n"
                            "7. For dates: Only convert if the date is clearly present (e.g., '17 SEP 2023' → '2023-09-17')\n"
                            "8. For lists (mrz_lines, vehicle_categories): Only include if explicitly present\n"
                            "9. MANDATORY NULL CHECK: If a standard field doesn't appear in the text, set it to null\n"
                            "10. OCR ERROR HANDLING: Only correct obvious OCR mistakes that are clearly errors (O/0, I/1)\n"
                            "11. CONFIDENCE SCORING: Be conservative - lower confidence for uncertain extractions\n"
                            "12. For each extracted field, return an object with 'value' (EXACT text from document) and 'confidence' (0-1)\n"
                            "13. MAXIMIZE INFORMATION CAPTURE: Use 'extra_fields' extensively to capture ALL meaningful document content\n"
                            "14. VERIFICATION: Before including any field, verify it exists in the provided OCR text\n\n"
                            "REMEMBER: Better to extract fewer accurate fields than many inaccurate ones. Use 'extra_fields' when document contains unique information not covered by standard fields.\n"
                        )
                    },
                    {
                        "role": "user",
                        "content": f"COMPREHENSIVE BUT ACCURATE EXTRACTION:\n\nAnalyze this OCR text and extract ALL meaningful information that is EXPLICITLY present. Be comprehensive but strictly accurate.\n\nOCR TEXT:\n{full_text}\n\n🎯 EXTRACTION REQUIREMENTS:\n\n✅ COMPREHENSIVE COVERAGE:\n- Read every line of the OCR text carefully\n- Extract ALL standard schema fields that have corresponding data in the text\n- Use extra_fields to capture ALL additional meaningful information that appears in the text\n- PAY SPECIAL ATTENTION TO ADDRESS INFORMATION - this is a critical priority\n- Create descriptive field names for extra_fields\n\n⚠️ CRITICAL ACCURACY RULE:\n- ONLY extract information that you can literally see in the OCR text above\n- Do NOT infer, generate, or assume any information not explicitly written\n- If information is not clearly present in the text, do NOT include it\n\n📋 EXTRACTION STRATEGY:\n1. Document Type: Identify from headers/titles in the actual text\n2. Standard Fields: Extract only if the information is present in the OCR text\n3. Extra Fields: For ANY additional information that appears in the text but doesn't fit standard fields\n4. Field Values: Use the EXACT text from the OCR, preserving spelling and formatting\n5. Field Names: Create clear, descriptive names for extra_fields\n\n🎯 UNIVERSAL EXTRACTION GUIDELINES FOR ANY DOCUMENT:\n\nWhen you see these types of information in the OCR text, extract them:\n- Names (person names, organization names) → extract as seen\n- Addresses (complete or partial) → extract exactly as written\n- Dates (any format) → extract and standardize if clear\n- Numbers/IDs/Codes → extract exactly as shown\n- Document-specific content → extract into appropriate extra_fields\n- Legal terms, restrictions, conditions → extract if visible\n- Contact information → extract if present\n- Technical details, measurements → extract if shown\n- Organizational information → extract if mentioned\n\n� FIELD NAMING FOR EXTRA_FIELDS:\n- Use descriptive names: 'grantor_name', 'property_address', 'restriction_details'\n- Be specific: 'effective_date' not just 'date', 'height_restriction' not just 'restriction'\n- Use domain-appropriate terms based on document type\n\n✅ VALIDATION CHECKLIST:\n- Every extracted field must have corresponding text in the OCR\n- Field values must be exactly as written (or standardized dates)\n- No information should be generated or inferred\n- Use extra_fields extensively for comprehensive coverage\n- Preserve exact spelling and content from the source\n\n🎯 SUCCESS CRITERIA:\n- Comprehensive: Extract all meaningful information that's actually present\n- Accurate: Only extract what you can verify in the OCR text\n- Well-structured: Use appropriate field names and organize information clearly\n- Rich: Use extra_fields to capture document-specific content\n\nReturn the data in JSON format. Be both comprehensive AND accurate!"
                    }
                ],
                temperature=0.2,  # Reduced to prevent hallucination while maintaining comprehensiveness
                max_completion_tokens=2048,  # Increased from 1024 to allow for comprehensive extraction
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
            
            # Clean and validate the extracted data to ensure schema compliance
            vision_extractor = VisionLLMExtractor()
            cleaned_data = vision_extractor._clean_extracted_data(extracted_data)
            
            # Create DocumentData object directly (schema validation handled by Groq)
            document_data = DocumentData.model_validate(cleaned_data)
            document_data.extraction_method = FieldWithConfidence(value="OCR+LLM (Groq Kimi-K2)", confidence=1.0)
            return document_data
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response from OCR LLM: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to structure OCR text using LLM: {str(e)}")


# Ensure `get_relevant_fields` is defined before usage
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

    # Get document type for filtering
    doc_type = ""
    if document_data.document_type and hasattr(document_data.document_type, "value") and document_data.document_type.value:
        doc_type = document_data.document_type.value.lower()
    else:
        # If no document type, treat as non-identity document
        doc_type = ""

    # Define identity document types
    identity_doc_types = ["passport", "national_id", "drivers_license", "voter", "nin", "birth_certificate", "work_permit", "residence_permit", "social_security"]

    # Check if this is an identity document
    is_identity_doc = any(id_type in doc_type for id_type in identity_doc_types)

    if is_identity_doc:
        # For identity documents, include standard identity fields (only if they have values)
        core_identity_fields = [
            "country", "surname", "given_names", "full_name", "nationality",
            "sex", "date_of_birth", "place_of_birth", "document_number",
            "date_of_issue", "date_of_expiry", "issuing_authority",
            "address", "secondary_address", "phone_number", "email"  # Include address and contact info
        ]

        for field in core_identity_fields:
            field_obj = getattr(document_data, field, None)
            if field_obj and hasattr(field_obj, 'value') and field_obj.value:  # Only include if field has a value
                relevant_data[field] = field_obj

        # Add document-specific fields based on document type
        if "passport" in doc_type:
            passport_fields = ["passport_type", "mrz_lines", "nin"]
            for field in passport_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj:
                    # Handle both list fields (like mrz_lines) and value fields
                    if hasattr(field_obj, 'value') and field_obj.value:
                        relevant_data[field] = field_obj
                    elif isinstance(field_obj, list) and field_obj:
                        relevant_data[field] = field_obj
        elif "driver" in doc_type or "license" in doc_type:
            driver_fields = ["license_class", "vehicle_categories", "restrictions", "endorsements"]
            for field in driver_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj:
                    # Handle both list fields and value fields
                    if hasattr(field_obj, 'value') and field_obj.value:
                        relevant_data[field] = field_obj
                    elif isinstance(field_obj, list) and field_obj:
                        relevant_data[field] = field_obj
        elif "voter" in doc_type or "voting" in doc_type:
            # Comprehensive voter card fields
            voter_fields = [
                "voting_district", "voter_number", "polling_unit", "voter_status",
                "registration_date", "ward", "local_government", "state", "vin"  # Added common voter card fields
            ]
            for field in voter_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj and hasattr(field_obj, 'value') and field_obj.value:
                    relevant_data[field] = field_obj
            
            # Also include extra_fields for voter cards as they often have unique information
            if document_data.extra_fields:
                relevant_data["extra_fields"] = document_data.extra_fields
        elif "nin" in doc_type:
            nin_fields = ["nin", "nin_tracking_id"]
            for field in nin_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj and hasattr(field_obj, 'value') and field_obj.value:
                    relevant_data[field] = field_obj
        elif "national" in doc_type or "id" in doc_type:
            id_fields = ["id_card_type", "nin"]
            for field in id_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj and hasattr(field_obj, 'value') and field_obj.value:
                    relevant_data[field] = field_obj
        elif "birth" in doc_type:
            birth_fields = ["birth_certificate_number", "birth_registration_date", "parents_names"]
            for field in birth_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj and hasattr(field_obj, 'value') and field_obj.value:
                    relevant_data[field] = field_obj
        elif "permit" in doc_type or "residence" in doc_type:
            permit_fields = ["permit_type", "permit_category"]
            for field in permit_fields:
                field_obj = getattr(document_data, field, None)
                if field_obj and hasattr(field_obj, 'value') and field_obj.value:
                    relevant_data[field] = field_obj
    else:
        # For non-identity documents (contracts, agreements, certificates, etc.)
        # Include more fields that could be relevant to legal/business documents
        document_fields = [
            "country", "date_of_issue", "date_of_expiry", "document_number", 
            "issuing_authority", "full_name", "surname", "given_names",
            "address", "secondary_address", "phone_number", "email",  # Include address and contact info
            "state_province", "jurisdiction"  # Include location information
        ]
        
        for field in document_fields:
            field_obj = getattr(document_data, field, None)
            if field_obj and hasattr(field_obj, 'value') and field_obj.value:
                relevant_data[field] = field_obj
        
        print(f"ℹ️ Processing non-identity document: {doc_type or 'unknown'}")
        
        # For non-identity documents, extra_fields is especially important
        # as it contains most of the document-specific content

    # Include extra_fields when present and needed - available for all document types
    if hasattr(document_data, 'extra_fields') and document_data.extra_fields:
        relevant_data["extra_fields"] = document_data.extra_fields
        print(f"✅ Including extra_fields for {doc_type or 'unknown'} document: {list(document_data.extra_fields.keys())}")
    else:
        print(f"ℹ️ No extra_fields found for {doc_type or 'unknown'} document")

    # Clean extra_fields conservatively to remove non-meaningful entries
    try:
        if 'extra_fields' in relevant_data and isinstance(relevant_data['extra_fields'], dict):
            cleaned_doc = clean_extra_fields({'extra_fields': relevant_data['extra_fields']})
            relevant_data['extra_fields'] = cleaned_doc.get('extra_fields', {})
    except Exception as e:
        print(f"⚠️ Warning: failed to clean extra_fields: {str(e)}")

    return relevant_data


def validate_extracted_fields(extracted_data: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
    """
    Validate extracted fields against OCR text to prevent hallucination.
    
    Args:
        extracted_data: The extracted data dictionary
        ocr_text: The raw OCR text
        
    Returns:
        Validated data dictionary with only fields that exist in OCR text
    """
    print("🔍 Starting field validation against OCR text...")
    
    if not ocr_text:
        print("   ⚠️ No OCR text provided for validation")
        return extracted_data
    
    ocr_lower = ocr_text.lower()
    validated_data = {}
    excluded_fields = []
    
    for field_name, field_value in extracted_data.items():
        if field_name in ['document_type', 'extraction_method', 'confidence_score']:
            # Always keep these core fields
            validated_data[field_name] = field_value
            continue
            
        if field_name == 'extra_fields':
            # Validate extra_fields separately - available when needed for all document types
            print("🔍 Validating extra_fields...")
            if isinstance(field_value, dict):
                validated_extra = {}
                for extra_key, extra_value in field_value.items():
                    if isinstance(extra_value, dict) and 'value' in extra_value:
                        value_to_check = str(extra_value['value']).lower()
                        if value_to_check in ocr_lower or any(word in ocr_lower for word in value_to_check.split() if len(word) > 2):
                            validated_extra[extra_key] = extra_value
                            print(f"   ✅ Extra field '{extra_key}' validated: '{extra_value['value']}'")
                        else:
                            print(f"   ❌ Extra field '{extra_key}' not found in OCR text: '{extra_value['value']}'")
                
                if validated_extra:
                    validated_data[field_name] = validated_extra
                    print(f"   📊 Included {len(validated_extra)} validated extra_fields")
                else:
                    print("   ℹ️ No extra_fields passed validation")
            continue
        
        # Handle field validation for FieldWithConfidence objects
        if isinstance(field_value, dict) and 'value' in field_value:
            value_to_check = str(field_value['value']).lower()
            
            # Special handling for dates (check parts of the date)
            if field_name in ['date_of_birth', 'date_of_issue', 'date_of_expiry']:
                # For dates, check if year, month parts exist in OCR
                if '-' in value_to_check:
                    date_parts = value_to_check.split('-')
                    year_found = date_parts[0] in ocr_lower
                    # Be flexible with date validation
                    if year_found or any(part in ocr_lower for part in date_parts if len(part) >= 2):
                        validated_data[field_name] = field_value
                        print(f"   ✅ Date field '{field_name}' validated: '{field_value['value']}'")
                    else:
                        excluded_fields.append(field_name)
                        print(f"   ❌ Date field '{field_name}' not found in OCR text: '{field_value['value']}'")
                else:
                    # Non-standard date format, check directly
                    if value_to_check in ocr_lower or any(word in ocr_lower for word in value_to_check.split() if len(word) > 2):
                        validated_data[field_name] = field_value
                        print(f"   ✅ Date field '{field_name}' validated: '{field_value['value']}'")
                    else:
                        excluded_fields.append(field_name)
                        print(f"   ❌ Date field '{field_name}' not found in OCR text: '{field_value['value']}'")
            else:
                # For non-date fields, check if value exists in OCR text
                # Split the value into words and check if most words exist
                words = value_to_check.split()
                if len(words) == 1:
                    # Single word - check directly
                    if len(value_to_check) > 2 and value_to_check in ocr_lower:
                        validated_data[field_name] = field_value
                        print(f"   ✅ Field '{field_name}' validated: '{field_value['value']}'")
                    else:
                        excluded_fields.append(field_name)
                        print(f"   ❌ Field '{field_name}' not found in OCR text: '{field_value['value']}'")
                else:
                    # Multiple words - check if at least 60% of meaningful words exist
                    meaningful_words = [w for w in words if len(w) > 2]
                    if meaningful_words:
                        found_words = sum(1 for word in meaningful_words if word in ocr_lower)
                        if found_words / len(meaningful_words) >= 0.6:
                            validated_data[field_name] = field_value
                            print(f"   ✅ Field '{field_name}' validated: '{field_value['value']}' ({found_words}/{len(meaningful_words)} words found)")
                        else:
                            excluded_fields.append(field_name)
                            print(f"   ❌ Field '{field_name}' insufficient matches: '{field_value['value']}' ({found_words}/{len(meaningful_words)} words found)")
                    else:
                        # No meaningful words to check
                        validated_data[field_name] = field_value
                        print(f"   ⚠️ Field '{field_name}' contains only short words - keeping: '{field_value['value']}'")
        
        # Handle list fields (like mrz_lines)
        elif isinstance(field_value, list):
            validated_list = []
            for item in field_value:
                if isinstance(item, dict) and 'value' in item:
                    value_to_check = str(item['value']).lower()
                    if value_to_check in ocr_lower or any(word in ocr_lower for word in value_to_check.split() if len(word) > 3):
                        validated_list.append(item)
                        print(f"   ✅ List item in '{field_name}' validated: '{item['value']}'")
                    else:
                        print(f"   ❌ List item in '{field_name}' not found in OCR text: '{item['value']}'")
            
            if validated_list:
                validated_data[field_name] = validated_list
            elif field_value:  # If original list had items but none validated
                excluded_fields.append(field_name)
        
        else:
            # Keep other field types as-is
            validated_data[field_name] = field_value
    
    if excluded_fields:
        print(f"   📊 Validation complete: {len(excluded_fields)} fields excluded: {excluded_fields}")
    else:
        print("   📊 Validation complete: All fields validated successfully")
    
    return validated_data


# Integrated function for document data extraction with OCR and LLM
async def extract_data_with_fallback(
    image_bytes: bytes, 
    ocr_results: List[Dict[str, Any]]
) -> Tuple[List[DocumentData], List[Dict[str, Any]]]:
    """
    Extract document data with intelligent fallback between OCR+LLM and Vision LLM.
    Handles both single and multiple documents intelligently.
    
    FLOW:
    1. Determine if OCR text represents single or multiple documents
    2. For single documents: Process entire text as one document
    3. For multiple documents: Split and process each segment separately
    4. Apply field validation to prevent hallucination
    5. Remove page_number from output
    
    Args:
        image_bytes: Binary content of the image
        ocr_results: Initial OCR results from PaddleOCR
        
    Returns:
        Tuple of (List of DocumentData objects, List of filtered relevant fields dicts)
    """
    
    # Extract raw OCR text
    ocr_texts = [item["text"] for item in ocr_results]
    full_text = "\n".join(ocr_texts)
    
    print(f"🔍 Processing document extraction - OCR text length: {len(full_text)} characters")
    print(f"📝 Raw OCR text preview: {full_text[:200]}...")
    
    # Determine document handling strategy
    text_segments = split_text_by_document(full_text)
    print(f"📄 Document analysis complete: {len(text_segments)} segment(s) detected")
    
    structured_documents = []
    relevant_fields_list = []
    
    # Process each segment
    for i, segment in enumerate(text_segments):
        print(f"\n🔄 Processing document {i+1}/{len(text_segments)}...")
        print(f"📄 Segment preview: {segment[:150]}...")
        
        try:
            # STEP 1: Try OCR+LLM extraction
            print(f"   🔄 Attempting OCR+LLM extraction...")
            ocr_structurer = OCRStructurer()
            
            # Create OCR result for this segment
            segment_ocr_result = [{"text": segment, "confidence": 0.8}]
            ocr_structured_data = await ocr_structurer.structure_ocr_results(segment_ocr_result)
            
            # STEP 2: Validate the extraction quality
            if _is_sufficient_data(ocr_structured_data):
                print(f"   ✅ OCR+LLM extraction successful! Document type: {ocr_structured_data.document_type}")
                
                # Get relevant fields and validate against OCR text
                relevant_fields = get_relevant_fields(ocr_structured_data)
                validated_fields = validate_extracted_fields(relevant_fields, segment)
                
                # Verify fields actually exist in the OCR text
                verification_results = verify_extracted_fields(validated_fields, segment)
                
                # Adjust confidence scores based on verification results
                for field_name, field_data in validated_fields.items():
                    if field_name == 'extra_fields' and isinstance(field_data, dict):
                        extra_verifications = verification_results.get('extra_fields', {})
                        for extra_name, extra_field in field_data.items():
                            if extra_name in extra_verifications:
                                extra_result = extra_verifications[extra_name]
                                if isinstance(extra_field, dict) and 'confidence' in extra_field:
                                    # Reduce confidence for unverified fields
                                    if not extra_result.get('verified', True):
                                        extra_field['confidence'] *= 0.5
                    elif field_name in verification_results:
                        field_result = verification_results[field_name]
                        if isinstance(field_data, dict) and 'confidence' in field_data:
                            # Reduce confidence for unverified fields
                            if not field_result.get('verified', True):
                                field_data['confidence'] *= 0.5
                
                # Apply confidence filter to remove potential hallucinations
                filtered_fields = filter_low_confidence_fields(validated_fields, confidence_threshold=0.65)
                
                # Count verified vs unverified fields
                verified_count = sum(1 for result in verification_results.values() 
                                    if isinstance(result, dict) and result.get('verified', False))
                total_count = len(verification_results)
                print(f"   🔍 Field verification: {verified_count}/{total_count} fields verified in OCR text")
                print(f"   🔍 Applied confidence filter: {len(validated_fields)} → {len(filtered_fields)} fields")
                
                # Remove page_number if present
                filtered_fields.pop('page_number', None)
                
                # Update the DocumentData object with filtered fields
                for field_name in list(ocr_structured_data.model_fields_set):
                    if field_name != 'document_type' and field_name != 'extraction_method':
                        if field_name not in filtered_fields and hasattr(ocr_structured_data, field_name):
                            setattr(ocr_structured_data, field_name, None)
                
                structured_documents.append(ocr_structured_data)
                relevant_fields_list.append(filtered_fields)
                
                print(f"   📊 Document {i+1} processed successfully with {len(validated_fields)} fields")
                
            else:
                print(f"   ⚠️ OCR+LLM output insufficient. Trying Vision LLM fallback...")
                
                # STEP 3: Fallback to Vision LLM
                try:
                    print(f"   🔄 Attempting Vision LLM extraction...")
                    vision_extractor = VisionLLMExtractor()
                    vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
                    
                    print(f"   ✅ Vision LLM extraction successful! Document type: {vision_structured_data.document_type}")
                    
                    # Get relevant fields and validate against OCR text
                    relevant_fields = get_relevant_fields(vision_structured_data)
                    validated_fields = validate_extracted_fields(relevant_fields, segment)
                    
                    # Verify fields actually exist in the OCR text - stricter for Vision LLM
                    verification_results = verify_extracted_fields(validated_fields, segment)
                    
                    # Adjust confidence scores based on verification results
                    for field_name, field_data in validated_fields.items():
                        if field_name == 'extra_fields' and isinstance(field_data, dict):
                            extra_verifications = verification_results.get('extra_fields', {})
                            for extra_name, extra_field in field_data.items():
                                if extra_name in extra_verifications:
                                    extra_result = extra_verifications[extra_name]
                                    if isinstance(extra_field, dict) and 'confidence' in extra_field:
                                        # Reduce confidence for unverified fields more aggressively
                                        if not extra_result.get('verified', True):
                                            extra_field['confidence'] *= 0.4  # More aggressive reduction for Vision LLM
                        elif field_name in verification_results:
                            field_result = verification_results[field_name]
                            if isinstance(field_data, dict) and 'confidence' in field_data:
                                # Reduce confidence for unverified fields
                                if not field_result.get('verified', True):
                                    field_data['confidence'] *= 0.4  # More aggressive reduction for Vision LLM
                    
                    # Apply stricter confidence filter for Vision LLM to prevent hallucinations
                    filtered_fields = filter_low_confidence_fields(validated_fields, confidence_threshold=0.7)
                    
                    # Count verified vs unverified fields
                    verified_count = sum(1 for result in verification_results.values() 
                                        if isinstance(result, dict) and result.get('verified', False))
                    total_count = len(verification_results)
                    print(f"   🔍 Field verification (Vision): {verified_count}/{total_count} fields verified in OCR text")
                    print(f"   🔍 Applied confidence filter (Vision): {len(validated_fields)} → {len(filtered_fields)} fields")
                    
                    # Remove page_number if present
                    filtered_fields.pop('page_number', None)
                    
                    # Update the DocumentData object with filtered fields
                    for field_name in list(vision_structured_data.model_fields_set):
                        if field_name != 'document_type' and field_name != 'extraction_method':
                            if field_name not in filtered_fields and hasattr(vision_structured_data, field_name):
                                setattr(vision_structured_data, field_name, None)
                    
                    structured_documents.append(vision_structured_data)
                    relevant_fields_list.append(filtered_fields)
                    
                    print(f"   📊 Document {i+1} processed successfully (Vision) with {len(validated_fields)} fields")
                    
                except Exception as e:
                    print(f"   ❌ Vision LLM failed: {str(e)}")
                    print(f"   ⚠️ Skipping document {i+1} - no valid extraction method succeeded")
                    
        except Exception as e:
            print(f"   ❌ OCR+LLM extraction failed: {str(e)}")
            
            # Final fallback to Vision LLM
            try:
                print(f"   🔄 Final fallback to Vision LLM...")
                vision_extractor = VisionLLMExtractor()
                vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
                
                print(f"   ✅ Vision LLM extraction successful! Document type: {vision_structured_data.document_type}")
                
                # Get relevant fields and validate against OCR text
                relevant_fields = get_relevant_fields(vision_structured_data)
                validated_fields = validate_extracted_fields(relevant_fields, segment)
                
                # Remove page_number if present
                validated_fields.pop('page_number', None)
                
                structured_documents.append(vision_structured_data)
                relevant_fields_list.append(validated_fields)
                
                print(f"   📊 Document {i+1} processed successfully (Final Vision) with {len(validated_fields)} fields")
                
            except Exception as e2:
                print(f"   ❌ All extraction methods failed for document {i+1}: {str(e2)}")
                print(f"   ⚠️ Skipping document {i+1}")
    
    # Handle case where no documents were successfully extracted
    if not structured_documents:
        print("⚠️ No documents successfully extracted. Attempting full-text extraction as last resort...")
        try:
            ocr_structurer = OCRStructurer()
            ocr_structured_data = await ocr_structurer.structure_ocr_results(ocr_results)
            
            if _is_sufficient_data(ocr_structured_data):
                relevant_fields = get_relevant_fields(ocr_structured_data)
                validated_fields = validate_extracted_fields(relevant_fields, full_text)
                validated_fields.pop('page_number', None)
                
                structured_documents.append(ocr_structured_data)
                relevant_fields_list.append(validated_fields)
                print("✅ Last resort extraction successful")
            else:
                # Final Vision LLM attempt
                vision_extractor = VisionLLMExtractor()
                vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
                
                relevant_fields = get_relevant_fields(vision_structured_data)
                validated_fields = validate_extracted_fields(relevant_fields, full_text)
                validated_fields.pop('page_number', None)
                
                structured_documents.append(vision_structured_data)
                relevant_fields_list.append(validated_fields)
                print("✅ Last resort Vision extraction successful")
                
        except Exception as e:
            raise Exception(f"❌ All extraction methods failed completely: {str(e)}")
    
    # Final summary
    total_documents = len(structured_documents)
    total_fields = sum(len(fields) for fields in relevant_fields_list)
    
    print(f"\n✅ Extraction complete: {total_documents} document(s) processed with {total_fields} total fields")
    
    for i, (doc, fields) in enumerate(zip(structured_documents, relevant_fields_list)):
        doc_type = "Unknown"
        if hasattr(doc.document_type, 'value'):
            doc_type = doc.document_type.value
        print(f"   📄 Document {i+1}: {doc_type} ({len(fields)} fields)")
    
    return structured_documents, relevant_fields_list
# Convenience function for simple extraction (backward compatibility)
async def extract_document_data(
    image_bytes: bytes, 
    ocr_results: List[Dict[str, Any]]
) -> DocumentData:
    """
    Simple extraction function that returns only the first DocumentData object
    
    Args:
        image_bytes: Binary content of the image
        ocr_results: Initial OCR results from PaddleOCR
        
    Returns:
        DocumentData object with structured information (first document if multiple found)
    """
    structured_data_list, _ = await extract_data_with_fallback(image_bytes, ocr_results)
    # Return the first document for backward compatibility
    return structured_data_list[0] if structured_data_list else None


def _is_sufficient_data(document_data: DocumentData) -> bool:
    """
    Assess if the structured document data contains sufficient information

    Args:
        document_data: Structured document data from OCR+LLM

    Returns:
        bool: True if data is sufficient, False if fallback needed
    """
    try:
        # Log the type and content of document_type for debugging
        print(f"DEBUG: document_type content: {document_data.document_type}")

        # Core required fields that most documents should have
        core_fields = [
            document_data.document_type.value if hasattr(document_data.document_type, 'value') and document_data.document_type else None,
            document_data.document_number.value if hasattr(document_data.document_number, 'value') and document_data.document_number else None,
            (document_data.surname.value if hasattr(document_data.surname, 'value') and document_data.surname else None) or
            (document_data.given_names.value if hasattr(document_data.given_names, 'value') and document_data.given_names else None)
        ]

        # Count non-empty core fields
        valid_core_fields = sum(1 for field in core_fields if field and str(field).strip())

        # Additional fields that add confidence
        additional_fields = [
            document_data.date_of_birth.value if hasattr(document_data.date_of_birth, 'value') else None,
            document_data.date_of_issue.value if hasattr(document_data.date_of_issue, 'value') else None,
            document_data.date_of_expiry.value if hasattr(document_data.date_of_expiry, 'value') else None,
            document_data.nationality.value if hasattr(document_data.nationality, 'value') else None,
            document_data.country.value if hasattr(document_data.country, 'value') else None,
            document_data.sex.value if hasattr(document_data.sex, 'value') else None
        ]

        valid_additional_fields = sum(1 for field in additional_fields if field and field.strip())

        # Require at least 1 core field and 1 additional field (more lenient for non-identity documents)
        # Or just document_type if it's a non-standard document type
        if valid_core_fields >= 1 and valid_additional_fields >= 1:
            return True
        elif document_data.document_type and hasattr(document_data.document_type, 'value') and document_data.document_type.value:
            # If we have document type and some extra fields, that might be sufficient for contracts/agreements
            if hasattr(document_data, 'extra_fields') and document_data.extra_fields:
                return True
        
        return False

    except AttributeError as e:
        print(f"❌ AttributeError in _is_sufficient_data: {str(e)}")
        return False


def validate_image_bytes(image_bytes: bytes):
    """
    Validate the input image bytes before sending to Vision LLM.

    Args:
        image_bytes: Binary content of the image

    Raises:
        ValueError: If the image bytes are invalid
    """
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("Image bytes are empty or invalid.")

    print("DEBUG: Image bytes validated successfully.")