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
         대상 문서의 상대 링크가 실재 파일·앵커를 가리킨다.

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


def _broken_links(root: Path, relative: str) -> list[str]:
    """문서의 상대 markdown 링크 중 파일/앵커가 없는 것(저장소 상대 경로 인용 포함)."""
    path = root / relative
    if not path.is_file():
        return [f"{relative} (문서 없음)"]
    text = path.read_text(encoding="utf-8")

    broken: list[str] = []
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = match.group(1).strip()
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


def test_readme_separates_rp_history_from_current_cr_state() -> None:
    readme = _read(README)

    assert re.search(r"RP-0?1|RP-12", readme), "과거 RP 이력이 README에서 사라졌다"
    assert re.search(r"CR-0?1\s*~\s*CR-1?\d", readme), "현재 CR 범위가 README에 없다"
    assert re.search(r"REVIEW", readme), "현재 CR 상태(REVIEW)를 밝히지 않는다"
    assert re.search(r"미커밋|uncommitted", readme), "코드가 미커밋임을 밝히지 않는다"
    assert re.search(r"승인 없음|no GA approval", readme), "GA 승인 없음을 밝히지 않는다"
    # 과거 GA-100 진행률(33/33)이 승인으로 읽히지 않게 이력임을 밝힌다.
    ga100_rows = [line for line in readme.splitlines() if "GA-100" in line and "33/33" in line]
    assert ga100_rows, "GA-100 완료율 행이 사라졌다"
    assert all("구현 이력" in row for row in ga100_rows), "GA-100 완료 수가 이력임을 밝히지 않는다"


def test_current_cr_status_is_not_reported_as_done() -> None:
    """CR 카드의 실행 기록은 code SHA와 독립 review SHA를 구분해 남긴다."""
    checklist = _read("docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md")

    assert re.search(r"code SHA / 독립 review SHA", checklist), "SHA 기록 형식이 사라졌다"
    assert "미커밋" in checklist, "코드가 미커밋이라는 사실이 체크리스트에 없다"


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
