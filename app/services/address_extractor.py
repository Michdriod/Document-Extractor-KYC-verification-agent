"""Address extraction helper functions to pull addresses, phone, and email from OCR text."""

import json
from typing import Dict, Any, List, Optional, Union
from app.models.document_data import DocumentData, FieldWithConfidence

def extract_addresses_from_text(ocr_text: str) -> Dict[str, FieldWithConfidence]:
    """
    Extract address information from OCR text as a post-processing step.
    This function looks for address patterns in the OCR text and extracts them.
    
    Args:
        ocr_text: The raw OCR text
        
    Returns:
        Dictionary with address fields and their values
    """
    import re
    
    # Initialize result
    address_fields = {}
    
    # Define address patterns (will match many address formats)
    address_patterns = [
        # Street address with number
        r"(?:address|residence|location)[\s:]+([\w\s\.,#\-/\\]+?)(?:\s*(?:city|state|zip|postal|country|phone|\n|$))",
        # Street address without explicit label but with common format
        r"(\d+\s+[A-Za-z\s\.,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)(?:[,\s]+(?:[A-Za-z\s]+))?)",
        # PO Box format
        r"(P\.?O\.?\s*Box\s+\d+[,\s]+[A-Za-z\s]+(?:[,\s]+\w+)?)",
        # Full address with city, state, zip
        r"([A-Za-z0-9\s\.,#\-/\\]+,[A-Za-z\s]+,\s*[A-Za-z]{2}\s*\d{5}(?:-\d{4})?)",
    ]
    
    # Look for primary address
    primary_address = None
    for pattern in address_patterns:
        matches = re.findall(pattern, ocr_text, re.IGNORECASE)
        if matches:
            # Use the longest match as it's likely more complete
            primary_address = max(matches, key=len).strip()
            if len(primary_address) > 8:  # Minimum reasonable address length
                address_fields["address"] = FieldWithConfidence(
                    value=primary_address, 
                    confidence=0.85
                )
                break
    
    # Look for secondary address if primary was found
    if primary_address:
        for pattern in address_patterns:
            # Find all matches
            all_matches = re.findall(pattern, ocr_text, re.IGNORECASE)
            # Filter out the primary address and short matches
            secondary_candidates = [
                match.strip() for match in all_matches 
                if match.strip() != primary_address and len(match.strip()) > 8
            ]
            
            if secondary_candidates:
                # Use the longest secondary address
                secondary_address = max(secondary_candidates, key=len)
                address_fields["secondary_address"] = FieldWithConfidence(
                    value=secondary_address, 
                    confidence=0.75
                )
                break
    
    # Try to extract state/province information
    state_pattern = r"(?:state|province|region)[\s:]+([\w\s\.]{2,30}?)(?:\s*(?:zip|postal|country|phone|\n|$))"
    state_matches = re.findall(state_pattern, ocr_text, re.IGNORECASE)
    if state_matches:
        address_fields["state_province"] = FieldWithConfidence(
            value=state_matches[0].strip(), 
            confidence=0.8
        )
    
    # Try to extract jurisdiction information
    jurisdiction_pattern = r"(?:jurisdiction|authority|governed\s+by)[\s:]+([\w\s\.]{2,50}?)(?:\s*(?:zip|postal|country|phone|\n|$))"
    jurisdiction_matches = re.findall(jurisdiction_pattern, ocr_text, re.IGNORECASE)
    if jurisdiction_matches:
        address_fields["jurisdiction"] = FieldWithConfidence(
            value=jurisdiction_matches[0].strip(), 
            confidence=0.8
        )
    
    # Try to extract phone number
    phone_pattern = r"(?:phone|tel|telephone|mobile|contact)[\s:]+([0-9\s\(\)\-\.\+]{7,20})"
    phone_matches = re.findall(phone_pattern, ocr_text, re.IGNORECASE)
    if phone_matches:
        address_fields["phone_number"] = FieldWithConfidence(
            value=phone_matches[0].strip(), 
            confidence=0.9
        )
    
    # Try to extract email
    email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    email_matches = re.findall(email_pattern, ocr_text)
    if email_matches:
        address_fields["email"] = FieldWithConfidence(
            value=email_matches[0].strip(), 
            confidence=0.95
        )
    
    return address_fields

def enhance_extracted_data(document_data: DocumentData, ocr_text: str) -> DocumentData:
    """
    Post-process extracted data to enhance address information
    
    Args:
        document_data: The original DocumentData object
        ocr_text: The raw OCR text
        
    Returns:
        Enhanced DocumentData object with improved address information
    """
    # Extract addresses from OCR text
    address_fields = extract_addresses_from_text(ocr_text)
    
    # Update the document data with extracted addresses if not already present
    for field_name, field_value in address_fields.items():
        current_field = getattr(document_data, field_name, None)
        
        # If the field doesn't exist or has no value, add the extracted one
        if not current_field or not getattr(current_field, 'value', None):
            setattr(document_data, field_name, field_value)
    
    return document_data
