"""학습 잡 API — StudioPage Start Training의 실제 백엔드 (Phase 59).

기존 POST /v1/integrations/unsloth/training/start는 Unsloth MCP 원격 런처라
로컬 mlx 파이프라인과 무관했다. 이 라우터는 ``LoRAPipeline.apply_recipe``로
레시피→데이터셋→설정을 구성하고 ``run_training``을 백그라운드 스레드로 실행해
``GET /api/training-jobs/{id}`` 폴링으로 진행/로그를 회수한다.

시뮬레이션 없음: progress는 실제 로그 라인 수 / 예상 반복 수 기반,
loss는 mlx-lm 로그에서 파싱한 실제 값 (파싱 실패 시 마지막 값 유지).
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from typing import TypedDict

from fastapi import APIRouter, HTTPException

from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.tool_contracts import Permission, ToolInvocation, ToolSpec

logger = logging.getLogger("antigravity_k.api.training_jobs")
router = APIRouter(prefix="/api/training-jobs")


class TrainingJobStartRequest(TypedDict, total=False):
    recipe: str
    base_model: str
    source: str
    platform: str
    hyperparameters: dict[str, float | int | str]
    pdf_pages: str
    pdf_header_filter: str
    pdf_question_template: str


class TrainingJobView(TypedDict):
    job_id: str
    status: str  # running | completed | failed
    recipe: str
    platform: str
    dataset_path: str
    config_path: str
    records: int
    sufficient: bool
    progress: int  # 0-100 (config 생성 완료 후 실제 반복 진행률)
    loss: float | None
    log_tail: list[str]
    error: str
    started_at: float
    finished_at: float | None


class _Job:
    """단일 학습 잡의 가변 상태. 스레드에서 갱신, 라우터에서 읽는다."""

    def __init__(self, job_id: str, recipe: str, platform: str) -> None:
        self.view: TrainingJobView = {
            "job_id": job_id,
            "status": "running",
            "recipe": recipe,
            "platform": platform,
            "dataset_path": "",
            "config_path": "",
            "records": 0,
            "sufficient": False,
            "progress": 0,
            "loss": None,
            "log_tail": [],
            "error": "",
            "started_at": time.time(),
            "finished_at": None,
        }
        self.iterations = 0  # mlx-lm --iterations (진행률 분모)
        self.cancelled = False
        self.proc: object | None = None  # run_training의 Popen — 취소용

    def append_log(self, line: str) -> None:
        tail = self.view["log_tail"]
        tail.append(line)
        if len(tail) > 80:
            del tail[: len(tail) - 80]
        if self.iterations > 0:
            m = re.search(r"^iter(?:ation)?\s+(\d+)", line)
            if m:
                self.view["progress"] = min(99, int(m.group(1)) * 100 // self.iterations)
        loss_match = re.search(r"(?:loss|train_loss)[=:]\s*([0-9.]+)", line, re.IGNORECASE)
        if loss_match:
            self.view["loss"] = float(loss_match.group(1))


# 프로세스 내 잡 저장 — 서버 재시작 시 사라지는 것이 정책 (학습 재개는 run_training 재실행으로)
_JOBS: dict[str, _Job] = {}
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 20


def _permission_gate() -> PermissionGate:
    from antigravity_k.api.routes.filesystem import WORKSPACE_ROOT

    return PermissionGate(project_root=WORKSPACE_ROOT, mode="auto-pilot")


def _require_allowed(tool_name: str, args: dict[str, str], risk_level: str) -> None:
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        raise HTTPException(status_code=403, detail=f"Permission denied for {tool_name}: {decision.permission.value}")


def _run_job(job: _Job, request: TrainingJobStartRequest) -> None:
    """백그라운드 스레드 본체 — apply_recipe 후 run_training."""
    from antigravity_k.engine.lora_pipeline import LoRAPipeline

    output_dir = f"data/training_jobs/{job.view['job_id']}"
    hyper = {k: v for k, v in request.get("hyperparameters", {}).items() if k != "iterations"}
    iterations_raw = request.get("hyperparameters", {}).get("iterations", 600)
    try:
        job.iterations = int(iterations_raw) if isinstance(iterations_raw, (int, float, str)) else 600
    except (TypeError, ValueError):
        job.iterations = 600

    try:
        pipeline = LoRAPipeline()
        result = pipeline.apply_recipe(
            request.get("recipe", "chat-sft"),
            base_model=request.get("base_model", ""),
            output_dir=output_dir,
            source=request.get("source", ""),
            platform=request.get("platform", "auto"),
            pdf_pages=request.get("pdf_pages", ""),
            pdf_header_filter=request.get("pdf_header_filter", ""),
            pdf_question_template=request.get("pdf_question_template", ""),
            hyperparameter_overrides=hyper or None,
        )
    except Exception as exc:  # noqa: BLE001 — 잡 스레드에서 모든 실패를 상태로 전환
        logger.exception("apply_recipe failed for job %s", job.view["job_id"])
        job.view["status"] = "failed"
        job.view["error"] = str(exc)
        job.view["finished_at"] = time.time()
        return

    job.view["dataset_path"] = str(result.get("dataset_path", ""))
    job.view["config_path"] = str(result.get("config_path", ""))
    job.view["records"] = int(result.get("records", 0))
    job.view["sufficient"] = bool(result.get("sufficient", False))
    job.view["progress"] = 5  # config 생성 완료

    config = result.get("config")
    if job.iterations <= 0 or not isinstance(config, dict):
        job.view["status"] = "completed"
        job.view["progress"] = 100
        job.view["finished_at"] = time.time()
        return

    # 실제 학습 실행 (동기 — 잡 스레드 안이므로 이벤트 루프를 막지 않는다)
    run_result = pipeline.run_training(
        config,
        on_log=job.append_log,
        timeout_sec=None,
    )
    job.view["progress"] = 100
    job.view["finished_at"] = time.time()
    job.view["status"] = "completed" if run_result.success else "failed"
    if not run_result.success:
        job.view["error"] = run_result.error or f"exit_code={run_result.exit_code}"


@router.post("")
async def start_training_job(request: TrainingJobStartRequest) -> dict[str, object]:
    """레시피 적용 + 학습 실행을 백그라운드 잡으로 시작한다."""
    _require_allowed(
        "start_training", {"recipe": request.get("recipe", ""), "base_model": request.get("base_model", "")}, "critical"
    )

    job_id = f"train_{uuid.uuid4().hex[:12]}"
    job = _Job(job_id, request.get("recipe", ""), request.get("platform", "auto"))
    with _JOBS_LOCK:
        _JOBS[job_id] = job
        # 상한 초과 시 가장 오래된 완료 잡 정리
        if len(_JOBS) > _MAX_JOBS:
            finished = [k for k, v in _JOBS.items() if v.view["status"] != "running"]
            for key in sorted(finished, key=lambda k: _JOBS[k].view["started_at"])[: len(_JOBS) - _MAX_JOBS]:
                _ = _JOBS.pop(key, None)

    thread = threading.Thread(target=_run_job, args=(job, request), name=f"training-{job_id}", daemon=True)
    thread.start()
    return {"ok": True, "job_id": job_id}


@router.get("/{job_id}")
async def get_training_job(job_id: str) -> TrainingJobView:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown training job")
    return job.view


@router.post("/{job_id}/cancel")
async def cancel_training_job(job_id: str) -> dict[str, object]:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown training job")
    if job.view["status"] != "running":
        return {"ok": False, "detail": "job is not running"}
    job.cancelled = True
    proc = job.proc
    if proc is not None and hasattr(proc, "terminate"):
        terminate = getattr(proc, "terminate")
        try:
            terminate()
        except Exception:  # noqa: BLE001 — 이미 종료된 프로세스는 무시
            pass
    job.view["status"] = "failed"
    job.view["error"] = "cancelled by user"
    job.view["finished_at"] = time.time()
    return {"ok": True}
