"""승격 뒤 **호출자 경로 계약** — 체인은 실재하는 도구만 부른다.

왜 이 시험이 필요한가(2026-09-17 실측):
    3차 배치가 감시·통제 도구를 `docs/qa/2026-09-16-followup/nx10/` 에서 `scripts/` 로 **옮겼다**.
    옮긴 쪽은 초록이었지만 **부르는 쪽은 아무도 안 봤다** — 그 순간 이 레인의 체인들은 존재하지 않는
    문서 사본(`$NX10/soak_control.sh`)을 부르고 있었고, 증상은 이렇게 나타난다:

      · `run_batch_chain.sh` 는 재장전(7단계)에서만 그 경로를 쓴다 → **4개 배치를 다 적용하고 커밋한 뒤에**
        재장전만 실패해, 반쯤 끝난 트리와 8시간 없는 밤을 남긴다(실패가 가장 늦게, 가장 비싸게 나온다).
      · `post_harvest_sequence3.sh` 는 판정 단계에서 그 경로를 쓴다 → 다음 회수가 "파일 없음" 으로 죽는다.

    그래서 계약은 **"옮겼으면 부르는 쪽도 같이 옮겼는가"** 이고, 판정 기준은 문장이 아니라 **파일의 존재**다:
    호출 경로가 디스크에 있는가.

계약(이 시험이 지키는 문장):
  · **P-1 실재성**: 이 레인의 셸 스크립트가 도구를 부르는 경로는 **전부 디스크에 있다**(변수는 그 파일의
    정의를 `$REPO`·`$NX10`·`$HERE` 로 펼쳐서 본다).
  · **P-2 승격 우선**: 승격된 도구는 `scripts/` 를 먼저 본다 — 문서 사본만 부르는 호출이 남아 있으면 빨개진다.
  · **P-3 문서도 같다**: `CLOSURE_RUNBOOK` 의 감시 실행 명령은 승격 위치를 쓴다(사람이 그대로 붙여 넣는 문장).

이빨(음성 대조군 — `test_the_checker_bites_*`):
  · 승격된 도구를 **옛 경로로만** 부르는 합성 스크립트 → 정확히 그 하나가 문제로 잡힌다.
  · 가드 없이 둘 다 부르는 합성 스크립트 → 잡히지 않는다(**실재하는 경로가 하나 있으면 계약은 성립한다**).
  · 검사기가 호출을 **하나도 못 찾으면** 시험은 실패한다(정규식이 무력해져 초록이 되는 것을 막는다).

실행:
  .venv/bin/python -m pytest docs/qa/2026-09-16-followup/nx10/batchchain/test_chain_tool_paths_contract.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

LANE = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
# 승격으로 위치가 바뀐 도구들 — 이 이름들이 계약의 대상이다.
TOOLS = ("soak_control.sh", "soak_watch.py", "soak_watch_loop.py")
# 승격 전 사본이 살던 곳(문서 레인). 여기로만 부르면 그 도구는 **더 이상 실재하지 않는다**.
LANE_PREFIX = "docs/qa/2026-09-16-followup/nx10/"

# `bash "<경로>"` / `bash '<경로>'` / `bash <경로>` 형태의 **호출만** 본다.
# 앞에 명령 위치 표시(`^` · `&&` · `||` · `;` · `(` · `then`/`do`)가 있어야 호출이다 — 이 조건이 없으면
# `echo "  bash …/soak_control.sh preflight"` 같은 **인쇄문**을 호출로 오해한다(실측: promote2 에서 두 건).
CALL = re.compile(r'(?:^|[;&|(]|\b(?:then|do|else|if)\s+)\s*bash\s+(?:--\s+)?(["\']?)([^\s"\'|;&)]+)\1')


def repo_root() -> Path:
    """`pyproject.toml` 을 위로 찾아 올라간다(시험 파일 위치가 옮겨져도 산다)."""
    for candidate in [HERE, *HERE.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise AssertionError("저장소 루트를 찾지 못했다 — pyproject.toml 이 없다")


def _expand(token: str, script_dir: str, repo: Path) -> str:
    """토큰의 `$REPO`·`$NX10`·`$HERE` 를 실제 경로로 펼친다(변수 하나만 펼치면 판정이 불가능하다)."""
    return (
        token.replace("${REPO}", str(repo))
        .replace("$REPO", str(repo))
        .replace("${NX10}", str(LANE))
        .replace("$NX10", str(LANE))
        .replace("${HERE}", script_dir)
        .replace("$HERE", script_dir)
    )


def _assignments(text: str) -> dict[str, list[str]]:
    """파일 안의 `VAR=값` 정의를 모은다(변수 간접 호출을 펼치기 위해 필요하다)."""
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)=([\"']?)([^\s\"'#]+)\2", line)
        if m:
            found.setdefault(m.group(1), []).append(m.group(3))
    return found


def _target_paths(token: str, assignments: dict[str, list[str]], script_dir: str, repo: Path) -> list[Path]:
    """호출 토큰이 가리킬 수 있는 **대상 도구의** 파일 경로들. 빈 목록 = 이 계약의 대상이 아니다.

    `bash "$CONTROL"` 처럼 **변수 하나로만** 부르는 형태도 본다 — 변수를 펼친 뒤 이름이 대상 도구인지
    보기 때문이다. 변수를 안 펼치면 그런 호출이 검사에서 **통째로 빠져** 계약이 헛돌게 된다.
    """
    variable = re.fullmatch(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", token)
    raw = assignments.get(variable.group(1), []) if variable else [token]
    paths = [Path(_expand(value, script_dir, repo)) for value in raw]
    return [path for path in paths if path.name in TOOLS]


def unresolved_tool_calls(text: str, script_dir: str, repo: Path) -> list[str]:
    """P-1 — 이 텍스트가 부르는 대상 도구 경로 중 **디스크에 없는 것**을 돌려준다.

    변수 호출(`bash "$VAR/soak_control.sh"`)은 그 파일 안의 `VAR=` 정의를 **전부** 모아 펼친 뒤
    **하나라도 실재하면 통과**로 본다 — 승격 위치를 먼저 보고 문서 사본으로 되돌아오는 가드가
    정확히 그 모양이기 때문이다(가드 없는 옛 경로만 남은 상태가 잡으려는 결함이다).
    """
    assignments = _assignments(text)
    problems: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # 주석·사용 예시는 호출이 아니다
        for _quote, token in CALL.findall(stripped):
            candidates = _target_paths(token, assignments, script_dir, repo)
            if not candidates:
                continue
            # 후보 중 **하나라도 실재하면** 계약 성립이다 — 승격 위치를 먼저 보고 옛 사본으로
            # 되돌아오는 가드가 정확히 그 모양이다(가드 없는 옛 경로만 남은 상태가 잡으려는 결함).
            if any(candidate.is_file() for candidate in candidates):
                continue
            rel = candidates[0].relative_to(repo) if candidates[0].is_relative_to(repo) else candidates[0]
            problems.append(f"{rel} 을(를) 부르는데 그 파일이 없다")
    return problems


def _chain_scripts() -> list[Path]:
    return sorted(LANE.rglob("*.sh"))


def test_every_tool_call_in_the_lane_resolves_to_a_file_that_exists() -> None:
    """P-1·P-2 — 레인의 모든 셸 스크립트가 대상 도구를 실재하는 경로로만 부른다."""
    repo = repo_root()
    problems: list[str] = []
    calls = 0
    for script in _chain_scripts():
        text = script.read_text(encoding="utf-8")
        assignments = _assignments(text)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for _quote, token in CALL.findall(stripped):
                if _target_paths(token, assignments, str(script.parent), repo):
                    calls += 1
        for problem in unresolved_tool_calls(text, str(script.parent), repo):
            problems.append(f"{script.relative_to(repo)}: {problem}")
    assert not problems, "승격된 도구를 실재하지 않는 경로로 부른다:\n  " + "\n  ".join(problems)
    # 정규식이 무력해지면(호출 0건) 이 시험은 **아무것도 안 지키면서** 초록이 된다 — 그 상태를 막는다.
    assert calls >= 8, f"대상 도구 호출을 {calls}건만 찾았다 — 검사기가 헛돌고 있을 수 있다"


def test_the_rearm_step_checks_the_promoted_tools_before_it_spends_eight_hours() -> None:
    """P-2 — 재장전은 승격 위치를 지목하고, **시작 전에** 그 파일들의 존재를 확인한다."""
    repo = repo_root()
    chain = (HERE / "run_batch_chain.sh").read_text(encoding="utf-8")
    assert 'CONTROL="$REPO/scripts/soak_control.sh"' in chain, "통제 도구를 승격 위치로 지목하지 않는다"
    assert 'WATCHER="$REPO/scripts/soak_watch_loop.py"' in chain, "감시 도구를 승격 위치로 지목하지 않는다"
    # 존재 확인이 **preflight 앞에** 있어야 한다: 뒤에 있으면 8시간을 태운 뒤에야 알게 된다.
    guard = chain.index('[ -f "$CONTROL" ]')
    spend = chain.index('bash "$CONTROL" preflight')
    assert guard < spend, "재장전 전에 승격 도구의 존재를 확인하지 않는다"
    assert 'scripts/soak_watch_loop.py"' in chain.split("screen -dmS")[1], (
        "감시 화면이 승격 위치의 감시 도구를 띄우지 않는다"
    )
    del repo


def test_the_runbook_prints_the_promoted_watcher_path() -> None:
    """P-3 — 사람이 붙여 넣는 감시 명령도 승격 위치를 쓴다."""
    repo = repo_root()
    runbook = (LANE / "CLOSURE_RUNBOOK.md").read_text(encoding="utf-8")
    command_block = "\n".join(
        line for line in runbook.splitlines() if "soak_watch_loop.py" in line and not line.strip().startswith("#")
    )
    assert command_block, "감시 실행 명령을 찾지 못했다"
    assert "scripts/soak_watch_loop.py" in command_block, "문서가 승격 위치가 아니라 문서 사본을 띄우라고 한다"
    assert LANE_PREFIX + "soak_watch_loop.py" not in command_block, "문서가 승격으로 사라진 사본 경로를 띄우라고 한다"
    del repo


def test_the_checker_bites_on_a_script_that_only_calls_the_old_copy() -> None:
    """음성 대조군 ① — 승격된 도구를 옛 경로로만 부르면 잡힌다(이빨)."""
    repo = repo_root()
    synthetic = "\n".join(
        [
            "#!/usr/bin/env bash",
            'NX10="$REPO/docs/qa/2026-09-16-followup/nx10"',
            'cd "$REPO" || exit 1',
            'bash "$NX10/soak_control.sh" preflight || exit 7',
            'bash "$NX10/soak_control.sh" run || exit 7',
        ]
    )
    problems = unresolved_tool_calls(synthetic, str(HERE), repo)
    assert len(problems) == 2, problems
    assert all("soak_control.sh" in problem for problem in problems), problems


def test_the_checker_bites_on_the_variable_form_used_by_the_real_chains() -> None:
    """음성 대조군 ③ — 실제 체인들이 쓰는 **변수 형태**로 옛 사본을 가리키면 잡힌다.

    이 간접 형태가 검사에서 빠지면(변수를 안 펼치면) 계약이 헛돌게 된다 — 그래서 따로 고정한다.
    """
    repo = repo_root()
    synthetic = "\n".join(
        [
            "#!/usr/bin/env bash",
            'NX10="$REPO/docs/qa/2026-09-16-followup/nx10"',
            'CONTROL="$NX10/soak_control.sh"',
            'bash "$CONTROL" preflight || exit 7',
        ]
    )
    problems = unresolved_tool_calls(synthetic, str(HERE), repo)
    assert len(problems) == 1, problems
    assert "soak_control.sh" in problems[0], problems


def test_the_checker_accepts_a_fallback_that_has_the_promoted_path_first() -> None:
    """음성 대조군 ② — 승격 위치를 먼저 보는 가드는 통과한다(계약은 실재성이다)."""
    repo = repo_root()
    synthetic = "\n".join(
        [
            "#!/usr/bin/env bash",
            'NX10="$REPO/docs/qa/2026-09-16-followup/nx10"',
            'CONTROL="$REPO/scripts/soak_control.sh"',
            '[ -f "$CONTROL" ] || CONTROL="$NX10/soak_control.sh"',
            'bash "$CONTROL" preflight || exit 7',
        ]
    )
    assert unresolved_tool_calls(synthetic, str(HERE), repo) == []


def test_the_checker_ignores_comments_and_usage_examples() -> None:
    """주석 속 사용 예시는 호출이 아니다 — 그것까지 잡으면 문서가 시험을 떠받치게 된다."""
    repo = repo_root()
    synthetic = "\n".join(
        [
            "#!/usr/bin/env bash",
            "#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh status",
            'CONTROL="$REPO/scripts/soak_control.sh"',
            'bash "$CONTROL" status',
        ]
    )
    assert unresolved_tool_calls(synthetic, str(HERE), repo) == []
