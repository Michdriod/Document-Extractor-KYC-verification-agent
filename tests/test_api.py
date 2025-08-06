# import pytest
# from fastapi.testclient import TestClient
# from app.main import app

# client = TestClient(app)

# def test_read_main():
#     """Test that the main route returns a 200 status code"""
#     response = client.get("/")
#     assert response.status_code == 200
#     assert "Document Extractor" in response.text

# def test_api_extract_invalid_file():
#     """Test that the API rejects unsupported file types"""
#     # Create a text file
#     file_content = b"This is a test file"
#     response = client.post(
#         "/api/extract",
#         files={"file": ("test.txt", file_content, "text/plain")},
#     )
#     assert response.status_code == 400
#     assert "Unsupported file format" in response.json()["detail"]






import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Document Extractor" in response.text
    
def test_api_extract_invalid_file():
    
    # create a text file 
    file_content = b"This is a test file"
    response = client.post(
        "/api/extract",
        files={"file": ("test.txt", file_content, "text/plain")},
    )
    assert response.status_code==400
    assert "Unsupported file format" in response.json()["detail"]