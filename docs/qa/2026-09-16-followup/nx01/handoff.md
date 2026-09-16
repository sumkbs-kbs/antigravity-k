---
title: NX-01 반복 압축에서 요구사항·결정 보존 — 인계
created: 2026-09-16
state: REVIEW
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
depends_on: docs/qa/2026-09-16-followup/nx00/handoff.md
tags: [nx-01, conversation-store, compaction, retention, handoff]
---

# NX-01 인계 기록

```text
Task ID / attempt: NX-01 / attempt-001
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토자 필요, REVIEW)
State: REVIEW — red 재현 + 구현 + 회귀 green. 독립 검토·실사용 동선(NX-09)은 미실시
Baseline full SHA: ffb0ebb312b76d86742d3e4065628a9704f8268e (시작·종료 동일, 커밋 없음)
Dirty paths (secret contents excluded): src/antigravity_k/engine/summary_memory.py(신규),
  src/antigravity_k/engine/context_summary.py, src/antigravity_k/engine/conversation_store.py,
  tests/test_nx01_compaction_retention.py(신규), docs/qa/2026-09-16-followup/nx00/**(신규), nx01/**(신규)
Scope / files / symbols:
  - summary_memory.py: SummaryMemory/Constraint, detect_kind, detect_supersede, update_from_messages,
    record_generation, render_constraint_block, render_marker, compose_summary, carryover_prose
  - context_summary.py: summarize_messages(+memory/+carryover/+budget), _summary_prompt
  - conversation_store.py: ConversationRecord.memory, _build_compaction_summary,
    _inline_compact_messages, compact, fork(요약 provenance 유지)
Preconditions / dependency evidence: NX-00 기준 확보(HEAD ffb0ebb, 원본 soak artifact 보존).
Observed failure before / exact reproduction: nx01/before-run-output.json.txt
  (appends 123 → messages 7, early_requirement_in_prompt=false, summary_chars 170→130)
Change and invariant: 압축 세대가 늘어도 사용자 명시 제약을 구조+prose 로 보존.
  revision 계약(논리 append 1회=revision 1증가)과 retain_tail 6, prompt 상한 불변.
Commands / cwd / exit codes / environment: nx01/regression.txt (모두 exit 0), nx00/commands.txt
Runtime expected vs observed: nx01/after-run-output.json.txt (appends 123 → 제약 유지, 재로드 후에도 유지)
Regression results / raw log paths / hashes: nx01/regression.txt (대상 3스위트 green, 전체 6439 passed)
Data migration / backup / rollback observed: migration 없음(추가 필드). 구버전 레코드 로드 시험 포함.
  rollback 은 임시 데이터 대상으로만 검증(아래 §5 참조).
Unverified / reason / impact:
  - 실제 LLM summarizer(유료 provider) 경로는 미실행 — fake/예외만 시험.
  - cue lexicon 밖 표현의 요구사항은 구조화되지 않는다(§6 한계).
  - 브라우저/API 실사용 동선과 재시작 동선은 NX-09 소관.
  - 구버전 바이너리로 downgrade 시 `memory` 필드가 다음 저장에서 사라진다(§5).
Reviewer verdict / reviewed SHA / artifact: 미지정 — REVIEW.
Next owner / exact next action: 독립 검토자는 nx01/repro_nx01_compaction.py 를 raw artifact 로
  재실행하고, tests/test_nx01_compaction_retention.py 의 assertion 이 약화되지 않았는지 확인한 뒤
  ACCEPT/REVISE 를 판정한다. 이후 NX-02(원본 이력 분리) 담당자에게 schema 를 인계한다.
```

## 1. 확정 원인

`ConversationStore.append`는 soft max(기본 64)를 넘으면 `_inline_compact_messages`로
`old = messages[:-6]`을 요약하고 `summary_msg + 마지막 6개`로 치환한다.

- append 65회: old 59개 → 요약 생성. 이때 요약문에는 `[user]: …` 형태로 **초기 제약이 포함**된다(관측: `early_requirement_present: true`).
- append 66~122회: 7개 + 57 = 64개 → 트리거 미달, 변화 없음.
- append 123회: 65 > 64 → 다시 압축. 이때 `old`에 **이전 요약 메시지**(role=`system`, provenance=`summary`)가 포함되는데,
  `summarize_messages`의 deterministic fallback은 `role in ("user","tool")`만 key_messages로 뽑는다.
  → 이전 요약문이 통째로 버려지고, 그 세대의 새 user 메시지 5개만 남아 초기 제약이 소실된다.
- 관측값: `messages 7`, `summary_chars 170 → 130`, `early_requirement_present false`.

즉 결함의 본질은 **"저장소가 만든 요약이 다음 세대의 요약 대상에서 권위를 잃는다"** 이다.

## 2. 변경

### 2.1 `engine/summary_memory.py` (신규)

- `Constraint`: `id`(텍스트 정규화 sha1 선두 10자 — 같은 문장은 같은 id), `kind`(requirement/prohibition/approval),
  `status`(active/superseded), `source_message_id`, `source_revision`, `superseded_by`, `superseded_reason`.
- `SummaryMemory`: `schema`(`agk.summary.v1`), `generation`, `constraints`, `summarized_ranges`(세대별 출처 범위), `carried_summary`.
  레코드 JSON의 `memory` 키로 저장되며, 키가 없는 구버전 레코드는 빈 상태로 로드된다.
- `update_from_messages`: **role == "user" 만** 제약을 만들거나 기존 항목을 supersede 할 수 있다.
  tool/assistant/citation 텍스트는 절대 승격되지 않는다(계약 e).
- supersede 는 명시적 표현(예: "더 이상", "이제부터", "취소", "no longer", "instead")이 있고
  **토큰 교집합이 있는** 기존 active 항목에만 적용하며, 기존 항목을 삭제하지 않고 `status`만 바꾼다(계약 a).
- `compose_summary`: header → 제약 블록 → 이전 요약 prose → 새 요약 prose → marker 순으로 조립하고
  전체 `SUMMARY_TEXT_BUDGET_CHARS = 4000` 예산을 적용한다(계약 d). 예산 때문에 prompt 에서 빠진 항목 수는
  문장으로 명시되고, 구조화 저장소에는 남는다(무음 유실 금지).
- marker(`<!-- agk-summary schema=… g=… c=… a=… b=… -->`)로 저장소 생성 요약임을 식별한다.
  단, **구조화 상태(제약/이월 요약)가 없으면 marker를 붙이지 않는다** — 모든 세대에 고정 비용을 붙이면
  기존 "압축 후 tokens 감소" 계약을 깨기 때문이다. 이 경우에도 `provenance="summary"`와 레코드의 `memory.schema`로 구분된다.

### 2.2 `engine/context_summary.py`

- `summarize_messages(..., memory=None, carryover="", budget=…)` — 기존 호출자는 인자 없이 그대로 동작(레거시 형태 유지, marker 없음, 빈 경우 System Note 유지).
- 이전 요약 prose(`carryover`)를 명시적으로 이월한다(계약 a의 두 번째 안전망).
- 제약으로 이미 보존된 메시지는 prose에서 중복 제거하고, 동일한 tool evidence 블록은 1회만 남긴다(prompt budget 회수).
- `memory`가 있으면 LLM 프롬프트에도 보존 제약을 함께 넣어 요약이 제약을 지우지 않도록 유도한다.

### 2.3 `engine/conversation_store.py`

- `ConversationRecord.memory: SummaryMemory`(to_dict/from_dict 왕복), `_build_compaction_summary`로
  `_inline_compact_messages`와 `compact`가 같은 로직을 쓰도록 통합.
- `fork`는 구조화 상태를 deepcopy 하고, 복사된 요약 메시지의 provenance 를 `summary`로 유지한다.
- **revision 계약 불변**: 내부 압축은 revision 을 올리지 않고, `compact()`만 1회 올린다.
- `retain_tail=6`, `_DEFAULT_SOFT_MAX_MESSAGES=64`, 임계값·환경변수 이름 모두 불변.

## 3. 검증 결과

| 시험 | 도구 | 결과 |
|---|---|---|
| 64/65/122/123 경계 재현 (before) | `repro_nx01_compaction.py` + HEAD 모듈 | 123회에서 초기 제약 소실 (`false`) |
| 동일 경계 (after) | 같은 driver | 64/65/122/123 모두 유지, 재로드 후에도 유지, active=1 |
| 카드 필수 시험 10종 | `tests/test_nx01_compaction_retention.py` | 10 passed |
| 기존 좁은 회귀 | `test_val02_conversation_multiprocess.py` + `test_cr02_session_durability.py` | 21 passed (기준과 동일) |
| 대화/컨텍스트 회귀 8파일 | `test_fr_context_end_to_end` 등 | 70 passed |
| 전체 스위트 | `pytest tests` | 6439 passed, 10 skipped, 1 failed(기존 CR-14 fence 테스트) |

테스트가 요구하는 세부:

- `cap0`은 자동 압축을 끄고 `generation == 0`, `summary is None`을 유지한다.
- `soft_max = 7`이 실질 최소치다(요약 1 + tail 6). 그 미만은 bounded 계약을 만족할 수 없어 시험하지 않았다(사전 동작과 동일).
- Unicode(`❄️`)·장문(40회 반복) 메시지에서도 제약과 예산이 유지된다.
- summarizer 가 예외(TimeoutError)를 던지거나 빈 문자열을 반환해도 제약은 남는다.

## 4. 하지 않은 것 (정직한 경계)

- **이미 소실된 과거 원문은 복구하지 않는다.** NX-01 이전에 압축으로 사라진 원문은 어디에도 없으며, 이번 변경은
  이후 세대에서의 소실을 막는다. 원본 이력/복구는 NX-02 의 범위다.
- 사용자 이력 전체를 무한히 붙이는 방식은 쓰지 않았다(카드의 불합격 조건). 보존 항목은 128 active / 32 superseded 로 유계다.
- 실제 유료 provider LLM 요약 경로는 실행하지 않았다(비용·외부 호출 미승인). fake summarizer/예외로만 검증했다.
- `docs/packaging`, `vault_data`, 인증 백업은 건드리지 않았다.

## 5. rollback

- 스키마는 **추가 필드**만 도입했다. 구버전 레코드(`memory` 키 없음)는 그대로 읽히며, 다음 압축에서 `memory`가 생성된다.
- 반대로 **구버전 바이너리로 downgrade 하면** `memory` 필드를 모르는 `from_dict`/`to_dict`가 다음 저장에서 필드를 떨어뜨린다.
  따라서 downgrade 는 금지하고, 필요 시 (1) 레코드 JSON 을 별도 경로로 백업하고 (2) 구버전 실행은 읽기 전용으로만 사용한다.
  자동 다운그레이드 절차는 제공하지 않는다(계획 NX-01 rollback 조건).
- 제품 데이터 포맷을 되돌릴 때는 반드시 백업 해시와 복구 리허설을 함께 남긴다. 이번 작업은 실사용 store 를 사용하지 않아
  실데이터 rollback 은 실행하지 않았고, 임시 `tmp_path` store 에서만 왕복을 확인했다.

## 6. 남은 한계 / 검토자가 확인할 것

1. **cue lexicon 의존** → **합성 코퍼스 실측을 추가했다(2026-09-16, NX-10 창 · 동결 중 측정·수정 없음)**:
   [cue-lexicon-measurement.md](cue-lexicon-measurement.md) · `cue_lexicon_probe.py` · `cue-lexicon-output.txt`.
   요약: 사전 표현 **9/10**(1건은 `반드시` 우선순위 때문에 approval→requirement 오분류) · 사전 밖 바꿔쓰기
   **0/12**(`"외부로는 나가지 않게 해줘"` 류 전부 누락) · 사전 단어가 든 잡담 **1/7** · supersede cue **5/7**.
   실제 경로에서 **피해 3건** 확인: ① 승인 규칙이 아예 생성되지 않음 ② `instead`+토큰 겹침으로 상시 규칙이
   superseded 로 내려가 프롬프트에서 사라짐 ③ `"mustard 색으로 바꿔줘"` 가 상시 requirement 로 승격(프롬프트 오염).
   어휘 수정 후보 5건과 **실사용 회수율 측정 설계**(2인 라벨링·저장소 밖 라벨 파일·집계만 커밋·제안 임계 — 승격 정밀도 ≥0.90 · 무효화 정밀도 ≥0.95 · 명시 규칙 회수율 ≥0.60)를 문서에 남겼다. **동결 때문에 어휘는 고치지 않았다** — 해제 뒤 진행하고,
   새 cue 를 넣는 카드는 이 합성 회귀를 `tests/` 로 승격해야 한다.
   종전 문구(참고): 목록 밖 표현의 요구사항은 구조화되지 않지만 이전 요약 prose 이월로 최소 한 세대는 살아남는다.
2. **prose 절단**: deterministic fallback 의 key message 는 기존과 동일하게 `[:100]`로 자른다. 제약 구조는 160자까지 보존한다.
3. **marker 조건부**: 구조화 상태가 없는 요약에는 marker가 없다. 저장소 구분은 `provenance`/`memory.schema`로 가능하다.
4. **API 응답 표면**: `ConversationSnapshot` 은 변경하지 않았다. 구조화 제약을 UI/API 로 노출할지는 NX-02·NX-09 에서 결정한다.
5. **CR-14 fence**: `tests/test_cr14_fence_movement_detection.py` 는 후보 `b6003205` 이후 코드 스코프 커밋이 움직였다고
   이미 실패한다(HEAD 에서 재현, 이번 변경과 무관). 이번 변경 파일(`conversation_store.py`, `tests/**`)도 fence 목록에 들어가므로
   **커밋 전에 CR-14 후보/판정을 담당하는 owner 결정이 필요**하다. 커밋·push 는 이번 작업에서 하지 않았다.
