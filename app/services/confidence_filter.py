def filter_low_confidence_fields(data: dict, confidence_threshold: float = 0.6) -> dict:
    """
    Filter out fields with confidence below a threshold to reduce hallucinations.
    
    Args:
        data: The extracted document data
        confidence_threshold: Minimum confidence score to keep a field
        
    Returns:
        Filtered document data with low-confidence fields removed
    """
    # Function to check if a field meets confidence threshold
    def meets_threshold(field):
        if isinstance(field, dict) and 'confidence' in field:
            return field['confidence'] >= confidence_threshold
        return True  # Keep fields without confidence score
    
    # Function to recursively filter fields
    def filter_fields(obj):
        if isinstance(obj, dict):
            # Handle FieldWithConfidence objects
            if 'value' in obj and 'confidence' in obj:
                if obj['confidence'] < confidence_threshold:
                    return None
                return obj
            
            # Handle dictionaries (including extra_fields)
            filtered = {}
            for k, v in obj.items():
                filtered_value = filter_fields(v)
                if filtered_value is not None:
                    filtered[k] = filtered_value
            return filtered
        elif isinstance(obj, list):
            # Handle lists (like mrz_lines)
            filtered = [filter_fields(item) for item in obj]
            filtered = [item for item in filtered if item is not None]
            return filtered if filtered else None
        else:
            # Handle primitive values
            return obj
    
    # Filter all fields except special fields
    filtered_data = {}
    for key, value in data.items():
        if key == 'document_type' or key == 'extraction_method':
            # Always keep these fields
            filtered_data[key] = value
        elif key == 'extra_fields' and isinstance(value, dict):
            # Filter extra_fields
            filtered_extra = filter_fields(value)
            if filtered_extra and len(filtered_extra) > 0:
                filtered_data[key] = filtered_extra
        else:
            # Filter other fields
            filtered_value = filter_fields(value)
            if filtered_value is not None:
                filtered_data[key] = filtered_value
    
    return filtered_data
