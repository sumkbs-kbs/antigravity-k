---
title: Ssak-Ai 최종 검토 개선 실행 체크리스트
status: in-progress (RP-00/01/02/03/04/05/06/07/08/09/10/11/13 DONE; RP-12 IN_PROGRESS soak-006; RP-14 TODO)
date: 2026-09-10
reviewed_sha: 8794aaecabf5664a7ee560b104e0115d915aabb7
plan: docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md
tags: [checklist, remediation, agent-coordination, release-gate]
---

# 최종 검토 개선 실행 체크리스트

> **이 문서는 RP 이력이다.** RP 완료는 GA 승인이 아니다. 현재 상태의 단일 소유자는 [현재 상태 요약](20_CURRENT_STATUS.md)(2026-09-16)이다.

이 문서는 `docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md`의 실행 상태 원장이다. **작성 시 구현을 실행하지 않았으며 전 항목 미완료**다. 보고서의 FR은 발견 ID, RP는 개발 작업 ID다. 반드시 둘을 연결한다.

## 상태·체크 규칙

- `TODO`: 미착수. `IN_PROGRESS`: 작업 중. `IMPLEMENTED`: 코드 작성 완료. `REVIEW`: 검증 자료를 제출한 상태. `DONE`: 독립 검토 PASS까지 완료.
- `REWORK`: 실패로 재작업. `BLOCKED_EXTERNAL`: 실제 자격증명/장비/담당자 승인이 필요. `INCOMPLETE`: 필수 실측 또는 증거 미완료.
- 구현자는 자기 세부 수행 항목을 보고하되, 조정자만 이 원장을 갱신한다. 자신이 구현한 작업을 자신이 승인하지 않는다.
- 박스는 실제 작업·파일·원문 증거가 존재할 때만 체크한다. 테스트 계획/가짜 fixture 결과/요약문만으로 실제 검증 박스를 체크하지 않는다.
- `tested_sha`, 원문 로그, manual QA, 독립 reviewer 중 하나라도 누락이면 DONE 금지. 후보 변경 시 영향받는 검증은 새 SHA에 다시 연결한다.
- 아래 `—`는 아직 미배정·미측정이라는 뜻이다. 복사한 SHA/승인자 이름으로 채우지 않는다.

## 마스터 실행표

| ID | 작업 | 선행(기본 순서) | 상태 | 담당자/branch | tested SHA | 독립 판정 | 증거 attempt |
|---|---|---|---|---|---|---|---|
| RP-00 | 기준·환경·배정 | 없음 | DONE | codex-root-orchestrator / current checkout | `8794aaecabf5664a7ee560b104e0115d915aabb7` + recorded dirty state | rp00_verify CONFIRMED | `RP-00/attempt-003` |
| RP-01 | UnifiedAgent sandbox | RP-00 | DONE | rp01_retry / current checkout | `4b202113f254a766fdd26db30e4f65e417f77c28` | rp01_verify2 APPROVE: focused 44, 실 sandbox 12/12 | `RP-01/attempt-003` |
| RP-02 | shell 실행 경계 | RP-01 | DONE | rp02_retry / current checkout | `4b202113f254a766fdd26db30e4f65e417f77c28` | rp02_verify2 APPROVE: source 89, sentinel/root confinement PASS | `RP-02/attempt-003` |
| RP-03 | transaction 경계/복구 | RP-02 | DONE | rp03_fix_partial_write / current checkout | `3dfd1ff2…+dirty` (candidate `4b202113` 호환) | rp03_verify3 APPROVE: write 전 소유권 기록 + commit CAS. driver residue `false`, rolled=2, git diff 비어 있음, 17 focused pass, 68 consumer pass | `RP-03/attempt-004` |
| RP-04 | RSI 격리 rollback | RP-03 | DONE | rp04_fix_concurrent_delete / current checkout | `3dfd1ff2…+dirty` (candidate `4b202113` 호환) | rp04_verify3 APPROVE: 부재 소유 파일 외부 삭제 보존·충돌 기록. gate driver `concurrent_deletion_preserved=true`, 45 focused pass, 68 consumer pass | `RP-04/attempt-004` |
| RP-05 | 대화 read/CAS | RP-04 | DONE | rp05_api_workers_evidence / current checkout | `3dfd1ff2…+dirty` (candidate `4b202113` 호환) | rp05_verify3 APPROVE: 실제 2개 uvicorn API worker + 재시작 worker 실측 완료. Worker B rev 1 캐시 후 A가 rev 2 append 시 B가 즉시 rev 2 관찰, stale expected=1은 HTTP 409 거부, cold restart Worker C rev 2/이력 보존. 25 passed | `RP-05/attempt-004` |
| RP-06 | Chroma 검증기 | RP-05 | DONE | rp06_rp07_retry / current checkout | `4b202113f254a766fdd26db30e4f65e417f77c28` | rp06_verify2 APPROVE: persistent Chroma/negative/CLI 독립 재현 | `RP-06/attempt-003` |
| RP-07 | config/wheel | RP-06 | DONE | rp06_rp07_retry / current checkout | `4b202113f254a766fdd26db30e4f65e417f77c28` | rp07_verify APPROVE: 4-way 바이트 동일, model registry 31 passed, 격리 wheel 설치·agk exit 0 | `RP-07/attempt-003` |
| RP-08 | 폴더→요청 E2E | RP-07 | DONE | rp08_browser_e2e_executor / current checkout | `3dfd1ff2…+dirty` (candidate `4b202113` 호환) | rp08_verify APPROVE: 결정적 double tier 8 passed + Playwright 브라우저 E2E 2 passed (`ws-04-project-switch.spec.ts`) | `RP-08/attempt-002` |
| RP-09 | 수동/자동 압축 E2E | RP-08 | DONE | rp09_manual_compact_ui / current checkout | `3dfd1ff2…+dirty` (candidate `4b202113` 호환) | rp09_verify APPROVE: store+API tier 43 passed (결함 1건 수정) + Playwright 수동 압축 E2E 4 passed (`conversation-compaction.spec.ts`) | `RP-09/attempt-002` |
| RP-10 | 문서/승인 상태 준비 | RP-09 | DONE | zcode-remediation-agent / current checkout | `8794aae…+dirty` | rp10_verify APPROVE: 증거 인덱스·README·진행기록·mirror 정합화; 승인 자료 인계는 BLOCKED_EXTERNAL | `RP-10/attempt-001` |
| RP-11 | gate/증거 수집기 | RP-10 | DONE | zcode-remediation-agent / current checkout | `8794aae…+dirty` | rp11_verify APPROVE: 검증기 18 passed+val01/val02 보강(부정 케이스 실측); cloud adapter는 자격증명 필요로 RP-12 이관(BLOCKED_EXTERNAL) | `RP-11/attempt-001` |
| RP-12 | 후보/실 provider/8h | RP-11 | IN_PROGRESS | zcode-remediation-agent + rp12_*_gate / candidate+current checkout | `4b202113f254a766fdd26db30e4f65e417f77c28` | **전체 gate 20/20 PASS(단일 실행·clean·검증기 PASS)** — 13개 테스트 격리 결함 해소(21635080, 4b202113). Ollama 12/12. soak-006 진행 중(~09-11 12:03Z, 70875519 — diff 근거로 소스 동일), cloud BLOCKED_EXTERNAL | `RP-12/attempt-001`~`004` |
| RP-13 | 배포/복구/manifest | RP-12 | DONE | rp13_remediate_evidence / candidate checkout | `4b202113f254…`(source) | rp13_verify2 APPROVE: R13-03 clean-install outside cwd API/auth 실측 및 원문 명령 로그 완비, R13-07 DR rehearsal에 previous_artifact_rollback 시나리오(0.0.9->0.1.0->0.0.9) 실측 추가, R13-05 manifest에 11개 artifacts 결합 및 검증기 PASS, 8 tests passed | `RP-13/attempt-002` |
| RP-14 | 독립 재검토/출시 판정 | RP-13 | TODO | — | — | — | — |
| RP-15 | 선택 유지보수 | RP-05 이후·후보 이전 | DEFERRED_NONBLOCKING | codex-root-orchestrator / current checkout | `4b202113f254a766fdd26db30e4f65e417f77c28` | DEFERRED_NONBLOCKING: append equality/제약 보존 이미 RP-05/09 완료; 대형 리팩토링 안정성 위해 유예 (`RP-15/attempt-001/decision.md`) | `RP-15/attempt-001` |

현재 필수 완료: **12/15** (RP-00 포함 13/15; RP-01/02/03/04/05/06/07/08/09/10/11/13 DONE; RP-12 IN_PROGRESS; RP-14 TODO). RP-03/04/05/07/08/09/10/11/13 독립 재검증(APPROVE) 완료 후 DONE 승격. 선택 RP-15는 분모에 포함하지 않는다. 체크 개수는 품질 점수나 상용화 백분율이 아니다. 조정자가 병렬화할 때에는 계획서 §4의 허용 범위 및 변경한 의존관계를 기록한다.

## 발견과 종료 증거 연결표

| 발견 | 해결 작업 | 최종 폐쇄 조건 | 현재 |
|---|---|---|---|
| FR-01 | RP-01, RP-14 | 실 sandbox 격리+fail-closed+독립 보안 승인 | 코드 수정+실측 완료(RP-01 DONE); 최종 출시 판정은 RP-14 |
| FR-02 | RP-02, RP-14 | shell 실제 우회 차단+외부 sentinel 불변 | 코드 수정+실측 완료(RP-02 DONE); 최종 출시 판정은 RP-14 |
| FR-03 | RP-03, RP-14 | traversal/symlink/transaction 복구 실측 | 재작업 실측 완료(RP-03 DONE): N번째 write 부분 쓰기 복원·commit CAS, driver residue 0, rp03_verify3 APPROVE; 최종 출시 판정은 RP-14 |
| FR-04 | RP-04, RP-14 | dirty/concurrent/untracked 변경 보존 | 재작업 실측 완료(RP-04 DONE): 동시 삭제 보존·충돌 기록, 독립 driver true, rp04_verify3 APPROVE; 최종 출시 판정은 RP-14 |
| FR-05 | RP-05, RP-09, RP-14 | cross-process read/create/append/compact CAS | 재작업 실측 완료(RP-05/09 DONE): 2개 실제 uvicorn worker 프로세스 경유 read/CAS 및 재시작 실측 완료, stale 409 확인, rp05_verify3 APPROVE(attempt-004); RP-09 수동 압축 E2E 완료; 최종 판정은 RP-14 |
| FR-06 | RP-11, RP-12, RP-14 | same-SHA 전부 gate+실 cloud/local+28,800초 | RP-12: 후보 4b202113에서 **전체 gate 20/20 PASS**(검증기 포함) — same-SHA 전체 gate 충족. 잔여: 28,800초 soak 완료 판정(~12:03Z), 실 cloud(BLOCKED_EXTERNAL) |
| FR-07 | RP-06, RP-12 | no-op delete를 검출하는 실 Chroma 시나리오 | RP-06 완료(DONE): 실측 VAL-01 12 passed·exit 0, no-op negative control FAIL 확인, rp06_verify2 APPROVE |
| FR-08 | RP-10, RP-14 | metadata/공식·mirror/지원·승인·점수 일치 | 문서 정합화 완료(REVIEW); 실제 승인 artifact는 BLOCKED_EXTERNAL, 최종 GO blocker 유지 |
| FR-09 | RP-11, RP-13, RP-14 | retrievable artifact/hash/provenance/복구 | 재작업 실측 완료(RP-13 DONE): wheel/sdist 해시·docker digest·SBOM/공지·benchmark·staging·logs 11개 아티팩트가 manifest로 연결, previous_artifact_rollback 포함 DR 5/5 통과, 검증기 8 tests passed, rp13_verify2 APPROVE(attempt-002); 최종 확인은 RP-14 |
| FR-10 | RP-07, RP-13 | source/bundle/installed config 일치 | RP-07+RP-13 완료(DONE): 4-way 바이트 동일·격리 설치·manifest에 wheel 해시로 provenance 연결, rp07_verify/rp13_verify2 APPROVE |
| 폴더 E2E 공백 | RP-08, RP-12 | A/B marker가 실 provider payload에 정확 반영 | RP-08 완료(DONE): 결정적 double 8 passed + Playwright 브라우저 E2E 2 passed(`ws-04-project-switch.spec.ts`), rp08_verify APPROVE; 실 provider는 RP-12 |
| 압축 E2E 공백 | RP-09, RP-12 | 수동 UI/자동 trigger/정보 보존/최종 budget | RP-09 완료(DONE): store+API 43 passed + Playwright 브라우저 수동 압축 E2E 4 passed(`conversation-compaction.spec.ts`), rp09_verify APPROVE; 실 provider는 RP-12 |

## RP-00 기준·증거 준비

- [x] R00-01 최종 보고서와 원래 VAL/RC 수용 기준 읽음
- [x] R00-02 HEAD/status/사용자 기존 변경을 기록하고 vault_data 보존
- [x] R00-03 이전 검토 대비 변경 항목 재현 상태 기록
- [x] R00-04 OS/Python/uv/Node/pnpm/sandbox backend 환경 기록
- [x] R00-05 evidence attempt 디렉터리와 owner/소유 파일/선행 배정 기록
- [x] R00-06 원문 명령 기록 방식과 비밀정보 제거 방식 확인
- [x] R00-07 독립 검토자가 기준/경로/미완료 상태를 확인

## RP-01 UnifiedAgent 격리

- [x] R01-01 API→단일/consistency 실행 호출 경로 확인
- [x] R01-02 두 경로 모두 검증된 공용 sandbox를 사용
- [x] R01-03 host raw fallback 제거, backend 불가 시 실행 전 실패
- [x] R01-04 최소 environment 구성, 가짜 secret 상속 없음
- [x] R01-05 정상 코드 성공과 실패 pytest 결과 구분
- [x] R01-06 실제 sandbox에서 외부 임시 sentinel 읽기/쓰기 거부
- [x] R01-07 loopback fixture egress 거부 확인
- [x] R01-08 timeout/자식 정리/output quota 확인
- [x] R01-09 기존 테스트 및 신규 isolation 회귀 통과
- [x] R01-10 원문 실측·실행 SHA·독립 보안 리뷰 PASS (`rp01_verify2`, candidate `4b202113`, attempt-003)

## RP-02 shell 경계

- [x] R02-01 permission 판정과 실제 실행의 request root 일치
- [x] R02-02 모델/API shell 실행에 OS 격리 강제
- [x] R02-03 sandbox 불가 시 raw host 실행이 없음
- [x] R02-04 `$HOME`/`${HOME}`와 quoted 경로 차단 실측
- [x] R02-05 붙은/분리 redirection, command substitution, backtick 우회 차단
- [x] R02-06 symlink/absolute/traversal/glob 우회 차단
- [x] R02-07 Python 등 child code의 외부 쓰기도 차단
- [x] R02-08 정상 내부 작업·공백/한글 경로 성공
- [x] R02-09 진행 중 프로젝트 전환이 이미 시작된 명령 root를 바꾸지 않음
- [x] R02-10 원문 로그·외부 파일 hash·독립 리뷰 PASS (`rp02_verify2`, candidate `4b202113`, attempt-003)

## RP-03 transaction 경계와 복구

- [x] R03-01 stage 원본 읽기 전 canonical containment 확인
- [x] R03-02 외부 absolute/traversal/symlink/new-leaf 경유 거부
- [x] R03-03 모든 op preflight 후 첫 write 수행
- [x] R03-04 stage→commit 경로 교체 및 write race 보호 검증
- [x] R03-05 원래 존재 여부와 원본 내용을 분리 보존
- [x] R03-06 기존 빈 파일은 실패 복구 후에도 존재
- [x] R03-07 새 파일은 실패 복구 후 제거, 관련 원본 복원
- [x] R03-08 N번째 write 실패 때 부분 변경·외부 변경 잔재 없음 — attempt-004: write 전 소유권 기록 + 실패 지점 preimage 복원. driver(`full`/`partial`) residue `true`→`false`, rolled 1→2, `git diff` 비어 있음; 신규 3 tests pre-fix 3 failed → post-fix 3 passed(`RP-03/attempt-004/logs/`)
- [x] R03-09 동시 변경/다른 파일 보존, 충돌 시 무조건 overwrite 없음
- [x] R03-10 focused 회귀·원문 재현·독립 리뷰 PASS (`rp03_verify3`, attempt-004 APPROVE: 17 focused pass, 68 consumer pass, driver residue 0, git diff 빈 문자열)

## RP-04 RSI mutation 소유권

- [x] R04-01 callback의 실제 cwd/root를 끝까지 추적
- [x] R04-02 격리 worktree 또는 검토된 소유 transaction 설계 확정
- [ ] R04-03 setup 실패 시 mutation 실행 0회 — 코드에 setup 실패 경로가 없어 N/A로 기록됨(RP-04/attempt-001 metadata limitations 참조)
- [x] R04-04 실패 시 전체 shared checkout 복구 명령을 사용하지 않음
- [x] R04-05 임시 repo에서 dirty B/untracked C 보존
- [x] R04-06 mutation 소유 A만 성공 반영 또는 실패 복구
- [x] R04-07 동일 파일 concurrent edit/delete 충돌 검출·보존 — attempt-004: 부재 소유 파일 복원 제거. 독립 gate driver `concurrent_deletion_preserved` `false`→`true`, dirty B/untracked C 보존, 신규 2 tests(`RP-04/attempt-004/logs/`)
- [x] R04-08 검증 예외/중복 복구/종료 후 자기 worktree만 정리
- [x] R04-09 mock rollback 없는 실제 Git 시나리오 수행
- [x] R04-10 호출자 회귀·원문 로그·독립 리뷰 PASS (`rp04_verify3`, attempt-004 APPROVE: 45 focused pass, 68 consumer pass, deletion preserved true)

## RP-05 대화 저장소

- [x] R05-01 기존 stale-cache 재현을 수정 전 기록
- [x] R05-02 read/create/CAS lock 순서와 disk refresh 통일
- [x] R05-03 get/get_revision이 다른 worker의 rev2를 즉시 관찰
- [x] R05-04 stale get_or_create를 conflict로 거부
- [x] R05-05 동시에 create/append가 기존 메시지를 덮어쓰지 않음
- [x] R05-06 append/compact 경쟁 시 CAS invariant 유지
- [x] R05-07 최종 메시지 수 = 성공 append 수 정확히 검증
- [x] R05-08 missing/corrupt 파일에 stale cache 재사용 없음
- [x] R05-09 반환 객체의 lock 밖 변경으로 store 손상 없음
- [x] R05-11 실제 API worker 경유 read/CAS 및 재시작 확인 — attempt-004: 실제 2개 uvicorn worker(Worker A, B) 및 재시작 Worker C 실측. Worker B stale CAS에 HTTP 409 거부, Worker C 재시작 후 rev 2/메시지 2건 보존 원문 기록 (`RP-05/attempt-004/logs/`)
- [x] R05-12 원문 로그·full SHA·독립 리뷰 PASS (`rp05_verify3`, attempt-004 APPROVE: 25 tests pass, live multi-process uvicorn workers authoritative read & 409 conflict & cold restart)


## RP-06 staging 검증기

- [x] R06-01 target/control source identity와 인덱스 초기값 확인
- [x] R06-02 삭제 후 target chunk 0, control 남음 검증
- [x] R06-03 semantic search hits 유무를 삭제 판정으로 오용하지 않음
- [x] R06-04 delete no-op negative control이 FAIL
- [x] R06-05 bool false detail이 성공으로 집계되지 않음
- [x] R06-06 restart/reindex/citation의 실제 수용 assert와 stats 키 확인
- [x] R06-07 required 미실행/예외/빈 목록이 PASS 되지 않음
- [x] R06-08 CLI 실패 exit code 및 JSON 판정 일치
- [x] R06-09 실제 persistent Chroma 정상/negative-control 원문 보존
- [x] R06-10 회귀·독립 리뷰 PASS (`rp06_verify2`, candidate `4b202113`, attempt-003)

## RP-07 기본 설정/패키지

- [x] R07-01 root/bundled config와 agent 소비자 계약 확인
- [x] R07-02 두 config 일치, equality 테스트 약화 없음
- [x] R07-03 전체 model-registry 테스트 통과
- [x] R07-04 새 wheel/sdist 생성, 포함 파일 확인
- [x] R07-05 별도 venv의 저장소 밖 cwd에서 wheel 설치 검증
- [x] R07-06 import 경로가 source checkout이 아님을 기록
- [x] R07-07 installed agent defaults와 agk --help/smoke 확인
- [x] R07-08 원문 출력·artifact hash·독립 리뷰 PASS (`rp07_verify`, attempt-003 APPROVE)

## RP-08 선택 폴더→요청

- [x] R08-01 동일 파일명·서로 다른 비밀 없는 marker의 A/B fixture 생성
- [x] R08-02 사용자 질문에는 marker 정답이 포함되지 않음
- [x] R08-03 실제 프로젝트 설정 선택/저장→새 요청 UI 실행 — Playwright E2E (`ws-04-project-switch.spec.ts`) desktop & narrow viewport 통과 (2 passed)
- [x] R08-04 UI identity/API request/server canonical root/tool read를 request ID로 연결
- [x] R08-05 provider 직전 payload에 A marker 포함·B marker 배제
- [x] R08-06 B 전환 및 A→B→A 반복, 반대 marker 배제
- [x] R08-07 reload/별도 탭/공백·한글/동명 경로 검증 — narrow viewport 및 라벨 동기화 브라우저 실측 완료
- [x] R08-08 진행 중 A 요청은 A root, 새 B 요청은 B root 유지
- [x] R08-09 삭제/미등록 root에서 fail-closed 오류 표시, cwd fallback 없음
- [x] R08-10 결정적 regression과 실제 브라우저 trace/screenshots 저장 — 결정적 8 passed + Playwright E2E 2 passed
- [x] R08-11 필요한 코드 수정의 타입·테스트·build 통과 — tsc clean, vitest 750 passed, playwright passed
- [x] R08-12 독립 리뷰 PASS (`rp08_verify`, attempt-002 APPROVE); 실 provider 반복은 RP-12에 명시적으로 이관

## RP-09 압축 종단간

- [x] R09-01 초기 제약/최신 지시/tool pair/citation 포함 fixture 준비
- [x] R09-02 실제 수동 UI control 클릭과 API 결과 연결 — Playwright E2E (`conversation-compaction.spec.ts`) 4 passed: 수동 버튼 클릭, aria-busy 및 진행 알림, snapshot 교체 및 이력 동기화
- [x] R09-03 자동 압축 threshold를 요청 흐름에서 실제 발생시킴 — API tier 실측 완료, 스트리밍 자동 압축 결함 수정 완료 (`context_summary.py`)
- [x] R09-04 summary에 초기 핵심 제약, 최신 사용자 지시 보존
- [x] R09-05 retained message IDs와 revision 단일 증분 검증
- [x] R09-06 tool-call/result pairing 및 citation source 보존
- [x] R09-07 모든 component 직렬화 후 provider 최종 budget 검사 — store 직렬화·토큰 감소 검증
- [x] R09-08 skipped/failed/over-budget UI와 events가 정확히 표시 — E2E 409 및 500 에러 처리 UI 검증 통과
- [x] R09-09 동시 append/stale revision/restart/다른 worker 읽기 확인
- [x] R09-10 압축 실패 시 무한 재시도·무한 running 없음 — 실패 시 에러 toast 및 버튼 재활성화 검증 완료
- [x] R09-11 원본 trace/응답/payload/count 저장, estimate와 실측 구분
- [x] R09-12 회귀 및 독립 리뷰 PASS (`rp09_verify`, attempt-002 APPROVE); 실 provider 반복은 RP-12로 이관


## RP-10 문서·승인 준비

- [x] R10-01 기존 DONE row별 SHA/test/manual/review 증거 인덱스 작성
- [x] R10-02 pending/누락은 현재 열린 상태로 표시, 역사 기록 보존
- [x] R10-03 공식 checklist와 .omo mirror의 현재 상태 동기화
- [x] R10-04 baseline/current/target 점수 구분, 근거 없는 100 제거
- [x] R10-05 플랫폼/provider 지원 범위와 Experimental/Unsupported 정확 표시
- [ ] R10-06 법무/개인정보/모델·공급자/라이선스/운영 승인 자료 인계 — 실제 담당자 artifact 필요(BLOCKED_EXTERNAL)
- [x] R10-07 승인 없는 항목은 BLOCKED_EXTERNAL/최종 blocker로 유지
- [x] R10-08 README/readiness/progress/claims의 현재 표현 일치
- [x] R10-09 후보 의존 승인과 준비 완료를 구분한 독립 문서 리뷰 PASS (`rp10_verify`, attempt-001 APPROVE)

## RP-11 gate·증거 수집기

- [x] R11-01 commercial_ga_gates.json의 모든 required gate 목록 고정
- [x] R11-02 실제 argv/cwd/UTC start/end/stdout/stderr/exit code 저장
- [x] R11-03 source SHA/dirty/environment/threshold hash를 artifact에 연결
- [x] R11-04 missing required/empty scenarios/false metric을 FAIL 처리
- [ ] R11-05 cloud 실제 실행 adapter와 streaming/tool/cancel/error 시나리오 준비 — cloud credential 없음(BLOCKED_EXTERNAL), RP-12에서 실 provider 실행 시 준비
- [x] R11-06 tool 목록 조회를 실행 성공으로 계산하지 않음
- [x] R11-07 soak workload가 요구한 실제 lifecycle/DB/worker/cleanup을 수행
- [x] R11-08 kill -9 후 재시작→최종 task 완료·중복 부작용 없음 검증 준비
- [x] R11-09 FD/RSS trend/DB lock/orphan 수집 실패를 0으로 숨기지 않음 — 샘플 구조화 및 실측 완료
- [x] R11-10 shipping lock/wheel과 dependency audit 대상 일치 — RP-13 manifest 작업으로 결합 완료
- [x] R11-11 잘못된 SHA/누락 artifact/60초 soak negative fixture 거부
- [x] R11-12 수집기 자체 테스트·dry run·독립 리뷰 PASS (`rp11_verify`, attempt-001 APPROVE, 18 passed)

## RP-12 후보와 실 운영 검증

- [x] R12-01 선행 코드/테스트/gate 변경 통합 완료
- [x] R12-02 clean release checkout의 full candidate SHA 고정
- [x] R12-03 전체 required gate 실행, 축소 smoke와 구분 — 4b202113 단일 실행 20/20 PASS·검증기 PASS(ga-final3.json)
- [x] R12-04 actual local provider streaming/실 tool/cancel/error 통과
- [ ] R12-05 actual cloud provider streaming/실 tool/cancel/error 통과 — 자격증명 없음(BLOCKED_EXTERNAL)
- [ ] R12-06 RP-08 marker 요청을 실제 provider에 반복·payload 확인 — 브라우저 tier 미실행
- [ ] R12-07 RP-09 수동/자동 압축을 실제 provider 경로에서 반복 — 미실행
- [x] R12-08 Chroma persistence/restart/reindex/delete/citation 실측
- [x] R12-09 지원 하드웨어 MLX 또는 CUDA 학습/checkpoint/resume/fuse 실측
- [ ] R12-10 SC-1~SC-6 필수 시나리오와 실제 복구 완료 검증 — 8초 리허설 전 green(복구 완료·중복 거부 포함), 28,800초 본실행 soak-006 진행 중(7h 10m 경과, 20/20 required gate PASS)
- [ ] R12-11 연속 부하 actual duration ≥ 28,800초 — rp12-soak-006 진행 중(PID 52583, 시작 13:03:29 KST, 7h 10m / 8h 경과, 예상 종료 ~21:03 KST), 완료 후 val02-006.json 판정
- [ ] R12-12 p95/p99/error/FD/RSS trend/orphan/DB lock 승인 기준 충족
- [ ] R12-13 샘플 누락·중단·미실행 없음, short rehearsal로 대체 없음
- [ ] R12-14 모든 결과의 동일 SHA와 clean 환경 확인, 독립 판정 PASS

## RP-13 배포/복구/manifest

- [x] R13-01 RP-12와 같은 SHA의 wheel/sdist/image 생성
- [x] R13-02 file/version/size/hash/retrievable location/provenance 기록
- [x] R13-03 source 밖 clean 설치에서 config/assets/CLI/API/auth 검증 — attempt-002: `/var/tmp`에서 cleanenv wheel 설치, `agk --help` exit 0, uvicorn 기동, Bearer auth 및 `/v1/health` 200, `/api/projects` 200 원문 로그 (`RP-13/attempt-002/logs/clean-install-api-auth.log`)
- [x] R13-04 container digest/health/auth/persistence 검증
- [x] R13-05 SBOM/notices/benchmark/staging/provenance/raw logs가 manifest에 연결 — attempt-002: 11개 아티팩트(wheel, sdist, gate-report, SBOM 2건, notices, benchmark, staging, docker-log, dr-log, clean-install-log) sha256/크기 매니페스트 결합 및 검증기 PASS
- [x] R13-06 backup→corruption→restore 뒤 실제 read/write 성공
- [x] R13-07 upgrade/migration 및 이전 artifact rollback 뒤 서비스/data 확인 — attempt-002: DR rehearsal에 previous_artifact_rollback 시나리오(0.0.9->0.1.0->0.0.9 롤백) 실측 추가 및 정합성 검증 (`dr-rehearsal.log`)
- [x] R13-08 Git checkout 성공만으로 rollback 완료 처리하지 않음
- [x] R13-09 두 번째 검증자가 파일 존재와 checksum/source SHA 확인 (`rp13_verify2`, attempt-002 APPROVE)
- [x] R13-10 삭제/변조 artifact negative fixture가 manifest 검증 실패
- [x] R13-11 독립 release artifact 리뷰 PASS (`rp13_verify2`, attempt-002 APPROVE)

## RP-14 최종 승인

- [ ] R14-01 code-quality 리뷰 PASS, full candidate SHA 기재
- [ ] R14-02 security 리뷰 PASS, full candidate SHA 기재
- [ ] R14-03 actual manual QA/runtime 리뷰 PASS, 원본 trace 포함
- [ ] R14-04 goal/release-criteria 리뷰 PASS, 필수 미실행 없음
- [ ] R14-05 docs/operations/context 리뷰 PASS
- [ ] R14-06 FR-01~10 및 폴더/압축 공백이 각각 증거로 닫힘
- [ ] R14-07 필요한 법무/privacy/provider/license/운영 승인 확보
- [ ] R14-08 지원 scope/SHA/date/reviewer/expiry 필드 완비
- [ ] R14-09 manifest 파일·hash·리뷰 candidate가 동일함
- [ ] R14-10 선행 RP-00~13 모두 DONE, 선택 RP-15의 실행/유예 근거 명시
- [ ] R14-11 공식/mirror/progress/readiness/claims/scorecard 동기화
- [ ] R14-12 FAIL/INCONCLUSIVE/미승인 blocker 0 확인 후에만 GO

## RP-15 선택적 유지보수 결정

- [x] R15-01 조정자가 EXECUTE 또는 DEFERRED_NONBLOCKING과 근거 기록 — `DEFERRED_NONBLOCKING` 결정 완료 (`.omo/evidence/final-review-remediation/RP-15/attempt-001/decision.md`: append equality/제약 보존 완료, 대형 리팩토링 안정성 위해 유예)
- [ ] R15-02 실행 시 candidate 고정 전 완료 일정·소유 파일 확정 (유예로 생략)
- [ ] R15-03 append equality를 RP-05에서 처리했는지 중복 확인 (유예로 생략)
- [ ] R15-04 상수 고정 테스트를 외부 관찰 계약 테스트로 보완 (유예로 생략)
- [ ] R15-05 budget refactor 실행 시 기존 behavior matrix·실패 사례 유지 (유예로 생략)
- [ ] R15-06 실행 시 RP-09 전체 회귀·독립 리뷰 PASS (유예로 생략)

유예한 경우 R15-02~06을 억지로 체크하지 않는다. DECISION/근거를 기록하고 이 작업을 필수 완료 분모에 추가하지 않는다.

## 외부 의존·재개 기록

| 작업 | 막힌 조건 | 필요한 자원/책임 역할 | 기술 작업 계속 가능한 범위 | 재개 조건 | 현재 |
|---|---|---|---|---|---|
| RP-01/02 | 실제 sandbox backend가 없다면 | 실행 환경 담당 | 단위 회귀와 fail-closed 검증 | 지원 backend에서 실제 격리 실행 | 해소 — macOS seatbelt 실측 완료(RP-01/02 attempt-002 원문 로그) |
| RP-10/14 | 법무/privacy/지원 승인 자료 없음 | 해당 권한 보유 담당자 | 코드 수정·증거 인덱스·문서 사실 정리 | 실제 승인 artifact 인계 | 확인 필요 |
| RP-12 | actual cloud credential/target 없음 | provider 계정 담당 | local/double 회귀·수집기 준비 | 테스트용 비밀정보를 안전하게 공급 | 확인 필요 |
| RP-12 | 지원 hardware 없음 | staging 운영 담당 | 일반 회귀·배포 준비 | 지원 장비에서 실측 가능 | 확인 필요 |
| RP-12 | 연속 8시간 실행 미완료 | staging 운영 담당 | 원문 수집·진행 상태 점검 | 끊김 없는 28,800초 결과 | 미실행 |

누락 credential을 소스·문서·대화에 평문으로 저장하지 않는다. “확인 필요”는 실제 blocker가 발생했다는 주장이 아니라 착수 점검 항목이다.

## 매 작업 종료/인계 양식

다음 양식을 실제 값으로 채워 해당 attempt의 handoff.md에 저장한다. 조정자가 검토 후 마스터 표를 갱신한다.

```text
작업 ID / attempt:
상태 (IMPLEMENTED / REVIEW / REWORK / BLOCKED_EXTERNAL / INCOMPLETE):
담당자 / branch 또는 worktree:
시작 SHA / 검증 full SHA / dirty diff 유무:
수정 파일 및 변경한 계약:
완료한 체크 ID:
실행 명령·exit code·원문 경로:
수동 QA 시나리오·실측·trace/screenshot 경로:
재현됐던 결함이 지금 어떻게 달라졌는지:
미완료 체크 ID와 이유:
실행 중 job ID/PID/출력 경로/재연결 방법 (없으면 없음):
외부 자원/승인 필요 여부:
다음 작업자가 시작할 정확한 단계:
다른 작업자 변경·수정 금지 파일:
독립 검토자에게 요청할 항목:
```

## 종료 전 조정자 확인

- [ ] 모든 링크/증거 파일이 실제 존재하며 원문과 요약이 구분됨
- [ ] 현재 SHA와 과거 SHA의 검증이 혼재하지 않음
- [ ] 테스트 실패를 skip/임계값 완화로 숨긴 사례 없음
- [ ] 사용자 vault/프로젝트 변경이 보존됨
- [ ] 승인 누락이 TODO/DONE 문구에 의해 감춰지지 않음
- [ ] 최종 사용자가 확인할 결과·남은 제한·다음 단계가 한국어로 기록됨
