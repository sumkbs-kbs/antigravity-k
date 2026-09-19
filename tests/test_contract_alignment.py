"""Frontend-Backend Contract Alignment Tests.
=============================================
Verifies that newly added desktop & workspace endpoints (/api/workspace/context,
/api/system/quota, /api/system/access-mode, /api/mcp/servers) match the exact
payload shapes and types expected by dashboard React frontend components.
"""

from fastapi.testclient import TestClient

from antigravity_k.api.server import app

client = TestClient(app)


def test_contract_workspace_context():
    """GET /api/workspace/context must return project_name, target, branch, projects."""
    response = client.get("/api/workspace/context")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    assert "project_name" in data and isinstance(data["project_name"], str)
    assert "target" in data and isinstance(data["target"], str)
    assert "branch" in data and isinstance(data["branch"], str)
    assert "projects" in data and isinstance(data["projects"], list)
    if data["projects"]:
        p = data["projects"][0]
        assert "name" in p and isinstance(p["name"], str)


def test_contract_system_quota():
    """GET /api/system/quota must return numeric percent_remaining and budget info."""
    response = client.get("/api/system/quota")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    assert "percent_remaining" in data and isinstance(data["percent_remaining"], (int, float))
    assert 0 <= data["percent_remaining"] <= 100
    assert "period_label" in data and isinstance(data["period_label"], str)
    assert "resets_note" in data and isinstance(data["resets_note"], str)
    assert "tokens_used" in data and isinstance(data["tokens_used"], int)
    assert "tokens_budget" in data and isinstance(data["tokens_budget"], int)
    assert data["tokens_budget"] > 0


def test_contract_access_mode_lifecycle():
    """GET and POST /api/system/access-mode roundtrip contract."""
    # 1. GET initial state
    res_get = client.get("/api/system/access-mode")
    assert res_get.status_code == 200, res_get.text
    data_get = res_get.json()
    assert "mode" in data_get and data_get["mode"] in ("full_access", "read_only")
    assert "label" in data_get and isinstance(data_get["label"], str)

    # 2. POST switch to read_only (restricted)
    res_post_ro = client.post("/api/system/access-mode", json={"mode": "restricted"})
    assert res_post_ro.status_code == 200, res_post_ro.text
    data_ro = res_post_ro.json()
    assert data_ro.get("ok") is True
    assert data_ro.get("mode") == "read_only"

    # 3. Verify via GET
    res_verify = client.get("/api/system/access-mode")
    assert res_verify.json().get("mode") == "read_only"

    # 4. POST switch back to full_access
    res_post_fa = client.post("/api/system/access-mode", json={"mode": "full_access"})
    assert res_post_fa.status_code == 200, res_post_fa.text
    data_fa = res_post_fa.json()
    assert data_fa.get("ok") is True
    assert data_fa.get("mode") == "full_access"

    # 5. POST invalid mode should return 400
    res_invalid = client.post("/api/system/access-mode", json={"mode": "super_admin"})
    assert res_invalid.status_code == 400


def test_contract_mcp_servers():
    """GET /api/mcp/servers must return list of configured servers with name and status."""
    response = client.get("/api/mcp/servers")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    assert data.get("ok") is True
    assert "servers" in data and isinstance(data["servers"], list)
    assert "source" in data and isinstance(data["source"], str)

    for server in data["servers"]:
        assert isinstance(server, dict)
        assert "name" in server and isinstance(server["name"], str)
        assert "status" in server
        assert "transport" in server
