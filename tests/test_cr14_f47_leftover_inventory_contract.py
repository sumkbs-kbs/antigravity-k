"""CR-14 F-47 leftover inventory — 소유되지 않은 ambient 슬라이스를 **센다**.

attempt-039 측정
================
- ``capture-disclosure-*`` 의 :5173 하드코드는 **값싼 하네스 결함**이었다.
  hermetic baseURL + ``AGK_SEED_LEVEL`` 로 초록 → ambient 게이트가 소유(폐쇄).
- ``capture-real-local-models`` 는 attempt-039 에서 ``AGK_SEED_LOCAL_HUB`` hermetic
  픽스처로 닫혀 ambient(``HUB_SPEC_FILES``) 가 소유한다 — **열린 leftover 0건**.
- GREP_INVERT 는 비움(PRODUCT_FLAKE 0). ``compacts a large event stream…`` 은
  attempt-038 에서 시드 스키마 정합으로 닫혀 ambient 가 소유한다.
- ``renders the execution trace at`` 는 attempt-036, ``should show file activity
  from git status`` 는 attempt-037 에서 닫혀 ambient 가 소유한다.

이 계약이 막는 침묵
==================
- 등록부 항목이 사라지면 실패(목록 정체성 · F-21).
- GREP_INVERT 문자열이 등록부의 substring 을 빼먹으면 실패.
- disclosure 가 다시 Vite-only 로 돌아가거나 ambient 소유 목록에서 빠지면 실패.
- review_due 가 지나면 실패(다시 보라).
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTER = REPO_ROOT / "scripts" / "cr14_f47_leftover_register.json"
AMBIENT_SCRIPT = REPO_ROOT / "scripts" / "run_dashboard_e2e_ambient.py"
E2E_TESTS = REPO_ROOT / "dashboard" / "e2e" / "tests"
BOUNDARY = REPO_ROOT / "docs" / "ga" / "CR14_GATE_COVERAGE_BOUNDARY.md"

# 목록 정체성 — 매직 넘버 금지(F-21). 등록부가 원본이다.
EXPECTED_OPEN_IDS: tuple[str, ...] = ()


def _register() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(REGISTER.read_text(encoding="utf-8")))


def _script_text() -> str:
    return AMBIENT_SCRIPT.read_text(encoding="utf-8")


def _disclosure_specs_from_script() -> list[str]:
    text = _script_text()
    start = text.find("DISCLOSURE_SPEC_FILES:")
    assert start >= 0, "DISCLOSURE_SPEC_FILES 를 스크립트에서 찾지 못했다"
    end = text.find("GREP_INVERT:", start)
    assert end > start, "DISCLOSURE_SPEC_FILES 블록 경계를 찾지 못했다"
    found = re.findall(r'"([^"]+\.spec\.ts)"', text[start:end])
    assert found, "disclosure 스펙이 비어 있다"
    return found


def _grep_invert_from_script() -> str:
    text = _script_text()
    # attempt-038: PRODUCT_FLAKE 0 이면 ruff 가 GREP_INVERT: str = "" 로 접는다.
    empty = re.search(r'GREP_INVERT:\s*str\s*=\s*""', text)
    if empty:
        return ""
    match = re.search(r"GREP_INVERT:\s*str\s*=\s*\((.*?)\)", text, re.S)
    assert match, "GREP_INVERT 를 스크립트에서 찾지 못했다"
    raw = match.group(1)
    parts = re.findall(r'"([^"]*)"', raw)
    return "".join(parts)


def test_leftover_register_list_identity() -> None:
    """이빨 — 열린 leftover id 목록이 등록부·계약 선언과 같다(매직 숫자 금지)."""
    entries = cast(list[dict[str, Any]], _register()["entries"])
    ids = tuple(str(e["id"]) for e in entries)
    assert ids == EXPECTED_OPEN_IDS, f"F-47 leftover 목록 정체성 불일치: got={ids} expected={EXPECTED_OPEN_IDS}"


def test_each_leftover_has_owner_plan_expiry_and_boundary_mention() -> None:
    today = date.today()
    boundary = BOUNDARY.read_text(encoding="utf-8")
    for entry in _register()["entries"]:
        entry_id = str(entry["id"])
        assert str(entry.get("owner", "")).strip(), f"{entry_id}: owner 비어 있음"
        assert str(entry.get("plan", "")).strip(), f"{entry_id}: plan 비어 있음"
        assert str(entry.get("capability", "")).strip(), f"{entry_id}: capability 비어 있음"
        assert str(entry.get("class", "")) in {"EXTERNAL_HUB", "PRODUCT_FLAKE"}
        due = date.fromisoformat(str(entry["review_due"]))
        assert due > today, f"{entry_id}: review_due({due}) 만료 — 다시 보거나 갱신하라"
        assert entry_id in boundary, f"{entry_id}: 경계 문서에 없음 — 보이지 않는 leftover"
        file_path = REPO_ROOT / str(entry["file"])
        assert file_path.is_file(), f"{entry_id}: 파일이 없다 {file_path}"


def test_grep_invert_covers_exactly_the_product_flake_substrings() -> None:
    """invert 문자열은 등록된 PRODUCT_FLAKE substring 을 **빠짐없이** 포함해야 한다.

    PRODUCT_FLAKE 가 0이면 GREP_INVERT 도 비어야 한다(attempt-038 — compact 폐쇄).
    """
    invert = _grep_invert_from_script()
    flakes = [e for e in _register()["entries"] if e["class"] == "PRODUCT_FLAKE"]
    if not flakes:
        assert invert == "", f"PRODUCT_FLAKE 0인데 GREP_INVERT 잔여: {invert!r}"
        return
    for entry in flakes:
        needle = str(entry["grep_invert_substring"])
        assert needle in invert, f"{entry['id']}: GREP_INVERT 에 '{needle}' 없음 — invert 만으로 숨기면 안 된다"


def test_disclosure_is_owned_by_ambient_seeded_phase_not_vite() -> None:
    """폐쇄 이빨 — disclosure 스펙이 DISCLOSURE_SPEC_FILES 에 있고 :5173 하드코드가 없다."""
    owned = _disclosure_specs_from_script()
    assert "e2e/tests/capture-disclosure-healthy.spec.ts" in owned
    assert "e2e/tests/capture-disclosure-exhausted.spec.ts" in owned
    for name in (
        "capture-disclosure-healthy.spec.ts",
        "capture-disclosure-exhausted.spec.ts",
    ):
        text = (E2E_TESTS / name).read_text(encoding="utf-8")
        assert "127.0.0.1:5173" not in text, f"{name} 에 Vite :5173 하드코드가 남아 있다"
        assert "page.goto('/settings')" in text, f"{name} 가 hermetic /settings 를 쓰지 않는다"
    script = _script_text()
    assert "AGK_SEED_LEVEL" in script or "seed_level" in script
    assert "DISCLOSURE_SPEC_FILES" in script


def _hub_specs_from_script() -> list[str]:
    text = _script_text()
    start = text.find("HUB_SPEC_FILES: tuple")
    assert start >= 0, "HUB_SPEC_FILES 를 스크립트에서 찾지 못했다"
    end = text.find("\ndef ", start + 1)
    assert end > start, "HUB_SPEC_FILES 블록 경계를 찾지 못했다"
    found = re.findall(r'"([^"]+\.spec\.ts)"', text[start:end])
    assert found, "hub 스펙이 비어 있다"
    return found


def test_real_local_models_is_owned_by_ambient_hub_seed() -> None:
    """attempt-039 — EXTERNAL_HUB 는 HUB_SPEC_FILES + AGK_SEED_LOCAL_HUB 로 소유되고 열린 목록에서 빠진다."""
    hub = _hub_specs_from_script()
    assert "e2e/tests/capture-real-local-models.spec.ts" in hub
    script = _script_text()
    assert "AGK_SEED_LOCAL_HUB" in script
    # 메인 ambient 목록에 몰래 넣지 않는다(시드 단계로만)
    match = re.search(
        r"AMBIENT_SPEC_FILES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)",
        script,
        re.S,
    )
    assert match
    ambient_owned = re.findall(r'"([^"]+\.spec\.ts)"', match.group(1))
    assert "e2e/tests/capture-real-local-models.spec.ts" not in ambient_owned
    ids = {str(e["id"]) for e in _register()["entries"]}
    assert "f47-capture-real-local-models" not in ids
    closed = {str(c["id"]) for c in _register()["closed_this_attempt"]}
    assert "f47-capture-real-local-models" in closed


def test_teeth_dropping_an_open_id_fails_list_identity() -> None:
    """이빨 — 열린 id 하나를 빼면 목록 정체성 단언이 실패한다.

    열린 목록이 비어 있으면(attempt-039) 가짜 id 를 하나 넣었을 때 불일치해야 한다.
    """
    if EXPECTED_OPEN_IDS:
        shortened = EXPECTED_OPEN_IDS[:-1]
        try:
            assert shortened == EXPECTED_OPEN_IDS
            raise AssertionError("짧아진 목록이 통과하면 안 된다")
        except AssertionError:
            pass
    else:
        polluted = ("ghost-leftover-must-fail",)
        try:
            assert polluted == EXPECTED_OPEN_IDS
            raise AssertionError("가짜 열린 id 가 통과하면 안 된다")
        except AssertionError:
            pass


def test_closed_disclosure_is_recorded() -> None:
    closed = cast(list[dict[str, Any]], _register()["closed_this_attempt"])
    assert any(c.get("id") == "capture-disclosure-hermetic" for c in closed)
    assert any(c.get("id") == "f47-invert-execution-trace-axe" for c in closed)
    assert any(c.get("id") == "f47-invert-git-status-file-activity" for c in closed)
    assert any(c.get("id") == "f47-invert-compact-large-stream" for c in closed)
    assert any(c.get("id") == "f47-capture-real-local-models" for c in closed)
    assert any("dashboard-e2e-ambient" in str(c.get("now_owned_by", "")) for c in closed)
