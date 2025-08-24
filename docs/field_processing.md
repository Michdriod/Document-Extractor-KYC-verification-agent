# 🧠 Advanced Field Processing

> See [example JSON response](example_response.json) with categorized fields

## Semantic Field Categorization

The system now includes advanced semantic understanding capabilities to organize extracted fields into meaningful categories. This categorization helps users quickly understand the document data and locate important information.

Fields are automatically organized into the following categories:

| Category | Description | Example Fields |
|----------|-------------|----------------|
| Personal Information | Personal details about individuals | full_name, first_name, last_name, date_of_birth, gender |
| Identification | ID numbers and identification references | passport_number, identification_number, social_security_number |
| Contact Details | Ways to contact individuals | email, phone_number, mobile_number |
| Address Information | Location and address components | address_line1, city, state, zip_code, country |
| Financial Details | Money-related information | total_amount, payment_amount, fee_amount, price |
| Important Dates | Time-based information | issue_date, expiration_date, effective_date |
| Document Information | Details about the document itself | document_type, document_number, reference_number |
| Property Details | Information about properties | property_address, property_value, property_description |
| Involved Parties | People involved in transactions | grantor, grantee, buyer, seller, tenant |
| Legal Terms | Legal aspects and conditions | terms, conditions, restrictions, requirements |

### Field Name Normalization

To ensure consistency across different document types, the system performs intelligent field name normalization:

1. **Standardization**: Different variations of field names are standardized to a consistent format (e.g., "dob", "date_birth", "birth_date" → "date_of_birth")

2. **Abbreviation Expansion**: Common abbreviations are expanded to their full form:
   - "ssn" → "social_security_number"
   - "dl_num" → "drivers_license_number"
   - "fname" → "first_name"

3. **Contextual Enhancement**: Generic field names are enriched with context:
   - "name" → "full_name"
   - "number" → "reference_number"
   - "date" → "document_date"

4. **Format Consistency**: All field names use snake_case formatting with meaningful prefixes and suffixes

### Field Relationship Detection

The system identifies relationships between fields based on semantic patterns:

- Names that belong together (first_name, last_name)
- Address components (address, city, state)
- Date pairs (issue_date, expiration_date)
- Transaction parties (buyer, seller)

These relationships help in understanding the document structure and verifying data consistency.

### Primary Field Identification

For each category, the system automatically identifies the most important fields, making it easy to quickly access the most relevant information. Primary fields are selected based on:

1. Field name importance within the document type
2. Value quality and confidence score
3. Semantic relevance to document purpose
