#!/usr/bin/env python3
"""
Test the enhanced document extraction system with multi-document support
and the new standardized output format.
"""

import sys
import os
import asyncio
import json
import argparse
from pprint import pprint

from app.services.enhanced_extractor import DocumentExtractor
from app.services.document_processor import ocr
from app.services.llm_extractor import get_image_bytes_from_input, OCRStructurer

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
123 Elm

Confidence: 94%
Street, Maple Town, Ontario, L2K 5M7, Canada.

Confidence: 99%
AND:

Confidence: 99%
[JANE SMITH], (the "Grantee") an individual with their main address located

Confidence: 98%
at 456 Oak Avenue, River City, British Columbia, V6B 3K9, Canada

Confidence: 98%
Phone: +1 (555) 123-4567
Email: jane.smith@example.com

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

async def test_legacy_extraction():
    """Test the original extraction method."""
    print("\n🤖 Testing Legacy Document Extraction...")
    
    # Create OCR results in the expected format
    ocr_results = [{"text": LAND_USE_OCR_TEXT, "confidence": 0.95}]
    
    try:
        # Initialize the OCR structurer
        structurer = OCRStructurer()
        
        # Extract data using the enhanced system
        document_data = await structurer.structure_ocr_results(ocr_results)
        
        # Convert to dictionary for display
        result_dict = document_data.model_dump()
        
        print("✅ Legacy extraction completed successfully!")
        print(f"📄 Document Type: {result_dict.get('document_type', {}).get('value', 'Unknown')}")
        print(f"🔧 Extraction Method: {result_dict.get('extraction_method', {}).get('value', 'Unknown')}")
        
        return document_data
        
    except Exception as e:
        print(f"❌ Error during legacy extraction: {str(e)}")
        raise

async def test_enhanced_document_extractor():
    """Test the new DocumentExtractor with the standardized output format."""
    print("\n🚀 Testing Enhanced Document Extractor (New Format)...")
    
    # Create OCR results in the expected format
    ocr_results = [{"text": LAND_USE_OCR_TEXT, "confidence": 0.95}]
    
    try:
        # Initialize the new document extractor
        document_extractor = DocumentExtractor()
        
        # Extract data using the new enhanced extractor
        result = await document_extractor.extract_data_with_fallback(b'dummy_image', ocr_results)
        
        print("✅ Enhanced extraction completed successfully!")
        print(f"📊 Documents found: {result['metadata']['total_documents']}")
        print(f"📊 Successful extractions: {result['metadata']['successful_extractions']}")
        print(f"📊 Methods used: {result['metadata']['extraction_methods']}")
        
        # Display information about each document
        for i, doc in enumerate(result['documents']):
            print(f"\n📄 Document {i+1}:")
            print(f"  • ID: {doc['document_id']}")
            print(f"  • Status: {doc['extraction_status']}")
            print(f"  • Type: {doc['document_type']}")
            print(f"  • Method: {doc['extraction_method']}")
            print(f"  • Confidence: {doc['confidence_score']}")
            
            # Show fields if available
            if doc['data']:
                standard_fields = [k for k in doc['data'].keys() if k != 'extra_fields']
                extra_fields = list(doc['data'].get('extra_fields', {}).keys()) if doc['data'].get('extra_fields') else []
                
                print(f"  • Standard fields: {len(standard_fields)}")
                print(f"  • Extra fields: {len(extra_fields)}")
                
                # Check specifically for address information
                print("\n  📍 ADDRESS INFORMATION EXTRACTED:")
                address_fields = ['address', 'secondary_address', 'phone_number', 'email', 'state_province', 'jurisdiction']
                for field in address_fields:
                    if field in doc['data'] and doc['data'][field]:
                        value = doc['data'][field]['value'] if isinstance(doc['data'][field], dict) and 'value' in doc['data'][field] else doc['data'][field]
                        print(f"    - {field}: {value}")
                
                if extra_fields:
                    print(f"\n  📋 EXTRA FIELDS:")
                    for field in extra_fields[:5]:  # Show first 5 extra fields
                        value = doc['data']['extra_fields'][field].get('value', 'N/A') if isinstance(doc['data']['extra_fields'][field], dict) else doc['data']['extra_fields'][field]
                        print(f"    - {field}: {value}")
                    
                    if len(extra_fields) > 5:
                        print(f"    - ... and {len(extra_fields) - 5} more")
        
        # Save results to file
        with open("enhanced_extraction_result.json", "w") as f:
            json.dump(result, f, indent=2)
        print("\n✅ Results saved to enhanced_extraction_result.json")
        
        return result
        
    except Exception as e:
        print(f"❌ Error during enhanced extraction: {str(e)}")
        raise

async def test_with_file(file_path):
    """
    Test the enhanced extraction functionality with a local file
    
    Args:
        file_path: Path to the local test file
    """
    try:
        print(f"📄 Testing enhanced extraction with file: {file_path}")
        
        # Get image bytes
        image_bytes = get_image_bytes_from_input(file_path)
        print(f"✅ Successfully loaded image: {len(image_bytes)} bytes")
        
        # Run OCR
        ocr_result = ocr.ocr(image_bytes, cls=True)
        
        # Format OCR results
        ocr_results = []
        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                bbox, (text, confidence) = line
                ocr_results.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": bbox
                })
        
        print(f"✅ OCR complete: {len(ocr_results)} text regions found")
        
        # Initialize document extractor and process
        document_extractor = DocumentExtractor()
        extraction_result = await document_extractor.extract_data_with_fallback(image_bytes, ocr_results)
        
        # Print results
        print("\n📊 EXTRACTION RESULTS:")
        print(f"Documents found: {extraction_result['metadata']['total_documents']}")
        print(f"Successful extractions: {extraction_result['metadata']['successful_extractions']}")
        print(f"Methods used: {extraction_result['metadata']['extraction_methods']}")
        
        # Print document details
        for i, doc in enumerate(extraction_result["documents"]):
            print(f"\n📄 DOCUMENT {i+1}:")
            print(f"  Status: {doc['extraction_status']}")
            if doc['extraction_status'] == 'success':
                print(f"  Type: {doc['document_type']}")
                print(f"  Method: {doc['extraction_method']}")
                print(f"  Confidence: {doc['confidence_score']}")
                
                # Print field summary
                if doc.get('data'):
                    standard_fields = [k for k in doc['data'].keys() if k != 'extra_fields']
                    extra_fields = list(doc['data'].get('extra_fields', {}).keys()) if doc['data'].get('extra_fields') else []
                    
                    print(f"  Standard fields: {len(standard_fields)}")
                    print(f"  Extra fields: {len(extra_fields)}")
                    
                    # Print some key fields if available
                    key_fields = ['document_type', 'document_number', 'full_name', 'surname', 'given_names', 'date_of_birth']
                    for field in key_fields:
                        if field in doc['data'] and doc['data'][field]:
                            value = doc['data'][field]['value'] if isinstance(doc['data'][field], dict) else doc['data'][field]
                            print(f"  {field}: {value}")
                    
                    # Check specifically for address information
                    print("\n  📍 ADDRESS INFORMATION EXTRACTED:")
                    address_fields = ['address', 'secondary_address', 'phone_number', 'email', 'state_province', 'jurisdiction']
                    found_addresses = False
                    for field in address_fields:
                        if field in doc['data'] and doc['data'][field]:
                            value = doc['data'][field]['value'] if isinstance(doc['data'][field], dict) and 'value' in doc['data'][field] else doc['data'][field]
                            print(f"    - {field}: {value}")
                            found_addresses = True
                    
                    if not found_addresses:
                        print("    (No address information extracted)")
        
        # Save results to a file
        output_file = "enhanced_extraction_results.json"
        with open(output_file, "w") as f:
            json.dump(extraction_result, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")
        
        return extraction_result
        
    except Exception as e:
        print(f"❌ Error during extraction: {str(e)}")
        raise e

async def main():
    """Run the comprehensive test with command line arguments."""
    parser = argparse.ArgumentParser(description="Test the enhanced document extraction system")
    parser.add_argument("--file", "-f", help="Path to a document file to process")
    parser.add_argument("--demo", "-d", action="store_true", help="Run the demo with sample text")
    args = parser.parse_args()
    
    print("🚀 Testing Enhanced Universal Document Extraction System\n")
    
    if args.file:
        # Test with actual file
        await test_with_file(args.file)
    elif args.demo or len(sys.argv) == 1:
        # Run demo with sample text
        await test_legacy_extraction()
        await test_enhanced_document_extractor()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
