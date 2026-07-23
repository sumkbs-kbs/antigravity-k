"""Tests for the Approval API routes."""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes.approval_api import router


@pytest.fixture
def client():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestListPending:
    def test_empty(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            mgr = mock.MagicMock()
            mgr.get_pending.return_value = []
            mock_get.return_value = mgr

            resp = client.get("/api/approval/pending")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 0
            assert data["pending"] == []

    def test_with_items(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            req = mock.MagicMock()
            req.to_dict.return_value = {"id": "req-1", "tool": "write_file"}
            mgr = mock.MagicMock()
            mgr.get_pending.return_value = [req]
            mock_get.return_value = mgr

            resp = client.get("/api/approval/pending")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 1
            assert data["pending"][0]["id"] == "req-1"


class TestGetRequest:
    def test_found(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            req = mock.MagicMock()
            req.to_dict.return_value = {"id": "req-1"}
            mgr = mock.MagicMock()
            mgr.get_request.return_value = req
            mock_get.return_value = mgr

            resp = client.get("/api/approval/req-1")
            assert resp.status_code == 200
            assert resp.json()["id"] == "req-1"

    def test_not_found(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            mgr = mock.MagicMock()
            mgr.get_request.return_value = None
            mock_get.return_value = mgr

            resp = client.get("/api/approval/nonexistent")
            assert resp.status_code == 404
            assert "찾을 수 없습니다" in resp.json()["detail"]


class TestResolveApproval:
    def test_approve(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            req = mock.MagicMock()
            req.status = mock.MagicMock()
            req.status.value = "approved"
            mgr = mock.MagicMock()
            mgr.resolve.return_value = True
            mgr.get_request.return_value = req
            mock_get.return_value = mgr

            resp = client.post("/api/approval/req-1/resolve", json={"decision": "approve"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["request_id"] == "req-1"

    def test_invalid_decision(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            mgr = mock.MagicMock()
            mock_get.return_value = mgr

            resp = client.post("/api/approval/req-1/resolve", json={"decision": "invalid"})
            assert resp.status_code == 400
            assert "잘못된 결정" in resp.json()["detail"]

    def test_resolve_fail_not_found(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            mgr = mock.MagicMock()
            mgr.resolve.return_value = False
            mock_get.return_value = mgr

            resp = client.post("/api/approval/req-1/resolve", json={"decision": "deny"})
            assert resp.status_code == 404
            assert "찾을 수 없거나" in resp.json()["detail"]


class TestResetAlwaysAllowed:
    def test_reset_ok(self, client):
        with mock.patch("antigravity_k.api.routes.approval_api.get_approval_manager") as mock_get:
            mgr = mock.MagicMock()
            mock_get.return_value = mgr

            resp = client.post("/api/approval/reset-always-allowed")
            assert resp.status_code == 200
            mgr.reset_always_allowed.assert_called_once()
            assert resp.json()["ok"] is True
