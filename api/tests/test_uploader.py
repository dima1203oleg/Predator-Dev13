import io

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_upload_excel_success(monkeypatch):
    # Mock DB write if needed
    # monkeypatch.setattr(...)
    file_content = b"col1,col2\n1,2\n3,4"
    response = client.post(
        "/datasets/upload",
        files={"file": ("test.xlsx", io.BytesIO(file_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    # Optionally check DB state

@pytest.mark.parametrize("file_content,expected_status", [
    (b"", 400),  # Empty file
    (b"not an excel", 400),  # Invalid format
])
def test_upload_excel_error(file_content, expected_status):
    response = client.post(
        "/datasets/upload",
        files={"file": ("bad.xlsx", io.BytesIO(file_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == expected_status
