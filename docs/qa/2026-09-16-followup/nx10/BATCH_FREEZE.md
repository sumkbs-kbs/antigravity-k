# NX-10 동결 배치 기록 (2026-09-16)

오너 판정(2026-09-16)에 따라, **soak 중단 → 후보에 닿는 남은 코드·정책을 한 배치로 마감 → 동결**
순서를 실행한 기록이다. 배치 전 지문 `c65fe0e1…` 의 값은 더 이상 후보의 것이 아니다(같은 코드가
아니다) — 아래 지문에서 다시 잰다.

## 1. 후보 동결 상태

| 항목 | 값 |
|---|---|
| HEAD | `20d529fc1f17c8ff580eaf0d853dcd1ce92172d5` |
| 공식 후보 SHA | **없음 — dirty**(미커밋 작업분). 커밋은 사용자 승인 사항이라 하지 않았다 |
| worktree fingerprint | **`157311cf106f6e1de937331d332c9dcf947ee826c28c856cfdaccead0ddad8ce`** |
| 의존성 잠금 | `uv.lock`·`dashboard/pnpm-lock.yaml`·`dashboard/package-lock.json` **변경 없음**(배치는 잠금을 건드리지 않는다) |
| 변경 규모 | `git status --porcelain` 157항목(배치 + 이전 카드 작업분 + 재생성된 번들 61) |

## 2. 배치가 바꾼 것 (3건, 전부 오너 선택)

| # | 항목 | 코드/정책 | 계약 시험 | 증거 |
|---|---|---|---|---|
| ① | **NX-05 SSE 실연결 폐기** | `api/sse_revocation.py` 신설 + `server.py` 배선 + `auth_routes.extract_bearer_token` 공개 + metric `stream_revoked` | `tests/test_nx05_sse_live_revocation.py` **10 passed** | [nx05/sse-live-revocation.md](../nx05/sse-live-revocation.md) · `before-sse.json`/`after-sse.json` · `repro_sse_live_revocation.py` |
| ② | **NX-02 journal retention 기본값** | `engine/conversation_retention.py` 신설 + `_commit_event` 집행 + `store_usage()` + 오류코드 507(wire 계약·fixture 동시 등록) | `tests/test_nx02_journal_retention.py` **9 passed** | [nx02/retention-decision.md](../nx02/retention-decision.md) · ADR-DAT-02 Context 8 결정 기록 |
| ③ | **NX-03 tombstone GC 정책** | `session_manager.py` 에 `tombstone_usage()` + `collect_tombstones()`(아카이브 이동 + 감사 JSON) | `tests/test_nx03_tombstone_gc.py` **6 passed** | [nx03/tombstone-gc.md](../nx03/tombstone-gc.md) |

셋 다 **기본 동작을 조용히 바꾸지 않는다**: ① 은 `text/event-stream` 응답에만, ② 는 한계 초과
시에만(기본값은 넉넉하고 `0` 으로 끌 수 있다), ③ 은 운영자가 호출할 때만 동작한다. 자동 삭제·
자동 만료는 **어디에도 추가하지 않았다**(ADR-DAT-02 의 silent-pruning 금지, NX-03 의 임의 TTL 금지).

## 3. 이 지문(`157311cf…`)에서 재측정한 검증

| 검증 | 결과 | 증거 |
|---|---|---|
| `python-ruff` / `python-format` | **passed**(수정 후 0 error) | 이 문서 §5 명령 |
| `python-mypy` | **passed** (`Success: no issues found in 492 source files`) | 동일 |
| `python-basedpyright` | **passed** (`0 errors, 0 warnings`) | 동일 (`_StreamingResponseLike` Protocol 로 캐스팅 — 초기 구현의 1 error 를 고쳤다) |
| `python-tests`(전량) | **4 failed · 6587 passed · 14 skipped**(10분 14초) | `batch-gates.log` — 실패 4건은 **타 레인 귀속**(CR-14 fence 2 + NX-07 EX-05 2), 배치가 만든 실패 **0** |
| `python-benchmark` | **passed**(16 passed, 18.9초) | `batch-runner-exit.txt` |
| `dashboard-tests`(vitest) | **passed**(89 files / **888 tests**) | 이 문서 §5 |
| `dashboard-build` | **passed + 결정론적**: 같은 트리에서 재빌드해도 지문이 `157311cf…` 그대로(번들이 소스와 일치, `tree_moved` 없음) | §5 |
| SSE 실연결(실 uvicorn) | before: 9프레임 계속 흐름·폐기 없음 / after: 1.112초에 폐기 프레임 + EOF | `before-sse.json`/`after-sse.json` |
| **필수 게이트 22개 단일 창 재측정** | **21 passed · 1 failed · 0 not_run**(18분 39초, 지문 전후 `157311cf…` 동일; 실패는 `python-tests` 타 레인 4건) | `gate-report-freeze002.json` · `freeze-runner-exit.txt` · `gate_verify-freeze002.txt` |
| **스위트 실행 전후 지문 동일** | 시작 `157311cf…` = 종료 `157311cf…`(측정 중 트리가 움직이지 않았다) | `batch-runner-exit.txt` |

`python-tests` 의 실패 4건은 **커밋된 트리만 비교하는 계약 테스트**라 이 배치의 미커밋 변경이 결과에
들어가지 않는다(전량 실행에서 다시 확인). **그래도 실패는 실패로 센다** — 카드는 원인별 면제를 주지 않는다.

## 4. 이 지문에서 **아직 안 잰 것** (다음 창)

1. **SC-1~6 28,800초 soak — 오늘 22:00 KST 예약 실행(동결 트리)**:
   * 1차: `07:21:51Z` 시작 → `07:41:42Z` 중단(오너 판정, 19분 51초)
   * 2차: `08:15:38Z` 시작 → `08:19:17Z` 중단(오너 지시로 예약 실행으로 이동, 3분 39초)
   * **예약(현재 상태):** `screen -dmS nx10soak bash docs/qa/2026-09-16-followup/nx10/schedule_nx10_soak.sh`
     — 목표 **오늘 22:00 KST = `2026-09-16T13:00:00Z`**, 예약 시점 대기 16,799초, 기대 지문 `157311cf…`,
     종료 예정 **`~06:00 KST`(2026-09-16T21:00Z)**. 기록: `soak-schedule.txt`(예약 시각·지문·pid),
     `soak-schedule.log`(15분 heartbeat), `soak-exit.txt`(시작/종료 지문·exit),
     `soak-28800.json`(최종 리포트).
   * **예약 실행기의 보호 장치:** 시작 직전에 지문을 재계산해 기대값과 다르면 **8시간을 쓰지 않고
     중단**한다(`aborted_reason: fingerprint drift`, exit 2). 대기·실행 중 idle sleep 은
     `caffeinate -i` 로 막는다(끄려면 `NX10_NO_CAFFEINATE=1`).
   * 회수 시 확인할 것: `all_pass`, **종료 지문 == 시작 지문 == `157311cf…`**, exit, 그리고 8h 규모에서
     처음 타는 `stream_line_count` 경로. **지금은 “통과”를 주장하지 않는다.**
   ⚠ 22:00 까지 **코드를 건드리지 않는다**: 한 줄이라도 바뀌면 예약 실행기가 지문 불일치로 중단하거나,
   중단하지 못한 경우에도 결과가 이 동결의 것이 아니게 된다 — 이 창의 작업은 `docs/` 안에서만 한다.
2. ~~나머지 required 게이트 전수 재실행~~ → **완료**(2026-09-16, `screen nx10freeze`, 18분 39초):
   `run_freeze_gates.sh` 가 `clean-machine-runtime` 만 빼고 22개를 한 리포트
   (`gate-report-freeze002.json`)로 돌렸다. 결과 **21 passed · 1 failed · 0 not_run** (실패는
   `python-tests` 의 타 레인 4건 그대로), **지문은 시작·종료 모두 `157311cf…`**
   (`freeze-runner-exit.txt`). 마감 도구는 문제 **2개**만 지적한다:
   `missing_required: clean-machine-runtime`(커밋 전제) · `required_red: python-tests`(타 레인).
   같은 창에서 `test_nx07_doc_consistency.py` 재실행 → 2 failed / 24 passed(동일 사유)로
   **문서 편집이 정합성 실패를 새로 만들지 않았음**을 확인.
   덧붙여 마감 전 점검(`verify_docs_commands.py` → `docs-command-verification.txt`): 문서가 안내하는
   CLI 플래그 13개·`AGK_*` 변수 13개·경로 21개가 **전부 실제로 존재**하고, 커밋 대상 121파일 비밀 스캔도
   깨끗하다. **WARN 1건**: `data/auth_hash.bak.pre-0000` 이 무시되지 않아 `git add -A` 로 커밋될 수 있다
   (→ 경로 명시 스테이징, `.gitignore` 수정은 동결 해제 뒤).
3. `clean-machine-runtime` — `--ref HEAD` 를 export 하므로 **커밋 뒤에만** 후보 값이 된다.
4. `ga_gate_verify`(후보 일치·soak 미충족 시 정직한 판정)와 attempt-close.
5. 타 레인 충돌 2건(EX-05 승격 판정 · CR-14 후보 재선언) — 게이트 수치에 계속 −4 로 나타난다.
6. **보조도구 승격**(`docs/` → `scripts/`·`tests/`) — **완료**(2026-09-16T09:46:05Z, 오너 판정 **B**):
   도구 3종 + 계약 시험 3종 이동 + `.gitignore` 규칙, 게이트 **7/7**, 지문 `157311cf…` → **`ab980ba5…`**.
   기록: `promote/promotion-applied.txt`(성공·실패 시도 모두) · 계획 [PROMOTION_PLAN.md](./PROMOTION_PLAN.md) ·
   리허설 `promote/dry-run-output.txt`. 리허설·본실행이 이제 **표와 게이트를 공유**한다
   (`promote/paths.sh`·`promote/gates.sh`) — 그 전에는 리허설이 본실행과 다른 게이트를 돌려
   도구의 `parents[4]` 가정·venv 하드 요구를 못 잡았다(첫 두 시도가 이동 0건으로 롤백).
   ⚠ **이 항목 때문에 §4-1 의 예약 soak 을 끓고 재장전했다**(두 번): 예약 실행기는 지문 불일치를 감지하면
   8시간을 쓰지 않고 멈추므로 — ① 승격 직후 `ab980ba5…` 로 재장전(09:47Z) → ② 그 뒤 게이트 재측정이
   끝난 지문 `0f345d0c…` 으로 **다시 재장전**(10:26Z). ②의 원인은 측정 중에 이 창이 `scripts/…py` 를
   고친 것이었다(순서 교훈: **마지막 측정 → 지문 확인 → 예약**, CLOSURE_RUNBOOK §5b). 취소·재장전 기록은
   `soak-exit.txt`·`soak-schedule.txt` 에 러너 기록과 구분해 남겼다.
   **새 지문에서의 필수 게이트 재측정**: `run_promote_gates.sh` → `gate-report-promote002.json`
   (**22개 중 21 passed · 1 failed**(`python-tests`, 타 레인 4건) · 시작 = 종료 = `0f345d0c…`),
   마감 도구 문제는 옛 지문과 동일한 2개(`missing_required: clean-machine-runtime` · `required_red: python-tests`)
   — 승격이 **새 문제를 만들지 않았다**. `promote001.json` 은 측정 중 편집으로 지문이 갈린 attempt 라
   값은 참고로만 둔다. 아래 §3 의 `157311cf…` 값은 이제 **옛 지문의 값**이므로 후보로 물려받지 않는다.

**판정은 여전히 NO-GO/REVIEW 다.** 이 문서는 "동결했고 그 지문에서 무엇을 쟀다"의 기록이지
출시 판정이 아니다.

## 5. 실행 명령 (그대로 재현 가능)

```bash
# 정적 4개
uv run --isolated --frozen --extra dev --extra rag --extra documents ruff check src/ tests/ scripts/
uv run --isolated --frozen --extra dev --extra rag --extra documents ruff format --check src/ tests/ scripts/
uv run --isolated --frozen --extra dev --extra rag --extra documents mypy src/
uv run --isolated --frozen --extra dev --extra rag --extra documents basedpyright src/ scripts/ --level error

# 전량 스위트 + 벤치 (전용 창, 게이트별 exit 를 따로 보존)
screen -dmS nx10batch bash docs/qa/2026-09-16-followup/nx10/run_batch_gates.sh
cat docs/qa/2026-09-16-followup/nx10/batch-runner-exit.txt

# 대시보드
cd dashboard && pnpm test --run && pnpm build && cd ..

# 배치 신규 계약 시험
.venv/bin/python -m pytest tests/test_nx05_sse_live_revocation.py \
  tests/test_nx02_journal_retention.py tests/test_nx03_tombstone_gc.py -q

# 지문(동결 확인)
.venv/bin/python -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; \
print(ga_gate.worktree_fingerprint(pathlib.Path('.')))"
```
