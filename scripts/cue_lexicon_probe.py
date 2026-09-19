#!/usr/bin/env python
"""NX-01 후속 — cue lexicon 의 **회수율과 오검출**을 합성 코퍼스로 측정한다.

왜: `nx01/handoff.md` §6-1 은 "cue lexicon 밖 표현의 요구사항은 구조화되지 않는다"를 한계로 적고,
회수율을 **별도 실측**하라고 남겼다(NX-09 는 하지 않았다). 그런데 "실사용 회수율"은 라벨링된 실데이터
코퍼스가 필요하고 — 그건 사람·프라이버시 결정이 먼저다. 반면 **어휘 자체의 성능**은 지금 측정할 수 있다.

이 스크립트는 제가 직접 만든 **합성 문장**만 쓴다(사용자 데이터·대화 내용을 넣지 않는다 → 결과를
그대로 문서에 실을 수 있다). 측정하는 것:

  1. **직접 cue**: 사전에 있는 표현 → 잡히는가, 종류(kind)가 맞는가
  2. **자연어 바꿔쓰기**: 같은 뜻인데 사전 밖 표현 → 놓치는가(blind spot)
  3. **사전 표현이지만 제약이 아닌 문장** → 잘못 구조화하는가(false positive)
  4. **명시적 supersede**: "더 이상/취소/이제부터 …" → 무효화가 잡히는가
  5. **supersede 처럼 보이는 편집 요청**: "변경/대신"이 든 평범한 요청 → 기존 제약을 잘못 무효화하는가

어휘를 **고치지 않는다**. 이 스크립트는 측정기이며, 결과가 곧 "무엇을 주장할 수 있는가"의 증거다.

실행(승격 뒤 — 이 파일은 `scripts/` 에 있다): python3 scripts/cue_lexicon_probe.py
결과 해석과 케이스 표는 `docs/qa/2026-09-16-followup/nx01/cue-lexicon-measurement.md` 가 소유한다.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    """저장소 루트 — **자기 파일 위치의 깊이에 의존하지 않는다**.

    스테이징(`docs/qa/2026-09-16-followup/nx01/`)과 승격 위치(`scripts/`) 양쪽에서 돈다.
    `parents[4]` 는 승격 뒤에는 `src` 가 없는 디렉터리를 가리켜 `antigravity_k` 를 못 찾는다
    (같은 깊이 가정을 쓰던 검사기가 실제로 그렇게 죽었다).
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


REPO = _repo_root()
sys.path.insert(0, str(REPO / "src"))

from antigravity_k.engine.summary_memory import (  # noqa: E402
    CONSTRAINT_KIND_APPROVAL,
    CONSTRAINT_KIND_PROHIBITION,
    CONSTRAINT_KIND_REQUIREMENT,
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    SummaryMemory,
    detect_kind,
    detect_supersede,
    update_from_messages,
)

PROHIBITION = CONSTRAINT_KIND_PROHIBITION
APPROVAL = CONSTRAINT_KIND_APPROVAL
REQUIREMENT = CONSTRAINT_KIND_REQUIREMENT


@dataclass(frozen=True)
class Case:
    family: str
    text: str
    expected: str | None  # 기대하는 kind (None = 제약이 아님)
    note: str = ""


# ── 1~3. 단일 메시지 케이스 ─────────────────────────────────────────────────
# 모든 문장은 이 문서 작성을 위해 **새로 만든 합성 문장**이다.
CASES: tuple[Case, ...] = (
    # A. 사전 안의 직접 표현 (기대: 잡힘)
    Case("A_direct", "네트워크 사용은 금지합니다", PROHIBITION),
    Case("A_direct", "외부 API 호출하지 마", PROHIBITION),
    Case("A_direct", "이 작업은 오프라인 으로만 진행해", PROHIBITION),
    Case("A_direct", "Do not call the network", PROHIBITION),
    Case("A_direct", "Never push to main", PROHIBITION),
    Case("A_direct", "배포 전에 반드시 나에게 물어봐", APPROVAL),
    Case("A_direct", "Ask before you deploy", APPROVAL),
    Case("A_direct", "승인 받고 진행해줘", APPROVAL),
    Case("A_direct", "이 설정은 반드시 유지해줘", REQUIREMENT),
    Case("A_direct", "Keep the existing schema", REQUIREMENT),
    # B. 같은 뜻, 사전 밖 표현 (기대: 잡혀야 함 — 실제로는 놓칠 것으로 보는 케이스)
    Case("B_paraphrase", "네트워크는 꺼 두고 작업해줘", PROHIBITION, "금지/차단 계열 cue 없음"),
    Case("B_paraphrase", "외부로는 나가지 않게 해줘", PROHIBITION, "'않게' 는 cue 가 아니다"),
    Case("B_paraphrase", "그 파일은 건드리지 않는 게 좋겠어", PROHIBITION, "'건드리지' 미등록"),
    Case("B_paraphrase", "이번엔 로컬에서만 돌려줘", PROHIBITION, "'로컬에서만' 미등록"),
    Case("B_paraphrase", "Avoid touching production", PROHIBITION, "'avoid' 미등록"),
    Case("B_paraphrase", "Please hold off on the migration", PROHIBITION, "'hold off' 미등록"),
    Case("B_paraphrase", "그건 실행하기 전에 나한테 알려줘", APPROVAL, "'알려줘' 는 approval cue 아님"),
    Case("B_paraphrase", "내가 오케이 할 때까지 기다려", APPROVAL, "'오케이' 미등록"),
    Case("B_paraphrase", "Let me decide that one", APPROVAL, "'let me' 미등록"),
    Case("B_paraphrase", "이 부분은 그대로 두는 게 좋아", REQUIREMENT, "'그대로' 미등록"),
    Case("B_paraphrase", "그 값은 바뀌면 안 돼", REQUIREMENT, "'바뀌면 안 돼' — 금지 cue 도 아님"),
    Case("B_paraphrase", "We should stick with the current layout", REQUIREMENT, "'stick with' 미등록"),
    # C. 사전 표현이 들어 있지만 제약이 아닌 문장 (기대: None — 실제 오검출을 확인하려는 케이스)
    Case("C_false_positive", "이 버그 재현되면 blocking 인지 봐줘", None, "'block' 부분일치"),
    Case("C_false_positive", "오프라인 미팅 얘기가 있었어", None, "'오프라인' 부분일치"),
    Case("C_false_positive", "keep going, 결과만 보여줘", None, "'keep' 부분일치"),
    Case("C_false_positive", "그 라이브러리는 only 테스트에서 써", None, "'only' — 지시는 아님"),
    Case("C_false_positive", "제한적인 상황이라고 생각해", None, "'제한' 부분일치"),
    Case("C_false_positive", "mustard 색으로 바꿔줘", None, "'must' 부분일치"),
    Case("C_false_positive", "이 로그 좀 봐주세요", None, "대조군: cue 없음"),
)

# ── 4~5. supersede 케이스 (제약 문장 → 후속 문장) ────────────────────────────
SUPERSEDE_CASES: tuple[tuple[str, str, bool, str], ...] = (
    ("네트워크 사용은 금지합니다", "이제부터 네트워크 써도 돼, 더 이상 금지 아님", True, "명시적 해제"),
    ("배포 전에 반드시 물어봐", "그 규칙 취소할게", True, "취소"),
    ("Always keep the schema", "You can change the schema now, no longer required", True, "영문 해제"),
    ("네트워크 사용은 금지합니다", "이 파일 좀 변경해줘", False, "'변경' 이 편집 요청"),
    ("배포 전에 반드시 물어봐", "그거 대신 이걸로 해줘", False, "'대신' 이 치환 요청"),
    ("Always keep the schema", "이번엔 다른 방법으로 해보자", False, "'다른 방법' — supersede 아님"),
    ("네트워크 사용은 금지합니다", "새 스크립트 하나 만들어줘", False, "대조군: supersede 없음"),
)


def measure_messages() -> tuple[Counter[str], list[Case], list[Case]]:
    stats: Counter[str] = Counter()
    misses: list[Case] = []
    false_positives: list[Case] = []
    for case in CASES:
        actual = detect_kind(case.text)
        stats["total"] += 1
        stats[f"family:{case.family}"] += 1
        hit = actual == case.expected
        if hit:
            stats["hit"] += 1
            stats[f"hit:{case.family}"] += 1
        else:
            stats[f"miss:{case.family}"] += 1
            (misses if case.expected is not None else false_positives).append(case)
            print(f"  [X] {case.family:18s} expected={case.expected} actual={actual} — {case.text!r}")
            if case.note:
                print(f"      note: {case.note}")
    return stats, misses, false_positives


def measure_supersede() -> tuple[int, int, list[tuple[str, str, bool, str]]]:
    ok = 0
    bad: list[tuple[str, str, bool, str]] = []
    for existing, followup, expected, note in SUPERSEDE_CASES:
        cue = detect_supersede(followup)
        actual = cue is not None
        if actual == expected:
            ok += 1
            print(f"  [O] supersede={actual} cue={cue!r} — {followup!r} ({note})")
        else:
            bad.append((existing, followup, expected, note))
            print(f"  [X] supersede={actual} expected={expected} cue={cue!r} — {followup!r} ({note})")
    return ok, len(SUPERSEDE_CASES), bad


def measure_end_to_end() -> tuple[int, int, list[str]]:
    """cue 가 아니라 **실제 경로**(`update_from_messages`)에서 피해가 나는지 본다.

    cue 오검출은 그 자체로 피해가 아니다. 피해는 ① 평범한 요청이 제약으로 승격되거나
    ② 기존 제약이 잘못 `superseded` 로 내려가 프롬프트에서 사라질 때 발생한다.
    supersede 는 **토큰 교집합**이 있어야 하므로, 그 조건이 성립하는 현실적인 시나리오를 쓴다.
    """
    # (이름, (사용자 발화…), 추적 대상 문장, 기대 상태: active|superseded|absent, 설명)
    scenarios: tuple[tuple[str, tuple[tuple[str, str], ...], str, str, str], ...] = (
        (
            "명시적 해제(정상 동작)",
            (("user", "네트워크 사용은 금지합니다"), ("user", "이제부터 네트워크 써도 돼, 더 이상 금지 아님")),
            "네트워크 사용은 금지합니다",
            STATUS_SUPERSEDED,
            "진짜 해제 → superseded 가 맞다(양성 대조군)",
        ),
        (
            "다른 주제의 편집 요청",
            (("user", "네트워크 사용은 금지합니다"), ("user", "이 파일 좀 변경해줘")),
            "네트워크 사용은 금지합니다",
            STATUS_ACTIVE,
            "토큰 교집합이 없어 기대대로 유지된다",
        ),
        (
            "같은 파일 + '변경'",
            (("user", "이 파일은 수정하지 마"), ("user", "이 파일 좀 변경해줘")),
            "이 파일은 수정하지 마",
            STATUS_ACTIVE,
            "한국어 조사 때문에 토큰이 안 겹쳐 supersede 가 안 걸릴 수 있다(측정 대상)",
        ),
        (
            "승인 규칙 표현이 사전 밖",
            (("user", "변경 전에는 먼저 확인해줘"),),
            "변경 전에는 먼저 확인해줘",
            STATUS_ACTIVE,
            "승인 규칙으로 구조화돼야 하는데, '확인해줘' 가 approval cue 가 아니라 사라졌는지",
        ),
        (
            "영문 'instead' + 토큰 교집합",
            (("user", "Always keep the deploy rule"), ("user", "Use instead the new deploy config")),
            "Always keep the deploy rule",
            STATUS_ACTIVE,
            "'instead' 는 supersede cue 이고 'deploy' 가 겹친다 — 편집 요청이 상시 규칙을 내리는가",
        ),
        (
            "평범한 요청의 제약 승격",
            (("user", "mustard 색으로 바꿔줘"),),
            "mustard 색으로 바꿔줘",
            "absent",
            "제약이 아니어야 한다(승격되면 프롬프트 오염)",
        ),
    )
    ok = 0
    problems: list[str] = []
    for name, speech, tracked, expected, note in scenarios:
        memory = SummaryMemory()
        messages = [{"id": f"m{i}", "role": role, "content": content} for i, (role, content) in enumerate(speech)]
        update_from_messages(memory, messages, revision=1)
        found = next((c for c in memory.constraints if c.text == tracked), None)
        actual = "absent" if found is None else found.status
        good = actual == expected
        marker = "[O]" if good else "[X]"
        print(f"  {marker} {name}: status={actual} (기대 {expected}) kind={getattr(found, 'kind', None)}")
        print(f"      {note}")
        if good:
            ok += 1
        else:
            problems.append(f"{name}(기대 {expected}, 실제 {actual})")
    return ok, len(scenarios), problems


def main() -> int:
    print("=== 1~3. 메시지 → kind 판정 (합성 코퍼스) ===")
    stats, misses, false_positives = measure_messages()
    for family in ("A_direct", "B_paraphrase", "C_false_positive"):
        total = stats[f"family:{family}"]
        hit = stats[f"hit:{family}"]
        print(f"  {family:18s} {hit}/{total}")
    print(f"  전체              {stats['hit']}/{stats['total']}")

    print("\n=== 4~5. supersede 판정 ===")
    ok, total_sup, bad_sup = measure_supersede()
    print(f"  {ok}/{total_sup}")

    print("\n=== 6. 실제 경로(update_from_messages)에서의 피해 여부 ===")
    e2e_ok, e2e_total, e2e_bad = measure_end_to_end()
    print(f"  {e2e_ok}/{e2e_total}")

    print("\n=== 요약 ===")
    print(
        f"  감지 실패(blind spot) {len(misses)}건 · 잘못 감지(false positive) {len(false_positives)}건 · supersede 오류 {len(bad_sup)}건 · 경로 피해 의심 {len(e2e_bad)}건{(' ' + str(e2e_bad)) if e2e_bad else ''}"
    )
    print("  ※ 이 코퍼스는 **합성**이라 실사용 회수율이 아니다(설계: nx01/cue-lexicon-measurement.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
