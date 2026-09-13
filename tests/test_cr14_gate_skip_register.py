"""CR-14 F-30 — 게이트에서 **조용히 사라지는 테스트**를 소유한다 (R-8 감사).

왜 필요한가
===========
게이트 초록은 "이 후보가 검증됐다"는 주장이다. 그런데 **스킵은 그 주장에서 조용히 빠지는
자리**다 — 게이트는 초록인데 그 테스트는 어디서도 돌지 않는다. attempt-011/012 는 ambient
도구로 돌아 성능/의존성 문제를 숨겼고(F-18·F-19), 게이트 환경을 lock 에 고정한 attempt-013
부터 스킵이 **40건**이 됐다. 도구 출처는 바로잡혔지만 **그 대가(커버리지 손실)는 아무도 세지
않았다** — attempt-013 이 스스로 "이 감사를 하지 않았다"고 적었고(R-8), attempt-021 이 그
감사를 수행했다.

감사가 찾은 것
==============
**어떤 파이프라인도 `documents` extra(pypdf)를 설치하지 않았다.** 그래서 출하 능력인
PDF/DOCX 수집을 재는 **23건**이 게이트·CI·weekly 어디서도 돌지 않았다(게이트는 초록).
게이트 환경에 그 extra 를 넣어 23건을 되살렸고(실측 87 passed / 0 skipped), 남은 **17건**을
이 등록부로 옮겼다. 그중 **4건은 어디서도 돌지 않는 제품 능력**이다(에이전트 루프 2건 ·
제품 설정 약속 2건) — 등록부가 그 사실을 소유하고 만료일을 건다.

규칙은 한 곳
============
"무엇이 스킵되는가"의 소유자는 **등록부**(`scripts/gate_skip_register.json`)다. 이 파일은
판정하지 않고 **대조한다**: 등록부와 (a) 스키마·소유자·만료, (b) **실제로 돌린 게이트 환경의
스킵 집합**을 한 건씩 맞춘다. 등록되지 않은 스킵이 생기면 실패한다(무엇이 사라졌는지 적어라).
등록된 스킵이 사라져도 실패한다(등록부가 낡았다). 양쪽 다 "조용한 변화 금지"의 구현이다.

관측 목록은 선언에서 파생하지 않는다 (attempt-022 가 찾은 구멍)
=============================================================
처음에는 관측 대상 파일을 `entries` 의 스킵 목록에서 파생했다. 그러면 **항목을 닫는 순간**
그 파일이 관측에서도 사라진다 — 능력을 되찾아 스킵이 0이 된 파일이 다시 스킵되기 시작해도
아무도 모른다(무엇보다 **닫는 일이 관측을 줄인다**: 보상을 뒤집은 셈이다). 그래서 관측 대상은
등록부가 `observed_files` 로 **고정**하고(선언된 파일을 모두 포함해야 한다), 닫힌 항목은
`closed` 에 적혀 그 파일이 계속 관측된다 — 그 파일에 스킵이 돌아오면 대조가 즉시 실패한다.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTER_FILE = REPO_ROOT / "scripts" / "gate_skip_register.json"
GATE_FILE = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
BOUNDARY_DOC = REPO_ROOT / "docs" / "ga" / "CR14_GATE_COVERAGE_BOUNDARY.md"

# 스킵을 실제로 관측하는 게이트 — 게이트 환경(도구 출처)의 소유자다.
OBSERVED_GATE_ID = "python-tests"
SKIP_LINE = re.compile(r"^SKIPPED \[(\d+)\] ([^:]+):\d+: (.*)$")

VALID_CLASSES = ("ENV_PLATFORM", "ENV_CONFIG", "KNOWN_GAP")

requires_uv = pytest.mark.skipif(shutil.which("uv") is None, reason="uv 없이는 게이트 환경을 잴 수 없다")


def _register() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(REGISTER_FILE.read_text(encoding="utf-8"))
    return payload


def _declared_skips() -> Counter[tuple[str, str]]:
    """등록부가 선언한 (파일, 사유) → 건수. 등록부가 스킵의 유일한 선언 자리다."""
    counted: Counter[tuple[str, str]] = Counter()
    for entry in _register()["entries"]:
        for skip in entry["skips"]:
            counted[(str(skip["file"]), str(skip["reason"]))] += int(skip["count"])
    return counted


def _gate_prefix() -> list[str]:
    """게이트 `python-tests` 의 **환경 접두사**(도구 토큰 앞까지) — 게이트 파일이 소유한다."""
    payload = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    for gate in payload["gates"]:
        if gate["id"] != OBSERVED_GATE_ID:
            continue
        command = [str(token) for token in gate["command"]]
        index = 2
        while index < len(command) and command[index].startswith("-"):
            index += 2 if command[index] == "--extra" else 1
        return command[:index]
    raise AssertionError(f"게이트 파일에서 {OBSERVED_GATE_ID} 를 찾지 못했다")


def _observed_files() -> list[str]:
    """관측 대상 파일 — 등록부가 **고정 목록**으로 소유한다(선언에서 파생하지 않는다)."""
    return sorted({str(name) for name in _register()["observed_files"]})


def _observed_skips() -> Counter[tuple[str, str]]:
    """게이트 환경을 **그대로 재현해** 실제로 스킵된 (파일, 사유) → 건수를 센다.

    `--extra` 목록은 게이트 파일에서 읽는다: 그래서 F-30 의 수정(출하 extra 를 게이트에
    넣는다)이 이 관측에도 그대로 반영되고, 누군가 그 extra 를 빼면 23건이 다시 스킵되어
    **여기서** 드러난다.
    """
    files = _observed_files()
    command = [*_gate_prefix(), "pytest", *files, "-q", "-rs", "--no-header"]
    completed = subprocess.run(  # noqa: S603 — 게이트 환경 접두사 + 이 계약의 대상 파일
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise AssertionError(f"게이트 환경 재현이 실패했다(exit {completed.returncode}):\n{completed.stderr[-2000:]}")

    counted: Counter[tuple[str, str]] = Counter()
    for line in (completed.stdout + completed.stderr).splitlines():
        match = SKIP_LINE.match(line.strip())
        if match:
            counted[(match.group(2), match.group(3))] += 1
    return counted


def _as_lines(counter: Counter[tuple[str, str]]) -> list[str]:
    return [f"{counted}건  {file}  ← {reason}" for (file, reason), counted in sorted(counter.items())]


# ─── 스키마: 등록부가 스스로 완전한가 ─────────────────────────────────


def test_every_registered_skip_is_well_formed() -> None:
    """등록부 — 모든 항목이 분류·이유·실재 파일·양수 건수를 갖는다."""
    register = _register()
    assert register["entries"], "등록부가 비어 있다 — 그 자체가 스킵이 사라졌다는 주장이다"

    seen: set[str] = set()
    for entry in register["entries"]:
        entry_id = str(entry["id"])
        assert entry_id not in seen, f"등록부 id 가 중복이다: {entry_id}"
        seen.add(entry_id)
        assert entry["class"] in VALID_CLASSES, f"{entry_id}: 알 수 없는 class {entry['class']!r}"
        assert str(entry["why"]).strip(), f"{entry_id}: why 가 비었다 — 왜 허용되는 스킵인지 적어라"
        assert entry["skips"], f"{entry_id}: skips 가 비었다 — 스킵하지 않는 항목은 등록부에 두지 않는다"
        for skip in entry["skips"]:
            assert (REPO_ROOT / str(skip["file"])).is_file(), f"{entry_id}: 파일이 없다 {skip['file']}"
            assert str(skip["reason"]).strip(), f"{entry_id}: reason 이 비었다"
            assert int(skip["count"]) > 0, f"{entry_id}: count 는 1 이상이어야 한다"


def test_declared_counts_are_unique_per_file_and_reason() -> None:
    """(파일, 사유)는 등록부에서 **한 번만** 선언된다 — 두 항목이 같은 스킵을 주장하면 대조가 무의미해진다."""
    counted = _declared_skips()
    declared_pairs = [
        (str(skip["file"]), str(skip["reason"])) for entry in _register()["entries"] for skip in entry["skips"]
    ]
    assert len(declared_pairs) == len(set(declared_pairs)), "같은 (파일, 사유)가 여러 항목에 있다"
    assert sum(counted.values()) > 0, "등록부가 한 건도 선언하지 않는다"


def test_observed_files_cover_every_declared_skip_and_exist() -> None:
    """관측 목록 — 선언된 파일을 모두 포함하고, **닫힌 항목의 파일도 잃지 않는다**.

    닫는 일이 관측을 줄이면 안 된다: 닫힌 파일이 관측에서 빠지는 순간 그 자리가 다시 열려도
    계약은 침묵한다. 그래서 `closed` 의 파일도 관측 목록에 있어야 한다.
    """
    observed = set(_observed_files())
    declared = {file for file, _ in _declared_skips()}
    assert declared <= observed, (
        f"선언된 스킵 파일이 관측 목록에 없다: {sorted(declared - observed)} — 그 파일은 재현되지 않아 대조되지 않는다"
    )
    for name in sorted(observed):
        assert (REPO_ROOT / name).is_file(), f"관측 목록에 없는 파일이 있다: {name}"

    for entry_id, closed in cast(Mapping[str, Mapping[str, object]], _register().get("closed") or {}).items():
        assert int(cast(int, closed["skips"])) > 0, f"closed.{entry_id}: 닫은 스킵 수가 0 이다"
        assert str(closed["how"]).strip(), f"closed.{entry_id}: 어떻게 닫았는지 적어라"
        for name in cast(Sequence[object], closed["files"]):
            assert str(name) in observed, (
                f"closed.{entry_id}: 닫은 파일 {name} 이 관측 목록에 없다 — 닫은 자리가 다시 열려도 보이지 않는다"
            )


# ─── 소유자: 스킵을 정당화하는 파이프라인이 실제로 도는가 ────────────────


def test_platform_entries_name_a_pipeline_that_actually_runs_them() -> None:
    """ENV_PLATFORM — `owner_run` 의 파일 이름이 owner 워크플로 안에 **실재해야** 한다.

    "다른 job 이 돌린다"는 주장은 그 job 의 파일을 읽어 확인한다: 주장만 적어 두고 아무도
    돌리지 않는 상태(가장 흔한 거짓)를 계약이 막는다.
    """
    for entry in _register()["entries"]:
        if entry["class"] != "ENV_PLATFORM":
            continue
        owner = REPO_ROOT / str(entry["owner"])
        assert owner.is_file(), f"{entry['id']}: owner 워크플로가 없다 {entry['owner']}"
        workflow = owner.read_text(encoding="utf-8")
        runs = [str(name) for name in entry.get("owner_run", [])]
        assert runs, f"{entry['id']}: owner_run 이 비었다 — 어느 파일을 도는지 밝혀라"
        for name in runs:
            assert name in workflow, (
                f"{entry['id']}: {entry['owner']} 가 {name} 를 돌리지 않는다 — 그 능력은 아무도 재지 않는다"
            )


def test_config_entries_point_at_the_gate_that_measures_the_same_boundary() -> None:
    """ENV_CONFIG — 같은 경계를 재는 파일을 가리키고, **등록부가 그 파일을 스킵으로 선언하지 않는다**.

    두 조각이 이 주장을 완성한다(각각 다른 자리가 소유한다):
      ① 여기서는 **등록부 안의 자기모순**을 본다 — "X 가 대신 잰다"고 적으면서 동시에 X 를
         스킵으로 적으면 그 경계는 아무도 안 잰다.
      ② 런타임 쪽은 아래 `test_gate_environment_skips_exactly_what_the_register_declares` 가
         소유한다 — 관측이 등록부와 달라지면 실패하므로, X 가 실제로 스킵되기 시작하면
         (선언하지 않았어도) 그 자리에서 드러난다.

    여기서 ②를 다시 재지 않는 이유: 같은 실행을 두 번 돌리면 계약이 느려지고, 측정을 두 곳이
    들고 있으면 갈라진다(F-27 의 병).
    """
    declared = _declared_skips()
    for entry in _register()["entries"]:
        if entry["class"] != "ENV_CONFIG":
            continue
        covering = REPO_ROOT / str(entry["owner"])
        assert covering.is_file(), f"{entry['id']}: owner 파일이 없다 {entry['owner']}"
        assert str(entry.get("note", "")).strip(), f"{entry['id']}: note 가 비었다 — 무엇이 대신 재는가"
        covered = {file for file, _ in declared if file == str(entry["owner"])}
        assert not covered, (
            f"{entry['id']}: 등록부가 대신 잰다는 {entry['owner']} 마저 스킵으로 적고 있다"
            " — 그러면 그 경계는 아무도 안 잰다(자기모순)"
        )


def test_known_gaps_are_owned_and_expire() -> None:
    """KNOWN_GAP — 미검증 능력은 **소유자·계획·만료일**을 갖고, 판정서 경계 문서에도 적힌다.

    만료일이 지나면 계약이 실패한다: 그 자리를 다시 보라는 뜻이다(감사 예외의 만료와 같은 규율).
    """
    register = _register()
    boundary = BOUNDARY_DOC.read_text(encoding="utf-8")
    today = date.today()

    for entry in register["entries"]:
        if entry["class"] != "KNOWN_GAP":
            continue
        entry_id = str(entry["id"])
        assert str(entry["owner"]).strip(), f"{entry_id}: owner 가 비었다"
        assert str(entry["plan"]).strip(), f"{entry_id}: plan 이 비었다 — 어떻게 닫을 것인가"
        assert str(entry.get("capability", "")).strip(), f"{entry_id}: capability 가 비었다 — 무엇이 미검증인가"
        due = date.fromisoformat(str(entry["review_due"]))
        assert due > today, f"{entry_id}: review_due({due}) 가 지났다 — 이 미검증 능력을 다시 보거나 계획을 갱신하라"
        assert entry_id in boundary, (
            f"{entry_id}: 경계 문서({BOUNDARY_DOC.name})에 적히지 않았다 — 보이지 않는 결함이다"
        )


# ─── 대조: 게이트 환경이 실제로 스킵하는 것과 같은가 ─────────────────────


@requires_uv
def test_gate_environment_skips_exactly_what_the_register_declares() -> None:
    """기능 계약 — 게이트 환경을 재현해 스킵 집합을 **한 건씩** 대조한다.

    실패하는 두 방향 모두 뜻이 있다: 관측이 더 많으면 **등록되지 않은 스킵이 생겼다**
    (커버리지가 조용히 줄었다), 관측이 더 적으면 **등록부가 낡았다**(능력이 돌아왔거나
    스킵이 다른 사유로 바뀌었다). 어느 쪽이든 사람이 그 변화를 적어야 한다.
    """
    observed = _observed_skips()
    declared = _declared_skips()

    assert observed == declared, (
        "게이트 환경의 스킵 집합이 등록부와 다르다.\n"
        f"  등록부에만 있음: {_as_lines(declared - observed)}\n"
        f"  관측에만 있음:   {_as_lines(observed - declared)}"
    )
