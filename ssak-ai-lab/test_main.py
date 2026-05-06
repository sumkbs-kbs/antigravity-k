from fastapi.testclient import TestClient
from main import app

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
