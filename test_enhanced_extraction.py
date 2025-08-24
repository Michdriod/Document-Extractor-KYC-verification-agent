#!/usr/bin/env python3
"""
Test the enhanced document extraction system with the Land Use Restriction Agreement example.
"""

import asyncio
import json
from app.services.llm_extractor import OCRStructurer
from app.services.document_type_detector import DocumentTypeDetector

# Sample Land Use Restriction Agreement OCR text from the user
LAND_USE_OCR_TEXT = """LAND USE RESTRICTION AGREEMENT

Confidence: 95%
This Land Use Restriction Agreement (the " Agreement") is effective on

Confidence: 99%
August 7, 2025.

Confidence: 99%
BETWEEN:

Confidence: 98%
[JOHN DOE], (the "Grantor") an individual with their main address located at

Confidence: 98%
123 EIm

Confidence: 94%
Street, Maple Town, Ontario, Canada.

Confidence: 99%
AND:

Confidence: 99%
[JANE SMITH], (the "Grantee") an individual with their main address located

Confidence: 98%
at 456 Oak Avenue, River City, British Columbia, Canada

Confidence: 96%
WHEREAS,the Grantor is the owner of a certain parcel of land located at 789

Confidence: 95%
Pine Road,Maple Town, Ontario (the "Land") and desires to impose

Confidence: 99%
restrictions on the use of the Land;

Confidence: 95%
NOW.THEREFORE,THE PARTIESAGREE AS FOLLOWS

Confidence: 94%
1.PURPOSE

Confidence: 99%
1.1. The purpose of this Agreement is to impose restrictions on the use of the

Confidence: 99%
Land located at 789 Pine Road,Maple Town,Ontario

Confidence: 95%
the Land and have the right to impose restrictions on its use.

Confidence: 99%
2.RESTRICTIONS

Confidence: 99%
2.1. The Grantor hereby restricts the use of the Land as follows:

Confidence: 99%
- The Land shall not be used for any commercial or industrial purposes.

Confidence: 98%
- No structure taller than two stories may be erected.

Confidence: 98%
No removal of trees without prior written consent.

Confidence: 96%
3. DURATION OE THE RESTRICTIONS

Confidence: 94%
3.1. The restrictions set forth in this Agreement shall run with the Land and

Confidence: 98%
shall be binding on the Grantor, the Grantee, and their respective heirs,

Confidence: 97%
executors, administrators, assigns,and successors, in interest. The restriction

Confidence: 95%
shall continue in full force and shall be effective for 25 years from the date of

Confidence: 96%
this Agreement."""

async def test_document_type_detection():
    """Test the document type detection functionality."""
    print("🔍 Testing Document Type Detection...")
    
    detector = DocumentTypeDetector()
    doc_type, confidence, analysis = detector.detect_document_type(LAND_USE_OCR_TEXT)
    
    print(f"📋 Detected Document Type: {doc_type}")
    print(f"🎯 Confidence: {confidence:.2f}")
    print(f"📊 Analysis: {json.dumps(analysis, indent=2)}")
    
    strategy = detector.get_extraction_strategy(doc_type)
    print(f"📝 Extraction Strategy: {json.dumps(strategy, indent=2)}")
    
    return doc_type, confidence, analysis

async def test_enhanced_extraction():
    """Test the enhanced extraction with dynamic prompts."""
    print("\n🤖 Testing Enhanced Document Extraction...")
    
    # Create OCR results in the expected format
    ocr_results = [{"text": LAND_USE_OCR_TEXT, "confidence": 0.95}]
    
    try:
        # Initialize the OCR structurer with enhanced features
        structurer = OCRStructurer()
        
        # Extract data using the enhanced system
        document_data = await structurer.structure_ocr_results(ocr_results)
        
        # Convert to dictionary for display
        result_dict = document_data.model_dump()
        
        print("✅ Extraction completed successfully!")
        print(f"📄 Document Type: {result_dict.get('document_type', {}).get('value', 'Unknown')}")
        print(f"🔧 Extraction Method: {result_dict.get('extraction_method', {}).get('value', 'Unknown')}")
        
        # Display core fields
        print("\n📊 Core Fields:")
        core_fields = ['document_type', 'date_of_issue', 'country']
        for field in core_fields:
            if field in result_dict and result_dict[field]:
                print(f"  • {field}: {result_dict[field].get('value', 'N/A')} (confidence: {result_dict[field].get('confidence', 'N/A')})")
        
        # Display extra fields (the key enhancement)
        print("\n🎯 Extra Fields (Document-Specific Content):")
        extra_fields = result_dict.get('extra_fields', {})
        if extra_fields:
            for field_name, field_data in extra_fields.items():
                if isinstance(field_data, dict) and 'value' in field_data:
                    value = field_data['value']
                    confidence = field_data.get('confidence', 'N/A')
                    
                    # Handle nested objects in value
                    if isinstance(value, dict):
                        print(f"  • {field_name} (confidence: {confidence}):")
                        for key, val in value.items():
                            print(f"    - {key}: {val}")
                    else:
                        print(f"  • {field_name}: {value} (confidence: {confidence})")
        else:
            print("  No extra fields found")
        
        # Show full JSON for reference
        print(f"\n📋 Full JSON Output:")
        print(json.dumps(result_dict, indent=2, ensure_ascii=False))
        
        return document_data
        
    except Exception as e:
        print(f"❌ Error during extraction: {str(e)}")
        raise

async def main():
    """Run the comprehensive test."""
    print("🚀 Testing Enhanced Universal Document Extraction System\n")
    
    # Test 1: Document Type Detection
    await test_document_type_detection()
    
    # Test 2: Enhanced Extraction
    await test_enhanced_extraction()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
