#!/usr/bin/env python3
"""
Test the improved logic with Land Use Agreement text
"""
import re

def test_is_single_document():
    """Test the logic with the Land Use Agreement"""
    
    # Sample text similar to what the user provided
    ocr_text = """LAND USE RESTRICTION AGREEMENT
This Land Use Restriction Agreement (the " Agreement") is effective on August 7, 2025.
BETWEEN:
[JOHN DOE], (the "Grantor") an individual with their main address located at 123 Elm
Street, Maple Town, Ontario, Canada.
AND:
[JANE SMITH], (the "Grantee") an individual with their main address located at 456 Oak
Avenue, River City, British Columbia, Canada.
WHEREAS, the Grantor is the owner of a certain parcel of land located at 789 Pine Road,
Maple Town, Ontario (the "Land") and desires to impose restrictions on the use of the Land;
NOW, THEREFORE, THE PARTIES AGREE AS FOLLOWS:
1. PURPOSE
1.1. The purpose of this Agreement is to impose restrictions on the use of the Land located
at 789 Pine Road, Maple Town, Ontario.
1.2. The Grantor hereby covenants and represents that they are the owner of the Land and
have the right to impose restrictions on its use.
2. RESTRICTIONS
2.1. The Grantor hereby restricts the use of the Land as follows:
• The Land shall not be used for any commercial or industrial purposes.
• No structure taller than two stories may be erected.
• No removal of trees without prior written consent.
3. DURATION OF THE RESTRICTIONS
3.1. The restrictions set forth in this Agreement shall run with the Land and shall be binding
on the Grantor, the Grantee, and their respective heirs, executors, administrators, assigns,
and successors, in interest. The restriction shall continue in full force and shall be effective
for 25 years from the date of this Agreement.
Land Use Restriction Agreement Page 1 of 4"""

    print(f"Testing text length: {len(ocr_text)} characters")
    
    # Test the header detection logic
    lines = ocr_text.split('\n')
    document_header_patterns = [
        r'^\s*passport\s*$',
        r'^\s*driver.*license\s*$', 
        r'^\s*national.*id\s*$',
        r'^\s*voter.*card\s*$',
        r'^\s*birth.*certificate\s*$',
        r'^\s*land.*use.*agreement\s*$',
        r'^\s*contract\s*$',
        r'^\s*certificate\s*$'
    ]
    
    header_count = 0
    found_headers = []
    unique_headers = set()
    
    for line in lines:
        line_clean = line.strip().lower()
        print(f"Checking line: '{line_clean}'")  # Debug output
        for pattern in document_header_patterns:
            if re.match(pattern, line_clean):
                header_count += 1
                found_headers.append(line.strip())
                unique_headers.add(line_clean)
                print(f"✅ MATCHED pattern '{pattern}': '{line.strip()}'")
                break
    
    print(f"Total headers found: {header_count}")
    print(f"Unique headers: {len(unique_headers)}")
    print(f"Headers: {found_headers}")
    
    # Test the new logic
    is_single = True
    
    if header_count > 2:
        print(f"Multiple headers ({header_count}) - checking if they're different types...")
        if len(unique_headers) > 1:
            print(f"Multiple different document types: {unique_headers}")
            is_single = False
        else:
            print(f"Same document type repeated - treating as single document")
    
    print(f"Final result: {'Single' if is_single else 'Multiple'} document")
    return is_single

if __name__ == "__main__":
    test_is_single_document()
