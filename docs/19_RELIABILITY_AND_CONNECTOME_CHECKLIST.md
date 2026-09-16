---
title: Ssak-Ai 신뢰성 및 Connectome 개발 실행 체크리스트
created: 2026-09-16
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
status: partially-implemented (NX-00~NX-10 REVIEW — NX-10 은 후보 고정·필수 게이트 23개 전수 실행[22 passed·1 failed·0 not_run]·NO-GO, NX-06 정적 REVIEW/런타임 BLOCKED, 2026-09-16)
tags: [checklist, agent-handoff, reliability, flywire]
---

# 실행 체크리스트

이 문서는 NX 작업 상태의 단일 원본이고, 제품 전체의 현재 상태(판정·포트 역할·soak 경과·지원 범위·사람 축)는 [현재 상태 요약](20_CURRENT_STATUS.md)이 소유한다. [계획서](18_RELIABILITY_AND_CONNECTOME_DEVELOPMENT_PLAN.md)의 상세 계약과 함께 사용한다. 체크는 증거가 생긴 뒤에만 한다. 현재 완료 표시는 문서 작성, soak JSON 확인, 그리고 2026-09-16 NX-00/NX-01/NX-02/NX-03 작업분이며 제품 출시 완료를 뜻하지 않는다.

## 진행 기록 (최신이 위)

| 날짜 | 카드 | 상태 변화 | 증거 | 남은 일 |
|---|---|---|---|---|
| 2026-09-16 | NX-10 | TODO → **REVIEW/NO-GO** (후보 고정·필수 게이트 **23개 전수 실행**(배치 이전 22 passed · 1 failed · 0 not_run) → **동결 지문 `157311cf…` 에서 22개 중 21 passed · 1 failed**(`gate-report-freeze002.json`); 마감 도구가 지적하는 문제는 `clean-machine-runtime`·`python-tests` 둘) | [nx10/SCOPE.md](qa/2026-09-16-followup/nx10/SCOPE.md), [SCOPE_ADDENDUM.md](qa/2026-09-16-followup/nx10/SCOPE_ADDENDUM.md), [GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md), [handoff.md](qa/2026-09-16-followup/nx10/handoff.md), [EX05_PROMOTION_CONFLICT.md](qa/2026-09-16-followup/nx10/EX05_PROMOTION_CONFLICT.md), `commands.txt`·`runner-exit.txt`·`gate-report-attempt001`~`016`·`full001`·`freeze002`·`newfp-*`·`gate_verify-freeze002.txt`, 러너 6개(`run_remaining_gates.sh`·`run_ambient_gate.sh`·`run_full_gates.sh`·`run_nx10_soak.sh`·`schedule_nx10_soak.sh`·`run_freeze_gates.sh`·`run_clean_machine_gate.sh`), [CLOSURE_RUNBOOK.md](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md), [PROMOTION_PLAN.md](qa/2026-09-16-followup/nx10/PROMOTION_PLAN.md)(보조도구 3종·계약 시험 3종의 `scripts/`·`tests/` 승격 — **완료**(2026-09-16T09:46:05Z, 게이트 7/7, 지문 `157311cf…`→`ab980ba5…`, `.gitignore` 규칙 포함); 첫 두 시도는 이동 0건 롤백, 기록 `promote/promotion-applied.txt`·`promote/dry-run-output.txt`·`promote/{paths,gates}.sh`), `run_promote_gates.sh`(지문 재측정 → `gate-report-promote002.json` 21/22 · `gate-report-promote003.json` **22/23(clean-machine 포함)**), `large-evidence-manifest.md`(1MB 초과 리포트 sha256), **예약 통제** [soak_control.sh](qa/2026-09-16-followup/nx10/soak_control.sh)(`arm`·`status`·`cancel`·`orphans`·`preflight`·`selftest` — 자기시험 **32/32**, `preflight` 는 발화 전 후보 귀속(현재 트리 == HEAD)·의존성·여유 공간 점검)·[SOAK_SCHEDULING.md](qa/2026-09-16-followup/nx10/SOAK_SCHEDULING.md)(살아 있던 예약 4벌 정리 사고와 잡은 결함 4건), soak 회수 판정기 `scripts/collect_soak_result.py`(selftest 6/6)·`soak-recovery-*.json`·`soak-recovery.log`, 마감 전 점검 `scripts/verify_docs_commands.py`·`docs-command-verification.txt`(CLI 플래그·환경변수·경로 검증 + 비밀 스캔 — WARN 1건[인증 해시 백업 미무시]은 `.gitignore` 규칙으로 **종결**, 검사기가 이제 조건을 보고 `[OK]` 로 적는다), `engine/atomic_write.py`·`security/ws_registry.py`(신규 leaf), `engine/vault.py`·`vault_privacy.py`·`model_manager.py`·`provider_adapters/inference_providers.py`·`tool_loop.py`·`api/routes/session_state.py`·`api/auth_routes.py`·`api/routes/network_access_api.py`·`engine/summary_memory.py`·`scripts/val02_staging.py`, `dashboard_dist/**`(재빌드), `tests/test_nx08_vault_durability.py`, **동결 배치**: `api/sse_revocation.py`·`engine/conversation_retention.py`(신규), `engine/conversation_store.py`·`engine/session_manager.py`·`api/contracts/errors.py`·`api/server.py`·`api/auth_routes.py`·`api/contracts/errors` fixture 2개·`dashboard/src/api/clientSchema.ts`, 계약 시험 `test_nx05_sse_live_revocation.py`·`test_nx02_journal_retention.py`·`test_nx03_tombstone_gc.py`, [BATCH_FREEZE.md](qa/2026-09-16-followup/nx10/BATCH_FREEZE.md) | ① **동결 배치 완료**(지문 `157311cf…` — SSE 폐기·retention·tombstone GC)와 그 지문 검증 ② SC-1~6 8시간 soak을 **동결 트리에서 1회**(이전 실행은 중단) ③ ~~나머지 required 게이트 전수 재실행 + `ga_gate_verify`~~ → **완료**(2026-09-16, `gate-report-freeze002.json`: 21 passed · 1 failed · 0 not_run — 지문 전후 동일, `gate_verify-freeze002.txt` 실패 이유 2개) ④ 타 레인 실패 4건 정리(EX-05 승격 오너 판정 · CR-14 후보 재선언) ⑤ ~~커밋(사용자 승인) 뒤 `clean-machine-runtime` 재실행~~ → **완료**(2026-09-16 오너 지시로 3분할 커밋 `d929da01`·`6417690e`·`89dd383b`; 커밋된 후보 `89dd383b` 에서 attempt `promote003` **23개 중 22 passed · 1 failed · 0 not_run**, `clean-machine-runtime` **passed(43.7s)** → `missing_required` 비었고 남은 문제는 `required_red: python-tests` 하나) ⑥ 독립 검토자·owner 허용 기록 ⑦ 8h 규모 `stream_line_count` 경로 — **사람 결정 8건을 한 장으로 정리**: [GA_OWNER_DECISION_PACKET.md](ga/GA_OWNER_DECISION_PACKET.md)(D1 EX-05 · D2 CR-14 재선언 · D3 검토자 · D4 커밋 · D5 값/정책 · D6 lexicon 임계 · D7 pause · D8 soak 규칙) ⑨ ~~회수 판정기가 “첫 예약”을 읽는 결함~~ → **수정·재측정·재장전**(2026-09-16: `soak-schedule.txt` 는 예약마다 블록을 덧붙이는데 판정기가 첫 매치를 썼다 → 재장전 뒤에는 기대값이 철 지난 예약이 되어 **정상 8시간 실행이 거짓 FAIL** 이 된다. 마지막 예약을 쓰도록 고치고(계약 시험 1 + 자기시험 3, **9/9**) 커밋 `1bd95e7d` → 지문 `92fcaeb5…`→`322b4d3b…` → 필수 23개 재측정 `promote004` **22 passed·1 failed·0 not_run** → 재장전) ⑧ ~~예약이 실제로 살아 있는지 확인·취소 검증~~ → **통제 도구로 대체**(2026-09-16: `screen -X quit` 로 "취소"한 예약 **3건이 살아 있었다** — 4벌 동시 발화 직전에 발견, 트리 단위 종료+검증으로 정리하고 `soak_control.sh` 자기시험 32/32 뒤 재장전) |
| 2026-09-16 | NX-09 | TODO → **REVIEW** (인증 후 실제 사용자 동선, 실 UI) | [nx09/handoff.md](qa/2026-09-16-followup/nx09/handoff.md), `before.md`/`after.md`, `t1`~`t8`-observation.json, `probe.json`, `commands.txt`, `regression.txt`, `repro_nx09_ws_revocation.py`, `dashboard/e2e/tests/nx09-user-journey.spec.ts`(F03 수정 후 8 passed — 이전 7+1 expected-fail), `f03/`(F03 증거: `probe-trace.json`, `ADRs`), `tests/test_nx09_f03_multimodal_attachments.py`(21 passed), `engine/multimodal.py`, `dashboard/e2e/helpers/fakeProvider.ts`, `stores/chatStore.ts`·`components/Chat/ChatPage.tsx`·`stores/uiStore.ts`·`components/UI/PinModal.tsx`·`pages/SettingsPage.tsx`·`App.tsx`, `api/routes/session_state.py`, `e2e/helpers/hermeticBackend.ts`, `src/stores/__tests__/chatStore.nx09.test.ts`(4 passed) ~~F04(서빙 번들 낡음) 결정~~ → **NX-10 에서 닫힘**(번들 재생성 + 동결 직전 `pnpm build` 절차), 이전 턴 이미지 재전송·압축 상호작용 결정, cue 회수율 시나리오 재지정, 미실시 동선(취소·재시도·disk-full·연타·keyboard-only·작은 화면), 독립 검토자 지정·판정, 후보 지문 재고정(NX-10) |
| 2026-09-16 | NX-08 | TODO → **REVIEW** (영속화 잔여 의혹 재검증) | [nx08/handoff.md](qa/2026-09-16-followup/nx08/handoff.md), `before.md`/`after.md`, `before-run-output.json`/`after-run-output.json`, `commands.txt`, `regression.txt`, `repro_nx08_vault_persistence.py`, `engine/vault.py`·`engine/vault_privacy.py`·`engine/vault_privacy_git.py`, `tests/test_nx08_vault_durability.py` (17 passed) | F2(다른 호스트 stale lock, 외부 의존성) 정책 결정, F1 NFS 실측·G1 tombstone GC 정책(NX-03 후속), 독립 검토자 지정·판정, ~~`vault.py` 후보 지문 재고정 대상 포함~~ → **NX-10 에서 지문 기록**(단 미커밋) |
| 2026-09-16 | NX-07 | TODO → **REVIEW** (문서·지원 범위의 단일 현재 상태) | [nx07/handoff.md](qa/2026-09-16-followup/nx07/handoff.md), `before.md`/`after.md`, `before-scan.txt`, `runtime-access.txt`, `before-run-output.json`/`after-run-output.json`, `commands.txt`, `regression.txt`, `docs/20_CURRENT_STATUS.md`(신규 단일 소유자), `README.md`, `docs/ga/GA_SUPPORT_MATRIX.md`, `docs/ga/CR14_EX_EXECUTION_LEDGER.md`, `docs/10`~`19` 상단 소유자 링크, `tests/test_nx07_doc_consistency.py` (26 passed) | 독립 검토자 지정·판정, NX-10 후 최종 수치 동기화(판정 카드 §5 소유), ~~지원표 나머지 행 재검증~~ → **2차 fact check 실시**(2026-09-16, NX-10 창: `shasum`·pyproject·model_manager·config·Dockerfile/k8s·provider 구성·ADR 문구 대조 — 일치, 동시 사용자 행의 val-02 브랜치·원본 아티팩트 2건 정정, 무단 분류 변경 0), NX-11 재개 시 `Not evaluated` 행 갱신 |
| 2026-09-16 | NX-06 | TODO → **REVIEW (정적) / 런타임 BLOCKED** | [nx06/handoff.md](qa/2026-09-16-followup/nx06/handoff.md), `before.md`/`after.md`, `before-run-output.json`/`after-run-output.json`, `commands.txt`, `regression.txt`, `deploy/k8s/deployment.yaml`, `deploy/k8s/namespace.yaml`, `deploy/README.md`, `engine/operational_metrics.py`, `api/server.py`, `tests/test_nx06_deploy_readiness.py` (14 passed) | 임시 cluster 확보 후 Pod readiness/EndpointSlice 관측(BLOCKED 해제), `degraded→200` 정책 승인, NetworkPolicy×CNI 확인, 독립 검토 |
| 2026-09-16 | NX-05 | TODO → **REVIEW** (PIN 변경 = 전체 세션 폐기) | [nx05/handoff.md](qa/2026-09-16-followup/nx05/handoff.md), `before.md`/`after.md`, `before-run-output.json`/`after-run-output.json`, `commands.txt`, `regression.txt`, `src/antigravity_k/security/auth_state.py`, `tests/test_nx05_auth_epoch_revocation.py` (21 passed), `dashboard/src/pages/SettingsPage.nx05.test.tsx` (4 passed) | 독립 검토자 지정·판정, SSE 실연결 폐기 경로, rollback 실리허설, ~~데스크톱 번들 재생성~~ → **NX-10 에서 완료**(`dashboard_dist` 재빌드) |
| 2026-09-16 | NX-04 | TODO → **REVIEW** (판정식·계측 분리) | [nx04/handoff.md](qa/2026-09-16-followup/nx04/handoff.md), `before.md`/`after.md`, `after-run-output.json.txt`, `staging-sc2.json`, `staging-sc6.json`, `regression.txt`, `tests/test_val02_conversation_multiprocess.py` (14 passed) | 독립 검토자 지정·판정, ~~SC-6 `orphan_worktrees` 환경 정리 또는 검사 범위 축소 결정~~ → **NX-10 에서 처리**(검사 범위 확정 + 프루닝 · 리허설 all_pass), **8h 규모 `stream_line_count` 미실행**(NX-10 soak 이 이 경로를 탄다 — 종료 후 확인 필요) |
| 2026-09-16 | NX-01 | TODO → **REVIEW** | [nx01/handoff.md](qa/2026-09-16-followup/nx01/handoff.md), `before-run-output.json.txt`, `after-run-output.json.txt`, `regression.txt`, `tests/test_nx01_compaction_retention.py` (10 passed) | 독립 검토자 지정·판정, NX-02 에 schema 인계, 실사용 동선은 NX-09 |
| 2026-09-16 | NX-02 | IN_PROGRESS(ADR) → **REVIEW** (구현·시험 green) | [nx02/handoff.md](qa/2026-09-16-followup/nx02/handoff.md), `before.md`/`after.md`, `before-run-output.json.txt`/`after-run-output.json.txt`, `migration-report.txt`, `regression.txt`, `tests/test_nx02_history_journal.py` (14 passed), [ADR-DAT-02](adr/ADR-DAT-02-conversation-history-journal.md) | 독립 검토자 지정·판정 및 ADR 승인자 결정, retention/quota 기본값(ADR §8), 실사용 디렉터리 migration 미실시, NX-02-F01 |
| 2026-09-16 | NX-02-F01 | 신규 TODO | nx02/handoff.md §5 (caller-trace.txt 의 `slash_commands_session.py:311-315` 인용) | 세션 저장소가 prompt view 로 오염되는 경로 수정 여부 결정 |
| 2026-09-16 | NX-03 | TODO → **REVIEW** | [nx03/handoff.md](qa/2026-09-16-followup/nx03/handoff.md), `before-run-output.json.txt`, `after-run-output.json.txt`, `regression.txt`, `tests/test_nx03_session_delete_race.py` (17 passed) | 독립 검토자 지정·판정, tombstone GC 정책, NX-08 로 잔여 의혹 이관 |
| 2026-09-16 | NX-00 | TODO(일부 조사) → **REVIEW** (지표 재확인 DONE / 종료·귀속 INCONCLUSIVE) | [nx00/handoff.md](qa/2026-09-16-followup/nx00/handoff.md), `independent-parse.txt`, `artifact-hashes.txt`, `log-prefix-check.txt` | ~~종료141 원문 명령은 복구 불가로 종결하고 NX-10 새 시험으로 대체~~ → **NX-10 에서 대체 구현**(러너 `run_nx10_soak.sh` 가 시작·종료 HEAD/지문 + exit 를 별도 보존; soak 실행 중), NX-00-F01 결정 |
| 2026-09-16 | NX-00-F01 | 신규 TODO | nx00/handoff.md §4 | harness/래퍼 계약 구현 여부 결정 |

작업 트리 주의: 위 변경은 **커밋되지 않았다**. `tests/test_cr14_fence_movement_detection.py` 는 후보 `b6003205` 이후 코드 스코프 커밋 이동으로 이미 실패 상태이며,
NX-01·NX-02 변경 파일(`engine/conversation_store.py`, `engine/conversation_journal.py`, `api/**`, `scripts/migrate_conversation_storage.py`, `tests/**`, `dashboard/src/api/fixtures/**`)도 그 fence 목록에 들어간다. 커밋·후보 재선언은 CR-14 판정 owner 의 결정이 필요하다.

기존 시험 계약 변경(NX-02, 검토 시 확인): `test_fr05…::test_deleted_file_invalidates_cache`(view 삭제는 replay 복구),
`test_val02…`(유실 계수 기준 = `original_history`), `test_nx01…::test_summarizer_failures_keep_constraints`(초기화가 journal 까지 제거),
ARC-01 fixture 2개(파이썬/대시보드 바이트 동일)에 오류 코드 2종 추가.
기존 시험 계약 변경(NX-06, 검토 시 확인): `compute_readiness()` 응답에 `checks[].kind`·`traffic` 이 **추가**되었고
(기존 소비자 호환), `model_manager` 실패는 `not_ready` 가 아니라 `degraded`(optional)가 되며,
`writable_storage` 는 설정된 프로젝트 루트 부재를 `ready` 가 아니라 `degraded` 로 보고한다.
OBS-01 시험 11건은 그대로 통과한다. `_READINESS_CHECKS` 는 함수 객체가 아니라 이름+kind 를 담고 호출 시점에
모듈 전역에서 함수를 찾는다 — `monkeypatch.setattr(om, "_check_*", …)` 실패 주입 계약 유지 목적.

NX-08 이 추가한 것(검토 시 확인): `engine/vault.py` 에 `write_text_atomically`(tmp → fsync → `os.replace` →
디렉터리 fsync)가 생겼고 `write_note` 와 `vault_privacy` 마스킹이 그것을 쓴다 — 저장 실패의 **결과가 달라졌다**:
예전에는 이전 bytes 가 지워졌고 이제는 보존되며 실패는 `VaultCommitError` 로 올라온다. 실패 주입 시험은
`_fsync_fd`/`_replace_file` 이름을 monkeypatch 한다(성공 경로 단위 테스트로 crash-safe 를 선언하지 않는다).
읽기 쪽은 CRLF 구분자 인식과 “닫는 `---` 로 끝나는 파일”이 예외 없이 동작한다 — 본문이 비게 되는 경우가
있으므로 `metadata` 만 필요한 소비자는 영향 없고, 본문을 그대로 기대하던 소비자는 더 이상 예외를 받지 않는다.
복구(`restore`)는 이제 내용만 되돌리고 파일 권한은 현재 값을 유지한다(`0600` → `0644` 완화 방지).

NX-07 이 추가한 것(검토 시 확인): 신규 문서 `docs/20_CURRENT_STATUS.md` 가 현재 상태의 단일 소유자이고,
README·`docs/10`~`19` 는 그 문서를 링크로만 가리킨다. README 의 포트 안내를 코드 기본값(8000)과 일치시켰고
(레거시 8400 제거), 지원표에 `Not evaluated` 단계와 DMG 산출물 행이 늘었다. 계약 시험
`tests/test_nx07_doc_consistency.py` 가 이 관계를 강제한다 — 포트는 `config.py`·`vite.config.ts` 에서 읽어
비교하므로 **문서에 값을 복사해서 맞추는 방식으로는 통과할 수 없다**. 제품 코드 변경은 0줄이다.

기존 시험 계약 변경(NX-05, 검토 시 확인): `test_auth.py::test_change_pin_success` 의 PIN 원복을 같은 토큰 재사용에서
새로 발급한 토큰으로 바꿨다 — PIN 변경이 세대를 올리므로 이전 토큰은 401 이 정상이다(대체 검증은
`tests/test_nx05_auth_epoch_revocation.py` 가 강하게 고정한다). `ChangePinResponse` 는 필드 추가(기존 소비자 호환),
저장 파일은 한 줄 hash 를 계속 읽는다(기존 파일 migration 불필요).

## A. 현재 확인 및 상태판

- [x] 현재 기준 SHA 확인: `ffb0ebb312b76d86742d3e4065628a9704f8268e`.
- [x] 재soak JSON 전체 파싱 및6개 시나리오 PASS 확인.
- [x] RSS48.7MB/기준64MB, 실제28,801.318초, append=revision 확인.
- [x] 원본 hash와 compact summary 보존.
- [x] `exit:141`을 미확정 사항으로 분리.
- [x] 과거23/23과 현재 후보 검증 구분.
- [x] 구현과 연구를 분리한 상세 카드·인계 계약 작성.
- [x] wrapper 종료141 을 stdout 절단(SIGPIPE)으로 설명하고, 실행 명령 원문 미확보를 근거로 INCONCLUSIVE 처리 (2026-09-16, nx00/handoff.md §2).
- [ ] 재soak 당시 코드 후보/시작·종료 지문 귀속 확정 — 증거 없음이 확인되어 NX-10 새 후보 시험으로 대체 예정.
- [ ] 현재 후보 전체 gate·의미 보존·삭제·인증 폐기 검증 완료.

| ID | 상태 | 담당자 | 선행 | 차단/완료 증거 |
|---|---|---|---|---|
| NX-00 | REVIEW (지표 DONE / 종료·귀속 INCONCLUSIVE) | 미배정(작업: Buffy, 검토자 미지정) | 없음 | [nx00/handoff.md](qa/2026-09-16-followup/nx00/handoff.md) |
| NX-00-F01 | TODO (신규, 계획서 §4 후속) | 미배정 | NX-00 | harness started_at/finished_at + exit code 보존 |
| NX-01 | REVIEW (구현·시험 green) | 미배정(작업: Buffy, 검토자 미지정) | NX-00 기준 확보 | [nx01/handoff.md](qa/2026-09-16-followup/nx01/handoff.md) |
| NX-02 | REVIEW (구현·시험 green) | 미배정(작업: Buffy, 검토자·ADR 승인자 미지정) | NX-01 계약(REVIEW 상태 — `memory` schema 인계 가능) | [nx02/handoff.md](qa/2026-09-16-followup/nx02/handoff.md) |
| NX-02-F01 | TODO (신규, 계획서 §4 후속) | 미배정 | NX-02 | 세션 저장소 prompt view 오염 경로 |
| NX-03 | REVIEW (구현·시험 green) | 미배정(작업: Buffy, 검토자 미지정) | NX-00 기준 확보 | [nx03/handoff.md](qa/2026-09-16-followup/nx03/handoff.md) |
| NX-04 | REVIEW (구현·시험 green) | 미배정(작업: Buffy, 검토자 미지정) | NX-01/02 계약 확정 | [nx04/handoff.md](qa/2026-09-16-followup/nx04/handoff.md) |
| NX-05 | REVIEW (구현·시험 green) | 미배정(작업: Buffy, 검토자 미지정) | NX-00 기준 확보 | [nx05/handoff.md](qa/2026-09-16-followup/nx05/handoff.md) |
| NX-06 | REVIEW (정적) / 런타임 BLOCKED (cluster 없음) | 미배정(작업: Buffy, 검토자 미지정) | NX-00 기준 확보 | [nx06/handoff.md](qa/2026-09-16-followup/nx06/handoff.md) |
| NX-07 | REVIEW (문서·지원 범위 green) | 미배정(작업: Buffy, 검토자 미지정) | NX-00 기준 확보 | [nx07/handoff.md](qa/2026-09-16-followup/nx07/handoff.md) |
| NX-08 | REVIEW (구현·시험 green) | 미배정(작업: Buffy, 검토자 미지정) | NX-00 기준 확보 | [nx08/handoff.md](qa/2026-09-16-followup/nx08/handoff.md) |
| NX-09 | REVIEW (실 UI 동선·시험 green, F03·F04 모두 닫힘 — F04 는 NX-10 에서 해소) | 미배정(작업: Buffy, 검토자 미지정) | NX-01~06 및08 REVIEW | [nx09/handoff.md](qa/2026-09-16-followup/nx09/handoff.md) |
| NX-10 | **REVIEW/NO-GO** (게이트 23개 전수 실행: 22 passed·1 failed·0 not_run → 동결 배치 후 재측정 → **보조도구 승격 후 새 지문에서 필수 22개 재측정 완료**(`gate-report-promote002.json`: 21 passed·1 failed·0 not_run, 실패는 타 레인 4건, 시작=종료 지문) → 커밋된 후보에서 23개 중 **22 passed·1 failed·0 not_run**(`promote003`, `clean-machine-runtime` passed 포함), 판정기 결함 수정 뒤 다시 23개 중 **22 passed·1 failed·0 not_run**(`promote004`, 커밋 `1bd95e7d`, 시작=종료 지문), 8h soak 은 **22:00 예약 대기**(예약 통제 도구 자기시험 32/32, 단일 예약·지문 일치·후보 귀속(현재 트리 == HEAD)·의존성·여유 공간 확인)) | 미배정(작업: Buffy, 검토자 미지정) | NX-00~09 | [nx10/handoff.md](qa/2026-09-16-followup/nx10/handoff.md) · [BATCH_FREEZE.md](qa/2026-09-16-followup/nx10/BATCH_FREEZE.md) |
| NX-11 | BLOCKED | 미배정 | 기존 desktop pause 해제,NX-09 | 사용자 재개 전 실행하지 않음 |
| NX-12 | TODO(선택 연구) | 미배정 | NX-01~05 | baseline·평가 계약 |
| NX-13 | TODO(선택 연구) | 미배정 | NX-12 | sparse 검색 실험 |
| NX-14 | TODO(선택 연구) | 미배정 | NX-12 | FAFB 비교 실험 |
| NX-15 | TODO(선택 연구) | 미배정 | NX-13 또는14,NX-10 | shadow·opt-in·disable |

NX-00의 종료 귀속을 복구할 수 없으면 INCONCLUSIVE 근거와 NX-10의 새 시험 대체 조건을 기록해 조사 카드를 닫을 수 있다. 그것은 기존 run이 정상 종료했다고 판정하는 것이 아니다. NX-07은 후보 전 문구·README를 먼저 고정하고, NX-10 후 docs 안의 최종 수치만 갱신하므로 순환 실행을 요구하지 않는다.

## B. 카드마다 복사하는 공통 체크

### 시작 전

- [ ] 사용자에게 해당 구현/시험 범위가 위임되었는지 확인.
- [ ] AGENTS/적용 skill과 해당 NX 카드 전체 읽음.
- [ ] 선행 카드의 실제 diff·증거·schema 확인.
- [ ] SHA/dirty state·코드 지문·환경·lock hash 기록.
- [ ] graph로 심볼/호출자 탐색 후 현재 원문 확인.
- [ ] 파일 소유권/공용 파일 충돌 확인.
- [ ] 실사용 데이터가 아닌 임시 fixture/runtime 경로 설정.
- [ ] 실패 재현 또는 현재 수정 여부 확인; 미확인 가설은 별도 표시.

### 구현 및 검증

- [ ] 고정 불변식·오류·복구·이전 계약을 유지.
- [ ] red→green 또는 원래 통과하던 계약과 변경 필요성 증거 보존.
- [ ] 정상·경계·실패·경쟁/중단·구버전 조건을 카드 요구대로 실행.
- [ ] assertion/임계값/skip을 통과 목적으로 약화하지 않음.
- [ ] 변경 파일 정적검사·관련 회귀 통과.
- [ ] 실제 library driver/API/browser/CLI 표면에서 직접 관측.
- [ ] stdout/stderr 원본 및 제품 exit 보존; 비밀 마스킹.
- [ ] 시작/종료 SHA·지문 일치 또는 변경 영향에 따른 재검증.
- [ ] rollback을 설명만 하지 않고 임시 데이터로 가능한 범위에서 실행.

### 인계 및 종료

- [ ] 변경 파일·심볼·원인·결과·미검증·운영 주의 기록.
- [ ] raw evidence 접근 가능 경로/hash 기록.
- [ ] 상태 REVIEW, 독립 검토자 지정.
- [ ] 검토 finding 해결 또는 명시적 BLOCKED.
- [ ] 검토자·검토SHA·판정·근거 기록 후 DONE.
- [ ] 해당 카드 DONE을 제품 출시 GO와 혼동하지 않음.

## C. 카드별 필수 수용 체크

### NX-00 — 기준선 (2026-09-16 작업분: nx00/handoff.md)

- [x] 원본 FAIL/재PASS 파일을 모두 보존 — 4종 + pid 해시 기록, 수정 없음.
- [x] stdout 잘림/파이프/프로세스 종료 관계를 명령 근거로 조사 — 로그 본문이 artifact JSON 의 정확한 접두부, 0.11% 소비 후 절단.
- [x] 시작·종료·generated timestamp 의미 구분 — `generated_at` 은 시작 시각, 종료 필드는 현재 artifact 에 없음.
- [x] run SHA/지문 입증 또는 미확인 명시 — `run_sha_binding: UNVERIFIED`.
- [x] 미확인일 때 NX-10 새 후보 시험에 재귀속 계획.
- [x] 기존 결과를 소급 정상 exit 로 수정하지 않음 — `finished exit:141` 유지.
- [ ] NX-00-F01(harness/래퍼 계약) 구현 여부 결정 — 미결정.

### NX-01 — 의미 보존 (2026-09-16 작업분: nx01/handoff.md)

- [x] 64/65/122/123 append 경계 재현 — before/after driver.
- [x] 이전 summary 만 신뢰할 수 있게 metadata/version 구분 — `provenance="summary"` + `memory.schema=agk.summary.v1` + 조건부 marker.
- [x] 활성 조건/금지/승인/결정의 구조·출처 보존 — `Constraint(id,kind,status,source_message_id,source_revision)`.
- [x] 최신 explicit 변경에 따른 supersede 검증 — 기존 항목 삭제 없이 status 전환.
- [x] tool/인용 text 가 system 권한으로 승격되지 않음 — user role 만 제약 생성/대체 가능.
- [x] 최소10회 압축 및 재시작 후 초기 활성 제약 유지 — `test_many_generations…`, 재로드 시험.
- [x] 최근6개·순서·revision 증가1·summary budget 유지.
- [x] summarizer timeout/빈 결과/실패에서도 안전한 fallback.
- [x] cap0/64/최소 허용값(7)·장문·Unicode 검증.
- [x] 소실된 과거 원문을 복구했다고 주장하지 않음 — NX-02 범위로 명시.
- [ ] 독립 검토자 지정·판정(ACCEPT/REVISE) — 미실시.
- [~] cue lexicon 회수율 — **어휘 성능은 실측, 실사용 회수율은 미실시(소유자 필요)**. 2026-09-16 합성 코퍼스로 측정([nx01/cue-lexicon-measurement.md](qa/2026-09-16-followup/nx01/cue-lexicon-measurement.md) · `cue_lexicon_probe.py` · `cue-lexicon-output.txt`): 사전 표현 **9/10**(1건 종류 오분류) · 사전 밖 바꿔쓰기 **0/12** · 사전 단어가 든 잡담 **1/7**(이 집합은 일부러 만든 스트레스 집합) · supersede cue **5/7**.
  실제 경로(`update_from_messages`)에서 **피해 3건 확인**: ① 승인 규칙 `"변경 전에는 먼저 확인해줘"` 가 아예 구조화되지 않음(absent) ② 영문 `instead` + 토큰 겹침으로 **상시 규칙이 편집 지시에 무효화됨**(`Always keep the deploy rule` → superseded) ③ `"mustard 색으로 바꿔줘"` 가 상시 requirement 로 **승격**(프롬프트 오염).
  어휘 수정 후보 5건과 실사용 코퍼스 측정 설계(라벨러 2인·프라이버시·임계값)를 문서에 남겼으나 **동결 때문에 미적용** — 해제 뒤 진행. **소유자 재지정 필요**(NX-01 후속 또는 NX-07 중 하나).

### NX-02 — 원본 이력 (2026-09-16 작업분: nx02/handoff.md)

- [x] read/export/delete 호출자 목록 작성 — `nx02/caller-trace.txt` (삭제·export 표면은 현재 미구현임을 확인).
- [ ] ADR 승인된 설계 기록 — ADR-DAT-02 **Proposed(REVIEW)** 상태. 별도 승인자가 필요하다(구현은 ADR 대로 진행).
- [x] journal/view 또는 선택한 구조의 단일 commit 지점 정의 — ADR §2 + `_commit_event`(journal line + fsync).
- [x] ID/revision/schema/출처 계약과 replay 정의 — `agk.conv-journal.v1`, seq↔revision, `replay()`, `is_original()`.
- [x] 원본 전체 조회와 prompt view 상한 각각 검증 — `before.md`/`after.md` (view 5건 / 원본 40건).
- [x] 1,000+ message ID exact round-trip — 1001턴 시험, ID·순서 일치.
- [x] 구버전 migration dry-run/backup/hash/idempotence — `migration-report.txt` + CR-01 시험 19 passed.
- [x] 원문 없는 구버전은 history incomplete 명시 — `base_event_from_view` + `history_incomplete` 시험.
- [x] 각 저장 중단 지점 crash·disk-full·권한 실패 시험 — `_persist` 예외 후 replay 복구, `_append_bytes` ENOSPC 시 503·이전 상태 보존.
- [x] 잘린 tail/중간 손상 분리; 묵시적 유실 금지 — tail 은 `*.tail-recovery-*.bin` 격리, 중간 손상은 409(line/offset).
- [x] 디스크 quota/retention/삭제·백업 범위 명시 — 삭제·백업 범위는 정의(delete 이벤트+표식, 저장소 밖 사본 미보증). **quota/retention 기본값 결정·구현 완료**(2026-09-16, NX-10 동결 배치): 대화당 soft 64 MiB 경고 / hard 512 MiB **쓰기 거절**(507 `conversation_history_quota_exceeded`), **자동 prune 없음**(ADR 의 silent-pruning 금지), `store_usage()` 관측, `AGK_CONVERSATION_JOURNAL_{SOFT,HARD}_CAP_MB`(`0`=비활성). 근거 [nx02/retention-decision.md](qa/2026-09-16-followup/nx02/retention-decision.md), 계약 `tests/test_nx02_journal_retention.py`(9 passed), ADR-DAT-02 Context 8 에 결정 기록.
- [ ] restore를 임시 경로에서 실행하고 최신 변경 손실 방지 — export 경로·journal sha256 까지 구현, 실제 restore 리허설은 미실시.
- [x] 동시 writer(CAS)와 journal 순서 보존 — 2프로세스 append/append·append/delete 시험.
- [x] 삭제 후 조회/export 불가 및 id 재사용 금지 — store·API 시험.
- [ ] 독립 검토자 지정·판정(ACCEPT/REVISE) — 미실시. 기존 시험 계약 4건을 바꾼 근거(handoff §4)를 함께 검토해야 한다.
- [x] 손상된 대화를 격리·폐기하는 운영 절차 — **문서화 + 프로브 실행**(2026-09-16, NX-10 창): 제품 경로는 읽기와 삭제가 같은 fail-closed 라 **삭제도 거절**됨을 실측(view 손상 → `ConversationIntegrityError`, journal 손상 → `ConversationHistoryCorruptError`), 운영 절차(서비스 정지 → 파일 2개를 **저장소 루트 밖**으로 격리 이동 → `write_deletion_marker` → 기동)를 실행해 `deleted=True`·`get()=None`·id 재사용 금지·원본 바이트 보존을 확인. **⚠ 격리 위치를 저장소 루트 안에 두면 `legacy_requires_migration` 이 되어 무관한 대화까지 전부 읽기 실패**(실측). **실데이터 사본 리허설 완료**(같은 날): 사용자 저장소 복사본에서 CR-01 migration(`dry-run`→`apply`→`verify-only`)과 격리 절차를 연속 실행해 손상 거절 → 격리 → `deleted=True` → id 재사용 금지 → **형제 대화 정상** → **원본 해시 불변**을 확인했고, 음성 대조군으로 "루트 안 격리가 치명적인 조건"(표식 없는 저장소)을 확정했다. 근거 [nx02/damaged-conversation-disposal.md](qa/2026-09-16-followup/nx02/damaged-conversation-disposal.md) · `repro_corrupt_disposal.py` · `corrupt-disposal-output.txt` · `rehearse_real_store_quarantine.py` · `rehearsal-real-store-output.txt`, 운영 가이드 [09 §NX 운영 runbook](09_OPERATION_GUIDE.md). 남은 것은 사람: **소유자 지정 · 제품 flag(A안) 채택 여부 · 격리본 보존 기간**.

### NX-03 — 삭제 정합성 (2026-09-16 작업분: nx03/handoff.md)

- [x] A생성/Bload/Adelete/Bsave에서 부활 없음 — `SessionDeletedError`, 파일·재시작 모두 미등장.
- [x] save/delete가 동일 lock 및 generation 검사 사용 — `_delete_session_file`/`_save_session` 모두 per-session flock.
- [x] 신규 생성/기존 저장/삭제/손상 상태 표 작성 — handoff §2(세대·표식 계약) 및 잔재 규칙.
- [x] barrier race 양 순서 및 process restart 검증 — spawn + Barrier, `os._exit(17)` 후 재시작.
- [x] tombstone durability·GC 안전성 확인 — durability 프로토콜은 시험. **GC 정책 결정·구현 완료**(2026-09-16, NX-10 동결 배치): 자동 만료 없음(의도), 운영자 명시 호출 `collect_tombstones(older_than_seconds=…, dry_run=False)` 가 **아카이브로 이동**(삭제 아님) + `gc-report.json` 감사, 관측은 `tombstone_usage()`, `0`/음수 기준은 `ValueError`. 근거 [nx03/tombstone-gc.md](qa/2026-09-16-followup/nx03/tombstone-gc.md), 계약 `tests/test_nx03_tombstone_gc.py`(6 passed).
- [x] stale retry가 ID를 재생성하지 않음 — 3회 반복 저장도 파일 미생성.
- [x] delete 실패를 성공 응답하지 않음 — 표식 기록/제거 실패 모두 전파, 파일 보존.
- [x] scope별 memory와 session 경계 유지 — working/session/project/global 시험.
- [x] API/UI에 stale/deleted 의미 전달 — 409 `session_deleted` + `public_detail`(내부 정보 미노출).
- [ ] tombstone 미지원 구버전 rollback 위험 통제 — 절차 문서화만 완료(자동 회귀 금지), 실리허실 미실시.
- [x] retention 삭제 경로도 같은 표식 규칙 적용(카드 범위 밖 추가 경로, 회귀 시험 포함).

### NX-04 — 테스트 계약 (2026-09-16 작업분: nx04/handoff.md)

- 2026-09-16 관찰(증거: nx01/regression.txt): `test_val02_conversation_multiprocess.py::test_multiprocess_append_is_atomic[6-20]` 가
  단독 실행에서는 5/5 통과하지만, 같은 프로세스에서 다른 대화 테스트 뒤에 실행하면 현재 트리와 HEAD 모듈 모두에서
  `assert final_count >= appended`(27 >= 85) 로 실패한다. cap64 압축이 켜지고 성공 append 가 64 를 넘을 때
  유효한 압축을 유실로 오인하는 비결정적 검사라는 카드 진단이 그대로 확인된 것이다.
  → cap0 exact-set CAS 시험과 cap64 결정적 ≥123 시험으로 분리한다.
- 2026-09-16 NX-02 부분 선행(증거: nx02/regression.txt): 같은 시험의 계수 기준을 압축된 view 가 아니라
  `original_history`(journal 원본)로 바꾸고 view ≤ 64 를 별도 단언하도록 고쳤다(단독·반복 5회 통과, 전체 스위트 포함 통과).
- 2026-09-16 NX-04 완료(증거: nx04/**): 카드 절차 5항목 전부 구현. 옛 판정식의 FALSE POSITIVE 를
  결정적으로 재현(같은 저장 결과: 유실 0인데 옛 판정식이 58건 유실로 주장)하고, CAS/압축 판정을 분리했다.
  시험은 3건 → 14건, 전체 스위트 6459 passed. 남은 것은 SC-6 gate 통과(공유 체크아웃 환경),
  8h 규모 `stream_line_count` 경로 실측, 독립 검토 판정이다.

- [x] cap0 CAS에서 성공 ID exact set와 revision 검증 — `test_cap0_cas_success_set_is_exactly_the_stored_set`(성공 32 = 저장 집합, 거절 ID ∩ 저장 = ∅, revision 32, 압축 0회).
- [x] cap64에서 성공 append≥123을 결정적으로 보장 — `test_cap64_sequential_123_appends_compact_twice_without_loss`(압축 세대 ≥ 2, 원본 123/123) + 드라이버 120 append 의 압축 1세대.
- [x] 원본 수/압축 view 수를 별도로 검증 — `original_history`(원본) vs `get().messages`(view) 기준 분리, view 상한·압축 세대·원본 순서를 각각 단언.
- [x] multiprocess 종료·timeout·retry 상한 정의 — spawn+Barrier, `join(timeout=120)`·종료코드 검사, worker 당 `max_attempts` bounded retry, SC-2 에 `workers_alive_after_join`/`join_timeout_s` 보고.
- [x] 10회 seed 고정 반복 증거 — `test_seed_fixed_repetition_keeps_invariants[0..9]`, 드라이버 `seeded_repetitions`(10/10 PASS, 매회 압축 2세대).
- [x] SC-6 의미 보존 검사와 계측 overhead 기록 — `conversation_constraint_preserved`, `conversation_originals*`, `measurement_overhead_s`/`_ratio`, `completed_ops`.
- [x] SC-6 gate **판정 기준 확정(NX-10)** — 오너 결정(검사 좁히기 + 환경 정리)에 따라 `orphan_wt` 를 제품 worktree 루트(`<repo>/.ag_worktrees`)로 좁히고(`_count_product_orphan_worktrees()`, 검사 삭제 아님) stale worktree 를 prune 했다. 60초 리허설 **`all_pass: true`**(SC-6 pass · `orphan_worktrees: 0`). 배경(역사 기록): 원래 증상은 `orphan_worktrees: 1` 이 공유 체크아웃의 타 작업 prunable worktree 때문에 걸린다(카드 범위 밖 정리 필요, 검사 삭제 금지). **NX-10 이 60초 리허설로 재현하고 비용을 수치화했다**: 검사가 시나리오 샌드박스가 아니라 **저장소 전역**을 세우므로(`git worktree list` @ REPO_ROOT), 그대로 8시간 soak 을 시작하면 **8시간 뒤 같은 이유로 SC-6 이 fail 한다**. 시작 전 결정(환경 정리 a / `orphan_wt` 를 `<repo>/.ag_worktrees` 로 좁히기 b)은 [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §10 · 러너는 `run_nx10_soak.sh`(시작·종료 HEAD/지문 + exit 보존).
- [ ] 8h 규모 `stream_line_count` 경로 실측 — 20초 리허설은 full_replay 경로만 확인.
- [ ] 독립 검토자 지정·판정(ACCEPT/REVISE) — 미실시.
- [x] 금지 사항 준수 확인 — assertion 삭제·하한 0 완화·cap 무한 고정·무관 fail 수치 합산 없음(nx04/handoff.md §3).
- [ ] 최종 메시지 수 assertion 삭제로 PASS를 만들지 않음.

### NX-05 — 인증 (2026-09-16 작업분: nx05/handoff.md)

- 2026-09-16 NX-05 완료(증거: nx05/**): 기준 트리(HEAD 추출)에서 이전 bearer 가 PIN 변경 뒤에도
  200 으로 통과하고(`old_bearer_accepted_after_change: true`), 다른 프로세스가 바꾼 PIN 뒤에도 구 PIN
  로그인이 200 이 되며(`old_pin_accepted_after_external_change: true` — 시작 시점 hash 캐시),
  변경 전 발급한 단기 WS ticket 이 재사용되고, 열린 WS 를 닫는 API 가 없음을 실측했다(드라이버 exit 3).
  수정 트리는 같은 입력에서 exit 0 이며, 토큰·PIN·ticket 이 모두 거부되고 `agk.auth.v1`(hash+epoch) 문서와
  4401 WS 폐기가 관측된다. 시험 21건, 전체 스위트 6485 passed / 0 failed.

- [x] PIN 변경 시 모든 세션 폐기 정책 문서화 — `ChangePinResponse.reauth_required/epoch/sessions_revoked` + ADR 은 불필요(PIN 폐기는 카드가 정한 기본 계약), `nx05/after.md` §1.
- [x] local4자리/remotebootstrap 규칙을 구분하고 기존 사용자 선호 존중 — 변경 경로는 4–128자를 그대로 허용(초기 bootstrap 의 ≥8자 규칙은 유지), 모드별 시험 `test_mode_specific_rules_for_pin_change`.
- [x] hash+epoch 원자 갱신 및 실패 원상태 유지 — `write_auth_state_atomic`(한 문서 os.replace) + `bump_epoch_atomic`(flock 직렬화), 실패 시 이전 bytes 유지 시험.
- [x] legacy no-epoch JWT 처리·migration 정의 — 한 줄 hash 는 epoch 0 으로 읽고, claim 없는 토큰은 거부(재로그인) 시험.
- [x] 기존 bearer 거부/신규 로그인·토큰 성공 — 통합 시험 + 드라이버 before/after.
- [x] 2 process/cache/restart 검증 — spawn 자식이 파일을 바꾸면 부모가 즉시 거부, restart 후에도 거부.
- [x] 활성WS 폐기 지연 실측, 재연결/티켓/refresh/SSE 검증 — 실제 TestClient WS 가 4401 로 닫힘(≤5초 상한 시험 포함), ticket 재사용 거부, 폐기된 bearer 재연결 401. **SSE 는 미연결 상태의 재연결 401 까지만 확인**(handoff 미검증 (2)).
- [x] 현재 UI 토큰 제거 및 재로그인 동선 확인 — `SettingsPage` 가 세션 폐기 응답에서 토큰 삭제 + PIN 모달, `agk:pin-required` 경로도 토큰 삭제(vitest 4건).
- [x] 실제 PIN·JWT·provider secret 증거에서 제거 — 산출물에 credential 없음(응답 키/상태코드만 기록), provider key 는 범위 밖.
- [ ] rollback으로 폐기 토큰이 살아나지 않음 — 이전 버전으로 되돌리면 폐기 토큰이 다시 살아나므로 **금지 절차**로 문서화만 했다(자동 회귀 금지, 실리허설 미실시).
- [x] SSE 실연결 폐기 — **구현·실서버 관측 완료**(2026-09-16, NX-10 동결 배치). `SSERevocationMiddleware` 가 `text/event-stream` 본문을 감싸 주기(기본 1초)로 세대를 재검증하고, 폐기 시 `event: session.revoked` 를 보낸 뒤 스트림을 끝낸다. before/after(같은 트리에서 가드만 제거): 세대 변경 뒤 흘러간 프레임 **9→1**, 폐기 프레임 **없음→1.112초**, EOF **아니오→예**. 근거 [nx05/sse-live-revocation.md](qa/2026-09-16-followup/nx05/sse-live-revocation.md) + `before-sse.json`/`after-sse.json`/`repro_sse_live_revocation.py`, 계약 `tests/test_nx05_sse_live_revocation.py`(10 passed). 남은 것: 브라우저 UI 동선, 클라우드 provider 버퍼링 하 관측.
- [ ] 독립 검토자 지정·판정(ACCEPT/REVISE) — 미실시.

### NX-06 — 배포 (2026-09-16 작업분: nx06/handoff.md)

- 2026-09-16 NX-06 완료(증거: nx06/**): 기준 manifest 의 readinessProbe 가 `/health`(프로세스 생존)를
  보고 있었고, readiness 보고서에 의존성 분류·트래픽 판정이 없었으며, `_check_writable_storage()` 가
  설정된 프로젝트 루트가 없으면 조용히 `data/` 를 검사해 **ready 로 오보**했다(드라이버 exit 3).
  수정 트리는 exit 0 이며 required→503/optional→200 계약이 응답 본문(`kind`/`traffic`)으로 표현된다.
  클러스터가 없어(kube context 0개, client dry-run 도 discovery 필요) **런타임 관측은 BLOCKED** 다.

- [x] readiness `/api/ready`, liveness 별도 역할 — readiness=`/api/ready`, liveness·startup=`/health`, manifest 주석+시험.
- [x] degraded200/not_ready503 허용 정책 — `compute_readiness()` 가 `checks[].kind`(required/optional)와 `traffic` 를 반환, README 에 상태·트래픽 표와 근거.
- [x] namespace→secret→application 순서 — `namespace.yaml` 헤더와 README 를 `namespace → secret → 나머지` 3단계로 수정(기존 README 는 1단계 Secret 이 namespace 부재로 실패), 시험으로 문구 고정.
- [ ] 임시 cluster 정상/장애/회복 Endpoint 관측 — **BLOCKED**(kube context 없음). 해제 조건과 절차는 nx06/handoff.md §Unverified.
- [x] 긴 시작 시간과 선택 의존 실패에서 restart loop 없음 — startup 유예 최대 5분, `test_liveness_stays_200_while_readiness_fails`(required 전부 실패해도 `/health` 200).
- [x] production context 미사용 및 생성한 자원만 정리 — 어떤 cluster 에도 접속하지 않았고 자원을 만들지 않았다. README 에 `kubectl delete -f deploy/k8s/` 와 namespace 별도 판단 문구.
- [x] runtime 미실행이면 BLOCKED 로 명시 — handoff/regression/체크리스트 3곳에 BLOCKED 표기, DONE 으로 쓰지 않음.
- [x] 잘못된 인증 secret 은 안전하게 실패 — `test_bad_auth_secret_fails_closed_at_startup`(production+0.0.0.0+약한 PIN+hash 없음 → `StartupSecurityError`) + README 에 `CreateContainerConfigError` 구분.
- [x] secret 미노출 — `test_readiness_never_exposes_secret_material`(probe 응답에 pin/token/secret/password 부재).
- [ ] `degraded → 200` 정책 승인 — 신규 설치가 막히지 않게 하려는 결정(handoff §1, after.md).
      "degraded 도 endpoint 제외"로 바꾸려면 ADR 후 `traffic` 판정만 수정.
- [ ] NetworkPolicy × CNI 의 kubelet probe 허용 확인 — 실 cluster 필요(README 에 절차).
- [ ] 독립 검토자 지정·판정(ACCEPT/REVISE) — 미실시.

### NX-07 — 문서

- [x] 현재 상태 단일 원본·중복 최신 배너 정리. (`docs/20_CURRENT_STATUS.md` 신설, README·`docs/10`~`19` 11곳이 실재 링크로 가리킴, `docs/10`·`docs/16` 의 "최신" 배너는 이력으로 하향)
- [x] 과거23/23에 후보/지문/범위 표시. (문맥 없는 4줄 보강 — `docs/08:119`, `docs/13:68`(다른 뜻이라 `23건`으로 명확화), `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md:71`, `docs/ga/CR14_GATE_COVERAGE_BOUNDARY.md:450`; `docs/20` §2 가 두 뜻을 정의)
- [x] soak JSON PASS와 종료귀속 미확인 병기. (`docs/20` §3 네 단계, EX 대장 EX-05 행 `JSON PASS / 종료·귀속 INCONCLUSIVE — DONE 아님`)
- [x] 기술 TODO와 ‘사람만 남음’ 모순 제거. (README 를 "**이 후보 범위에서는**" 으로 한정 + NX 상태·미커밋 사실 명시, 독립 검토자 "미배정" → "겸직" 정정)
- [x] release owner 배정과 독립 검토 분리. (`docs/20` §5 — 출시 책임자 강병석 기록은 있고 **독립 검토자는 미배정(겸직)** 으로 분리 표기)
- [~] port8000/8400/dev5174/packaging 환경별 확인. (코드 기본 8000 · dev **5173**(카드의 5174 표기는 코드와 다름 — `dashboard/vite.config.ts` 가 5173) · 패키징 `SSAK_HOST_URL` 을 `docs/20` §1 에 구분. 8400 은 레거시로 제거. README 따라가기 런타임 관측은 `nx07/runtime-access.txt`)
- [x] 지원표의 구현 존재·검증·정식 지원 구분. (4단계 어휘 + 데스크톱 행을 범위`Unsupported`/산출물`Not evaluated` 로 분리, DMG 존재와 서명·실기기·업데이트 미검증을 같은 행에 병기)
- [x] README 변경은 후보 고정 전에 완료. (NX-10 전에 완료·문서 전용이며 값은 넣지 않았다)
- [ ] NX-10 후 docs 수치와 최종 판정 동기화.

### NX-08 — 추가 영속화 검증

- 2026-09-16 NX-08 완료(증거: nx08/**): 기준 나무(`git archive HEAD src`)에서 드라이버가
  **exit 0 · CONFIRMED 6** 을 관측했다 — fsync 실패가 이전 bytes 를 지우고(A1, sha 변경),
  write 도중 SIGKILL 이 잘린 파일을 커밋 후보로 남기고(A2), CRLF frontmatter 가 본문으로
  새고(C1), 닫는 `---` 로 끝나는 파일이 `ValueError` 로 죽고(C2), 복구가 `0600` 을 `0644`
  로 넓혔다(D1). 수정 후 같은 드라이버가 **CONFIRMED 1 · NOT_REPRODUCED 12** — 남은 1건은
  외부 의존성(filelock, F2)이다.
- [x] fsync 실패 후 bytes/Git 상태 관측. (A1 sha 동일 + `VaultCommitError`, git HEAD 불변)
- [x] kill9 뒤 lock recovery 실증. (B1 `NOT_REPRODUCED` — 같은 호스트 죽은 pid 는 filelock 이 스스로 깬다; 다른 호스트 lock 은 F2 로 별도 판정)
- [x] frontmatter EOF/CRLF fixture 검증. (C1-crlf·C2-eof-no-newline **CONFIRMED → 수정**, LF·개행 있음·malformed 는 NOT_REPRODUCED)
- [x] backup/restore/schema/권한 보존. (D1 — 내용·Schema 는 보존, **권한은 완화됐고** 수정 후 `0o600 → 0o600`)
- [x] 각 의혹 CONFIRMED/NOT_REPRODUCED/INCONCLUSIVE. (15 probe 판정표는 `nx08/handoff.md` §2)
- [x] 확인 결함은 별도 ID·수정·회귀 후 종료. (A1/A2 = F01, C1/C2/D1 = F02/F03/D1 로 표기, `tests/test_nx08_vault_durability.py` 17 passed, 좁은 회귀 103 passed)
- [x] 사용자 vault 미사용. (임시 디렉터리 임시 Git repo 만; 작업 트리도 SIGKILL 시험에서만 임시 경로를 썼다)
- [~] F2 — **CONFIRMED, 미해결**. filelock 3.29 는 `hostname != socket.gethostname()` 이면
  stale lock 을 깨지 않는다(의존성 동작, 코드로 없애려면 lock 계층 교체). 단일 호스트
  배포에서는 발생하지 않고 복구 절차는 `.git/.agk_vault.lock` 수동 제거다. 공유 볼륨·다중
  인스턴스 확장 시 정책 결정 필요(NX-10 출시 판단 대상).
- [~] F1(NFS 등 비로컬 FS 의 flock/fsync) — **INCONCLUSIVE**: 이 호스트에 NFS 마운트가
  없어 로컬 관측을 일반화하지 않았다.
- [~] G1(tombstone GC 경로) — **INCONCLUSIVE**: GC 심볼 부재만 확인. 보존 기간·트리거 정책은
  NX-03 후속으로 남긴다.
- 참고: NX-03 이관 의혹 4건의 결말은 `nx08/handoff.md` §3 — ③(redact 무잠금)은 lock 은
  유지되나 **비원자적 쓰기**였고 함께 수정했다. ②(구버전 삭제 이력 부활)는 재현 불가능한
  과거 이력이라 측정 대상이 아니다.

### NX-09 — 사용자 품질 (2026-09-16 작업분: nx09/handoff.md)

- [x] 인증 후 모델 선택→대화→**결과** — 실 UI·실 서버·가짜 provider(T1): 화면에 응답, provider 본문에 사용자 요청(`reachedProvider: true`).
- [x] 첨부 — **이미지가 실제 바이트로 모델에 도달한다**(T4: provider `/api/chat` 본문에 PNG base64, 첨부 칩 표시, **다음 턴에는 미전송**). 예전에는 `[첨부 파일: …]` 텍스트만 가고 모델은 파일명만 봤다(**NX-09-F03** → [f03/after.md](qa/2026-09-16-followup/nx09/f03/after.md) · [ADR-0005](adr/0005-multimodal-attachments.md)). 거부는 400 + 사유 코드로 사용자에게 보인다. 잔여: 이전 턴 이미지 재전송·압축 상호작용은 미정.
- [x] 저장→재시작→이어가기 — 서버 r2·메시지 2건, **빈 localStorage 로 새로 연 창**이 `/v1/conversations/<id>` 로 복원(T2). 그 전에는 동기화가 **한 번도** 실행되지 않았다(**NX-09-F02** 수정).
- [x] 삭제→검색/export 불노출 — DELETE 200 뒤 스냅샷/export/history **404·404·404**, 새 창에도 원문 없음(T3).
- [x] PIN 변경→재로그인·연결 종료 실제 UI 관측 — 모달 표시 + 저장 토큰 제거 + 모달이 이유를 설명(T5, UX 수정) · API 경로에서 열린 이벤트 WS **4401 폐기**(T7, `sessions_revoked: 1`, 브라우저 소켓 1/1 closed).
- [x] UI 경로에서도 폐기 — **창 두 개 시험(T8)**: 창 A(채팅, 이동 없음)의 살아 있는 이벤트 WS 가 `sessions_revoked: 1`·close **571ms**(카드 계약 ≤5초)로 닫혔다. 한 창에서 설정 화면으로 이동하던 원래 관측은 **NOT_REPRODUCED** — 이동이 문서를 교체해 WS 소유자(ChatPage)가 사라지고, 파괴된 창의 소켓 객체는 close 를 보고하지 않아(`isClosed: false`) 살아 있는 것처럼 보였다(**NX-09-F06**).
- [x] 대화 정체성 — 새 대화가 별개 레코드이고 저장소에 폴백 id 레코드가 없다(T6). 그 전에는 첫 대화가 `conv_unspecified` 로 합쳐졌다(**NX-09-F01** 수정).
- [ ] 반복 요약 후 초기 네트워크/폴더 제한 유지 — **미실시**(NX-01 이 넘긴 cue 회수율 항목과 함께 별도 카드 필요).
- [ ] unavailable/cancel/retry/network drop/disk-full/중복 클릭 — **미실시**(이번 witnessed 범위 밖).
- [ ] 긴 출력·keyboard-only·작은 화면 — **미실시**(이번 witnessed 범위 밖).
- [x] local/fake/live provider 결과 분리 — 모든 결과를 **fake provider** 기준으로 표시하고 cloud/live 증거로 승격하지 않음(EX-01 은 별도 축).
- [x] P1 데이터/보안 실패0·일반 미해결 목록 명시 — F01·F02(P1 데이터) 수정, **F03(P2 기능)은 후속 작업에서 수정**(첨부 실전달), F04(P2 패키징)는 아직 열려 있다. F06 은 재측정으로 결함 아님(NOT_REPRODUCED) — 계약은 T8 이 고정한다.
- [x] **NX-09-F04 해소**(NX-10): 커밋된 `dashboard_dist` 가 소스보다 낡아 `dashboard-build` 가 `tree_moved` 로 끝나는 것을 게이트가 직접 잡았다. 소스에서 번들을 재생성한 뒤 같은 게이트가 passed, 이 상태에서 UI 증인 **30/30 passed**. **절차화**: 대시보드 소스를 고치는 카드는 후보 동결 직전에 `pnpm build` 로 번들을 소스와 일치시킨다([nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §5, [nx09/handoff.md](qa/2026-09-16-followup/nx09/handoff.md)).

### NX-10 — 최종 후보

- [x] 지원 범위·manifest·skip 사유 측정 전에 고정 — [nx10/SCOPE.md](qa/2026-09-16-followup/nx10/SCOPE.md)(수정하지 않음) + 동결 후 변경은 [SCOPE_ADDENDUM.md](qa/2026-09-16-followup/nx10/SCOPE_ADDENDUM.md). 지원 범위(Supported 행)는 **0개 그대로**.
- [x] full SHA·시작/종료 지문·환경·lock hash 기록 — HEAD `20d529fc1f17c8ff580eaf0d853dcd1ce92172d5`, worktree fingerprint `da54e07b…`, `uv.lock`·`dashboard/pnpm-lock.yaml`·`dashboard/package-lock.json`(리포트 `dependency_locks`). **dirty=true** 라 공식 후보 SHA 는 없다.
- [x] required 전수 실행, 실패/not_run과 승인된 제외 구분 — **23개 전부 실행: 22 passed · 1 failed · 0 not_run** (`clean-machine-runtime` 은 SCOPE 의 `BLOCKED_EXTERNAL` 분류가 사실오류였음이 드러나 실행했고 통과 — `--ref HEAD` 를 export 하므로 그 green 은 HEAD 의 것이고 커밋 뒤 후보 값이 된다). 이전 값은 23개 중 **21 passed · 1 failed · 1 not_run**(python-tests 전량·benchmark·master-e2e·dashboard-e2e-ambient 를 전용 창에서 실행한 뒤 갱신). **failed 1 = `python-tests`**(`4 failed, 6562 passed, 14 skipped`)이고 **실패 4건은 전부 타 레인 커밋 귀속**이다(커밋된 트리만 비교하는 계약 테스트 — 미커밋 작업 트리는 결과에 안 들어간다). **not_run 1** = clean-machine-runtime(`BLOCKED_EXTERNAL` — 깨끗한 지원 호스트 필요). 실패도 not_run 도 “승인된 제외”가 아니므로 수용 기준 미달.
- [~] 최종 제품 코드에서 SC-1~6 28,800초 이상 완료 — **오늘 22:00 KST 예약 실행**(`schedule_nx10_soak.sh`): 목표 `2026-09-16T13:00:00Z`(=22:00 KST), 종료 예정 `~06:00 KST`. 보조도구 승격으로 지문이 이동해 **예약을 취소하고 재장전**했다(2026-09-16T09:47:11Z) — 지금 예약은 **승격된 트리**를 재므로, 8시간이 최종 후보를 잰다(기대 지문·대기 시간의 소유자는 `nx10/soak-schedule.txt`). **시작 직전 지문이 다르면 8시간을 쓰지 않고 중단**한다. 종료 뒤 `all_pass` 와 **종료 지문 일치**를 확인해야 판정이 된다. 이전 실행은 1차 `07:41:42Z`(오너 판정)·2차 `08:19:17Z`(22:00 예약으로 이동) 중단. 사유: 후보 코드를 더 고칠 예정이라 종료 지문이 최종 후보와 달라져 **“시작/종료 지문 동일” 조건을 만족할 수 없고**, 러너가 종료 시에만 리포트를 쓰므로 중단 시점 기대값이 0이었다. 중단 사실은 `nx10/soak-exit.txt` 에 **러너 기록(`exit: 143`)과 운영자 기록을 구분해** 남겼다. 순서를 바꿨다: **후보 동결 → 8시간 soak 1회 → 게이트 재측정**이고, 러너(`run_nx10_soak.sh`)는 그대로 재사용한다. 유효한 기준선은 `soak-60.json`(60초 리허설, `all_pass: true`)이다.
- [~] RSS64MB·FD·오류·orphan 기준 유지 — 60초 리허설은 SC-6 pass(RSS +21.2MB · fd 0 · errors 0 · orphan 0)고, **8시간 규모 판정은 미완**(22:00 KST 예약 실행 — 보조도구 승격 뒤 **새 지문으로 재장전**됨). 8h 규모에서 처음 타는 `stream_line_count` 경로도 그때 확인한다.
- [x] 대화 저장소 migration 실데이터 확인 — 레거시인 사용자 저장소 **복사본**에서 `dry-run`→`apply`(3개 백필)→`verify-only` 통과, 원본 해시 불변(2026-09-16, `rehearse_real_store_quarantine.py`). 실제 저장소 자체의 migration(서비스 정지 후 적용)은 **미실시** — 운영 결정.
- [ ] 반복 압축 의미 보존·원본 보존·삭제·인증 폐기 별도 증거 — 각 카드(NX-01~05) 증거는 있으나 **NX-10 후보 위에서 재귀속하지 않았다**.
- [x] 래퍼 파이프와 무관한 실제 exit 보존 — `ga_gate.py` 가 게이트별 `exit_code` 를 JSON 에 남긴다(attempt 001~014 원본 보존). 긴 게이트는 `run_remaining_gates.sh` + `screen` 으로 돌리고 게이트별 exit 를 `runner-exit.txt` 에 **따로** 적는다 — 백그라운드 실행이 래퍼만 죽이고 exit 를 잃는 실패 모드를 실제로 겪은 뒤(고아 pytest + 리포트 미기록) 만든 장치다.
- [x] gate_verify 및 현 attempt-close 검증 — **경계 문서화 + 후보에서 재실행**: 전용 창의 단일 리포트(`gate-report-full001.json`, 22개 중 21 passed)에서는 이유가 **정확히 2개**(`missing_required: clean-machine-runtime` · `required_red: python-tests`)였다(`gate_verify-full001.txt`). **2026-09-16 커밋 뒤에는 그 이유가 하나로 줄었다**: 커밋된 후보 `89dd383b` 의 리포트 `gate-report-promote003.json`(23개 중 22 passed · 1 failed · 0 not_run)에서 `ga_gate_verify` 는 `required_red: python-tests` **만** 지적한다(`gate_verify-promote003.txt`) — `clean-machine-runtime` 이 후보 값으로 닫혔다. 쪼갠 증거로는 애초에 마감 형태가 안 된다는 것도 실측했다(`gate_verify-boundary.txt`).
- [x] 다른 후보의 PASS 합산 없음 — attempt 별 지문(`d8f040ef…`→`da54e07b…`)을 분리해 기록했고 `--merge-into` 를 쓰지 않았다.
- [ ] 독립 reviewer와 owner 판정 기록 — **없음**. 판정자는 공백을 숨기지 않고 그대로 기록([handoff §7](qa/2026-09-16-followup/nx10/handoff.md)).
- [x] 지원 환경별 한계·운영 runbook·복구 기록 — [09 운영 가이드 §NX 운영 runbook](09_OPERATION_GUIDE.md) 에 작성(2026-09-16): 지원 한계표(`Supported` 0행 근거), 런타임 경로·기동, **폐기 경로의 실제 범위**(WS 4401 닫힘 571ms, 열린 SSE 는 2026-09-16 구현 후 `session.revoked`+EOF — [상세](qa/2026-09-16-followup/nx05/sse-live-revocation.md)), SC-1~6 임계(P95/P99/error/FD/RSS/orphan — orphan 은 제품 worktree 루트 한정), 복구 절차 표와 **리허설 상태**(DR 3개 완료 / restore·rollback은 **미실시**, 손상 대화 폐기는 **절차 문서화 + 프로브 + 실데이터 사본 리허설 완료**(2026-09-16) — 실제 저장소 자체에 적용은 미실시), 그리고 **결정된** retention·tombstone 한계(자동 prune·자동 만료 없음, 507 거절, 운영자 명시 회수). 이 항목은 문서 산출물이라 별도 증거 디렉터리 없이 운영 가이드 본문이 소유한다.
- [x] blocker 남으면 NO-GO, 출시 승인 전 GO 금지 — 판정 **NO-GO/REVIEW**(not_run 5 + owner 허용 없음 + dirty 후보).
- [!] **교차 레인 충돌(미해결, 오너 결정 브리프 작성) — 실패 4건의 정체**: ① 다른 레인의 커밋 `20d529fc` 가 `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 의 EX-05 행을 **PASS** 로 올기며 “귀속 UNVERIFIED” 문구를 지웠다 — 같은 문서 §재soak 결과와 `docs/20` §3 ④(미확정)에 반하는 자기모순이고, NX-07 문서 정합성 계약 2건(`test_soak_phases_stay_separated`·`test_teeth_soak_done_promotion_is_detected`)이 현재 **실패**한다. 이 2건은 이후 전량 스위트가 실제로 돌면서 `python-tests` 게이트 수치에 **드러났다**(2026-09-16: `4 failed, 6587 passed` — EX-05 2건 + CR-14 울타리 2건). 되돌리지 않았다(타 레인 소유·오너 판정) — 증거 4단계 분리·선택지 A/B/C·적용할 1줄 수리안은 [EX05_PROMOTION_CONFLICT.md](qa/2026-09-16-followup/nx10/EX05_PROMOTION_CONFLICT.md), 대장 맥락은 [GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §6. ② **CR-14 울타리 이동 2건**(`test_cr14_fence_movement_detection`): 선언 후보 `b6003205`(지문 `02349a8d…`) 이후 코드 스코프 **38개 경로**가 움직여 HEAD(`20d529fc`, 지문 `2068e72b…`)와 달라졌다 — 후보 재선언 또는 울타리 규칙 조정이 필요하고, 소유자는 CR-14 레인/오너다.

### NX-11 — 조건부 패키징

- [ ] 기존 pause 해제 지시 확인 전 실행하지 않음.
- [ ] DMG hash/SBOM/서명/notarization/update feed 검증.
- [ ] 깨끗한 지원 기기의 설치→실제 사용→재기동.
- [ ] 업그레이드/중단/손상 서명 거부/rollback.
- [ ] E→DMG 이전 및 데이터 유지.
- [ ] loopback/LAN/Tailscale 인증·접속 각각 검증.
- [ ] 미검증 Windows 등 Supported로 표시하지 않음.

### NX-12 — 연구 기준선

- [ ] 현 heuristic/vector/BM25 baseline 재현.
- [ ] typed context/advice·최종 정책 우선 계약.
- [ ] repo/task family holdout·누수 방지·사용권한.
- [ ] pilot100 및 본시험 규모 결정 근거.
- [ ] primary metric·guardrail·장비·budget 사전 동결.
- [ ] task success/cost/P95/RSS/Recall/MRR/fallback 측정.
- [ ] 사용자 명시 모델/승인/차단 provider 우회0.
- [ ] 항상 fallback일 때 기존 실행 결과 유지.

### NX-13 — sparse 검색

- [ ] 실제 FAFB를 사용하지 않는 아이디어 실험임을 명시.
- [ ] seed/dimension/top-k/index·embedding version 고정.
- [ ] 기존 ranker/authoritative facts/정책 필터 유지.
- [ ] BM25/vector/random projection 동등 조건 비교.
- [ ] 삭제/update/reindex/한국어·코드/중복 검증.
- [ ] artifact 누락·version mismatch fallback.
- [ ] feature OFF에서 선택 의존성 없이 정상 시작.
- [ ] 기준 미달 시 STOPPED, 달성 시 NX-15 후보.

### NX-14 — FAFB 구조

- [ ] URL/version/checksum/license/인용 자산 명세.
- [ ] filter/root ID/direction/neuropil aggregation/unknown 규칙.
- [ ] sparse subset budget과 선정 규칙 사전 확정.
- [ ] encoder→graph→readout의 가정·학습 변수 기록.
- [ ] heuristic/MLP또는bandit/random/rewired 대조군.
- [ ] parameter/학습/LLM·tool 예산 동등성 및 차이 기록.
- [ ] sparse driver/학습/holdout/ablation 재현.
- [ ] 외부 model artifact 안전한 로드·hash 검증.
- [ ] 실제 topology 기여 미입증이면 효과 주장하지 않음.
- [ ] default OFF, wholebrain dense 탑재 없음.

### NX-15 — 선택 통합

- [ ] OFF→SHADOW→OPT-IN 단계별 판정.
- [ ] shadow 실행 선택/도구 호출 변화0 확인.
- [ ] timeout/NaN/손상/누락/예산초과 fallback.
- [ ] 모델/승인/권한 정책이 추천보다 우선.
- [ ] 원문 telemetry 자동 외부 전송 없음.
- [ ] reason/version/fallback/latency/cost 관측.
- [ ] kill switch/disable 실제 수행 및 반영시간 확인.
- [ ] 사전 효과 기준과 모든 guardrail 충족.
- [ ] 실패 시 baseline 복귀, default ON은 별도 결정.

## D. 실행/인계 기록 양식

카드별 아래 양식을 복사해 evidence `handoff.md`에 작성한다. 빈칸은 DONE이 아니다.

```text
Task ID / attempt:
Owner / reviewer:
State: TODO | IN_PROGRESS | REVIEW | DONE | BLOCKED | STOPPED
Baseline full SHA / code fingerprint:
Final full SHA / code fingerprint:
Dirty paths (secret contents excluded):
Scope / files / symbols:
Preconditions / dependency evidence:
Observed failure before / exact reproduction:
Change and invariant:
Commands / cwd / exit codes / environment:
Runtime expected vs observed:
Regression results / raw log paths / hashes:
Data migration / backup / rollback observed:
Unverified / reason / impact:
Reviewer verdict / reviewed SHA / artifact:
Next owner / exact next action:
```

## E. 즉시 중단하고 원인을 기록할 조건

- [ ] 원본 사용자 데이터 손실, 삭제 세션 부활, 권한/승인 우회가 발생하면 해당 경로 작업을 중단하고 임시 fixture에서 원인 조사.
- [ ] 후보 지문이 시험 중 바뀌면 현재 결과를 최종 인증에 합산하지 않음.
- [ ] 실사용 secret·vault가 fixture로 연결되면 실행 전 분리.
- [ ] 다른 에이전트와 같은 파일 충돌이면 타인 변경을 되돌리지 말고 소유권 재조정.
- [ ] 효과 없는 신경 구조를 ‘개선’으로 출시하지 말고 STOPPED 기록.

이 절은 사고가 발생했다는 표시가 아니라 실행자의 안전 점검표다. 전체 항목을 기계적으로 체크해 완료율을 계산하지 않는다. 선택 연구·조건부 패키징·출시 필수 작업의 분모는 서로 다르다.
