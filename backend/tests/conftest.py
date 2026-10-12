import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import get_settings
from backend.app.storage import reset_store_for_tests
from backend.app.main import app

@pytest.fixture(autouse=True)
def isolated_store(monkeypatch,tmp_path):
    monkeypatch.setenv("STORAGE_MODE","local")
    monkeypatch.setenv("LOCAL_DATA_DIR",str(tmp_path/"data"))
    monkeypatch.setenv("SERVICENOW_MODE","mock")
    monkeypatch.setenv("AI_PROVIDER","offline")
    monkeypatch.setenv("EMBEDDING_MODE","offline")
    get_settings.cache_clear();reset_store_for_tests()
    yield
    get_settings.cache_clear();reset_store_for_tests()

@pytest.fixture
def client():
    with TestClient(app) as c:yield c
