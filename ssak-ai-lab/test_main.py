import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

_main_spec = importlib.util.spec_from_file_location("ssak_ai_lab_main", Path(__file__).with_name("main.py"))
assert _main_spec is not None and _main_spec.loader is not None
_main_module = importlib.util.module_from_spec(_main_spec)
_main_spec.loader.exec_module(_main_module)
app = _main_module.app

client = TestClient(app)


def test_create_article():
    response = client.post(
        "/api/knowledge/",
        json={"title": "Test Article", "content": "Test Content", "tags": ["test"]},
    )
    assert response.status_code == 200
    assert response.json() == {
        "title": "Test Article",
        "content": "Test Content",
        "tags": ["test"],
    }


def test_read_articles():
    response = client.get("/api/knowledge/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
