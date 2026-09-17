# NX-10 — 게이트 실행 대장 (필수 게이트 23개, 후보 지문 `da54e07b…`)

카드: `docs/18` §NX-10 / `docs/19` §NX-10. 작성: 2026-09-16.
측정 도구: `.venv/bin/python scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json`
(게이트 목록·명령은 **manifest 에서 읽었다** — 하드코딩하지 않는다. manifest sha256
`a40867c743a9df5ba5854548476fcc53913e5364968a01e30e00c3e03b2eadb7`.)

## 0. 후보 식별자 (마지막 attempt 기준)

| 항목 | 값 |
|---|---|
| HEAD SHA | `20d529fc1f17c8ff580eaf0d853dcd1ce92172d5` |
| 작업 트리 | **dirty** (NX 카드 작업분 미커밋) — 공식 후보 SHA 는 아직 없다 |
| worktree fingerprint | **`c65fe0e1649e5e89…`** (게이트를 측정한 지문은 `da54e07b…` — §10 의 하네스 수정으로 이동) |
| 지문 범위 | code (경로 규칙: `docs/`, `.omo/` 제외) |

**주의(지문별로 어디까지 쟀는가):** §2 의 **22 passed · 1 failed · 0 not_run** 은 서로 다른 지문의
측정을 합쳐 말한 값이다 — `python-tests`(failed)는 `da54e07b…` 에서, `clean-machine-runtime` 과
정적·supply 9개는 `c65fe0e1…` 에서 쟀다(`gate-report-newfp-static.json`·`-supply.json`·`attempt016.json`).
지문이 이동한 원인은 §10 의 하네스 수정이다. soak 과 간섭하는 게이트(E2E·대시보드·전량 스위트)는
**코드 동결 + 8시간 soak 이 끝난 뒤** 재측정 대상이다(§10). **`c65fe0e1…` 도 최종 지문이 아니다** —
오너 판정으로 NX-05 SSE 폐기·NX-02 quota·NX-03 tombstone 을 한 배치로 더 고치기로 했으므로,
최종 후보는 그 배치 뒤의 지문이고 그때 모든 required 게이트를 그 지문에서 다시 잰다.
→ **그 재측정은 완료됐다**: 동결 지문 `157311cf…` 에서 **21 passed · 1 failed · 0 not_run**(§12,
`gate-report-freeze002.json`). 즉 현재 유효한 수치는 **§12 의 것**이고, §2 의 표는 지문별 경위를
남기기 위한 이력이다. 커밋 전이라 `clean-machine-runtime` 만 후보 값이 아니다.

**attempt 007~011 은 모두 이 지문에서 측정됐다.** attempt 002 이전은 지문이 다르므로
(`d8f040ef…` → `cd9d9560…` → `7d4ed001…` → `b7850c76…` → `da54e07b…`) **합산하지 않는다**.
지문이 바뀐 이유는 전부 이 카드에서 코드/번들을 고쳤기 때문이며 attempt 별로 아래에 적었다.

### 후보 SHA 가 이동했다 (측정 중 외부 커밋)

attempt 001 은 `ffb0ebb3` 에서, attempt 002 부터는 `20d529fc` 에서 측정됐다. 이동 원인은
**이 카드가 아니라 다른 레인의 커밋**이다(`78012f4a fix(conversation): soft-max auto-compact…`,
`ef960ae2`/`ffb0ebb3`/`20d529fc` = CR-14 EX-05 문서 커밋). 카드 §절차 6(“창·후보가 다르면 green
을 합산하지 않는다”)에 따라 attempt 001 의 결과는 **참고 기록으로만** 남긴다.

## 1. attempt 별 결과 (원본 리포트 보존)

| attempt | 지문 | 게이트 | 결과 |
|---|---|---|---|
| 001 | `d8f040ef…` | python-ruff, python-format, python-mypy, python-basedpyright | ruff 1 passed · **format/mypy/basedpyright failed** |
| 002 | `cd9d9560…` | 같은 4개 | format passed · **ruff/mypy/basedpyright failed**(리팩터 중간 상태) |
| 003 | `7d4ed001…` | 4개 + package-build + security-bandit | **5 passed · bandit failed**(B324) |
| 004 | `b7850c76…` | 4개 + package-build + sbom-generate + bandit + api-e2e | **8 passed / 0 failed** |
| 005 | `b7850c76…` | dashboard-install, dashboard-lint, dashboard-typecheck | **3 passed** |
| 006 | `b7850c76…` | dashboard-test, dashboard-build | test passed · build **tree_moved** |
| 007 | `da54e07b…` | dashboard-build | **passed**(번들 재생성 후 안정) |
| 008 | `da54e07b…` | dashboard-e2e-witnesses | **passed 30/30** |
| 009 | `da54e07b…` | accessibility-e2e, dependency-audit-dashboard | **2 passed** |
| 010 | `da54e07b…` | docker-build | **passed**(230.6s) |
| 011 | `da54e07b…` | dependency-audit-python | **passed** |
| 012 | `da54e07b…` | **python-tests(전량)** | **failed** — `4 failed, 6562 passed, 14 skipped, 16 deselected` (608.09s, exit 1) |
| 013 | `da54e07b…` | python-benchmark | **passed** — `16 passed, 6580 deselected` (18.43s) |
| 014 | `da54e07b…` | master-e2e | **passed** — 하네스 6단계 **6/6** (2.4s) |
| 015 | `da54e07b…` | dashboard-e2e-ambient | **passed** — main **16/16** · disclosure healthy 1 · exhausted 1 · hub 2 (46.3s, exit 0) |

## 2. 최종 per-gate 상태 (23개 = 전부 required)

| # | 게이트 | 상태 | 소요 | 측정 attempt |
|---|---|---|---|---|
| 1 | python-ruff | passed | 3.0s | 004 |
| 2 | python-format | passed | 2.5s | 004 |
| 3 | python-mypy | passed | 5.0s | 004 |
| 4 | python-basedpyright | passed | 12.2s | 004 |
| 5 | package-build | passed | 3.0s | 004 |
| 6 | security-bandit | passed | 5.4s | 004 |
| 7 | sbom-generate | passed | 1.1s | 004 |
| 8 | api-e2e | passed | 22.9s | 004 |
| 9 | dashboard-install | passed | 0.2s | 005 |
| 10 | dashboard-lint | passed | 5.5s | 005 |
| 11 | dashboard-typecheck | passed | 3.4s | 005 |
| 12 | dashboard-test | passed | 11.8s | 006 |
| 13 | dashboard-build | passed | 26.7s | 007 |
| 14 | dashboard-e2e-witnesses | passed | 45.0s | 008 |
| 15 | accessibility-e2e | passed | 9.8s | 009 |
| 16 | dependency-audit-dashboard | passed | 0.5s | 009 |
| 17 | dependency-audit-python | passed | 6.9s | 011 |
| 18 | docker-build | passed | 230.6s | 010 |
| 19 | python-tests (전량, 7200s) | **failed** | 608.1s | 012 — 실패 4건, 전부 **타 레인 커밋** 귀속(§6·§8-1) |
| 20 | python-benchmark (1800s) | passed | 22.0s | 013 |
| 21 | master-e2e | passed | 2.4s | 014 (하네스 6단계 6/6) |
| 22 | dashboard-e2e-ambient | passed | 46.3s | 015 — main 16/16 · disclosure healthy 1 · exhausted 1 · hub 2 |
| 23 | clean-machine-runtime (7200s) | passed | 42.6s | 016 — **HEAD(`20d529fc`) 클린룸 재현 성공** (아래 경계 주의) |

**23개 required 가 모두 최소 1회 실행됐다: 22 passed · 1 failed · 0 not_run**
(지문 주의: `python-tests` 는 `da54e07b…` 에서 측정된 failed 이고, `c65fe0e1…` 에서는 재측정하지 않았다.
clean-machine 과 정적·supply 9개는 `c65fe0e1…` 에서 측정했다.)

not_run 0 은 카드 §수용의 절반을 만족한다. 그러나 **실패 1개는 남아 있고**, 카드는 원인별
면제를 주지 않으므로 판정은 여전히 NO-GO 다(§11).

### `clean-machine-runtime` — SCOPE 의 분류가 틀렸고, 실행해서 바로잡았다

`SCOPE.md` 는 이 게이트를 “깨끗한 지원 호스트 필요(`BLOCKED_EXTERNAL`)” 로 선언했다. **그 선언이
잘못이었다** — `scripts/verify_clean_machine.sh` 를 읽어 보면 그것은 호스트 청결 검사가 아니라
**클린룸 재현 검사**다:

```
git archive HEAD → 임시 디렉터리(3078 파일)
  → uv sync --locked (extras: dev rag mlx)   ✓
  → 패키지 임포트 · CLI smoke · agk doctor    ✓
  → API E2E smoke (tests/test_e2e_smoke.py)   ✓ 24s
  → wheel 빌드 (6.5M)                          ✓
  → 신규 venv pip install (PyPI 해석)          ✓ 6s
  → wheel 아티팩트 검증(버전·package-data·bin/agk·pip check) ✓
```

필요 조건은 `git` + `uv`(+ 네트워크)뿐이라 **어느 호스트에서든 돌 수 있다**(실제로 통과했다).

**경계 — 이 green 은 후보의 것이 아니라 HEAD 의 것이다:** 스크립트는 `--ref`(기본 `HEAD`)를 export 하므로
**커밋된 트리**를 검증한다. 이 카드의 후보는 미커밋(dirty)이라 그 안에 들어가지 않는다.
따라서 “클린머신 재현 성공”은 **`20d529fc` 에 대해** 참이고, 후보 값이 되려면 **커밋 뒤 재실행**이 필요하다.

`dashboard-e2e-ambient` 는 **스스로 자유 포트를 고르고** 격리 서버(`/health` 폴링 후 시작)를 세워
스펙에 `AGK_BACKEND_URL` 로 넘긴다 — 그래서 NX-09 가 기록한 “상시 8012 인스턴스와의 포트 경합으로
흔들리던 9건”과 다른 조건이다(그 게이트는 `cr\d+-` 증인 세트였고, 이건 ambient 전용 스펙 세트다).

**실패 1개(python-tests)는 이 카드의 변경 때문에 실패한 것이 아니다.** 4건 모두 다른 레인의 커밋에
귀속되고, 두 가지 원인이 있다(§6·§8-1): ① NX-07 의 EX-05 승격 계약 2건, ② CR-14 의 “울타리 이동”
계약 2건(선언된 후보 `b6003205` 뒤에 코드 스코프 38개 경로를 건드린 커밋들이 생겼다).

### not_run 5개의 다음 창 명령 (그대로 복사해 실행)

```bash
.venv/bin/python scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json \
  --output docs/qa/2026-09-16-followup/nx10/gate-report-next-<try>.json \
  --only python-tests --only python-benchmark --only master-e2e \
  --only dashboard-e2e-ambient --only clean-machine-runtime
```

`--merge-into gate-report-attempt011.json` 은 **같은 SHA·같은 manifest sha·같은 지문일 때만**
이월된다(`merge_refusal_reason`). 그 조건이 깨지면 새 파일로 남기고 합산하지 않는다.

## 3. 이 카드에서 실제로 고친 결함 (게이트가 드러낸 것)

측정 자체가 세 종류의 결함을 드러냈고, 셋 다 **기준선(HEAD) 재측정으로 귀속을 확정**했다
(`git archive HEAD` 추출본 `/tmp/nx10-base` 에서 같은 명령 실행).

| # | 결함 | 기준선에서도 실패? | 처리 |
|---|---|---|---|
| NX-10-B1 | `basedpyright` 순환 임포트 **6건** — `vault↔vault_privacy`, `auth_routes↔session_state`, `engine/__init__↔model_manager·inference_providers`(4) | 아니오(기준선 2건) → **이 카드 이전 NX 작업이 만든 것** | 3개 leaf 모듈로 구조 분리(아래 §4) |
| NX-10-B2 | `mypy` 중복 cast 7건(`inference_providers` 6 · `model_manager` 1) | 아니오 | cast 제거(타입이 이미 일치) |
| NX-10-B3 | `security-bandit` B324 — `summary_memory.constraint_id` 의 sha1 | 아니오(이 함수는 이 카드 이전 작업의 신규 코드) | `usedforsecurity=False` 로 의도 명시(**해시는 바꾸지 않는다** — 저장된 constraint id 가 달라진다) |
| NX-10-P1 | `mypy`/`basedpyright` `network_access_api.py:23-24` (`str \| int`) | **예** — 기준선에서도 같은 2건 | 최소 가드(`isinstance(ip, str)`)로 해소. **다른 레인 파일을 건드렸으므로 기록을 남긴다** |
| NX-10-P2 | `dashboard-build` → `tree_moved` | 확인 필요(아래 §5) | 커밋된 번들이 낡아 빌드가 추적 파일을 덮어썼다 → 번들 재생성(§5) |

## 4. 순환 임포트 6건 — 왜 “억제”가 아니라 분리인가

셋 다 **함수 내부 임포트**여서 런타임에는 문제가 없었고, 따라서 `# type: ignore`/`noqa` 로
덮을 수도 있었다. 덮지 않은 이유: 게이트가 잡은 것은 표면 증상이 아니라 **의존 방향의
역류**이고, 그 역류는 이 저장소가 이미 문서로 금지한 규칙이다(예:
`api/routes/session_state.py` 모듈 docstring “라우트 모듈 간에는 이 모듈을 향한 의존만
허용하고, 모듈 간 직접 임포트(역류)는 하지 않는다”).

| 만든 사람/시점 | 역류하던 의존 | 분리한 곳 |
|---|---|---|
| NX-08 (마스킹이 원자적 저장을 재사용) | `vault_privacy → vault` (그리고 기존 `vault → vault_privacy`) | `engine/atomic_write.py` (신규 leaf, stdlib + `vault_git` 만) |
| NX-09 (PIN 변경이 열린 WS 를 즉시 닫음) | `auth_routes → session_state` (그리고 기존 `session_state → auth_routes`) | `security/ws_registry.py` (신규 leaf, stdlib + `WebSocket` 타입만) |
| NX-09-F03 (표면별 첨부 변환) | `from antigravity_k.engine import multimodal` = **패키지 루트 요구** | `from antigravity_k.engine.multimodal import adapter_messages` (직접 이름) — `model_manager`·`tool_loop` 도 동일 |

기존 이름은 깨지 않았다: `vault.write_text_atomically`, `session_state.register_authorized_ws`
/`close_authorized_ws_blocking`/`authorized_ws_count`/`reset_authorized_ws_registry` 는
**재바인딩(재내보내기)** 으로 그대로 남는다. NX-08 의 실패 주입 시험만 seam 위치를 따라
옮겼다(`patch(antigravity_k.engine.atomic_write._fsync_fd)`).

## 5. `dashboard-build` = `tree_moved` — F04(서빙 번들 신선도)의 원인 확정

NX-09 가 “커밋된 `dashboard_dist` 가 소스보다 낡았다”로 남긴 F04 를, 이 카드는 **게이트가
직접 잡아내는 형태로** 재현했다:

1. attempt 006: `dashboard-build` 가 exit 0 으로 빌드했지만 상태가 **`tree_moved`** —
   즉 빌드가 **추적 중인** `src/antigravity_k/dashboard_dist/**` 를 덮어썼다(61개 파일).
2. 같은 명령 재실행(attempt 007): **passed**. 빌드는 결정론적이므로, 커밋된 번들이
   소스의 빌드 산출물과 **바이트 단위로 같아지면** 게이트는 통과한다.

→ F04 의 해소책은 “번들을 무시한다”가 아니라 **후보 동결 전에 번들을 소스에서 다시 만들고
그 결과를 후보에 포함한다**이다. 이번 후보는 그 상태다(§0 의 지문에 반영됨).
부작용: 대시보드 소스를 고치는 카드는 **동결 직전에 `pnpm build` 를 다시 돌려야** 한다.

또한 attempt 006 의 `dashboard-build` 는 exit code 0 이면서 상태가 `tree_moved` 였다 —
게이트 러너가 “빌드 성공”과 “트리가 움직임”을 구분해 보고한다는 사실도 이번에 확인했다.

## 6. 측정 중 발견한 **교차 레인 충돌** (이 카드가 고치지 않는다)

게이트 밖에서 표적 실행(tests)을 돌리면서 NX-07 의 문서 정합성 계약이 **두 개 실패**하는 것을 찾았다:

```
tests/test_nx07_doc_consistency.py::test_soak_phases_stay_separated
  AssertionError: EX-05 상태 셀이 종료·귀속 미확정(INCONCLUSIVE)을 말하지 않는다
tests/test_nx07_doc_consistency.py::test_teeth_soak_done_promotion_is_detected
  AssertionError: 기준선이 이미 위반이다
```

원인은 **다른 레인의 커밋**이다. HEAD `20d529fc`(“docs(cr14): record EX-05 PASS after Decision A 8h
resoake”, 이 카드의 변경이 아니다)가 `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 의 EX-05 행을
`**PASS** (resoake Decision A)` 로 바꾸면서 **“귀속 UNVERIFIED / 종료·귀속 미확정” 문구가 사라졌다.**
같은 문서 §EX-05 재soak 결과는 여전히 “이 결과로 EX-05 를 DONE 으로 올리지 않는다. ④ 가 남아
있다”라고 적고 있어 **한 문서 안에서 자기모순**이고, `docs/20` §3의 ④(종료·귀속)도 미확정 그대로다.

**이 카드는 그 행을 되돌리지 않았다** — CR-14 레인의 소유 문서이고, 사통 수정은 오너 판정이다.
대신 이 충돌을 기록한다. 이것은 NX-07 계약 테스트가 **자기 임무를 수행한** 결과이지 테스트 고장이 아니다:

| 필요 결정 | 선택지 |
|---|---|
| EX-05 승격 | (a) ④ 를 증거로 닫고(시작/종료 지문·exit 보존) 그때 PASS 로 승격 · (b) 승격을 취소하고 “JSON PASS / 귀속 UNVERIFIED” 를 복원 |
| 계약 위치 | 위 결정과 무관하게 `tests/test_nx07_doc_consistency.py` 의 두 계약은 유지 (문구 혼재를 금지하는 것이 목적) |

**이 failure 2건은 처음에는 `python-tests` 가 `not_run` 이라 “18 passed / 0 failed” 뒤에 가려져 있었다.**
전용 창에서 전량 스위트를 실제로 돌린 뒤(attempt 012) **게이트 실패로 드러났다** — 대장 수치만 보면
놓치는 것이 바로 이 지점이고, 카드 §수용이 not_run 0을 요구하는 이유가 이것이다.

이 충돌은 **오너 판정 브리프**로 분리했다: **[EX05_PROMOTION_CONFLICT.md](EX05_PROMOTION_CONFLICT.md)**
(단계 ①FAIL/②결정/③JSON PASS/④귀속 INCONCLUSIVE 분리 · 증거 필드 인용 · 선택지 A/B/C · 적용할 1줄 수리안).

## 8. 전용 창 실행 (이 대장 작성 이후)

남은 3개(긴) 게이트를 **`screen` 세션으로 분리 실행**한다. 왜 별도 세션인가: 이 창에서 백그라운드로
띄우면 도구의 호출 타임아웃이 **래퍼(ga_gate)만 죽이고 exit 를 잃는다** — 실측했다(pytest 가 고아로
남았고 리포트 JSON 이 기록되지 않았다). 그 실패 모드를 피하려고 실행기를 스크립트로 고정하고
게이트별 exit 를 **별도 파일**에 남긴다:

```bash
screen -dmS nx10gates bash docs/qa/2026-09-16-followup/nx10/run_remaining_gates.sh
screen -ls ; cat docs/qa/2026-09-16-followup/nx10/runner-exit.txt    # 진행·exit 대장
```

**먼저 실패한 방식을 증거로 남긴다**: 도구 호출 안에서 `nohup … &` 로 띄운 첫 시도에서는 호출 타임아웃이
**ga_gate 프로세스만 죽이고** pytest 가 고아로 남았고 리포트 JSON 이 기록되지 않았다. 그 파일이
`background-wrapper-failure.log` 다 — 내용은 게이트 헤더 1줄뿐이고, **결과가 없다는 사실 자체가 실패 모드의 증거**다
(고아 pytest 를 죽이고 screen 방식으로 다시 돌렸다). NX-00 이 “래퍼 파이프와 무관한 실제 exit 보존”을
요구한 이유를 이 카드에서 재현한 셈이다.

| 게이트 | 리포트 | 시작 | exit |
|---|---|---|---|
| python-tests | `gate-report-attempt012.json` | 2026-09-16T06:14:46Z | **1** (06:25:01Z, 608s — `4 failed, 6562 passed, 14 skipped, 16 deselected`) |
| python-benchmark | `gate-report-attempt013.json` | 06:25:01Z | **0** (06:25:23Z — `16 passed, 6580 deselected`) |
| master-e2e | `gate-report-attempt014.json` | 06:25:23Z | **0** (06:25:26Z — 하네스 6단계 6/6) |

### 8-1. `python-tests` 실패 4건의 귀속 (전부 타 레인 — 재확인함)

```
FAILED tests/test_cr14_fence_movement_detection.py::test_no_code_scope_commit_after_the_declared_candidate
FAILED tests/test_cr14_fence_movement_detection.py::test_declared_fingerprint_is_the_fingerprint_of_head_within_the_fence
FAILED tests/test_nx07_doc_consistency.py::test_soak_phases_stay_separated
FAILED tests/test_nx07_doc_consistency.py::test_teeth_soak_done_promotion_is_detected
`**어느 것도 이 카드의 변경 탓이 아니다** — 넷 다 **커밋된 트리**(`commit_fingerprint(root, rev)`)를
비교하므로 미커밋 작업 트리(이 카드의 변경)는 결과에 들어가지 않는다. 실행해서 직접 확인한 값:

- CR-14 울타리 2건: 선언된 후보 `b6003205365606407cadfd6cbb1c813110beef0f`(지문 `02349a8d…`)와
  HEAD `20d529fc`(지문 `2068e72b…`) 사이에 **코드 스코프 38개 경로**가 움직였다 — `code_scope_changes()`
  가 돌려준 목록에 `src/**`·`dashboard/src/**`·`tests/**`·`desktop/**` 가 있다(지문에서 빠지는 건
  `docs/`·`.omo/` 뿐). 즉 **CR-14 의 선언 후보가 자기 레인의 커밋들로 이미 이동했고**, 계약 테스트가
  그것을 잡은 것이다. (NX-07/NX-08 기록의 “후보 이후 데스크톱 레인 커밋이 지문을 옮긴 2건”과 같은 계열이며,
  커밋 범위가 그때보다 넓어졌다.)
- NX-07 EX-05 2건: §6 의 교차 레인 충돌(= 오너 판정 대기).

**이전에 알려졌던 다른 실패 5건(사용자 홈 레거시 대화로 503)은 이번 전량 실행에서 재현되지 않았다.**
실패 집합이 바뀌었으므로 “예전과 같은 7건”으로 뭉개지 않고, 이번 측정값(`4 failed / 6562 passed / 14 skipped`)을
그대로 기록한다.

기록 파일: `runner-exit.txt`(게이트별 exit + HEAD + dirty), `runner.log`(러너 원문).
러너 스크립트가 시작 시 HEAD·dirty 를 적어 두므로, **결과가 나온 뒤 후보가 이동했다면 그 사실이
대장에 남는다**(다른 레인이 이 창에서 커밋할 수 있다 — 실제로 측정 중 1회 이동했다).

## 9. 단일 창 재실행과 마감 도구의 경계 (attempt full001)

게이트를 전용 창에서 **한 번에** 돌려 **리포트 1개**를 만들었다(호출 예산 때문에 쪼갠 15개 파일로는
마감 형태가 되지 않는다 — 실측: `missing_required: …` 22개). 제외 1개는 `clean-machine-runtime`
(`BLOCKED_EXTERNAL`)이다.

| 항목 | 값 |
|---|---|
| 리포트 | `gate-report-full001.json` (HEAD `20d529fc`, fingerprint `da54e07b…`) |
| 결과 | **21 passed · 1 failed · 22개 중** (09:41:13Z → 09:59:59Z, 약 19분) |
| 실패 | `python-tests`(exit 1) — 실패 4건은 §8-1 그대로(타 레인 귀속) |
| 마감 도구 | `ga_gate_verify.py` → **FAIL**: `missing_required: clean-machine-runtime` · `required_red: python-tests` |

이 실행은 쪼갠 측정과 **일치했다**. 특히 이번에는 `dashboard-build` 가 **첫 시도에 passed** 로 나왔다
— 번들이 소스와 일치하는 상태라는 사실이 단일 창에서도 확인된다(§5).

**마감까지 남은 장애물이 이제 정확히 2개다**(추측이 아니라 도구가 이름을 대면서):
`clean-machine-runtime`(깨끗한 지원 호스트) 과 `python-tests`(타 레인 커밋에 귀속된 4건).

## 10. soak 러너 준비 + 60초 리허설 (SC-6 이 차단됨)

8시간 soak(SC-1~6, 28,800s)은 NX-10 수용의 남은 항목이다. 러너 `run_nx10_soak.sh` 를 만들고
NX-00 의 세 실패 모드를 코드로 막았다: ① 원문 명령 보존, ② **시작·종료 시 HEAD SHA와 지문** 기록,
③ 파이프 대신 파일 출력 + exit 별도 보존.

리허설(60초)을 실제로 돌려 하네스가 동작하는지 확인했다 — `soak-60.json` · `soak-exit.txt`:

| SC | 결과 |
|---|---|
| SC-1 | pass — workers 8·tasks 32·terminal_contradictions 0·cross_owner_leak 0 |
| SC-2 | pass — appended 150·lost_originals 0·view 34(soft max 64)·revision 일치 |
| SC-3 | pass — projects 40·missing 0·errors 0 |
| SC-4 | pass — SIGKILL 후 재개·중복 side effect 거부 |
| SC-5 | pass — p95 2.86ms·error_rate 0·fd_growth 0 |
| **SC-6** | **fail** — `orphan_worktrees: 1` (RSS +19.4MB · fd 0 · errors 0 · 나머지 불변식 모두 true) |

### 그 실패의 정체 (추측 아님 — 실행해서 확인)

`orphan_worktrees` 는 **시나리오 샌드박스가 아니라 저장소 전역**을 센다:

```python
orphan_wt = subprocess.run(["git", "worktree", "list"], cwd=REPO_ROOT, ...).stdout.count("prunable")
```

그리고 지금 이 체크아웃의 prunable 항목은 **제품이 만든 것이 아니라 다른 작업의 러너**다:

```
/private/tmp/ssak-runner-gates.ENbZhm/checkout   adae06a6 (detached HEAD) prunable
```

**이 차단 요소는 이 카드가 처음 발견한 것이 아니다** — NX-04 가 이미 같은 경로를 지목하며
남겼다(“카드 범위 밖 정리 필요, 검사 삭제 금지”, `nx04/handoff.md` §4). 이번 리허설의 기여는
**비용을 수치화한 것**이다: 그대로 8시간 soak 를 시작하면 **8시간 뒤에** 같은 이유로 SC-6 이 fail 한다.

제품의 worktree 는 `WorktreeManager` 가 `<repo>/.ag_worktrees` 에 만든다 — 그러므로 “이 실행이 만든
worktree 만 센다”는 **좁히기**는 의도를 지키면서 격리할 수 있다(검사를 지우는 것이 아니다).

### 결정과 실행 (오너 결정: **검사 좁히기 + 환경 정리**)

1. **검사 좁히기** — `orphan_wt` 를 제품 worktree 루트(`<repo>/.ag_worktrees`)로 한정했다.
   저장소 전역 카운트를 지운 것이 아니라 **무엇을 세는지 확정**한 것이다(타 작업의 `/tmp`
   worktree 는 제품의 불변식이 아니다). 새 헬퍼 `_count_product_orphan_worktrees()` 는 직접
   호출해서 **0** 을 돌려주는 것을 확인했다(전역 카운트는 1 이었다).
2. **환경 정리** — `git worktree prune` 으로 stale 항목(`/private/tmp/ssak-runner-gates.ENbZhm/checkout`)을
   치웠다. 남은 두 항목(`agk-f45-before-034`, `ssak-rp12-candidate`)은 **디렉터리가 살아 있어
   타 작업 소유**이므로 건드리지 않았다 — 이제 좁힌 검사 때문에 이것들이 prunable 이 되어도 SC-6 은 영향받지 않는다.
3. **판정 기준을 먼저 초록으로** — 60초 리허설 재실행: **`all_pass: true`** · SC-1~5 pass ·
   **SC-6 pass**(`orphan_worktrees: 0` · rss_growth 21.2 · fd_growth 0 · errors 0).
4. **8시간 soak 시작 → 19분 51초 뒤 의도적 중단**(오너 판정) — `screen -dmS nx10soak … run_nx10_soak.sh`,
   시작 `2026-09-16T07:21:51Z`, HEAD `20d529fc`, 시작 지문 `c65fe0e1…`, 작업 디렉터리 `/tmp/nx10-soak-work-…`
   (공유 체크아웃을 더럽히지 않는다). 중단 사유·방법·경과는 `soak-exit.txt` 에 **러너 줄과 구분해서** 기록했다
   (러너 자신이 `exit: 143` 을 쓴다 — 래퍼 exit 를 잃지 않는다).

### 중단 결정의 근거 (그대로 남긴다)

soak 을 계속 두면 **손해만 커지는 구조**였다:

- 후보 코드를 더 고칠 항목이 남아 있다(SSE 실연결 폐기·journal quota/retention·tombstone GC). 하나라도
  손대면 종료 지문이 `c65fe0e1…` 과 달라져 **카드의 “시작/종료 지문 동일”을 만족하지 못한다** — 8시간을
  써도 판정 근거가 되지 않는다(지문이 다른 후보의 green 을 합산하지 않는 규칙과 같다).
- 러너는 **종료 시점에만** 리포트를 쓰므로 중단 시점에 남는 부분 산출물이 없다(`soak-28800.json` 없음).
  즉 유지해도 기대값이 0 이었다.
- 99.4% CPU 를 계속 점유해, 코드 배치에서 필요한 전량 스위트(10분)·E2E·번들 빌드와 경합한다.
- 반대로 **문서 작업은 soak 과 완벽히 병행된다**(지문 제외 대상). 그래서 문서·결정 배치를 “지금”이 아니라
  **최종 soak 창**으로 옮겼다 — 8시간은 한 번만 쓴다.

중단은 실패가 아니라 **순서 수정**이고, 유효한 기준선은 그대로 남았다: `soak-60.json`(60초 리허설,
`all_pass: true`).

### 그 뒤: 동결 배치 실행 + 새 지문 (2026-09-16)

중단 사유였던 3건을 한 배치로 끝냈다(상세·명령·검증표: [BATCH_FREEZE.md](BATCH_FREEZE.md)):
NX-05 SSE 실연결 폐기 · NX-02 journal retention 기본값 · NX-03 tombstone GC 정책.
따라서 **`c65fe0e1…` 는 최종 후보가 아니고, 그 지문의 값은 새 지문으로 이월되지 않는다.**

* 새 지문: **`157311cf106f6e1de937331d332c9dcf947ee826c28c856cfdaccead0ddad8ce`** (HEAD `20d529fc`, dirty)
* 새 지문에서 재측정: 정적 4개 green · 전량 스위트 `4 failed, 6587 passed, 14 skipped`(실패 4건은
  타 레인 귀속) · 벤치 16 passed · 대시보드 888 passed · 재빌드 후에도 지문 동일(번들과 소스 일치)
* 아직 안 잰 것: SC-1~6 28,800s soak · 나머지 required 게이트 전수 · `clean-machine-runtime`(커밋 후)
  · `ga_gate_verify` · attempt-close

`soak` 일정(2026-09-16 오너 지시: **오늘 22:00 KST**):

* `screen -dmS nx10soak bash docs/qa/2026-09-16-followup/nx10/schedule_nx10_soak.sh`
  — 목표 `2026-09-16T13:00:00Z`(=22:00 KST), 기대 지문 `157311cf…`, 종료 예정 `~06:00 KST`.
* 시작 직전 지문 불일치면 **8시간을 쓰지 않고 중단**(`aborted_reason: fingerprint drift`, exit 2).
* 기록: `soak-schedule.txt`(예약 시각·pid·지문) · `soak-schedule.log`(15분 heartbeat) ·
  `soak-exit.txt`(시작/종료 지문·exit — 1·2차 중단도 여기에 운영자 기록으로 남겼다).
* 대기·실행 중에는 `caffeinate -i` 로 idle sleep 을 막는다(`NX10_NO_CAFFEINATE=1` 로 끌 수 있다).
  기계가 자거나 재시작되어 screen 세션이 죽으면, 다시 깨어난 시점에 같은 명령으로 재예약한다 —
  목표 시각이 이미 지났다면 즉시 시작한다(늦게라도 돌리도록 설계했다).


`soak-exit.txt` 를 보면 이 장치가 실제로 작동한다: 수정 전 리허설(`exit: 1`)의 시작·종료 지문은
`da54e07b…`, 수정 후 리허설(`exit: 0`)은 `c65fe0e1…` 로 **따로 기록**된다 — NX-00 이 겪은
“어느 트리의 결과인지 모른다”(`run_sha_binding: UNVERIFIED`)를 반복하지 않는다.

### 지문 이동의 대가 (숨기지 않는다)

하네스 수정은 **제품 코드가 아니지만** 후보 지문 대상 파일(`scripts/`)이다. 따라사:

- `da54e07b…` 에서의 21 green 은 **그 지문의 값**으로만 유효하다(참고값).
- `c65fe0e1…` 에서 재측정한 것은 **정적 4개**(ruff·format·mypy·basedpyright)와 관련 시험
  `test_val02_conversation_multiprocess.py`(14 passed), SC-1~6 리허설이다.
- 나머지 게이트(특히 E2E·대시보드·전량 스위트)는 **soak 종료 후** 재실행한다 — soak 이 CPU 를
  占유한 상태에서 latency·RSS 관련 측정을 같이 하면 서로를 오염시킨다.

## 12. 동결 트리 단일 창 재측정 (attempt freeze002, 2026-09-16)

배치(NX-05 SSE 폐기 · NX-02 retention · NX-03 tombstone GC)로 지문이 `157311cf106f6e1de937331d332c9dcf947ee826c28c856cfdaccead0ddad8ce`
로 이동했으므로, **그 지문에서** required 22개를 한 창에서 다시 쟀다(`clean-machine-runtime` 는 커밋을
전제하므로 제외 — 제외 사실은 마감 도구 출력에 그대로 드러난다).

| 항목 | 값 |
|---|---|
| 러너 | `run_freeze_gates.sh` (`screen nx10freeze`) |
| 창 | `2026-09-16T08:27:10Z` → `08:45:49Z` (18분 39초) |
| 리포트 | `gate-report-freeze002.json` (attempt 017) |
| 결과 | **21 passed · 1 failed · 0 not_run** (22개 중) |
| 실패 | `python-tests` — `4 failed, 6587 passed, 14 skipped, 16 deselected` (633.8s). 실패 4건은 **여전히 동일한 타 레인 귀속**: `test_cr14_fence_movement_detection.py` 2건(`test_no_code_scope_commit_after_the_declared_candidate`·`test_declared_fingerprint_is_the_fingerprint_of_head_within_the_fence`) + `test_nx07_doc_consistency.py` 2건(`test_soak_phases_stay_separated`·`test_teeth_soak_done_promotion_is_detected`) — **배치가 만든 실패 0** |
| 지문 | **시작 = 종료 = `157311cf…`**(러너가 `freeze-runner-exit.txt` 에 전후를 기록) → 22:00 예약 soak 의 기대 지문이 그대로 유효하다 |
| 마감 도구 | `ga_gate_verify` verdict **FAIL**, 문제 **정확히 2개**: `missing_required: clean-machine-runtime` · `required_red: python-tests`(`gate_verify-freeze002.txt`) |

이번 재측정으로 **"지문 이동 때문에 다시 재야 한다"가 실제로 완료됐다**: 이전 attempt(004~016)의
21 green 은 배치 이전 트리의 값이었고, 이제 `157311cf…` 의 값이 있다. 게이트별 소요도 대체로 재현됐다
(`docker-build` 234.6s vs 232.4s, `dashboard-e2e-ambient` 46.4s vs 46.6s, `dashboard-e2e-witnesses` 45.7s vs 45.2s).

문서 편집이 이 카드의 다른 계약을 깨지 않았는지도 같은 창에서 확인했다: `tests/test_nx07_doc_consistency.py`
재실행 → **2 failed, 24 passed** 로 실패 집합·사유가 동일(EX-05 상태 셀 문구) — 내 `docs/` 편집이
문서 정합성 실패를 **새로 만들지도, 가리지도 않았다**.

### 이 attempt 이후 남은 required 작업은 정확히 두 개

1. `clean-machine-runtime` — `--ref HEAD` 를 export 하므로 **커밋 뒤 재실행**해야 후보 값이 된다(커밋은 사용자 승인).
2. `python-tests` 의 빨간 4건 — 오너(EX-05 승격 판정)와 CR-14 레인(울타리 재선언)의 정리.

둘 다 **이 창이 코드로 해결할 수 없는 것**이고, 하나는 사람의 결정이다. 8시간 soak 은 동결 트리에서
22:00 KST 예약 실행 대기 중이며, 그 결과가 도착하면 이 대장에 회수 행을 추가한다.

## 13. 보조도구 승격 + 그 지문에서의 재측정 (attempt promote001/002, 2026-09-16)

오너 판정 **B** 로 보조도구 3종 + 계약 시험 3종을 `docs/` → `scripts/`·`tests/` 로 옮겼다(계획·이동표·실행 기록:
[PROMOTION_PLAN.md](./PROMOTION_PLAN.md)). 이 이동은 **코드지문을 옮긴다**(둘 다 `tree_digests` 범위다).

| attempt | 트리 | 게이트 | 지문 before→after | 판정 도구 |
| --- | --- | --- | --- | --- |
| freeze002(이전) | 동결 배치, 승격 전 | 22개 중 **21 passed · 1 failed** | `157311cf…` 동일 | 문제 2개(아래와 같음) |
| promote001 | 승격 직후 | 22개 중 21 passed · 1 failed | `ab980ba5…` → `0f345d0c…` **갈림** | — |
| promote002 | 승격 + 창의 편집 반영 | 22개 중 **21 passed · 1 failed** | `0f345d0c…` **동일** | `missing_required: clean-machine-runtime` · `required_red: python-tests` |

**실패 1개와 판정 도구의 문제 2개는 옛 지문과 같다** — 승격이 만든 새 실패는 0건이다. 실패는 여전히
`python-tests` 안의 타 레인 4건(EX-05 승격 2 · CR-14 울타리 2)이다.

**promote001 이 갈린 이유는 게이트가 아니라 사람이다**: 측정 중(09:52Z) 이 창이 `scripts/verify_docs_commands.py` 를
고쳤다. 게이트가 지문을 흔드는지 먼저 의심했는데, 지문 범위 파일을 mtime 으로 세워 보니 (a) `dashboard-build`·
`sbom-generate` 는 추적 중인 번들·SBOM 을 재작성해도 지문을 흔들지 않았고(동결 러너와 같은 관찰),
(b) 최근에 쓰인 파일은 이 창이 편집한 스크립트였다. 그래서 무편집 구간에서 promote002 를 돌렸다.

**예약과의 순서도 이 대장에 남긴다**: 예약을 먼저 걸고(09:47Z) 측정을 나중에 했더니(22:00 에 쓰일
기대 지문 ≠ 측정 종료 지문) 재장전이 필요해졌다 — 지금 예약은 **마지막 측정 뒤**에 걸었고
(`10:26Z`, `soak-schedule.txt`), 그 뒤 이 창은 `docs/` 만 수정한다. 이 두 규칙은 절차 문서에도 적었다
([CLOSURE_RUNBOOK.md](./CLOSURE_RUNBOOK.md) §5b).

## 14. 커밋 3분할 + 커밋된 후보에서 필수 23개 완주 (attempt promote003, 2026-09-16)

오너 지시로 이 창의 변경을 3분할로 커밋했다(경로 명시 스테이징, `git add -A` 0회, 훅 우회 0회):
`d929da01`(후보 코드+계약+승격 도구+`.gitignore`) · `6417690e`(대시보드 소스·번들·SBOM) · `89dd383b`(증거·문서).
`vault_data`(gitlink, 소유 불명)는 **의도적으로 미커밋**으로 남겼고, 1MB 초과 게이트 리포트 4개는
`check-added-large-files` 정책을 우회하지 않고 [`large-evidence-manifest.md`](./large-evidence-manifest.md) 에
sha256 으로 식별해 두었다.

**커밋이 지문을 옮겼다**(`0f345d0c…` → `92fcaeb5…`): 내용이 아니라 **맵에서 사라진 항목** 때문이다 —
추적 중이지만 삭제된 옛 번들 30개는 맵에 `MISSING_CONTENT` 로 있었고, 그 삭제가 인덱스에 반영되면서 항목이
없어졌다. 그래서 “커밋은 지문을 안 바꿔진다”는 종전 문장(§12 문맥)을 실측으로 정정했다.

그 지문에서 필수 **23개를 한 창에서 완주**했다(`gate-report-promote003.json`, 시작 = 종료 = `92fcaeb5…`,
15분 46초): **22 passed · 1 failed · 0 not_run**. 여기서 `clean-machine-runtime` 이 처음 후보 값이 된다
(**passed, 43.7s**) — 그 게이트는 `--ref HEAD` 를 export 하므로 **커밋을 요구**했고, 그동안
`missing_required` 의 유일한 항목이었다. 결과적으로 마감 도구(`ga_gate_verify`)가 지적하는 문제는
**정확히 하나로 줄었다**: `required_red: python-tests`(타 레인 4건 — EX-05 승격 2 · CR-14 울타리 2).

| attempt | HEAD | 게이트 | 지문 before→after | 판정 도구 문제 |
| --- | --- | --- | --- | --- |
| promote002 | `20d529fc`(미커밋 트리) | 22개 중 21/1 | `0f345d0c…` 동일 | `missing_required: clean-machine-runtime` + `required_red: python-tests` |
| **promote003** | **`89dd383b`(커밋된 후보)** | **23개 중 22/1** | **`92fcaeb5…` 동일** | **`required_red: python-tests` 하나** |
| **promote004** | **`1bd95e7d`(커밋된 후보)** | **23개 중 22/1** | **`322b4d3b…` 동일** | **`required_red: python-tests` 하나(같음)** |

## 15. 회수 판정기의 기대 지문 결함 수정 + 재측정·재장전 (attempt promote004, 2026-09-16)

**왜 코드를 또 고쳤는가.** 예약 통제 도구를 붙이다가 회수 판정기(`scripts/collect_soak_result.py`)의
`expected_fingerprint()` 가 `soak-schedule.txt` 에서 `re.search`(= **첫 매치**)를 쓴다는 것을 찾았다.
그 파일은 예약할 때마다 블록을 **덧붙이므로**, 이 창의 재장전 뒤에는 기대값이 **철 지난 예약의 지문**
(`157311cf…`, 08:20Z)으로 잡혔다. 그대로 두면 **밤새 정상으로 끝난 8시간 실행이 ③(기대 == 시작)에서
거짓 FAIL** 로 판정된다 — 이 카드가 반복해서 겪은 “지표는 PASS 인데 귀속이 어긋나 판정 근거가 사라짐”
(EX-05)을 사람 손으로 다시 만드는 일이고, 그 8시간을 그대로 버리게 된다.

**고침**: 마지막 예약을 쓴다(`latest_expected_fingerprint`) + 판정 출력에 **어느 예약을 썼는지**(이력
몇 건 중 마지막인지)를 문장으로 남긴다 + 사람이 주는 `--expected-fingerprint` 우회로는 그대로 둔다.
이빨: 계약 시험 1건(`tests/test_soak_recovery_judge.py`, 승격 위치에서도 돈다) + 자기시험 3건
(이력 3건 → 마지막 · 이력 없음 → `UNVERIFIED` · `previous_expected_fingerprint:` 는 기대값이 아님).
판정기 자기시험은 **9/9**(종전 6/6). 커밋 `1bd95e7d`(코드 2파일만).

**실측 확인**: 수정 전 실행 — `기대=157311cf…` / 수정 뒤 — `기대=92fcaeb5… (예약 이력 5건 중 마지막)`.

**재측정**: 판정기가 `scripts/`(= 지문 범위)라 지문이 `92fcaeb5…` → `322b4d3b…` 로 옮겼고, 작업 트리
지문 = HEAD 트리 지문(`tree_fingerprint_of_commit`)을 **실측으로 확인**한 뒤 필수 23개를 한 번에
돌렸다(`NX10_INCLUDE_CLEAN_MACHINE=1`, `12:47:04Z`→`12:02:52Z` = 15분 48초, 시작 = 종료 =
`322b4d3b…`): **22 passed · 1 failed · 0 not_run**. 실패는 `python-tests` 의 타 레인 4건 뿐이고,
판정 도구 문제도 **`required_red: python-tests` 하나**로 promote003 과 동일하다(새 실패 0건).

**재장전**: 옛 예약(기대 `92fcaeb5…`)은 `soak_control.sh cancel` 로 내렸고 — 출력은
`[OK] 죽음 확인` · `검증: 살아 있는 예약 0건` — 새 지문으로 `arm` 했다(`12:04:19Z`, 단일 예약,
`status` exit 0).

**그리고 22:00 을 기다리지 않고 시작했다**(오너 지시, `12:13:12Z` = 21:13 KST): 그 예약도 `cancel` 로
검증 종료한 뒤 `soak_control.sh run` — 발화 전 preflight(즉시 시작 모드 5/5 OK: 현재 트리 == HEAD 트리 ·
인터프리터 · 러너 자산 · `/tmp` 여유 · 도는 soak 없음)를 통과했고, 예약과 **같은 포장**(screen +
`caffeinate -i`)으로 러너를 띄웠다(수동 타이핑 0줄). 러너가 적은 `start_head fd16368c…` ·
`start_fingerprint 322b4d3b…` · 종료 예정 `20:13Z` = 05:13 KST. 작업디렉터리
`/tmp/nx10-soak-work-20260916T121312Z` · 실행 잠금 pid 89463. 기록: `soak-exit.txt`(취소·사고)·`soak-schedule.txt`(새 기대 지문·대기)·
[SOAK_SCHEDULING.md](./SOAK_SCHEDULING.md)(사고·도구·자기시험).

예약 soak 은 이 지문으로 재장전했다(`soak-schedule.txt`, `10:47:15Z`, 대기 7,964초). 이 창은 이제
**`docs/` 만** 수정한다 — 그 이유도 이 창에서 실측됐다: 문서 편집은 지문 이동을 일으키지 않았다
(문서 발행 중 지문 재계산 → 동일).

## 11. 판정 (카드 §판정)

- 이 attempt 는 **GO 가 아니다**. required 상태가 **22 passed · 1 failed · 0 not_run** 이고(카드 §수용은
  실패 0 **그리고** not_run 0), 카드 §선행의 “NX-00~09 완료 또는 **명시적으로 허용된** 비차단 조건”도
  아직 비어 있다(§3 전제조건 대장 = `SCOPE.md`, 허용 기록 **없음**).
- **실패 1개의 귀속이 이 카드의 변경이 아니라도 면제되지 않는다** — 카드는 원인별 면제를 주지 않는다.
  정리 주체는 오너(EX-05 승격 브리프)와 CR-14 레인(울타리 재선언)이다.
- 이 attempt 가 실제로 만든 것은 **후보 고정 기계장치 + 23개 required 전수 실행(22 green) + 실패 1개의 증거 있는 귀속**
  이다. `not_run` 이 0이 된 것은 SCOPE 의 분류 오류를 실행으로 바로잡은 결과다(§2).
- 지문이 다른 attempt 는 합산하지 않았고, 실패한 attempt(001~003, 006, 012)도 **지우지 않고**
  그대로 남겼다.

## 17. 꼬리 창 수정 뒤 필수 23개 재측정 (attempt tailfix001, 2026-09-16)

**회수 → 수정 → 계약 시험 → 커밋 → 재측정** 순서를 끝까지 돌린 attempt 다.
명령: `NX10_GATE_ATTEMPT=tailfix001 NX10_INCLUDE_CLEAN_MACHINE=1 bash run_promote_gates.sh`(22:52:51Z → 23:12:20Z).

| 항목 | 값 |
|---|---|
| 커밋 | `7d8c25b5`(tail 창 수정 + 계약 시험 2건) · `099cfc8b`(문서 10파일) · HEAD `099cfc8b` |
| 지문 | **시작 = 종료 = `98855031…` = HEAD 트리 지문**(측정 중 코드 무편집) |
| 게이트 | **23개 전수: 22 passed · 1 failed · 0 not_run** — `clean-machine-runtime` **passed(43.0s)**, 이번에는 후보 값이다 |
| 마감 도구 | `ga_gate_verify` FAIL — 문제는 **정확히 하나** `required_red: python-tests`(`gate_verify-tailfix001.txt`) |
| `python-tests` | `5 failed, 6621 passed, 13 skipped, 16 deselected, 20 xfailed`(635.6s) |
| 실패 목록 | **promote004 와 시험 단위로 동일**(CR-14 울타리 3 · NX-07 문서 정합성 2) → **이 수정이 만든 새 실패 0건** |

### 17-1. 종전 수치 하나를 정정한다 (오기)

종전 기록 여러 곳이 이 실패를 **“타 레인 4건(EX-05 2 · CR-14 울타리 2)”** 로 적었다. 실물 리포트를
다시 열어보니 **틀렸다**: `promote004` 와 `tailfix001` 둘 다 **5건**이고, 내역은
**CR-14 울타리 3건** + **NX-07 문서 정합성 2건** 이다.

- “EX-05 2건”으로 부른 두 건은 사실 `tests/test_nx07_doc_consistency.py` 의 테스트다 — 그 내용이
  EX-05 대장 행을 보므로 그렇게 불렸지만, **파일 이름과 소유 레인이 다르다**(문서 정합성 계약).
- 세 번째 CR-14 건은 `test_worktree_matches_the_declared_fingerprint_when_the_code_scope_is_settled` 다.
  이 attempt 에서도 빨간색이지만, **promote004 에서도 이미 빨간색**이었다 — 내 수정이 만든 것이 아니다.

이 정정은 §12·§14·§15 의 결론을 바꾸지 않는다(게이트 수 22/1/0 · 마감 도구 지적 1개는 그대로 참이다).
바뀌는 것은 **빨간 5건의 귀속 문장**이다.

### 17-3. 수정 뒤 8시간 재실행 — 시작 (2026-09-17)

게이트 재측정이 끝난 같은 지문에서 8시간을 다시 시작했다. 순서는 **수정 → 계약 시험 → 커밋 →
게이트 23개 재측정 → 8시간 soak** 이다(앞의 세 단계를 다 통과한 뒤에만 밤을 태운다).

| | |
|---|---|
| 시작 / 종료 예정 | `2026-09-16T23:26:23Z` → `2026-09-17T07:26:23Z` (08:26 → 16:26 KST) |
| 시작 지문 | `98855031…` = 현재 트리 = HEAD 트리(커밋된 후보 `7691ccc5`) |
| 작업디렉터리 | `/tmp/nx10-soak-work-20260916T232623Z` |
| preflight | **6/6 OK**(즉시 시작 모드) — **처리량 하한 443 ops/s**(기준 133/s · 8시간 외삽 ≈12.8M ops) |
| 보존 | 직전 FAIL 리포트를 `soak-28800-fail001.json` 으로 사본(새 실행이 `soak-28800.json` 을 쓴다) |

**preflight 에 처리량 하한을 추가한 이유는 이 대장의 §16-1 이다**: 직전 실행은 60초에 2,978 ops
(49.6 ops/s)를 내고도 preflight 10개를 전부 통과해서 8시간을 태웠다. 이제 그 문이 있다(도구·자기시험
43/43·두 함정 기록: [SOAK_SCHEDULING.md](./SOAK_SCHEDULING.md) §3b).

### 17-2. 판정 (attempt tailfix001)

**여전히 NO-GO.** ① required red 1(`python-tests`)은 타 레인/오너의 일이고, ③ CR-14 울타리 3건은
**후보 재선언 전까지 설계상 빨간색**이며(선언 후보 뒤에 코드 스코프 커밋이 있다), ④ owner 허용 기록이 없다.
수정이 닫은 것은 **원인 하나(SC-6 RSS 의 원인)** 이고, 그것도 8시간 재실행으로 확인해야 한다.
**“22 passed”를 GO 로 확대 해석하지 않는다** — 이 카드가 시종일관 지켜온 규칙이다.

## 16. 8시간 soak 회수 판정 — SC-6 RSS FAIL, 원인은 측정됨 (2026-09-16 실행 / 09-17 회수)

**회수 행.** 명령: `PYTHONPATH=src .venv/bin/python scripts/collect_soak_result.py` (2026-09-16T22:09:18Z).
기록: `soak-recovery-20260916T121312Z.json` · `soak-recovery-latest.json` · `soak-recovery.log`.

| 항목 | 값 |
|---|---|
| 실행 | `12:13:12Z` → `20:13:16Z` · `duration_s 28800.075`(요청 28800, 100.0%) · **exit 1** |
| 귀속 | start = end = 기대 = 지금 트리 = `322b4d3b…` (측정 후 코드 무변경) |
| 리포트 | `soak-28800.json` (40,524 B) · 작업디렉터리 `/tmp/nx10-soak-work-20260916T121312Z` |
| SC-1~5 | 전부 pass |
| SC-6 | `completed_ops 70,430` · append/revision 일치 · view 19 ≤ soft max 64 · `errors 0` · `fd_growth 0` · `orphan_worktrees 0` · 원본 70,431 **전수 확인** · **`rss_growth_mb 1683.5` (기준 64) → FAIL** |
| 판정 | **FAIL** — 미충족 ① 지표(`all_pass False`) · ② 실행(`exit 1`). 둘 다 같은 원인 하나 |

**원인(측정, 추측 아님).** `ConversationStore.append()` 1회 = `journal.tail()` **3회**, 그리고 `tail()` 은
마지막 줄만 필요한데 **journal 전체를 읽고 모든 줄을 `json.loads` + `JournalEvent.from_dict`** 한다
(자기 docstring 은 "without replaying the whole file" — 구현이 반대다). 실물 8h journal(24.4 MB / 70,431줄)에서:
`tail()` 265~271 ms · append 1회 814~830 ms 중 **`tail()` 누적 810 ms = 99.5%** · 같은 저장소의 `_refresh_latest`(view 캐시)는 0 ms.
비용이 journal 크기에 비례하므로 실행 전체가 제곱이 되고(`70,430 × 3 × 평균 12.2 MB ≈ 2.6 TB`), 평균 0.41초 × 70,430 = **8시간 벽시계의 전부**다.
RSS 는 **객체 누수가 아니다**: 60초 프로브에서 살아 있는 객체 수 평탄(±25), 8h append 1회의 일시 할당 peak 52 MB,
live object 델타 −292 — 매 호출의 대량 일시 할당이 남긴 high-water 다. 상세: [SOAK_8H_FINDINGS.md](./SOAK_8H_FINDINGS.md).

**부수 정정 2건.** ① NX-04 의 `stream_line_count` 경로는 이번에도 타지 않았다 — 8h journal 24.4 MB 가
`ORIGINALS_REPLAY_MAX_BYTES` 32 MiB **미달**이라 `full_replay` 분기를 탔다(코드 주석의 "8h, 수 GB" 가정이 반증됨).
② `soak_control.sh preflight` 10항목은 예약·지문·여유공간을 보지만 **처리량 하한**을 보지 않는다 — 시작 5분
시점에 이미 정상의 1% 였고, 그때 알았다면 8시간을 태우지 않았다(다음 회차에 항목 추가).

**이 행은 어떤 green 도 만들지 않는다.** required 23개 중 `python-tests`(타 레인 4건)는 그대로 red 이고,
SC-6 도 FAIL 이다. 수정 → 재측정 순서는 문서 §6.

### 16-1. 같은 날 결함 수정 + 측정 (기록)

| 단계 | 결과 |
|---|---|
| 수정 | `ConversationJournal.tail()` 이 꼬리 창(64 KiB)만 읽는다. 창으로 판정 못 하는 파일만 종전 전체 스캔 폴백. 관대한 파싱·`truncated_tail` 의미 불변 |
| 계약 시험 2건 | `tests/test_nx02_history_journal.py` — 창 경계(전체 읽기 금지) · 전체 스캔 동등성(7가지 파일 모양 + 창보다 긴 줄). **수정 전 구현을 주입하면 첫 시험이 실제로 빨개진다**(1 failed) |
| 실물 8h journal | `tail()` 265~271 ms → **0.04 ms** · `append()` 814~830 ms → **0.5~0.8 ms** · append 3회 `maxrss` 133 → **60.9 MB** |
| 60초 리허설 | ops 2,978 → **29,180**(journal 10배) · `rss_growth` 21.2 → **16.8 MB** · pass 유지 |
| 10분 (600초) | ops **269,087**(448.5 ops/s) · journal 94.1 MB · `rss_growth` **32.2 MB** · pass · RSS 기울기 평탄부 **0.004 KB/op** → 8h 외삽 **+48 MB < 64** |
| 부수 | **NX-04 `stream_line_count` 첫 실행**(94.1 MB > 32 MiB): `journal_lines=269,088` · `terminated=True` · `originals_complete=True` |

| 회귀 확인 | 전체 스위트 `5 failed, 6640 passed, 10 skipped, 20 xfailed`(10분 31초). 5건 중 **이 수정의 것 0건**: ① benchmark latency(기능 게이트는 `-m "not benchmark"` 로 제외 — 단독 실행 2.65s pass) ② CR-14 울타리 2건(코드 스코프 이동 = 설계된 빨간색) ③ NX-07 문서 일관성 2건(**HEAD 내용으로도 같은 위반** — `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 의 EX-05 행이 `PASS` 한 단어인데 그 실행의 귀속은 UNVERIFIED). 대화 저장소 계약 79건 전부 통과 · 문서 검사기 ALL OK(링크 134) |

상세와 한계(무엇을 주장하지 않는가): [SOAK_8H_FINDINGS.md](./SOAK_8H_FINDINGS.md) §5c·§5d·§7.
이 수정은 지문을 움직인다 — 커밋 뒤 **작업 트리 지문 = HEAD 트리 지문 = `98855031…`**
(코드 `7d8c25b5` · 문서 `099cfc8b`; 시작 지문 `322b4d3b…` 와 다름). 게이트 23개는 이 지문에서
재측정했고(`tailfix001`), 8시간 soak 재실행은 그 뒤다.
**교차 레인 항목**: EX-05 대장 행의 두 단계 분리(위 표 ③)는 CR-14 레인/오너의 일이다 — 이 카드가
그 문서의 문장을 바꾸지 않는다(§6 의 경계와 같다).

## 18. 통제 도구가 **돌고 있는 soak 을 오탐**하던 결함 (2026-09-17, soak 실행 중 발견)

8시간 재실행(§17-3)이 도는 중에 `soak_control.sh` 를 돌렸더니 **정상 실행을 문제로 보고**했다.
둘 다 도구·시험 쪽 결함이고, soak 기록에는 영향이 없다(수정 전후 트리 지문 `98855031…` 동일).

| # | 결함 | 실측 | 수정 |
|---|---|---|---|
| ① | `status` 가 **예약과 실행을 구분하지 않았다** — `run`(즉시 시작)은 예약 잠금이 없으므로 `armed` 요구 판정이 상시 거짓 경보 | `2026-09-16T23:28Z`: 실행 중인데 `판정: ATTENTION` | 모드를 먼저 가름. 실행 중이면 **시작 지문 == 현재 트리**를 판정하고 경과·남은 초·종료 예정을 함께 표시(`RUNNING`, exit 0) |
| ② | 자기시험이 **환경에 결합** — preflight 의 “다른 soak 실행 없음” 이 `val02_staging.py` 를 기계 전체에서 찾는데(판단은 옳다), 그 이름을 시험이 통제하지 않아 **진짜 soak 이 도는 동안 픽스처가 전부 실패** | `47/50 passed` — 실패 3건이 모두 이 하나(preflight 2 · `run` 거부 사유 1) | 하네스 이름을 `NX10_SOAK_PROC_PATTERN` 으로 분리(시험이 통제), “돌고 있는 soak 을 pid 로 지목하는가”를 결정적으로 고정 |
| ③ | 새 픽스처가 공용 변수 `$d` 를 바꿔 **뒤 픽스처의 전제를 깨뜨림** | 유일한 잔여 실패 = 처리량 픽스처가 “스케줄러 자산 없음” | 픽스처별 지역 변수로 분리(시험끼리 상태를 공유하지 않는다) |

**자기시험: 47/50 → 52/52** — 그리고 이제 **진짜 soak 이 도는 중에도** 통과한다(그것이 이 수정의 요점이다:
시험을 돌리려고 8시간을 멈출 필요가 없다). 관련 문서: [SOAK_SCHEDULING.md](./SOAK_SCHEDULING.md) §3d.

오너/타 레인에 남기는 요청 4건(CR-14 후보 재선언 · EX-05 대장 행 두 단계 분리 · 독립 검토자 · 위생 결정 2건)은
한 장으로 정리했다: [OWNER_REQUEST_TAILFIX.md](./OWNER_REQUEST_TAILFIX.md).

## 19. 수정이 만든 새 상한 — 쓰기량이 기본 hard cap 을 넘었다 (2026-09-17, 회수 도구·preflight 확장)

§17-3 의 8시간 재실행을 **48분에 중단**하고 같은 지문에서 다시 시작했다. 중단은 실패가 아니라
**도구가 잡은 다섯 번째 종류의 사각지대** 때문이다(§16 의 처리량·§18 의 오탐과 같은 가족).

| | |
|---|---|
| 1차 실행 | `2026-09-16T23:26:23Z` → 중단 `09-17T00:13:54Z`(48분) · 러너 `exit: 143` · `end_fingerprint` = `start_fingerprint` = `98855031…`(트리는 안 흔들렸다) |
| 발견 | journal 이 47분에 **452 MiB**(159 KB/s) — 기본 hard cap **512 MiB** 까지 **8분**. 중단 시점 439 MiB |
| 왜 결함인가 | ADR-DAT-02 는 자동 prune 없는 **쓰기 거절**(507)이다. 하네스는 그 예외를 `errors += 1` 로 세고 SC-6 `pass` 에 `errors == 0` 이 있다 → 8시간이 **제품 결함이 아닌 설정 때문에 거짓 FAIL**. 직전 FAIL 실행의 8h journal 은 24.4 MB 라 이 벽을 못 봤다(수정으로 20배 빨라져서 생겼다) |
| 2차 실행 | `2026-09-17T00:15:16Z` → **`00:22:48Z` 중단**(`exit: 143`) · `retention_caps: soft=64MiB hard=8192MiB`(러너가 기록에 남긴다) · preflight **6/6 OK**(처리량 437 ops/s · **쓰기량 투영 4,050 MiB < cap 8,192 MiB**) · 시작 지문 = 당시 트리 = HEAD(`aa1ead1f`). 중단 이유는 §20(SC-3 경합 + 하네스 무한 대기) |

**도구에 넣은 문 2개**

| 문 | 무엇을 막는가 | 자기시험 |
|---|---|---|
| `preflight` 의 **쓰기량 투영** | “빠르게 도는가”만 묻고 “그 속도로 쓰면 어디서 멈추는가”를 묻지 않던 사각지대. 프루브 journal 바이트를 8시간으로 외삽해 cap 의 90% 미만을 요구(넘침이면 빨개지고 **왜 빨간지**(507 → 거짓 FAIL)를 함께 출력) | 캡 1 MiB → FAIL 지목 · 캡 8192 MiB → OK(투영·캡을 숫자로) — **70/70** |
| `harvest`(회수 대기·판정) | “끝난 뒤에만 판정이 성립한다”를 사람의 시각에 묶지 않는다. 러너는 종료 시에만 `end_*`·`exit` 를 쓰므로, 도는 중 판정은 **옛 블록**을 읽는다 → `--no-wait` 는 `exit 4` 로 거부 | 거부(exit 4·사유 문장·판정기 미실행) · 대기 뒤 판정(판정기 exit 전달) · 완성 블록 없음(exit 3) · 기다린 사실 기록 |

판정기 `exit` 는 harvest 가 **그대로** 전한다(0=PASS). 판정 출력은 `soak-harvest-<UTC>.txt` 로도 남고,
대장 반영은 사람이 한다(자동화한 것은 “빠뜨리지 않는 일”이지 “읽지 않아도 되는 일”이 아니다).
관련 문서: [SOAK_SCHEDULING.md](./SOAK_SCHEDULING.md) §3e · [CLOSURE_RUNBOOK.md](./CLOSURE_RUNBOOK.md) §0a.

**이번 창의 변경 경로**(전부 `docs/` — 지문 제외 경로라 실행 중에도 안전):
`soak_control.sh`(harvest · 쓰기량 투영 · status 모드 분기) · `run_nx10_soak.sh`(캡 export + 기록)
· 문서 6개. **`src/`·`tests/`·`scripts/` 는 이 8시간 동안 건드리지 않는다.**

## 20. SC-3 경합과 **하네스 무한 대기** — 2차 실행이 7분에 멈췄다 (2026-09-17, 수정 `c522b256`)

§19 의 2차 실행은 시작 13초 뒤 멈췄다: 로그 마지막 줄이 SC-3 worker 의 traceback 이었고, 그 뒤
90초 이상 아무 쓰기 없이 프로세스는 살아서 CPU 0.0% 였다(러너는 종료 시에만 리포트를 쓴다 → 8시간이면 결과 0).

| # | 결함 | 실측 | 고침(계약 시험) |
|---|---|---|---|
| ⑦ | 제품: `ProjectRegistry` 최초 생성이 **공유 lock 밖** + 백업 회전 tmp 이름이 **고정**(`projects.json.bak.tmp`) → 동시 시작 프로세스가 서로의 파일을 옮겨 `RegistrySaveError` | `FileNotFoundError: … projects.json.bak.tmp -> … projects.json.bak` · SC-3 격리 재현 5/5 통과(간헐) · 같은 종류를 대화 저장소에서는 이미 고쳤다(F1) | 생성도 `with self._locked()` 안에서 · tmp 이름 `.{name}.tmp-{pid}` — 시험 3건(lock 을 잡는가 · 이름이 고유한가 · 5-프로세스 동시 생성) |
| ⑧ | 하네스: `q.get()` 무타임아웃(SC-1·SC-2·SC-3 세 곳) → worker 하나가 죽으면 부모가 **영원히** 대기 | 위 실행이 그대로 멈췄다(하루 전 실행은 같은 경합을 안 만나 통과 — 운으로 갈렸다) | `_collect_worker_results`(상한 기본 120초 · `AGK_VAL02_WORKER_TIMEOUT_S`) 가 타임아웃 worker 를 terminate 하고 **오류 1건**으로 세며 계속 · 리포트에 `worker_timeouts` — 시험 2건 |

⑦은 실행을 FAIL 시키는 결함이고 ⑧은 **판정 자체를 없애는** 결함이다(“아무 결과도 없는 결과”는
“다른 이유로 빨간 결과”보다 나쁘다). 둘 다 코드라 지문이 움직인다 → 커밋 `c522b256` 뒤
**필수 23개 재측정(attempt `sc3fix001`, `clean-machine-runtime` 포함)** 을 돌렸다.

### 20-1. 재측정 결과 (attempt `sc3fix001`, 2026-09-17T00:31:15Z → 00:50:17Z)

| 항목 | 값 |
|---|---|
| 결과 | **22 passed · 1 failed · 0 not_run** (`clean-machine-runtime` **passed**) |
| 지문 | 시작 = 종료 = **`5c90b637…`** = HEAD 트리(`c522b256`) — 측정 중 코드 무편집 |
| 실패 1개 | `python-tests` — `5 failed, 6626 passed, 13 skipped, 16 deselected, 20 xfailed`(622초) |
| 실패 5건 | `promote004` 와 **시험 단위로 동일**(CR-14 울타리 3 · NX-07 문서 정합성 2) → **이 수정이 만든 새 실패 0건** |
| 증가분 | 통과 수 **6621 → 6626**(+5) = 이 창이 추가한 계약 시험 5건(registry 3 · 하네스 2) |
| 마감 도구 | `required_red: python-tests` **하나**(`gate_verify-sc3fix001.txt`) |

**로컬 실행과 게이트 실행이 8건 달랐다**(주의할 사실): `.venv/bin/python -m pytest` 로 돌리면
`tests/test_ws01_project_binding.py` 5 · `tests/test_agent_runtime.py` 3 이 **이 기기의 실제 홈 저장소**
(`~/.antigravity/conversations` — v2 이전 레거시 레코드 3건, 이관 표식 없음) 때문에 503 으로 빨개지지만,
게이트(`uv run --isolated --frozen`)에서는 재현되지 않는다. 로컬 8건만 보고 판단했으면 있지도 않은 회귀를
쫓았다 — 확인은 **게이트 리포트의 실패 시험 목록을 직전 attempt 와 시험 단위로 맞대는 것**으로 했다([OWNER_REQUEST_TAILFIX.md](./OWNER_REQUEST_TAILFIX.md) R5).

### 20-2. 도구에 추가한 문(하네스 밖)

| 문 | 무엇을 막는가 | 자기시험 |
|---|---|---|
| `harvest` 의 **무응답 상한**(`NX10_HARVEST_MAX_STALL` 기본 1800초) | 이번 사고의 모양 그대로: 프로세스는 살아 있는데 아무것도 안 쓰는 상태를 "도는 중" 으로 보면 하루치를 기다린다 → 마지막 쓰기(작업디렉터리·로그, 디렉터리 자신의 mtime 포함) 이후 경과로 판단해 `exit 6` 으로 내려온다 | 살아 있지만 안 쓰는 픽스처 → exit 6 · 쓰기가 살아 있는 픽스처 → exit 5(오탐 금지) |
| `NX10_HARVEST_SETTLE`(기본 120초) | 러너가 마지막 필드를 쓰는 중일 수 있으므로 **완성 블록**을 기다리되, 도구 시험은 그것을 짧게 쓸 수 있게 분리 | 완성 블록 없음 → exit 3 |

자기시험: **70 → 75/75 passed**(약 4분).

**교차 레인 기록(내가 고친 파일)**: `src/antigravity_k/engine/project_registry.py` 는 이 카드가 만든 파일이
아니다(WS-01/BR-03 계열 — `tests/test_project_registry_atomic.py` 가 그 계약을 소유한다). 소크 시나리오
SC-3 이 그 코드를 직접 재므로 **고치되 기록을 남긴다**(동작은 안 바뀐다: lock 범위 확대 + tmp 이름 고유화).
판정: 이 수정은 “어제 리허설의 초록”을 다시 쓰지 않는다 — 실패한 실행은 지우지 않고 증거로 남긴다
(두 번의 중단 모두 러너가 `exit: 143` 과 시작·종료 지문을 기록했다).

## 21. 잔여 작업 창 — 낡은 문장 정정 + NX-01 restore 리허설 (2026-09-17, 3차 soak 실행 중)

3차 8시간 soak 이 도는 동안(시작 `01:19:43Z` · 지문 `5c90b637…`) **`docs/` 만** 수정했다
(게이트 제외 프리픽스 `docs/` — 시작 지문이 안 움직인다).

| 무엇 | 결과 | 근거 |
|---|---|---|
| NX-04 “최종 메시지 수 assertion 삭제로 PASS 를 만들지 않음” | **확인 후 종결** — 옛 단언 `final_count >= appended` 는 지워진 게 아니라 **더 강한 쪼개진 단언으로 대체**됐다(`revision == 성공 수` · `view_count <= 64` · **`view_count < 성공 수`** · `original_history` 로 본 원본 수). 파일 재실행 **14 passed**(2.27s) | `tests/test_val02_conversation_multiprocess.py` |
| 상위 상태 문서가 **지나간 실행을 현재로** 적고 있었다 | `docs/20` §3 표·서술과 `docs/19` NX-10 행의 “1차 재실행 = 실행 중” 을 세 실행(48분 중단 · 7분 중단 · 현재)으로 분리하고 사유·커밋·값을 넣었다 | `docs/20` §3 · `docs/19` NX-10 행 |
| NX-04 “`stream_line_count` 실측 규모 미실행” | **실측으로 정정**(10분 실행, journal 94.1 MB > 임계 32 MiB → `stream_line_count`·`replay_deferred=True`·`journal_lines=269,088`). 남은 미검증은 **시간 규모**뿐 — 도는 8시간 soak 의 리포트가 닫는다 | [SOAK_8H_FINDINGS.md §5·§6](SOAK_8H_FINDINGS.md) · [../nx04/handoff.md](../nx04/handoff.md) |
| NX-01 미완 항목 “restore 를 임시 경로에서 실행 + 최신 변경 손실 방지” | **종결(exit 0)** — 왕복 · 최신 변경 손실 방지(대상이 더 새로우면 거절) · 멱등 · 삭제 거절. 이빨: 가드를 끄면 revision 8→5 이며 원문 3건 소실 | [../nx01/restore-rehearsal.md](../nx01/restore-rehearsal.md) · `restore_rehearsal.py` · `restore-rehearsal-output.txt` |
| **발견 `NX03-RESTORE-MARKER`** | 삭제 표식은 `history_state.deleted` 에만 적용되고 원문 읽기 표면은 journal 의 `delete` 이벤트만 본다 → 삭제 전 바이트를 되돌리면 `deleted=true` 인데 원문이 다시 읽힌다(3건). **동결 중이라 코드 미수정**(`src/` 수정은 도는 soak 의 지문을 가른다) — 운영 절차가 거절하고, 수리안은 동결 해제 뒤 | 위 문서 §2 · [../nx03/handoff.md §6-5](../nx03/handoff.md) |
| NX-03 미완 항목 “tombstone 미지원 구버전 rollback, 실리허설 미실시” | **종결(exit 0)** — 구버전 판(`d929da01^`)을 그림자 트리로 돌려 ① 구버전끼리는 되살아난다(표식 0개) ② **현재가 삭제한 뒤에도 구버전은 다시 쓴다**(표식은 살아남음) ③ **복귀하면 현재 코드가 거절한다**(`marker_visible false` · 삭제된 id 대신 **새 id**). 종전 문구 “되돌리면 폐기 토큰이 살아난다” 를 **“위험은 되돌림 창 안에서의 노출”** 로 정정 | [../nx03/handoff.md §5b](../nx03/handoff.md) · `rollback_rehearsal.py` · `rollback-rehearsal-output.txt` |
| **조기 경보 도구 `soak_watch.py`** (새 도구) | 돌고 있는 실행을 **매 표본 읽는다**(읽기 전용·저널을 읽지 않아 측정을 안 건드린다): 살아 있음 · 쓰기 진행 · **journal 증가율 vs 보존 cap 투영** · **RSS 기울기 vs SC-6 기준** · 추정 처리량 vs 하한. 오늘 두 실패가 모두 **끝나야 알 수 있었던** 종류여서 만들었다(1차: 47분에야 cap 초과 투영을 알았다 · 2차: 멈춘 뒤 30분 대기). 자기시험 **3/3**(정상 · 멈춤 → exit 6 · cap 초과 투영 → exit 2) | `soak_watch.py` · [soak-watch-live.txt](soak-watch-live.txt) |
| ↳ **돌고 있는 3차 실행 실측**(2026-09-17T01:41Z, 실행 경과 21분) | 판정 **정상**: journal **290.0 MiB**(증가 ≈230 KiB/s) · 추정 **672 ops/s**(하한 133) · **종료 시 cap 추정 6,396 MiB < 8,192 MiB** · RSS 외삽 **+11~40 MB < 64 MB**. **주목**: preflight 의 사전 투영은 **4,282 MiB** 였는데 실측 추세는 **~6.4 GiB** 로 더 크다 — 여유가 사전 계산보다 **얓다**(둘 다 통과지만 사전 투영이 낙관적이다) | 위 출력 파일 |
| **상시 감시 + 라이브 추세 화면 `soak_watch_loop.py`** | 한 표본씩 묻는 `soak_watch.py` 를 **주기 실행**으로 붙이고(화면 `screen nx10watch`, `caffeinate` 로 잠자기 방지) 표본을 `soak-watch-history.jsonl` 에 쌓아 **자체 완결 HTML**(`soak-watch-live.html`, 서버·외부 자산 0, 인라인 SVG, 30초 자기 새로고침)로 그린다 — **경보 등급 배지 · 배지가 바뀔 때 경고 배너 · journal/RSS/추정 처리량 추세 · 기준 대비 막대(cap·SC-6) · 최근 30표본 표**. 자기시험 **9/9**: 판정이 바뀌면 배지·배너·색이 **실제로 달라지는지**(픽스처 3종)까지 본다. 쓰기 대기 때문에 `-u`(무버퍼)로 띄운다 — 안 그러면 로그가 빈 채로 보인다 | `soak_watch_loop.py` · `soak-watch-live.html` · `soak-watch-history.jsonl` · `soak-watch-loop.log` |
| ↳ 확인 방법 | 이 창에서는 Preview 탭(`register_preview` 가 `soak-watch-live.html` 을 등록) · 터미널에서는 `open`/브라우저로 같은 파일. 표본이 2개 미만이면 그림이 “표본이 아직 부족하다” 로 비어 있고, 2개째부터 선이 그려진다(빈 표본을 0 으로 그리지 않는다) | 위 파일 |
| ↳ **첫 경보가 오탐이었다 — 규칙을 두 번 고쳤다** | 돌린 지 29분에 "RSS 외삼 +305 MB > 기준 64 MB" 가 떴다. 원인은 **순간 기울기로 외삼**한 것 — 실행 초기의 작은 계단(할당·캐시)을 8시간으로 증폭했다. 1차 수정: 누적 평균 기준. 그 뒤에도 +112~126 MB 경보가 남았는데 화면의 RSS 그림이 답을 보여 줬다 — **계단 뒤 평탄**(101.7 → 103.7 MB 후 변화 없음). 2차 수정: ① **워밍업**(실행 25% 전에는 경보하지 않고 “기다린다”를 문장으로 출력) ② **감속 판정**(뒤 구간 상승률이 앞 구간의 절반 미만이면 워밍업). 이빨도 같이 넣었다: 지속 증가는 **경보**(2), 계단 하나·감속은 **정상**(0). 자기시험 `soak_watch` **7/7** · `soak_watch_loop` **9/9** | `soak_watch.py` §외삼 규칙 · 아래 로그 |
| ↳ 교훈 | **거짓 경보는 경보가 아니다** — 상시 거짓 경보는 다음 사람이 그 줄을 안 읽게 만든다(§3d 의 `status` 오탐과 같은 교훈). 임계값을 안 올리고 **판단 근거를 늘리는 쪽**으로 고쳤고, 경보를 끈 것이 아니라 **잘못된 외삼만 보류**했다(지속 증가는 그대로 잡힌다 — ⑤ 이빨) | 위 행 |
| **2차 승격 배치 준비 완료**(계약 시험 2본 + 미러 리허설) | `promote2/` 에 이동표·게이트·리허설·본실행을 만들고 **미러에서 ALL PASS**(본 트리 쓰기 0건): 이동 전 초록 → 이동(바이트 동일) → **승격 위치 14 passed** → 도구 직접 실행 → ruff 초록 → **도구를 치우면 시험이 실패**(이빨) → 스테이징 잔존 0. 본실행 스크립트는 **도는 soak 을 발견하면 거절**한다(실측 확인: `[FAIL] 8시간 soak 이 돌고 있다(pid 56261) — 지문이 갈리므로 거절한다` · 이동 0건) | `promote2/` · [dry-run2-output.txt](promote2/dry-run2-output.txt) · [PROMOTION_PLAN.md §1c](PROMOTION_PLAN.md) |
| ↳ **승격 계약 시험이 내 리허설의 경합을 잡았다** | 계약 시험을 처음 돌렸을 때 14건 중 1건이 간헐 실패했다(3회 중 1회). 원인은 리허설 쪽: `stale_save` 자식이 세션을 **적재하기 전에** `delete` 가 끝나면 그 자식은 이어받을 세션이 없어 **새 세션**을 만들어 “되살아님”을 다른 경로로 재게 된다(`loaded_id != created_id`). 고침: 자식이 적재 뒤 `ready` 신호를 쓰고 부모가 그것을 기다린다. 실측 6/6 · 계약 시험 3회 연속 14 passed | `nx03/rollback_rehearsal.py` · `promote2/test_rollback_rehearsal_contract.py` |
| ↳ 교훈(도구를 만드는 일에도 적용된다) | 사람이 손으로 돌릴 때는 6번 중 1번 실패해도 “그럴 수도 있지”로 넘어간다. **계약 시험으로 옮기려는 순간 그 1번이 드러난다** — `docs/` 안에 두면 영원히 안 드러난다 | 위 행 |
| ↳ 부수 함정 하나 | 미러를 `rsync -a` 로 뜨려다 **복사가 통째로 중단**됐다: 이 기기의 rsync 는 openrsync 2.6.9 이고 작업 트리 안의 비UTF-8 이름에서 `Illegal byte sequence` 로 죽는다. 그래서 미러는 **객체 공유 클론(`git clone -s`) + 이 배치가 건드리는 파일만 `cp -R`** 로 만든다(작업 트리 전체 복사가 필요 없다) | `promote2/dry_run_promotion2.sh` |
| ↳ **승격 위치 확인을 기록으로 고정**(오너 요청 “승격된 위치에서 전부 통과하는지 확인”) | 게이트 `A` 가 `promote2/promoted-contract-tests.txt` 를 매번 다시 쓴다: 시각·루트·HEAD·명령·**승격 위치 두 파일 sha256**·exit·전문(`-v`) · **수집 노드가 `tests/` 인지**. 종전엔 `pytest \| tail` 로 요약만 찍어서 승격 위치 통과가 **16분짜리 리포트 안에만** 있었다 | `promote2/gates2.sh` · [promoted-contract-tests.txt](promote2/promoted-contract-tests.txt) |
| ↳ **새 확인이 첫 실행에서 거짓 FAIL 2건을 냈다** | 작은따옴표로 쓴 정규식에 배열 변수가 확장되지 않았고(`'^${PROMOTED_TESTS[0]}::'`), 요약줄 grep 은 `==== 14 passed in 7.86s ====` 형태를 못 잡았다(행이 `=` 로 시작). 고침: 패턴을 큰따옴표로 + `grep -oE '[0-9]+ passed'` 로 파싱. 재실행 **14 passed**(노드 검사 초록) | 위 두 파일 |
| ↳ 그 김에 드러난 진짜 함정 | 종전 `if (cd … && pytest … \| tail -3)` 는 **파이프라인의 exit 가 `tail` 의 것**이라 `pipefail` 없는 셸에서 실패해도 초록이 된다. 이번 호출자들은 `set -uo pipefail` 을 쓰지만, 게이트 자체가 그것을 전제하지 않도록 `out="$(… )" \|\| rc=$?` 로 바꿔 **셸 옵션과 무관하게** 실패를 받는다(exit 4 는 요약줄이 없어서도 red 로 떨어진다 — 이중 방어) | `promote2/gates2.sh` A |
| ↳ 음성 대조군 | 승격 **전** 같은 명령: `pytest tests/test_restore_rehearsal_contract.py` → **exit 4** · 노드 검사 red. 즉 이 확인은 승격 위치에서만 초록이 된다(빈 껍데기가 아니다) | 위 파일 · 실행 기록 |
| ↳ **2차 배치 상태**(2026-09-17T02:2xZ) | 미러 리허설 **재실행 ALL PASS**(14 passed · 이빨 2/2 · 스테이징 잔존 0) · 본 트리 쓰기 **0건** · 본실행은 **동결 가드 때문에 거절**(도는 soak pid 56261 → 이동 0건). 본실행 순서는 `post_harvest_sequence.sh`(대기 → 판정 → 승격 → 새 지문 게이트 23개 → 재장전)이고, **지금 `screen nx10promote` 로 무인 대기 중**이다(종료 18:19 KST · 취소 `screen -S nx10promote -X quit`) | [PROMOTION_PLAN.md §1c](PROMOTION_PLAN.md) · [CLOSURE_RUNBOOK.md §5-6](CLOSURE_RUNBOOK.md) · `promote2/post-harvest-sequence.log` |
| ↳ **무인 실행에 필요한 두 가드**(샌드박스 4경로 확인) | ① **판정 FAIL 이면 승격을 멈춘다**(트리 무변경 · 강행은 `NX10_PROMOTE_ON_FAIL=1`) — FAIL 이면 후보에 손을 대야 하므로 승격 직후 지문이 또 움직인다(SC-6 가 그랬다) ② 이미 떠 있는 감시가 남긴 **방금 쓰인** 판정 원문을 먼저 기다린다(둘이 동시에 판정기를 돌리면 자물쇠 경합으로 이 순서가 끊긴다). 음성 대조군까지: 낡은 원문(mtime 과거)은 오늘 것으로 안 보고, 원문이 없으면 직접 harvest 한다 | `promote2/post_harvest_sequence.sh` |
| 승격 예약 | 리허설·경보 도구가 모두 `docs/` 안이라 **어느 게이트도 지키지 않는다** → 다음 승격 후보로 등록 | [PROMOTION_PLAN.md §1b](PROMOTION_PLAN.md) |
| ↳ **“SC-6 를 넘길까”를 사람의 머리에서 도구로 옮겼다**(2026-09-17T04:1xZ, 오너 질문에 답하려고) | 종전 도구는 외삼(→“8시간이면 +293 MB”)만 냈는데, 실제 질문은 **“지금 이 속도가 남은 시간을 버티는가”** 다. 남은 예산(기준 − 현재 증가)을 남은 시간으로 나눠 **허용 증가율**을 내고 실측 최근 증가율과 나란히 놓는다. 실측(4차 · 48분): 증가 **+29.4 / 64 MB** → 남은 7h11m 동안 허용 **+0.080 MB/분** · 최근 실측 **+0.210 MB/분** → **초과 추세** · 워밍업(2h) 전이라 경보는 보류. 두 신호(누적 외삼 · 예산 대 최근 기울기)를 **따로** 보고 하나라도 서면 경보한다 | `soak_watch.py` · 자기시험 **12/12 → 18/18**(이빨: 허용율 숫자를 실제로 내놓는가 · 평균 외삼은 한계 안인데 최근 기울기가 가파를 때 **예산 신호가 단독으로 경보하는가** · 워밍업 중에는 예산 초과율이어도 보류하면서 숫자는 밝히는가) |
| ↳ **기준의 모양을 코드에 적었다**(`ru_maxrss` 최고수위) | 하네스는 현재 RSS 가 아니라 **최고수위**를 50 op 마다 샘플해 `마지막 − 처음` 을 `rss_growth_mb` 로 쓴다. 보관된 리포트로 확인: 60초 리허설의 **첫 표본 67.2 MB**, 8시간 FAIL 실행의 첫 표본 66.8 MB — 즉 **시작 계단이 기준에 포함**되고, 이 도구의 `ps` 증가가 하네스 값과 **같은 것을 잿는다**(실측 첫 표본 71.7 MB). 60초 리허설의 증가는 이미 **+21.2 MB** 로, 64 MB 예산의 1/3 을 시작 계단이 먹는다 | 같은 파일 주석 · `soak-60.json` · `soak-28800-fail001.json` |
| ↳ **`--once` 가 위험을 침묵하고 있었다** | 운영자가 가장 자주 쓰는 한 줄 명령이 표본 1개로 판정해 **경과·저널 크기만** 보여 주고 “정상”이라 말했다(증가율·cap 투영·예산 없음 — 분석은 두 점이 있어야 성립한다). 고침: `--once` 는 1초 간격 **두 표본**, 그리고 **기준선의 출처**를 문장으로 밝힌다(① 호출자 값 ② 감시 이력에서 **같은 pid** 의 첫 표본 ③ 둘 다 없으면 “이 호출의 첫 표본이다 — 실행 시작 기준선 아님”) | `soak_watch.py` ⑩ 이빨(같은 pid만 · 다른 pid 는 섞지 않음 · 호출자 값 우선 · 근거 없으면 없다고 말함) |
| ↳ **화면이 존재하지 않는 급강하를 그리고 있었다**(4차 실행 시작 뒤 발견, 2026-09-17T04:06Z) | 새 실행은 journal 이 **0 에서 다시 자라므로**, 이전 실행의 표본을 같은 추세선에 이으면 화면이 **“journal 861.8 MiB → 1.4 MiB 로 줄었다”** 을 보여 준다(실제 그림). 그대로 두면 다음 사람이 “보존이 돌았나?” 를 먼저 의심하고, 경보 배지는 정상인데 그래프는 재해처럼 보이는 모순이 생긴다. 고침: 표본을 **실행(pid) 단위로 가르고**, 이전 실행의 표본은 `soak-watch-history-pid<pid>.jsonl` 로 **옮긴 뒤**(버리지 않는다) 새 실행의 선만 그린다. pid 를 모르면 가르지 않는다 — 빈손으로 단정하지 않는다 | `soak_watch_loop.py` · 자기시험 **9/9 → 14/14**(이빨: 섞인 이력은 861.8 MiB 급강하를 **재현**하고, 가른 이력은 재현하지 않는다 · 나눈 합이 원본과 같은가 · pid 없으면 안 가른다) · 실측: 3차 표본 **40개를 `soak-watch-history-pid56261.jsonl`** 로 이동 |

**지문 불변 확인**: 이 편집들은 `docs/` 안에만 있으므로 3차 실행의 시작 지문 `5c90b637…` 이 그대로 유효하다
(`docs/` 는 정적 게이트 지문 제외 구역 — `scripts/ga_gate.py` 의 `FINGERPRINT_EXCLUDED_PREFIXES`).
**판정은 변하지 않는다**: required red 1(`python-tests`, 타 레인) · CR-14 후보 재선언 없음 · owner 허용 없음.

## 22. 오너 지시로 **승격을 즉시 실행** — 새 지문에서 재측정, 4차 soak 시작 (2026-09-17)

오너 지시: “무인 대기를 취소하고 지금 2차 승격을 실행한 뒤, 필수 게이트를 재측정하고 8시간 soak 을 새로
걸어줘”. §21 이 `docs/` 만 고치며 **준비만** 해 둔 상태였으므로 §5b 의 순서 규칙을 그대로 밟았다:
**중단 → 승격 → 커밋 → 재측정 → 재장전**.

### 22-1. 도는 실행과 무인 대기를 먼저 내렸다(그리고 생존까지 확인)

| 무엇 | 방법 | 확인 |
|---|---|---|
| 3차 8시간 soak(경과 1h 04m 32s) | `kill -TERM <harness pid 56261>` | 러너가 정상 종료 경로로 `exit: 143` 을 기록 · **시작 = 종료 지문 = `5c90b637…`**(트리를 안 흔들었다) · 실행 잠금(`.soak-run.lock`)을 **스스로 해제**(실측: 잠금 없음) |
| 승격 무인 대기(`screen nx10promote`) | `screen -S … -X quit` + **프로세스 생존 확인** | `pgrep` 빈 결과 — `-X quit` 은 취소가 아니므로(§3e) 종료까지 봤다 |
| 회수 감시(`nx10harvest`) · 감시 루프(`nx10watch`) | 같음 | 회수할 실행이 사라졌으므로 남기면 12시간을 헛되이 기다린다 |

대가는 **1시간(8시간의 13%)** — 게이트를 새 지문에서 다시 재는 값에 비하면 싸다. 이 실행은 **판정 대상이 아니다**
(8시간 미충족 · 러너는 종료 시에만 리포트를 쓰므로 부분 산출물이 없다). 중단 시점 감시 표본은 남긴다:
journal **861.8 MiB** · RSS 108 MB · 추정 **681 ops/s** · 종료 시 cap 추정 6,482 / 8,192 MiB.

### 22-2. 승격 본실행 (2026-09-17T02:24Z, `promote2/apply_promotion2.sh`)

이동 4건(도구 2 → `scripts/`, 계약 시험 2 → `tests/`) 전부 **sha256 동일**(백업 `/tmp/nx10-promote2-backup-20260917T022400Z`),
승격 위치에서 **14 passed**(`promote2/promoted-contract-tests.txt` — 수집 노드가 `tests/`), 도구 직접 실행 초록 ·
ruff check·format 초록. 커밋 **`bde261dc`** · 기록 `promote2/promotion2-applied.txt`.

### 22-3. 재측정 — **승격이 숨은 타입 오류 12건을 드러냈다** (attempt `promote2b`)

| 항목 | 값 |
|---|---|
| 결과 | **21 passed · 2 failed · 0 not_run**(지문 시작 = 종료 = `50b82dd1…`, 커밋 `bde261dc`) |
| 새 실패 | **`python-basedpyright` 가 새로 빨개졌다** — 승격 **전**에는 이 두 파일이 `docs/` 안이라 정적 게이트가 **보지 않았다**. 커밋된 후보로 들어오자 타입 오류 **12건**이 드러났다(`scripts/restore_rehearsal.py` · `scripts/rollback_rehearsal.py`: `dict[str, object]` 언패킹 · `Any` 누수 · 시그니처) |
| 나머지 실패 | `python-tests` — 같은 5건(CR-14 울타리 3 · NX-07 문서 2) |

이것이 “승격하면 게이트가 지킨다”의 실제 값이다 — 승격은 파일을 옮기는 일이 아니라 **검사 대상으로 편입**시키는 일이고,
그 편입이 곧 **첫 검사**다. 수정 **`5c979c0f`**(타입 12건 + 테스트 파일의 `Any` 최소화) 뒤 같은 날 재측정했다.

### 22-4. 새 지문에서의 재측정 (attempt `promote2c` · `promote2d`)

| attempt | 언제 | 지문 | 결과 | 남은 실패 |
|---|---|---|---|---|
| `promote2c` | 02:50:33Z → 03:07:03Z | 시작 = 종료 = **`b6a74304…`** = HEAD(`5c979c0f`) | **22 passed · 1 failed · 0 not_run** · `clean-machine-runtime` passed | `python-tests`(같은 5건) — `python-basedpyright` **초록** |
| `promote2d` | 03:08:57Z → 03:19:22Z | 시작 = 종료 = `b6a74304…`(문서 링크 수정은 `docs/` 전용이라 불변) | `python-tests` **단독** 재측정: **5 failed · 6640 passed**(618.94s) | 위와 **시험 단위 동일**(울타리 3 · NX-07 2) → **새 실패 0건** |

**승격이 깬 문서 링크 1건**도 여기서 닫았다: `tests/test_local_relative_links_resolve` 가 승격 뒤 빨개졌다 —
옮겨진 파일을 옛 경로로 가리키는 참조 3곳(`docs/09` 복구·rollback 절 · `docs/19` NX-01/NX-03 항목 ·
`nx01/handoff.md` · `nx01/restore-rehearsal.md` · `nx03/handoff.md`). 고친 뒤 위 `promote2d` 를 돌렸다.
**통과 수 증가분이 승격의 증거다**: 6626(`sc3fix001`) → **6640**(`promote2d`) = **+14** = 승격한 계약 시험 14건.

### 22-5. 4차 soak 시작 — 이 지문이 지금의 후보 트리다

| 항목 | 값 |
|---|---|
| 시작 / 종료 예정 | `2026-09-17T03:25:56Z` → `11:25:56Z` = **20:25 KST** |
| 지문 | `b6a74304…` = **현재 트리 = HEAD 트리**(`5c979c0f`) — 3차 중단 뒤 편집은 `docs/` 뿐이다 |
| preflight | **7/7 OK** — 처리량 474 ops/s(하한 133) · 쓰기량 투영 < cap 8,192 MiB · 현재 트리 == HEAD |
| 경과(36분 시점 실측) | 판정 **정상** · journal **504.2 MiB** · 추정 **703 ops/s** · 종료 시 cap 추정 **6,696 MiB < 8,192 MiB** |
| **주의할 것 — RSS 증가(SC-6)** | 48분 시점 실측 판정: 증가 **+29.4 MB / 기준 64 MB**(기준선은 이 실행 첫 표본 71.7 MB — 하네스가 쓰는 것과 같은 자리) → 남은 7h11m 동안 **허용 +0.080 MB/분** 인데 **최근 실측 +0.210 MB/분**(누적 외삼이면 종료 시 +293 MB) → **초과 추세**. 다만 실행 48분은 워밍업(2h = 실행 25%) 전이라 도구가 경보를 보류하고 숫자만 밝힌다(§21). **판단 시점은 `05:25:56Z` = 14:25 KST** — 그때까지 상시 감시가 계속 돌므로 별도 작업 없이 배지·로그가 뒤집힌다(뒤집히면 이 추세가 8시간 유지된다는 뜻이다). 최종 판정은 하네스 지표가 한다 — 이 수치는 “언제 볼지”를 알려 주는 용도다 |
| 감시 | `screen nx10watch`(라이브 화면 `soak-watch-live.html`) · `screen nx10harvest`(회수 대기) 재부착 |

**판정은 변하지 않는다**: required red 1(`python-tests` — 타 레인) · **CR-14 후보 재선언 없음** · owner 허용 기록 없음.
이번에도 “22 passed”를 GO 로 확대 해석하지 않는다 — 울타리 3건은 **선언 후보 뒤에 코드 스코프 커밋이 있으면
설계상 빨간색**이고, 승격 커밋 2건(`bde261dc`·`5c979c0f`)이 그 뒤에 더해졌으므로 재선언 없이는 초록이 될 수 없다.

**추세 추적(같은 실행, 표본마다 갱신)**: 48분 `+29.4 MB` · 최근 기울기 `+0.210 MB/분`(허용 0.080 — 초과) →
1h41m `+32.4 MB` · 최근 기울기 **`+0.016 MB/분`(이내)** · 누적 외삼은 여전히 `+154 MB`. 즉 증가는 계단 뒤에
멈칫했고(1h41m 시점), **판단 시점 `05:25:56Z` 는 그대로**다. 도구가 “누적 외삼”과 “최근 기울기”를 따로
보고하도록 고쳐 둔 이유가 이 숫자쌍에 그대로 드러난다.

## 23. 3차 승격 리허설이 잡은 것은 **시험 쪽 결함**이었다 (2026-09-17, 4차 soak 실행 중)

승격 3차 배치(감시·통제 도구 3종 + 계약 시험 2종 — `PROMOTION_PLAN` §1e)의 미러 리허설이 네 번 돌았고,
처음 두 번은 **도구가 아닌 자기시험 쪽 전제** 때문에 빨개졌다.

### 23-1. 증상과 원인

자기시험의 “건강하면 `preflight` 0” 픽스처 넷이 공통으로 **깨끗한 작업 트리**를 가정했다(후보 귀속 =
`현재 트리 == HEAD`). 리허설은 커밋되지 않은 파일을 작업 트리에 두는 것이 **정의**이므로 그 항목이 설계상
거짓이고, 픽스처는 정당하게 1을 받아 게이트가 red 가 됐다.

| attempt | 손댄 것 | 결과 |
|---|---|---|
| `attempt1` | 초판 | 실패 2건 — 계약 시험 `1 failed` + 승격 위치 자기시험 실패 |
| `attempt2` | 두 픽스처에 skip 플래그를 **박아 넣음** | 여전히 실패 — 나머지 두 픽스처가 같은 전제를 공유. **박아 넣기는 답이 아니었다** |
| `attempt3` | 트리 ≠ HEAD 면 시험이 **스스로 계산**(`attr_skip`), 생략 사실을 출력에 남긴다 | **ALL PASS** |
| `attempt4` | 게이트 B 가 자기시험 전문을 산출물로 남김 | **ALL PASS** + `promoted-selftest3.txt` 에 생략 문장·`76/76` 기록 |
| `attempt5` | 계약 시험 docstring 의 “자기시험 75/75” 를 75~76 으로 정정 | **ALL PASS** — 바이트가 바뀌었으니 리허설을 다시 돌려 “이동 바이트 동일” 을 재확인(승격될 마지막 바이트) |

### 23-2. 왜 이게 오늘의 세 번째 같은 부류인가

오늘 하루 “초록이지만 아무것도 지키지 않는” 상태를 세 번 만났다: 판정기의 기대 지문이 실행마다 달라
**항상 FAIL**(§15) · 통제 도구가 돌고 있는 soak 을 오탐(§18) · 그리고 여기 — 게이트가 **자기 환경을
가정**해 리허설을 거짓으로 빨갛게 만들었다. 두 번째는 “항상 빨강”이 사람을 무디게 만들고, 이번은
“빨강의 원인이 도구가 아닌 시험”이라 **수리 대상을 잘못 짚게** 만든다. 처방은 같았다: **판단 근거를 늘리고,
생략·보류를 문장으로 밝힌다.**

### 23-3. 남긴 규칙 두 가지

1. **깨끗한 트리 / 더러운 트리를 갈라서 묻는다.** 생략은 환경을 스스로 감지해 자동으로, 그러나 **문장으로
   밝히고**(`후보 귀속(생략됨)`), 깨끗한 트리에서는 종전대로 검사한다(실트리 `75/75` 에서 확인). 이빨은
   깨끗한 트리에서 그대로 물고, 리허설에서는 “무엇을 생략했는지”가 증거로 남는다.
2. **돌고 있는 셸 스크립트를 편집하지 않는다.** `soak_control.sh` 는 회수 감시(`screen nx10harvest`)가
   그 순간 실행 중이었다 — bash 는 스크립트를 조금씩 읽으므로 수정이 실행을 깨뜨린다. 편집 전에 감시를
   내리고(**프로세스 0건 실측**) 편집 뒤 재부착했다. 회수 도구의 `cancel` 이 “취소했다고 기록한 예약이
   살아 있었다” 를 겪은 뒤 세운 **죽음 확인** 규칙을 편집에도 적용한 것이다.

**아직 하지 않은 것(동결 뒤 5분이면 됨, 기록만 남긴다)**: `attempt1`/`attempt2` 가 곧 음성 대조군이다(같은
픽스처·생략 없음 → red). 별도의 인위적 대조군(더러운 트리 + 옛 파일)을 돌리지는 않았다 — 8시간 soak 의
처리량·RSS 측정과 같은 기기를 나눠 쓰기 때문에, 판정 중에 부하를 더하는 쪽이 이득보다 위험이 크다.

## 24. 회수 뒤 순서를 **무인으로** 걸었다 — 그리고 그 리허설이 네 번째 어긋남을 잡았다 (2026-09-17)

오너 요청: “회수가 끝나는 즉시 3차 승격이 무인으로 실행되고 그 뒤 필수 게이트가 새 지문에서 재측정되도록.”
그래서 순서를 한 줄로 묶고(`promote3/post_harvest_sequence3.sh`), **걸기 전에 그 순서를 미러에서 리허설**했다
(`promote3/rehearse_sequence3.sh` → `promote3/sequence3-rehearsal.txt`). 무인 실행은 커밋까지 만드므로,
“멈춰야 할 때 멈추는가”를 확인하지 않고 걸면 사람이 자는 사이에 트리가 옮겨진다.

### 24-1. 세 경로를 실측했다 (ALL PASS)

| 경로 | 조건 | 결과 |
|---|---|---|
| A | 판정 PASS · 시작 == 종료 지문 | 승격 + 커밋까지 진행 · 커밋 뒤 코드 경로 깨끗(게이트 측정 전제 성립) |
| B | 판정 FAIL | 멈춤 · **트리 무변경**(스테이징 sha256 동일) · 중단 기록 |
| C | 시작 ≠ 종료 지문 | 멈춤 · **트리 무변경** · 중단 기록 |

검증된 바이트: `post_harvest_sequence3.sh` sha256 `a429baa3cb1c…` · `rehearse_sequence3.sh` `281935f727da…` ·
`sequence3-rehearsal.txt` `0644abf1dac9…`. 리허설은 본 트리 쓰기 0건이고, 진짜 soak·감시를 건드리지 않도록
식별 패턴을 시험용 이름으로 돌렸다(그 통로가 없으면 리허설이 돌고 있는 soak 을 건드릴 수 있다).

### 24-2. 네 번째 “조용한 어긋남” — 시험과 도구가 다른 이름을 본다

케이스 A 가 첫 리허설에서 **승격 도중** 멈춰 자동 롤백됐다. 원인은 승격이 아니라 계약 시험이었다:
`tests/test_soak_control_contract.py::test_harvest_refuses_to_judge_a_live_run` 이 “도는 soak 이 있는가”를
`pgrep -f val02_staging.py` 로 **하드코딩**해 판단했는데, 도구(`soak_control.sh`)는 그 이름을
`NX10_SOAK_PROC_PATTERN` 으로 받는다. 이름을 바꿔 돌리는 환경(미러 리허설이 정확히 그랬다)에서 **시험은
“있음”(exit 4 를 기대), 도구는 “없음”(exit 3 을 반환)** — 계약 시험이 거짓으로 빨개지고, 그 빨강이
게이트 A 의 `1 failed` 로 나타났다. 오늘 이 부류는 네 번째다: 판정기의 기대 지문(§15) · 통제 도구의 오탐(§18) ·
더러운 트리 가정(§23) · **시험과 도구의 이름 규칙 불일치(§24)**. 처방도 같았다 — 하드코딩을 없애고
**같은 이름 규칙을 공유**한다. 같은 이유로 `apply_promotion3.sh` 의 동결 가드도 이름을 받게 바꿨다:
가드를 **끄는** 옵션(`NX10_PROMOTE3_FORCE=1`, 운영용)과 **대상 이름을 통제하는** 통로는 다른 것이고,
리허설은 후자를 쓴다.

### 24-3. 걸어 둔 것과 그 의미

`screen nx10promote3` 가 `post_harvest_sequence3.sh --wait` 를 돌린다: 실행 종료(`11:25:56Z` = 20:25 KST)를
기다렸다가 판정 → (PASS 면) 감시 정리 → 승격 → 커밋 → **필수 23개 재측정**(약 19분) → 기록을
`promote3/post-harvest-record3.md` 에 남긴다. 재장전은 기본값이 아니다(`--rearm` 필요) — 밤에 두 번째 8시간을
자동으로 태우는 것은 오너 결정이다. 취소는 `screen -S nx10promote3 -X quit`(승격 전이면 트리 무변경).

**이 창은 여기서 멈춘다**: 순서가 돌기 시작하면(20:25 KST 이후) 트리를 옮기는 주체는 스크립트이고, 창이 같은
시간에 `docs/` 밖을 만지면 그 지문이 흔들린다. 기록을 읽고 대장에 반영하는 일은 그 뒤에 한다.

## 25. SC-6 기준 정량 검토 — 워밍업 포함이 맞는가, 그리고 “30 MB 순간 최고치”의 정정 (2026-09-17, 4차 soak 실행 중)

오너 질문(“SC-6 RSS 기준이 워밍업 구간을 포함하는 게 맞나”)에 숫자로 답하기 위해 **분석기**를 만들었다:
`analyze_sc6_criterion.py` → `sc6-criterion-analysis.txt`(같은 표본으로 재현 · 표본을 다듬지 않음).
기준 설계 문서는 [SC6_CRITERION_REVIEW.md](SC6_CRITERION_REVIEW.md) 이고, **판정값 소유자는 여전히 이 대장 §16** 이다.

### 25-1. 답 — 포함한다. 구조적으로, 그리고 처리량에 따라 다르게 포함한다

기준은 `rss_growth_mb = 마지막 표본 − 첫 표본` 인데 첫 표본은 **루프 50 반복 뒤**다. 그 50 반복이
**20.45초**(누수 실행 2.4회/초) ~ **0.08초**(4차 실행 606회/초) 로 움직인다 = 같은 코드·같은 시간을 재도
처리량에 따라 다른 것을 잰다. 예산(64 MB)에서 워밍업이 차지하는 몫: **60초 리허설 21.2 MB(33%)** ·
**4차 9.7 MB(15.2%)** · 누수 실행 2.4 MB(3.8%). 창 민감도(4차): 창 1분 → 창 밖 28.0 MB(74.2%),
창 5분 → 19.2 MB(50.9%), 창 10분 → 18.5 MB(49.0%), 창 48분 → 8.3 MB(22.1%).
누수 대조군은 창을 늘려도 판정력이 그대로다(창 밖 몫 99.9% → 97.2%).

### 25-2. 창 길이를 감이 아니라 **판정 안정성**으로 고른다

4차 실행의 종료(480분) 투영을 세 모델(창 밖 평균 · 마지막 30분 · 마지막 1시간)로 내면:
**창 1분 41.8~69.5 MB = 기준 64 MB 를 straddle(모델 분산 43.2%)** · 창 5분 33.0~48.3 MB(모두 PASS) ·
창 10분 32.3~47.3 MB · 창 48분 22.1~31.1 MB. 27분 뒤(221.8분 스냅샷) 같은 계산은 **32.1~61.8 MB** 로 갈리지 않았다 —
즉 **창 1분의 판정은 “어떤 모델”뿐 아니라 “언제 물었나”에도 매달린다**(분산 30.7% → 43.2% → 46.4%). 그 불안정성 자체가
결함의 증거다. 창 5분이면 두 시각 모두 **세 모델이 일치**하고, 그 이상으로 늘리면 숫자 폭만 줄고 판정 구간을 잃는다.

### 25-3. 률 한계 “8 MB/h” 는 이 부하에서 성립하지 않는다

건강한 실행의 창 잡음: **30분 창 최대 8.1 MB(@40분) = 16.2 MB/h** · 10분 창 최대 4.0 MB = 23.8 MB/h
(한계 8 MB/h 의 2~3배). 그래서 률로 물으면 건강한 실행이 거짓 FAIL 이 된다(전 구간 평균 C3 = 8.8 MB/h → FAIL).
**창 안 바이트**로 바꾸면 문턱 20 MB/30분이 2.5배 여유를 갖고, 누수 실행을 **40.0분**에 잡는다 —
현행 총량 기준은 **70.2분**에야 말한다(운에 따라 8시간이 끝날 때까지 침묵).
분석기 출력은 자기 **스냅샷 시각**을 첫 줄에 인쇄한다(진행 중 값은 매 분 변하고 구조적 결론만 남는다).

### 25-4. 기준은 시간 예산인데 부하는 반복 예산이다

605회/초에서 “64 MB / 8시간” = **3.85 B/회** 인데 건강한 실행의 창 밖 creep 은 **2.93 B/회** = **여유 0.76배**
(593회/초·221.8분 스냅샷에서는 3.93 B/회 대 2.67 B/회 = **0.68배** — 시간이 갈수록 여유가 줄어든다).
옛 처리량(2.4회/초)에서는 같은 기준이 **952.85 B/회**였다. 4차의 창 밖 30분 창별 반복당 값은
0.4~2.7 B/회로 진동하고 추세가 없다(1~31분 창의 13.49 B/회는 시작 계단). → **반복당 지표 병기가 필수**이고,
**기준값 64 MB 의 적절성**은 그 위에서 다시 정해야 한다(제안서 §9 D-B).

### 25-5. 정정 — 오늘 중간 보고의 “30 MB 순간 최고치”는 계측 오염이었다

감시 이력 188행의 pid 분포는 `78808 ×186 · 54012 ×2 · 16928 · 42557 · 51861 · 55758 각 1` 이었고, 제외된 6표본의
RSS(**64.6 · 75.5 · 76.0 · 77.2 · 1.9 MB**)가 실행 값(~104~107 MB) 사이에 끼어 “−28 MB → +28 MB” 를 만들었다.
**실행 자신의 계열은 사실상 단조**다: 표본 간 감소 9건 · 최대 **−0.047 MB** · 5 MB 초과 증가 **2건**(t=1.0분 +9.7 ·
t=2.0분 +6.7 — 둘 다 시작 계단). 그래서 중간 보고의 “30 MB 피크가 예산의 47%” 와 그것을 근거로 한 **절대 상한 논의의
전제는 취소**한다(제안서 §9 D-A 를 창 길이 결정으로 교체). 감시기는 이미 **기록 단계에서** pid 를 가른다
(`_find_pid`: 살아 있으면 갈아타지 않음 · 새 후보는 두 표본 연속 · 래퍼 comm 거부), 분석기는 섞인 표본을
**버리지 않고 개수·pid 를 출력**한다. 이 정정은 도구가 만든 거짓 결론이 도구의 다른 규칙에 의해 잡힌 사례로 남긴다.

### 25-6. 제안서가 요구하는 오너 결정 3건 (승인 전에는 코드 변경 없음)

- **D-A 창 길이**: 권고 `max(5분, 지속의 5%)` (1분은 판정을 모델에 매단다 · 5분 이상은 평평하다).
- **D-B 기준값 64 MB**: ① 유지 + 반복당 병기 ② 반복당을 주 판정으로 ③ 처리량에 맞춰 재산정 중 택일.
- **D-C 60초 리허설의 SC-6 행**: 권고는 삭제가 아니라 **`not_applicable`**(1분 실행에 8시간 임계값을 쓰는 것이 다른 질문).

구현은 **지문이 움직이므로**(`scripts/val02_staging.py`) 4차 soak 종료 + 3차 승격 배치 뒤에만 한다. 계약 시험 초안
6건(창 제외 · 창 길이 스케일 · 짧은 실행 `not_applicable` · 반복당 나눗셈 · 새 필드 기록 · **음성 대조군 FAIL 재현**)은
제안서 §10 에 있다. 관측된 별개 신호 둘도 카드로 남긴다: **처리량 −26.6%**(191분, 704→517회/초) · **반복당 creep 의 출처**.

### 25-7. 이 작업 중 관측한 도구 잡음 하나 — `status` 가 자기 픽스처를 “고아 예약”으로 보고한다

`soak_control.sh status` 가 **잠금 밖(고아) 예약: 1** 을 보고했고, 확인해 보니 그것은 돌고 있는 3차 배치 미러 리허설
(`screen nx10p3dry6`)이 자기시험(`soak_control.sh selftest`)을 돌리며 만든 **임시 픽스처**
(`/var/folders/…/nx10-ctl-selftest-*/t1/schedule_nx10_soak.sh`, 수명 14~23초)였다. 즉 **진짜 예약이 아니다.**
이 카드가 하루 전 “취소했다고 기록한 예약이 살아 있었다”로 한 번 물렸기 때문에 이 서명은 위험한 잡음이다 —
운영자가 그대로 읽으면 “예약이 다시 걸렸다” 로 오해하고 정리 절차를 밟는다. 오늘은 서명(pid·수명)을 눈으로 갈랐다.

**고치지 않고 남긴다**: `soak_control.sh` 는 3차 배치(§24)의 승격 대상이라, 지금 바이트를 바꾸면 도는 리허설
(`attempt6`)의 검증이 무효가 된다. 처방안(픽스처 이름·임시 경로를 도구가 스스로 식별해 제외)은 배치가 끝난 뒤
§1b 목록에 올린다. 판정 규칙: **“고아 예약”은 뿌리 pid 의 명령줄과 수명을 함께 보고, 셀프테스트 픽스처면 무시한다.**

### 25-8. 다섯 번째 “조용한 어긋남” — 내가 새로 넣은 이빨이 **청정한 트리에서만** 통과했다

§25-5 의 정정에 맞춰 `soak_control.sh` 에 **셸 오탐 차단**(`comm` 이 파이썬인 것만 하네스로 센다)과 그 이빨(⑧b)을
넣었고, 본 트리에서 자기시험 **77/77** 을 확인했다. 그런데 3차 배치 미러 리허설 `attempt6` 이
**실패 2건**으로 멈췄다: `⑧ (이빨) 셸이 패턴에 걸러도 preflight 0 (기대=0 실제=1)` — exit 1 이 나왔다.

원인은 도구가 아니라 **내 시험**이었다. 그 자리만 preflight 를 **직접 호출**했고(다른 픽스처는 공용 헬퍼를 쓴다),
공용 헬퍼가 넣어 주는 **`NX10_PF_SKIP_ATTRIBUTION="$attr_skip"` 문을 빠뜨렸다. 그래서 더러운 트리(승격 미러는
이동을 재현하므로 필연적으로 더럽다)에서 “현재 트리 == HEAD” 검사가 빨개져 exit 1 이 됐고, 청정한 본 트리에서는
같은 시험이 초록이었다. **오늘 이 부류가 다섯 번째다**: 판정기의 기대 지문(§15) · 통제 도구의 오탐(§18) ·
계약 시험이 더러운 트리를 가정하지 않음(§23) · 시험과 도구의 이름 규칙 불일치(§24) · **내가 넣은 이빨이
“본 트리에서만 통과하는” 단언이 됨(§25-8)**. 처방도 같다 — 그 자리에 **같은 문**을 붙이고, 생략이 일어난 경우
**문장으로 밝히는 검사**를 함께 넣었다(조용한 생략 금지). 헬퍼를 쓰지 않는 직접 호출은 이제 이유를 주석으로 남긴다.

실측(고친 뒤): 본 트리 자기시험 **77/77**(exit 0) · 미러 `attempt7` 이 **ALL PASS**(계약 시험 14 passed in 110.64s ·
이동 5건 sha256 동일 · 이빨 3/3 · 스테이징 잔존 0 · 자기시험 **79/79**). 시험 수가 77/79 로 늘어난 이유는
⑧b 이빨 2건과 더러운 트리 전용 생략 확인 1건이며, 그 수를 말하는 문장들(계약 시험 docstring)도 함께 고쳤다
(값을 말하는 문장과 값을 만드는 코드는 같은 커밋에서 움직인다 — 이 카드의 규칙).

### 25-9. 감시 계열에 남은 7번째 외부 표본 — 범인은 **내 리허설의 처리량 프루브**였다

SC-6 분석을 하며 pid 필터가 제외한 표본을 세어 보니 **7개**였고, 그중 하나(pid 71644 · `elapsed 11,936.9s` =
`06:44:53Z`)는 **pid 고정 수정 뒤**에 들어와 있었다. 성격을 보면 단서가 분명하다: `rss 69.3 MB` ·
`cpu_s 3.88` · 하루 동안 `pgrep` 진단 명령(§25-5)으로 설명되던 앞의 것들과 달리 **파이썬 프로세스**다.

원인은 감시 도구가 아니라 **이 창이 돌린 리허설**이다. 3차 배치 리허설·자기시험의 `preflight` 는
**처리량 프루브**를 돌리며 그것이 하네스(`scripts/val02_staging.py`)를 실제로 **짧게 실행**한다(5~60초).
그 순간에는 “패턴에 걸린, `comm` 이 파이썬인” 프로세스가 **둘**이 되고, 감시기가 **막 시작해서 잡은 pid 가 없는**
표본에서는 `pgrep` 순서(오름차순)가 앞선 **프루브**를 먼저 채택한다. 그 프로세스는 곧 죽으므로 다음 표본에서
본 실행(78808)으로 되돌아온다 — 그래서 **딱 한 행**이 남는다.

**고치지 않고 카드로 남긴다**(이유: `soak_watch.py` 는 지금 `attempt8` 로 검증된 배치 바이트라, 지문 대상이 아닌
`docs/` 파일이지만 승격될 바이트를 지금 바꾸면 그 검증이 무효가 된다). 처방안은 이미 눈앞에 있다:
하네스는 `--workdir $WORKDIR` 로 뜨므로(러너 `run_nx10_soak.sh:47,120`) **후보의 argv 가 감시 중인 workdir 을
포함하는 것만 하네스로 세우면** 프루브가 배제된다 — “pid 가 없을 때의 첫 채택”에도 같은 조건을 걸어야 한다
(오늘의 한 행이 정확히 그 문으로 들어왔다). 계약 시험은 픽스처 둘(다른 workdir 을 가진 파이썬 + 진짜 하네스)로
“첫 표본에서 남의 workdir 을 채택하지 않는다”를 고정하면 된다. 배치 뒤 §1b 목록에 올린다.

## 26. SC-6 기준을 **코드와 시험으로** 옮겼다 — 배치 `SC6` (2026-09-17 · 오너 지시 · 동결 해제 뒤 적용)

오너 지시: “동결이 풀리는 즉시 적용할 수 있도록 새 기준(창 밖 증가 + 반복당 creep)을 구현하고
계약 시험으로 고정해줘.” 그래서 준비물을 다 만들고 **미러에서만** 돌려 두었다(본 트리 쓰기 0건).

### 26-1. 무엇을 바꾸는가(코드)

`scripts/val02_staging.py` 에 ① 상수 셋(`RSS_WARMUP_MIN_S=300` · `RSS_WARMUP_FRACTION=0.05` ·
`RSS_CREEP_MAX_KB_PER_OP=0.25`) ② **순수 함수 둘** — `sc6_warmup_window_s()` 와
`sc6_rss_criterion(rss_samples, sample_ops, sample_times_s, actual_duration)` ③ `scenario_soak` 의 배선
(표본의 시각·반복 수를 모아 함수를 부르고 그 결과를 그대로 리포트에 싣는다) ④ `pass` 가 새 판정을 본다
(옛 `growth <= 64` 를 **대체**한다 — `not_applicable` 은 통과가 아니다) ⑤ `thresholds` 에 새 값 셋.

판정을 **순수 함수로 분리한 것이 핵심**이다: 그 덕에 계약 시험이 8시간을 태우지 않고(합성 계열 1000표본)
① 창 안 계단이 빠지는가 ② 짧은 실행이 `not_applicable` 인가 ③ 반복당 creep 이 반복 수로 나뉘는가
④ **음성 대조군**(끝으로 갈수록 가팔라지는 곡선)이 두 축 모두 FAIL 인가 ⑤ 리포트만으로 재현되는가
⑥ 시나리오가 실제로 그 함수를 부르는가(배선 이빨) 를 고정한다. 리포트에 실리는 필드는
`rss_growth_warmup_excluded_mb` · `rss_warmup_growth_mb` · `rss_warmup_window_s` · `rss_warmup_index` ·
`rss_creep_kb_per_operation` · `rss_criterion`(pass|fail|not_applicable) · `rss_criterion_basis` · 옛 `rss_growth_mb`(기록용).

### 26-2. 가드가 실제로 물렸는가(실측)

첫 리허설 회차가 `apply` 단계에서 **자동 롤백**됐다 — 계약 시험이 재현성에서 걸렸고, 되돌림이 돌아
미러의 하네스가 사전 이미지로 복구됐다(가드가 문서만이 아니라 코드로 동작한다는 증거).
원인은 기준이 아니라 **반올림 지점이 두 곳**인 것이었다: 리포트는 0.1 MB 단위로 싣는데 creep 은 반올림 전
증가량으로 계산해, 리포트만 보고 재현하면 1e-4 어긋났다. 반올림을 **한 번만** 하도록 고치고 그 틈을
고정하는 시험을 추가했다 — “리포트만으로 같은 판정을 재현한다”가 새 기준의 전제이기 때문이다.
(이 카드에서 “값을 만드는 곳과 값을 말하는 곳이 다르다” 부류가 여섯 번째다: §15 · §18 · §23 · §24 · §25-8 · **§26-2**.)

### 26-3. 리허설 결과(미러 · 본 트리 무변경)

`sc6fix/rehearse_sc6fix.sh` → **ALL PASS 22건**(`sc6fix/rehearsal-output.txt`): 사전 이빨(적용 전 계약 시험이
**실패**한다 — 패치 없이 통과하는 시험은 아무것도 안 지킨다) · 동결 가드 물림(exit 9) · 적용 뒤
ruff/format/**basedpyright 0 errors**/계약 시험 8 passed/기존 val02 시험 · **실제 60초 리허설**이
`rss_criterion="not_applicable"`(창 300s · 사유 문자열)을 리포트에 남김 · 도구를 되돌리면 시험이 빨개짐 ·
다른 바이트 위에는 거부(exit 8) · 본 트리 하네스 바이트 불변·신설 파일 없음·지문 대상 쓰기 0건.
검증된 바이트: `val02_staging.py ecd826ce90af…` · `test_sc6_criterion_contract.py cd4ff2da732b…` ·
`apply_sc6fix.sh ea45db386c96…` · `rehearse_sc6fix.sh b34ef49cfdc1…`(사전 이미지 고정값
`83da9a4885038bac…`).

### 26-4. 순서와 남는 위험

순서는 **4차 soak 회수 → 3차 배치(도구) 승격 → 배치 `SC6` 적용 → 필수 게이트 재측정 → 새 지문에서 8시간 soak** 이다.
`scripts/` 는 지문 대상이라 순서를 바꾸면 도는 실행이 무효가 된다(apply 스크립트가 동결 가드로 그것을 막는다).
남는 위험 둘: ① **통과 경로**(`not_applicable` 이 아닌 판정)는 픽스처로만 증명했다 — 실물 규모는 다음 8시간 실행이
처음 지난다 ② `rss_samples_mb` 는 50 반복마다 쌓이므로 **처리량이 오르면 리포트가 커진다**(600회/초 × 8시간 ≈ 29만 표본 → 그 필드만 ~2 MB).
후자는 다음 회수에서 실측해 필요하면 카드를 올린다(기준 문제가 아니라 산출물 크기 문제다).

### 26-5. 현재 실행에 미치는 영향(즉시 확인용)

지금 돌거나 판정될 4차 soak 은 **옛 기준으로 끝난다** — 적용은 회수 뒤다. 다만 새 기준을 그 표본에
소급해 물어보면(222분 스냅샷) 창 밖 증가 **28.5 MB** · 반복당 **0.004 KB/회** 로 새 기준도 PASS 이고,
근거는 “처리량 불변”이라 더 튼튼하다(옛 기준이 PASS 라도 처리량이 250배 바뀌면 같은 판정이 위태로웠다는
것이 §25-4 의 요지다).

## 27. 감시기가 **감시 중인 workdir 을 가진 하네스만** 후보로 삼는다 — 리허설 프루브가 계열에 못 앉는다 (2026-09-17 · 오너 지시 · 4차 soak 실행 중)

§25-9 의 범인(내 리허설의 처리량 프루브 = 이름도 인터프리터도 같은 **진짜 하네스**)을 문 하나로 막았다.
종전 문은 **관대**했다: 후보 중 감시 중인 workdir 을 담은 것이 하나라도 있으면 그것들만 남겼지만
**하나도 없으면 전부 남겼다** — 그 틈으로 프루브가 pid 순서상 앞자리를 차지해 표본 한 행을 계열에 앉혔고,
그 한 행이 없는 급강하를 만들었다(그림이 거짓말을 한다).

### 27-1. 무엇이 바뀌었나(문장 단위)

| 종전 | 지금 |
| --- | --- |
| argv **어딘가에** 감시 workdir 이 들어 있으면 통과(`needle in command`) | argv 가 **선언한** `--workdir <값>` 만 읽고, realpath 로 정규화해 감시 workdir 과 **같아야** 통과 |
| `--workdir` 선언이 없는 파이썬 → 후보로 남긴다 | `rejected_no_workdir` 로 **뺀다**(하네스는 러너가 `--workdir` 로 띄운다 — 그게 계약이다) |
| 맞는 후보가 하나도 없으면 **전부 남긴다** | **아무도 채택하지 않는다** + “없다”를 문장으로 밝힌다 |
| 판정 줄은 “찾지 못했다”만 | **왜** 못 찾았는지(뺀 pid 목록 · 감시 workdir)까지 줄로 남긴다 |

realpath 정규화가 필요한 이유는 실측에 있다: 감시 workdir 은 `/tmp/nx10-soak-work-20260917T032556Z`,
하네스 argv 도 같은 문자열이지만 macOS 에서 `/tmp` 는 `/private/tmp` 로 풀린다 — 문자열 비교로는 같은
디렉터리를 두 표기로 다르게 본다(그러면 감시가 통째로 눈이 먼다).

### 27-2. 이빨 — 문을 무력화하면 시험이 빨개진다(실측)

메모리에서 **필터만 무력화한 사본**을 만들어 두 규칙을 같은 픽스처에 물렸다(파일 쓰기 0건):

| 규칙 | 후보 | 채택 |
| --- | --- | --- |
| 새 규칙 | `[]` | `None` (아무도 아님) |
| 종전의 관대한 문 | `[선언없음 pid, 외부 workdir pid]` | **선언없음 pid** — 그 프로세스가 계열의 주인이 된다 |

즉 시험은 구현의 폭에 맞춰 넓어진 게 아니라 **실제 결함을 겨눈다**(같은 픽스처에서 종전 문이면 빨개진다).
자기시험 **24/24** · 계약 시험 `promote3` 기준 **17 passed**. ⑬ 픽스처(유령 후보)도 이제 **계약대로**
`--workdir` 로 뜬다 — 종전 픽스처가 관대한 문을 시험에 **고정**하고 있었다(구현이 넓히면 시험도 넓어지는 고리).

### 27-3. 화면 재부착이 즉사하던 결함 — 같은 지시를 수행하다 발견

고친 바이트로 상시 감시를 다시 붙이자 **루프가 첫 표본에서 끝났다**:

```
[16:37:17] 실행을 찾지 못했다(pid None) — 패턴 `val02_staging.py`
실행이 사라졌다 — 감시를 끝낸다(화면은 마지막 상태를 유지한다)
```

원인은 새 후보에 요구하는 **연속 두 표본 확인**이다(유령 차단). 갓 붙은 감시는 보고 있는 pid 가 없어 첫
표본이 **필연적으로** pid 없음인데, 루프는 그 한 표본을 “실행이 사라졌다”로 읽고 끝냈다 — 즉 **돌고 있는
soak 에 감시를 나중에 붙이는 정상 운영이 불가능**했다(이전 창의 재부착은 `--pid` 를 받았기 때문에 이
결함이 가려져 있었다). 처방: pid 없는 표본은 **기록하지 않고**(이력에 pid 없는 행이 남으면 다음 재시작의
첫 표본과 섞여 선이 끊긴다) 연속 두 번까지 기다린 뒤에야 “사라졌다”고 말한다.

재부착 결과(실측 `16:43:56Z`): 화면 `screen nx10watch` · 배지 **정상** · `pid 78808` · 이력 247행(옛 pid 표본
7건은 `soak-watch-history-pid*.jsonl` 로 **보존 이동** — 실계열은 불변). 계약 시험에 이 계약을 추가했다:
`test_loop_attaches_to_a_run_already_in_flight`(`--pid` 없이 붙여 exit ≠ NO_RUN · 이력에 붙은 실행의 표본 1행만).

### 27-4. 바이트가 바뀌었으므로 배치 3차 리허설을 다시 돌렸다

| 회차 | 결과 |
| --- | --- |
| `attempt9` | **실패 1건** — `ruff format --check`(포맷만 어긋남 · 게이트 A·B·D 와 계약 시험 17 passed 는 초록) |
| `attempt10` | **ALL PASS** — 계약 시험 `17 passed in 108.89s` · 이빨 3/3 · 스테이징 잔존 0 · 이동 5건 sha256 동일 |

본실행이 옮길 **검증된 바이트**: `soak_watch.py fc8599af9d48` · `soak_watch_loop.py c38d16d58845` ·
`soak_control.sh 00661d6f2152` · `test_soak_watch_contract.py 263ea2da0777` · `test_soak_control_contract.py a713185925d4`.

> 지문은 **불변**이다: 이번 변경은 전부 `docs/` 안(`nx10/soak_watch*.py` · `nx10/promote3/`)이라
> `src/`·`scripts/`·`tests/` 쓰기 **0건** — 돌고 있는 4차 soak(시작 지문 `b6a74304…`)에 영향이 없다(실측).

## 28. “반복당 2~3 바이트”의 출처 — 저널도 캐시도 인덱스도 아니다 (2026-09-17 · 오너 질문 · 4차 soak 실행 중)

질문: 남는 메모리를 **저널·캐시·인덱스 중 누가** 붙잡는가. 답: **셋 다 아니다** — 선형으로 커지는 것은
**저널 파일(디스크)** 뿐이고, 메모리 증가는 보유가 아니라 **매 회차 할당·해제가 남기는 몫**이다.
상세·원자료: `sc6creep/FINDINGS.md` · `sc6creep/probe_creep_source.py`(국면 A/B/C/D · `--no-tracemalloc`).

### 28-1. 셋을 각각 기각한 실측

| 후보 | 측정 | 판정 |
| --- | --- | --- |
| **인덱스**(sqlite·WAL·shm·페이지 캐시) | 국면 A 11,400회 4분위 기울기 871 → 407 → 190 → **15 B/회**(tracemalloc 끔), WAL·shm 0 유지 | **무죄** — 초기 몇 MB 는 페이지 캐시가 **차오르는 구간** |
| **캐시**(인메모리 `_records` 레코드) | messages 1→24~41(soft max 64) · summary 1,281자 · `carried_summary` **900자 고정** · `summarized_ranges` **8 고정** · `gc.collect()` 후 객체 수 증가 없음 · tracemalloc 생존 바이트 **후반 0.4~3 B/회** | **무죄** — 상한이 코드와 실측 양쪽에 |
| **저널**(디스크) | journal **+348.0 B/회**(60 ops/s) · **+352.7 B/회**(600 ops/s) → 처리량 무관 · 실측 179 KB/s(1시간 604 MB) | **유일한 선형 증가** — 하지만 **디스크**다 |

### 28-2. 남은 몫은 churn 이다(대조군 + rate 대조)

- **대조군(국면 D)**: 저장소 코드를 **0줄** 쓰고 같은 일감량(348 B 파일 append + ~7 KiB JSON 재작성·재읽기)
  을 돌렸더니 **285~390 B/회** 로 같은 모양의 증가가 재현됐다.
- **rate 대조**: 같은 일감을 60 → 600 ops/s(10배)로 돌리면 반복당 증가가 **1,143 → 659 B/회** 로 **줄었다**.
  진짜 보유라면 처리량과 무관해야 한다.
- **실측 4차**: 최근 1시간 RSS **+2.4 MB(0.7 KB/s = 1.2 B/회)** vs 같은 기간 저널 **+604 MB(179 KB/s)** —
  RSS 증가는 저널 증가의 **0.4%** 로 **완전히 분리**되어 있다. 초반 몇 분의 fill(약 +18 MB)이 8시간 총량의 대부분이다.

### 28-3. 계측기가 만든 몫을 같이 분리했다

같은 sqlite 국면의 마지막 구간이 tracemalloc 을 **켜면 219 B/회**, **끄면 15 B/회** 였다. 즉 오늘 “누수”로
보였던 값의 일부는 **도구 자신의 힙·추적 테이블**이었다(§25-5 의 “30 MB 순간 최고치” 허상과 같은 부류,
이번엔 내가 새로 만든 도구가 같은 실수를 할 뻔했다 — 그래서 끄는 통로를 도구에 넣었다).

### 28-4. 그래서 다음 행동

1. SC-6 기준의 **워밍업 제외**는 옳다(실측 fill ≈ 18 MB · 정상상태 1 B/회) — §25-4 의 “반복당을 주 판정으로” 권고와 일치.
2. **진짜 한계는 메모리가 아니라 디스크**: 저널 348 B/회 + sqlite db 191 B/회에 상한이 없다 → ADR §8 의
   retention/quota 가 릴리스 blocker 라는 기존 판단이 이 측정으로 확정된다.
3. 남은 churn 의 1순위 후보는 `_persist` 의 **view 전체 재작성**(매 회차 `json.dumps(..., indent=2)`) —
   **지문 대상(`src/`)** 이라 동결 해제 뒤 별도 배치로 다룬다.

## 29. 처리량 감소를 **1급 판정 축**으로 — 배치 `PERF` 설계·구현·리허설 (2026-09-17 · 오너 지시 · 4차 soak 실행 중)

지시: *“처리량 감소를 1급 판정 축으로 삼는 성능 회귀 게이트를 설계해줘 — 8시간 동안 27% 느려진 실행을
RSS 누수와 별개로 잡아내야 해.”* 설계 전문·보정 원자료: [perf/THROUGHPUT_GATE_DESIGN.md](./perf/THROUGHPUT_GATE_DESIGN.md).
스테이징 `nx10/perf/` · 계약 시험 **13개** · 리허설 스크립트까지 `docs/` 전용(지문 **불변**).

### 29-1. 먼저 드러난 사실: **벽시계 단독은 게이트가 될 수 없다**(실측)

돌고 있던 4차 실행(8시간 중 5시간)의 30분 블록 실측:

| 축 | 첫 25% → 끝 25% | 의미 |
| --- | --- | --- |
| 벽시계 `ops/s` | 692 → 508 = **−26.5%** | 요구 임계(27%)와 사실상 같은 값 — **단독 판정이면 건강한 실행을 빨갛게 만든다** |
| 효율 `ops/CPU초` | 779.9 → 740.6 = **−5.0%** | 일당 비용은 거의 그대로 |
| 이용률 `CPU초/벽초` | 0.887 → 0.686 = −22.6% | 기계가 바빴다(오늘 이 기계에서 게이트·리허설·프로브를 돌렸다) |

그래서 판정은 단일 숫자가 아니라 **정체식 분해**로 한다:

```
벽시계 처리량 = 효율(ops/CPU초) × 이용률(CPU초/벽초)      # 리포트에 identity_gap 도 함께 남긴다
```

같은 “27% 느려짐”이 ① 코드가 느려짐(효율↓ = **제품 회귀**) ② 기계가 바빴음(이용률↓·호스트 부하 높음 =
**재실행**) ③ 제품이 대기를 늘림(I/O·lock·fsync · 이용률↓ 인데 호스트는 조용 = **서비스 회귀**) 로 갈리고
처방이 서로 다르다. 판정 규칙·임계(`THROUGHPUT_MAX_DECLINE = 15%` · 블록 `max(5분, 지속×2%)` ·
사분위 중앙값 · `load1/코어 > 0.5`)는 설계 문서 §2·§3 에 있고, 임계는 전부 **실측 보정**이다
(60초 표본 잡음 CV 16.8% · 10분 블록 편차 중앙 8.4%/최대 29.6%).

### 29-2. RSS 축과 **독립**임을 시험으로 고정

계약 시험 #7 이 네 조합을 각각 다르게 판정한다 — (느림·누수)(느림·깨끗)(빠름·누수)(빠름·깨끗).
즉 처리량 게이트만 빨갛거나 RSS 게이트만 빨간 상태가 **표현 가능**하고, 그 구분이 리포트에 남는다.
시험 #10 은 **오늘의 그 실행**(`live-4th-series.json` = 실측 표본 288개)을 “제품 회귀”라고 부르지 않는다
— 벽시계 −26.5% 를 근거로 건강한 실행을 처벌하지 않는지가 회귀 시험의 요점이다.

### 29-3. 리허설이 문 것을 실측 (미러 · 본 트리 쓰기 0건 · **ALL PASS 17/17**) — §30 합류 뒤 재측정

| # | 시나리오 | 실측 |
| --- | --- | --- |
| P1 | 적용 전 이빨 | SC6 이미지(처리량 축 없음) 위에서 계약 시험이 **실패**(14줄 표시) — 시험이 조용히 통과하지 않는다 |
| P2 | 적용 | 가드 3개 통과 · 계약 시험 통과 · 스모크가 `throughput=not_applicable`(60초→사유 문장)을 실제로 냄 · 이동 sha256 동일 |
| P3 | 동결 가드 | 하네스가 도는 이름(`val02_staging.py`)이면 **exit 9**(쓰기 0건) |
| P4 | **합성 순서** | 도구가 SC6 **이전** 바이트면 “SC6 를 먼저” + **exit 6**(쓰기 0건) |
| P5 | 사전 이미지 불일치 | 제3의 바이트 위에는 안 덮는다 — **exit 8** |
| P6 | 본 트리 무변경 | 지문 대상 3파일 전후 동일 · `scripts/val02_staging.py` = 동결 바이트 `83da9a48…` 그대로 |

| P2b | 승격 위치 정적 문 | 승격 위치에 타입 오류를 심으면 **exit 5** + **자동 롤백**(승격 파일 제거 · 도구를 사전 이미지로 복원) |

리허설이 **결함 2건**을 실제로 잡았다. ① 60초 실행이 두 축 다 `not_applicable` 인데 시나리오 `pass = True`
였다(= 환경 변수 한 줄로 게이트를 비울 수 있는 문). `criteria_gate` 를 넣어 **긴 실행의 `not_applicable`
은 통과가 아니다**로 고정했다(계약 시험 #12). ② 계약 시험 파일이 `docs/` 안에 있는 동안 **정적 게이트의
시야 밖**이라 `basedpyright` 오류 **5건**(제네릭 미지정 4 · `int` 미반복 1)을 숨기고 있었다 — 승격하면
`python-basedpyright` 가 빨개지는 부류다(§22 에서 같은 부류를 실제로 겪었다). 고친 뒤 **승격 위치 정적
검사**(ruff check/format + basedpyright)를 `apply_perf_gate.sh` 검증에 넣고, 그 문이 무는지를 P2b 로 증명했다.

### 29-4. 적용 순서와 검증된 바이트

두 배치가 **같은 파일**(`scripts/val02_staging.py`)을 바꾸므로 순서를 코드로 고정했다:
**SC6 → PERF**. `apply_perf_gate.sh` 의 사전 이미지 해시는 SC6 적용 뒤 이미지
`ecd826ce90af…` 이고, 동결 트리 바이트 `83da9a48…` 를 만나면 “SC6 먼저”로 멈춘다.

본실행이 옮길 바이트(리허설 ALL PASS 를 받은 것): `val02_staging.py 1c65ad5f…` →
`scripts/` · `test_throughput_gate_contract.py 94ff5246…` → `tests/` · `live-4th-series.json b9f25b21…` → `tests/`
(가드·러너: `apply_perf_gate.sh 59a6c01f…` · `rehearse_perf.sh e32f7594…`).

### 29-5. 오너 결정 3건(승인 전 `src/` 변경 없음)

- **D-P1** 허용 감소 **15%** 확정(대안 10% = 민감·오탐 / 20% = 27% 를 7%p 여유로).
- **D-P2** 경합(`not_applicable`) 시 **재실행 요구**(권고·현재 구현) vs 경고 후 통과.
- **D-P3** 최소 실행 길이 **2시간**(8시간 게이트에서는 자동 만족).

### 29-6. 남는 한계(먼저 적는다)

단일 기계 위에서만 뜻이 있다(부하는 `load1/코어` 라는 거친 프록시) · CPU 는 `time.process_time()` 이라
대기는 이용률 하락으로만 보인다 · **어느 호출이 느려졌는지는 조사하지 않는다**(잡고·분해하고·처방을 가르는 데까지) ·
감시기(`soak_watch.py`)의 처리량은 여전히 바이트 추정이다(정본은 하네스의 `sample_ops`) ·
6만 초 이상 실행에서는 블록이 2% 로 커져 해상도가 떨어진다(상한 결정은 오너 몫).

## 30. 귀속 사다리 — “느려졌다” 다음의 질문: **어느 호출이** 느려졌나 (2026-09-17 · 오너 지시 · 4차 soak 실행 중)

지시: *“처리량 회귀가 잡혔을 때 어느 호출이 느려졌는지 자동으로 좁혀 주는 귀속 사다리를 설계하고 계약
시험으로 고정해줘.”* 설계·실측: [perf/THROUGHPUT_GATE_DESIGN.md](./perf/THROUGHPUT_GATE_DESIGN.md) §9.
배치 `PERF` 에 **합류**했다(같은 파일·같은 계약 시험 파일) — 별도 배치가 아니라 같은 승격 단위다.

### 30-1. 다섯 칸

한 반복을 세 국면으로 나누고(`SOAK_PHASES`: `task.create` · `task.transition` · `conversation.append`)
국면 경계에서 `process_time()` 을 적립한다(반복당 3회). 반복 끝에서 시계를 **청구 없이** 리셋하므로
루프·표본 수집·할당자·GC 는 어느 국면에도 안 붙고 그만큼이 **잔차**가 된다.

| 칸 | 조건 | 말하는 것 |
| --- | --- | --- |
| `not_applicable` | 게이트가 초록이거나 실행 < 2시간 | **돌지 않는다**(귀속은 빨간 판정의 설명이지 별도 판정이 아니다) |
| `insufficient` | 총 증가 < 첫 분기 단가 2%(잡음) 또는 계열/블록 부족 | **아무도 지목하지 않는다** — 없는 범인을 만들지 않는다 |
| `outside_phases` | 잔차 > 총 증가의 50% | 할당자·GC·인터프리터·루프 → 프로세스 전체 프로파일 |
| `phase` | 한 국면이 증가분의 ≥ 50% | **이름을 지목** + 몫 + 다음 칸(그 경로의 하위 단계) |
| `spread` | 지배 국면 없음 · 잔차 작음 | 고르게 늘었다 → 공통 경로 |

**정체식은 실측에서 지켜졌다.** 총량은 국면 합이 아니라 **프로세스 전체 CPU 표본**에서 잰다 — 국면 합을
총량으로 쓰면 잔차가 정의상 0 이 되어 `outside_phases` 가 영영 안 난다(첫 구현이 그랬고 계약 시험 ⑯ 이
그 구멍을 겨눈다). 이 결정이 실측에서 확인됐다: Σ 국면 2,240 µs/반복 = 전체 표본 총량 2,240 µs/반복.

### 30-2. 이빨 — 계약 시험 10개(합계 **23 passed**)

⑭ 한 국면 지목(합성 +1200 µs/반복 → `conversation.append`, 몫 ≥ 0.9) · ⑮ 잡음이면 무지목 ·
⑯ 국면이 설명 못 하면 `outside_phases`(잔차 비율 > 0.5) · ⑰ 균등 증가면 `spread` ·
⑱ **빨라진 국면은 음수 기여로 남고 범인으로 안 지목** · ⑲ 초록 실행엔 안 돎 · ⑳ 60초엔 안 돎 ·
㉑ 정체식 + **리포트만으로 재현** · ㉒ 두 계열이 안 맞으면 판정 불가(사유 문장) · ㉓ 배선 이빨(경계 3곳·리포트·임계).

시험 ⑭ 는 추정량의 성질도 밝힌다: 분기 중앙값은 선형 궤적의 12.5%/87.5% 에 앉아 **주입 증가분의 약 72%** 를
본다(워밍업 창이 앞을 자른다). 그래서 사다리 숫자는 “얼마나”의 상한이 아니라 **어느 국면인가**를 가리는 재료다.

### 30-3. 배선 실측 — 계약 시험 밖의 것을 프로브가 본다

`perf/probe_ladder_end_to_end.py`(→ `probe-ladder-output.json`)가 실제 하네스를 60초씩 세 번 돌렸다:

| 실행 | 조건 | 실측 |
| --- | --- | --- |
| A | 상수 그대로 | 게이트 `not_applicable`(60초로는 5분 블록이 안 찬다) · 사다리 미실행 · **국면 스냅샷 32개 적립** = 배선 살아 있음 |
| B | 프로브 노브(블록 1초·워밍업 3초·최소 30초) | 게이트가 **판정을 낸다**(블록 48개): 벽시계 −5.1% · 효율 −2.7% · 부하 0.30 → `pass`(경합도 회귀도 아님) |
| C | 같은 노브 + 게이트 인위 빨강 | 사다리가 **실제 계열을 쪼갠다**: 국면 블록 46개 · 총 단가 2,240→2,280 µs/반복 · create 500 · **transition 980→1,000**(가장 비쌈) · append 760 · Σ 국면 = 총량 → 판정 `insufficient`(+1.8% = 잡음, 잔차 +20 = 50%) |

C 가 증명하는 것은 정확한 귀속이 아니라 **계열의 풍부함**이다: 8시간을 쓰기 전에 “실제 계열이 국면 쪼개기를
감당하는가”를 값싸게 확인한다(배선이 끊겼으면 즉시 빨개진다).

### 30-4. 검증된 바이트 · 남는 한계

배치 `PERF` 의 이동 바이트가 갱신됐다(§29-4 대체): `val02_staging.py **d4771262…**` ·
`test_throughput_gate_contract.py **6dbef041…**` · `live-4th-series.json b9f25b21…`.
도구: `apply_perf_gate.sh 59a6c01f…` · `rehearse_perf.sh c5332d00…` · 프로브 `c55a266c…`.
미러 리허설 **ALL PASS 17/17**(P1 이 사다리 시험도 빨개지는 것까지 확인).

한계: ① **`phase` 칸은 실측으로 아직 안 태워졌다** — 그 칸은 다음 8시간 soak 이 처음 태운다(회귀가 없으면
`not_applicable` 로 끝난다) ② 국면은 경계까지만 본다(하위 단계는 `next_step` 이 가리키는 다음 조사)
③ 국면 목록이 하드코딩이라 새 작업은 “국면 밖”으로 간다 ④ `process_time()` 기반이라 **대기**는 국면 단가에
안 들어간다(대기는 게이트의 이용률 축이 잡는다).

> 지문은 **불변**이다: 이번 변경은 `docs/`(`nx10/perf/`)만 건드렸다 — `src/`·`scripts/`·`tests/` 쓰기 `0` 건(실측).

## 31. 사다리의 다음 칸 — 국면 **안**의 하위 단계, 그리고 그것이 곧바로 찾아낸 것 (2026-09-17 · 오너 지시)

지시: *“지목된 국면 안의 하위 단계(저널 append · view 재작성 · tail 같은)까지 자동으로 좁히는 사다리 다음
칸을 설계하고 계약 시험으로 고정해줘.”* 설계·실측: [perf/THROUGHPUT_GATE_DESIGN.md](./perf/THROUGHPUT_GATE_DESIGN.md) §10.
배치 `PERF` 에 합류(같은 파일·같은 계약 시험 파일) — 세 번째 칸까지 같은 승격 단위다.

### 31-1. 왜 창(window) 프로파일인가

그 하위 단계는 **제품 코드 안**(`src/antigravity_k/engine/conversation_store.py`)에 있고 그 파일들은 **지문
대상**이다 — 잴 때마다 제품에 타이머를 심을 수 없다. 그래서 하네스가 **창 단위로 `cProfile`** 을 걸고, 창은
**국면 하나씩 돌려 가며** 연다(그래야 “그 국면 안의 함수 순위”가 나온다). 계측한 창의 반복은 **판정 계열에서
제외**한다(`attribution_measured_ops`) — 계측이 판정을 오염시키면 “느려졌다”가 측정기 때문일 수 있다(§28 의 규칙).

표본률 1/200 반복 · 창 25 호출 · 창 상한 40(= 1,000 호출 ≈ 8시간 측정 계열의 **0.006%**) · 8시간에서 국면
스냅샷 ≈ 3.5만 표본. 꺼도 되는 칸이다(`NX10_DEEP_PROFILE=0`) — 설명용이므로 꺼도 통과/실패는 약해지지 않고,
대신 “왜 느린지 말할 수 없다”고 리포트가 문장으로 밝힌다.

### 31-2. 실측(D 실행 · 60초 실제 하네스 · 창 13개) — 답이 바로 나왔다

| 국면 | 파이썬이 본 단가 | 상위 함수(자기 시간) | 판정 |
| --- | --- | --- | --- |
| `task.create` | 604 µs/반복 | `builtins.next` 587 · sqlite `commit` 555 · `execute` 203 | 가장 싼 국면 |
| `task.transition` | 1,085 µs/반복 | `builtins.next` 472 · sqlite `execute` 398 · `commit` 305 | sqlite 쓰기 경로 |
| `conversation.append` | 1,223 µs/반복 | **`posix.fsync` 847 = 69%** · `posix.replace` 98 · `_io.open` 80 | **`function` — 이름 지목** |

즉 `conversation.append` 안의 지배 항은 **내구성 flush(`fsync`)** 이고, view 재작성(원자적 `replace`)과
tail 은 그 뒤다. 이 칸이 노린 것이 정확히 이것이다: 국면 이름만 보면 “JSON 직렬화가 느린가?”로 읽히지만
실제 비용은 **디스크 flush** 이므로 처방이 “직렬화 줄이기”가 아니라 **“flush 정책·배치”** 가 된다.
(오버헤드 비율 **1.57** · 잔차 −441 µs 는 음수 → `deep_residual_note` 가 “계측 오버헤드가 부풀렸다”고 밝힌다.)

### 31-3. 이빨 — 계약 시험 12개 추가(합계 **35 passed**)

㉔ 국면 안 지배 함수 지목 · ㉕ 안에서 퍼지면 무지목 · ㉖ 파이썬 밖이면 `outside_functions` ·
㉗ **계측기를 순위에서 빼고 뺐다고 밝힌다** · ㉘ 음수 잔차를 오버헤드 탓으로 설명 · ㉙ 앞칸 미지목이면 안 돎 ·
㉚ 60초엔 안 돎 · ㉛ 창이 적으면 무지목(노브 안내 · 계측 끔도 사유) · ㉜ 리포트만으로 재현 ·
㉝ **계측기 계약**(창 수 × 창 크기 = 계측 호출 수) · ㉞ **음성 대조군: 유령 창** · ㉟ 배선 이빨(계열 제외 포함).

### 31-4. 계측기를 만든 그 자리에서 세 번 틀렸고, 프로브·시험·타입검사가 각각 잡았다

| 결함 | 누가 잡았나 | 증상 |
| --- | --- | --- |
| 창이 닫힌 뒤 **같은 반복의 꼬리 호출**까지 계측 → 창이 두 번 닫힘 | **프로브**(실측 14/26/0 — 세 번째 국면이 영영 안 돌았다) | 창 수 40 → **3,776**(계측 호출 3,800) · 국면 회전이 어긋남 → `active_for` 로 막고 계약 시험 ㉝㉞ 로 고정 |
| 호출마다 **창 전체 시간**을 다시 더함(전이는 반복당 2회 → 두 배) | **프로브**(국면 단가가 29,642 µs/반복으로 폭주) | 이제 호출 경계 사이 델타만 더한다 |
| `getstats()` 의 **[3]=cumtime · [4]=tottime** 을 반대로 읽음 | **프로브**(자기 시간 > 총합이라는 불가능한 표) | 순위의 근거가 뒤바뀐 상태였다 — 주석에 실측 순서를 못박음 |
| 계측기 자신(`val02_staging.py:<lambda>`)이 **1위**로 올라옴 | **프로브**(첫 회차) | 하네스 파일 프레임을 순위에서 빼고 `deep_instrument_us_per_op` 로 밝힘 |

타입검사도 한 번 잡았다(계열 분기 중간값을 낼 때 **버킷을 행처럼** 순회 → 블록이 두 번 접힘).

### 31-5. 검증된 바이트 · 미러 리허설

`val02_staging.py **84ab2c93…**` · `test_throughput_gate_contract.py **64dde41f…**` ·
`live-4th-series.json b9f25b21…`(변동 없음) · 도구 `apply_perf_gate.sh 59a6c01f…` ·
`rehearse_perf.sh c5332d00…` · 프로브 `731f7f76…` · 프로브 출력 `d19c44a3…`.
미러 리허설 **ALL PASS 17/17**(P1 이 “국면 내부 시험도 SC6 도구에서 빨개진다”까지 확인).

한계: ① `function` 칸은 프로브 노브 실행에서 나온 것이고 **8시간 실행 연쇄는 아직 안 태워졌다**(회귀가 없으면
두 칸 다 `not_applicable`) ② C 확장은 cProfile 이 자기 시간을 부풀리므로 **순위는 신뢰, 절대값은 오버헤드
감안** ③ 창 경계는 호출 단위(창당 최대 1회분은 계열 밖) ④ 프로파일러는 파이썬만 본다.

> 지문은 **불변**이다: 이번 변경도 `docs/`(`nx10/perf/`)만 건드렸다 — `src/`·`scripts/`·`tests/` 쓰기 `0` 건(실측).

## 32. 사다리의 네 번째 칸 — 지목된 함수를 **누가·얼마나 자주** 부르는가 (2026-09-17 · 오너 지시)

지시: *“지목된 함수가 어느 호출 경로에서 얼마나 자주 불리는지까지 자동으로 좁히는 사다리 네 번째 칸을
설계하고 계약 시험으로 고정해줘.”* 설계·실측: [perf/THROUGHPUT_GATE_DESIGN.md](./perf/THROUGHPUT_GATE_DESIGN.md) §11.
배치 `PERF` 에 합류(같은 두 파일) — 네 칸까지 같은 승격 단위다.

### 32-1. 두 답을 나눠 내는 이유는 **처방이 다르기 때문**이다

| 답 | 처방 |
| --- | --- |
| 반복당 **1회** | 횟수는 이미 최소 → **그 호출 자체를 싸게**(정책·배치·비동기화) |
| 반복당 **여러 번** | 한 번으로 줄일 여지가 있다 → **호출을 합친다**(중복 제거·일괄 처리) |
| 한 경로가 지배 | 그 경로를 고친다 |
| 여러 경로가 부른다 | 부르는 곳 대신 **그 함수 자체**를 싸게 |

그래서 **경로 판정**(`path_criterion`: `path`/`multi_path`/`insufficient`/`not_applicable`)과 **빈도**
(`path_frequency_class` · `path_calls_per_iteration` · `path_frequency_note`)를 별도 필드로 낸다. 빈도는
경로 판정을 흔들지 않는다(시험 ㊶이 그걸 고정한다).

### 32-2. 새 계측 비용은 0 — 다만 통로가 직관과 다르다

호출자 표는 `cProfile` 이 **이미 만들고 있었다**. 그런데 `Profile.getstats()` 튜플의 **6번째 칸은 callees**
(내가 부른 것)이고 호출자가 아니며, 내장 함수에서는 `None` 이다 — 그걸 호출자로 읽은 첫 구현은 **바로
`None` 을 만났다**(프로브가 실측으로 잡았다: `entry len 6 … e[5] is None`). `pstats.Stats(profile).stats` 가
callee 목록을 뒤집어 호출자 표를 만든다(`print_callers` 가 쓰는 그 자료). 튜플 순서도 다르다: raw 는
`(code, nc, cc, ns, tt, ct)` · pstats 는 `(cc, nc, tt, ct, callers)`.

**교체가 측정을 바꾸지 않았는지 실측 확인**: 같은 프로파일에서 `pstats.tt` == `raw[4]`(inlinetime),
`pstats.ct` == `raw[3]`(totaltime) 이 **상위 6개 프레임 전부에서 소수점까지 일치**했다. 즉 통로만 바뀌었고
숫자는 안 건드렸다. 부작용 하나를 코드에 못밖았다: `Stats(profile)` 는 `profile.stats` 를 **비운다**(그래서
창마다 새 `Profile` 을 쓴다 · 테스트 스텁에 `Stats.stats` 가 없어 `vars()` 우회를 `_pstats_table` 한 곳에만 둔다).

### 32-3. 실측(프로브 E · 실제 하네스 60초 · 창 13개) — 두 질문에 답이 나왔다

```
판정: path · 함수 posix.fsync · 반복당 1.00회 (at_most_once_per_iteration)
호출자: conversation_journal.py:_fsync_fd  (몫 1.00 · 호출 325회)
사슬: posix.fsync ← conversation_journal.py:_fsync_fd ← conversation_journal.py:_append_bytes
      ← conversation_journal.py:append ← conversation_store.py:_commit_event
```

즉 “`append` 안의 `fsync`”(셋째 칸)가 **“저널의 `_fsync_fd`, 반복당 정확히 1회, `_commit_event` 에서
시작하는 사슬”**(넷째 칸)이 된다. **빈도 1.00 이 이 칸의 산출**이다: 반복당 한 번이면 코얼리싱으로 줄일
것이 없고(저널 커밋당 한 번이면 최소), 처방은 **그 한 번을 싸게 만드는** 정책·배치다.

### 32-4. 이빨 — 계약 시험 12개 추가(합계 **47 passed**)

㊱ 지배 호출자 이름 지목 · ㊲ 지배자 없으면 `multi_path` · ㊳ 호출자 표가 불완전하면 무지목 ·
㊴ 표가 비면 “없다” · ㊵ 앞칸 미지목이면 안 돎 · **㊶ 빈도가 처방을 가른다**(1회 vs 3회 · 경로 판정은 불변) ·
㊷ 사슬을 위로 걷는다 · ㊸ **하네스를 국면 진입점이라고 밝힌다**(사슬에서 계측기를 건너뛰고 건너뛴 수를 밝힘) ·
㊹ 리포트만으로 재현 · ㊺ 짧은 실행·계측 꺼짐은 사유를 말함 · **㊻ 계측기 계약**(실제 `cProfile` 로 국면마다
호출자 표가 담기고 **진짜 호출 관계**가 잡힌다) · **㊼ 음성 대조군**(표를 비우면 `insufficient` 로 퇴화).
미러 리허설 **ALL PASS 17/17**.

### 32-5. 그 과정에서 확인된 것: 셋째 칸의 **몫은 실행마다 흔들린다**

첫 프로브에서 `posix.fsync` 847 µs(69%, `function`) 였는데 다음 프로브에서 405 µs(33%,
`spread_within_phase`) 였다. 같은 일감(200 반복)을 세 번 재서 알아냈다:

| 회차 | 전체 | `fsync` | `fsync` 몫 |
| --- | --- | --- | --- |
| 1 | 3,515 µs/op | **1,930 µs** | **54.9%** |
| 2 | 1,036 µs/op | 27.5 µs | 2.7% |
| 3 | 1,074 µs/op | 27.9 µs | 2.6% |

**70배 차이**다. `fsync` 는 커널 대기라 **디스크가 더러운 상태냐**에 달려 있다 — 그러니까 847 도 405 도 틀린
값이 아니고 *그 때의 디스크* 값이다. 진단할 때는 **순위와 호출 횟수**를 읽고 몫은 “그 순간의 크기”로 읽어야
한다. 이 흔들림이 **네 번째 칸의 빈도 축이 결정적인 이유**다(빈도 1.00 은 결정적이다).

### 32-6. 계약치고 이빨이 있다: 창은 **샘플 주기의 배수**에서만 열린다

`take()` 는 `index % DEEP_SAMPLE_EVERY == 0` 인 반복에서만 창을 연다 → 창 상한 40을 다 쓰려면 인덱스가
`40 × 200` 이상 흘러야 한다. 1,200 반복짜리 시험 구동으로는 열림 기회가 5번뿐이라 국면당 창이 2개로 끝나
**넷째 칸이 `insufficient` 로 죽는다**(시험을 쓰다 실측으로 밟았다: “국면 task.create 창 2개 · 계측 반복 50”).
실제 8시간(수천만 반복)·60초 프로브(기회 180번)는 무관하다 — 시험 구동만 20,000 반복으로 올렸다.

### 32-7. 검증된 바이트 · 리허설

`val02_staging.py **a67695013fde…**` · `test_throughput_gate_contract.py **e47a4151872d…**` ·
`live-4th-series.json b9f25b218c76…`(변동 없음) · 도구 `apply_perf_gate.sh 59a6c01fd6f0…` ·
`rehearse_perf.sh c5332d007d1e…` · 프로브 `d9f48b3ef0f9…` · 프로브 출력 `6ca277f959c3…`.
미러 리허설 **ALL PASS 17/17**(P1 이 네 칸 시험 전부가 SC6 도구에서 빨개지는 것까지 확인).

한계: ① `path` 칸은 프로브 노브 실행에서 나온 것이고 **8시간 연쇄는 아직 안 태워졌다** ② 셋째 칸의 몫이 흔들리면
이 칸도 안 돈다(앞칸이 `function` 일 때만) ③ 호출자가 C 쪽이면 답하지 못한다 ④ 호출자 수는 **창 안의 호출**만 센다.

## 33. flush 배치 설계 — fsync 를 어떻게 다룰 것인가(설계만 · 적용은 동결 해제 뒤) (2026-09-17 · 오너 지시)

지시: *“`conversation.append` 의 fsync 69% 를 근거로 flush 정책·배치 대안들을 동결 해제 뒤 지문에 반영할 수
있는 배치로 설계해줘.”* 설계·증거: [fsync/FLUSH_BATCH_DESIGN.md](./fsync/FLUSH_BATCH_DESIGN.md). 배치 `FLUSH`.
**본실행하지 않았다**(`src/` 는 지문 대상 — 4차 soak 이 그 바이트를 재는 중).

### 33-1. 출발점은 “69%” 가 아니라 “1.00회/반복” 이다

사다리 넷째 칸이 `posix.fsync` 의 호출자를 `conversation_journal.py:_fsync_fd`, 빈도를 **반복당 1.00회**로
지목했다(§32-3). 그런데 그 **몫**은 70배 흔들린다(§32-5) — 왜인지 이번에 곡선으로 밝혔다:

| 페이지 캐시 더티 | 0 MB | 8 MB | 64 MB | 256 MB |
| --- | --- | --- | --- | --- |
| `fsync` 지연 중앙값 | **22.4 µs** | 341.3 µs | 352.0 µs | 289.3 µs |

즉 fsync 는 **“캐시가 더러운가”의 계단 함수**이고, 일감 크기(저널 271 B/회)와 무관하게 약 **300~350 µs 고정세**다.
그래서 “직렬화를 줄여 fsync 를 싸게” 는 **성립하지 않는다** — 지렛대는 ① sync 를 덜 부른다(정책) ② fsync
주변을 덜 쓴다(예산) 둘뿐이고, 이 배치는 그 둘을 **다른 부품**으로 나뉜다.

### 33-2. 증거 — append 1회 예산(결정적)과 플랫폼 능력

도구 `fsync/probe_flush_path.py` → `probe-flush-output.json`(`os.*` 계기 + `Path.write_text` 계기):

| 항목 | 실측/append |
| --- | --- |
| `os.fsync` | **1.000** (내구성 계약) |
| `os.open`/`os.close` | 5.000 / 5.000 |
| `os.pread` | 3.000 · **읽은 바이트 116,025 B(≈113 KiB)** |
| **`tail()` 호출** | **3.000** |
| `os.stat`/`os.fstat`/`os.replace` | 11.000 / 3.000 / 1.000 |
| **view 재작성** | **1.000회 · payload 8,021 B** |
| 저널 증가 | 271 B/회 |

꼬리 읽기 3회의 출처은 네 지점이다(소스 확인): `_authoritative_record` · `_reconcile_view_with_journal` ·
`_commit_event` · `journal.append` — 넷은 **같은 flock 임계 구역 안**에 있고, 그 구역에서 쓰지 않는 한 꼬리는
변하지 않는다. 플랫폼: `darwin` · `os.fdatasync` **없음** · `fcntl.F_FULLFSYNC` 있음 ⇒ 여기서 `os.fsync` 는
**미디어까지 내려간다는 보장이 아니다**(ADR §2 의 “durable” 문구가 덮고 있는 구멍 — §33-5).

### 33-3. 세 부품 — 위험·계약 영향별로 나눈 것

| 부품 | 무엇 | 계약 영향 | 상태 |
| --- | --- | --- | --- |
| **F1** | 꼬리 읽기 **3회 → 1회**(+ 통계 최소화) | **없음** | **스테이징 완료 · 미러 리허설 ALL PASS 16/16** |
| **F2** | **view 재작성 스로틸**(매 append → 필요할 때 · 8 KB+rename/회) | 읽기 표면의 신선도 | 설계만(D-F2) |
| **F3** | **sync 정책**(`always`/`batched`/`fdatasync`) | **ADR-DAT-02 §2 문장을 바꿀다** | 설계만(D-F3) |

성격이 다른 결정을 한 배치에 묶으면 내구성 논쟁이 **예산 절감까지 함께 멈춰 세운다** — 그래서 나뉘다.

### 33-4. F1 의 안전 논변·이빨·리허설

**계약**: flock 임계 구역 안에서 꼬리는 한 번만 읽고 그 값을 나눠 쓴다. `journal.append()` 가 호출자의 꼬리를
받는다(미결 꼬리를 들고 오면 다시 읽는다). **왜 안전한가**: 기억의 수명이 한 임계 구역이고, 그 안에서 꼬리를
바꿀 수 있는 것은 우리뿐이며(다른 프로세스는 flock 을 못 잡는다), 우리가 바꾸면 그 자리에서 비운다.

기대(측정 기준선 기준): `tail()` 3.00 → **1.00** · 읽은 바이트 116 KB → **≈38 KB** · `open` 5.00 → **≤4** ·
`fsync` **1.00 불변**. **시간 환산은 하지 않는다** — 근거는 개수다(§33-1 의 교훈).

계약 시험 **9개**: ① 꼬리 한 번(재읽기 ≤70 KB) ② fsync 정확핼 1회 ③ open 예산 무회귀 ④ seq/revision 1씩
⑤ **낡은 기억을 재사용하지 않는다**(CAS 실패 + 타 writer 전진 뒤에도 revision 미중복) ⑥ 미결 꼬리는 커밋 전에
이동 ⑦ 커밋 순서(줄+fsync → view) ⑧ view 실패에도 커밋 생존 ⑨ 기억을 비우는 지점이 임계 구역 진입.

**미러 리허설 ALL PASS 16/16**(본 트리 쓰기 0건): P1 적용 전 **3 failed**(예산·소스 이빨이 실제로 문다) ·
P2 적용 뒤 **9 passed** + ruff + basedpyright **0 errors** · P2b 심은 타입 결함을 물고 롤백 · P3 기존 시험
**70 passed** 무회귀 · P4 동결 **exit 9** · 합성 순서 **exit 6** · P5 사전 이미지 **exit 8** · P6 본 트리 무변경.

리허설이 만든 **거짓 FAIL 2건**이 도구 교훈으로 남았다: ① 저장소 루트에서 절대경로로 정적 검사를 돌리면 임포트
해석이 **진짜 `src/`** 를 집어 미러의 새 시그니처를 못 보고 “No parameter named tail” 을 거짓 보고(정적 검사는 그
바이트를 소유한 뿌리에서) ② **`basedpyright` 는 경고만 있어도 exit 1**(errors 0 · warnings 116 · exit 1 실측)
→ 판정은 종료 코드가 아니라 **파싱한 `errorCount`**(안 그러면 깨끗한 패치를 롤백한다).

### 33-5-bis. 세 대안을 한 표에 놓다 — 그리고 결정 뒤 배치로 만드는 조건(설계 §10)

“대안들을 배치로 설계”하라는 지시에 답해, 결정 항목을 **고르는 표**로 정리했다(설계 §10-1):
`FLUSH`(F1 · 계약 불변 · **준비 완료**) → `FLUSH2`(F2 · 개수를 줄이고 표시만 늦춘다) →
`FLUSH3`(F3 · 계약 자체를 바꾼다 · **ADR 개정이 선행물**). 특히 F2·F3 은 “문장이 정해져야 시험을 쓰는 종류”라
코드를 못 쓴다는 판단을, 대신 **배치의 훅·시험 후보·사전 이미지·합성 순서·되돌림**을 미리 적어 두는 것으로 바꿨다
(§10-2 · §10-3): F2 = 훅 4개 + 시험 5건(기본값은 현행 `immediate` = 무회귀) · F3 = ADR 6문장 먼저 + 훅(정책 객체·
플랫폼 강등) + 시험 6건(크래시 시뮬레이션 포함) + 노브 한 줄 되돌림. 그리고 적용이 지문에 일으킬 일
(게이트 23 재측정 → 새 지문 8시간 soak → 회수 → 커밋)도 §10-4 에 적었다.

### 33-5. F2·F3 — 설계만 남긴 이유와 오너 결정

- **F2( view 스로틸)**: ADR §2 가 이미 “view 가 뒤처져도 된다”고 적었다 — **ADR 안에 있는 여지**다. 효과는
  **8 KB + rename 1회/append**(결정적). 대가: 읽기 표면 신선도. D-F2.
- **F3(sync 정책)**: `batched` 를 기본값으로 만들면 **약속의 변경**이다(ADR §2). 그래서 세 후보(`always` /
  `batched` / `fdatasync`)와 **각각의 대가**·유실 창의 정의·관측(`sync_pending`)·셧다운 `flush()` 를 문장으로
  적어 두고 오너 결정을 기다린다. 권고 **보류** — 유실 창은 되돌릴 수 없는 결정이고, 지금 문제는 F1 로 대부분 사라진다.
  **`durable` 의 플랫폼별 정의**(macOS `F_FULLFSYNC`)도 ADR 에 명시해야 한다(D-F3′).

### 33-6. 검증된 바이트·가드

배치는 `docs/qa/…/nx10/fsync/` 에 있다: `probe_flush_path.py` · `probe-flush-output.json` ·
`patch_flush_budget.py`(사전 이미지 고정: `conversation_journal.py a89dfd2d82cc…` · `conversation_store.py
7f3e4605da9d…`) · `test_flush_budget_contract.py`(→ `tests/`) · `apply_flush_batch.sh` · `rehearse_flush.sh`.
가드: 동결 **exit 9** · 합성 순서 **exit 6** · 사전 이미지 **exit 8** · 검증 실패 **exit 5(자동 롤백)**.
**적용 순서**: 4차 soak 회수 → 3차 배치 → SC6 → PERF → 게이트 재측정 → **FLUSH** → 게이트 재측정 → 새 8시간 soak.

**검증된 바이트**(동결 해제 때 다시 대조할 값 — 2026-09-17T10:01Z 실측):

| 파일 | sha256(앞 12) |
| --- | --- |
| `fsync/patch_flush_budget.py` | `e2016ef42ced…` |
| `fsync/test_flush_budget_contract.py` | `59d469ead4e1…` |
| `fsync/apply_flush_batch.sh` | `92fdcef5b0e3…` |
| `fsync/rehearse_flush.sh` | `945250421759…` |
| `fsync/probe_flush_path.py` | `0382e99fbcf2…` |
| `fsync/probe-flush-output.json` | `537fa87fbb38…` |

**리허설 재확인(2026-09-17T10:01Z · 현재 바이트)**: **ALL PASS 16/16** — P1 적용 전 `3 failed`(이빨) ·
P2 적용 뒤 `9 passed` + ruff + basedpyright `errors=0` · P2b 심은 결함 `errors=1` → **롤백** · P3 기존 시험
**70 passed** 무회귀 · P4 동결 `exit 9` · 합성 순서 `exit 6` · P5 사전 이미지 불일치 **거부·쓰기 0건** ·
P6 본 트리 `src/` 두 파일 sha256 전후 **동일**(`a89dfd2d82cc…` · `7f3e4605da9d…` = 사전 이미지 일치).
문서 검사기 **ALL OK**(링크 201) · 4차 soak 은 계속 도는 중(동결 유지 = 본실행 불가가 정상).

> 지문은 **불변**이다: 이번 설계는 `docs/`(`nx10/fsync/`)만 썼고 `src/`·`scripts/`·`tests/` 쓰기 **0건**(미러 리허설
> P6 이 실측으로 확인).

> 지문은 **불변**이다: 이번 변경도 `docs/`(`nx10/perf/`)만 건드렸다 — `src/`·`scripts/`·`tests/` 쓰기 `0` 건(실측).

## 34. view 신선도 계약 — “방금 쓴 턴이 언제 보여야 하는가”(배치 `FLUSH2` · 결정·구현·리허설) (2026-09-17 · 오너 지시)

지시: *“view 재작성 스로틸(F2)을 위해 ‘방금 쓴 턴이 언제 보여야 하는가’ 신선도 계약을 정하고, 그 문장을
계약 시험으로 옮겨 둬.”* 결정문·근거: [fsync2/VIEW_FRESHNESS_CONTRACT.md](./fsync2/VIEW_FRESHNESS_CONTRACT.md).
**본실행하지 않았다**(`src/` 는 지문 대상 · 4차 soak 이 그 바이트를 재는 중).

### 34-1. 계약 여섯 문장의 핵심 — 신선도는 파일이 아니라 **반환값**의 성질이다

조사가 전제를 바꿨다: 공개 읽기는 모두 `_refresh_latest` 를 지나고, 그것이 view 가 뒤처졌으면 journal 로
재생성한다 — 즉 반환값은 **원래 journal 에서 온다**. 그래서 “언제 보이는가”의 답은 **“커밋 즉시”** 이고,
지연될 수 있는 것은 **표시용 파일**의 내용뿐이다. 계약 8문장(C-1~C-8)은 이 관점을 코드로 고정한다:
C-1 반환값(시험 ①) · C-2 판정은 시퀀스(②③) · C-3 유한 창(④⑥⑩) · C-4 따라잡기에 저널 재생 금지(④) ·
C-5 수렴점(⑧) · C-6 기본값 현행(⑤) · C-7 읽기 수렴(⑦) · C-8 삭제는 안 되살아난다(⑨).

### 34-2. 이 조사가 드러낸 것 ① — mtime 판정은 실측으로 **거짓이었다**

현행 판정은 `journal.st_mtime_ns > view.st_mtime_ns` 다. 그런데 복원·백업·동기화 도구는 파일을 **옛 내용으로,
새 mtime 으로** 놓는다(그게 복원의 정의다). 프로브 `fsync2/probe_view_staleness.py` → `probe-view-staleness-output.json`:

```
journal_tail_seq 3 · view_bytes_seq_after_restore 1 · view_mtime_newer_than_journal true
observed {revision: 1, journal_seq: 1} · read_missed_committed_turns true   ← 커밋된 턴 2개를 놓쳤다
```

**F2 와 무관하게 닫아야 할 구멍**이다(지연이 만드는 상태와 같은 모양이다). 계약 C-2 가 판정을
`_journal_tail` 의 시퀀스 비교로 바꾼다 — 시험 ②가 이 상황을 그대로 재현하고, ③이 소스 이빨로
“판정에 mtime 이 없다”를 고정한다(`st_mtime_ns` 가 판정 경로에서 **사라진다**).

### 34-3. 이 조사가 드러낸 것 ② — “미루기”는 이득이 아니라 **회귀**였다

view 쓰기를 k회에 1회로 미루면, 다음 판정이 “journal 이 더 새롭다”를 보고 **저널 전체 재생**을 한다:
미루기 3회에 1회 · 12턴에서 **재생 7회(미룸당 1.17회)** — 3 KiB 저널에서도 그렇다. 8시간 soak 의 저널은 수백 MiB 이고
그 크기의 전체 파싱이 바로 하루를 날렸던 부류(`rss_growth_mb 1683.5`)다. 그래서 C-4 를 계약에 넣고 시험 ④가
“지연이 일어나면서도 재생은 0”을 잰다: 지연의 **대가로 재생이 붙으면 그 배치는 적용하지 않는다**.

### 34-4. 이득은 개수로 — 400턴 실측

`fsync2/probe_view_throttle_benefit.py` → `probe-view-throttle-benefit.json`(임시 트리에 F1+F2 적용):

| 모드 | view 재작성 | 다시 쓴 view 바이트 | 저널 증가 | 저널 전체 재생 |
| --- | --- | --- | --- | --- |
| `immediate`(기본) | **402회** | **5,612,000 B(≈5.6 MB)** | 109,727 B | 0 |
| `coalesced(max_lag=8)` | **52회** | **701,600 B(≈0.70 MB)** | 109,713 B | **0** |

**같은 400턴에서 저널(내구 기록)이 110 KB 자라는 동안 view(표시용)는 5.6 MB 를 다시 썼다 — 표시용이 내구
기록보다 약 51배 많이 쓴다.** 이 배치가 노리는 것은 그 5.6 MB 쪽이고 내구성 계약은 한 글자도 안 바꾼다.
시간은 주장하지 않는다(§33-1 의 교훈: 근거는 개수다).

### 34-5. 배치 — 훅 12개 · 계약 시험 10건 · 미러 리허설 ALL PASS 21/21

| 항목 | 값 |
| --- | --- |
| 스테이징 | `nx10/fsync2/` · 본실행 `bash fsync2/apply_flush2.sh`(`--dry-run`) |
| 바뀌는 소스 | **`conversation_store.py` 하나**(훅 12개) — 기본 동작은 현행 그대로 |
| 노브 | `AGK_CONVERSATION_VIEW_REFRESH=immediate|coalesced` · `…_MAX_LAG=N`(기본 8) |
| 승격 시험 | `tests/test_view_freshness_contract.py`(10건) |
| 가드 | 동결 `exit 9` · 사전 이미지 `exit 8` · 합성 순서 `exit 6` · 검증 실패 `exit 5`(자동 롤백 · 시험 포함) |
| 선행물 | **F1(`FLUSH`)** — 사전 이미지 = F1 적용 뒤 바이트(`c9029151ccbd…`) |

**리허설(본 트리 쓰기 0건)**: P0 F1 없이 적용 → `exit 8` · **P1 적용 전 이빨 8 failed/2 passed** ·
P2 적용 뒤 계약 시험 **10 passed** + ruff + basedpyright `errors=0` · P2b 심은 타입 결함 `errors=1` → F1-상태로 복원 ·
P3 기존 계약 시험 **70 passed** + **F1 예산 계약 9 passed** · P4 동결 `exit 9` · PERF 미승격 `exit 6` ·
P5 사전 이미지 불일치 **거부·쓰기 0건** · P6 본 트리 sha256 전후 동일. 전문: `fsync2/rehearsal-output.txt`.

**검증된 바이트**: 패처 `d9186ad2125b…` · 시험 `3002bc7034bb…` · apply `3ab331ccbe83…` · rehearse `a8fc759be967…`.
**적용 순서**: 회수 → 3차 배치 → `SC6` → `PERF` → 게이트 재측정 → **`FLUSH`** → 게이트 재측정 → **`FLUSH2`** →
게이트 재측정 → 새 8시간 soak.

### 34-6. D-F2 에 대한 답 — “늦춰도 되는 것은 파일뿐이다”

- **읽기는 한 순간도 늦추지 않는다**(C-1 · 시험 ①) — D-F2 의 원래 질문(“읽기 신선도를 어디까지 늦출까”)은
  전제가 틀렸다: 늦출 것이 값이 아니라 파일이다.
- **기본값은 현행(`immediate`)** 이다 — D-F2 는 “옵트인 기능을 준비해 두었으니 켤 시점만 정하면 된다”로 바뀌었다.
  켜는 비용은 이미 측정되어 있고(1/8 · 재생 0), 되돌리는 비용은 환경변수 한 줄이다.
- 남는 한계(먼저 적었다): 지연 창 동안 **다른 프로세스의 첫 읽기가 재생 1회**를 낸다 · `SIGKILL` 로 죽으면 view 가
  뒤처진 채 남는다(안전 — 판정이 시퀀스라 다음 읽기가 재생성) · `mtime` 을 신선도 근거로 쓰던 외부 도구의 가정은 깨진다.

> 지문은 **불변**이다: 이번 변경은 `docs/qa/…/nx10/fsync2/` 만 썼다 — `src/`·`scripts/`·`tests/` 쓰기 **0건**
> (P6 이 실측으로 확인 · 4차 soak 계속).

## 35. ADR-DAT-02 §2 개정 **초안** — sync 정책과 “durable” 의 뜻(배치 `FLUSH3` · 설계만) (2026-09-17 · 오너 지시)

지시: *“sync 정책 batched 를 위한 ADR-DAT-02 §2 개정 초안을 유실 창 정의·관측·플랫폼별 durable 문장까지 갖춘
리뷰 가능한 형태로 작성해줘.”* → 초안 [fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md](./fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md) ·
근거 [fsync3/probe-durability-output.json](./fsync3/probe-durability-output.json). **코드는 쓰지 않았다**(승인 뒤).
ADR 본문에는 **비규범 포인터 한 줄**만 넣었다(§2 아래 · Status 는 `Proposed` 그대로 · “결정 아님”을 명시).

### 35-1. 개정이 필요한 이유 — 현행 문장은 플랫폼이 보장하지 않는 것을 약속한다

현행 §2 는 (a) 순서 규칙(“줄 → fsync → view”)과 (b) 내구성 등급(“durably committed”)을 섞어 적었다. (a) 는
정확하고 그대로 둔다. 문제는 (b) 다: **macOS 의 `os.fsync` 는 미디어 보장이 아니고**, 보장하는 `F_FULLFSYNC` 는
이 호스트에서 **88배** 비싸다. 그래서 제안은 “내구성을 낮추자”가 아니라 **등급에 이름을 붙이고 유실 창을
정의하고 관측 가능하게 만들자**다.

### 35-2. 실측 — 등급별 비용(같은 파일 · 커밋 1회 = 271 B 한 줄 · 605 ops/s → 커밋당 예산 1,653 µs)

| 등급 | sync 주기 | **µs/커밋** | always 대비 | 예산 대비 |
| --- | --- | --- | --- | --- |
| `cache`(`os.fsync`) | **1회/커밋(현행)** | **45.37** | 1.0 | **2.74 %** |
| `cache` | 8회에 1회 | **9.82** | 0.22 | 0.59 % |
| `cache` | 32회에 1회 | 5.06 | 0.11 | 0.31 % |
| `media`(`F_FULLFSYNC`) | **1회/커밋** | **4,008.13** | **88.3** | **242.5 %** |
| `media` | 8회에 1회 | **527.91** | 11.6 | 31.9 % |

유지 단발: `os.fsync` 44.2 µs(p95 57.5) vs `F_FULLFSYNC` 4,163.4 µs(**94배**) · 같은 파일에 8 MB 를 쌓고 sync
1회 = 1,710 µs(30,954 커밋분 → **0.055 µs/커밋**). 플랫폼: `darwin` · `os.fdatasync` **없음** · `F_FULLFSYNC` 있음.

### 35-3. 이 숫자가 뒤집는 것 — 배치는 요점이 아니다

1. **`cache` 등급은 이미 커밋당 예산의 2.7 %** 다 — 배치를 걸면 0.6 % 가 되지만, 그 2 %p 를 얻자고 **약속(유실 창)을
   바꾸는 것은 남는 장사가 아니다**(FLUSH 설계 §5 의 결론을 숫자가 확인).
2. **`media` 등급은 커밋마다 줄 수 없다** — 242 % = 반복 1회의 2.4배. 배치(k=8)라도 32 % 로 여전히 지배적이다.
   즉 “정말 디스크에 남는다”는 보장은 **핫패스 밖**(주기·체크포인트·셧다운)에만 존재할 수 있다.
3. 그래서 개정의 핵심은 동기화 **주기**가 아니라 **등급 이름과 창·강등·관측**이다.

### 35-4. 초안이 넣는 문장(발췌) — 등급 셋 · 창의 정의 · 플랫폼 표 · 관측

- **등급 셋**: `process`(sync 없음) / **`cache`(현행 = `os.fsync`)** / `media`(`F_FULLFSYNC`·`fdatasync`).
- **창의 정의**: *“크래시에서 사라질 수 있는 것은 **가장 최근 성공한 sync 이후에 커밋된 줄들**뿐이다 — 줄이
  사라지는 것이지 **뒤바뀌거나 일부만 남는 것이 아니다**.”* 창 크기는 `sync_period`(N 커밋 또는 T ms)로 정하고
  **관측 가능**해야 한다. 미결 꼬리(torn tail) 규칙은 그대로다.
- **관측**: `store_usage()` 에 `sync_policy`·`sync_level`·`sync_pending`·`last_sync_at` · 등급 변경/강등은
  **로그 1회** · `flush()` 뒤 `sync_pending == 0` · 숨기거나 0 으로 반올림하지 않는다.
- **플랫폼 표**: macOS `F_FULLFSYNC` · Linux `fdatasync`(없으면 `fsync` 강등 + **기록**) · 알 수 없는 플랫폼은
  `media` 요구를 **거부**하고 조용히 `cache` 로 안 내려간다.
- **바뀌지 않는 것**: 줄 → sync → view 순서 · 미결 꼬리 규칙 · 재생 결정성 · 커밋 1회 = 리비전 1회 ·
  **기본 동작 불변**(F1 계약 시험 ② “append 1회당 fsync 정확히 1회”는 기본 등급의 계약으로 남고, `batched` 는
  별도 시험을 갖는다 — 안 그러면 F3 이 F1 의 시험을 깨뜨린다).

### 35-5. 오너 결정 D-F3-1~4(초안 §8)과 계약 시험 후보 7건

초안은 답을 강요하지 않고 **권고와 대가를 함께** 적었다: **D-F3-1** 기본 등급(`cache` 유지 + 이름 정정 권고) ·
**D-F3-2** `media` 를 준다면 단위(대화별 옵트인 권고) · **D-F3-3** `batched` 를 **하지 않는다** 권고(이득 2 %p vs
되돌릴 수 없는 약속) · **D-F3-4** 관측 위치(`store_usage()` + 로그 1회 권고). 계약 시험 후보 7건은
① 기본 등급 sync 1회 고정 ② batched 는 줄이 먼저 ③ 창 관측 ④ `flush()` 뒤 창 0 ⑤ 강등이 리포트에 남는다
⑥ 크래시 시뮬레이션(마지막 창이 사라져도 재생 일관) ⑦ 불가능한 플랫폼에서 `media` 요구는 거부/명시 강등.

### 35-6. 한계(초안 §9 에도 적었다)

① **크래시 유실은 실측할 수 없다**(전원 손실 필요) — 창은 규칙으로 정의했고 시험 ⑥은 잘라내기로 간접 검증한다
② 지연은 디스크·FS·부하에 흔들린다 — 읽어야 할 것은 **비율과 계단** ③ 이 호스트에 `fdatasync` 가 없어 Linux 값은
문서 기반 ④ “미디어 보장 없음”은 플랫폼 **문서** 근거(실측이 증명한 것은 88배 비용 차이다).

> 지문은 **불변**이다: 이번 변경은 `docs/qa/…/nx10/fsync3/` 와 ADR 의 비규범 포인터 한 줄뿐이다 —
> `src/`·`scripts/`·`tests/` 쓰기 **0건**(4차 soak 계속). 본실행은 `FLUSH`·`FLUSH2` 뒤 · ADR 승인이 선행물이다.

## 36. `media` 를 핫패스 밖에서만 — 비용 모델과 간섭 실측(**D-F3-2 결정지 채움**) (2026-09-17 · 오너 지시)

지시: *“media 등급을 핫패스 밖(주기·체크포인트·셧다운)에서만 돌리는 대안을 비용 모델과 함께 비교해서,
D-F3-2 결정지를 채워줘.”* → 근거 [fsync4/MEDIA_OFFLOAD_COST_MODEL.md](./fsync4/MEDIA_OFFLOAD_COST_MODEL.md) ·
프로브 [run-a](./fsync4/probe-media-offload-run-a.json)/[run-b](./fsync4/probe-media-offload-run-b.json) ·
계기·문서 계약 시험 **17건 passed**(계기 16 + 문서↔픽스처 대조 1). **코드는 안 썼다**(ADR 승인이 선행물) —
ADR 초안의 §3-3·§7·§8·§9 를 이 실측으로 갱신했다.

### 36-1. 비용 모델 — 호출은 **부피와 무관한 배리어**다(그래서 상각이 1/k 로 준다)

커밋 `k`개를 쌓고 `F_FULLFSYNC` 1회(교차 반복 4회 · 최소값). 바닥값(호출당 고정세) **4,383 / 4,216 µs**,
그 바닥값이 **가장 큰 호출(8.9 MB)에서도 67.1 % / 58.5 %** 다. 유휴 호출(쓸 것 없음)도 **4,119 / 4,013 µs** —
비용은 **호출당**이지 바이트당이 아니다. 이웃 파일에 dirty 64 MB 를 둔 상태에서 이 파일 호출은 **0.99× / 1.02×**
(남의 바이트를 지불하지 않는다). 부피 항은 **식별되지 않았다**: 판정이 실행마다 뒤집혔고(A 미관측 / B 관측),
그래서 점추정 대신 **상한 0.33/0.43 µs/KB + 민감도 열**로만 적는다.

주기 T초 정책의 커밋당 상각(run A 바닥값): T=1 s **7.25 µs**(예산 0.44 %) · 10 s **0.72**(0.044 %) ·
60 s **0.121**(0.0073 %) · 600 s **0.0121**(0.0007 %) · 3,600 s **0.002**(0.0001 %). 가장 나쁜 가정(0.5 GB/s)에서도
T=60 s 가 0.66 µs 다 — **비용은 결정을 가르지 않는다.**

### 36-2. 간섭 — “핫패스 밖”은 가정이 아니라 재야 할 주장이었다

605 ops/s 페이스(예산 1,653 µs)를 맞춘 쓰기 위에 배경 스레드가 `media` 를 부른다. **매 라운드 기준선을 끼워**
짝지어 비교(10라운드 × 4팔 × 2실행):

| 팔 | 중앙 Δ(A/B) | 최악 라운드 | >100 ms 밀림 | 밀림∩호출 | 배경 호출 최대 |
| --- | --- | --- | --- | --- | --- |
| 기준선 | 0 % / 0 %(604.5 ops/s) | 0 % | **0 / 0** | — | — |
| 같은 파일 200 ms | **−27.4 % / −2.2 %** | −78.2 / −34.9 % | 8 / 5 | **8/8 · 5/5** | 3.21 s / 0.13 s |
| 같은 파일 1,000 ms | **−0.44 % / −0.43 %** | −18.5 / −35.1 % | 0 / 2 | — / 2-2 | 2.79 s / 3.20 s |
| **다른 파일** 200 ms | −4.6 % / −1.8 % | −77.7 / −55.9 % | 6 / 6 | **6/6 · 6/6** | 3.24 s / 1.07 s |

세 문장: ① **밀림은 진행 중인 호출과 100 % 겹친다**(기준선에는 0건) — 평균이 아니라 구간으로 물었기에 보인다
② **다른 파일이어도 멈춘다** — 단위를 좁히는 것만으로는 보호가 안 된다 ③ **드물게 부르면 중앙 비용은 사라지고
(1,000 ms 팔 −0.43 %, 두 실행 일치) 스톨은 남는다** — 빈도는 주기로 줄이고, 스톨 자체는 못 줄인다.

### 36-3. 대안 다섯 비교 → D-F3-2 답

전역 주기(**기각**: 비용이 테넌트 수에 곱해지고, 다른 대화의 호출이 이 대화를 멈춘다) · 대화별 옵트인 주기
(조건부) · 체크포인트(**기각**: 핫한 대화는 회전하지 않아 **창이 무계** = 등급이 거짓말이 된다) · 셧다운만(보조) ·
**정지 감지 + 상한 `T_max`(권고)**. 조용한 창에서의 호출은 4.0–4.1 ms 이고 **아무도 안 멈춘다**(그 값은 soak 이
같은 디스크에 쓰는 동안 얻었다). 강행할 때는 **스톨을 관측에 남긴다**(`media_stall_us`).
`T_max` 의 값은 오너 선택(권고 60 s). 계약 시험 후보 ①~⑦ + **⑧~⑪**(조용한 창/상한 강행/옵트인 격리/스톨 관측).

### 36-4. 계기를 만들며 네 번 틀렸고, 잡은 것은 계기였다

① 워커가 `O_CREAT` 없이 열어 **스레드만 죽었다**(“0 호출”이 정상처럼 보였다 — 그 팔은 media 가 없는 팔이었다)
② 이웃 dirty 64 MB 를 남겨 OS writeback 이 뒤 실측을 밀었다(**기준선끼리 13 % 차이** → 원인 귀속 불가)
③ 팔을 순차 실행해 ①·②를 증폭했다(→ **라운드 짝짓기**로 교체) ④ “겹친다”를 계기 없이 추정했다(→ 구간 기록 추가).
계기 계약 시험 16건이 이 부류를 물고, **음성 대조군으로 확인**했다: 워커의 `O_CREAT` 를 빼면 정확히 그 시험 하나가 빨개진다.
더해 **17번째는 문서 자신을 겨눈다**: 이 글을 쓰면서 프로브를 한 번 더 돌려(`1,000 ms` 팔 추가) 픽스처가 바뀌었는데
표는 **옛 세대의 수치**를 들고 있었다 — `test_documented_numbers_match_the_recorded_runs` 가 문서의 수치를
픽스처에서 다시 계산해 **문자 단위로 대조**한다(음성 대조군: 한 수치를 옛 값으로 되돌리면 정확히 그 시험이 빨개진다).

### 36-5. 한계

① 크래시 유실은 실측 불가 ② 스톨은 **꼬리가 두껍다**(같은 팔이 −27 %/−2 %) — 그래서 한 수로 주장하지 않는다
③ `T_max` 값은 위험 선택이라 이 문서가 정하지 않는다 ④ 스톨 기제는 유휴 호출과 상관이 지지하는 **가설**이다.

> 지문 **불변**: 이번 변경은 `docs/qa/…/nx10/fsync4/` 와 `fsync3` 초안·이 대장·handoff·계획·러너북뿐이다 —
> `src/`·`scripts/`·`tests/` 쓰기 **0건**(사전 이미지 `a89dfd2d82cc…` · `7f3e4605da9d…` 와 **동일** 확인).

## 37. 4차 실행은 깨끗했는데 판정은 FAIL 이었다 — 판정기가 **없는 근거**를 집었다 (2026-09-17 · 오너 지시)

### 37-1. 실측: 지표도 실행도 귀속도 전부 통과였고, 판정만 FAIL

4차 8시간 실행(`run_nx10_soak.sh`, 2026-09-17 `03:25:56Z → 11:26:00Z`)의 사실관계:

| 항목 | 값 |
|---|---|
| 러너 블록 | `soak_seconds=28800` · `exit=0` · 벽시계 **28804s** |
| 지문 | 시작 `b6a74304…` == 종료 `b6a74304…` == **현재 트리** |
| 지표 | `all_pass=true` · SC-1~6 **전부 pass**(SC-6 `duration_s=28800.006` · `orphans=0` · `errors=0`) |
| 판정 | **FAIL** — 체인 ② 단계에서 멈춤(트리 무변경) |

FAIL 을 만든 검사는 **단 하나**였다: `③ 기대 지문 == 시작 지문`. 기대값이 `322b4d3b…` 였는데
그 지문은 **한 틱도 돌지 않은 예약**의 것이다.

### 37-2. 원인 — 판정기는 “마지막”을 “살아 있는 마지막”이라 믿었다

`latest_expected_fingerprint()` 는 `soak-schedule.txt` 의 **마지막** `expected_fingerprint:` 를 기대값으로 쓴다
(종전 결함 ①: 첫 매치를 썼다가 09-16 에 고쳤다). 그런데 그 파일의 마지막 두 블록은:

```
expected_fingerprint: 322b4d3b…
start_check_fingerprint: UNVERIFIED
aborted: true            # 2026-09-16T12:13:11Z — fingerprint unverifiable
```

즉 **중단된 예약**(`aborted: true`)이었고, 그 예약은 지문을 못 재서 시작조차 하지 않았다. 반면 4차 실행은
예약이 아니라 **즉시 실행**(`soak_control.sh run`)으로 시작됐고, 그 경로는 예약 이력에 **아무것도 남기지 않았다**.
그래서 판정기는 “철 지난/중단된 예약의 지문”과 “실제로 돌아간 실행”을 비교했고, 정상 실행이 FAIL 이 됐다.
없던 근거를 만든 것이 아니라 **있던 낡은 근거를 집은** 것이다.

### 37-3. 처방 셋(각각 커밋·계약 시험으로 고정)

| # | 무엇 | 파일 | 커밋 | 증거 |
|---|---|---|---|---|
| ① | **중단된 예약은 기대값이 아니다** · 살아 있는 예약이 없으면 러너가 스스로 기록한 시작 지문으로 내려가되 **출처를 문장으로 밝힌다** | `scripts/collect_soak_result.py` | `7e632ec7` | 자체 시험 **11/11**(중단 블록 2건 추가) · 계약 시험 3건 |
| ② | **즉시 실행이 자기 기대값을 스스로 적는다**(`_record_run_expectation`) — 계산 실패면 “주장하지 않는다” 로 남긴다 | `nx10/soak_control.sh` → `scripts/soak_control.sh` | `e840d07d` | 자기시험 **82/82**(⑬ 5건 추가, 종전 77/79) |
| ③ | 승격 체인 ② 단계가 **내용으로만** 판정을 받는다(러너 종료 뒤 수집 · 실행 트리에서 판정 · 판정 대상 명시) | `promote3/post_harvest_sequence3.sh` | `de50af93` | 리허설 6케이스 **ALL PASS**(실제 산출물 포함) |

②는 **처방 쌍**의 앞쪽이다: 판정기가 “마지막 살아 있는 블록”을 쓰므로, 즉시 실행의 블록이 **마지막**이어야
새 실행이 낡은 예약을 덮는다(자기시험 ⑬ 이 그 순서를 실제로 확인한다).

### 37-4. 4차 실행의 PASS 는 **어떻게** 기록됐나(정직하게)

판정기 결함이 남아 있던 시점에, 나는 트리를 **한 바이트도 건드리기 전에** 판정을 다시 받았다:

```
.venv/bin/python scripts/collect_soak_result.py --seconds 28800 \
  --expected-fingerprint b6a74304dbd21148e83e7e4f4920068568a73e8166bce86c30828ea0890da5c8
→ 판정: PASS · collected_at 2026-09-17T11:32:13Z · 산출물 soak-recovery-20260917T032556Z.json (+ latest)
```

- `--expected-fingerprint` 는 판정기가 **스스로 “사람이 지정”** 이라 출력하는 정식 통로다(조용한 우회가 아니다).
- 왜 그 시점이 유일했나: `③ 지금 트리 == 시작 지문` 은 **측정 후 코드 무변경**을 요구한다. 판정기를 고치는
  순간(그것이 `scripts/` 편집이다) 이 검사는 설계상 거짓이 된다 — 즉 **어떤 편집 뒤에도 4차 실행은 PASS 가 될 수 없다**.
  그래서 순서가 강제된다: **판정 → (그 뒤에) 수정**.
- 원문 txt(`soak-harvest-20260917T112611Z.txt`)는 그 이전(결함 있는) 판정의 글이고, **판정의 출처는 JSON** 이다.
  체인은 이 차이를 만나면 “[참고] 원문 txt 는 이 JSON 보다 오래됐다” 를 기록에 남긴다(읽는 사람을 속이지 않기 위해서).

### 37-5. 계기에서 두 번 더 틀렸고, 두 번 다 “시각”이 원인이었다

① 내가 처음 쓴 짝 검사(“새 JSON + 옛 txt 를 거부”)는 **방향이 반대**였다 — 판정기를 직접 돌리면 JSON 만 새로
쓰이고 txt 는 남으므로, 더 새로운 판정이 **더 낡은 것처럼** 보였다(체인이 대기 루프에 갇힌 것으로 드러났다).
② 그 검사를 만들게 한 전제 자체가 틀렸다: **mtime 은 쓰기 순서가 아니다** — 프리커밋 훅이 `git stash`/`restore`
로 파일을 다시 쓰면서 시각을 바꾼다(이 대장의 JSON 이 그랬다). 그래서 최종 규칙은 **내용만** 본다.

### 37-6. 지금 걸려 있는 것(무인)

| 화면 | 무엇 | 상태 |
|---|---|---|
| `nx10promote3` | 3차 배치: 판정 수용 → 승격 5건(sha256 동일) → 커밋 → 필수 23개(~19분) | 실행 중(`04. 승격 위치 게이트` 단계) |
| `nx10batchchain` | `SC6 → PERF → FLUSH → FLUSH2` 각각 적용·커밋·게이트 23개 → **새 8시간 soak 재장전** | 앞 단계 대기 중 |

새 soak 은 `soak_control.sh run`(즉시 실행)으로 시작되며, 이번에는 **그 실행이 자기 기대 지문을 적는다**(처방 ②) —
8시간 뒤 회수가 같은 거짓 FAIL 을 반복하지 않는다.

> 지문: 이번 변경은 `scripts/collect_soak_result.py`·`tests/test_soak_recovery_judge.py` 를 움직였고
> (측정 트리 `b6a74304…` → 승격 뒤 새 지문), 그 뒤 게이트가 **새 지문에서** 다시 재어진다(체인 ⑤~⑦).

## 38. 세션이 죽어 멈춘 승격을 이어받았다 — 그리고 승격이 **자기 호출자를 고아로** 만든 것을 찾았다 (2026-09-18 · 오너 지시)

### 38-1. 실측: 12:19Z 에 모든 것이 멈춰 있었다(화면 0개)

4차 실행 회수 뒤의 무인 체인(§37-6)은 **커밋 직전**에서 죽어 있었다. 남은 상태를 그대로 읽었다:

| 확인 | 값 |
|---|---|
| 화면·프로세스 | **0건** — 재부팅으로 승격 체인·배치 체인·감시·회수 대기가 전부 사라졌다 |
| HEAD | `de50af93`(내 체인 수정) — **승격 커밋이 없다** |
| 인덱스 | 승격 5건이 `git mv` 로 **스테이징된 채** 남아 있었다(`R` 5건 + 기록 `A` 4건) |
| 판정·게이트 | 회수 `PASS`(수집 `11:32:13Z`) · 승격 위치 게이트 A·B·C 초록(`18 passed in 258.71s`) · 그러나 `gate-report-promote3.json` **없음** |
| 배치 체인 | `12:13:47Z` 에 다시 걸렸다가 `12:19:48Z` 에 **②관문에서 멈춤**(사유: 3차 게이트 리포트 부재) — 즉 **옳게 멈췄다**(쓰기 0건) |

승격 자체는 성공했고(이동 5건 sha256 동일 · 백업 `/tmp/nx10-promote3-backup-20260917T121211Z`), 죽은 곳은
`post_harvest_sequence3.sh` ⑤커밋의 **한가운데**였다. 그래서 이어받을 일은 “승격”이 아니라 **커밋 → 게이트 → 배치 체인**이다.

### 38-2. 이어받기 전에 찾은 결함: 승격이 옮긴 도구를 **부르는 쪽은 안 옮겼다**

배치 체인을 그대로 걸기 전에 그 체인의 재장전(7단계)을 읽었더니, 이렇게 되어 있었다:

| 파일 | 승격 뒤 상태 |
|---|---|
| `batchchain/run_batch_chain.sh` | 통제 도구를 `$NX10/soak_control.sh` 로 **6곳**에서 부르고, 감시 화면도 `docs/…/soak_watch_loop.py` 를 띄운다 |
| `promote3/post_harvest_sequence3.sh` | 판정 대기·재장전에서 같은 경로 4곳 |
| `promote3/after_promotion3.sh` · `promote2/post_harvest_sequence.sh` | 같은 경로(각 3곳·1곳) |

그리고 **세 파일의 사본은 그 시각 존재하지 않았다**(승격이 `mv` 이므로). 실패의 모양이 문제다 —
배치 체인은 그 경로를 **재장전에서만** 쓰므로 **4개 배치를 적용·커밋하고 필수 게이트를 네 번 잰 뒤에야**
`파일 없음` 으로 멈춘다. 밤을 걸어 가장 비싼 자리에서 실패하고, 트리는 반쯤 옮겨진 채 남는다.

이 부류는 “옮겼으면 부르는 쪽도 같이 옮겼는가” 하나이고, 판정 기준은 문장이 아니라 **파일의 존재**다.
그래서 호출자를 승격 위치로 바꾸고(존재 확인을 붙여), 그 문장을 계약 시험으로 고정했다.

### 38-3. 계약 시험 `batchchain/test_chain_tool_paths_contract.py` — 7건, 이빨 3개

| # | 문장 | 이빨(음성 대조군) |
|---|---|---|
| 1 | 레인의 **모든** 셸 스크립트가 대상 도구를 실재하는 경로로만 부른다 | 변수를 펼친 뒤 호출이 **8건 미만이면 실패** — 정규식이 무력해져 초록이 되는 것을 막는다 |
| 2 | 재장전은 승격 위치를 지목하고 **preflight 앞에서** 존재를 확인한다 | 옛 동작(존재 확인이 뒤)에서 빨개진다 |
| 3 | 러너북의 감시 명령도 승격 위치를 쓴다 | 문서 사본 경로가 들어오면 빨개진다 |
| 4 | 승격된 도구를 옛 경로로만 부르면 잡힌다 | 합성 스크립트 2건 → 정확히 2건 문제 |
| 5 | **변수 형태**(`bash "$CONTROL"`)로 옛 사본을 가리켜도 잡힌다 | 이 형태가 검사에서 빠지면 계약이 헛돈다 |
| 6 | 승격 위치를 먼저 보는 가드는 통과한다 | 계약은 “실재성”이지 “사본 금지”가 아니다 |
| 7 | 주석 속 사용 예시는 호출이 아니다 | 문서가 시험을 떠받치지 않게 |

검사기가 **인쇄문을 호출로 오해**하는 것도 실제로 잡았다: `promote2/apply_promotion2.sh` 의
`echo "  bash docs/…/soak_control.sh preflight"` 두 줄이 그렇게 걸렸다 — 그래서 “명령 위치 표시
(`^`·`&&`·`||`·`;`·`(`·`then`/`do`) 뒤의 `bash` 만 호출로 본다”는 규칙을 넣었다.

### 38-4. 체인 리허설의 **거짓 빨강**도 하나 고쳤다(계기 결함)

`rehearse_chain.sh` R4 는 본 운영 기록이 **비어 있어야** 통과했다(`[ -s batchchain-record.md ] && fail`).
그 검사가 쓰일 때는 실제 사고가 아직 기록되지 않았기 때문인데, §37 의 사고가 `batchchain-record.md` 에
남은 뒤로는 **정상 기록을 오염으로 오판**해 빨개졌다. 계약은 “비어 있다”가 아니라 **“리허설이 건드리지 않았다”**
이므로 **내용 해시 비교**로 바꾸고, 해시 비교가 실제로 한 바이트 차이를 감지하는지 확인하는 이빨을 붙였다.
결과: 리허설 **ALL PASS**(R1 `--plan` 부작용 0 · R2 즉시 거부 · R3 상한 초과 · R4 쓰기 전 관문 + 기록 무변화 · R5 관문<첫 적용).

### 38-5. 이어받은 순서와 산출물

| 단계 | 결과 |
|---|---|
| ① 승격 커밋 | `a1c6387f` — `test(nx10): promote the soak watcher and control tools under the gates` (이동 5건 + 기록 4건, 인덱스에 남아 있던 그대로) |
| ② 호출자 경로 수정 | `8d762c3e` — 체인 4개 + 러너북 + 계약 시험 7건. **지문 불변 확인**(`af462f78…` 커밋 전 == 커밋 후 → `docs/` 는 지문을 움직이지 않는다, 실측) |
| ③ 필수 23개 재측정 | `screen nx10gates3`(`21:19:42Z` 시작) → `gate-report-promote3.json` |
| ④ 배치 체인 | `SC6 → PERF → FLUSH → FLUSH2` 각각 적용·커밋·게이트 → **새 8시간 soak 재장전** |

### 38-6. 남는 교훈

① **승격의 완료 조건은 “옮겼다”가 아니라 “부르는 쪽이 산다”** 다. 이동표·해시·게이트가 다 초록이어도
호출자가 죽어 있으면 그 배치는 실패다(그리고 이번엔 **가장 늦게** 실패했다).
② **무인 체인의 실패 지점은 어디서 터지는지로 평가해야 한다** — 같은 결함도 재장전에서 터지면 밤을 태운다.
그래서 게이트가 아니라 **경로 실재성**을 정적으로 먼저 재는 시험이 필요했다.
③ 오늘의 결함 셋(판정기의 없는 근거 · 승격의 고아 호출자 · 리허설의 빈 파일 요구)은 모두
**“문장을 근거로 삼은 검사”** 였다. 셋 다 **파일·내용**을 근거로 바꾸면서 닫혔다.

### 38-7. 세 번째 결함 — 승격이 코드를 **검사 대상 안으로** 옮기는데, 승격 게이트는 그 검사를 안 했다

새 지문에서 필수 23개를 재는 첫 회차가 `python-basedpyright` 에서 **28 errors** 로 빨개졌다(기록:
[promote3/promote3-basedpyright-fail.txt](./promote3/promote3-basedpyright-fail.txt)). 실패는 회귀가 아니라
**승격의 부작용**이다 — 필수 게이트는 `src/ scripts/` 를 검사하므로 옮겨진 파일이 **그 순간 검사 대상이 된다**.
그런데 승격 게이트 C 는 `ruff check`·`ruff format --check` 만 돌렸다(`docs/` 에 있던 동안 아무 게이트도
안 보던 코드라, 타입 주석이 미준비 상태였다). 오류의 성격도 전형적이다:

| 무엇 | 왜 났나 | 고침 |
|---|---|---|
| `object` 로 적힌 표본 행 10곳 | JSON 에서 온 dict 를 `dict[str, object]` 로 두어 숫자 읽기가 전부 인자 오류 | `Any`(출처가 JSON 이고 실제로 그렇다) |
| `allowed_rate` possibly unbound 2곳 | 예산 줄이 안 나오는 경로에서 나중 비교가 미바인딩을 읽을 수 있었다 | 선언을 분기 앞으로 + `is not None` 가드 |
| `import soak_watch` implicit-relative 1곳 | `scripts/` 는 패키지가 아니라 스크립트다 | 파일 머리에 `# pyright: reportImplicitRelativeImport=false` + 사유 문장 |

그리고 **같은 부류를 막는 수정**을 함께 넣었다: 승격 게이트 C 가 **필수 게이트와 같은 명령**
(`uv run --isolated --frozen … basedpyright … --level error`)을 **승격 전에** 돌린다. 이렇게 하면 다음 승격은
“옮긴 뒤 20분 지나” 가 아니라 **옮기기 전에** 빨개진다(커밋 `22d653c9`). 검증: basedpyright **0 errors** ·
승격 위치 계약 시험 **18 passed** · 두 도구 자기시험 **ALL OK** · ruff check·format 통과.

> 이 결함은 2차 배치에서 **같은 모양으로 한 번 났었다**(승격 뒤 `basedpyright` 가 새로 빨개짐 — 그때는
> `restore_rehearsal.py`·`rollback_rehearsal.py` 의 타입 12건). 그때는 **고치기만** 했고 게이트에 검사를
> 넣지 않았다. 그래서 같은 부류가 3차에서 다시 났다 — 이번에 게이트가 바뀐 이유다(재발 방지는 고침이
> 아니라 **검사를 옮기는 일**이다).

### 38-8. 체인을 걸기 **전에** 배치들의 가드를 실제로 물려 봤다(쓰기 0건)

무인으로 4개 배치를 넘기는 일이라, 걸기 전에 각 배치의 `--dry-run` 으로 **순서 규칙이 살아 있는지** 확인했다:

| 배치 | dry-run 결과 | 뜻 |
|---|---|---|
| `SC6` | **지금 적용 가능**(동결 가드 통과 · 사전 이미지 일치 · 자체 점검 초록) | 첫 배치 |
| `PERF` | **거부** — “`scripts/val02_staging.py` 가 SC6 **이전** 바이트다” | SC6 가 먼저여야 한다 |
| `FLUSH` | **거부(exit 6)** — “배치 PERF 가 아직 승격되지 않았다 … 순서: 회수 → 3차 → SC6 → PERF → FLUSH” | PERF 없이는 `FLUSH` 하나로는 **아무것도 적용되지 않는다** |

즉 “soak 끝나면 `FLUSH`·`FLUSH2` 를 걸어 달라”는 요청을 문자 그대로 받으면 **exit 6 으로 멈춘다** — 그래서
체인의 순서는 취향이 아니라 **코드가 강제하는 제약**이다(전부 쓰기 0건으로 확인).
