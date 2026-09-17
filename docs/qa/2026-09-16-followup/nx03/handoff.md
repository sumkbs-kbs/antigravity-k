---
title: NX-03 삭제 세션 stale writer 부활 방지 — 인계
created: 2026-09-16
state: REVIEW
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
depends_on: docs/qa/2026-09-16-followup/nx00/handoff.md
tags: [nx-03, session-manager, deletion, tombstone, handoff]
---

# NX-03 인계 기록

```text
Task ID / attempt: NX-03 / attempt-001
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토자 필요, REVIEW)
State: REVIEW — red 재현 + 구현 + 회귀 green. 독립 검토·실사용 UI 동선(NX-09)은 미실시
Baseline full SHA: ffb0ebb312b76d86742d3e4065628a9704f8268e (시작·종료 동일, 커밋 없음)
Dirty paths (secret contents excluded): src/antigravity_k/engine/session_manager.py,
  src/antigravity_k/api/error_handler.py, src/antigravity_k/api/routes/system_api.py,
  tests/test_nx03_session_delete_race.py(신규), docs/qa/2026-09-16-followup/nx03/**(신규)
Scope / files / symbols:
  - session_manager.py: SessionDeletedError(신규), SESSION_GENERATION_FIELD, .tombstones,
    _read_session_payload/_session_generation/_read_tombstone/_write_session_tombstone/_deleted_residue,
    _delete_session_file(신규), _save_session, clear_memory(all), apply_retention,
    load_session, _find_latest_session, list_sessions, _load_session
  - error_handler.py / system_api.py: 409 session_deleted 매핑
Preconditions / dependency evidence: NX-00 기준 확보(HEAD ffb0ebb, soak 원본 보존).
Observed failure before / exact reproduction: nx03/before-run-output.json.txt
  (clear_memory("all") → 파일 삭제·표식 없음 → B.save() 성공·revision 1 → 재시작 시 원본 ID resume·삭제본 재등장)
Change and invariant: 삭제는 per-session 잠금 안에서 tombstone(세대)을 선기록 후 파일 제거.
  tombstone 세대 이하 스냅샷은 같은 ID를 재생성할 수 없다. revision CAS·원자 저장 계약 불변.
Commands / cwd / exit codes / environment: nx03/regression.txt (모두 exit 0), nx00/commands.txt
Runtime expected vs observed: nx03/after-run-output.json.txt (B.save → SessionDeletedError, 파일 없음, 표식 잔존)
Regression results / raw log paths / hashes: nx03/regression.txt (17+120+559 passed, 전체 6455 passed)
Data migration / backup / rollback observed: migration 없음(추가 필드 generation + 표식 파일).
  구버전 레코드(필드 없음) 읽기/저장/삭제 시험 포함. rollback 은 임시 디렉터리에서만 검증.
Unverified / reason / impact:
  - ~~tombstone GC 정책 없음(임의 TTL 금지).~~ → **정책·구현(2026-09-16, NX-10 동결 배치)**:
    자동 만료는 여전히 없다(의도 — 임의 TTL 금지). 대신 운영자 명시 호출
    `SessionManager.collect_tombstones(older_than_seconds=…, dry_run=False)` 가 표식을 **아카이브로
    이동**(삭제 아님) + `gc-report.json` 감사 기록을 남기며, 관측은 `tombstone_usage()` 다. `0`/음수
    기준은 `ValueError`. 근거: [tombstone-gc.md](tombstone-gc.md), 계약:
    `tests/test_nx03_tombstone_gc.py`(6 passed). 표식 파일은 삭제된 세션 ID당 1개이며 자동 만료되지 않는다.
  - 구버전(NX-03 이전) 실행 파일이 남긴 삭제는 표식이 없다 → 그 뒤의 stale writer는 여전히 부활할 수 있다.
    NX-03 이후의 모든 삭제 경로(clear_memory/apply_retention)는 표식을 남긴다.
  - kill -9 는 자식 프로세스 os._exit 로 근사했고, unlink 중단은 fault injection 으로 재현했다(실제 전원 손실 미시험).
  - 삭제-저장의 완전한 선형화는 per-session flock 기준이다. NFS 등 flock 미보장 파일시스템은 미검증.
  - 실제 UI(대시보드)에서 삭제 후 화면 동선은 NX-09 소관.
Reviewer verdict / reviewed SHA / artifact: 미지정 — REVIEW.
Next owner / exact next action: 독립 검토자는 nx03/repro_nx03_session_delete.py 를 raw artifact 로
  재실행하고, tests/test_nx03_session_delete_race.py 의 assertion 이 약화되지 않았는지 확인한 뒤
  ACCEPT/REVISE 를 판정한다. 잔여 의혹은 NX-08(영속화 재검증)로 넘긴다.
```

## 1. 확정 원인 (before 재현)

1. `clear_memory(scope="all")`은 `*.json`을 순회하며 `session_path.unlink()`를 호출했다.
   `current_path` 비교는 **집계 중복만** 피했고 unlink는 모든 파일(현재 세션 포함)에 실행됐다.
2. 삭제는 삭제 표식을 남기지 않았고, per-session 잠금(`_session_process_lock`)도 잡지 않았다.
3. `_save_session`은 `path.is_file()`일 때만 revision을 비교했다. 파일이 없으면 `disk_revision = None` →
   `revision 1`로 새로 썼다. 즉 **B가 보유한 오래된 스냅샷이 신규 세션으로 취급**됐다.
4. 관측: `deleted_count 1`, 파일 0건, `tombstones 0건`, `B.save() 성공`(revision 1),
   `restart_resumed_original true`, 삭제 대상 문구(`SYNTHETIC-DELETED-MARKER`)가 파일·재시작 후 프롬프트에 남음.

## 2. 변경 (고정 계약 α)

- **세대(generation)**: 세션 JSON에 `generation` 필드를 추가한다. 신규·구형 레코드는 첫 저장에서 1,
  이후 저장은 세대를 유지한다(`_base_generation`).
- **삭제 표식(tombstone)**: `<base_dir>/.tombstones/<lock-name>.json`에
  `{schema, session_id, generation, revision, deleted_at}`만 기록한다.
  **세션 본문·PIN 등 민감 내용은 넣지 않는다**(시험으로 확인: `test_tombstone_has_no_session_body_or_secret`).
- **삭제 경로(`_delete_session_file`)**: per-session flock 안에서
  (1) 최신 파일 재독 → (2) 표식 durable 기록(fsync) → (3) 파일 제거.
  표식 기록 실패는 `SessionPersistenceError`로 전파하고 **파일을 남긴다**(삭제 성공으로 보고하지 않음).
  제거 실패(OSError)도 전파한다. 현재 세션은 집계 중복을 피한다.
- **저장 경로(`_save_session`)**: 같은 flock 안에서
  (1) 표식이 있고 `base_generation <= 표식 세대`이면 `SessionDeletedError`,
  (2) 파일이 없고 `base_revision > 0` 또는 `base_generation > 0`이면 `StaleSessionWriteError`
  (삭제 표식 없는 소실은 부활 금지, 신규 세션 생성과 구별),
  (3) 그 뒤 기존 revision CAS와 원자 저장.
- **읽기 경로**: `load_session`/`_find_latest_session`/`list_sessions`는 **표식 세대 ≥ 파일 세대**인
  잔재(삭제가 중단된 파일)를 가시 세션으로 취급하지 않는다. 잔재는 재시도 삭제로 정리된다.
- **retention**: `apply_retention`도 삭제 경로이므로 같은 규칙으로 표식을 남긴다(현재 세션은 계속 보호).
- **API/UI 의미**: `SessionDeletedError.error_code = "session_deleted"`,
  `public_detail = "Session was deleted; reload or start a new session"`.
  `POST /api/session/save`와 전역 handler 모두 **409**로 매핑한다(503 아님 — 클라이언트가 재로드/새 세션으로 회복 가능).
- **정책 결정(명시)**: 삭제된 세션 ID의 재사용(부활)은 허용하지 않는다. 새 세션은 항상 새 UUID다.

## 3. 검증 결과

| 시험 | 도구 | 결과 |
|---|---|---|
| 순차 2인스턴스 repro (before) | HEAD 모듈 + driver | 부활 true (파일·재시작 모두) |
| 같은 repro (after) | 같은 driver | `SessionDeletedError`, 파일 없음, 표식 1건, 재시작 시 새 ID |
| 카드 필수 시험 17종 | `tests/test_nx03_session_delete_race.py` | 17 passed |
| 세션/메모리/라이프사이클 회귀 7파일 | CR-02·memory·claw·ws03 | 120 passed |
| 관련 스위트 전체 | `-k "session or memory or ..."` | 559 passed, 1 skipped |
| 전체 스위트 | `pytest tests` | 6455 passed, 10 skipped, 1 failed(아래 §5) |

카드가 요구한 시험 매핑:

- **barrier 두 프로세스 경쟁 양 순서**: `test_delete_wins_then_stale_process_save_is_refused`,
  `test_save_wins_then_delete_still_blocks_the_next_save` (spawn + `mp.Barrier` + Event).
- **delete 직후 kill9/restart**: `test_hard_exit_after_delete_is_durable_and_not_resumable`
  (자식이 삭제 후 `os._exit(17)`; 부모가 파일 부재·표식 durability·비-resume 확인).
- **삭제 중단(디스크/제거 실패)**: `test_unlink_failure_is_not_reported_as_success_and_residue_is_hidden`,
  `test_tombstone_write_failure_keeps_the_file_and_reports_failure`.
- **두 번 delete**: `test_second_delete_is_a_noop` (두 번째 0, 표식 1건).
- **구버전 load/save/delete**: `test_legacy_record_delete_blocks_legacy_writer`,
  `test_generation_is_persisted_and_upgraded_from_legacy`.
- **scope별 memory 유지**: `test_scoped_clears_keep_the_session_and_other_memory` (working/session/project/global).
- **디스크 실패를 삭제 성공으로 보지 않음**: 위 §1의 두 실패 주입 시험 + 파일 바이트 보존 확인.
- **stale 재시도가 세션 재생성하지 않음**: `test_stale_writer_cannot_recreate_deleted_session`,
  `test_save_failure_does_not_leave_a_partial_session` (3회 반복 저장도 파일 미생성).
- **API/UI 의미 전달**: `test_session_save_maps_delete_to_409`, `test_app_handler_maps_session_deleted`.

## 4. rollback

- 스키마는 **추가 필드(`generation`)와 추가 디렉터리(`.tombstones/`)** 뿐이다.
  NX-03 이전 파일은 그대로 읽히고, 첫 저장에서 세대가 1로 승격된다.
- **구버전으로 되돌리면 표식을 모르는 코드가 tombstone을 무시**하므로 삭제된 세션이 다시 보일 수 있다.
  자동 회귀를 금지하고, 되돌릴 때는 (1) 모든 writer 종료 (2) 세션 파일 부재 확인
  (3) `.tombstones/` 를 백업 후 제거하는 순서를 문서화한다. 표식 제거는 최대 writer 수명 보장이 없으면 하지 않는다.
- 실사용 세션 디렉터리(`~/.antigravity/sessions`)는 이번 시험에 사용하지 않았고, rollback 리허설도 임시 디렉터리에서만 수행했다.

## 5. 전체 스위트의 실패 1건 (NX-03 무관 판정 근거)

`tests/test_benchmark_performance.py::test_context_enrich_total_latency` 가 전체 스위트에서 1회 실패했다.

- 이 테스트는 `CodeTreeIndexer.build_tree()` + `FileSummarizer.summarize_files()` 의 **wall-clock 시간**만 측정한다.
  NX-03 이 건드린 모듈(session_manager/api)을 사용하지 않는다.
- 해당 파일 단독 실행은 16 passed(7.34s)이며, 같은 테스트가 NX-01 작업 후의 전체 실행에서는 통과했다
  (그 실행에서 유일한 실패는 CR-14 fence 테스트였다). 즉 **부하/캐시 상태에 민감한 성능 임계값 테스트**로 판정한다.
- 완전 배제는 NX-10의 고정 후보 전체 실행에서 다시 확인해야 하며, 여기서 "회귀 없음"을 단정하지 않는다.

## 6. 남은 의혹 (NX-08 로 이관)

1. tombstone 누적: 삭제 ID당 1개(수 바이트~수십 바이트). **정책·구현 완료**(위 §한계 참조 — 자동 만료 없음,
   운영자 명시 회수는 아카이브 이동). 장기 운영에서 디스크·목록 성능 영향은 **미측정**으로 남는다
   (회수 시점을 정하려면 실사용 누적률이 필요하다).
2. NX-03 이전에 이미 삭제된 세션(표식 없음)의 stale writer는 여전히 부활 가능하다. 구버전 삭제 이력은 복구 불가.
5. **`NX03-RESTORE-MARKER` — 표식이 원문 읽기 표면을 막지 못한다**(2026-09-17 실측, NX-01 restore 리허설):
   삭제된 대화에 대해 **삭제 전 journal 바이트를 파일로 되돌려 놓으면** `history_state.deleted` 는 표식
   덕에 `true` 로 남지만 **`original_history` 가 원문을 다시 반환**한다(관측 3건; 같은 함수 docstring 은
   “Deleted conversations return an empty list.” 라고 적혀 있다). 즉 표식은 **상태 플래그에만** 적용되고
   읽기 표면은 journal 안의 `delete` 이벤트만 본다 — 백업 복원·디스크 이미지 복구처럼 바이트를 되돌리는
   경로에서 삭제된 대화의 본문이 export 표면으로 나올 수 있다. **동결 중이라 코드는 고치지 않았다**(`src/`
   수정은 도는 8시간 soak 의 지문을 움직인다). 수리안: `original_history`/`export_original_history` 가
   `read_deletion_marker` 도 확인하게 한다(동결 해제 뒤 별도 카드). 운영 절차는 이 상태를 거절한다 —
   근거 [../nx01/restore-rehearsal.md](../nx01/restore-rehearsal.md) §2·§3.
3. `redact`(마스킹) 경로는 여전히 잠금 없이 파일을 직접 덮어쓴다 → NX-08 에서 확인해야 한다.
4. 파일시스템별 `flock`/fsync 신뢰성(NFS 등)은 미검증이다.
