# Day 2 Checklist: Vision LLM Fallback + Structured Output

## Setup and Environment

- [ ] Update your .env file with your OpenRouter API key:
  ```bash
  # Open the .env file
  nano .env
  
  # Update the OPENROUTER_API_KEY value
  OPENROUTER_API_KEY=your-actual-api-key-here
  ```

- [ ] Install any additional dependencies:
  ```bash
  pip install pydantic-ai requests
  ```

## Implementation Tasks

- [ ] Test the structured data extraction:
  ```bash
  # Start the FastAPI server if it's not already running
  uvicorn app.main:app --reload
  ```

- [ ] Access the API documentation at http://localhost:8000/docs and test:
  - [ ] Upload a document with structured=false (default)
  - [ ] Upload a document with structured=true to test LLM extraction
  - [ ] Use the /api/analyze endpoint for direct structured extraction

- [ ] Test document uploads with different types of identity documents:
  - [ ] Test with passport
  - [ ] Test with national ID card
  - [ ] Test with driver's license

- [ ] Verify LLM fallback:
  - [ ] Test with a document that has poor OCR quality to ensure LLM fallback works
  - [ ] Check the extraction_method field to verify if it used "OCR", "LLM", or "OCR+LLM"

## Optimization Tasks

- [ ] Fine-tune the Pydantic AI configuration if needed:
  - [ ] Adjust the system instructions in llm_extractor.py for better results
  - [ ] Try different models available through OpenRouter (check the [model list](https://openrouter.ai/models))
  - [ ] Experiment with different vision models like:
    - [ ] anthropic/claude-3-opus:beta (highest quality)
    - [ ] anthropic/claude-3-sonnet:beta (balanced)
    - [ ] google/gemini-1.5-pro (alternative provider)
  - [ ] Customize the DocumentExtractorTrait for better extraction

- [ ] Improve DocumentData model:
  - [ ] Add any additional fields needed for your specific document types
  - [ ] Enhance validation or normalization of fields
  - [ ] Customize the field validators for better data standardization

## Troubleshooting

- If OpenRouter API calls fail:
  - Verify your API key is correct
  - Check if you have sufficient credits/quota
  - Check that your chosen model supports vision capabilities
  - Look for error messages in the console

- If document extraction gives poor results:
  - Try adjusting the prompts for better guidance to the LLM
  - Use higher quality images if possible

## Next Steps (After Day 2)

- [ ] Review structured data quality
- [ ] Plan for caching implementation (Day 3)
- [ ] Design validation endpoints for comparing extracted data with user input
