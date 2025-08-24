"""
Field categorization service.
Provides functionality to group and categorize extracted fields based on their semantic meaning.
"""

import re
from typing import Dict, Any, List, Tuple
from app.models.document_data import FieldWithConfidence

class FieldCategory:
    """Enum-like class for field categories"""
    PERSONAL = "personal_information"
    IDENTIFICATION = "identification_documents"
    CONTACT = "contact_details"
    ADDRESS = "address_information"
    FINANCIAL = "financial_details"
    DATES = "important_dates"
    DOCUMENT = "document_information"
    PROPERTY = "property_details"
    PARTIES = "involved_parties"
    LEGAL = "legal_terms"
    OTHER = "other_information"

def categorize_fields(fields: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Organize extracted fields into semantic categories.
    
    Args:
        fields: Dictionary of field name to field value
        
    Returns:
        Dictionary of category names to dictionaries of categorized fields
    """
    categorized = {
        FieldCategory.PERSONAL: {},
        FieldCategory.IDENTIFICATION: {},
        FieldCategory.CONTACT: {},
        FieldCategory.ADDRESS: {},
        FieldCategory.FINANCIAL: {},
        FieldCategory.DATES: {},
        FieldCategory.DOCUMENT: {},
        FieldCategory.PROPERTY: {},
        FieldCategory.PARTIES: {},
        FieldCategory.LEGAL: {},
        FieldCategory.OTHER: {},
    }
    
    for field_name, field_value in fields.items():
        category = determine_field_category(field_name, field_value)
        categorized[category][field_name] = field_value
    
    # Remove empty categories
    return {k: v for k, v in categorized.items() if v}

def determine_field_category(field_name: str, field_value: Any) -> str:
    """
    Determine the appropriate category for a field based on its name and value.
    
    Args:
        field_name: The name of the field
        field_value: The value of the field
        
    Returns:
        Category identifier string
    """
    field_name_lower = field_name.lower()
    
    # Personal information patterns
    if any(term in field_name_lower for term in [
        'name', 'first', 'last', 'middle', 'full', 'gender', 'sex', 
        'age', 'birth', 'nationality', 'citizenship', 'marital', 
        'spouse', 'dependent'
    ]):
        return FieldCategory.PERSONAL
    
    # Identification patterns
    if any(term in field_name_lower for term in [
        'id', 'identification', 'passport', 'license', 'ssn', 'social_security',
        'tax', 'tin', 'driver', 'national_id', 'certificate', 'registration'
    ]):
        return FieldCategory.IDENTIFICATION
    
    # Contact information patterns
    if any(term in field_name_lower for term in [
        'phone', 'mobile', 'cell', 'telephone', 'email', 'fax', 
        'website', 'url', 'web', 'contact'
    ]):
        return FieldCategory.CONTACT
    
    # Address patterns
    if any(term in field_name_lower for term in [
        'address', 'street', 'road', 'avenue', 'boulevard', 'lane', 'drive',
        'city', 'town', 'state', 'province', 'county', 'country', 'zip', 'postal',
        'apartment', 'unit', 'building', 'floor', 'suite'
    ]):
        return FieldCategory.ADDRESS
    
    # Financial patterns
    if any(term in field_name_lower for term in [
        'amount', 'payment', 'fee', 'price', 'cost', 'value', 'total',
        'sum', 'balance', 'deposit', 'withdraw', 'transfer', 'transaction',
        'account', 'bank', 'currency', 'interest', 'principal', 'loan', 'debt',
        'credit', 'debit', 'income', 'expense', 'salary', 'wage', 'tax', 'rate'
    ]):
        return FieldCategory.FINANCIAL
    
    # Date patterns
    if any(term in field_name_lower for term in [
        'date', 'time', 'day', 'month', 'year', 'expiry', 'expiration',
        'issued', 'effective', 'start', 'end', 'term', 'period', 'duration',
        'deadline', 'schedule', 'calendar', 'anniversary', 'renewal'
    ]):
        return FieldCategory.DATES
    
    # Document information patterns
    if any(term in field_name_lower for term in [
        'document', 'form', 'application', 'file', 'record', 'type',
        'category', 'class', 'title', 'name', 'subject', 'reference', 'number',
        'status', 'version', 'revision', 'edition', 'signature'
    ]):
        return FieldCategory.DOCUMENT
    
    # Property patterns
    if any(term in field_name_lower for term in [
        'property', 'land', 'real_estate', 'parcel', 'lot', 'plot', 'acre', 
        'hectare', 'square', 'dimension', 'area', 'footage', 'asset', 'estate'
    ]):
        return FieldCategory.PROPERTY
    
    # Parties involved patterns
    if any(term in field_name_lower for term in [
        'party', 'grantor', 'grantee', 'borrower', 'lender', 'buyer', 'seller',
        'owner', 'tenant', 'landlord', 'lessor', 'lessee', 'assignor', 'assignee',
        'trustee', 'beneficiary', 'guarantor', 'witness', 'signatory', 'agent',
        'representative', 'broker', 'attorney', 'lawyer', 'notary'
    ]):
        return FieldCategory.PARTIES
    
    # Legal terms patterns
    if any(term in field_name_lower for term in [
        'term', 'condition', 'clause', 'provision', 'covenant', 'warranty',
        'representation', 'indemnity', 'liability', 'obligation', 'right',
        'law', 'legal', 'regulation', 'compliance', 'violation', 'penalty',
        'dispute', 'resolution', 'arbitration', 'litigation', 'jurisdiction',
        'governing', 'enforcement'
    ]):
        return FieldCategory.LEGAL
    
    # Default to OTHER if no specific category is matched
    return FieldCategory.OTHER

def get_primary_fields(categorized_fields: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract the most important fields from each category.
    
    Args:
        categorized_fields: Dictionary of category names to dictionaries of categorized fields
        
    Returns:
        Dictionary of the most important fields across categories
    """
    primary_fields = {}
    
    # Define priority fields for each category
    priority_fields = {
        FieldCategory.PERSONAL: ['full_name', 'first_name', 'last_name', 'date_of_birth', 'gender'],
        FieldCategory.IDENTIFICATION: ['identification_number', 'passport_number', 'social_security_number', 'drivers_license_number'],
        FieldCategory.CONTACT: ['email', 'phone_number', 'mobile_number'],
        FieldCategory.ADDRESS: ['address', 'street_address', 'city', 'state', 'zip_code', 'country'],
        FieldCategory.FINANCIAL: ['total_amount', 'payment_amount', 'fee_amount', 'price_amount'],
        FieldCategory.DATES: ['issue_date', 'effective_date', 'expiration_date', 'signing_date'],
        FieldCategory.DOCUMENT: ['document_type', 'document_number', 'document_title', 'reference_number'],
        FieldCategory.PARTIES: ['grantor', 'grantee', 'buyer', 'seller', 'owner', 'tenant'],
        FieldCategory.PROPERTY: ['property_address', 'property_description', 'property_value'],
    }
    
    # For each category, extract priority fields if available
    for category, fields in categorized_fields.items():
        if category in priority_fields:
            # First try to find exact matches for priority fields
            for priority_field in priority_fields[category]:
                if priority_field in fields:
                    primary_fields[priority_field] = fields[priority_field]
                    
            # If no exact matches, try partial matches
            if category not in [k.split('.')[0] for k in primary_fields.keys()]:
                for field_name in fields:
                    for priority_field in priority_fields[category]:
                        if priority_field in field_name:
                            primary_fields[field_name] = fields[field_name]
                            break
            
            # If still no matches, just take the first field if available
            if category not in [k.split('.')[0] for k in primary_fields.keys()] and fields:
                first_field = next(iter(fields.items()))
                primary_fields[first_field[0]] = first_field[1]
    
    return primary_fields

def match_related_fields(fields: Dict[str, Any]) -> List[Tuple[str, str, float]]:
    """
    Find potentially related fields based on field name patterns.
    
    Args:
        fields: Dictionary of field name to field value
        
    Returns:
        List of tuples (field1, field2, relationship_score)
    """
    related_fields = []
    field_names = list(fields.keys())
    
    # Define patterns for field relationships
    relationships = [
        # Names (first, middle, last)
        (r'first_name', r'last_name', 0.9),
        (r'first_name', r'middle_name', 0.8),
        (r'middle_name', r'last_name', 0.8),
        # Address components
        (r'address', r'city', 0.9),
        (r'city', r'state', 0.9),
        (r'state', r'zip_code', 0.9),
        (r'country', r'(city|state|zip)', 0.8),
        # Dates
        (r'issue_date', r'expiration_date', 0.9),
        (r'start_date', r'end_date', 0.9),
        (r'effective_date', r'term_date', 0.8),
        # Parties
        (r'grantor', r'grantee', 0.9),
        (r'buyer', r'seller', 0.9),
        (r'landlord', r'tenant', 0.9),
        (r'lender', r'borrower', 0.9),
    ]
    
    for i, field1 in enumerate(field_names):
        for j, field2 in enumerate(field_names[i+1:], i+1):
            # Skip comparing the same field
            if field1 == field2:
                continue
                
            # Check field name patterns for relationships
            for pattern1, pattern2, score in relationships:
                if (re.search(pattern1, field1, re.IGNORECASE) and re.search(pattern2, field2, re.IGNORECASE)) or \
                   (re.search(pattern2, field1, re.IGNORECASE) and re.search(pattern1, field2, re.IGNORECASE)):
                    related_fields.append((field1, field2, score))
                    break
            
            # Check for fields with the same prefix but different suffixes
            if '_' in field1 and '_' in field2:
                prefix1 = field1.split('_')[0]
                prefix2 = field2.split('_')[0]
                if prefix1 == prefix2 and len(prefix1) > 2:
                    related_fields.append((field1, field2, 0.7))
    
    return sorted(related_fields, key=lambda x: x[2], reverse=True)
