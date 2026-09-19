"""CR-14 F-42 — 브라우저 증인에게 **게이트 소유자**를 준다.

왜 필요한가
===========
attempt-030/031 은 실 브라우저 증인으로 F-39·F-41 을 닫았고, 그때 그린 경계 문서(§2-6·§2-7)는
자기 한계로 이렇게 적었다: *"실 브라우저 증인 셋은 모두 수동이고, required 21개 중 어느 것도
이들을 돌리지 않는다."* 그 문장은 정직했지만, 다음 attempt 가 없으면 **영원히 참**이다.

측정된 사실(attempt-032)
========================
- `dashboard/e2e/tests/cr*.spec.ts` — **9파일 29건** — 은 어느 required 게이트도 돌리지 않았다:
  `accessibility-e2e` 는 `accessibility.spec.ts` **한 파일**만 실행한다. CI(`ci.yml`)의 full
  suite 는 `push`/`pull_request`(**main**)에서만 돌고, 게이트 절차(`run_attempt_close.py`)·
  주간(`ga-close.yml`)·릴리스(`release.yml` → ga-close)는 **어느 것도** 그 슈트를 부르지 않는다.
  그래서 F-39·F-37·F-35 같은 결함을 찾아낸 증인들은 **사람이 기억해서 돌려야만** 돌았다.
- 그 증인들은 **ambient 백엔드 없이** 돈다(스스로 서버를 띄우거나 화면만 본다) — 실측
  `29 passed(43.5s)`. 즉 게이트로 세울 수 있었는데 세우지 않았고, 그것이 이 결함의 전부다.

무엇을 소유하는가
=================
이 계약은 **커버리지 주장** 하나를 소유한다: "required 게이트 하나가 그 패밀리를 돈다."
게이트 목록은 manifest 가, 스킵 분류는 등록부가 소유한다 — 여기서 재는 것은 그 둘을 잇는
**전수성**이다: 증인을 새로 만들면 **그 자리에서** 멈춘다(이 저장소에서 반복된 병은
"검사가 사라지는 경로"였고, 여기서 사라지는 것은 **검사 자체**였다).

재지 않는 것
============
- **게이트가 실제로 초록인지**는 게이트 실행이 답한다 — 이 계약은 `pnpm`·브라우저를 부르지 않는다
  (그 주장은 편입된 보고서를 마감 검사가 읽는 자리, 즉 attempt 의 실측이다).
- **ambient 백엔드가 필요한 스펙**(`task-execution`·`ws-contract-e2e`·`file-explorer` 등,
  CLI 로 서버를 띄워 `AGK_BACKEND_URL` 을 주는 CI job 에서만 돈다)은 **여전히 required 게이트
  밖**이다. 이 계약은 그 사실을 지우지 않는다 — 오히려 아래 세 번째 조항이 그 경계를 고정한다
  (게이트 선택자가 그 스펙들을 삼키면 게이트가 게이트 환경에서 빨개진다).
- **증인의 내용이 옳은지**(무엇을 재는가)는 이 계약의 소관이 아니다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_MANIFEST = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
SKIP_REGISTER = REPO_ROOT / "scripts" / "gate_skip_register.json"
E2E_TESTS = REPO_ROOT / "dashboard" / "e2e" / "tests"

WITNESS_GATE_ID = "dashboard-e2e-witnesses"
# 이 게이트가 소유하는 파일 패밀리 — 이름이 아니라 **접두사**다. 그래야 새 증인이 자동으로 들어온다.
WITNESS_FAMILY = re.compile(r"^cr\d+-.*\.spec\.ts$")
# 게이트 밖에 **남아야** 하는 스펙(ambient 백엔드 필요 — CLI 로 서버를 띄운 CI job 의 슬라이스).
AMBIENT_SPECS = ("accessibility.spec.ts", "task-execution.spec.ts", "ws-contract-e2e.spec.ts")


def _manifest() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(GATE_MANIFEST.read_text(encoding="utf-8"))
    return payload


def _witness_gate() -> dict[str, Any]:
    for gate in _manifest()["gates"]:
        if gate["id"] == WITNESS_GATE_ID:
            return cast(dict[str, Any], gate)
    raise AssertionError(f"게이트 {WITNESS_GATE_ID} 가 manifest 에 없다")


def _selector() -> re.Pattern[str]:
    """게이트 명령이 playwright 에 넘기는 **파일 선택자**(위치 인자)를 정규식으로 읽는다.

    선택자를 계약에 다시 적지 않는다 — 명령에서 읽는다. 두 곳이 같은 규칙을 손으로 들고 있으면
    갈라지고, 갈라진 쪽은 **아무것도 재지 않는다**(이 저장소에서 반복된 병).
    """
    command = [str(token) for token in _witness_gate()["command"]]
    positional = [token for token in command if token.endswith(".spec.ts") or "e2e/tests/" in token]
    assert len(positional) == 1, f"선택자가 하나여야 한다(명령에서 위치 인자): {command}"
    return re.compile(positional[0])


def _as_playwright_sees(name: str) -> str:
    r"""playwright 는 위치 인자를 **파일 경로 전체**에 대한 정규식으로 본다.

    그래서 계약도 같은 문자열에 물린다 — 파일 이름만 보면 선택자(`e2e/tests/cr\d+-`)와 어긋나
    **계약이 거짓 실패**한다(실측: 이 조항의 첫 판본이 그랬고, 그 실패는 자의 결함이었다).
    """
    return f"e2e/tests/{name}"


def _witness_files() -> list[str]:
    return sorted(path.name for path in E2E_TESTS.glob("*.spec.ts") if WITNESS_FAMILY.match(path.name))


# ─── 게이트 자체: required 이고, 귀속 플래그를 명령이 갖는다 ──────────────


def test_the_witness_gate_is_required_and_pins_its_own_environment() -> None:
    """게이트는 required 이고, 프로젝트·리포터를 **명령에서** 고정한다.

    `--reporter=list` 를 설정(`playwright.config.ts`)에 기대지 않는 이유: 등록부가 스킵의 귀속을
    그 리포터에 걸어 두었고, 설정을 바꾸면 그 게이트의 스킵이 **익명**이 된다. 게이트가 자기
    리포터를 들고 있으면 그 위험이 게이트에 닿지 않는다.
    """
    gate = _witness_gate()
    assert gate["required"] is True, "브라우저 증인 게이트가 required 가 아니다"
    assert str(gate["cwd"]) == "dashboard", f"cwd 가 dashboard 가 아니다: {gate['cwd']}"
    command = [str(token) for token in gate["command"]]
    assert "--project=chromium" in command, f"프로젝트 고정이 없다: {command}"
    assert "--reporter=list" in command, f"스킵을 이름으로 내는 리포터가 명령에 없다: {command}"


# ─── 전수성: 증인 패밀리의 **모든** 파일이 그 게이트 안이다 ────────────────


def test_every_cr_witness_file_is_matched_by_the_gate_selector() -> None:
    """`cr*.spec.ts` 전부가 선택자에 걸린다 — 새 증인도 **자동으로** 게이트 안이다(F-42).

    개수를 손으로 맞추지 않는 이유는 F-21 이 개수 고정을 목록 고정으로 바꾼 것과 같다:
    세어 두면 하나를 빼고 하나를 넣어도 통과한다.
    """
    files = _witness_files()
    assert files, "게이트가 돌릴 증인 파일이 하나도 없다 — 선택자가 낡았거나 증인이 사라졌다"
    selector = _selector()
    unmatched = [name for name in files if not selector.search(_as_playwright_sees(name))]
    assert not unmatched, f"증인인데 게이트 선택자에 걸리지 않는다: {unmatched} — 그 파일은 아무도 돌리지 않는다(F-42)"


def test_the_selector_does_not_swallow_specs_that_need_an_ambient_backend() -> None:
    """선택자는 증인 패밀리에서 멈춘다 — ambient 백엔드가 필요한 스펙을 삼키면 게이트가 빨개진다.

    실측(attempt-032): ambient 백엔드 없이 full suite 를 돌리면 **12건**이 실패한다
    (`task-execution`·`ws-contract-e2e`·`file-explorer`·`capture-*`). 그 스펙들을 선택자가
    삼키면 이 required 게이트는 **게이트 환경에서 항상 실패**하고, 사람은 게이트를 끄는 쪽을
    고른다 — 그래서 경계 자체를 계약이 고정한다.
    """
    selector = _selector()
    swallowed = [name for name in AMBIENT_SPECS if selector.search(_as_playwright_sees(name))]
    assert not swallowed, (
        f"게이트가 ambient 백엔드가 필요한 스펙을 삼킨다: {swallowed} — 그 슬라이스는 CI 의 "
        "full-suite job 이 소유하고, required 게이트에는 그 서버를 세우는 단계가 없다"
    )
    for name in AMBIENT_SPECS:
        assert (E2E_TESTS / name).is_file(), f"기준선으로 삼은 스펙이 없다: {name}"


def test_teeth_a_new_witness_cannot_be_born_unowned() -> None:
    """이빨 — 선택자가 **이름 규칙**이 아니라 목록이면 이 계약이 문다.

    두 방향을 함께 잰다: ① 가족 이름(`cr15-...`)은 선택자를 통과한다(전수성의 근거)
    ② 가족 밖 이름(`witness-15-...`)으로 증인을 만들면 같은 조항이 **실패**한다
    (목록 고정으로 되돌아가면 이빨이 무뎌진다).
    """
    selector = _selector()
    assert selector.search(_as_playwright_sees("cr15-new-witness.spec.ts")), (
        "가족 이름으로 만든 새 증인이 선택자를 통과하지 않는다 — 전수성이 목록 고정으로 퇴화했다"
    )
    assert WITNESS_FAMILY.match("cr15-new-witness.spec.ts")
    assert not WITNESS_FAMILY.match("witness-15-new.spec.ts"), (
        "가족 밖 이름도 증인으로 세면 `_witness_files()` 가 줄어들지 않는다 — 그러면 증인을 "
        "게이트 밖에 만드는 경로가 조용히 열린다"
    )


# ─── 스킵 가시성: 새 게이트도 소유자가 있어야 한다 ─────────────────────────


def test_the_witness_gate_is_classified_for_skip_visibility() -> None:
    """required 게이트를 늘렸으면 등록부의 분류도 함께 적는다 — 여기서 그 짝을 확인한다.

    (전수성 자체는 `test_cr14_gate_skip_register.py` 가 잰다: 이 조항은 그 게이트가 **어떻게**
    분류됐는지까지 본다 — playwright 의 스킵은 `list` 리포터가 이름으로 내고, 그 관측 자리는
    마감 검사다.)
    """
    register = json.loads(SKIP_REGISTER.read_text(encoding="utf-8"))
    entries = cast(list[dict[str, Any]], register["gate_visibility"]["gates"])
    matching = [entry for entry in entries if entry["gate"] == WITNESS_GATE_ID]
    assert len(matching) == 1, f"등록부에 {WITNESS_GATE_ID} 분류가 정확히 하나가 아니다: {len(matching)}"
    entry = matching[0]
    assert entry["runner"] == "playwright", entry
    assert entry["attribution"] == "per_test", entry
    assert entry["observation"] in {"registered", "close_check"}, entry
    assert "cr" in str(entry["how"]), (
        "분류의 how 가 이 게이트의 **대상 집합**을 말하지 않는다 — 그러면 누구도 그 경계를 다시 못 찾는다"
    )
