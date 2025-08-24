import re
from typing import Dict, Any, Optional, List
from app.models.document_data import FieldWithConfidence

def extract_nonstandard_fields(ocr_text: str) -> Dict[str, FieldWithConfidence]:
    """
    Extract non-standard fields from OCR text based on common patterns.
    This is a fallback method to ensure we capture fields not defined in the schema.
    
    Args:
        ocr_text: Raw OCR text
        
    Returns:
        Dictionary of field names to FieldWithConfidence objects
    """
    # Initialize results
    extracted_fields = {}
    
    # Define patterns for key-value pairs
    key_value_patterns = [
        # Common pattern: Key: Value
        r"([A-Za-z][A-Za-z\s\-\_]+)[\:\s]+([^\n:]{2,100}?)(?:\n|$)",
        # Key - Value pattern
        r"([A-Za-z][A-Za-z\s\-\_]+)[\s\-]+([^\n:]{2,100}?)(?:\n|$)",
        # Labeled data with parentheses (like "the Grantor")
        r'(?:the\s+")([^"]+)(?:")[\s\(].*?[\)][\s:]+([^\n:]{2,100}?)(?:\n|$)',
        # Form field pattern with label
        r"([A-Za-z][A-Za-z\s\-\_]+):\s*([^\n:]{2,100}?)(?:\n|$)",
        # Table-like format: Key............Value
        r"([A-Za-z][A-Za-z\s\-\_]+)[\.]{3,}([^\n\.]{2,100}?)(?:\n|$)",
        # Entity detection pattern (like "Grantor: John Smith" or "Grantor - John Smith")
        r"(Grantor|Grantee|Borrower|Lender|Witness|Guarantor|Buyer|Seller|Owner|Tenant|Landlord)[\s\:\-]+([^\n:]{2,100}?)(?:\n|$)",
        # Person with role pattern
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)[\s,]+(?:the|as)[\s]+([A-Za-z\s\-\_]+)(?:\n|$)",
        # Amount pattern
        r"(Amount|Sum|Total|Payment|Fee|Price|Cost|Value)[\s\:\-]+[\$\€\£]?([0-9,.]+)(?:\s?[A-Za-z]+)?(?:\n|$)",
    ]
    
    # Define specific patterns to extract semantic information
    semantic_patterns = [
        # Person named as a specific role
        (r"\[([A-Za-z\s]+)\],?\s*\(?(?:the|as)\s*[\"']?([A-Za-z\s]+)[\"']?\)?", "{1}_{0}"),
        # Entity with specific role
        (r"([A-Za-z\s]+)\s+(?:is|as)\s+(?:the|a|an)\s+([A-Za-z\s]+)", "{1}_{0}"),
        # Property or asset reference
        (r"(?:property|land|asset|premises|building)\s+(?:at|located\s+at|known\s+as)\s+([^,\n]{5,100})", "property_location"),
        # Restriction or condition
        (r"(?:No|Not|Prohibited)\s+([A-Za-z\s\-\_]+)", "restriction_{0}"),
        # Amount fields
        (r"(?:amount|sum|fee|payment)\s+of\s+[\$\€\£]?([0-9,.]+)", "payment_amount"),
        # Date fields
        (r"(?:dated|effective|expires|terminated)\s+(?:on|as\s+of)?\s+([A-Za-z0-9\s,]+\d{4})", "relevant_date"),
        # Document identifiers
        (r"(?:Document|Agreement|Contract|Form|Certificate)\s+(?:No\.|Number|ID|#)\s*:?\s*([A-Za-z0-9\-\_]+)", "document_identifier"),
    ]
    
    # Find all potential key-value pairs
    potential_fields = []
    
    # Extract from standard key-value patterns
    for pattern in key_value_patterns:
        matches = re.findall(pattern, ocr_text)
        for match in matches:
            if len(match) >= 2:
                key = match[0].strip().lower().replace(' ', '_')
                value = match[1].strip()
                potential_fields.append((key, value, 0.7))  # Standard pattern confidence
    
    # Extract from semantic patterns with special field naming
    for pattern, field_format in semantic_patterns:
        matches = re.findall(pattern, ocr_text)
        for match in matches:
            if isinstance(match, tuple) and len(match) >= 2:
                # Format the field name using the template
                field_name = field_format.format(*[item.strip().lower().replace(' ', '_') for item in match])
                value = match[0].strip()  # Usually the first capture group has the main value
                potential_fields.append((field_name, value, 0.8))  # Higher confidence for semantic patterns
            elif isinstance(match, str):
                # Single capture group
                field_name = field_format.replace("{0}", match.strip().lower().replace(' ', '_'))
                potential_fields.append((field_name, match, 0.8))
    
    # Filter invalid or irrelevant fields
    valid_fields = []
    for key, value, confidence in potential_fields:
        # Skip very short or empty values
        if not value or len(value) < 2:
            continue
        
        # Skip common stop words as keys
        stop_words = ['the', 'and', 'or', 'but', 'for', 'with', 'this', 'that', 
                     'in', 'on', 'at', 'by', 'to', 'from', 'of', 'a', 'an', 
                     'shall', 'will', 'may', 'can', 'all', 'any', 'such', 'been', 'have']
        if key in stop_words or any(key.startswith(word + '_') for word in stop_words):
            continue
        
        # Skip values that are likely not actual data
        if value.lower() in ['please', 'yes', 'no', 'n/a', 'na', 'none', 'not applicable', 
                           'see above', 'as above', 'as stated', 'as mentioned']:
            continue
        
        # Skip values that are likely sentence fragments (contains multiple words and ending punctuation)
        if len(value.split()) > 10 and re.search(r'[.;!?]$', value):
            continue
        
        # Skip very long keys (likely not actual fields)
        if len(key) > 30:
            continue
        
        # Skip keys that don't represent actual data fields
        if re.match(r'^(page|section|paragraph|item|clause|article|chapter)_\d+$', key):
            continue
        
        # Make key suitable for field name
        clean_key = re.sub(r'[^\w\_]', '', key).lower()
        if not clean_key:
            continue
        
        valid_fields.append((clean_key, value, confidence))
    
    # Check for meaningful field names
    meaningful_fields = []
    for key, value, confidence in valid_fields:
        # Check if key is meaningful (contains informative terms)
        meaningful_terms = ['name', 'date', 'number', 'id', 'address', 'code', 'amount', 'fee',
                           'grantor', 'grantee', 'owner', 'tenant', 'buyer', 'seller',
                           'restriction', 'condition', 'limitation', 'requirement',
                           'property', 'land', 'asset', 'payment', 'term', 'expiry']
        
        # Keep fields with meaningful names or high confidence semantic matches
        if any(term in key for term in meaningful_terms) or confidence >= 0.8:
            meaningful_fields.append((key, value, confidence))
    
    # Process the meaningful fields to create the final output
    for key, value, confidence in meaningful_fields:
        # Avoid duplicate keys by appending a number if needed
        base_key = key
        counter = 1
        while key in extracted_fields:
            key = f"{base_key}_{counter}"
            counter += 1
        
        # Create field with confidence
        extracted_fields[key] = FieldWithConfidence(value=value, confidence=confidence)
    
    print(f"🔍 Extracted {len(extracted_fields)} meaningful non-standard fields from OCR text")
    return extracted_fields

def normalize_field_name(field_name: str) -> str:
    """
    Normalize field names to a consistent format with semantic meaning.
    
    Args:
        field_name: Original field name
        
    Returns:
        Normalized field name with improved semantic clarity
    """
    # Handle empty keys
    if not field_name:
        return "unknown_field"
    
    # Convert to lowercase
    name = field_name.lower()
    
    # Replace spaces and special characters with underscores
    name = re.sub(r'[^\w]+', '_', name)
    
    # Remove leading/trailing underscores
    name = name.strip('_')
    
    # Ensure no double underscores
    name = re.sub(r'_+', '_', name)
    
    # Comprehensive dictionary of field name replacements
    replacements = {
        # Personal identification
        'dob': 'date_of_birth',
        'birthdate': 'date_of_birth',
        'birth_date': 'date_of_birth',
        'date_birth': 'date_of_birth',
        'ssn': 'social_security_number',
        'ss_num': 'social_security_number',
        'social_sec': 'social_security_number',
        'social_sec_num': 'social_security_number',
        'tin': 'tax_identification_number',
        'tax_id': 'tax_identification_number',
        'passport': 'passport_number',
        'passport_no': 'passport_number',
        'passport_num': 'passport_number',
        'driver_license': 'drivers_license_number',
        'dl_number': 'drivers_license_number',
        'dl_num': 'drivers_license_number',
        'drivers_lic': 'drivers_license_number',
        'id_num': 'identification_number',
        'id_number': 'identification_number',
        'id_no': 'identification_number',
        'ident_num': 'identification_number',
        
        # Names
        'fname': 'first_name',
        'firstname': 'first_name',
        'first': 'first_name',
        'name_first': 'first_name',
        'given_name': 'first_name',
        'lname': 'last_name',
        'lastname': 'last_name',
        'last': 'last_name', 
        'name_last': 'last_name',
        'surname': 'last_name',
        'family_name': 'last_name',
        'mname': 'middle_name',
        'middle': 'middle_name',
        'middlename': 'middle_name',
        'name_middle': 'middle_name',
        'fullname': 'full_name',
        'full': 'full_name',
        'name_full': 'full_name',
        'complete_name': 'full_name',
        
        # Contact information
        'addr': 'address',
        'address_line_1': 'address_line1',
        'address_line_2': 'address_line2',
        'addr_1': 'address_line1',
        'addr_2': 'address_line2',
        'street_addr': 'street_address',
        'street_address': 'street_address',
        'city_name': 'city',
        'state_name': 'state',
        'state_province': 'state',
        'province': 'state',
        'zip': 'zip_code',
        'zipcode': 'zip_code',
        'postal': 'postal_code',
        'postal_code': 'postal_code',
        'country_name': 'country',
        'phone': 'phone_number',
        'phone_num': 'phone_number',
        'telephone': 'phone_number',
        'tel': 'phone_number',
        'tel_num': 'phone_number',
        'mobile': 'mobile_number',
        'cell': 'mobile_number',
        'cellphone': 'mobile_number',
        'fax': 'fax_number',
        'fax_num': 'fax_number',
        'email_address': 'email',
        'mail': 'email',
        'e_mail': 'email',
        
        # Dates
        'exp': 'expiration',
        'exp_date': 'expiration_date',
        'expiry': 'expiration_date',
        'expiry_date': 'expiration_date',
        'expiration': 'expiration_date',
        'issue': 'issue_date',
        'issue_dt': 'issue_date',
        'issued': 'issue_date',
        'issued_date': 'issue_date',
        'date_issued': 'issue_date',
        'effective': 'effective_date',
        'effective_dt': 'effective_date',
        'date_effective': 'effective_date',
        'start': 'start_date',
        'start_dt': 'start_date',
        'date_start': 'start_date',
        'end': 'end_date',
        'end_dt': 'end_date',
        'date_end': 'end_date',
        'term': 'term_date',
        
        # Financial
        'amt': 'amount',
        'total_amt': 'total_amount',
        'sum': 'total_amount',
        'tot': 'total',
        'fee': 'fee_amount',
        'charge': 'charge_amount',
        'price': 'price_amount',
        'cost': 'cost_amount',
        'value': 'value_amount',
        'rate': 'rate_value',
        'percentage': 'percentage_value',
        'pct': 'percentage_value',
        'balance': 'balance_amount',
        'payment': 'payment_amount',
        'deposit': 'deposit_amount',
        'currency': 'currency_type',
        
        # Document
        'desc': 'description',
        'descr': 'description',
        'summary': 'description',
        'ref': 'reference',
        'ref_num': 'reference_number',
        'reference_num': 'reference_number',
        'doc': 'document',
        'doc_num': 'document_number',
        'document_num': 'document_number',
        'type': 'document_type',
        'doc_type': 'document_type',
        'document_type': 'document_type',
        'status': 'status_value',
        'state': 'status_value',
        'title': 'document_title',
        
        # Company/Organization
        'org': 'organization',
        'org_name': 'organization_name',
        'company': 'organization_name',
        'company_name': 'organization_name',
        'business': 'business_name',
        'business_name': 'business_name',
        'corp': 'corporation_name',
        'corporation': 'corporation_name'
    }
    
    # Check for exact matches first
    if name in replacements:
        return replacements[name]
    
    # Check for common prefixes/suffixes
    for old, new in replacements.items():
        # Replace standalone terms (bounded by underscores or start/end of string)
        pattern = r'(^|_)' + re.escape(old) + r'($|_)'
        if re.search(pattern, name):
            # Replace while preserving context
            name = re.sub(pattern, r'\1' + new + r'\2', name)
            # Remove doubled underscores that might have been created
            name = re.sub(r'_{2,}', '_', name)
            # Remove leading/trailing underscores
            name = name.strip('_')
            break
    
    # Fix redundant terms
    redundant_patterns = [
        (r'number_num', 'number'),
        (r'date_dt', 'date'),
        (r'amount_amt', 'amount'),
        (r'name_of_name', 'name')
    ]
    
    for pattern, replacement in redundant_patterns:
        name = re.sub(pattern, replacement, name)
    
    # Check for common prefixes that should be moved to suffixes
    prefixes = ['the_', 'a_', 'an_', 'this_', 'that_']
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):] + '_' + prefix.rstrip('_')
    
    # Ensure the field name starts with a context if a well-known field type is detected
    generic_names = ['name', 'date', 'number', 'id', 'amount', 'address', 'code']
    if name in generic_names:
        name = 'document_' + name
    
    return name

def is_meaningful_field(key: str, value: Any) -> bool:
    """
    Check if a field is semantically meaningful across any document type.
    
    Args:
        key: Field name
        value: Field value
        
    Returns:
        True if field is meaningful, False otherwise
    """
    if not key or not value:
        return False
    
    # Convert key to lowercase for case-insensitive checking
    key_lower = key.lower()
    
    # 1. Check for meaningful field name patterns (comprehensive list)
    meaningful_patterns = [
        # People and roles
        r'.*(name|person|individual|holder|owner|party|signatory|grantor|grantee|borrower|lender|buyer|seller|tenant|landlord|witness|guarantor|trustee|beneficiary|applicant|employee|employer).*',
        
        # Identification
        r'.*(id|identifier|number|code|reference|passport|license|registration|account|certificate|document).*',
        
        # Locations
        r'.*(address|location|place|property|premises|building|street|road|avenue|city|state|province|country|jurisdiction|territory).*',
        
        # Dates and time
        r'.*(date|time|period|term|duration|expiry|expiration|deadline|schedule|calendar|anniversary|renewal|extension).*',
        
        # Financial
        r'.*(amount|sum|total|payment|fee|price|cost|value|rate|percentage|interest|principal|balance|deposit|currency|money|tax).*',
        
        # Legal and status
        r'.*(status|condition|state|requirement|limitation|restriction|prohibition|permission|right|obligation|duty|clause|provision|term|rule).*',
        
        # Document attributes
        r'.*(type|category|class|classification|grade|level|tier|rank|status|title|version|edition).*',
        
        # Specific data types
        r'.*(height|weight|age|gender|sex|color|size|dimension|measurement|quantity).*',
        
        # Contact information
        r'.*(phone|email|contact|website|url|fax|mobile|telephone).*',
        
        # Relationship terms
        r'.*(relation|relationship|connection|association|affiliation|membership|partnership).*'
    ]
    
    for pattern in meaningful_patterns:
        if re.search(pattern, key_lower):
            return True
    
    # 2. Check for well-structured field names (contains underscore separating context and content type)
    if '_' in key_lower and len(key_lower) > 5:
        parts = key_lower.split('_')
        if len(parts) >= 2 and all(len(part) >= 2 for part in parts):
            return True
    
    # 3. Check value content for meaningful patterns
    value_str = ""
    confidence = 0.0
    
    # Extract the actual value and confidence
    if isinstance(value, dict) and 'value' in value:
        value_str = str(value['value']) if value['value'] is not None else ""
        confidence = value.get('confidence', 0.0)
    elif isinstance(value, str):
        value_str = value
    else:
        value_str = str(value)
    
    # Skip empty values
    if not value_str or value_str.strip() == "":
        return False
    
    # Higher confidence fields are more likely to be meaningful
    if confidence > 0.8:
        return True
    
    # Check for specific value patterns that indicate meaningful data
    
    # Date patterns (various formats)
    if re.search(r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b', value_str):
        return True
    
    # Currency/amount patterns
    if re.search(r'\b[\$\€\£]\s*\d+(?:[.,]\d+)*\b|\b\d+(?:[.,]\d+)*\s*(?:USD|EUR|GBP|dollars|euros|pounds)\b', value_str):
        return True
    
    # Identifier patterns (numbers with special formatting)
    if re.search(r'\b[A-Z0-9]{5,}\b|\b\d{3}[\-\s]\d{2}[\-\s]\d{4}\b|\b[A-Z]\d{6,}\b', value_str):
        return True
    
    # Name patterns (proper names with capitalization)
    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', value_str):
        return True
    
    # Address patterns
    if re.search(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Place|Pl)\b', value_str, re.IGNORECASE):
        return True
    
    # Filter out values that are clearly not data fields
    
    # Exclude very long values (likely paragraphs or sentences)
    if len(value_str) > 100:
        return False
    
    # Exclude values that look like sentence fragments
    if value_str.endswith(('.', ';', '!', '?')) and len(value_str.split()) > 5:
        return False
    
    # Exclude non-data values
    non_data_values = ['yes', 'no', 'n/a', 'na', 'none', 'not applicable', 
                       'see above', 'as above', 'as stated', 'as mentioned',
                       'please', 'thank you', 'signature', 'signed']
    if value_str.lower() in non_data_values:
        return False
    
    # Short or generic keys are probably not meaningful
    generic_keys = ['the', 'and', 'for', 'with', 'this', 'that', 'data', 'info', 
                    'item', 'text', 'value', 'other', 'content', 'field', 
                    'section', 'paragraph', 'page', 'note']
    if key_lower in generic_keys or len(key_lower) < 3:
        return False
    
    # Default to False for anything else that doesn't match specific patterns
    return False

def enrich_document_data(data_dict: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
    """
    Enrich a document data dictionary with non-standard fields from OCR text
    
    Args:
        data_dict: Current document data dictionary
        ocr_text: Raw OCR text
        
    Returns:
        Enriched dictionary with additional fields
    """
    # Extract non-standard fields
    nonstandard_fields = extract_nonstandard_fields(ocr_text)
    
    # Skip if no fields found
    if not nonstandard_fields:
        return data_dict
    
    # Initialize extra_fields if needed
    if 'extra_fields' not in data_dict or data_dict['extra_fields'] is None:
        data_dict['extra_fields'] = {}
        
    # First clean up any existing extra_fields
    if 'extra_fields' in data_dict and data_dict['extra_fields']:
        # Keep only meaningful fields
        meaningful_fields = {}
        for key, value in data_dict['extra_fields'].items():
            if is_meaningful_field(key, value):
                # Normalize the field name
                normalized_key = normalize_field_name(key)
                meaningful_fields[normalized_key] = value
                
        # Replace with meaningful fields only
        if len(meaningful_fields) < len(data_dict['extra_fields']):
            removed = len(data_dict['extra_fields']) - len(meaningful_fields)
            print(f"🧹 Removed {removed} non-meaningful fields from extra_fields")
            data_dict['extra_fields'] = meaningful_fields
    
    # Get standard field names to avoid duplication
    # Consider both direct field names and keys from field objects
    standard_fields = set()
    for key, value in data_dict.items():
        if key != 'extra_fields':
            standard_fields.add(key.lower())
            # If it's a dictionary with 'value', also add the key
            if isinstance(value, dict) and 'value' in value:
                field_value = value['value']
                if isinstance(field_value, str):
                    standard_fields.add(field_value.lower())
    
    # Add non-standard fields to extra_fields
    added_fields = 0
    for key, value in nonstandard_fields.items():
        # Skip if not meaningful
        if not is_meaningful_field(key, value):
            continue
            
        # Normalize the field name
        normalized_key = normalize_field_name(key)
            
        # Skip if this key or a similar key exists in standard fields
        if normalized_key.lower() in standard_fields:
            continue
            
        # Skip if already in extra_fields
        if normalized_key in data_dict['extra_fields']:
            continue
            
        # Add the new field
        data_dict['extra_fields'][normalized_key] = value.model_dump()
        added_fields += 1
    
    if added_fields > 0:
        print(f"✅ Added {added_fields} meaningful non-standard fields to extra_fields")
    
    return data_dict
