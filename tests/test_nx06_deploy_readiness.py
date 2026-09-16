"""NX-06: deployment readiness 계약 — probe 역할 분리와 트래픽 판정.

카드(docs/18_RELIABILITY_AND_CONNECTOME_DEVELOPMENT_PLAN.md §NX-06)의 정적/런타임
시험을 이 환경에서 가능한 범위로 고정한다:

* manifest 정적 검증: readinessProbe 가 실제 의존성 검사(`/api/ready`)를 보고,
  liveness/startup 은 프로세스 생존(`/health`)만 본다. probe 포트·namespace·이름이
  서로 맞물린다.
* 트래픽 판정: required 검사 실패 → 503(`traffic: reject`), optional 실패 → 200
  (`degraded`, 수용), 회복 → 다시 200/ready. `/health` 는 의존성이 모두 실패해도 200
  을 유지한다(liveness 가 restart loop 를 만들지 않는다는 계약).
* 잘못된 인증 secret 은 기동 단계에서 fail-closed 로 실패한다.
* 설정된 프로젝트 루트가 없는 상태를 `data/` 로 갈아타서 "ready" 라고 보고하지 않는다.

cluster 가 없는 환경이므로 Pod/EndpointSlice 런타임 관측은 BLOCKED 이며(handoff §),
여기서는 제품 계약과 manifest 계약만 검증한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml
from fastapi.testclient import TestClient

from antigravity_k.engine import operational_metrics as om

ROOT = Path(__file__).resolve().parents[1]
K8S_DIR = ROOT / "deploy" / "k8s"
NAMESPACE = "antigravity-k"


def _documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(K8S_DIR.glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(doc, dict):
                docs.append(doc)
    return docs


def _by_kind(kind: str) -> list[dict[str, Any]]:
    return [doc for doc in _documents() if doc.get("kind") == kind]


def _deployment() -> dict[str, Any]:
    deployments = _by_kind("Deployment")
    assert len(deployments) == 1
    return deployments[0]


def _container() -> dict[str, Any]:
    containers = _deployment()["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    return containers[0]


# ---------------------------------------------------------------------------
# 정적 검증 — manifest 계약
# ---------------------------------------------------------------------------


def test_readiness_probe_uses_dependency_check_not_process_health() -> None:
    """결함이었던 지점: readiness 가 `/health`(프로세스 생존)를 보고 있었다."""
    container = _container()
    probe = container["readinessProbe"]["httpGet"]
    assert probe["path"] == "/api/ready"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["startupProbe"]["httpGet"]["path"] == "/health"


def test_probe_ports_and_resource_names_are_consistent() -> None:
    container = _container()
    port_names = {p["name"] for p in container["ports"]}
    container_port = next(p["containerPort"] for p in container["ports"] if p["name"] == "http")
    for probe_name in ("readinessProbe", "livenessProbe", "startupProbe"):
        assert container[probe_name]["httpGet"]["port"] in port_names, probe_name

    service = _by_kind("Service")[0]
    assert service["spec"]["ports"][0]["targetPort"] == "http"
    assert service["spec"]["ports"][0]["protocol"] == "TCP"

    # NetworkPolicy 가 실제 포트를 허용하지 않으면 probe/traffic 이 막힌다.
    policy = _by_kind("NetworkPolicy")[0]
    allowed_ports = {rule["ports"][0]["port"] for rule in policy["spec"]["ingress"] if rule.get("ports")}
    assert container_port in allowed_ports
    assert "Ingress" in policy["spec"]["policyTypes"]


def test_every_namespaced_resource_uses_the_created_namespace() -> None:
    namespace = _by_kind("Namespace")[0]["metadata"]["name"]
    assert namespace == NAMESPACE
    for doc in _documents():
        if doc.get("kind") == "Namespace":
            continue
        assert doc["metadata"].get("namespace") == namespace, doc["metadata"].get("name")


def test_deployment_fails_closed_without_the_auth_secret() -> None:
    container = _container()
    env = {entry["name"]: entry for entry in container["env"]}
    assert env["AGK_ENV"]["value"] == "production"
    secret = env["AGK_SEC_ACCESS_PIN"]["valueFrom"]["secretKeyRef"]
    assert secret == {"name": "antigravity-k-auth", "key": "AGK_SEC_ACCESS_PIN"}

    # PIN hash/token secret 이 사는 경로는 영속 볼륨이어야 한다 — 아니면 재시작마다
    # secret 이 바뀌어 모든 세션이 끊긴다(NX-05 의 폐기 계약과 연결되는 조건).
    mounts = {m["mountPath"]: m["name"] for m in container["volumeMounts"]}
    assert "/app/data" in mounts
    volumes = {v["name"]: v for v in _deployment()["spec"]["template"]["spec"]["volumes"]}
    assert "persistentVolumeClaim" in volumes[mounts["/app/data"]]
    assert "persistentVolumeClaim" in volumes[mounts["/app/vault_data"]]


def test_install_order_and_removal_scope_are_documented() -> None:
    namespace_manifest = (K8S_DIR / "namespace.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")

    # namespace 를 먼저 적용하지 않으면 Secret 생성이 실패한다(순서 계약).
    for text in (namespace_manifest, readme):
        assert "kubectl apply -f deploy/k8s/namespace.yaml" in text
        first_ns = text.index("deploy/k8s/namespace.yaml")
        first_secret = text.index("kubectl create secret generic antigravity-k-auth")
        assert first_ns < first_secret, "namespace 가 secret 보다 먼저 문서화되어야 한다"

    assert "kubectl delete -f deploy/k8s/" in readme
    assert "namespace 는 다른 자원까지 함께 지우므로" in readme


def test_readiness_and_health_paths_are_public_for_probes() -> None:
    """probe 는 credential 을 갖지 않는다 — 두 경로 모두 인증 면제여야 한다."""
    from antigravity_k.api.server import _PUBLIC_EXACT_PATHS

    assert "/api/ready" in _PUBLIC_EXACT_PATHS
    assert "/health" in _PUBLIC_EXACT_PATHS


# ---------------------------------------------------------------------------
# 런타임 계약 — 트래픽 판정 (TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _check_report(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["name"]: check for check in report["checks"]}


def test_readiness_classification_matches_the_documented_table() -> None:
    report = om.compute_readiness()
    checks = _check_report(report)
    assert set(checks) == {"task_db", "registry", "writable_storage", "model_manager"}
    assert checks["task_db"]["kind"] == "required"
    assert checks["registry"]["kind"] == "required"
    assert checks["writable_storage"]["kind"] == "required"
    assert checks["model_manager"]["kind"] == "optional"
    assert report["traffic"] in ("accept", "reject")
    assert report["traffic"] == ("reject" if report["status"] == "not_ready" else "accept")


def test_required_failure_rejects_traffic_with_503(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def _broken() -> tuple[str, str]:
        raise RuntimeError("volume unmounted")

    monkeypatch.setattr(om, "_check_writable_storage", _broken)
    response = client.get("/api/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["traffic"] == "reject"
    assert "RuntimeError" in _check_report(body)["writable_storage"]["detail"]


def test_optional_failure_is_served_as_degraded(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """선택 의존성(model manager) 실패는 트래픽을 막지 않는다."""

    def _broken() -> tuple[str, str]:
        raise RuntimeError("manager crashed")

    monkeypatch.setattr(om, "_check_model_manager", _broken)
    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("degraded", "ready")
    assert body["traffic"] == "accept"
    model_check = _check_report(body)["model_manager"]
    assert model_check["status"] == "degraded"
    assert "optional dependency" in model_check["detail"]


def test_liveness_stays_200_while_readiness_fails(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """모델 다운로드/의존성 실패로 컨테이너를 재시작시키지 않는다(liveness 역할 분리)."""

    def _broken() -> tuple[str, str]:
        raise RuntimeError("registry exploded")

    for name in ("_check_task_db", "_check_registry", "_check_writable_storage", "_check_model_manager"):
        monkeypatch.setattr(om, name, _broken)

    assert client.get("/api/ready").status_code == 503
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert client.get("/v1/health").status_code == 200


def test_readiness_recovers_to_200_after_the_dependency_returns(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    state = {"broken": True}
    original = om._check_task_db

    def _maybe() -> tuple[str, str]:
        if state["broken"]:
            raise RuntimeError("db locked")
        return original()

    monkeypatch.setattr(om, "_check_task_db", _maybe)
    assert client.get("/api/ready").status_code == 503

    state["broken"] = False
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["traffic"] == "accept"


def test_missing_configured_project_root_is_not_reported_as_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """결함: 프로젝트 루트가 없으면 조용히 `data/` 를 검사해 'ready' 로 보고했다."""
    from antigravity_k.api import project_binding

    monkeypatch.setattr(project_binding, "get_request_project_root", lambda: "/nonexistent/nx06-project-root")
    status, detail = om._check_writable_storage()
    assert status == "degraded"
    assert "missing" in detail
    assert "nx06-project-root" in detail


def test_readiness_never_exposes_secret_material(client: TestClient) -> None:
    """probe 응답은 진단 정보만 담는다 — credential 경로/secret 값이 없어야 한다."""
    body = client.get("/api/ready").json()
    serialized = str(body).lower()
    for forbidden in ("pin", "token", "secret", "password"):
        assert forbidden not in serialized, forbidden


def test_bad_auth_secret_fails_closed_at_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """production/non-loopback + 약한 PIN + 유효 hash 없음 → 기동 실패(안전한 실패)."""
    from antigravity_k.api.server import app
    from antigravity_k.api.startup_security import StartupSecurityError
    from antigravity_k.config import config

    monkeypatch.setenv("AGK_ENV", "production")
    monkeypatch.setattr(config.server, "host", "0.0.0.0")
    monkeypatch.setattr(config.security, "access_pin", "1234")
    monkeypatch.setattr(config.security, "pin_hash_file", str(tmp_path / "absent-hash"))

    with pytest.raises(StartupSecurityError):
        with TestClient(app, raise_server_exceptions=False):
            pass
