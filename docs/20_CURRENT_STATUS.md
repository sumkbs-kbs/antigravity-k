---
title: Ssak-Ai 현재 상태 (단일 요약)
created: 2026-09-16
status_owner: true
observed_head: ffb0ebb312b76d86742d3e4065628a9704f8268e
tags: [current-status, single-source, handoff, ga]
---

# 현재 상태 — 단일 요약

이 문서가 **"지금 무엇이 참인가"의 단일 소유자**다. 다른 문서(README · `docs/10`~`19` · `docs/ga/**`)는
이 문서를 가리키고 자기 범위와 날짜만 밝힌다. 그 문서들에 남은 "현재 상태 / 최신 판정" 배너는
**그 시점의 이력**이며 현재 상태가 아니다.

이 문서가 소유하지 **않는** 것: 값(후보 SHA · 코드 지문 · required gate 개수)은
[CR-14 판정 카드 §5](ga/CR14_FINAL_CANDIDATE_VERDICT.md)가 유일한 소유자다. 이 문서는 그 값을
복사하지 않고 **범위와 해석**만 말한다. 이 문서와 README 어디에도 값을 박지 않는다 — 값을 박으면
다음 기록 커밋이 그 파일을 고쳐 gate 지문을 옮긴다(attempt-013 에서 실제로 발생, F-22).

기준 HEAD: `ffb0ebb3` (2026-09-16 관측). 판정의 대상은 HEAD 가 아니라 **커밋된 후보**다.

## 1. 제품 접속 — 포트 세 역할을 구분한다

| 역할 | 기본값 | 정의 위치 | 성격 |
|---|---:|---|---|
| **제품 API 서버**(제품 기본값) | **8000** | `src/antigravity_k/config.py` `ServerConfig.port` | `agk serve` 를 인자 없이 띄웠을 때의 포트. `AGK_SERVER_PORT` 로 변경. 대시보드·`/health`·`/api/ready`·`/docs` 가 **같은 포트**다 |
| **대시보드 개발 서버**(Vite dev) | **5173** | `dashboard/vite.config.ts` | `make dev-dashboard` 전용. 제품 사용자 경로가 아니다(서버가 정적 자산을 서빙한다) |
| **패키징(Desktop/Electron)** | `SSAK_HOST_URL` 이 가리키는 주소 | `desktop/hostLifecycle.js` | 없으면 자식 프로세스로 `agk serve --host --port` 를 띄운다. 별도 제품 포트를 발명하지 않는다 |
| 레거시 `8400` | **기본값 아님** | — | Phase 6 커밋(`ddcf3599`)에서 8400 → 8000 기본값 정리. 문서에 남은 8400 은 오기다([운영 가이드 §실행/검증](09_OPERATION_GUIDE.md)) |

**8400 을 무조건 8000 으로 치환하지 않는 이유:** 예시 로컬 런타임 주소도 8000 을 쓴다
(`AGK_VLLM_API_BASE=http://127.0.0.1:8000/v1`, `docker run -p 8000:8000`). 즉 "8000" 은
**제품 서버**와 **사용자가 따로 띄우는 OpenAI 호환 런타임** 양쪽에 등장하는 값이고, 같은 호스트에서
겹치면 한쪽을 옮겨야 한다. 치환은 값이 아니라 **역할**을 보고 해야 한다.

새 사용자 접속: 서버를 띄우면 브라우저에서 그 포트를 열면 된다(같은 포트가 대시보드·API·문서를 모두 낸다).
PIN 이 설정된 배포에서는 첫 화면이 PIN 입력이다.

## 2. 판정·게이트 상태

- **마지막으로 커밋된 후보**: CR-14 attempt-040. 값(후보 SHA · 코드 지문 · required gate 인벤토리 23)은
  [판정 카드 §5](ga/CR14_FINAL_CANDIDATE_VERDICT.md)가 소유한다. 그 후보의 required gate 는 전 항목 통과했고
  **판정은 NO-GO** 다(사유는 §5).
- **이 후보 이후의 NX 작업은 커밋되지 않았다.** `src/**`·`tests/**`·`README.md` 의 NX-01~07 변경은
  작업 트리에만 있고 판정 카드의 코드 지문 **밖**이다. 따라서 "required gate 전 항목 PASS"는
  **현재 작업 트리에 대한 주장이 아니다.**
- `23/23`(required gate 인벤토리 기준) 은 이 저장소에서 **두 가지 뜻**으로 쓰여 왔다:
  1. CR-14 required gate **인벤토리** 23개 중 23개 통과(후보 귀속 — 판정 근거가 되려면 후보·지문이 붙어야 한다),
  2. 특정 테스트 파일 묶음의 **23건** 통과(게이트와 무관 — 판정 근거가 아니다).
  문맥(후보·지문·범위)이 없는 `23/23` 은 판정 근거로 쓰지 않는다.

## 3. 8시간 soak 경과 — 세 단계를 섞지 않는다

| 단계 | 시각 | 결과 | 상태 |
|---|---|---|---|
| ① 1차 8시간 | 2026-09-15 ~14:47 KST | SC-1~5 PASS · **SC-6 FAIL** — RSS `~66.8 → 1721.8 MB`(`rss_growth_mb=1654.9` ≫ 기준 `64`) · workload ~150,554 append · `errors=0` · `fd_growth=0` · 후보 `b6003205` | **FAIL**(기록 보존) |
| ② 교정 결정 A | 2026-09-15 | ConversationStore soft-max auto-compact 기본 64(`78012f4a`) · **임계값 64MB 는 올리지 않음** | 결정 |
| ③ 재soak | 2026-09-15 15:07 → ~23:08 KST | `duration_s=28801.318` · append `12,102,886` = revision `12,102,886` · 최종 view 26 (≤ soft max 64) · RSS `65.7 → 114.4`(+48.7) · `errors=0` · `fd_growth=0` · `orphan_worktrees=0` · SC-1~6 `all_pass: true` | **JSON 지표 PASS** |
| ④ 종료·귀속 | — | 래퍼 로그 마지막 줄 `finished exit:141`(원문 명령 미보존 → stdout 절단 가능성, INCONCLUSIVE) · **재soak 당시 코드 후보·시작/종료 지문 귀속 UNVERIFIED** | **미확정** |

요약 JSON 의 SHA256 과 sample 배열 요약(count/min/max/first/last)은
[soak 요약](qa/2026-09-16-followup/soak-summary.json)에 있고 원본은 수정하지 않았다.

**그래서 "8시간 soak PASS"는 JSON 지표 기준이며, ④ 가 닫히기 전에는 게이트 PASS 로 승격하지 않는다.**
종료 원문은 복구 불가로 종결하고 NX-10 의 새 후보 시험으로 대체한다(NX-00-F01).

## 4. 열려 있는 기술 TODO (사람 축과 별도로 존재한다)

**"기술 축은 모두 닫혔다"는 문장은 CR-14 후보 범위에서만 참이다.** 신뢰성·커넥톰 계획 범위에서는
아래가 열려 있다([체크리스트 진행 기록](19_RELIABILITY_AND_CONNECTOME_CHECKLIST.md)이 카드 상태의 단일 원본):

- NX-00: 종료·귀속 INCONCLUSIVE (지표 재확인은 DONE) · **NX-00-F01** harness started/finished + exit 보존 결정
- NX-01·NX-02·NX-03·NX-04·NX-05·NX-06·NX-08: 구현·시험 green **REVIEW** — 독립 검토자 미지정, NX-02 는 ADR 승인자 미지정
- **NX-02-F01**: 세션 저장소가 prompt view 로 오염되는 경로 수정 여부 결정
- NX-06: 정적 REVIEW / **런타임 BLOCKED**(cluster 없음 — Pod readiness·EndpointSlice 미관측) · `degraded→200` 정책 승인 필요
- **NX-09**(2026-09-16, REVIEW): 실 UI 동선 — ~~**F04**(커밋된 `dashboard_dist` 가 소스보다 낡아 **서빙되는 SPA ≠ 소스**)~~ → **NX-10 에서 닫힘**(번들 재생성 후 UI 증인 30/30 passed · 동결 직전 `pnpm build` 를 절차로 고정)
  (NX-09-F06 은 재측정으로 **결함 아님** — 한 창 측정 아티팩트였고, 두 창 증인 T8 이 `sessions_revoked: 1`·close 571ms 로 계약을 고정한다)
  (NX-09-F03 첨부 이미지 미전달은 **수정** — [ADR-0005](adr/0005-multimodal-attachments.md) · 증인 T4 가 provider 본문의 PNG 바이트와 "그 턴에만" 정책을 고정한다. 잔여: 이전 턴 이미지 재전송, 압축과 첨부의 상호작용)
- NX-01 이 넘긴 **cue lexicon 회수율** — **어휘 성능은 실측**(2026-09-16, 합성 코퍼스 + 실제 경로: 사전 표현 9/10 · 사전 밖 0/12 · 잡담 승격 6/7 · 경로 피해 3건 — [cue-lexicon-measurement.md](qa/2026-09-16-followup/nx01/cue-lexicon-measurement.md)). **실사용 회수율은 미실시**(라벨 코퍼스 필요) — 소유자 재지정 필요(별도 카드).
- NX-02 가 넘긴 **손상 대화 격리·폐기 운영 절차**는 NX-09 가 가져가지 않았으나, NX-10 창에서 **문서화 + 프로브 + 실데이터 사본 리허설까지 마감**했다 — 남은 것은 소유자 지정과 정책 선택(제품 flag·보존 기간).
- NX-08 잔여: **F2**(다른 호스트가 남긴 vault lock 은 깨지지 않음 — filelock 동작, 단일 호스트 배포에서 미발생,
  공유 볼륨·다중 인스턴스 확장 시 정책 필요) · **F1**(NFS flock/fsync 미실측) · **G1**(tombstone GC 정책 미결정, NX-03 후속)
- **NX-10**(2026-09-16, **REVIEW/NO-GO**): 후보 고정·필수 게이트 실행 — 필수 게이트 일부 green·일부 not_run 이고, **후보 SHA·지문과 게이트 수치는 §8 규칙에 따라 여기에 쓰지 않는다**(값 소유자: [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) · 판정·미해결: [nx10/handoff.md](qa/2026-09-16-followup/nx10/handoff.md)).
  이 attempt 가 실제로 고친 것: 순환 임포트 6건(`engine/atomic_write.py`·`security/ws_registry.py` leaf 신설 + 패키지 루트 임포트 제거) · 중복 cast 7건 · bandit B324 1건 ·
  기준선에서도 실패하던 `network_access_api` 타입 2건 · **낡은 커밋 번들 재생성**. 동작 변경 0줄(seam 시험 192 passed).
  전용 창에서 전량 스위트·벤치·master-e2e·ambient E2E 를 실행해 대장을 마감했다(전량 스위트에서 **실패 4건**이 드러났고, 넷 다 다른 레인의 커밋에 귀속된다 — 커밋된 트리만 비교하는 계약 테스트다).
SC-1~6 8시간 soak 1차 실행은 **중단했다**(오너 판정): 19분 51초 경과 시점(`2026-09-16T07:41:42Z`)에 SIGTERM 으로 끊었고, 러너가 `exit: 143` 을 기록하는지까지 확인했다(중단 사유·방법·경과는 `nx10/soak-exit.txt` 에 러너 기록과 **구분해서** 남겼다 — 상세는 [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §10). 동결 배치 뒤에는 오너 지시로 **오늘 22:00 KST 예약 실행**으로 옮겼고(`schedule_nx10_soak.sh`, 목표 `2026-09-16T13:00:00Z`, 종료 예정 `~06:00 KST`), 보조도구 승격으로 지문이 이동해 **그 예약을 취소하고 새 지문으로 재장전**했다(취소 이유·시각은 `nx10/soak-exit.txt`, 현재 기대 지문·대기는 `nx10/soak-schedule.txt` 가 소유 — §8 규칙대로 여기 값은 쓰지 않는다). 예약 실행기는 시작 직전 지문을 확인해 동결 트리가 아니면 **8시간을 쓰지 않고 중단**한다. 2차 즉시 실행(08:15:38Z)은 예약으로 옮기며 3분 39초에 중단됐다 — 그때까지 코드를 건드리지 않는다.
사유: **후보 코드를 더 고치기로 했으므로**(SSE 실연결 폐기 · journal quota/retention · tombstone GC) 이 실행의 종료 지문이 최종 후보와 달라져 “시작/종료 지문 동일”을 만족할 수 없고, 러너는 종료 시에만 리포트를 쓰므로 중단 시점에 남는 판정 근거가 없다.
대신 순서를 바꿨다: **코드 배치 → 동결 → 8시간 soak 1회 → 게이트 재측정**. soak 과 나란히 돌릴 수 있는 문서·결정 작업은 그 soak 창으로 옮겼다.
필수 게이트 23개를 **전부 실행**했다(배치 이전 트리: 22 passed · 1 failed · **0 not_run**; 동결 지문 `157311cf…` 에서 **22개 중 21 passed · 1 failed**(`gate-report-freeze002.json`, `clean-machine-runtime` 은 커밋 전제라 제외) — `ga_gate_verify` 가 지적하는 문제는 정확히 `missing_required: clean-machine-runtime` · `required_red: python-tests` 둘). `clean-machine-runtime` 은 SCOPE 의 `BLOCKED_EXTERNAL` 이 사실오류였음이 드러나 실행해 통과했고(`--ref HEAD` 특성상 그 green 은 HEAD 의 것 — 커밋 뒤 후보 값), 실패 1개는 타 레인 계약 충돌 4건이다. **커밋해도 그 4건은 초록이 되지 않는다**(CR-14 울타리 이동·EX-05 승격은 타 레인/오너의 일이고, 우리 커밋은 HEAD 를 선언된 후보에서 더 멀어진다) — 마감 순서는 [nx10/CLOSURE_RUNBOOK.md](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md) 가 소유한다.
  **2026-09-16 갱신(커밋 뒤):** 오너 지시로 **3분할 커밋 완료**(코드+계약 / 대시보드·번들·SBOM / 증거·문서 — SHA 와 스테이징 방식은 [nx10/CLOSURE_RUNBOOK.md](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md) §3.1b)했고, 커밋된 후보에서 필수 **23개를 완주**(22 passed · 1 failed · 0 not_run)해 **`clean-machine-runtime` 이 처음으로 후보 값**이 됐다(passed, 43.7s). 그 결과 마감 도구가 지적하는 문제는 **`required_red: python-tests` 하나**로 줄었다. 지문이 이동했으므로(커밋도 지문을 옮길 수 있다 — [§3.1](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md)) 예약 soak 을 그 지문으로 재장전했다.
  **미해결:** soak 결과와 지문 일치 확인 · 타 레인 실패 4건 정리(CR-14 후보 재선언 · EX-05 승격 판정) · 독립 검토자·owner 허용 기록 · `vault_data`(gitlink·소유 불명) 미커밋 유지 · 1MB 초과 게이트 리포트 4개는 정책상 미커밋(sha256 매니페스트만 커밋).
  **손상 대화 격리·폐기 절차**는 문서화·프로브까지 끝냈다(2026-09-16): 제품은 읽기·삭제 모두 fail-closed 라 삭제도 거절되고, 운영자는 파일을 **저장소 루트 밖**으로 보존 이동 + 삭제 표식으로 처리한다(루트 안에 두면 마이그레이션 **표식 없는** 저장소에서 `legacy_requires_migration` 으로 무관한 대화까지 실패 — 실측 A; 표식이 있으면 견딤 — 실측 B). **실데이터 사본 리허설까지 완료**(migration 3단계 + 격리 절차, 원본 해시 불변) — [nx02/damaged-conversation-disposal.md](qa/2026-09-16-followup/nx02/damaged-conversation-disposal.md).
- **NX-10 동결 배치**(2026-09-16, 오너 판정 — soak 중단 사유이기도 하다): 후보에 닿는 남은 코드·정책을 한 배치로 마감했다. ① **NX-05 SSE 실연결 폐기 구현**(`api/sse_revocation.py` + `server.py` 배선 — 실서버 관측에서 세대 변경 1.112초 뒤 `session.revoked`+EOF, before 는 9프레임 계속 흐름) ② **NX-02 journal retention 기본값 결정·구현**(대화당 soft 64 MiB 경고 / hard 512 MiB 쓰기 거절 507, **자동 prune 없음**, `store_usage()` 관측) ③ **NX-03 tombstone GC 정책·구현**(자동 만료 없음, 운영자 명시 회수를 아카이브 이동으로, 감사 JSON). 지문이 이동했으므로 `c65fe0e1…` 의 값은 더 이상 후보의 것이 아니다 — 새 지문·게이트·soak 값은 [nx10/BATCH_FREEZE.md](qa/2026-09-16-followup/nx10/BATCH_FREEZE.md) 와 [GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) 가 소유한다.
- **보조도구 승격 완료**(NX-10 창, 2026-09-16T09:46:05Z, 오너 판정 B): 검사기·판정기·프로브 3종과 계약 시험 3종을 `scripts/`·`tests/` 로 옮겨 이제 **정적 게이트와 스위트가 지킨다**(그 전에는 `docs/` 안이라 어느 게이트도 돌지 않았다). 지문이 이동했고 `.gitignore` 에 인증 해시 백업 규칙이 들어갔으며, **승격 뒤 필수 22개를 새 지문에서 다시 측정했다**(값은 §8 규칙대로 여기 쓰지 않는다 — 소유자: [nx10/BATCH_FREEZE.md](qa/2026-09-16-followup/nx10/BATCH_FREEZE.md) §4 · [nx10/promote-runner-exit.txt](qa/2026-09-16-followup/nx10/promote-runner-exit.txt) · `gate-report-promote002.json` · [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §13). 계획·이동표·실행 기록: [nx10/PROMOTION_PLAN.md](qa/2026-09-16-followup/nx10/PROMOTION_PLAN.md). 22:00 soak 은 **마지막 측정 뒤에** 새 지문으로 재장전됐다(`docs/` 만 추가 수정 중).
- NX-11: desktop 지원 확정 **BLOCKED**(사용자 pause)
- NX-12~NX-15: 선택 연구(커넥톰 baseline·평가 계약)
- CR-14 잔여 기술 항목: **C14-03**(전 구간 번들 시나리오) · **C14-04**(이전 artifact 업그레이드) ·
  **C14-05**(28,800초 + 실 provider) 미완

## 5. 사람·조직·외부 축 (기술 진행으로 닫히지 않는다)

| 항목 | 상태 |
|---|---|
| 출시 책임자 | **강병석** 배정(2026-09-14) — 근거 있는 **NO-GO** 기록([C14-08 판정](ga/CR14_C14_08_RELEASE_OWNER_VERDICT.md)) |
| 독립 code/security/QA 검토자 | **미배정** — 출시 책임자 **겸직**, 제3자 독립성 **미충족**(그 사실을 숨기지 않는다) |
| EX-01 실 provider | **PARTIAL** — 로컬 Ollama PASS · NVIDIA PASS · openrouter/free PASS · Gemini/ZAI/OpenRouter 유료 FAIL |
| EX-02 승인 | **PARTIAL** — 범위 문구 자체 승인 완료, legal **BLOCKED_EXTERNAL** |
| EX-03 이전 artifact | **DONE — NOT_AVAILABLE**(이전 릴리스 artifact 없음) |
| EX-04 지원 OS sandbox | **DONE**(macOS 26.6.2 arm64, seatbelt) — **행렬은 승격하지 않음** |
| EX-05 8시간 soak | §3 참조(JSON PASS / 종료·귀속 미확정) |
| EX-06 범위 축소 | **DONE — 축소 없음** |
| GA 승인 | **없음.** 이 저장소에서 GO 를 선언할 수 있는 주체는 출시 책임자뿐이다 |
| 오너 결정 요청 모음 | [GA owner decision packet](ga/GA_OWNER_DECISION_PACKET.md) — D1~D8(선택지·영향·권고·의존 순서). **값은 이 표가 소유하지 않고 소유 문서를 가리킨다** |

## 6. 지원 범위

분류와 근거의 소유자는 [GA 지원표](ga/GA_SUPPORT_MATRIX.md)다. 분류는 네 단계를 쓴다:
**Supported**(GA 지원 약속 — 현재 **0행**) · **Experimental**(구현/설정 근거는 있고 지원 약속은 없음) ·
**Unsupported**(범위 밖) · **Not evaluated**(관측·산출물은 있으나 판정하지 않음).

- 실험 행을 마케팅할 때는 "평가용으로 제공" 까지만 말할 수 있다 — supported/certified/production-ready 금지.
- **macOS DMG**: 로컬 작업 트리에 설치 가능한 산출물이 **있다**(`dist/Ssak-Ai-0.1.0.dmg`, 2026-09-15,
  sha256 로컬 검증 · `dmg-smoke` PASS). 그러나 **커밋되지 않았고**(`dist/` 는 gitignore), 서명·공증 검증,
  깨끗한 실기기 설치, 업데이트 피드·롤백 검증은 **미완**이다. 산출물의 존재와 검증 완료를 같은 것으로
  읽지 않는다 — 그 구분은 지원표의 `Not evaluated` 행이 소유한다.

## 7. 문서 지도 — 누가 무엇을 소유하는가

| 문서 | 소유 범위 | 현재 상태 표기 |
|---|---|---|
| **`docs/20_CURRENT_STATUS.md`** (이 문서) | **현재 상태 · 포트 역할 · soak 단계 · 열린 축** | 소유자 |
| `README.md` | 설치·실행·기능·환경 변수 | 이 문서를 **링크 한 줄**로 가리킨다(값 없음) |
| `docs/08_CHANGELOG.md` | 변경 이력 | 이력 |
| `docs/10_FINAL_READINESS_REPORT.md` | attempt 이력 · 최종 준비도 보고 | 이력(값은 판정 카드 §5) |
| `docs/11`~`13` | GA-100 계획·체크·진행 이력 | 이력 |
| `docs/14`~`15` | RP(최종 검토 개선) 이력 | 이력 |
| `docs/16`~`17` | CR(상용 신뢰성) 이력 · 값 소유자 표기 | 이력 |
| `docs/18`~`19` | **NX 개발계획 · 카드 상태의 단일 원본** | 카드 상태 |
| `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md` | **후보 SHA · 코드 지문 · 게이트 인벤토리 값** | 이력(값 소유자) |
| `docs/ga/CR14_GATE_COVERAGE_BOUNDARY.md` | 게이트 커버리지 경계(무엇을 검증하지 않는가) | 경계 |
| `docs/ga/GA_SUPPORT_MATRIX.md` | 지원 분류 | 지원 상태 |
| `docs/ga/CR14_EX_EXECUTION_LEDGER.md` | 외부 조건(EX-01~06) 실행 대장 | 실행 상태 |
| `docs/09_OPERATION_GUIDE.md` · `deploy/README.md` | 운영 · 배포 | 운영 |
| `docs/packaging/**` | 데스크톱 패키징 이력(pause) | 이력 |

규칙: **현재 상태 배너는 이 문서가 소유한다.** 다른 문서는 배너를 새로 만들지 않고, 자기가 어느
범위의 이력인지 밝힌 뒤 이 문서를 가리킨다.

## 8. 갱신 규칙

1. 최종 수치(후보·지문·게이트 개수)는 NX-10 이후 **판정 카드 §5 에서 한 번만** 갱신한다.
   이 문서와 README 는 값을 복사하지 않는다.
2. 이 문서를 고칠 때는 §1(포트) · §3(soak) · §4(열린 축) 세 절이 서로 모순되지 않는지 확인한다.
3. 이 문서는 `docs/` 안에 있으므로 gate 코드 지문 **밖**이다 — 기록 커밋은 `docs/` 전용으로 유지한다.
