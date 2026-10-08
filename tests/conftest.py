from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import files_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI test client with isolated upload storage."""
    monkeypatch.setattr("app.routes.UPLOAD_DIR", tmp_path)
    files_db.clear()
    with TestClient(app) as test_client:
        yield test_client
    files_db.clear()
