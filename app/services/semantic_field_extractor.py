"""Semantic field extraction using LLM analysis to find entities and relationships across document text."""

import os
import re
import json
from typing import Dict, Any, List, Optional
from groq import Groq
from dotenv import load_dotenv

from app.models.document_data import FieldWithConfidence

# Load environment variables from .env file
load_dotenv()

# Get environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class SemanticFieldExtractor:
    """
    Extract semantically meaningful fields from document text using LLM analysis.
    This extracts entities and relationships that may be spread across different parts of the document.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API credentials"""
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("API key is required. Set environment variable or pass it to the constructor.")
        
        # Initialize Groq client
        self.client = Groq(api_key=self.api_key)
    
    async def extract_semantic_fields(
        self, 
        document_type: str, 
        ocr_text: str, 
        current_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyzes document text to extract semantically meaningful entities and relationships
        
        Args:
            document_type: The type of document being analyzed
            ocr_text: Raw OCR text from the document
            current_fields: Currently extracted fields
            
        Returns:
            Dictionary of field names to FieldWithConfidence objects with semantic entities
        """
        print(f"🧠 Extracting semantic fields for document type: {document_type}")
        
        # Define document type specific extraction guidelines
        guidelines = self._get_document_guidelines(document_type)
        
        # Create field analysis prompt
        prompt = self._create_semantic_extraction_prompt(document_type, ocr_text, current_fields, guidelines)
        
        try:
            # Call LLM for semantic analysis
            completion = self.client.chat.completions.create(
                model="kimi-k2-instruct",
                messages=[
                    {"role": "system", "content": "You are an expert in document analysis and entity extraction, specialized in identifying key information and relationships."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            response_content = completion.choices[0].message.content
            
            if not response_content or not response_content.strip():
                print("⚠️ Empty response from LLM")
                return {}
                
            extracted_fields = json.loads(response_content)
            
            # Convert to proper field format and filter irrelevant fields
            semantic_fields = {}
            
            # Define data field patterns that are considered valuable
            valuable_field_patterns = [
                # People and roles
                r'.*_(name|role|title|position|signatory|party|person|individual|contact)$',
                # Identifiers
                r'.*_(id|number|code|reference|identifier|account|case|file|registration|license)$',
                # Dates and times
                r'.*_(date|time|period|term|duration|expiry|expiration|deadline|schedule)$',
                # Locations and jurisdictions
                r'.*_(address|location|place|city|state|country|jurisdiction|venue|county|district)$',
                # Monetary and numerical values
                r'.*_(amount|fee|cost|price|value|payment|salary|income|rate|percentage|total|sum)$',
                # Legal terms and status
                r'.*_(status|condition|term|provision|clause|requirement|obligation|right|restriction|limitation)$',
                # Document properties
                r'.*_(type|category|classification|class|grade|level|tier|rank|priority)$',
                # Entity relationships
                r'(grantor|grantee|witness|guarantor|borrower|lender|employer|employee|buyer|seller|landlord|tenant|owner|occupant).*'
            ]
            
            for field_name, field_value in extracted_fields.items():
                # Skip empty or None values
                if field_value is None or (isinstance(field_value, dict) and (field_value.get("value") is None or field_value.get("value") == "")):
                    continue
                    
                # Skip fields with very long values (likely full sentences or paragraphs)
                if isinstance(field_value, dict) and isinstance(field_value.get("value"), str) and len(field_value.get("value")) > 150:
                    print(f"⚠️ Skipping field {field_name} with long value ({len(field_value.get('value'))} chars)")
                    continue
                    
                # Skip non-descriptive field names
                if len(field_name) < 3 or field_name in ["the", "and", "for", "this", "that"]:
                    continue
                
                # Check if field name matches valuable patterns
                is_valuable = False
                for pattern in valuable_field_patterns:
                    if re.match(pattern, field_name, re.IGNORECASE):
                        is_valuable = True
                        break
                        
                if not is_valuable:
                    # Skip fields that don't match valuable patterns unless they have high confidence
                    if isinstance(field_value, dict) and field_value.get("confidence", 0) < 0.85:
                        print(f"⚠️ Skipping non-essential field: {field_name}")
                        continue
                
                # Format the field properly
                if isinstance(field_value, dict) and "value" in field_value:
                    semantic_fields[field_name] = FieldWithConfidence(
                        value=field_value["value"],
                        confidence=field_value.get("confidence", 0.8)
                    ).model_dump()
                else:
                    semantic_fields[field_name] = FieldWithConfidence(
                        value=field_value,
                        confidence=0.8
                    ).model_dump()
            
            print(f"✅ Extracted {len(semantic_fields)} semantic fields after filtering")
            return semantic_fields
            
        except Exception as e:
            print(f"❌ Error extracting semantic fields: {str(e)}")
            return {}
    
    def _get_document_guidelines(self, document_type: str) -> str:
        """
        Get document-specific extraction guidelines with universal extraction principles
        """
        # Universal extraction guidelines that apply to ALL document types
        universal_guidelines = """
        UNIVERSAL INTELLIGENT EXTRACTION PRINCIPLES:
        
        For ANY document type, always apply these principles:
        
        1. ENTITY IDENTIFICATION:
           - Identify people, organizations, and entities mentioned by name
           - Determine their role/relationship in the document context
           - Create fields named [role]_name containing the person/entity name
        
        2. RELATIONSHIP MAPPING:
           - Identify who is related to whom and how
           - Map ownership, responsibility, and authority relationships
           - Use field names that show the relationship (owner_of_property, guarantor_for_borrower)
        
        3. DOCUMENT PURPOSE RECOGNITION:
           - Understand what the document is trying to accomplish
           - Extract key information related to its primary purpose
           - Focus on information most relevant to document's main function
        
        4. CONTEXTUAL FIELD NAMING:
           - Name fields according to their semantic role, not just content type
           - Include both CONTEXT (whose/what aspect) and CONTENT TYPE (name/date/amount)
           - Example: "borrower_address" not just "address"
        
        5. PATTERN RECOGNITION ACROSS DOCUMENT TYPES:
           - Identify patterns like "[Person] as [Role]" → [role]_name: Person
           - Extract from phrases like "[Person], (the [Role])" → [role]_name: Person
           - Capture relationships like "[Entity] located at [Address]" → [entity]_address: Address
        
        ENTITY EXTRACTION TECHNIQUES FOR ALL DOCUMENTS:
        
        1. FOR PEOPLE & ORGANIZATIONS:
           - Look for titles or descriptors near names (Mr., Dr., Company, Corporation)
           - Identify roles from context (borrower, lender, applicant, owner)
           - Examine text around quotes, parentheses, or "the" for role indicators
        
        2. FOR LOCATIONS & PROPERTIES:
           - Look for address patterns (street numbers, postal codes)
           - Identify location references with context words (located at, premises at)
           - Distinguish between mailing addresses and physical locations
        
        3. FOR DATES & TIMEFRAMES:
           - Identify the purpose of each date (issue, expiry, birth, effective)
           - Look for date formats (MM/DD/YYYY, Month Day, Year)
           - Connect dates to events or actions they relate to
        
        4. FOR IDENTIFIERS & REFERENCES:
           - Recognize document numbers, account numbers, reference codes
           - Look for formatted patterns like XXX-XX-XXXX, XXXXX-XXXX
           - Connect identifiers to what they identify
        
        5. FOR CONDITIONS & TERMS:
           - Identify restrictions, requirements, prohibitions
           - Look for "must", "shall", "no", "prohibited", "required"
           - Name fields according to what is being restricted/required
        """
        
        # Now add document-specific guidelines
        if "land" in document_type.lower() or "agreement" in document_type.lower():
            return universal_guidelines + """
            SPECIFIC TO AGREEMENTS & CONTRACTS:
            
            1. PARTY IDENTIFICATION:
               - Look specifically for "Grantor", "Grantee", "Lessor", "Lessee", "Buyer", "Seller"
               - Extract names using patterns like "[NAME], (the \"Grantor\")"
               - Create fields like grantor_name, grantee_name with the actual person/entity name
            
            2. PROPERTY INFORMATION:
               - Extract complete property addresses and descriptions
               - Look for legal descriptions following property addresses
               - Identify property by references like "the Land", "the Premises", "the Property"
            
            3. AGREEMENT TERMS:
               - Extract specific restrictions, conditions, and requirements
               - Look for sections describing what parties can/cannot do
               - Create specific fields for each type of restriction
            
            4. TEMPORAL INFORMATION:
               - Identify agreement effective date, termination date
               - Extract durations, terms, and notice periods
               - Look for renewal and extension provisions
            """
        elif "license" in document_type.lower() or "driving" in document_type.lower() or "id" in document_type.lower() or "card" in document_type.lower() or "passport" in document_type.lower():
            return universal_guidelines + """
            SPECIFIC TO IDENTIFICATION DOCUMENTS:
            
            1. HOLDER INFORMATION:
               - Extract the document holder's full name and create holder_name field
               - Look for personal attributes (height, weight, eye color, etc.)
               - Find the holder's address information
            
            2. DOCUMENT IDENTIFIERS:
               - Look for formatted ID numbers, license numbers, passport numbers
               - Extract document class or type information
               - Identify security features or special codes
            
            3. VALIDITY INFORMATION:
               - Extract issue date, expiry date, and valid period
               - Look for restrictions or limitations on use
               - Identify issuing authority or office
            
            4. SPECIAL ENDORSEMENTS:
               - Look for special permissions or endorsements
               - Extract vehicle classes or categories
               - Identify special status indicators (organ donor, veteran)
            
            5. SECONDARY IDENTIFIERS:
               - Extract secondary numbers like NIN, SSN, or other reference codes
               - Look for machine readable information (MRZ)
               - Identify unique document attributes
            """
        elif "financial" in document_type.lower() or "invoice" in document_type.lower() or "receipt" in document_type.lower() or "statement" in document_type.lower():
            return universal_guidelines + """
            SPECIFIC TO FINANCIAL DOCUMENTS:
            
            1. MONETARY INFORMATION:
               - Extract all currency amounts with their purpose
               - Look for totals, subtotals, taxes, fees
               - Identify payment terms and conditions
            
            2. PARTY INFORMATION:
               - Identify payer/payee relationships
               - Extract account holder information
               - Look for billing and shipping addresses
            
            3. TRANSACTION DETAILS:
               - Extract transaction dates, reference numbers
               - Identify products/services provided
               - Look for quantity, rate, and amount information
            
            4. PAYMENT INFORMATION:
               - Extract payment methods, account numbers (last 4 digits)
               - Identify payment status (paid, due, overdue)
               - Look for payment schedules or installments
            """
        else:
            # Generic guidelines that work for any document type
            return universal_guidelines + """
            GENERAL DOCUMENT ANALYSIS:
            
            1. DOCUMENT CLASSIFICATION:
               - Determine the document's primary purpose and function
               - Identify key sections and their purposes
               - Extract the most relevant information based on document type
            
            2. ENTITY EXTRACTION:
               - Identify all named people and organizations
               - Determine their roles in the document context
               - Map relationships between entities
            
            3. KEY INFORMATION EXTRACTION:
               - Extract dates with their purpose/context
               - Identify all reference numbers and identifiers
               - Capture locations, addresses, and jurisdictions
               - Extract monetary amounts and financial terms
            
            4. DOCUMENT-SPECIFIC CONTENT:
               - Look for specialized terminology relevant to the document domain
               - Identify technical specifications or parameters
               - Extract domain-specific information based on document context
            
            5. STATUS AND CLASSIFICATION:
               - Determine document status (draft, final, approved)
               - Identify classification or confidentiality level
               - Extract validity and effective date information
            """
    
    def _create_semantic_extraction_prompt(
        self, 
        document_type: str, 
        ocr_text: str, 
        current_fields: Dict[str, Any],
        guidelines: str
    ) -> str:
        """
        Create prompt for semantic field extraction
        """
        # Truncate OCR text if it's too long
        if len(ocr_text) > 6000:
            ocr_text = ocr_text[:6000] + "..."
        
        # Format current fields for context
        fields_str = json.dumps(current_fields, indent=2)[:1000] + "..." if len(json.dumps(current_fields)) > 1000 else json.dumps(current_fields, indent=2)
        
        return f"""
        # UNIVERSAL INTELLIGENT DOCUMENT ANALYSIS: SEMANTIC ENTITY EXTRACTION
        
        ## DOCUMENT TYPE
        {document_type}
        
        ## DOCUMENT TEXT
        ```
        {ocr_text}
        ```
        
        ## CURRENTLY EXTRACTED FIELDS
        ```json
        {fields_str}
        ```
        
        ## DOCUMENT-SPECIFIC EXTRACTION GUIDELINES
        {guidelines}
        
        ## YOUR TASK: UNIVERSAL INTELLIGENT SEMANTIC ANALYSIS
        
        You are an expert in document analysis with advanced semantic understanding capabilities. Your task is to extract meaningful data entities from ANY type of document, understanding the context, roles, and relationships regardless of document format.
        
        ## UNIVERSAL EXTRACTION PRINCIPLES
        
        1. CONTEXTUAL UNDERSTANDING: Detect what the document is about and extract relevant information
        2. ENTITY RECOGNITION: Identify people, organizations, and other entities with their roles
        3. RELATIONSHIP MAPPING: Understand relationships between entities (who is doing what, who owns what)
        4. SEMANTIC FIELD NAMING: Create field names that convey both WHAT the data is and its CONTEXT
        5. DOCUMENT PATTERN RECOGNITION: Recognize common patterns across document types
        
        ## UNIVERSAL ENTITY DETECTION PATTERNS
        
        Look for these patterns in ANY document type:
        
        1. PEOPLE AND ROLES:
           - "[NAME], (the \"[ROLE]\")" → [role]_name: NAME
           - "the [ROLE], [NAME]" → [role]_name: NAME
           - "[NAME], an individual with [DESCRIPTION]" → individual_name: NAME
           - "[NAME] as [ROLE]" → [role]_name: NAME
           
        2. LOCATIONS AND PROPERTIES:
           - Street addresses with city, state/province → location or address field
           - References to "premises", "property", "land" → property_location or property_description
           
        3. IDENTIFIERS AND REFERENCES:
           - Document numbers, reference codes, IDs → [document_type]_number or reference_id
           - Serial numbers, registration numbers → [context]_number or [item]_id
           
        4. DATES AND TIMEFRAMES:
           - Dates with context (effective, expiry, issue) → [context]_date
           - Periods, durations, terms → [context]_period or [context]_duration
           
        5. CONDITIONS AND REQUIREMENTS:
           - "No [action/item]" statements → [item]_restriction or [action]_prohibition
           - "Must [action]" statements → [action]_requirement
           - Limitations, constraints → [item]_limitation
           
        6. FINANCIAL INFORMATION:
           - Currency amounts → [purpose]_amount or [context]_fee
           - Rates, percentages → [item]_rate or [context]_percentage
        
        ## SMART FIELD NAMING SYSTEM
        
        Always create field names that follow this pattern: [CONTEXT]_[WHAT]
        
        Where:
        - [CONTEXT] tells WHOSE information it is or WHAT ASPECT it relates to (grantor, property, license, agreement)
        - [WHAT] tells WHAT TYPE of data it is (name, date, address, number, amount, restriction)
        
        Examples:
        - "John Smith" as a grantor → "grantor_name": "John Smith"
        - "123 Main St" as property → "property_address": "123 Main St"
        - "$500" as payment → "payment_amount": "$500"
        - "January 15, 2025" as agreement date → "agreement_date": "January 15, 2025"
        
        ## DATA EXTRACTION FOCUS
        
        For ANY document type, ALWAYS extract these universal entities when present:
        
        1. People and organizations with their roles/relationships
        2. Dates with their purpose/context
        3. Locations with their relevance/purpose
        4. Amounts with their purpose
        5. Identifiers/numbers with their meaning
        6. Conditions, restrictions, requirements
        7. Status information and classifications
        
        ## OUTPUT FORMAT
        
        Return ONLY a JSON object with semantically meaningful field names and their values.
        Include confidence scores (0-1) with each field.
        
        Example format:
        ```json
        {{
          "grantor_name": {{ "value": "John Doe", "confidence": 0.95 }},
          "property_location": {{ "value": "123 Elm Street", "confidence": 0.9 }},
          "height_restriction": {{ "value": "No structure taller than two stories", "confidence": 0.85 }}
        }}
        ```
        
        ## QUALITY REQUIREMENTS
        
        1. EXTRACT ONLY meaningful data - not sentences, paragraphs, or explanatory text
        2. ALWAYS use specific, contextual field names (never generic names like "name" or "date")
        3. FOCUS on semantic understanding (who/what/when/where/why) for each piece of data
        4. AVOID DUPLICATING information already in the current fields
        5. APPLY these intelligent extraction principles to ANY document type
        6. PRIORITIZE quality over quantity - better to extract fewer meaningful fields than many low-quality ones
        
        Return ONLY the JSON object with meaningful fields and values - no explanations.
        """

async def enrich_with_semantic_fields(
    data_dict: Dict[str, Any], 
    document_type: str, 
    ocr_text: str
) -> Dict[str, Any]:
    """
    Enrich document data with semantically extracted fields
    
    Args:
        data_dict: Current document data dictionary
        document_type: Type of document being processed
        ocr_text: Raw OCR text
        
    Returns:
        Enriched dictionary with semantic fields
    """
    # Skip semantic extraction for certain document types or short texts
    if len(ocr_text) < 200:
        return data_dict
    
    try:
        # Create extractor
        semantic_extractor = SemanticFieldExtractor()
        
        # Get document type
        doc_type = document_type
        if isinstance(document_type, dict) and "value" in document_type:
            doc_type = document_type["value"]
        
        # Extract semantic fields
        semantic_fields = await semantic_extractor.extract_semantic_fields(
            doc_type, 
            ocr_text,
            data_dict
        )
        
        # Skip if no fields found
        if not semantic_fields:
            return data_dict
        
        # Initialize extra_fields if needed
        if 'extra_fields' not in data_dict or data_dict['extra_fields'] is None:
            data_dict['extra_fields'] = {}
        
        # Filter out low-quality fields from existing extra_fields
        if 'extra_fields' in data_dict and isinstance(data_dict['extra_fields'], dict):
            # List of fields to keep (meaningful fields)
            fields_to_keep = {}
            fields_to_remove = []
            
            # Define what makes a field name meaningful
            meaningful_field_patterns = [
                r'.*(name|address|date|number|id|code|amount|fee|location|type|role|title|reference|status).*',
                r'.*(grantor|grantee|borrower|lender|buyer|seller|owner|tenant|landlord|witness).*',
                r'.*(property|asset|land|document|restriction|limitation|requirement|condition).*',
                r'.*(payment|sum|total|value|price|cost|rate|percentage).*',
                r'.*(expiry|expiration|term|duration|period|deadline|schedule).*'
            ]
            
            for field_name, field_value in data_dict['extra_fields'].items():
                # Check if it's a meaningful field name
                is_meaningful = False
                
                # Check against patterns
                for pattern in meaningful_field_patterns:
                    if re.search(pattern, field_name, re.IGNORECASE):
                        is_meaningful = True
                        break
                
                # Also consider fields with high confidence
                if isinstance(field_value, dict) and field_value.get('confidence', 0) > 0.8:
                    is_meaningful = True
                    
                # If field name is very short or generic, likely not meaningful
                if len(field_name) < 4 or field_name in ['the', 'and', 'for', 'with', 'this', 'that', 'data', 'info']:
                    is_meaningful = False
                
                # Keep meaningful fields, mark others for removal
                if is_meaningful:
                    fields_to_keep[field_name] = field_value
                else:
                    fields_to_remove.append(field_name)
            
            # Replace extra_fields with only the meaningful ones
            if fields_to_remove:
                print(f"🧹 Removing {len(fields_to_remove)} non-meaningful fields from extra_fields")
                data_dict['extra_fields'] = fields_to_keep
        
        # Add semantic fields to extra_fields
        added_fields = 0
        for key, value in semantic_fields.items():
            if key not in data_dict and key not in data_dict.get('extra_fields', {}):
                data_dict['extra_fields'][key] = value
                added_fields += 1
        
        print(f"✅ Added {added_fields} semantic fields to document data")
        
    except Exception as e:
        print(f"⚠️ Error in semantic field extraction: {str(e)}")
    
    return data_dict
