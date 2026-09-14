"""CR-14 — **런타임 상태는 코드 스코프 밖에 있다**: 상대경로 기본값이 코드 지문을 옮기지 못하게 한다.

attempt-033 에서 실제로 일어난 일 (F-44)
========================================
attempt-033 은 `python-tests` 배치를 **완주하고도** 마감 검사에서 멈출 뻔했다. 원인은 코드가 아니라
**측정 트리**였다: 작업 트리에는 후보 커밋에 없는 경로 **한 개**가 더 있었고, 그 경로가 지문 스코프
안이었다.

    ONLY IN WORKTREE: ['src/data/projects.json']   count 1
    worktree_fingerprint(.)      = e116d58d…
    tree_fingerprint_of_commit(ec76c7ce) = f8cab12b…

그 파일은 **제품이 쓴 런타임 상태**다 — `project_registry.py:31` 의
`_DEFAULT_STORAGE_PATH = Path("data/projects.json")` 는 **상대경로**이고, 그래서 cwd 에 따라 위치가
정해진다. cwd 가 `src/` 인 프로세스(패키지를 소스 트리에서 직접 `-m uvicorn` 으로 띄우면 자연스럽다:
`src/` 가 곧 import 루트다)는 `src/data/projects.json` 을 만들고, 그때 등록되는 기본 프로젝트는
**cwd 의 이름**을 갖는다(실측: `{"id": "default", "name": "src", "path": "…/Ssak-Ai/src"}`).

왜 이것이 CR-14 의 문제인가
===========================
`ga_gate` 의 코드 지문은 `git ls-files --cached --others --exclude-standard` 를 읽는다 — **추적 +
무시되지 않은 미추적** 파일이다. 즉 `docs/`·`.omo/` 를 뺀 나머지 스코프에서 git 이 모르는 파일도
지문 **안**이다. 그래서 런타임 상태가 하나 생기는 것만으로

  * 보고서의 `tree_fingerprint`(작업 트리) ≠ **후보 커밋의 코드 트리** 지문이 되고,
  * 그 결과 `verify_attempt_close.py` 항목 2·3 이 \"선언된 지문을 측정한 보고서가 없다\"로 **마감을
    거부**하며,
  * 게이트 배치 자체는 **초록으로 통과한다**(탐지가 마감까지 늦는다 — 늦게라도 잡히는 것이 유일한
    탐지기라는 사실이 attempt-025 의 F-34 와 같은 구조다).

루트의 같은 파일(`data/projects.json`)은 이미 무시되고 있었다(`.gitignore` 175행). 빠진 것은 **cwd 가
`src/` 인 경우**뿐이다 — 즉 이 결함은 \"제품이 자기 상태를 어디에 두는가\"와 \"코드 스코프가 무엇인가\"의
경계가 **한 곳에서만** 선언돼 있던 것이다.

이 파일이 고정하는 것
=====================
  C14-F44-1  레지스트리의 기본 저장 경로가 **제품 소스에서** 온다(하드코딩하면 제품이 옮겨도 통과한다).
  C14-F44-2  이 저장소가 실제로 Python 프로세스를 띄우는 **각 cwd 루트**에서 그 경로가 무시된다 —
             잠금 파일(`<저장경로>.lock`)까지. (`project_registry.py` 는 저장 경로 옆에 flock 파일을 만든다.)
  C14-F44-3  **측정**: 지금 이 작업 트리의 코드 스코프(게이트가 쓰는 바로 그 목록)에 그 후보 경로가
             **하나도 없다**. 규칙을 믿지 않고 게이트의 함수로 잰다.
  C14-F44-4  이빨 — 임시 저장소에서 규칙을 **떼면** 같은 측정이 실패한다(규칙이 실제로 일을 한다).

`C14-F44-2` 의 cwd 루트 목록은 **증거가 있는 것만** 적는다: 저장소 루트(제품의 문서화된 실행 방식 —
`.gitignore` 175행이 이미 그 자리를 덮고 있다)와 `src/`(패키지 import 루트 — 이 결함이 실제로 난 자리).
새 루트가 생기면 여기에 이유와 함께 추가한다: 이 계약은 \"우리가 띄우는 모든 cwd\"를 주장하지 않는다.

이 파일이 검사하지 **않는** 것: 기본 저장 경로가 상대경로라는 **설계 자체**의 옳고 그름(그것은
인계 문서가 다음 attempt 에 남긴다 — 근본 고침은 기본값을 저장소 루트나 `AGK_PATH_*` 설정에
묶는 것이고, 그 변경은 제품 동작을 바꾸므로 별도 attempt 의 몫이다).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE_SCRIPT = REPO_ROOT / "scripts" / "ga_gate.py"
_REGISTRY_SOURCE = REPO_ROOT / "src" / "antigravity_k" / "engine" / "project_registry.py"

# 이 저장소가 실제로 Python 프로세스를 띄우는 cwd 루트 — **이유가 있는 것만** 적는다(C14-F44-2).
_CWD_ROOTS: tuple[tuple[str, str], ...] = (
    (".", "제품의 문서화된 실행 방식(저장소 루트에서 `uv run uvicorn …`) · `.gitignore` 가 이미 덮던 자리"),
    ("src", "패키지 import 루트 — 소스 트리에서 `-m uvicorn` 으로 띄우면 cwd 가 여기다(F-44 가 난 자리)"),
)


def _load_gate_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cr14_ga_gate_runtime_state_under_test", _GATE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_GATE = _load_gate_module()


def _registry_storage_path() -> str:
    """제품 소스가 선언한 기본 저장 경로 — **제품이 소유자**다(C14-F44-1).

    import 하지 않고 소스에서 읽는다: 이 계약은 pydantic·설정 로딩 없이도 성립해야 하고, 읽는
    대상이 \"제품이 무엇을 쓰는가\"라는 사실 자체이기 때문이다.
    """
    text = _REGISTRY_SOURCE.read_text(encoding="utf-8")
    marker = '_DEFAULT_STORAGE_PATH = Path("'
    start = text.find(marker)
    assert start != -1, f"`_DEFAULT_STORAGE_PATH` 선언을 찾지 못했다: {_REGISTRY_SOURCE}"
    start += len(marker)
    end = text.find('"', start)
    assert end != -1, "`_DEFAULT_STORAGE_PATH` 값이 닫히지 않았다"
    return text[start:end]


def _candidate_paths() -> list[tuple[str, str]]:
    """(cwd 루트, 그 루트에서 저장 경로가 놓이는 상대 경로) — 저장 파일과 잠금 파일 둘 다."""
    storage = _registry_storage_path()
    assert not Path(storage).is_absolute(), (
        "저장 경로가 절대경로가 되었다 — 이 계약(cwd 별 무시)의 전제가 바뀌었다: "
        f"{storage!r} (그렇다면 cwd 루트 목록과 무시 규칙을 다시 정해야 한다)"
    )
    return [(root, storage if root == "." else f"{root}/{storage}") for root, _why in _CWD_ROOTS]


def _check_ignore(path: str, root: Path = REPO_ROOT) -> str | None:
    """그 경로를 무시하는 규칙(`check-ignore -v` 출력) — 없으면 `None`."""
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--", path], cwd=root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or None


def _code_scope_paths(root: Path) -> set[str]:
    """게이트가 지문을 만들 때 읽는 **바로 그** 경로 목록(`ga_gate.tree_digests` 의 키)."""
    digests = _GATE.tree_digests(root)
    assert isinstance(digests, dict)
    return set(digests)


# ---------------------------------------------------------------------------
# 계약
# ---------------------------------------------------------------------------


def test_registry_storage_path_is_relative_to_cwd() -> None:
    """C14-F44-1 — 전제를 **가정하지 않고** 잰다: 상대경로라서 cwd 가 위치를 정한다."""
    storage = _registry_storage_path()
    assert not Path(storage).is_absolute()
    assert storage.endswith("projects.json")


@pytest.mark.parametrize(("root", "why"), _CWD_ROOTS, ids=[root for root, _ in _CWD_ROOTS])
def test_runtime_state_is_ignored_from_each_cwd_root(root: str, why: str) -> None:
    """C14-F44-2 — 이 cwd 에서 제품의 기본 상태(과 잠금 파일)가 코드 스코프 **밖**이다.

    `_CWD_ROOTS` 의 둘째 값이 **그 루트를 여기 올린 이유**다 — 이유 없는 루트는 올 수 없다.
    """
    storage = _registry_storage_path()
    prefix = "" if root == "." else f"{root}/"
    for relative in (f"{prefix}{storage}", f"{prefix}{storage}.lock"):
        rule = _check_ignore(relative)
        assert rule, (
            f"cwd 루트 {root!r}({why})에서 제품의 런타임 상태 {relative!r} 를 무시하는 규칙이 없다 — "
            "이 상태는 코드 스코프에 들어와 코드 지문을 옮긴다(F-44)"
        )


def test_code_scope_holds_no_runtime_state_path() -> None:
    """C14-F44-3 — 규칙을 믿지 않고 **게이트의 함수로** 잰다: 후보 경로가 코드 스코프에 없다."""
    scope = _code_scope_paths(REPO_ROOT)
    intruders = sorted(relative for _root, relative in _candidate_paths() if relative in scope) + sorted(
        path for path in scope if path.endswith("/data/projects.json")
    )
    assert not intruders, (
        "런타임 상태가 코드 스코프 안에 있다 — 코드 지문이 움직여 보고서와 후보 트리가 갈라진다(F-44): "
        + ", ".join(sorted(set(intruders)))
    )


def test_teeth_removing_the_rule_makes_the_state_enter_the_code_scope(tmp_path: Path) -> None:
    """C14-F44-4 — 이빨: 규칙이 **실제로** 일을 하는지 임시 저장소에서 확인한다(규칙을 떼면 들어온다)."""
    repo = tmp_path / "repo"
    (repo / "src" / "data").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    storage = _registry_storage_path()

    def _write_state() -> None:
        (repo / storage).parent.mkdir(parents=True, exist_ok=True)
        (repo / storage).write_text("[]\n", encoding="utf-8")

    # ① 규칙이 없으면 — 제품이 쓴 상태가 **코드 스코프에 들어온다**(F-44 그 자체).
    _write_state()
    without_rule = _code_scope_paths(repo)
    assert storage in without_rule, "규칙 없는 임시 저장소에서 런타임 상태가 코드 스코프 밖으로 샜다 — 자가 고장났다"

    # ② 무시 규칙을 쓰면 — 같은 파일이 사라진다(규칙이 일을 한다).
    (repo / ".gitignore").write_text(f"{storage}\n{storage}.lock\n", encoding="utf-8")
    with_rule = _code_scope_paths(repo)
    assert storage not in with_rule, "무시 규칙이 있는데도 런타임 상태가 코드 스코프에 남았다"

    # ③ 그 파일은 여전히 존재한다 — 사라진 것은 **스코프**이지 파일이 아니다(규칙이 아니라 삭제로 통과하는 것 방지).
    assert (repo / storage).is_file()
