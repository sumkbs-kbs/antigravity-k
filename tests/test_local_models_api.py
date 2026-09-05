"""Tests for Local Models Discovery and List API.
=================================================
Verifies that GET /api/models/local returns only models present on the PC,
with accurate metadata and sensible recommended default.
"""

from fastapi.testclient import TestClient

from antigravity_k.api.server import app

client = TestClient(app)


def test_list_local_models():
    """GET /api/models/local must return ok and only local models."""
    res = client.get("/api/models/local")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("ok") is True
    assert "models" in data
    assert "total" in data
    assert data["total"] == len(data["models"])

    for model in data["models"]:
        assert model.get("is_local") is True
        assert "id" in model
        assert "provider" in model
        assert "status" in model
        assert model["status"] in ("running", "installed", "cached")
        assert "disk_size_gb" in model

    # Verify phantom models from config.yaml that are not on PC are NOT returned
    model_ids = {m["id"] for m in data["models"]}
    assert "lmstudio/qwen3.6" not in model_ids, "LM Studio is not running; should not be returned"

    # If there are local models, recommended_default should be one of them
    if data["total"] > 0:
        rec = data.get("recommended_default")
        assert rec is not None
        assert any(m["id"] == rec for m in data["models"])


def test_list_local_models_refresh():
    """GET /api/models/local?refresh=true triggers a fresh discovery."""
    res = client.get("/api/models/local?refresh=true")
    assert res.status_code == 200, res.text
    assert res.json().get("ok") is True


def test_load_local_model():
    """POST /api/models/load successfully prepares and loads a local model."""
    # First get local models to find a real one on this PC
    list_res = client.get("/api/models/local")
    data = list_res.json()
    assert data.get("ok") is True

    if data.get("models"):
        target_model = data["models"][0]["id"]
        load_res = client.post("/api/models/load", json={"model": target_model})
        assert load_res.status_code == 200, load_res.text
        load_data = load_res.json()
        assert load_data.get("ok") is True
        assert load_data.get("model") == target_model
        assert load_data.get("status") == "running"

    # Test invalid model returns 404
    bad_res = client.post("/api/models/load", json={"model": "non_existent_fake_model_xyz"})
    assert bad_res.status_code == 404
