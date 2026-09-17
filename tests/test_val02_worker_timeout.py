"""계약 시험 — 하네스가 **죽은 worker** 를 만났을 때 멈추지 않고 오류로 세는가.

왜 계약인가 (2026-09-17 실측): 8시간 soak 의 SC-3 에서 worker 하나가 `RegistrySaveError` 로
죽자 `q.get()` 에 타임아웃이 없어 부모가 **영원히** 대기했고, 러너는 종료 시에만 리포트를 쓰므로
실행 전체가 **아무 산출물 없이** 멈췄다(8시간을 태우고 결과 0). worker 가 죽는 것과 실행이
멈추는 것은 다른 사건이고, 후자는 어느 게이트도 보지 않았다.

이 시험은 하네스를 8시간 돌리지 않는다 — `_collect_worker_results` 를 직접 불러
① 살아 있지만 결과를 안 보내는 worker 가 **상한 안에서** 오류 1건으로 계상되고
② 정상 worker 의 결과는 그대로 통과하고
③ 타임아웃된 프로세스가 남지 않는다(다음 시나리오의 측정을 오염시키지 않는다)를 고정한다.
"""

from __future__ import annotations

import importlib.util
import inspect
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


def _load_staging() -> Any:
    path = _repo_root() / "scripts" / "val02_staging.py"
    spec = importlib.util.spec_from_file_location("val02_staging_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


staging = _load_staging()


def _silent_worker(q: Any) -> None:  # 결과를 **보내지 않고** 살아 있는 worker
    time.sleep(30)


def _reporting_worker(q: Any) -> None:
    q.put({"errors": 0, "ok": True})


def test_silent_worker_is_counted_as_error_not_waited_forever(monkeypatch: Any) -> None:
    monkeypatch.setattr(staging, "WORKER_RESULT_TIMEOUT_S", 1.0)
    q: Any = mp.Queue()
    silent = mp.Process(target=_silent_worker, args=(q,))
    reporting = mp.Process(target=_reporting_worker, args=(q,))
    for p in (silent, reporting):
        p.start()
    try:
        started = time.perf_counter()
        results, timeouts = staging._collect_worker_results(q, [silent, reporting], fallback={"errors": 1, "ok": False})
        elapsed = time.perf_counter() - started
    finally:
        for p in (silent, reporting):
            if p.is_alive():
                p.terminate()
            p.join(timeout=10)

    assert timeouts == 1, f"타임아웃이 계상되지 않았다: {timeouts}"
    assert sum(r["errors"] for r in results) == 1, "타임아웃이 오류 1건으로 세어지지 않았다"
    assert any(r.get("ok") for r in results), "정상 worker 의 결과가 전달되지 않았다"
    assert elapsed < 20, f"타임아웃 상한이 지켜지지 않았다({elapsed:.1f}s)"
    assert not silent.is_alive(), "타임아웃된 worker 가 남았다 — 다음 시나리오 측정을 오염시킨다"


def test_all_race_scenarios_use_the_timeout_collector() -> None:
    """세 경합 시나리오가 **모두** 타임아웃 있는 수집기를 쓴다(하나만 고치면 나머지에서 같은 멈춤)."""
    for name in ("scenario_task_cas", "scenario_conversation_cas", "scenario_registry_concurrent"):
        source = inspect.getsource(getattr(staging, name))
        assert "_collect_worker_results" in source, f"{name} 이 타임아웃 있는 수집기를 쓰지 않는다"
        assert "worker_timeouts" in source, f"{name} 이 타임아웃 수를 리포트에 남기지 않는다"
