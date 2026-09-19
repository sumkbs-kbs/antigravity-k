"""CR-14 F-08 회귀 — 기본 사용량 DB 경로가 검증 실행에서 저장소를 더럽히지 않는다.

발견(F-08)
=========
``api/dependencies.py`` 는 ModelManager 를 만들 때 **CWD 상대 경로를 하드코딩**했다:

    tracker = UsageTracker(db_path="data/token_usage.json")

``data/token_usage.json`` 은 **추적 파일**이고, ``UsageTracker.record()`` 는
``auto_save_interval``(기본 50)건마다 ``_save()`` 를 호출한다. 즉 **사용량을 50건 이상 기록하는
테스트 조합 하나면 pytest 전체 실행이 후보 트리를 더럽혔다**(실측: ``M data/token_usage.json``).
F-02(``benchmark_harness``)와 **같은 결함이 두 번째 경로에 남아 있었다** — F-02 는 그 경로 하나만
격리했고, 이 하드코딩은 격리 대상이 아니었다.

계약
====
  C14-F08-1 기본 경로는 **단일 패치 지점**(``default_usage_db_path``)으로 정의되고,
            API 런타임이 그 지점을 사용한다(하드코딩 문자열이 남아 있지 않다).
  C14-F08-2 ``AGK_USAGE_DB`` 로 배포/실행 환경이 경로를 바꿀 수 있다(``~`` 확장 포함).
            우선순위 규칙은 전역 패치와 무관하게 순수 함수로도 검증된다.
  C14-F08-3 빈 값/공백/미설정은 프로덕션 기본값(추적 파일)으로 돌아간다 — 누적 사용량 DB 계약.
  C14-F08-4 기본 설정으로 기록해도 **저장소 추적 파일이 바뀌지 않는다**.
  C14-F08-5 그 격리는 ``tests/conftest.py`` 가 제공하며, 사라지면 이 테스트가 깨진다.
  C14-F08-6 명시한 경로로는 계속 저장된다(격리가 기능을 죽이지 않는다).
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

import antigravity_k.engine.usage_tracker as usage_mod
from antigravity_k.engine.usage_tracker import (
    USAGE_DB_ENV_VAR,
    UsageTracker,
    resolve_usage_db_path,
)


# 주의(F-02 와 같은 함정): conftest 는 **모듈 속성**을 패치한다.
# `from ... import default_usage_db_path` 로 이름을 직접 바인딩하면 임포트 시점 객체가 잡혀
# 패치가 보이지 않는다 — 그래서 테스트는 항상 모듈을 통해 읽는다.
def _default_usage_db_path() -> Path:
    return usage_mod.default_usage_db_path()


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_TRACKED_DB = REPO_ROOT / "data" / "token_usage.json"
PRODUCTION_DEFAULT = Path("data/token_usage.json")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def _resolved_db_path(tracker: UsageTracker) -> Path | None:
    db_path = getattr(tracker, "_db_path")
    assert db_path is None or isinstance(db_path, Path)
    return db_path


class TestDefaultPathIsPatchable:
    """C14-F08-1 — 기본 경로는 한 지점에서 결정된다(수정 전에는 호출자 하드코딩이었다)."""

    def test_tracker_has_no_baked_in_default(self) -> None:
        # UsageTracker 자체는 기본값을 갖지 않는다 — 경로 결정은 리졸버 한 곳이다.
        assert _resolved_db_path(UsageTracker()) is None

    def test_default_relative_constant_matches_production_target(self) -> None:
        assert usage_mod.DEFAULT_USAGE_DB_RELATIVE == PRODUCTION_DEFAULT
        assert not PRODUCTION_DEFAULT.is_absolute()

    def test_api_runtime_uses_the_resolver_not_a_hardcoded_string(self) -> None:
        """C14-F08-1 — 하드코딩 경로가 돌아오면 이 테스트가 깨진다."""
        from antigravity_k.api import dependencies

        source = inspect.getsource(dependencies.get_model_manager)

        assert "default_usage_db_path()" in source
        assert 'db_path="data/token_usage.json"' not in source
        assert "db_path='data/token_usage.json'" not in source


class TestEnvironmentOverride:
    """C14-F08-2/3 — 배포가 경로를 바꿀 수 있고, 빈 값은 기본값으로 돌아간다."""

    def test_env_override_wins(self, tmp_path: Path) -> None:
        target = tmp_path / "from-env.json"

        assert resolve_usage_db_path({USAGE_DB_ENV_VAR: str(target)}) == target

    def test_tilde_is_expanded(self) -> None:
        resolved = resolve_usage_db_path({USAGE_DB_ENV_VAR: "~/agk-usage/f08.json"})

        assert resolved.is_absolute()
        assert "~" not in str(resolved)
        assert resolved.name == "f08.json"

    @pytest.mark.parametrize("blank", ["", "   ", "\n"])
    def test_blank_env_falls_back_to_production_default(self, blank: str) -> None:
        assert resolve_usage_db_path({USAGE_DB_ENV_VAR: blank}) == PRODUCTION_DEFAULT

    def test_missing_env_falls_back_to_production_default(self) -> None:
        assert resolve_usage_db_path({}) == PRODUCTION_DEFAULT

    def test_os_environ_path_uses_the_same_rule(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        target = tmp_path / "from-environ.json"
        monkeypatch.setenv(USAGE_DB_ENV_VAR, str(target))

        assert usage_mod.resolve_usage_db_path() == resolve_usage_db_path({USAGE_DB_ENV_VAR: str(target)})


class TestTestHarnessDoesNotTouchTheRepository:
    """C14-F08-4/5 — 자동 저장 임계값을 넘겨도 저장소 추적 파일이 바뀌지 않는다."""

    def test_default_path_is_redirected_out_of_the_repository(self) -> None:
        # conftest 픽스처가 사라지면 이 단언이 깨진다(C14-F08-5).
        resolved = _default_usage_db_path()

        assert resolved != PRODUCTION_DEFAULT
        assert not str(resolved.resolve()).startswith(str(REPO_ROOT / "data"))

    def test_autosave_interval_does_not_touch_the_tracked_file(self) -> None:
        """F-08 의 핵심 — 임계값(기본 50)을 넘겨 기록해도 추적 파일은 그대로다."""
        tracked_before = _digest(REPO_TRACKED_DB)
        resolved = _default_usage_db_path()
        isolated_before = _digest(resolved)

        tracker = UsageTracker(db_path=str(resolved))
        interval = tracker._auto_save_interval  # noqa: SLF001 — 실제 임계값을 넘겨야 의미가 있다
        for _ in range(interval):
            tracker.record("cr14-f08", tokens_in=1, tokens_out=1, latency_ms=1.0)

        # 자동 저장은 격리된 파일에만 일어나고, 저장소 추적 파일은 바이트 단위로 그대로다.
        assert _digest(resolved) != isolated_before
        assert _digest(REPO_TRACKED_DB) == tracked_before

    def test_explicit_db_path_still_persists(self, tmp_path: Path) -> None:
        # C14-F08-6 — 격리가 "저장 자체"를 죽이지 않았는지 확인한다.
        explicit = tmp_path / "explicit-usage.json"
        tracker = UsageTracker(db_path=str(explicit), auto_save_interval=1)

        tracker.record("cr14-f08-explicit", tokens_in=2, tokens_out=3, latency_ms=1.0)

        assert explicit.exists()
        assert "cr14-f08-explicit" in explicit.read_text(encoding="utf-8")
