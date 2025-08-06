from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator
import re
from datetime import date, datetime

class DocumentData(BaseModel):
    """
    Structured data extracted from identity documents.
    
    This model is designed to work with Pydantic AI for automatic extraction
    of structured information from identity documents.
    """
    
    # Document metadata
    document_type: str = Field(description="Type of document (passport, national ID, driver's license, voter card, NIN slip, etc.)")
    country: Optional[str] = Field(None, description="Issuing country of the document")
    
    # Personal information
    surname: str = Field(description="Last name/surname of the document holder")
    given_names: str = Field(description="First and middle names of the document holder")
    full_name: Optional[str] = Field(None, description="Full name as it appears on the document (if different from given_names + surname)")
    nationality: Optional[str] = Field(None, description="Nationality of the document holder")
    sex: Optional[str] = Field(None, description="Gender of the document holder (M/F/X)")
    date_of_birth: Optional[str] = Field(None, description="Date of birth in ISO format (YYYY-MM-DD) or as it appears on document")
    place_of_birth: Optional[str] = Field(None, description="Place of birth")
    
    # Document details
    document_number: str = Field(description="The primary identification number of the document")
    date_of_issue: Optional[str] = Field(None, description="Date when the document was issued (YYYY-MM-DD)")
    date_of_expiry: Optional[str] = Field(None, description="Date when the document expires (YYYY-MM-DD)")
    issuing_authority: Optional[str] = Field(None, description="Authority that issued the document")
    
    # Additional fields for specific document types
    # National ID specific fields
    nin: Optional[str] = Field(None, description="National Identification Number, if present")
    id_card_type: Optional[str] = Field(None, description="Type of ID card (e.g., National, Resident, Temporary)")
    
    # Passport specific fields
    mrz_lines: Optional[List[str]] = Field(None, description="Machine Readable Zone text lines, if present")
    passport_type: Optional[str] = Field(None, description="Type of passport (e.g., Regular, Diplomatic, Service)")
    
    # Driver's license specific fields
    license_class: Optional[str] = Field(None, description="License class/category for driver's licenses")
    vehicle_categories: Optional[List[str]] = Field(None, description="Vehicle categories for driver's licenses")
    restrictions: Optional[str] = Field(None, description="Restrictions on a license or permit")
    endorsements: Optional[str] = Field(None, description="Special endorsements on a driver's license")
    
    # Voter registration specific fields
    voting_district: Optional[str] = Field(None, description="Voting district/constituency for voter cards")
    voter_number: Optional[str] = Field(None, description="Voter registration number for voter cards")
    polling_unit: Optional[str] = Field(None, description="Specific polling unit or station")
    voter_status: Optional[str] = Field(None, description="Status of voter registration")
    
    # NIN slip/card specific fields
    nin_tracking_id: Optional[str] = Field(None, description="Tracking ID associated with NIN")
    
    # Residence permit specific fields
    permit_type: Optional[str] = Field(None, description="Type of residence permit")
    permit_category: Optional[str] = Field(None, description="Category of residence permit (e.g., work, study, family)")
    
    # Birth certificate specific fields
    birth_certificate_number: Optional[str] = Field(None, description="Birth certificate identification number")
    birth_registration_date: Optional[str] = Field(None, description="Date when birth was registered")
    parents_names: Optional[dict] = Field(None, description="Names of parents (mother, father)")
    
    # Metadata about extraction
    extraction_method: str = Field("OCR", description="Method used to extract the data: 'OCR', 'LLM', or 'OCR+LLM'")
    confidence_score: Optional[float] = Field(None, description="Overall confidence score of the extraction (0-1)")
    
    # Validators to standardize date formats where possible
    @field_validator('date_of_birth', 'date_of_issue', 'date_of_expiry')
    def validate_date_format(cls, v):
        if not v:
            return v
            
        # Try to standardize date format
        try:
            # Common date formats to try
            date_formats = [
                '%Y-%m-%d',        # 2023-01-15
                '%d/%m/%Y',        # 15/01/2023
                '%m/%d/%Y',        # 01/15/2023
                '%d-%m-%Y',        # 15-01-2023
                '%m-%d-%Y',        # 01-15-2023
                '%d %b %Y',        # 15 Jan 2023
                '%d %B %Y',        # 15 January 2023
                '%b %d %Y',        # Jan 15 2023
                '%B %d %Y',        # January 15 2023
                '%d.%m.%Y',        # 15.01.2023
                '%Y/%m/%d',        # 2023/01/15
            ]
            
            # If it's already in ISO format, return as is
            if re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                return v
                
            # Try to parse with various formats
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(v, fmt)
                    return parsed_date.strftime('%Y-%m-%d')  # Convert to ISO format
                except ValueError:
                    continue
                    
            # If we can't parse it, return the original string
            return v
        except Exception:
            # If any error occurs, return the original string
            return v
    
    class Config:
        schema_extra = {
            "example": {
                "document_type": "International Passport",
                "country": "Nigeria",
                "surname": "ALEJO",
                "given_names": "OLUWASEGUN MICHEAL",
                "nationality": "NIGERIAN",
                "sex": "M",
                "date_of_birth": "1997-04-29",
                "place_of_birth": "LAGOS",
                "document_number": "B02663186",
                "date_of_issue": "2023-09-17",
                "date_of_expiry": "2028-09-16",
                "issuing_authority": "ABEOKUTA",
                "nin": "90605780898",
                "extraction_method": "OCR+LLM",
                "confidence_score": 0.92
            },
            "examples": [
                # International Passport example
                {
                    "document_type": "International Passport",
                    "country": "Nigeria",
                    "surname": "ALEJO",
                    "given_names": "OLUWASEGUN MICHEAL",
                    "nationality": "NIGERIAN",
                    "sex": "M",
                    "date_of_birth": "1997-04-29",
                    "place_of_birth": "LAGOS",
                    "document_number": "B02663186",
                    "date_of_issue": "2023-09-17",
                    "date_of_expiry": "2028-09-16",
                    "issuing_authority": "ABEOKUTA",
                    "nin": "90605780898",
                    "mrz_lines": ["P<NGAALEJO<<OLUWASEGUN<MICHEAL<<<<<<<<<<<<<<<", "B02663186NGA9704296M2809168<<<<<<<<<<<<<<06"],
                    "extraction_method": "OCR+LLM",
                    "confidence_score": 0.92
                },
                # Driver's License example
                {
                    "document_type": "Driver's License",
                    "country": "United States",
                    "surname": "SMITH",
                    "given_names": "JOHN MICHAEL",
                    "nationality": "USA",
                    "sex": "M",
                    "date_of_birth": "1985-06-15",
                    "document_number": "DL1234567",
                    "date_of_issue": "2020-01-10",
                    "date_of_expiry": "2028-01-10",
                    "issuing_authority": "DMV CALIFORNIA",
                    "license_class": "C",
                    "vehicle_categories": ["Passenger vehicles"],
                    "restrictions": "Corrective lenses",
                    "extraction_method": "LLM",
                    "confidence_score": 0.89
                },
                # Voter Card example
                {
                    "document_type": "Voter Registration Card",
                    "country": "Nigeria",
                    "surname": "ADEBAYO",
                    "given_names": "FOLAKE ELIZABETH",
                    "sex": "F",
                    "date_of_birth": "1990-11-28",
                    "document_number": "VC98765432",
                    "date_of_issue": "2022-08-05",
                    "issuing_authority": "INEC",
                    "voting_district": "LAGOS-EAST/15/07/09",
                    "voter_number": "9876543210",
                    "extraction_method": "OCR+LLM",
                    "confidence_score": 0.85
                }
            ]
        }
