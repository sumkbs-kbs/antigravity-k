#!/usr/bin/env python
"""NX-06 before/after driver: manifest probe 역할 분리와 readiness 판정.

두 트리를 같은 스크립트로 측정한다:

    rm -rf /tmp/nx06-before && mkdir -p /tmp/nx06-before
    git archive HEAD deploy src | tar -x -C /tmp/nx06-before

    NX06_TREE=before NX06_MANIFEST_DIR=/tmp/nx06-before/deploy/k8s \
        PYTHONPATH=/tmp/nx06-before/src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx06/repro_nx06_readiness_probe.py > before.json
    NX06_TREE=after PYTHONPATH=src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx06/repro_nx06_readiness_probe.py > after.json

측정 항목:

* `readinessProbe` 경로 (의존성 검사인가 프로세스 생존인가),
* `livenessProbe` / `startupProbe` 경로,
* probe 가 쓰는 포트가 컨테이너 포트 이름과 맞는가,
* readiness 보고서에 의존성 분류(`kind`)와 트래픽 판정(`traffic`)이 있는가,
* 설정된 프로젝트 루트가 없는 상태를 ready 로 오보하는가(false ready),
* required/optional 실패를 각각 503/200 으로 판정하는가.

종료 코드: 0 = 계약 충족, 3 = 결함 재현(readiness 가 생존 검사를 보거나 false ready).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# docs/qa/2026-09-16-followup/nx06/<file> → parents[4] 가 저장소 루트다.
DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[4] / "deploy" / "k8s"


def _load_deployment(manifest_dir: Path) -> dict[str, Any]:
    import yaml

    for path in sorted(manifest_dir.glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(doc, dict) and doc.get("kind") == "Deployment":
                return doc
    raise SystemExit(f"no Deployment manifest under {manifest_dir}")


def _probe_path(container: dict[str, Any], probe: str) -> str | None:
    definition = container.get(probe)
    if not isinstance(definition, dict):
        return None
    http_get = definition.get("httpGet")
    return http_get.get("path") if isinstance(http_get, dict) else None


def main() -> int:
    manifest_dir = Path(os.environ.get("NX06_MANIFEST_DIR", DEFAULT_MANIFEST_DIR))
    deployment = _load_deployment(manifest_dir)
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    port_names = {p["name"] for p in container["ports"]}

    report: dict[str, Any] = {
        "tree": os.environ.get("NX06_TREE", "unknown"),
        "manifest_dir": str(manifest_dir),
        "readiness_probe_path": _probe_path(container, "readinessProbe"),
        "liveness_probe_path": _probe_path(container, "livenessProbe"),
        "startup_probe_path": _probe_path(container, "startupProbe"),
        "readiness_probe_port_is_named": container["readinessProbe"]["httpGet"]["port"] in port_names,
        "readiness_reports_dependencies": _probe_path(container, "readinessProbe") == "/api/ready",
        "liveness_is_process_alive_only": _probe_path(container, "livenessProbe") not in (None, "/api/ready"),
    }

    # ── 제품 코드 판정 ────────────────────────────────────────────────
    from antigravity_k.api import project_binding
    from antigravity_k.engine.operational_metrics import compute_readiness

    baseline = compute_readiness()
    report["report_keys"] = sorted(baseline.keys())
    report["has_dependency_kind"] = all("kind" in c for c in baseline["checks"])
    report["has_traffic_verdict"] = "traffic" in baseline
    report["initial_status"] = baseline["status"]

    # ① 설정된 프로젝트 루트가 없을 때 false ready 를 보고하는가
    original = project_binding.get_request_project_root
    project_binding.get_request_project_root = lambda: "/nonexistent/nx06-configured-root"  # type: ignore[assignment]
    try:
        missing_root = compute_readiness()
    finally:
        project_binding.get_request_project_root = original  # type: ignore[assignment]
    storage = next(c for c in missing_root["checks"] if c["name"] == "writable_storage")
    report["missing_project_root_status"] = storage["status"]
    report["missing_project_root_detail"] = storage["detail"]
    report["false_ready_on_missing_root"] = storage["status"] == "ready" and "nonexistent" not in storage["detail"]

    # ② required 실패 → 거부, optional 실패 → 수용 인가
    import antigravity_k.engine.operational_metrics as om

    saved = {name: getattr(om, name) for name in ("_check_task_db", "_check_model_manager")}

    def _broken() -> tuple[str, str]:
        raise RuntimeError("injected failure")

    try:
        om._check_task_db = _broken  # type: ignore[assignment]
        required_failed = compute_readiness()
        om._check_task_db = saved["_check_task_db"]  # type: ignore[assignment]
        om._check_model_manager = _broken  # type: ignore[assignment]
        optional_failed = compute_readiness()
    finally:
        for name, fn in saved.items():
            setattr(om, name, fn)

    report["required_failure_status"] = required_failed["status"]
    report["required_failure_traffic"] = required_failed.get("traffic")
    report["required_failure_rejected"] = required_failed.get("traffic") == "reject"
    report["optional_failure_status"] = optional_failed["status"]
    report["optional_failure_traffic"] = optional_failed.get("traffic")
    report["optional_failure_served"] = optional_failed.get("traffic") == "accept"
    report["degraded_is_accepted"] = optional_failed["status"] != "ready" and optional_failed.get("traffic") == "accept"

    # ── cluster 가용성 (없으면 runtime 관측은 BLOCKED) ────────────────
    import subprocess

    contexts = subprocess.run(
        ["kubectl", "config", "get-contexts", "-o", "name"], capture_output=True, text=True, check=False
    )
    available = [line for line in contexts.stdout.splitlines() if line.strip()]
    report["kube_contexts"] = available
    report["runtime_observation"] = "BLOCKED (no kube context)" if not available else "possible"

    defects = []
    if not report["readiness_reports_dependencies"]:
        defects.append("readinessProbe does not use /api/ready")
    if report["false_ready_on_missing_root"]:
        defects.append("missing configured project root reported as ready")
    if not report["required_failure_rejected"]:
        defects.append("required failure is not rejected")
    if not report["degraded_is_accepted"]:
        defects.append("degraded is not served")
    report["defects"] = defects
    report["contract_met"] = not defects

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["contract_met"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
