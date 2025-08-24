"""
Document Type Detection Service

This service intelligently detects the type of document from OCR text
to enable dynamic field extraction strategies.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DocumentTypePattern:
    """Represents a document type detection pattern"""
    name: str
    confidence: float
    patterns: List[str]
    required_elements: List[str]
    optional_elements: List[str]


class DocumentTypeDetector:
    """
    Intelligent document type detection for universal document processing.
    
    This detector identifies document types to enable adaptive extraction strategies
    while maintaining flexibility for any document type.
    """
    
    def __init__(self):
        self.document_patterns = self._initialize_patterns()
    
    def _initialize_patterns(self) -> List[DocumentTypePattern]:
        """Initialize known document type patterns"""
        return [
            # Identity Documents
            DocumentTypePattern(
                name="international_passport",
                confidence=0.95,
                patterns=[r"passport", r"international.*passport", r"p<[a-z]{3}"],
                required_elements=["passport"],
                optional_elements=["nationality", "document.*number", "date.*birth"]
            ),
            DocumentTypePattern(
                name="national_id_card",
                confidence=0.90,
                patterns=[r"national.*id", r"identity.*card", r"nin"],
                required_elements=["national", "id"],
                optional_elements=["identification", "number"]
            ),
            DocumentTypePattern(
                name="drivers_license",
                confidence=0.90,
                patterns=[r"driver.*license", r"driving.*license", r"license.*class"],
                required_elements=["license"],
                optional_elements=["driver", "class", "vehicle"]
            ),
            DocumentTypePattern(
                name="voter_registration_card",
                confidence=0.90,
                patterns=[r"voter.*card", r"voter.*registration", r"polling.*unit"],
                required_elements=["voter"],
                optional_elements=["registration", "card", "polling"]
            ),
            
            # Legal Documents
            DocumentTypePattern(
                name="land_use_restriction_agreement",
                confidence=0.95,
                patterns=[r"land.*use.*restriction", r"land.*use.*agreement", r"restriction.*agreement"],
                required_elements=["land", "restriction"],
                optional_elements=["agreement", "grantor", "grantee"]
            ),
            DocumentTypePattern(
                name="contract",
                confidence=0.85,
                patterns=[r"contract", r"agreement", r"whereas", r"party.*agrees"],
                required_elements=["contract|agreement"],
                optional_elements=["parties", "terms", "conditions"]
            ),
            DocumentTypePattern(
                name="lease_agreement",
                confidence=0.90,
                patterns=[r"lease.*agreement", r"rental.*agreement", r"tenant.*landlord"],
                required_elements=["lease"],
                optional_elements=["tenant", "landlord", "rent"]
            ),
            
            # Certificates
            DocumentTypePattern(
                name="birth_certificate",
                confidence=0.95,
                patterns=[r"birth.*certificate", r"certificate.*birth"],
                required_elements=["birth", "certificate"],
                optional_elements=["born", "parents"]
            ),
            DocumentTypePattern(
                name="marriage_certificate",
                confidence=0.95,
                patterns=[r"marriage.*certificate", r"certificate.*marriage"],
                required_elements=["marriage", "certificate"],
                optional_elements=["spouse", "married"]
            ),
            DocumentTypePattern(
                name="academic_certificate",
                confidence=0.90,
                patterns=[r"certificate.*completion", r"diploma", r"degree.*certificate"],
                required_elements=["certificate"],
                optional_elements=["institution", "course", "grade"]
            ),
            
            # Financial Documents
            DocumentTypePattern(
                name="invoice",
                confidence=0.90,
                patterns=[r"invoice", r"bill.*to", r"amount.*due"],
                required_elements=["invoice"],
                optional_elements=["amount", "due", "total"]
            ),
            DocumentTypePattern(
                name="receipt",
                confidence=0.85,
                patterns=[r"receipt", r"payment.*received", r"thank.*you.*purchase"],
                required_elements=["receipt"],
                optional_elements=["payment", "total", "change"]
            ),
            
            # Medical Documents
            DocumentTypePattern(
                name="medical_certificate",
                confidence=0.90,
                patterns=[r"medical.*certificate", r"health.*certificate", r"fit.*work"],
                required_elements=["medical"],
                optional_elements=["certificate", "health", "doctor"]
            ),
            
            # Government Documents
            DocumentTypePattern(
                name="permit",
                confidence=0.85,
                patterns=[r"permit", r"authorization", r"license.*operate"],
                required_elements=["permit"],
                optional_elements=["authorization", "valid", "expires"]
            ),
        ]
    
    def detect_document_type(self, ocr_text: str) -> Tuple[str, float, Dict[str, any]]:
        """
        Detect document type from OCR text using intelligent pattern matching.
        
        Args:
            ocr_text: Raw OCR text from the document
            
        Returns:
            Tuple of (document_type, confidence, analysis_details)
        """
        if not ocr_text or not ocr_text.strip():
            return "unknown_document", 0.5, {"reason": "Empty OCR text"}
        
        text_lower = ocr_text.lower()
        
        # Score each document type pattern
        type_scores = []
        
        for pattern in self.document_patterns:
            score = self._calculate_pattern_score(text_lower, pattern)
            if score > 0:
                type_scores.append((pattern.name, score, pattern))
        
        # If no patterns match, try generic detection
        if not type_scores:
            return self._detect_generic_type(text_lower)
        
        # Sort by score and return the best match
        type_scores.sort(key=lambda x: x[1], reverse=True)
        best_match = type_scores[0]
        
        analysis = {
            "matched_patterns": [score[0] for score in type_scores[:3]],  # Top 3 matches
            "confidence_factors": self._analyze_confidence_factors(text_lower, best_match[2])
        }
        
        return best_match[0], best_match[1], analysis
    
    def _calculate_pattern_score(self, text: str, pattern: DocumentTypePattern) -> float:
        """Calculate how well the text matches a document pattern"""
        score = 0.0
        
        # Check required elements
        required_found = 0
        for element in pattern.required_elements:
            if re.search(element, text, re.IGNORECASE):
                required_found += 1
        
        # Must have all required elements
        if required_found < len(pattern.required_elements):
            return 0.0
        
        # Base score for required elements
        score += 0.6
        
        # Check pattern matches
        pattern_matches = 0
        for pattern_regex in pattern.patterns:
            if re.search(pattern_regex, text, re.IGNORECASE):
                pattern_matches += 1
        
        # Score based on pattern matches
        if pattern_matches > 0:
            score += 0.3 * (pattern_matches / len(pattern.patterns))
        
        # Check optional elements
        optional_found = 0
        for element in pattern.optional_elements:
            if re.search(element, text, re.IGNORECASE):
                optional_found += 1
        
        # Bonus for optional elements
        if pattern.optional_elements:
            score += 0.1 * (optional_found / len(pattern.optional_elements))
        
        return min(score * pattern.confidence, 1.0)
    
    def _detect_generic_type(self, text: str) -> Tuple[str, float, Dict[str, any]]:
        """Fallback generic document type detection"""
        
        # Look for common document indicators
        if re.search(r"agreement|contract", text):
            return "legal_agreement", 0.7, {"type": "generic_legal"}
        elif re.search(r"certificate", text):
            return "certificate", 0.7, {"type": "generic_certificate"}
        elif re.search(r"invoice|bill|payment", text):
            return "financial_document", 0.7, {"type": "generic_financial"}
        elif re.search(r"report|summary|analysis", text):
            return "report", 0.7, {"type": "generic_report"}
        elif re.search(r"letter|correspondence", text):
            return "letter", 0.7, {"type": "generic_correspondence"}
        elif re.search(r"form|application", text):
            return "form", 0.7, {"type": "generic_form"}
        else:
            return "unknown_document", 0.5, {"type": "unclassified"}
    
    def _analyze_confidence_factors(self, text: str, pattern: DocumentTypePattern) -> Dict[str, any]:
        """Analyze factors that contribute to confidence in document type detection"""
        factors = {
            "document_structure": self._analyze_structure(text),
            "key_phrases": self._find_key_phrases(text, pattern),
            "completeness": self._assess_completeness(text)
        }
        return factors
    
    def _analyze_structure(self, text: str) -> Dict[str, any]:
        """Analyze the structural elements of the document"""
        lines = text.split('\n')
        return {
            "line_count": len(lines),
            "has_headers": bool(re.search(r'^[A-Z\s]{10,}$', text, re.MULTILINE)),
            "has_dates": bool(re.search(r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}', text)),
            "has_numbers": bool(re.search(r'\b\d{5,}\b', text))
        }
    
    def _find_key_phrases(self, text: str, pattern: DocumentTypePattern) -> List[str]:
        """Find key phrases that indicate the document type"""
        found_phrases = []
        for phrase in pattern.patterns + pattern.required_elements + pattern.optional_elements:
            matches = re.findall(phrase, text, re.IGNORECASE)
            found_phrases.extend(matches)
        return found_phrases[:5]  # Return top 5 matches
    
    def _assess_completeness(self, text: str) -> Dict[str, any]:
        """Assess how complete the document appears to be"""
        return {
            "text_length": len(text),
            "appears_complete": len(text) > 200,  # Basic heuristic
            "has_signature_area": bool(re.search(r'signature|signed|seal', text, re.IGNORECASE))
        }
    
    def get_extraction_strategy(self, document_type: str) -> Dict[str, any]:
        """
        Get extraction strategy recommendations based on document type.
        
        This helps the LLM focus on the most relevant fields for each document type.
        """
        strategies = {
            # Identity Documents
            "international_passport": {
                "focus_fields": ["surname", "given_names", "nationality", "document_number", "date_of_birth", "date_of_expiry"],
                "extra_field_patterns": ["mrz_lines", "passport_type", "issuing_authority"],
                "extraction_priority": "personal_info"
            },
            "national_id_card": {
                "focus_fields": ["full_name", "document_number", "date_of_birth", "nin"],
                "extra_field_patterns": ["id_card_type", "state_of_origin"],
                "extraction_priority": "personal_info"
            },
            "drivers_license": {
                "focus_fields": ["full_name", "document_number", "date_of_birth", "date_of_expiry"],
                "extra_field_patterns": ["license_class", "vehicle_categories", "restrictions"],
                "extraction_priority": "personal_info"
            },
            
            # Legal Documents
            "land_use_restriction_agreement": {
                "focus_fields": ["date_of_issue"],
                "extra_field_patterns": ["grantor_name", "grantee_name", "property_location", "restrictions", "duration", "effective_date"],
                "extraction_priority": "legal_content"
            },
            "contract": {
                "focus_fields": ["date_of_issue"],
                "extra_field_patterns": ["party_1", "party_2", "contract_terms", "duration", "effective_date", "termination_date"],
                "extraction_priority": "legal_content"
            },
            
            # Default strategy for unknown documents
            "default": {
                "focus_fields": ["document_type", "date_of_issue"],
                "extra_field_patterns": ["all_meaningful_content"],
                "extraction_priority": "comprehensive"
            }
        }
        
        return strategies.get(document_type, strategies["default"])
