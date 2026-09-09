"""OBS-01 — 운영 관측 계층 (도메인 metric + operation correlation + readiness).

GA-100 plan §OBS-01: "request/project/task/conversation correlation을 log와
metric에 연결한다. 압축 실패, auth lockout, registry write, vault merge,
task terminal conflict, provider failure를 관측한다."

구성:
  1. 도메인 metric — 기존 ``engine/metrics.py``의 RED/LLM 계열에 더해
     OBS-01이 요구하는 6개 운영 이벤트 계열을 추가한다. 모든 계열은
     ``outcome`` label 1개만 사용해 cardinally 폭발을 막는다:
       - ``ssak_context_compactions_total{outcome}``     success|degraded|halted|error
       - ``ssak_auth_events_total{outcome}``             success|failed|lockout
       - ``ssak_registry_writes_total{outcome}``         success|save_error|lock_timeout
       - ``ssak_vault_commits_total{outcome}``           success|commit_error
       - ``ssak_task_transition_conflicts_total{outcome}`` conflict|rejected
       - ``ssak_provider_failures_total{outcome}``       timeout|error
     기존 코드가 쓰던 ``http_requests_total`` 등은 그대로 유지된다.

  2. operation correlation — ``correlation_id_var``(요청 상관 id)에
     ``set_bound_request_execution_context``가 바인딩한 실행 컨텍스트
     (project/task/conversation)를 합쳐 **operation 범위 구조화 로그**를
     남긴다. 구조화 로그 한 줄로 한 operation의 project/task/tool/model
     흐름을 추적할 수 있어야 한다는 수용기준의 축이다.

  3. readiness — ``/health``(liveness)와 구분되는 실제 필수 dependency
     검사를 집계한다: task DB 접근, registry 로드, 프로젝트 저장소 쓰기
     가능, model manager 상태. 각 검사는 독립 실행으로 한 검사 실패가
     다른 검사를 오염하지 않는다.

모든 metric은 ``engine/metrics.py``와 동일한 lazy 등록 패턴을 따른다
(테스트에서 임포트만으로 중복 수집기 예외가 나지 않게).
"""

from __future__ import annotations

import logging
import time
from typing import Literal

from prometheus_client import Counter

from antigravity_k.api.error_handler import correlation_id_var
from antigravity_k.engine.metrics import REGISTRY

logger = logging.getLogger("antigravity_k.ops")


def _ops_logger() -> logging.Logger:
    """Return the operation logger, ensuring INFO records are not swallowed.

    ``setup_json_logger``가 설치하는 JSON file handler가 있으면 그쪽으로도
    흘러간다. 부모 로거가 WARNING으로 제한하면 operation 이벤트가 통계에서
    사라지므로, 명시적으로 INFO로 올린다 (setup_json_logger가 이미 했다면
    무해 — 같은 레벨).
    """
    if logger.getEffectiveLevel() > logging.INFO:
        logger.setLevel(logging.INFO)
    return logger


# ─── 도메인 metric ────────────────────────────────────────────────────────

_COMPACTIONS = "ssak_context_compactions_total"
_AUTH_EVENTS = "ssak_auth_events_total"
_REGISTRY_WRITES = "ssak_registry_writes_total"
_VAULT_COMMITS = "ssak_vault_commits_total"
_TASK_CONFLICTS = "ssak_task_transition_conflicts_total"
_PROVIDER_FAILURES = "ssak_provider_failures_total"

# outcome label 값 도메인 — 문서화된 계약 (docs/09_OPERATION_GUIDE.md §OBS-01)
CompactionOutcome = Literal["success", "degraded", "halted", "error"]
AuthOutcome = Literal["success", "failed", "lockout"]
RegistryOutcome = Literal["success", "save_error", "lock_timeout"]
VaultOutcome = Literal["success", "commit_error"]
TaskConflictOutcome = Literal["conflict", "rejected"]
ProviderFailureKind = Literal["timeout", "error"]

_metrics: dict[str, Counter] = {}


def _counter(name: str, description: str) -> Counter:
    """Lazy-create a single-label (outcome) domain counter."""
    if name not in _metrics:
        _metrics[name] = Counter(
            name,
            description,
            labelnames=("outcome",),
            registry=REGISTRY,
        )
    return _metrics[name]


def record_compaction(outcome: CompactionOutcome) -> None:
    """압축 시도 결과 1건을 기록한다 (CTX-03 이벤트와 1:1 대응)."""
    _counter(_COMPACTIONS, "Context compaction attempts by outcome.").labels(outcome=outcome).inc()


def record_auth_event(outcome: AuthOutcome) -> None:
    """인증 결과 1건을 기록한다 (SEC-02 audit 이벤트와 1:1 대응)."""
    _counter(_AUTH_EVENTS, "Authentication outcomes (success/failed/lockout).").labels(outcome=outcome).inc()


def record_registry_write(outcome: RegistryOutcome) -> None:
    """프로젝트 레지스트리 저장 결과 1건을 기록한다 (DAT-03 계약 대응)."""
    _counter(_REGISTRY_WRITES, "Project registry write outcomes.").labels(outcome=outcome).inc()


def record_vault_commit(outcome: VaultOutcome) -> None:
    """Vault git commit 결과 1건을 기록한다."""
    _counter(_VAULT_COMMITS, "Vault git commit outcomes.").labels(outcome=outcome).inc()


def record_task_transition_conflict(outcome: TaskConflictOutcome) -> None:
    """Task terminal CAS 충돌/거절 1건을 기록한다."""
    _counter(_TASK_CONFLICTS, "Task CAS transition conflicts/rejections.").labels(outcome=outcome).inc()


def record_provider_failure(kind: ProviderFailureKind) -> None:
    """모델 provider 실패 1건을 기록한다."""
    _counter(_PROVIDER_FAILURES, "Model provider failures by kind.").labels(outcome=kind).inc()


def snapshot_domain_counters() -> dict[str, dict[str, float]]:
    """테스트/진단용: 도메인 계열별 outcome → 값 스냅샷."""
    out: dict[str, dict[str, float]] = {}
    for name in (
        _COMPACTIONS,
        _AUTH_EVENTS,
        _REGISTRY_WRITES,
        _VAULT_COMMITS,
        _TASK_CONFLICTS,
        _PROVIDER_FAILURES,
    ):
        counter = _metrics.get(name)
        if counter is None:
            out[name] = {}
            continue
        samples: dict[str, float] = {}
        for metric in counter.collect():
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    samples[sample.labels.get("outcome", "")] = sample.value
        out[name] = samples
    return out


# ─── operation correlation 로거 ───────────────────────────────────────────

OperationOutcome = Literal["ok", "error"]


def log_operation_event(
    event: str,
    *,
    outcome: OperationOutcome = "ok",
    duration_ms: float | None = None,
    error_code: str | None = None,
    **fields: object,
) -> None:
    """operation 범위 구조화 로그 — correlation + 실행 컨텍스트 자동 주입.

    요청 미들웨어가 세팅한 ``correlation_id_var``와 바인딩된
    ``RequestExecutionContext``(project/task/conversation)를 읽어 한 줄로
    기록한다. 호출자는 이벤트 이름과 도메인 필드만 넘긴다.
    """
    from antigravity_k.api.project_binding import get_bound_request_execution_context

    context = get_bound_request_execution_context()
    payload: dict[str, object] = {
        "event": event,
        "outcome": outcome,
        "ts": time.time(),
        "correlation_id": correlation_id_var.get(""),
        "project_id": context.project_id if context else None,
        "task_id": context.task_id if context else None,
        "conversation_id": context.conversation_id if context else None,
        "session_id": context.session_id if context else None,
        "model_id": context.model_id if context else None,
    }
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 3)
    if error_code:
        payload["error_code"] = error_code
    for key, value in fields.items():
        payload[key] = value
    _ops_logger().info("%s", event, extra=payload)


# ─── readiness ────────────────────────────────────────────────────────────

ReadinessStatus = Literal["ready", "degraded", "not_ready"]


def _check_task_db() -> tuple[ReadinessStatus, str]:
    """TaskStateStore SQLite가 실제로 읽기 가능한지 확인."""
    try:
        import os

        from antigravity_k.engine.task_state_store import TaskStateStore

        db_path = os.environ.get("AGK_TASK_DB_PATH", "data/tasks.db")
        if not os.path.exists(db_path):
            # 아직 생성 전이면 ready로 본다 — 첫 요청 시 initialize된다.
            return "ready", "task_db (not yet created)"
        store = TaskStateStore(db_path)
        _ = store.list_tasks(limit=1)
        return "ready", "task_db ok"
    except Exception as exc:  # noqa: BLE001 — readiness는 모든 실패를 보고해야 한다
        return "not_ready", f"task_db: {type(exc).__name__}"


def _check_registry() -> tuple[ReadinessStatus, str]:
    """프로젝트 레지스트리 로드 + 활성 프로젝트 존재 확인."""
    try:
        from antigravity_k.engine.project_registry import get_project_registry

        registry = get_project_registry()
        active = registry.get_active_project()
        if not active.path:
            return "degraded", "registry: no active project"
        return "ready", "registry ok"
    except Exception as exc:  # noqa: BLE001
        return "not_ready", f"registry: {type(exc).__name__}"


def _check_writable_storage() -> tuple[ReadinessStatus, str]:
    """활성 프로젝트 루트(또는 데이터 디렉터리)에 실제 쓰기가 가능한지 확인."""
    import tempfile
    from pathlib import Path

    root: Path | None = None
    try:
        from antigravity_k.api.project_binding import get_request_project_root
        from antigravity_k.engine.project_registry import get_project_registry

        bound = get_request_project_root()
        if bound:
            root = Path(bound)
        else:
            active = get_project_registry().get_active_project()
            if active and active.path:
                root = Path(active.path).expanduser()
    except Exception:  # noqa: BLE001 — registry 실패 시 데이터 디렉터리로 fallback
        root = None
    if root is None or not root.exists():
        root = Path("data")
    probe_dir = root if root.is_dir() else root.parent
    try:
        with tempfile.NamedTemporaryFile(prefix="agk-readiness-", dir=probe_dir, suffix=".tmp") as fh:
            _ = fh.write(b"ok")
        return "ready", f"writable: {probe_dir}"
    except Exception as exc:  # noqa: BLE001
        return "not_ready", f"storage: {type(exc).__name__}"


def _check_model_manager() -> tuple[ReadinessStatus, str]:
    """모델 매니저가 응답 가능한 상태인지 확인 (로드된 모델 부재는 degraded)."""
    try:
        from antigravity_k.api.dependencies import get_model_manager

        manager = get_model_manager()
        if manager is None:
            return "degraded", "model_manager unavailable"
        status = manager.status() if hasattr(manager, "status") else {}
        loaded = status.get("loaded_models", {}) if isinstance(status, dict) else {}
        if isinstance(loaded, dict) and loaded:
            return "ready", f"models: {len(loaded)} loaded"
        return "degraded", "models: none loaded"
    except Exception as exc:  # noqa: BLE001
        return "not_ready", f"model_manager: {type(exc).__name__}"


def compute_readiness() -> dict[str, object]:
    """필수 dependency readiness를 집계한다.

    반환: {status, checks: [{name, status, detail}], checked_at}
      - ready     — 전 검사 ready
      - degraded  — not_ready 0건, degraded ≥1
      - not_ready — not_ready ≥1 (트래픽 수용 불가)
    """
    checks: list[dict[str, str]] = []
    for name, fn in (
        ("task_db", _check_task_db),
        ("registry", _check_registry),
        ("writable_storage", _check_writable_storage),
        ("model_manager", _check_model_manager),
    ):
        try:
            status, detail = fn()
        except Exception as exc:  # noqa: BLE001 — 개별 검사 크래시도 보고한다
            status, detail = "not_ready", f"{name}: {type(exc).__name__}"
        checks.append({"name": name, "status": status, "detail": detail})

    not_ready = sum(1 for c in checks if c["status"] == "not_ready")
    degraded = sum(1 for c in checks if c["status"] == "degraded")
    overall: ReadinessStatus = "not_ready" if not_ready else ("degraded" if degraded else "ready")
    return {
        "status": overall,
        "checks": checks,
        "checked_at": time.time(),
    }


__all__ = [
    "AuthOutcome",
    "CompactionOutcome",
    "ProviderFailureKind",
    "RegistryOutcome",
    "TaskConflictOutcome",
    "VaultOutcome",
    "compute_readiness",
    "log_operation_event",
    "record_auth_event",
    "record_compaction",
    "record_provider_failure",
    "record_registry_write",
    "record_task_transition_conflict",
    "record_vault_commit",
    "snapshot_domain_counters",
]
