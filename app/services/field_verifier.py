import re
from typing import Dict, Any, List

def verify_field_exists_in_text(field_name: str, field_value: str, text: str) -> bool:
    """
    Verify that a field value actually appears in the source text to prevent hallucinations.
    
    Args:
        field_name: Name of the field
        field_value: Value of the field to verify
        text: Source OCR text
        
    Returns:
        True if the value is found in the text, False otherwise
    """
    # Skip verification for empty or None values
    if not field_value or not isinstance(field_value, str):
        return False
    
    # Clean up the field value and text for comparison
    # Remove whitespace variations and normalize case
    clean_value = re.sub(r'\s+', ' ', field_value.strip().lower())
    clean_text = re.sub(r'\s+', ' ', text.strip().lower())
    
    # Simple case: direct match
    if clean_value in clean_text:
        return True
    
    # Try without spaces (for cases where OCR might miss spaces)
    no_space_value = re.sub(r'\s', '', clean_value)
    no_space_text = re.sub(r'\s', '', clean_text)
    if no_space_value in no_space_text:
        return True
    
    # Special handling for date formats
    if any(term in field_name.lower() for term in ['date', 'expiry', 'issue', 'birth']):
        # Extract potential date components from the value
        date_parts = re.findall(r'\d+', clean_value)
        if date_parts and all(part in clean_text for part in date_parts):
            return True
    
    # Special handling for complex fields like names
    if any(term in field_name.lower() for term in ['name', 'person']):
        # Split into parts and check if each major part is in the text
        name_parts = clean_value.split()
        if name_parts and len(name_parts) > 1:
            # Check for names with at least 2 characters
            significant_parts = [part for part in name_parts if len(part) >= 2]
            if significant_parts and all(part in clean_text for part in significant_parts):
                return True
    
    # For numbers and IDs
    if any(term in field_name.lower() for term in ['number', 'id', 'code']):
        # Extract number sequences and check if they appear in the text
        num_sequences = re.findall(r'\d{2,}', clean_value)
        if num_sequences and all(seq in clean_text for seq in num_sequences):
            return True
    
    return False

def verify_extracted_fields(fields: Dict[str, Any], text: str) -> Dict[str, Dict[str, float]]:
    """
    Verify all extracted fields against the source text and add verification scores.
    
    Args:
        fields: Dictionary of field names to field values
        text: Source OCR text
        
    Returns:
        Dictionary of field names to verification information
    """
    verification_results = {}
    
    for field_name, field_data in fields.items():
        # Skip special fields
        if field_name == 'document_type' or field_name == 'extraction_method':
            verification_results[field_name] = {'verified': True, 'score': 1.0}
            continue
        
        # Handle FieldWithConfidence objects
        if isinstance(field_data, dict) and 'value' in field_data:
            field_value = field_data['value']
            confidence = field_data.get('confidence', 0.0)
            
            # Skip None or empty values
            if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                verification_results[field_name] = {'verified': False, 'score': 0.0}
                continue
            
            # Convert to string if needed
            if not isinstance(field_value, str):
                field_value = str(field_value)
            
            # Verify the field exists in text
            verified = verify_field_exists_in_text(field_name, field_value, text)
            
            # Calculate verification score
            # Use original confidence but reduce it if verification fails
            verification_score = confidence if verified else confidence * 0.5
            
            verification_results[field_name] = {
                'verified': verified,
                'score': verification_score
            }
        
        # Handle extra_fields dictionary
        elif field_name == 'extra_fields' and isinstance(field_data, dict):
            extra_verification = {}
            for extra_name, extra_field in field_data.items():
                if isinstance(extra_field, dict) and 'value' in extra_field:
                    extra_value = extra_field['value']
                    extra_confidence = extra_field.get('confidence', 0.0)
                    
                    # Skip None or empty values
                    if extra_value is None or (isinstance(extra_value, str) and not extra_value.strip()):
                        extra_verification[extra_name] = {'verified': False, 'score': 0.0}
                        continue
                    
                    # Convert to string if needed
                    if not isinstance(extra_value, str):
                        extra_value = str(extra_value)
                    
                    # Verify the extra field exists in text
                    verified = verify_field_exists_in_text(extra_name, extra_value, text)
                    
                    # Calculate verification score
                    verification_score = extra_confidence if verified else extra_confidence * 0.5
                    
                    extra_verification[extra_name] = {
                        'verified': verified,
                        'score': verification_score
                    }
            
            verification_results['extra_fields'] = extra_verification
    
    return verification_results
