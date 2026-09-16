---
title: NX-02 원본 이력과 제한된 prompt view 분리 — 구현 인계
created: 2026-09-16
state: REVIEW (구현·시험 green, 독립 검토 대기)
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
adr: ../../adr/ADR-DAT-02-conversation-history-journal.md
depends_on: docs/qa/2026-09-16-followup/nx01/handoff.md
tags: [nx-02, conversation-store, journal, adr, handoff]
---

# NX-02 인계 기록 (구현 완료 / REVIEW)

```text
Task ID / attempt: NX-02 / attempt-002
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토 필요)
State: REVIEW — ADR-DAT-02 대로 구현·시험 완료. 커밋하지 않았다.
Baseline full SHA: ffb0ebb312b76d86742d3e4065628a9704f8268e
Dirty paths (secret contents excluded): src/antigravity_k/engine/conversation_journal.py(신규),
  src/antigravity_k/engine/conversation_store.py, src/antigravity_k/engine/summary_memory.py(NX-01),
  src/antigravity_k/api/routes/conversation_api.py, src/antigravity_k/api/contracts/conversation.py,
  src/antigravity_k/api/contracts/errors.py, scripts/migrate_conversation_storage.py,
  tests/test_nx02_history_journal.py(신규), tests/test_fr05_conversation_authoritative_reads.py,
  tests/test_nx01_compaction_retention.py, tests/test_val02_conversation_multiprocess.py,
  tests/fixtures/commercial_ga/arc01_request_execution_context.json,
  dashboard/src/api/fixtures/arc01_request_execution_context.json, docs/qa/2026-09-16-followup/nx02/**
Scope / files / symbols: ConversationStore(append/compact/fork/delete_conversation/original_history/
  history_state/export_original_history/backfill_journal/_commit_event/_materialize_from_journal/
  _reconcile_view_with_journal/_ensure_journal_base/_journal_errors/_cross_process_lock),
  ConversationJournal(append/read/tail/rewrite_without_truncated_tail/fingerprint), replay(),
  base_event_from_view(), is_original(), api /v1/conversations/{id}/history|export|DELETE.
Preconditions / dependency evidence: NX-01(REVIEW) memory schema 재사용, NX-00 기준선,
  nx02/caller-trace.txt(호출자 추적), ADR-DAT-02 §1·§2(저장 위치 결정).
Observed failure before / exact reproduction: before-run-output.json.txt (exit 3).
  40턴 append + compact(retain_tail=4) 후 client 이력 5건, turn-0 소실, 원본 조회 API 없음,
  journal 파일 없음. 드라이버 repro_nx02_view_only.py 는 store_module 경로를 보고서에 남긴다.
Change and invariant: journal = 원본(append-only jsonl), .json = materialized view.
  commit 은 journal line+fsync, view 는 journal_seq 로 지연 감지해 replay 재생성.
  revision 계약(1 append = 1 revision), soft max 64, retain_tail 6, 임계값은 불변.
  originals 는 provenance != summary 만 포함(요약을 원문으로 제시하지 않음).
  삭제는 같은 잠금에서 delete 이벤트 + 표식 + 파일 제거, 삭제 id 재사용 금지.
Commands / cwd / exit codes / environment: commands.txt (모두 cwd=레포 루트).
Runtime expected vs observed: after-run-output.json.txt (40/40 원문 복구, view 5건 bounded),
  migration-report.txt (dry-run → applied → already_migrated → verified).
Regression results / raw log paths / hashes: regression.txt
  - tests/test_nx02_history_journal.py 14 passed (수용 조건 10종 + API 표면)
  - 관련 12파일 130 passed (CR-01 마이그레이션·FR-05·VAL-02·NX-01·NX-03·ARC-01 fixture 포함)
  - 전체 6448 passed / 9 skipped (test_benchmark_performance.py 제외,
    CR-14 fence 검사는 git history 만 읽어 후보 커밋 이동으로 이미 실패 — 작업 트리 무관)
  - ruff All checks passed! / mypy Success: no issues found in 5 source files
Data migration / backup / rollback observed: migration-report.txt. 기존 CR-01 절차(dry-run → backup →
  원자 교체 → 검증 → marker)에 journal backfill 단계를 추가했다. backup sha256·멱등·충돌 차단은
  tests/test_cr01_conversation_identity.py 19 passed 로 유지된다. rollback: journal 을 모르는 이전
  바이너리로 자동 전환 금지(ADR §downgrade), v2 view 는 남아 있으므로 journal 파일을 제거하면
  구버전 동작으로 되돌아간다(운영자 판단, 문서화 필요).
Unverified / reason / impact: (1) 실제 사용자 storage 디렉터리 migration 은 실행하지 않았다
  (테스트 fixture·임시 디렉터리만 사용). (2) journal 의 장기 디스크 사용량(retention/quota)은
  ADR §8 릴리스 blocker 로 남아 있고 기본값을 정하지 않았다(자동 prune 없음). (3) 다음 항목은
  코드 추론이며 실측 아님: 대시보드가 "messages == 전체 이력" 을 가정하는 화면은 NX-09 에서 확인 필요.
Reviewer verdict / reviewed SHA / artifact: 미지정 — 독립 검토 필요.
Next owner / exact next action: NX-09 로 "view vs originals" 를 소비하는 대시보드/클라이언트 표면을
  확인하고, 남은 카드(NX-04/05/06/07/08/10)를 19번 체크리스트 순서대로 진행한다.
  NX-02-F01(신규): engine/slash_commands_session.py:311-315 가 `after.prompt_messages()` 를
  세션 저장소 messages 에 덮어써 두 번째 durable store 를 view 로 오염시킨다.
```

## 1. 파일·데이터 지도

| 경로 | 역할 |
|---|---|
| `v2/<sha(project)>/<sha(conv)>.jsonl` | **원본**(append-only). `agk.conv-journal.v1`, seq 1..N |
| `v2/<sha(project)>/<sha(conv)>.json` | **materialized view**(bounded prompt view + summary + NX-01 `memory` + `journal_seq`) |
| `v2/<sha>/<sha>.deleted.json` | 삭제 표식(NX-02, 세션 tombstone(NX-03)과 별개 저장소) |
| `v2/<sha>/<sha>.jsonl.tail-recovery-<stamp>.bin` | 미커밋으로 판정된 잘린 tail 원문(삭제하지 않음) |
| `migration_v2.json` | CR-01 마커 + `journal_backfilled` 건수 |

이벤트: `base`(뷰 스냅샷 backfill) / `append` / `compact`(요약 + retained ids + memory) /
`fork`(새 id 의 시작점) / `delete`.

## 2. 계약 (구현이 보장하는 것)

1. **쓰기 경로**: 모든 변경은 journal line + fsync 가 commit. view 는 파생물이며 실패해도
   다음 읽기에서 replay 된다(시험 4). view 쓰기 실패는 호출자에게 전파된다.
2. **revision**: CAS 는 flock 안에서 journal tail 의 revision 으로 평가. 압축을 동반한 append 도
   이벤트 1건·revision 1 증가(시험 1·6).
3. **읽기 표면 분리**: 기존 `GET /v1/conversations/{id}` 응답 형태는 그대로(호환).
   원문은 `GET /v1/conversations/{id}/history`(offset/limit/total/journal_seq/history_incomplete),
   export 는 `…/export`(journal sha256 포함). 삭제된 대화는 404 + `reason`.
4. **삭제**: `DELETE /v1/conversations/{id}` — `expected_revision` 선택 CAS, 409는
   `stale_conversation_revision`. 응답은 `erased_scope` 와 "저장소 밖 사본은 지웠다고 주장하지 않음" note.
   삭제 id 재사용 금지(재생성 시 `ConversationNotFoundError`).
5. **손상/중단**: 잘린 tail 은 미커밋으로 보고·격리, 중간 손상은 409 `conversation_history_corrupt`
   (line/offset) 로 hard error. journal IO/상위 schema 는 503 `conversation_history_unavailable`.
   두 코드는 `CONTEXT_ERROR_HTTP_STATUS` 와 ARC-01 fixture(파이썬/대시보드 동일 바이트)에 등록했다.
6. **migration**: 기존 v2 view 는 `base` 이벤트로 1회 backfill(멱등). 요약이 있던 view 는
   `history_incomplete=true` 로 남고 원문을 창작하지 않는다(시험 10). `--verify-only` 는 v2 트리의
   모든 view 에 journal 이 있는지 검사한다.
7. **originals 정의**: provenance `summary` 는 originals 에 포함하지 않는다(요약을 원문 턴으로
   제시하지 않음). `history_incomplete` 가 "원문이 일부 없다" 를 표시한다.

## 3. 시험 ↔ 수용 조건 매핑 (`tests/test_nx02_history_journal.py`, 14건)

| 카드 수용 조건 | 시험 |
|---|---|
| 1) 1,000+ round-trip | `test_round_trip_1000_originals_with_bounded_view` (1001턴) |
| 2) view 상한 유지 | 위 시험 + `test_compaction_keeps_originals_and_view_is_rebuilt_from_journal` |
| 3) migration 멱등/dry-run/backup | `test_migration_backfills_journals_idempotently`, `test_verify_only_reports_missing_journal_without_rewriting` (+ CR-01 19건) |
| 4) 단계별 crash injection | `test_crash_after_journal_commit_recovers_view` |
| 5) disk-full/권한 | `test_journal_write_failure_preserves_state_and_is_explicit` |
| 6) 2 프로세스 경쟁 | `test_two_process_append_race_keeps_journal_order`, `test_two_process_append_delete_race_never_resurrects` |
| 7) 삭제 후 조회/export | `test_delete_removes_originals_and_export`, `test_api_history_export_and_delete_surface` |
| 8) tail 잘림 | `test_torn_tail_is_uncommitted_and_moved_aside` |
| 9) 중간 손상 오프셋 | `test_corrupt_committed_line_reports_offset_and_is_not_skipped`, `test_api_history_rejects_bad_paging_and_reports_corruption` |
| 10) 구버전 `history_incomplete` | `test_legacy_view_with_summary_backfills_history_incomplete` |

## 4. 기존 시험을 바꾼 이유 (검토 시 확인 필요)

| 파일 | 변경 | 근거 |
|---|---|---|
| `tests/test_fr05_conversation_authoritative_reads.py` | "view 삭제 = 삭제" → "view 삭제는 replay 복구, journal 까지 사라지면 캐시 무효" | view 가 파생물이 된 계약 변경(ADR §2). 캐시 무효화 의도는 유지 |
| `tests/test_nx01_compaction_retention.py` | summarizer 실패 시나리오의 초기화가 view 뿐 아니라 journal 도 제거 | view 삭제가 더 이상 대화를 리셋하지 않음 |
| `tests/test_val02_conversation_multiprocess.py` | 유실 계수 기준을 압축된 view → `original_history` 로 변경, view ≤ 64 단언 추가 | view 는 soft max 64 로 bounded 이므로 성공 수와 같을 수 없다(NX-04 의혹과 같은 지점). F2 계약(침묵 덮어쓰기 0)은 그대로 검증 |
| `tests/fixtures/.../arc01_request_execution_context.json` + dashboard 동일 파일 | 새 오류 코드 2종 추가 | `test_fixture_error_http_status_matches_python_contract` 가 맵 전체 동등성을 요구. 두 파일 바이트 동일성도 유지 |

## 5. 잔여 위험 / 후속

- **NX-02-F01(신규)**: `slash_commands_session._cmd_compact` 가 `after.prompt_messages()` 를 세션
  저장소에 덮어쓰고 저장한다 → 두 번째 durable store 도 view 로 오염. 이번 카드 범위 밖(저장 포맷 변경 아님).
- ~~**retention/quota 미정**: journal 은 총 턴 수에 비례해 커진다. ADR §8 의 릴리스 blocker.~~ →
  **결정·구현(2026-09-16, NX-10 동결 배치)**: 대화당 soft 64 MiB 경고 / hard 512 MiB **쓰기 거절**(507
  `conversation_history_quota_exceeded`), **자동 prune 없음**(ADR 의 silent-pruning 금지). 값은
  `AGK_CONVERSATION_JOURNAL_{SOFT,HARD}_CAP_MB`(`0`=비활성), 관측은 `ConversationStore.store_usage()`.
  근거·한계: [retention-decision.md](retention-decision.md), 계약:
  `tests/test_nx02_journal_retention.py`(9 passed). 저장소 **전체** 상한은 관측만 한다(쓰기 경로에
  O(대화 수) 스캔을 넣지 않는다).
- **손상된 대화의 삭제 경로 없음(의도적)** → **운영 절차는 문서화했다(2026-09-16, NX-10 창)**:
  `delete_conversation` 이 `_authoritative_record` 로 journal 을 읽으므로 **손상 시 삭제도 거절**된다
  (성공으로 감추지 않는 안전 측 동작). 실측 프로브(`repro_corrupt_disposal.py` · `corrupt-disposal-output.txt`)가
  네 케이스를 확인했다: view 손상 → 읽기·삭제 모두 `ConversationIntegrityError` / journal 손상 → 같은 경로가
  `ConversationHistoryCorruptError` / **격리 이동 + 삭제 표식**(코드 변경 없음) → `deleted=True`·`get()=None`·
  id 재사용 금지·원본 바이트 보존 / **⚠ 격리 디렉터리를 저장소 루트 안에 두면** `legacy_requires_migration` 이
  되어 무관한 정상 대화까지 `ConversationStorageMigrationRequiredError` 로 전부 실패한다.
  절차·선택지(A안 제품 flag, B안 운영 절차, C안 복구)와 미결정 4항: [damaged-conversation-disposal.md](damaged-conversation-disposal.md).
  `docs/09` 의 복구 표·"기대하면 안 되는 것" 에도 반영.
  **실데이터 사본 리허설까지 완료**(`rehearse_real_store_quarantine.py` · `rehearsal-real-store-output.txt`):
  사용자 저장소 복사본(레거시 3개 대화)에서 CR-01 migration(`dry-run`→`apply`(`journal_backfilled: 3`)→`verify-only`)과
  격리 절차를 연속 실행 — 손상 거절 → 격리 → `deleted=True` → id 재사용 금지 → **형제 대화 정상** →
  **원본 해시 불변**(4개 파일). 음성 대조군으로 앞서 적은 함정의 조건도 정정했다: 루트 안 격리가
  치명적인 것은 **마이그레이션 완료 표식이 없는** 저장소이고(실측 A), 표식이 있으면 레이아웃·읽기·`--verify-only`
  모두 통과한다(실측 B).
  **남은 것은 사람의 몫**: 소유자 지정, A안(제품 폐기 flag) 채택 여부, 격리본 보존 기간.
  손상 파일을 기본 삭제로 밀어버리는 수정은 이 카드에서 하지 않았다(NX-08 vault 재검증도 같은 이유로 안 다룸).
- **세대/삭제 표기**: 세션(NX-03 `generation`/tombstone)과 conversation(journal `delete`/표식)은
  서로 다른 저장소다. 통합 조회가 필요하면 별도 카드로 결정해야 한다.
- **대시보드 가정**: "messages == 전체 이력" 을 가정하는 화면이 있는지 NX-09 에서 확인.
- **미커밋 상태**: 커밋은 요청받지 않아 하지 않았다. 후보 커밋을 만들면 CR-14 fence 규칙
  (`docs/`·`.omo/` 외 경로 이동 금지)을 먼저 확인해야 한다.
