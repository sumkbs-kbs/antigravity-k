"""CR-12 — 지원·운영·VS Code 문구 정합화.

수용 기준(docs/17 C12-01 ~ C12-05)을 문서 문자열 복사가 아니라 **검사**로 고정한다:

  C12-01 기능/지원 주장→증거 매핑  → 레지스트리에 확장 주장 행이 있고, 인용한 저장소
         경로가 실제로 존재한다.
  C12-02 확장 README 실제 범위     → README가 주장하는 배경 재연결/오프라인 큐가
         extension 소스에 없으면 실패한다(부정문 고지는 주장으로 세지 않는다).
  C12-03 런북 초안·결과 반영       → 이전/복원, 저장 실패, 키 재입력, sandbox
         unavailable 런북이 절차·복구(또는 롤백)·확인·실행 명령을 갖춘다.
  C12-04 승인 누락/담당자/요청 범위 → BLOCKED_EXTERNAL이 정의되고, Pending 행마다
         붙어 있다.
  C12-05 과거 RP와 새 CR 상태 분리 → README가 RP 이력과 CR 현재 상태를 구분하고,
         대상 문서의 상대 링크가 실재 파일·앵커를 가리킨다. 값의 소유자는 README 가
         **실재하는 링크로** 가리키며(이름만 적는 것은 가리킴이 아니다 — F-29),
         체크리스트의 **현재 상태 줄**은 커밋된 후보와 승인 없음을 말한다(과거 attempt 의
         "미커밋" 기록을 현재로 읽히게 하지 않는다 — F-29).

링크 검사기는 음성 입력(없는 파일/없는 앵커)을 거부하는지도 함께 시험한다 — 통과만
하는 검사기는 계약이 아니다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CLAIMS_REGISTER = "docs/ga/GA_CLAIMS_AND_REVIEW_REGISTER.md"
SUPPORT_MATRIX = "docs/ga/GA_SUPPORT_MATRIX.md"
EXTENSION_README = "vscode-extension/README.md"
EXTENSION_SOURCE = "vscode-extension/src/extension.ts"
README = "README.md"

LINK_CHECK_TARGETS = (
    README,
    CLAIMS_REGISTER,
    SUPPORT_MATRIX,
    EXTENSION_README,
    "docs/10_FINAL_READINESS_REPORT.md",
    "docs/16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md",
    "docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md",
)

# CR-12가 요구하는 런북 주제 → 후보 파일(하나 이상 존재해야 한다).
REQUIRED_RUNBOOKS: dict[str, tuple[str, ...]] = {
    "conversation-migration": ("docs/ga/CR01_CONVERSATION_STORAGE_MIGRATION_RUNBOOK.md",),
    "session-storage-failure": ("docs/ga/CR02_SESSION_STORAGE_FAILURE_RUNBOOK.md",),
    "settings-key-reentry": (
        "docs/ga/CR05_KEY_REENTRY_RUNBOOK.md",
        "docs/ga/CR05_SETTINGS_SECRET_CONTRACT.md",
    ),
    "sandbox-unavailable": (
        "docs/ga/CR12_SANDBOX_UNAVAILABLE_RUNBOOK.md",
        "docs/ga/CR04_SHELL_EXECUTION_BOUNDARY.md",
        "docs/ga/CR03_SANDBOX_READ_BOUNDARY.md",
    ),
}

# 확장이 주장해서는 안 되는 배경 능력 문구.
BACKGROUND_CLAIMS = (
    "automatic reconnection",
    "auto reconnect",
    "automatic reconnect",
    "offline support",
    "offline queue",
    "offline mode",
)

# 그 능력을 뒷받침할 구현 신호.
BACKGROUND_IMPLEMENTATIONS = (
    "setInterval",
    "retry",
    "reconnect",
    "backoff",
    "queue",
    "buffer",
    "offline",
)

# 부정어 — 이 표현이 있는 문장의 능력 언급은 주장이 아니라 고지다.
NEGATIONS = (
    "no ",
    "not ",
    "never",
    "without",
    "isn't",
    "doesn't",
    "n't",
    "없",
    "않",
    "금지",
    "미지원",
    "out of scope",
)

RECOVERY_MARKERS = ("복구", "롤백")


def _read(relative: str, root: Path = REPO_ROOT) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _slug(heading: str) -> str:
    """GitHub 제목 슬러그 — 소문자화, 구두점 제거, 공백은 하이픈."""
    text = heading.strip().lower()
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text).strip("-")


def _anchors(markdown: str) -> set[str]:
    return {_slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.*)$", markdown, re.M)}


_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _link_targets(markdown: str) -> list[str]:
    """markdown 링크 대상 — **링크 문법의 유일한 자리**다.

    `_broken_links` 와 값 소유자 검사가 둘 다 이 함수를 쓴다: 링크 문법을 두 곳에 적으면
    한쪽만 고쳐져 검사가 갈라진다(F-18·F-24·F-27·F-28 과 같은 병).
    """
    return [match.group(1).strip() for match in _LINK_RE.finditer(markdown)]


def _broken_links(root: Path, relative: str) -> list[str]:
    """문서의 상대 markdown 링크 중 파일/앵커가 없는 것(저장소 상대 경로 인용 포함)."""
    path = root / relative
    if not path.is_file():
        return [f"{relative} (문서 없음)"]
    text = path.read_text(encoding="utf-8")

    broken: list[str] = []
    for target in _link_targets(text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path_part, _, anchor = target.partition("#")
        path_part = path_part.split(" ", 1)[0]
        if not path_part:
            continue
        resolved = path.parent / path_part
        candidates = [resolved, resolved.with_suffix(".md"), resolved / "README.md"]
        found = next((candidate for candidate in candidates if candidate.exists()), None)
        if found is None:
            broken.append(f"{relative} -> {path_part} (파일 없음)")
            continue
        if anchor and found.suffix == ".md":
            if _slug(anchor) not in _anchors(found.read_text(encoding="utf-8")):
                broken.append(f"{relative} -> {path_part}#{anchor} (앵커 없음)")
    return broken


def _sentence_at(text: str, index: int) -> str:
    """`index`를 품는 문장(또는 목록 항목 줄)."""
    boundary = re.compile(r"(?<=[.!?])\s+|\n")
    start = 0
    for match in boundary.finditer(text):
        if match.end() <= index:
            start = match.end()
        else:
            break
    end = len(text)
    for match in boundary.finditer(text, index):
        end = match.start()
        break
    return text[start:end]


def _claimed_behaviours(readme: str, phrases: tuple[str, ...] = BACKGROUND_CLAIMS) -> list[str]:
    """부정되지 않은 능력 주장만 — 고지(“no offline queue”)는 주장이 아니다."""
    lowered = readme.lower()
    claimed: list[str] = []
    for phrase in phrases:
        start = 0
        while (index := lowered.find(phrase, start)) != -1:
            if not any(negation in _sentence_at(lowered, index) for negation in NEGATIONS):
                claimed.append(phrase)
                break
            start = index + len(phrase)
    return claimed


def _table_rows(text: str, needle: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("|") and needle in line]


# --------------------------------------------------------------------------- C12-01


def test_claims_register_maps_extension_behaviour_to_evidence() -> None:
    register = _read(CLAIMS_REGISTER)

    assert re.search(r"evidence", register, re.IGNORECASE), "레지스트리에 증거 열이 사라졌다"
    rows = [line for line in register.splitlines() if line.startswith("|")]
    extension_rows = [row for row in rows if "vscode-extension" in row]
    assert extension_rows, "확장 동작을 주장→증거로 매핑한 행이 없다"

    row = extension_rows[0]
    assert EXTENSION_SOURCE.split("/")[-1] in row, "확장 주장 행이 실제 소스를 인용하지 않는다"
    assert "companion" in row or "context-sync" in row, "확장 범위가 companion으로 한정되지 않았다"


def test_claims_register_evidence_paths_exist() -> None:
    """레지스트리가 인용한 저장소 상대 경로는 실재해야 한다(이름이 바뀌면 실패)."""
    register = _read(CLAIMS_REGISTER)
    referenced = re.findall(r"`([A-Za-z0-9_./-]+\.(?:md|py|ts|json|toml|txt))`", register)
    assert referenced, "인용 경로가 하나도 없다 — 매핑이 산문으로 퇴화했다"

    missing = sorted(
        path
        for path in referenced
        if not (REPO_ROOT / path).exists() and not (REPO_ROOT / "docs" / "ga" / path).exists()
    )
    assert not missing, f"레지스트리가 없는 경로를 인용한다: {missing}"


# --------------------------------------------------------------------------- C12-02


def test_extension_readme_claims_do_not_exceed_extension_source() -> None:
    readme = _read(EXTENSION_README)
    source = _read(EXTENSION_SOURCE)

    claimed = _claimed_behaviours(readme)
    if claimed:
        implemented = [signal for signal in BACKGROUND_IMPLEMENTATIONS if signal in source]
        assert implemented, f"README가 주장하지만 소스에 구현이 없다: {claimed}"


def test_extension_readme_states_next_event_retry_and_absence_of_background_retry() -> None:
    readme = _read(EXTENSION_README)

    assert re.search(r"next (editor )?event|다음 .*(편집기 )?이벤트", readme, re.IGNORECASE), (
        "실제 재시도가 '다음 편집기 이벤트'임을 밝히지 않는다"
    )
    assert re.search(
        r"no[^\n]{0,60}(reconnection|reconnect|offline queue)|없[^\n]{0,30}(재연결|오프라인)",
        readme,
        re.IGNORECASE,
    ), "배경 재연결·오프라인 큐가 없다는 고지가 없다"


def test_claim_detector_treats_disclaimer_as_disclaimer() -> None:
    """검사기 자체의 음성 케이스: 고지를 주장으로 세면 위 시험이 무의미해진다."""
    disclaimer = "There is no background reconnection timer and no offline queue."
    genuine_claim = "Features: automatic reconnection and offline support."

    assert _claimed_behaviours(disclaimer) == []
    claimed = _claimed_behaviours(genuine_claim)
    assert "automatic reconnection" in claimed
    assert "offline support" in claimed


# --------------------------------------------------------------------------- C12-03


@pytest.mark.parametrize("topic", sorted(REQUIRED_RUNBOOKS))
def test_required_runbook_has_runnable_procedure(topic: str) -> None:
    candidates = REQUIRED_RUNBOOKS[topic]
    existing = [candidate for candidate in candidates if (REPO_ROOT / candidate).is_file()]
    assert existing, f"{topic} 런북이 없다(후보 {candidates})"

    text = "\n".join(_read(candidate) for candidate in existing)
    assert "## " in text, f"{topic} 런북에 절이 없다"
    assert "```" in text, f"{topic} 런북에 실행할 수 있는 명령 블록이 없다"
    assert "절차" in text or "단계" in text, f"{topic} 런북에 절차가 없다"
    assert any(marker in text for marker in RECOVERY_MARKERS), f"{topic} 런북에 복구/롤백이 없다"
    assert "확인" in text or "검증" in text, f"{topic} 런북에 확인 절차가 없다"


# --------------------------------------------------------------------------- C12-04


def test_blocked_external_disposition_is_defined() -> None:
    register = _read(CLAIMS_REGISTER)

    assert "## Disposition vocabulary" in register, "상태 어휘 표가 없다"
    assert "BLOCKED_EXTERNAL" in register
    assert re.search(r"`BLOCKED_EXTERNAL`", register), "BLOCKED_EXTERNAL이 상태로 정의되지 않았다"
    assert re.search(r"external approver|외부", register), "누가 해제할 수 있는지 밝히지 않았다"


def test_every_pending_review_row_is_marked_blocked_external() -> None:
    """Pending은 '아직'이 아니라 '우리 통제 밖'임을 표기해야 한다."""
    register = _read(CLAIMS_REGISTER)

    pending_rows = _table_rows(register, "| Pending")
    assert len(pending_rows) >= 5, "검토 대기 행이 사라졌다 — 검사가 헛돌고 있다"
    unmarked = [row for row in pending_rows if "BLOCKED_EXTERNAL" not in row]
    assert not unmarked, f"Pending 행에 BLOCKED_EXTERNAL 표기가 없다: {unmarked}"


def test_support_matrix_preserves_external_blockers() -> None:
    matrix = _read(SUPPORT_MATRIX)

    assert "BLOCKED_EXTERNAL" in matrix
    rows = _table_rows(matrix, "BLOCKED_EXTERNAL")
    assert len(rows) >= 6, f"지원 매트릭스에 외부 blocker 표기가 부족하다: {len(rows)}행"
    assert "No row below is supported" in matrix, "미지원 기본값 문구가 사라졌다"
    assert re.search(r"\bowner\b|담당자", matrix, re.IGNORECASE), "담당자 열이 없다"


def test_approval_is_not_inferred_from_configuration() -> None:
    register = _read(CLAIMS_REGISTER)

    assert re.search(r"[Ll]egal review cannot be inferred", register), (
        "설정·라이선스로 법무 승인을 추론하지 않는다는 규칙이 사라졌다"
    )
    assert "approval" in register.lower()


# --------------------------------------------------------------------------- C12-05


README_VALUE_OWNER = "CR14_FINAL_CANDIDATE_VERDICT.md"
# 체크리스트의 **현재 상태 줄** — 과거 attempt 기록과 구분되는 자리.
CURRENT_STATUS_PREFIX = "**현재:"


def readme_value_owner_violations(text: str, *, repo_root: Path | None = None) -> list[str]:
    """README 가 현재 값을 **소유한 문서**를 가리키지 않으면 보고한다(F-22, 빈 목록 = 통과).

    CR-14 attempt-009 는 이 자리에 "README 가 후보 SHA(`\b[0-9a-f]{7,40}\b`)를 담을 것"을
    요구했고, attempt-014(F-22)에서 그 요구를 **내려놓았다**. 그 요구는 성립할 수 없었다:

      * README 의 값은 사람이 손으로 쓴다. 그런데 **최종 커밋의 SHA 는 그 커밋 전에는
        알 수 없다** — 즉 README 의 SHA 는 구조적으로 항상 **과거** 커밋을 가리킨다
        (실측: README 는 `54e4169a` 를 가리킨 채 후보가 `1207118d`·`0593dd27`·`ded52af6` 로
        진행했고, 그 값을 손보려던 attempt-013 의 **기록 커밋**이 `README.md` 를 건드려
        gate 지문을 `2c5a15c8…` → `b9590b01…` 로 옮겼다 — 기록이 증거를 낡게 만들었다).
      * 값은 `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md`(= 지문 제외 대상)가 소유한다.
        README 는 그 문서를 가리키면 된다.

    그래서 검사 대상이 '값'에서 '값의 출처'로 옮겨졌다 — 느슨해진 것이 아니라 README 가
    지킬 수 있는 주장만 하도록 좁힌 것이고, 그 출처 포인터 자체를 아래에서 강제한다.

    **R-5 재확인에서 고친 것(F-29)** — 그 포인터 강제가 처음에는 **토큰**을 보았다:
    `README_VALUE_OWNER in text`, 즉 "README 가 그 **이름**을 어딘가에 담고 있는가". 요구는
    "README 가 그 문서를 **가리킨다**"인데 확인은 "이름이 있다"였다 — 산문에 이름만 적거나
    링크를 **다른 문서**로 바꿔도 통과한다(F-28 과 같은 병: 의도가 아니라 표기를 본다).
    이제 **실재하는 링크**를 요구한다: 링크 대상의 파일명이 소유자이고, 그 대상이 저장소에
    실제로 있다(`repo_root` 는 이빨이 임시 트리를 쓸 수 있게 하는 인자다).
    """
    root = REPO_ROOT if repo_root is None else repo_root
    owner_targets = [
        target for target in _link_targets(text) if Path(target.partition("#")[0]).name == README_VALUE_OWNER
    ]
    if not owner_targets:
        return [
            f"README 가 값을 소유한 판정서(`{README_VALUE_OWNER}`)를 **링크로** 가리키지 않는다"
            " — 맨이름·산문 언급은 '가리킴'이 아니다"
        ]
    unresolved = [target for target in owner_targets if not (root / target.partition("#")[0]).is_file()]
    if unresolved:
        return [f"README 의 값 소유자 링크가 실재 파일을 가리키지 않는다: {unresolved}"]
    return []


def current_status_violations(text: str) -> list[str]:
    """체크리스트의 **현재 상태 줄**이 커밋된 후보·승인 없음을 말하고 미커밋으로 읽히지 않는가(F-29).

    attempt-001 의 계약은 `"미커밋" in checklist` 를 요구했다 — 그때는 참이었지만 후보가
    커밋된(attempt-009) 뒤로는 **과거 attempt 의 기록 행**이 그 문자열을 계속 공급해 검사가
    무의미해졌고, 메시지는 거짓을 말하게 됐다("코드가 미커밋이라는 사실이 체크리스트에 없다").
    요구를 **현재를 말하는 한 줄**로 좁힌다: 과거 행의 "미커밋" 은 기록이므로 그대로 두고,
    현재 상태가 그것을 현재로 읽히게 하면 실패한다.
    """
    lines = [line for line in text.splitlines() if line.startswith(CURRENT_STATUS_PREFIX)]
    if not lines:
        return [f"체크리스트에 현재 상태 줄이 없다(`{CURRENT_STATUS_PREFIX}` 로 시작하는 줄)"]
    line = lines[0]
    violations: list[str] = []
    if "커밋" not in line:
        violations.append("현재 상태가 후보가 **커밋된** 상태임을 밝히지 않는다")
    if "승인" not in line or "없음" not in line:
        violations.append("현재 상태가 **GA 승인 없음**을 밝히지 않는다")
    if re.search(r"미커밋(?!\s*(?:아님|없))", line):
        violations.append("현재 상태가 코드를 **미커밋**으로 말한다 — 그 표현은 과거 attempt 기록의 것이다")
    return violations


def test_readme_separates_rp_history_from_current_cr_state() -> None:
    readme = _read(README)

    assert re.search(r"RP-0?1|RP-12", readme), "과거 RP 이력이 README에서 사라졌다"
    assert re.search(r"CR-0?1\s*~\s*CR-1?\d", readme), "현재 CR 범위가 README에 없다"
    assert re.search(r"REVIEW", readme), "현재 CR 상태(REVIEW)를 밝히지 않는다"
    # CR-14 attempt-009 에서 후보를 커밋했다(`54e4169a`). 그 전까지 이 자리는 "미커밋"을 요구했다.
    # **커밋은 승인이 아니므로** 의도는 그대로다 — README 는 **후보가 커밋된 상태**와
    # **승인 없음**을 함께 밝혀야 하며, "커밋됨"이 풀린 것으로 읽히지 않아야 한다.
    # 값(SHA·게이트 수)을 README 에 박지 않는 이유와 그 대체 검사는 `readme_value_owner_violations`
    # 참조 — 값의 소유자는 판정 카드이고, README 는 그 카드를 가리킨다(F-22).
    assert not readme_value_owner_violations(readme), " / ".join(readme_value_owner_violations(readme))
    assert not re.search(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b", readme), (
        "README 가 커밋 SHA 리터럴을 담고 있다 — 그 값은 갱신할 수 없고(최종 SHA 는 커밋 전 미지), "
        "갱신 시도가 기록 커밋으로 지문을 옮긴다(F-22)"
    )
    assert re.search(r"커밋", readme), "후보가 커밋된 상태인지 밝히지 않는다"
    assert re.search(r"승인 없음|no GA approval", readme), "GA 승인 없음을 밝히지 않는다"
    assert re.search(r"미배정|unassigned", readme), "독립 검토자·출시 책임자 미배정을 밝히지 않는다"
    # 과거 GA-100 진행률(33/33)이 승인으로 읽히지 않게 이력임을 밝힌다.
    ga100_rows = [line for line in readme.splitlines() if "GA-100" in line and "33/33" in line]
    assert ga100_rows, "GA-100 완료율 행이 사라졌다"
    assert all("구현 이력" in row for row in ga100_rows), "GA-100 완료 수가 이력임을 밝히지 않는다"


def test_readme_value_owner_pointer_is_enforced() -> None:
    """통과만 하는 검사기는 계약이 아니다 — 출처 포인터가 사라지면 실패해야 한다(F-22)."""
    readme = _read(README)
    assert not readme_value_owner_violations(readme), "README 가 이미 판정서를 가리키지 않는다"
    assert readme_value_owner_violations(readme.replace(README_VALUE_OWNER, "판정서")), (
        "이빨 없음 — 출처 포인터를 지웠는데도 통과했다"
    )


def test_readme_value_owner_pointer_must_be_a_resolving_link(tmp_path: Path) -> None:
    """이름만 적는 것은 가리킴이 아니다(F-29) — ① 산문 ② 다른 문서 ③ 없는 파일 순으로 심는다.

    R-5 재확인 전의 계약은 `README_VALUE_OWNER in text` 였다: README 의 **산문**에 그 이름이
    한 번이라도 있으면 통과했고, 링크가 **다른 문서**를 가리켜도 통과했다. 요구("값을 소유한
    문서를 가리킨다")와 확인("그 이름이 있다")이 갈라져 있었다 — F-28 과 같은 병이다.
    """
    owner_rel = f"docs/ga/{README_VALUE_OWNER}"
    (tmp_path / "docs" / "ga").mkdir(parents=True)
    (tmp_path / owner_rel).write_text("# 판정\n", encoding="utf-8")

    assert readme_value_owner_violations(f"판정서는 {README_VALUE_OWNER} 이다\n", repo_root=tmp_path), (
        "이빨 없음 — 링크가 아니라 산문으로 이름만 담아도 통과했다"
    )
    assert readme_value_owner_violations("[판정서](docs/10_FINAL_READINESS_REPORT.md)\n", repo_root=tmp_path), (
        "이빨 없음 — 다른 문서를 가리켜도 통과했다"
    )
    assert readme_value_owner_violations(f"[판정서]({owner_rel})\n", repo_root=tmp_path) == [], (
        "기준선 — 실재하는 소유자 링크가 통과하지 않았다"
    )

    (tmp_path / owner_rel).unlink()
    assert readme_value_owner_violations(f"[판정서]({owner_rel})\n", repo_root=tmp_path), (
        "이빨 없음 — 없는 파일을 가리키는 링크를 통과시켰다"
    )


def test_current_cr_status_is_not_reported_as_done() -> None:
    """현재 상태 표기는 커밋된 후보를 말하고, 과거 attempt 의 '미커밋' 을 현재로 읽히게 하지 않는다."""
    checklist = _read("docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md")

    assert re.search(r"code SHA / 독립 review SHA", checklist), "SHA 기록 형식이 사라졌다"
    assert not current_status_violations(checklist), " / ".join(current_status_violations(checklist))


def test_current_status_must_state_committed_and_not_uncommitted() -> None:
    """이빨 — 현재 상태 줄에 "미커밋" 을 심으면 실패하고, 커밋된 상태를 빼도 실패해야 한다."""
    checklist = _read("docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md")
    assert not current_status_violations(checklist), "기준선이 이미 위반이다"

    lines = checklist.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(CURRENT_STATUS_PREFIX))

    uncommitted = list(lines)
    uncommitted[index] = lines[index].replace(CURRENT_STATUS_PREFIX, f"{CURRENT_STATUS_PREFIX} 코드는 미커밋이다.", 1)
    assert current_status_violations("\n".join(uncommitted)), "이빨 없음 — 현재 상태가 미커밋이라고 말해도 통과했다"

    silent = list(lines)
    silent[index] = f"{CURRENT_STATUS_PREFIX} CR-01 ~ CR-14 REVIEW / GA 승인 없음."
    violations = current_status_violations("\n".join(silent))
    assert any("커밋된" in violation for violation in violations), f"이빨 없음: {violations}"

    no_approval = list(lines)
    no_approval[index] = f"{CURRENT_STATUS_PREFIX} 코드 후보 커밋 동결. 최종 판정 NO-GO."
    violations = current_status_violations("\n".join(no_approval))
    assert any("승인" in violation for violation in violations), f"이빨 없음: {violations}"


@pytest.mark.parametrize("relative", LINK_CHECK_TARGETS)
def test_document_relative_links_resolve(relative: str) -> None:
    assert _broken_links(REPO_ROOT, relative) == []


def test_all_ga_documents_have_resolvable_links() -> None:
    broken: list[str] = []
    for path in sorted((REPO_ROOT / "docs/ga").glob("*.md")):
        relative = str(path.relative_to(REPO_ROOT))
        broken.extend(_broken_links(REPO_ROOT, relative))
    assert not broken, f"docs/ga 문서에 깨진 링크가 있다: {broken}"


def test_link_checker_rejects_missing_file_and_anchor(tmp_path: Path) -> None:
    """검사기 자체의 음성 케이스 — 통과만 하는 검사기는 계약이 아니다."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "target.md").write_text("# Only Heading\n", encoding="utf-8")
    (docs / "doc.md").write_text(
        "[ok](target.md)\n"
        "[anchor ok](target.md#only-heading)\n"
        "[missing](absent.md)\n"
        "[anchor bad](target.md#no-such-heading)\n",
        encoding="utf-8",
    )

    broken = _broken_links(tmp_path, "docs/doc.md")

    assert len(broken) == 2, broken
    assert any("absent.md" in item for item in broken)
    assert any("no-such-heading" in item for item in broken)


def test_extension_readme_links_to_register() -> None:
    readme = _read(EXTENSION_README)

    assert "GA_CLAIMS_AND_REVIEW_REGISTER.md" in readme, "확장 README가 주장 레지스트리를 가리키지 않는다"
