"""task 14 계약 시험 — 검색 통합 화면이 쓰는 상태·설정·증거.

여기서 고정하는 문장:

- **상태는 사용자 의미로 말한다**: 화면이 보는 라벨에 구현 용어(`ready`/`degraded`/`stopped`)가
  나오지 않는다. 사용자는 "번들이 준비됐다"가 아니라 "사용 가능"을 알아야 한다.
- **조회는 부작용이 없다**: 상태 조회가 child 를 만들지 않는다(아직 시작 전이면 `idle`).
- **잘못된 설정은 켜지지 않는다**: 켰는데 경로가 없거나 신뢰 밖이면 `misconfigured` 이고, 저장은 400 이며
  `.env` 는 손대지 않는다.
- **저장은 즉시 반영된다**: 설정 저장이 `.env` + 프로세스 env 를 함께 바꾼다(재시작 대기 없음).
- **증거는 버려지지 않는다**: 출처 링크·수집시각·부분 수집(aborted_backends)·상한 초과(budget)가
  **실제 child 응답**에서 보존된다.
- **실패는 성공으로 렌더되지 않는다**: `isError` 응답은 `ok=False` + 오류 코드로 오고 출처가 비어 있다.
- **연결 확인은 대체하지 않는다**: transient 실패에도 legacy 엔진을 부르지 않는다(질문이 "번들이
  되느냐"이기 때문). 이 시험의 spy 가 그 문장을 잡는다.
- **비밀·경로를 흘리지 않는다**: 상태 응답에는 artifact **파일명**만 있고 절대 경로가 없다.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.tools.ssak_search_provider import (
    EVIDENCE_HISTORY_LIMIT,
    SearchEvidence,
    SsakSearchSettings,
    bundled_runtime_config,
    clear_search_evidence,
    latest_search_evidence,
    record_search_evidence,
    search_with_bundled_provider,
    settings_snapshot,
)
from antigravity_k.tools.ssak_search_runtime import shutdown_ssak_search_runtime
from antigravity_k.tools.ssak_search_status import (
    AVAILABILITY_LABELS,
    AVAILABLE,
    MISCONFIGURED,
    UNAVAILABLE,
    availability_snapshot,
    evidence_snapshot,
    probe_search,
    retry_availability,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ssak_search_evidence_child.py"
HERMETIC_ARGS: tuple[str, ...] = ("-I", "-S")


# ── 도우미 ────────────────────────────────────────────────────────────────────


def write_config(tmp_path: Path, ssak: dict[str, Any]) -> Path:
    """`search.ssak.*` 만 가진 config.yaml."""
    lines = ["search:", "  ssak:"]
    for key, value in ssak.items():
        lines.append(f"    {key}: {json.dumps(value) if isinstance(value, str) else value}")
    path = tmp_path / "config.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def bundle(tmp_path: Path, scenario: str = "ok") -> Path:
    """fixture child 를 실행하는 shim(+매니페스트)을 신뢰 루트 안에 만든다."""
    shim = tmp_path / "bin" / "ssak-mcp"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(
        "#!/bin/sh\n"
        f'export SSAK_EVIDENCE_SCENARIO="{scenario}"\n'
        f'exec "{sys.executable}" {" ".join(HERMETIC_ARGS)} "{FIXTURE}"\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    manifest = tmp_path / "release" / "ssak-search-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "artifact": {
                    "sha256": hashlib.sha256(shim.read_bytes()).hexdigest(),
                    "platform": "darwin",
                    "arch": "arm64",
                }
            }
        ),
        encoding="utf-8",
    )
    return shim


def enable(tmp_path: Path, shim: Path, monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    """번들 provider 를 켠 상태로 만든다(신뢰 루트 = tmp_path)."""
    config = write_config(tmp_path, {"enabled": True, "artifact_path": str(shim), **overrides})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))
    monkeypatch.delenv("AGK_SEARCH_SSAK_ENABLED", raising=False)
    monkeypatch.delenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", raising=False)


@pytest.fixture(autouse=True)
def isolated_env_file(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """이 모듈의 어떤 시험도 **저장소의 진짜 `.env`** 를 건드릴 수 없게 한다.

    왜 기본값으로 두는가: 설정 저장 시험은 "검증이 먼저"를 주장하지만, 그 주장을 **깨는 변이**
    (검증을 건너뛰는 한 줄)를 넣고 돌리면 쓰기가 그대로 실행된다. 그때 격리가 없으면 공유 체크아웃의
    `.env` 에 `AGK_SEARCH_SSAK_MODE=carrier-pigeon` 같은 값이 실제로 남아 **그 뒤 모든 검색이
    `blocked (invalid search.ssak configuration)`** 이 된다 — 시험 하나가 개발자 환경을 망가뜨린다.
    그래서 격리는 "각 시험이 잊지 않기를" 기대하지 않고 기본값으로 둔다.
    """
    env_file = tmp_path_factory.mktemp("search-settings") / "isolated.env"
    monkeypatch.setenv("AGK_ENV_FILE", str(env_file))


@pytest.fixture(autouse=True)
def clean_evidence() -> Iterator[None]:
    """호스트 전역 링과 싱글턴을 시험마다 초기화한다(순서 오염 금지)."""
    clear_search_evidence()
    yield
    clear_search_evidence()
    status = shutdown_ssak_search_runtime(timeout=20)
    assert status is None or status["child_pids"] == [], f"child 가 남았다: {status}"


# ── 1. 상태는 사용자 의미로 말한다 ────────────────────────────────────────────


def test_every_availability_label_is_user_meaning_not_a_process_name() -> None:
    internal = ("ready", "degraded", "stopped", "starting", "disabled", "failed", "circuit")
    for availability, label in AVAILABILITY_LABELS.items():
        assert label, availability
        lowered = label.lower()
        for word in internal:
            assert word not in lowered, f"{availability} 라벨에 구현 용어가 샌다: {label}"


def test_status_returns_label_tone_action_and_no_internal_state_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shim = bundle(tmp_path)
    enable(tmp_path, shim, monkeypatch)

    snapshot = availability_snapshot()

    # 실행 전이므로 idle — "사용 가능"이라고 주장하지 않는다(아직 아무것도 하지 않았다).
    assert snapshot["availability"] == "idle"
    assert snapshot["label"] == AVAILABILITY_LABELS["idle"]
    assert snapshot["tone"] == "info"
    assert snapshot["recoverable"] is True
    assert snapshot["detail"]
    assert snapshot["runtime"]["present"] is False
    # 파일명만 — 절대 경로가 응답에 실리지 않는다.
    assert snapshot["settings"]["artifact_name"] == "ssak-mcp"
    assert str(tmp_path) not in json.dumps(snapshot, ensure_ascii=False)
    assert str(shim) not in json.dumps(snapshot, ensure_ascii=False)


def test_disabled_status_is_not_recoverable_and_never_claims_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, {"enabled": False})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("AGK_SEARCH_SSAK_ENABLED", raising=False)

    snapshot = availability_snapshot()

    assert snapshot["availability"] == "disabled"
    assert snapshot["recoverable"] is False
    assert snapshot["settings"]["enabled"] is False


def test_enabled_without_a_path_is_misconfigured_and_not_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, {"enabled": True})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", raising=False)

    snapshot = availability_snapshot()

    assert snapshot["availability"] == MISCONFIGURED
    assert snapshot["settings"]["problem"]
    assert snapshot["recoverable"] is False


def test_enabled_with_a_path_outside_the_trusted_roots_is_misconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    shim = bundle(outside)
    config = write_config(tmp_path, {"enabled": True, "artifact_path": str(shim)})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path / "trusted-only"))

    snapshot = availability_snapshot()

    assert snapshot["availability"] == MISCONFIGURED
    assert snapshot["settings"]["artifact_trusted"] is False


def test_an_invalid_fallback_is_misconfigured_even_though_mode_and_path_are_fine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`problem` 자체가 상태를 결정하는 자리 — mode/path 검사가 통과해도 설정이 틀리면 켜지지 않는다.

    이 경우가 없으면 "설정 문제를 먼저 본다"는 규칙을 다른 검사가 가려 준다(이빨 S2 가 그 구멍을 지적했다).
    """
    shim = bundle(tmp_path)
    enable(tmp_path, shim, monkeypatch, fallback="pretend-nothing-happened")

    snapshot = availability_snapshot()

    assert snapshot["settings"]["mode_supported"] is True
    assert snapshot["settings"]["artifact_trusted"] is True
    assert snapshot["settings"]["problem"], "설정 문제가 보고되어야 한다"
    assert snapshot["availability"] == MISCONFIGURED
    assert snapshot["recoverable"] is False


class _FakeRuntime:
    """상태기계를 흥내내는 최소 객체 — 실제 child 없이 **매핑만** 재기 위한 것이다."""

    def __init__(self, state: str, *, child_pids: list[int] | None = None, artifact: str = "") -> None:
        self.state = type("State", (), {"value": state})()
        self.circuit_open = False
        self.config = type("Config", (), {"artifact_path": artifact, "enabled": True})()
        self._child_pids = child_pids or []

    def status(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "circuit_open": self.circuit_open,
            "child_pids": self._child_pids,
            "spawn_attempts": 1,
        }


def test_an_unknown_runtime_state_is_reported_as_unavailable_not_available(tmp_path: Path) -> None:
    """상태기계가 커진 뒤 이 표를 안 고치는 실수를 막는다 — 모르면 성공으로 읽지 않는다."""
    shim = bundle(tmp_path)
    settings = SsakSearchSettings(enabled=True, artifact_path=str(shim), extra_trusted_roots=(str(tmp_path),))

    snapshot = availability_snapshot(
        settings,
        runtime=_FakeRuntime("invented-by-a-future-refactor", artifact=str(shim)),  # type: ignore[arg-type]
        include_evidence=False,
    )

    assert snapshot["availability"] == UNAVAILABLE
    assert snapshot["recoverable"] is True


def test_a_ready_runtime_is_available(tmp_path: Path) -> None:
    """매핑의 성공 쪽도 직접 잰다 — 실패 쪽만 재면 "전부 실패" 구현도 통과한다."""
    shim = bundle(tmp_path)
    settings = SsakSearchSettings(enabled=True, artifact_path=str(shim), extra_trusted_roots=(str(tmp_path),))

    snapshot = availability_snapshot(
        settings,
        runtime=_FakeRuntime("ready", child_pids=[1234], artifact=str(shim)),  # type: ignore[arg-type]
        include_evidence=False,
    )

    assert snapshot["availability"] == AVAILABLE
    assert snapshot["label"] == AVAILABILITY_LABELS[AVAILABLE]
    assert snapshot["recoverable"] is False
    assert snapshot["runtime"]["child_count"] == 1
    # child 가 살아 있고 설정이 같으면 재시작이 필요 없다.
    assert snapshot["runtime"]["restart_required"] is False


# ── 2. 조회는 부작용이 없다 ───────────────────────────────────────────────────


def test_status_endpoint_never_starts_a_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = bundle(tmp_path)
    enable(tmp_path, shim, monkeypatch)
    client = TestClient(app)

    response = client.get("/api/search/status")

    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "idle"
    assert body["runtime"]["present"] is False
    assert body["runtime"]["child_count"] == 0
    # 조회가 spawn 을 일으켰다면 싱글턴이 생겼을 것이다 — 그것 자체가 계약 위반이다.
    assert availability_snapshot()["runtime"]["present"] is False


# ── 3. 설정 저장 — 검증 먼저, 즉시 반영 ───────────────────────────────────────


def test_settings_endpoint_refuses_to_enable_without_a_path_and_leaves_env_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "isolated.env"
    env_file.write_text("# untouched\n", encoding="utf-8")
    monkeypatch.setenv("AGK_ENV_FILE", str(env_file))
    monkeypatch.setenv("AGK_CONFIG_FILE", str(write_config(tmp_path, {"enabled": False})))
    # teardown 이 지우도록 미리 등록한다(엔드포인트는 os.environ 을 직접 만진다).
    monkeypatch.setenv("AGK_SEARCH_SSAK_ENABLED", "false")
    monkeypatch.setenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", "toBeReplaced")
    # 경로를 정말 지워 "켜려는데 경로가 없는" 상태를 만든다.
    monkeypatch.delenv("AGK_SEARCH_SSAK_ARTIFACT_PATH")
    client = TestClient(app)

    response = client.post("/api/search/settings", json={"enabled": True})

    assert response.status_code == 400
    assert "artifact" in response.json()["detail"]
    assert env_file.read_text(encoding="utf-8") == "# untouched\n"


def test_settings_endpoint_persists_to_env_and_applies_without_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shim = bundle(tmp_path)
    env_file = tmp_path / "isolated.env"
    env_file.write_text("# isolated\n", encoding="utf-8")
    monkeypatch.setenv("AGK_ENV_FILE", str(env_file))
    monkeypatch.setenv("AGK_CONFIG_FILE", str(write_config(tmp_path, {"enabled": False})))
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))
    # teardown 이 지우도록 미리 등록한다(엔드포인트는 os.environ 을 직접 만진다).
    monkeypatch.setenv("AGK_SEARCH_SSAK_ENABLED", "false")
    monkeypatch.setenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", "toBeReplaced")
    client = TestClient(app)

    response = client.post("/api/search/settings", json={"enabled": True, "artifact_path": str(shim)})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["saved"] == ["artifact_path", "enabled"]
    assert body["settings"]["enabled"] is True
    assert body["settings"]["artifact_trusted"] is True
    assert body["availability"] == "idle"
    written = env_file.read_text(encoding="utf-8")
    assert "AGK_SEARCH_SSAK_ENABLED=true" in written
    assert f"AGK_SEARCH_SSAK_ARTIFACT_PATH={shim}" in written
    # 재시작 없이 즉시 반영 — 프로세스 env 도 바뀌었고 스냅숏이 그 값을 읽는다.
    assert os.environ["AGK_SEARCH_SSAK_ENABLED"] == "true"
    assert settings_snapshot().enabled is True
    # 저장은 child 를 만들지 않는다(저장과 실행은 다른 결정이다).
    assert availability_snapshot()["runtime"]["present"] is False


def test_settings_endpoint_clears_the_path_when_given_an_empty_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shim = bundle(tmp_path)
    env_file = tmp_path / "isolated.env"
    env_file.write_text(f"AGK_SEARCH_SSAK_ARTIFACT_PATH={shim}\n", encoding="utf-8")
    monkeypatch.setenv("AGK_ENV_FILE", str(env_file))
    monkeypatch.setenv("AGK_CONFIG_FILE", str(write_config(tmp_path, {"enabled": False})))
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))
    monkeypatch.setenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", str(shim))
    monkeypatch.setenv("AGK_SEARCH_SSAK_ENABLED", "false")
    client = TestClient(app)

    response = client.post("/api/search/settings", json={"artifact_path": ""})

    assert response.status_code == 200, response.text
    assert response.json()["settings"]["artifact_configured"] is False
    assert "AGK_SEARCH_SSAK_ARTIFACT_PATH" not in env_file.read_text(encoding="utf-8")


def test_settings_endpoint_rejects_an_unknown_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = Path(os.environ["AGK_ENV_FILE"])
    env_file.write_text("# untouched\n", encoding="utf-8")
    monkeypatch.setenv("AGK_CONFIG_FILE", str(write_config(tmp_path, {"enabled": False})))
    client = TestClient(app)

    response = client.post("/api/search/settings", json={"mode": "carrier-pigeon"})

    assert response.status_code == 400
    assert "mode" in response.json()["detail"]
    # 거절은 **쓰기 없음**을 뜻한다 — 검증 순서가 뒤집히면 이 줄이 진짜 파일을 지킨다.
    assert env_file.read_text(encoding="utf-8") == "# untouched\n"
    assert "AGK_SEARCH_SSAK_MODE" not in os.environ or os.environ["AGK_SEARCH_SSAK_MODE"] != "carrier-pigeon"


# ── 4. 증거 — 실제 child 응답에서 보존되는가 ─────────────────────────────────


def _attempt(query: str = "증거") -> Any:
    return search_with_bundled_provider(query, settings=settings_snapshot())


def test_success_evidence_keeps_links_scores_providers_and_retrieved_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable(tmp_path, bundle(tmp_path, "ok"), monkeypatch)

    attempt = _attempt()

    assert attempt.ok is True, attempt.message
    evidence = attempt.evidence
    assert isinstance(evidence, SearchEvidence)
    assert evidence.partial is False
    assert [source.url for source in evidence.sources] == [
        "https://example.test/official",
        "https://blog.example.test/post",
    ]
    assert evidence.sources[0].score == pytest.approx(0.93)
    assert evidence.sources[0].provider == "searxng"
    assert evidence.sources[1].snippet == "블로그 본문"
    assert evidence.took_ms == 512
    assert evidence.signal_confidence == "HIGH"
    assert evidence.phishing_filtered == 1
    assert evidence.decomposed_subqueries == ("정상 하위질의",)
    assert evidence.budget is None
    retrieved = datetime.fromisoformat(str(evidence.retrieved_at).replace("Z", "+00:00"))
    assert datetime.now(timezone.utc) - retrieved < timedelta(seconds=60)


def test_partial_scenario_reports_aborted_backends_as_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable(tmp_path, bundle(tmp_path, "partial"), monkeypatch)

    attempt = _attempt()

    assert attempt.ok is True
    evidence = attempt.evidence
    assert evidence is not None
    assert evidence.partial is True
    assert evidence.aborted_backends == ("bing", "naver")
    assert evidence.signal_confidence == "MEDIUM"
    assert evidence.sources, "부분 수집이어도 받은 출처는 남아야 한다"


def test_truncated_scenario_reports_the_budget_that_forced_the_trim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable(tmp_path, bundle(tmp_path, "truncated"), monkeypatch)

    attempt = _attempt()

    evidence = attempt.evidence
    assert evidence is not None
    assert evidence.budget is not None
    assert evidence.budget.truncated is True
    assert evidence.budget.trimmed_items == 3
    assert evidence.budget.exceeded == "tokens"
    assert evidence.budget.tokens == 9000


def test_cached_response_dates_the_collection_in_the_past(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    enable(tmp_path, bundle(tmp_path, "cached"), monkeypatch)

    attempt = _attempt()

    evidence = attempt.evidence
    assert evidence is not None
    assert evidence.from_cache is True
    assert evidence.cache_age_ms == 900_000
    retrieved = datetime.fromisoformat(str(evidence.retrieved_at).replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - retrieved
    # 캐시 응답을 "방금 수집"으로 표시하면 화면이 사용자에게 거짓 신선도를 준다.
    assert timedelta(minutes=14) < age < timedelta(minutes=16), age


def test_error_response_is_not_evidence_of_a_successful_search(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    enable(tmp_path, bundle(tmp_path, "error"), monkeypatch)

    attempt = _attempt()

    assert attempt.ok is False
    evidence = attempt.evidence
    assert evidence is not None
    assert evidence.ok is False
    assert evidence.error_code == "AUTH_REQUIRED"
    assert evidence.failure_class == "permanent"
    assert evidence.sources == ()
    assert evidence.route.startswith("bundled")


def test_a_plain_text_response_is_zero_hits_not_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    enable(tmp_path, bundle(tmp_path, "plain"), monkeypatch)

    attempt = _attempt()

    assert attempt.ok is True
    evidence = attempt.evidence
    assert evidence is not None
    assert evidence.sources == ()
    assert evidence.route == "bundled"


def test_refusals_before_routing_are_recorded_as_evidence_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    settings = SsakSearchSettings(
        enabled=True,
        artifact_path=str(bundle(outside)),
        extra_trusted_roots=(str(tmp_path / "trusted-only"),),
    )

    attempt = search_with_bundled_provider("거절", settings=settings)

    assert attempt.ok is False
    assert attempt.evidence is not None
    assert attempt.evidence.error_code == "UNTRUSTED_ARTIFACT_PATH"
    assert attempt.evidence.failure_class == "permanent"
    assert latest_search_evidence()[0].error_code == "UNTRUSTED_ARTIFACT_PATH"


def test_the_evidence_ring_is_bounded_and_newest_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """링은 **총 검색 수에 비례해 자라지 않는다** + 이력은 화면용이라 작게 잡혀 있다.

    두 번째 주장이 왜 필요한가: 첫 주장만 있으면 `EVIDENCE_HISTORY_LIMIT` 를 키우는 변이가
    살아남는다(시험이 상수를 따라가므로 자기참조가 된다 — 메모리는 여전히 유계지만 응답·기억이
    같이 커진다). 이빨 S15 가 실제로 그 구멍을 지적했고, 그래서 상한을 **문장으로** 고정한다.
    """
    enable(tmp_path, bundle(tmp_path), monkeypatch)

    # 화면용 최근 이력 — 커지면 검색 1회당 응답·메모리 비용이 같이 늘어난다.
    assert 1 <= EVIDENCE_HISTORY_LIMIT <= 10, EVIDENCE_HISTORY_LIMIT

    for index in range(EVIDENCE_HISTORY_LIMIT + 3):
        _attempt(f"질의 {index}")

    items = latest_search_evidence()

    # 상수를 따라가지 않고 **독립적으로** 잰다: 상한을 키우는 변이도 여기서 죽는다.
    assert len(items) <= 10, len(items)
    assert len(items) == EVIDENCE_HISTORY_LIMIT
    assert items[0].query == f"질의 {EVIDENCE_HISTORY_LIMIT + 2}"
    assert evidence_snapshot(2)["count"] == 2


def test_the_evidence_ring_never_holds_more_than_the_history_limit() -> None:
    """링의 **실제 크기**를 큰 limit 으로 직접 본다 — 무계 링(변이 S15)은 이 줄에서만 죽는다.

    왜 별도 시험인가: `latest_search_evidence()` 는 호출 limit 으로 **잘라서** 돌려주므로,
    무계 링이어도 기본 limit(5) 만큼만 보여 기본 시험은 초록이었다(이빨이 지적한 구멍 1건).
    """
    for index in range(30):
        record_search_evidence(SearchEvidence(query=f"질의 {index}", ok=True, route="bundled"))

    items = latest_search_evidence(limit=1000)

    assert len(items) <= 10, f"링이 총 검색 수를 따라 자랐다: {len(items)}"
    assert len(items) == EVIDENCE_HISTORY_LIMIT
    assert items[0].query == "질의 29"


# ── 5. 재시도·연결 확인 ──────────────────────────────────────────────────────


def test_retry_closes_the_circuit_and_reports_the_truth_about_a_broken_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "bin" / "ssak-mcp"
    missing.parent.mkdir(parents=True, exist_ok=True)
    enable(tmp_path, missing, monkeypatch)
    # 실행 파일이 없으니 시작은 실패한다 — 그 사실을 그대로 보고해야 한다.
    first = search_with_bundled_provider("실패", settings=settings_snapshot())
    assert first.ok is False

    snapshot = retry_availability(timeout=6.0)

    assert snapshot["retried"] is True
    assert snapshot["availability"] == UNAVAILABLE
    assert snapshot["label"] == AVAILABILITY_LABELS[UNAVAILABLE]
    assert snapshot["recoverable"] is True
    assert snapshot["ready"] is False
    assert snapshot["runtime"]["circuit_open"] is True or snapshot["runtime"]["last_error"]


def test_probe_failure_does_not_fall_back_to_the_legacy_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """질문은 "번들이 되느냐"다 — transient 실패에도 legacy 로 답을 바꾸면 답이 사라진다.

    spy 가 의미를 갖는 이유: 여기 설정은 `fallback=legacy_on_transient` 이고 실패는 transient
    (`RUNTIME_NOT_READY`)라, 라우팅 계층을 지났다면 legacy 가 **반드시** 불렸을 것이다.
    """
    calls: list[str] = []

    async def spy(self: object, *args: object, **kwargs: object) -> object:
        calls.append(str(args[0] if args else kwargs.get("query")))
        raise AssertionError("legacy 엔진이 호출됐다")

    monkeypatch.setattr("antigravity_k.tools.web_search_engine.WebSearchEngine.search", spy)
    missing = tmp_path / "bin" / "ssak-mcp"
    missing.parent.mkdir(parents=True, exist_ok=True)
    enable(tmp_path, missing, monkeypatch, fallback="legacy_on_transient")

    result = probe_search("대체 금지", timeout=8.0)

    assert result["ok"] is False
    assert calls == []
    evidence = result["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["ok"] is False
    assert evidence["error_code"] in {"RUNTIME_NOT_READY", "ARTIFACT_REJECTED", "CHILD_EXITED", "CIRCUIT_OPEN"}


def test_probe_refuses_when_search_is_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_CONFIG_FILE", str(write_config(tmp_path, {"enabled": False})))
    monkeypatch.delenv("AGK_SEARCH_SSAK_ENABLED", raising=False)

    result = probe_search("꺼짐")

    assert result["ok"] is False
    evidence = result["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["error_code"] == "RUNTIME_DISABLED"


def test_probe_through_the_api_returns_one_call_of_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    enable(tmp_path, bundle(tmp_path), monkeypatch)
    client = TestClient(app)

    response = client.post("/api/search/probe", json={"query": "연결 확인", "max_results": 3})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["evidence"]["ok"] is True
    assert len(body["evidence"]["sources"]) == 2
    # 상태 응답도 같은 시도를 본다(화면이 두 번 묻지 않아도 된다).
    status = client.get("/api/search/status").json()
    assert status["evidence"][0]["query"] == "연결 확인"


def test_probe_rejects_an_empty_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_CONFIG_FILE", str(write_config(tmp_path, {"enabled": False})))
    client = TestClient(app)

    response = client.post("/api/search/probe", json={"query": "   "})

    assert response.status_code == 400


def test_evidence_endpoint_honours_the_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    enable(tmp_path, bundle(tmp_path), monkeypatch)
    client = TestClient(app)
    assert client.post("/api/search/probe", json={"query": "일"}).status_code == 200
    assert client.post("/api/search/probe", json={"query": "이"}).status_code == 200

    response = client.get("/api/search/evidence", params={"limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["evidence"][0]["query"] == "이"


def test_bundled_runtime_config_carries_the_effective_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = bundle(tmp_path)
    enable(tmp_path, shim, monkeypatch)

    config = bundled_runtime_config(settings_snapshot())

    assert config.enabled is True
    assert config.artifact_path == str(shim)
    assert config.manifest_path is not None and config.manifest_path.endswith("ssak-search-manifest.json")
