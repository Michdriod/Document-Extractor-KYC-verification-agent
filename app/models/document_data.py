from typing import Optional, List, Union, Any
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator
import re
from datetime import date, datetime


class FieldWithConfidence(BaseModel):
    value: Optional[Union[str, int, float, list, dict]]
    confidence: Optional[float]

    def to_dict(self):
        """Convert FieldWithConfidence to a dictionary for JSON serialization."""
        return {
            "value": self.value,
            "confidence": self.confidence
        }

class DocumentData(BaseModel):
    """
    Structured data extracted from identity documents.
    
    This model is designed to work with Pydantic AI for automatic extraction
    of structured information from identity documents.
    """
    
    # Document metadata
    document_type: Optional[FieldWithConfidence] = Field(None, description="Type of document (passport, national ID, driver's license, voter card, NIN slip, etc.)")
    country: Optional[FieldWithConfidence] = Field(None, description="Issuing country of the document")
    
    # Personal information
    surname: Optional[FieldWithConfidence] = Field(None, description="Last name/surname of the document holder")
    given_names: Optional[FieldWithConfidence] = Field(None, description="First and middle names of the document holder")
    full_name: Optional[FieldWithConfidence] = Field(None, description="Full name as it appears on the document (if different from given_names + surname)")
    nationality: Optional[FieldWithConfidence] = Field(None, description="Nationality of the document holder")
    sex: Optional[FieldWithConfidence] = Field(None, description="Gender of the document holder (M/F/X)")
    date_of_birth: Optional[FieldWithConfidence] = Field(None, description="Date of birth in ISO format (YYYY-MM-DD) or as it appears on document")
    place_of_birth: Optional[FieldWithConfidence] = Field(None, description="Place of birth")
    
    # Document details
    document_number: Optional[FieldWithConfidence] = Field(None, description="The primary identification number of the document")
    date_of_issue: Optional[FieldWithConfidence] = Field(None, description="Date when the document was issued (YYYY-MM-DD)")
    date_of_expiry: Optional[FieldWithConfidence] = Field(None, description="Date when the document expires (YYYY-MM-DD)")
    issuing_authority: Optional[FieldWithConfidence] = Field(None, description="Authority that issued the document")
    
    # Additional fields for specific document types
    # National ID specific fields
    nin: Optional[FieldWithConfidence] = Field(None, description="National Identification Number, if present")
    id_card_type: Optional[FieldWithConfidence] = Field(None, description="Type of ID card (e.g., National, Resident, Temporary)")
    
    # Passport specific fields
    mrz_lines: Optional[List[FieldWithConfidence]] = Field(None, description="Machine Readable Zone text lines, if present")
    passport_type: Optional[FieldWithConfidence] = Field(None, description="Type of passport (e.g., Regular, Diplomatic, Service)")
    
    # Driver's license specific fields
    license_class: Optional[FieldWithConfidence] = Field(None, description="License class/category for driver's licenses")
    vehicle_categories: Optional[List[FieldWithConfidence]] = Field(None, description="Vehicle categories for driver's licenses")
    restrictions: Optional[FieldWithConfidence] = Field(None, description="Restrictions on a license or permit")
    endorsements: Optional[FieldWithConfidence] = Field(None, description="Special endorsements on a driver's license")
    
    # Voter registration specific fields
    voting_district: Optional[FieldWithConfidence] = Field(None, description="Voting district/constituency for voter cards")
    voter_number: Optional[FieldWithConfidence] = Field(None, description="Voter registration number for voter cards")
    polling_unit: Optional[FieldWithConfidence] = Field(None, description="Specific polling unit or station")
    voter_status: Optional[FieldWithConfidence] = Field(None, description="Status of voter registration")
    
    # NIN slip/card specific fields
    nin_tracking_id: Optional[FieldWithConfidence] = Field(None, description="Tracking ID associated with NIN")
    
    # Residence permit specific fields
    permit_type: Optional[FieldWithConfidence] = Field(None, description="Type of residence permit")
    permit_category: Optional[FieldWithConfidence] = Field(None, description="Category of residence permit (e.g., work, study, family)")
    
    # Birth certificate specific fields
    birth_certificate_number: Optional[FieldWithConfidence] = Field(None, description="Birth certificate identification number")
    birth_registration_date: Optional[FieldWithConfidence] = Field(None, description="Date when birth was registered")
    parents_names: Optional[FieldWithConfidence] = Field(None, description="Names of parents (mother, father)")
    
    # Removed duplicate/commented extra_fields
    
    # Address information (can apply to any document)
    address: Optional[FieldWithConfidence] = Field(None, description="Primary address mentioned in the document")
    secondary_address: Optional[FieldWithConfidence] = Field(None, description="Secondary or alternate address if present")
    
    # Contact information
    phone_number: Optional[FieldWithConfidence] = Field(None, description="Phone number if present")
    email: Optional[FieldWithConfidence] = Field(None, description="Email address if present")
    
    # General location and jurisdiction information
    jurisdiction: Optional[FieldWithConfidence] = Field(None, description="Legal jurisdiction or governing location")
    state_province: Optional[FieldWithConfidence] = Field(None, description="State or province information")
    
    # Metadata about extraction
    extraction_method: FieldWithConfidence = Field("OCR", description="Method used to extract the data: 'OCR', 'LLM', 'Vision LLM', or 'OCR+LLM'")
    confidence_score: Optional[float] = Field(None, description="Overall confidence score of the extraction (0-1)")
    
    # Dynamic field detection - the key to universal document handling
    extra_fields: Optional[Dict[str, FieldWithConfidence]] = Field(
        None,
        description="Intelligently detected fields specific to the document type. This captures ALL meaningful information not covered by standard fields. Use descriptive field names like 'grantor_name', 'property_location', 'restriction_details', 'contract_terms', etc."
    )
    
    # Validators to standardize date formats where possible
    @field_validator('date_of_birth', 'date_of_issue', 'date_of_expiry')
    def validate_date_format(cls, v):
        if not v or not getattr(v, 'value', None):
            return v
        value = v.value
        try:
            date_formats = [
                '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y',
                '%d %b %Y', '%d %B %Y', '%b %d %Y', '%B %d %Y', '%d.%m.%Y', '%Y/%m/%d'
            ]
            if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                return v
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(value, fmt)
                    return FieldWithConfidence(value=parsed_date.strftime('%Y-%m-%d'), confidence=v.confidence)
                except ValueError:
                    continue
            return v
        except Exception:
            return v
    
    class Config:
        schema_extra = {
            "example": {
                "document_type": {"value": "International Passport", "confidence": 0.99},
                "country": {"value": "Nigeria", "confidence": 0.98},
                "surname": {"value": "ALEJO", "confidence": 0.95},
                "given_names": {"value": "OLUWASEGUN MICHEAL", "confidence": 0.95},
                "nationality": {"value": "NIGERIAN", "confidence": 0.97},
                "sex": {"value": "M", "confidence": 0.99},
                "date_of_birth": {"value": "1997-04-29", "confidence": 0.95},
                "place_of_birth": {"value": "LAGOS", "confidence": 0.97},
                "document_number": {"value": "B02663186", "confidence": 0.98},
                "date_of_issue": {"value": "2023-09-17", "confidence": 0.97},
                "date_of_expiry": {"value": "2028-09-16", "confidence": 0.97},
                "issuing_authority": {"value": "ABEOKUTA", "confidence": 0.97},
                "nin": {"value": "90605780898", "confidence": 0.98},
                "extraction_method": {"value": "OCR+LLM", "confidence": 1.0},
                "confidence_score": 0.92
            },
            "examples": [
                # International Passport example
                {
                    "document_type": {"value": "International Passport", "confidence": 0.99},
                    "country": {"value": "Nigeria", "confidence": 0.98},
                    "surname": {"value": "ALEJO", "confidence": 0.95},
                    "given_names": {"value": "OLUWASEGUN MICHEAL", "confidence": 0.95},
                    "nationality": {"value": "NIGERIAN", "confidence": 0.97},
                    "sex": {"value": "M", "confidence": 0.99},
                    "date_of_birth": {"value": "1997-04-29", "confidence": 0.95},
                    "place_of_birth": {"value": "LAGOS", "confidence": 0.97},
                    "document_number": {"value": "B02663186", "confidence": 0.98},
                    "date_of_issue": {"value": "2023-09-17", "confidence": 0.97},
                    "date_of_expiry": {"value": "2028-09-16", "confidence": 0.97},
                    "issuing_authority": {"value": "ABEOKUTA", "confidence": 0.97},
                    "nin": {"value": "90605780898", "confidence": 0.98},
                    "mrz_lines": [
                        {"value": "P<NGAALEJO<<OLUWASEGUN<MICHEAL<<<<<<<<<<<<<<<", "confidence": 0.97},
                        {"value": "B02663186NGA9704296M2809168<<<<<<<<<<<<<<06", "confidence": 0.97}
                    ],
                    "extraction_method": {"value": "OCR+LLM", "confidence": 1.0},
                    "confidence_score": 0.92
                },
                # Driver's License example
                {
                    "document_type": {"value": "Driver's License", "confidence": 0.99},
                    "country": {"value": "United States", "confidence": 0.98},
                    "surname": {"value": "SMITH", "confidence": 0.95},
                    "given_names": {"value": "JOHN MICHAEL", "confidence": 0.95},
                    "nationality": {"value": "USA", "confidence": 0.97},
                    "sex": {"value": "M", "confidence": 0.99},
                    "date_of_birth": {"value": "1985-06-15", "confidence": 0.95},
                    "document_number": {"value": "DL1234567", "confidence": 0.98},
                    "date_of_issue": {"value": "2020-01-10", "confidence": 0.97},
                    "date_of_expiry": {"value": "2028-01-10", "confidence": 0.97},
                    "issuing_authority": {"value": "DMV CALIFORNIA", "confidence": 0.97},
                    "license_class": {"value": "C", "confidence": 0.98},
                    "vehicle_categories": [
                        {"value": "Passenger vehicles", "confidence": 0.97}
                    ],
                    "restrictions": {"value": "Corrective lenses", "confidence": 0.96},
                    "extraction_method": {"value": "LLM", "confidence": 1.0},
                    "confidence_score": 0.89
                },
                # Voter Card example
                {
                    "document_type": {"value": "Voter Registration Card", "confidence": 0.99},
                    "country": {"value": "Nigeria", "confidence": 0.98},
                    "surname": {"value": "ADEBAYO", "confidence": 0.95},
                    "given_names": {"value": "FOLAKE ELIZABETH", "confidence": 0.95},
                    "sex": {"value": "F", "confidence": 0.99},
                    "date_of_birth": {"value": "1990-11-28", "confidence": 0.95},
                    "document_number": {"value": "VC98765432", "confidence": 0.98},
                    "date_of_issue": {"value": "2022-08-05", "confidence": 0.97},
                    "issuing_authority": {"value": "INEC", "confidence": 0.97},
                    "voting_district": {"value": "LAGOS-EAST/15/07/09", "confidence": 0.96},
                    "voter_number": {"value": "9876543210", "confidence": 0.97},
                    "extraction_method": {"value": "OCR+LLM", "confidence": 1.0},
                    "confidence_score": 0.85
                }
            ]
        }
