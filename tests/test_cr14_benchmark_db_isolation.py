"""CR-14 F-02 회귀 — 기본 벤치마크 DB 경로가 검증 실행에서 저장소를 더럽히지 않는다.

발견(F-02)
=========
`BenchmarkHarness` 의 기본 DB 경로는 CWD 상대 ``data/benchmark_results.json``(추적 파일)이었고
그 정의는 클래스 상수 한 곳뿐이었다. API 런타임은

    AgentRuntime(task_outcome_recorder=benchmark_harness.record_task_outcome)   # api/dependencies.py

로 **모든 작업 완료를 그 파일에 기록**하므로, 작업을 실행하는 테스트가 하나라도 있으면
``pytest`` 전체 실행이 후보 트리의 추적 파일을 다시 썼다. 그 결과

  · 검증 후 clean tree 를 만들 수 없었고(CR-13 R03 드리프트의 뿌리),
  · 게이트 코드 지문이 실행마다 이동해 단계별 ``ga_gate.py --merge-into`` 가 거부됐다
    (attempt-001 의 `different working tree`, attempt-002 는 실행 후 되돌려 회피).

계약
====
  C14-F02-1 기본 경로는 **단일 패치 지점**(``default_benchmark_db_path``)으로 정의되고,
            하네스가 그 지점을 실제로 사용한다.
  C14-F02-2 ``AGK_BENCHMARK_DB`` 로 배포/실행 환경이 경로를 바꿀 수 있다(``~`` 확장 포함).
            우선순위 규칙은 전역 패치와 무관하게 순수 함수로도 검증된다
            (``resolve_benchmark_db_path(environ)``).
  C14-F02-3 빈 값/공백은 프로덕션 기본값으로 되돌아간다 — 추적 파일은 계속 누적 결과 DB 다.
  C14-F02-4 테스트 하네스에서 인자를 생략한 하네스는 **저장소 추적 파일을 쓰지 않는다**.
  C14-F02-5 그 격리는 ``tests/conftest.py`` 가 제공하며, 사라지면 이 테스트가 깨진다.
  C14-F02-6 명시한 경로로는 계속 저장된다(격리가 기능을 죽이지 않는다).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import antigravity_k.engine.benchmark_harness as harness_mod
from antigravity_k.engine.benchmark_harness import (
    BENCHMARK_DB_ENV_VAR,
    BenchmarkHarness,
    TaskOutcome,
    resolve_benchmark_db_path,
)


# 주의: conftest 는 **모듈 속성**을 패치한다. `from ... import default_benchmark_db_path`
# 로 이름을 직접 바인딩하면 임포트 시점 객체가 잡혀 패치가 보이지 않는다 — 그래서
# 테스트는 항상 모듈을 통해 읽는다(`harness_mod.default_benchmark_db_path()`).
def _default_db_path() -> Path:
    return harness_mod.default_benchmark_db_path()


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_TRACKED_DB = REPO_ROOT / "data" / "benchmark_results.json"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def _resolved_db_path(harness: BenchmarkHarness) -> Path:
    db_path = getattr(harness, "_db_path")
    assert isinstance(db_path, Path)
    return db_path


def _outcome(case_id: str = "cr14-f02") -> TaskOutcome:
    return TaskOutcome(
        case_id=case_id,
        target="test-model",
        success=True,
        completion_reason="test",
        latency_ms=1.0,
        tokens_in=1,
        tokens_out=1,
        cost_usd=0.0,
        error="",
        calibration_eligible=False,
    )


class TestDefaultPathIsPatchable:
    """C14-F02-1 — 기본 경로는 한 지점에서 결정된다(수정 전에는 클래스 상수뿐이었다)."""

    def test_harness_uses_the_resolver_not_a_frozen_constant(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "patched-benchmark.json"
        monkeypatch.setattr(harness_mod, "default_benchmark_db_path", lambda: target)

        harness = BenchmarkHarness(model_manager=MagicMock())

        assert _resolved_db_path(harness) == target

    def test_class_constant_still_points_at_the_production_default(self) -> None:
        # 하위 호환용 상수는 남아 있고, 프로덕션 기본값과 같아야 한다.
        assert BenchmarkHarness.DEFAULT_DB_PATH == Path("data/benchmark_results.json")
        assert harness_mod.DEFAULT_BENCHMARK_DB_RELATIVE == Path("data/benchmark_results.json")


class TestEnvironmentOverride:
    """C14-F02-2/3 — 배포가 경로를 바꿀 수 있고, 빈 값은 기본값으로 돌아간다.

    conftest 가 ``default_benchmark_db_path`` 를 패치하므로, 우선순위 규칙은 **순수 함수**
    (``resolve_benchmark_db_path``)로 검증한다 — 패치와 무관하게 규칙 자체를 고정한다.
    """

    def test_env_override_wins(self, tmp_path: Path) -> None:
        target = tmp_path / "from-env.json"

        assert resolve_benchmark_db_path({BENCHMARK_DB_ENV_VAR: str(target)}) == target

    def test_tilde_is_expanded(self) -> None:
        resolved = resolve_benchmark_db_path({BENCHMARK_DB_ENV_VAR: "~/agk-bench/f02.json"})

        assert resolved.is_absolute()
        assert "~" not in str(resolved)
        assert resolved.name == "f02.json"

    @pytest.mark.parametrize("blank", ["", "   ", "\n"])
    def test_blank_env_falls_back_to_production_default(self, blank: str) -> None:
        assert resolve_benchmark_db_path({BENCHMARK_DB_ENV_VAR: blank}) == Path("data/benchmark_results.json")

    def test_missing_env_falls_back_to_production_default(self) -> None:
        assert resolve_benchmark_db_path({}) == Path("data/benchmark_results.json")

    def test_os_environ_path_uses_the_same_rule(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        # 인자 없는 호출(os.environ 경로)과 매핑을 준 호출이 같은 답을 내는지 고정한다.
        target = tmp_path / "from-environ.json"
        monkeypatch.setenv(BENCHMARK_DB_ENV_VAR, str(target))

        assert harness_mod.resolve_benchmark_db_path() == resolve_benchmark_db_path({BENCHMARK_DB_ENV_VAR: str(target)})


class TestTestHarnessDoesNotTouchTheRepository:
    """C14-F02-4/5 — pytest 실행이 저장소 추적 파일을 쓰면 안 된다."""

    def test_default_path_is_redirected_out_of_the_repository(self) -> None:
        # conftest 픽스처가 사라지면 이 단언이 깨진다(C14-F02-5).
        resolved = _default_db_path()

        assert resolved != Path("data/benchmark_results.json")
        assert not str(resolved.resolve()).startswith(str(REPO_ROOT / "data"))

    def test_recording_an_outcome_with_default_args_leaves_the_tracked_file_intact(self, tmp_path: Path) -> None:
        tracked_before = _digest(REPO_TRACKED_DB)
        resolved = _default_db_path()
        isolated_before = _digest(resolved)

        harness = BenchmarkHarness(model_manager=MagicMock())
        harness.record_task_outcome(_outcome())

        # 기록은 격리된 파일에만 남고, 저장소 추적 파일은 바이트 단위로 그대로다.
        assert _digest(resolved) != isolated_before
        assert _digest(REPO_TRACKED_DB) == tracked_before
        _ = tmp_path  # 픽스처 사용 명시(임시 디렉터리 수명 보장)

    def test_explicit_db_path_still_persists(self, tmp_path: Path) -> None:
        # C14-F02-6 — 격리가 "저장 자체"를 죽이지 않았는지 확인한다.
        explicit = tmp_path / "explicit.json"
        harness = BenchmarkHarness(model_manager=MagicMock(), db_path=explicit)

        harness.record_task_outcome(_outcome("explicit-case"))

        assert explicit.exists()
        assert "explicit-case" in explicit.read_text(encoding="utf-8")
