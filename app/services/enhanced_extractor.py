"""High-level document extraction orchestrator that uses OCR and LLMs to produce structured documents."""

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

from app.models.document_data import DocumentData, FieldWithConfidence
from app.services.llm_extractor import (
    VisionLLMExtractor, OCRStructurer, get_relevant_fields,
    validate_extracted_fields, _is_sufficient_data, split_text_by_document,
    UNIVERSAL_EXTRACTION_GUIDELINES
)
from app.services.address_extractor import enhance_extracted_data
from app.services.field_extractor import enrich_document_data
from app.services.semantic_field_extractor import enrich_with_semantic_fields

# Load environment variables from .env file
load_dotenv()

# Get environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

class DocumentExtractor:
    """Enhanced document extraction with support for multiple documents and structured output"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API credentials"""
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("API key is required. Set environment variable or pass it to the constructor.")
        
        # Initialize Groq client
        self.client = Groq(api_key=self.api_key)

    async def extract_data_with_fallback(
        self,
        image_bytes: bytes, 
        ocr_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract document data with intelligent fallback between OCR+LLM and Vision LLM.
        Handles both single and multiple documents intelligently and returns a standardized
        response format with documents array and metadata.
        
        Args:
            image_bytes: Binary content of the image
            ocr_results: Initial OCR results from PaddleOCR
            
        Returns:
            Dict with standardized response format containing:
            - documents: Array of extracted document data
            - metadata: Processing information
        """
        # Extract raw OCR text
        ocr_texts = [item["text"] for item in ocr_results]
        full_text = "\n".join(ocr_texts)
        
        print(f"🔍 Processing document extraction - OCR text length: {len(full_text)} characters")
        print(f"📝 Raw OCR text preview: {full_text[:200]}...")
        
        # Determine document handling strategy
        text_segments = split_text_by_document(full_text)
        print(f"📄 Document analysis complete: {len(text_segments)} segment(s) detected")
        
        # Initialize response structure
        response = {
            "documents": [],
            "metadata": {
                "total_documents": len(text_segments),
                "successful_extractions": 0,
                "failed_extractions": 0,
                "extraction_methods": [],
                "processing_time_ms": 0  # This would be filled in by the API endpoint
            }
        }
        
        # Process each segment
        for i, segment in enumerate(text_segments):
            print(f"\n🔄 Processing document {i+1}/{len(text_segments)}...")
            print(f"📄 Segment preview: {segment[:150]}...")
            
            document_result = {
                "document_id": f"doc_{i+1}",
                "extraction_status": "failed",
                "extraction_method": None,
                "confidence_score": None,
                "document_type": None,
                "data": None
            }
            
            try:
                # STEP 1: Try OCR+LLM extraction
                print(f"   🔄 Attempting OCR+LLM extraction...")
                ocr_structurer = OCRStructurer()
                
                # Create OCR result for this segment
                segment_ocr_result = [{"text": segment, "confidence": 0.8}]
                ocr_structured_data = await ocr_structurer.structure_ocr_results(segment_ocr_result)
                
                # STEP 2: Enhance the data with address extraction
                ocr_structured_data = enhance_extracted_data(ocr_structured_data, segment)
                
                # STEP 3: Validate the extraction quality
                if _is_sufficient_data(ocr_structured_data):
                    print(f"   ✅ OCR+LLM extraction successful! Document type: {ocr_structured_data.document_type.value}")
                    
                    # Get relevant fields and validate against OCR text
                    relevant_fields = get_relevant_fields(ocr_structured_data)
                    validated_fields = validate_extracted_fields(relevant_fields, segment)
                    
                    # Enrich fields with additional non-standard fields
                    validated_fields = enrich_document_data(validated_fields, segment)
                    
                    # Further enrich with semantic field analysis
                    validated_fields = await enrich_with_semantic_fields(
                        validated_fields, 
                        ocr_structured_data.document_type.value if ocr_structured_data.document_type else "Unknown",
                        segment
                    )
                    
                    # Remove page_number if present
                    validated_fields.pop('page_number', None)
                    
                    # Update document result
                    document_result["extraction_status"] = "success"
                    document_result["extraction_method"] = "OCR+LLM"
                    document_result["confidence_score"] = ocr_structured_data.confidence_score or 0.8
                    document_result["document_type"] = ocr_structured_data.document_type.value if ocr_structured_data.document_type else "Unknown"
                    document_result["data"] = validated_fields
                    
                    print(f"   📊 Document {i+1} processed successfully with {len(validated_fields)} fields")
                    
                else:
                    print(f"   ⚠️ OCR+LLM output insufficient. Trying Vision LLM fallback...")
                    
                    # STEP 3: Fallback to Vision LLM
                    try:
                        print(f"   🔄 Attempting Vision LLM extraction...")
                        vision_extractor = VisionLLMExtractor()
                        vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
                        
                        print(f"   ✅ Vision LLM extraction successful! Document type: {vision_structured_data.document_type.value}")
                        
                        # Enhance the data with address extraction
                        vision_structured_data = enhance_extracted_data(vision_structured_data, segment)
                        
                        # Get relevant fields and validate against OCR text
                        relevant_fields = get_relevant_fields(vision_structured_data)
                        validated_fields = validate_extracted_fields(relevant_fields, segment)
                        
                        # Enrich fields with additional non-standard fields
                        validated_fields = enrich_document_data(validated_fields, segment)
                        
                        # Further enrich with semantic field analysis
                        validated_fields = await enrich_with_semantic_fields(
                            validated_fields, 
                            vision_structured_data.document_type.value if vision_structured_data.document_type else "Unknown",
                            segment
                        )
                        
                        # Remove page_number if present
                        validated_fields.pop('page_number', None)
                        
                        # Update document result
                        document_result["extraction_status"] = "success"
                        document_result["extraction_method"] = "Vision LLM"
                        document_result["confidence_score"] = vision_structured_data.confidence_score or 0.7
                        document_result["document_type"] = vision_structured_data.document_type.value if vision_structured_data.document_type else "Unknown"
                        document_result["data"] = validated_fields
                        
                        print(f"   📊 Document {i+1} processed successfully (Vision) with {len(validated_fields)} fields")
                        
                    except Exception as e:
                        print(f"   ❌ Vision LLM failed: {str(e)}")
                        document_result["extraction_status"] = "failed"
                        document_result["error"] = f"Both extraction methods failed: {str(e)}"
                        response["metadata"]["failed_extractions"] += 1
                        
            except Exception as e:
                print(f"   ❌ OCR+LLM extraction failed: {str(e)}")
                
                # Final fallback to Vision LLM
                try:
                    print(f"   🔄 Final fallback to Vision LLM...")
                    vision_extractor = VisionLLMExtractor()
                    vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
                    
                    print(f"   ✅ Vision LLM extraction successful! Document type: {vision_structured_data.document_type.value}")
                    
                    # Enhance the data with address extraction
                    vision_structured_data = enhance_extracted_data(vision_structured_data, segment)
                    
                    # Get relevant fields and validate against OCR text
                    relevant_fields = get_relevant_fields(vision_structured_data)
                    validated_fields = validate_extracted_fields(relevant_fields, segment)
                    
                    # Enrich fields with additional non-standard fields
                    validated_fields = enrich_document_data(validated_fields, segment)
                    
                    # Further enrich with semantic field analysis
                    validated_fields = await enrich_with_semantic_fields(
                        validated_fields, 
                        vision_structured_data.document_type.value if vision_structured_data.document_type else "Unknown",
                        segment
                    )
                    
                    # Remove page_number if present
                    validated_fields.pop('page_number', None)
                    
                    # Update document result
                    document_result["extraction_status"] = "success"
                    document_result["extraction_method"] = "Vision LLM (fallback)"
                    document_result["confidence_score"] = vision_structured_data.confidence_score or 0.6
                    document_result["document_type"] = vision_structured_data.document_type.value if vision_structured_data.document_type else "Unknown"
                    document_result["data"] = validated_fields
                    
                    print(f"   📊 Document {i+1} processed successfully (Final Vision) with {len(validated_fields)} fields")
                    
                except Exception as e2:
                    print(f"   ❌ All extraction methods failed for document {i+1}: {str(e2)}")
                    document_result["extraction_status"] = "failed"
                    document_result["error"] = f"All extraction methods failed: {str(e2)}"
                    response["metadata"]["failed_extractions"] += 1
            
            # Add document result to response
            if document_result["extraction_status"] == "success":
                response["metadata"]["successful_extractions"] += 1
                if document_result["extraction_method"] not in response["metadata"]["extraction_methods"]:
                    response["metadata"]["extraction_methods"].append(document_result["extraction_method"])
            
            response["documents"].append(document_result)
        
        # Handle case where no documents were successfully extracted
        if not response["documents"] or response["metadata"]["successful_extractions"] == 0:
            print("⚠️ No documents successfully extracted. Attempting full-text extraction as last resort...")
            try:
                # Clear existing documents if all failed
                response["documents"] = []
                response["metadata"]["failed_extractions"] = 0
                
                ocr_structurer = OCRStructurer()
                ocr_structured_data = await ocr_structurer.structure_ocr_results(ocr_results)
                
                # Enhance the data with address extraction
                ocr_structured_data = enhance_extracted_data(ocr_structured_data, full_text)
                
                if _is_sufficient_data(ocr_structured_data):
                    relevant_fields = get_relevant_fields(ocr_structured_data)
                    validated_fields = validate_extracted_fields(relevant_fields, full_text)
                    
                    # Enrich fields with additional non-standard fields
                    validated_fields = enrich_document_data(validated_fields, full_text)
                    
                    # Further enrich with semantic field analysis
                    validated_fields = await enrich_with_semantic_fields(
                        validated_fields, 
                        ocr_structured_data.document_type.value if ocr_structured_data.document_type else "Unknown",
                        full_text
                    )
                    
                    validated_fields.pop('page_number', None)
                    
                    document_result = {
                        "document_id": "doc_1",
                        "extraction_status": "success",
                        "extraction_method": "OCR+LLM (last resort)",
                        "confidence_score": ocr_structured_data.confidence_score or 0.5,
                        "document_type": ocr_structured_data.document_type.value if ocr_structured_data.document_type else "Unknown",
                        "data": validated_fields
                    }
                    
                    response["documents"].append(document_result)
                    response["metadata"]["successful_extractions"] = 1
                    response["metadata"]["failed_extractions"] = 0
                    response["metadata"]["extraction_methods"] = ["OCR+LLM (last resort)"]
                    print("✅ Last resort extraction successful")
                else:
                    # Final Vision LLM attempt
                    vision_extractor = VisionLLMExtractor()
                    vision_structured_data = await vision_extractor.extract_from_image(image_bytes)
                    
                    # Enhance the data with address extraction
                    vision_structured_data = enhance_extracted_data(vision_structured_data, full_text)
                    
                    relevant_fields = get_relevant_fields(vision_structured_data)
                    validated_fields = validate_extracted_fields(relevant_fields, full_text)
                    
                    # Enrich fields with additional non-standard fields
                    validated_fields = enrich_document_data(validated_fields, full_text)
                    
                    # Further enrich with semantic field analysis
                    validated_fields = await enrich_with_semantic_fields(
                        validated_fields, 
                        vision_structured_data.document_type.value if vision_structured_data.document_type else "Unknown",
                        full_text
                    )
                    
                    validated_fields.pop('page_number', None)
                    
                    document_result = {
                        "document_id": "doc_1",
                        "extraction_status": "success",
                        "extraction_method": "Vision LLM (last resort)",
                        "confidence_score": vision_structured_data.confidence_score or 0.4,
                        "document_type": vision_structured_data.document_type.value if vision_structured_data.document_type else "Unknown",
                        "data": validated_fields
                    }
                    
                    response["documents"].append(document_result)
                    response["metadata"]["successful_extractions"] = 1
                    response["metadata"]["failed_extractions"] = 0
                    response["metadata"]["extraction_methods"] = ["Vision LLM (last resort)"]
                    print("✅ Last resort Vision extraction successful")
                
            except Exception as e:
                print(f"❌ All extraction methods failed completely: {str(e)}")
                response["metadata"]["error"] = f"Complete extraction failure: {str(e)}"
                
        # Update metadata with final counts
        response["metadata"]["total_documents"] = len(response["documents"])
        
        # Final summary
        print(f"\n✅ Extraction complete: {response['metadata']['successful_extractions']} of {response['metadata']['total_documents']} document(s) processed successfully")
        print(f"   📊 Methods used: {response['metadata']['extraction_methods']}")
        
        return response

# Compatibility function for backward compatibility
async def extract_document_data_legacy(
    image_bytes: bytes, 
    ocr_results: List[Dict[str, Any]]
) -> DocumentData:
    """
    Simple extraction function that returns only the first DocumentData object
    (for backward compatibility)
    
    Args:
        image_bytes: Binary content of the image
        ocr_results: Initial OCR results from PaddleOCR
        
    Returns:
        DocumentData object with structured information (first document if multiple found)
    """
    extractor = DocumentExtractor()
    result = await extractor.extract_data_with_fallback(image_bytes, ocr_results)
    
    # Get first successful document
    for doc in result["documents"]:
        if doc["extraction_status"] == "success" and doc["data"]:
            # Convert back to DocumentData format
            doc_data = doc["data"]
            if isinstance(doc_data, dict):
                # Create DocumentData from the dictionary
                return DocumentData.model_validate(doc_data)
    
    # If no successful extractions, return None
    return None
