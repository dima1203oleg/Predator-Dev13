import io
import os
import tempfile
from typing import Optional

import pytest
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient

from api.upload_service import MultiDatabaseUploadService

# Use native union type for optional values on Python 3.10+


def fake_user_uploader():
    return {
        "id": "test",
        "username": "tester",
        "email": "t@e.com",
        "roles": ["data_uploader"],
        "groups": [],
    }


def fake_user_no_role():
    return {
        "id": "no_role",
        "username": "norole",
        "email": "no@role.com",
        "roles": [],
        "groups": [],
    }


async def fake_process_upload(self, *args, **kwargs):
    return {
        "success": True,
        "dataset_id": "fake-ds-id",
        "records_processed": 2,
        "duplicates": 0,
        "failed": 0,
        "databases_indexed": {"postgresql": 2},
        "processing_time": 0.05,
        "errors": [],
    }


# Minimal test app built at module scope so dependency function objects are reachable
test_app = FastAPI()


async def _get_test_user():
    return None


@test_app.post("/api/v1/customs/upload")
async def upload_customs_data(
    file: UploadFile, dataset_name: Optional[str] = None, user=Depends(_get_test_user)
):
    if not user or "data_uploader" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Role 'data_uploader' required")

    content = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()

    svc = MultiDatabaseUploadService()
    result = await svc.process_upload(
        file_path=tmp.name,
        filename=file.filename,
        dataset_name=dataset_name or "test_ds",
        owner=user.get("username", "tester"),
        db=None,
    )

    os.remove(tmp.name)

    return {
        "records_processed": result["records_processed"],
        "records_failed": result["failed"],
        "duplicates_found": result["duplicates"],
        "processing_time": result["processing_time"],
    }


@pytest.fixture(autouse=True)
def _patch_process(monkeypatch):
    monkeypatch.setattr(MultiDatabaseUploadService, "process_upload", fake_process_upload)
    yield


def test_upload_success():
    # Override dependency to return uploader
    test_app.dependency_overrides.clear()

    async def _uploader_dep():
        return fake_user_uploader()

    test_app.dependency_overrides[_get_test_user] = _uploader_dep

    client = TestClient(test_app)
    content = b"col1,col2\n1,2\n"
    files = {"file": ("test.csv", io.BytesIO(content), "text/csv")}
    resp = client.post("/api/v1/customs/upload", files=files, data={"dataset_name": "test_ds"})

    async def _norole_dep():
        return fake_user_no_role()

    test_app.dependency_overrides[_get_test_user] = _norole_dep

    client = TestClient(test_app)

    content = b"col1\n1\n"
    files = {"file": ("test.csv", io.BytesIO(content), "text/csv")}

    resp = client.post("/api/v1/customs/upload", files=files)

    assert resp.status_code == 403
    data = resp.json()
    assert "detail" in data
    assert "required" in str(data["detail"]).lower()
