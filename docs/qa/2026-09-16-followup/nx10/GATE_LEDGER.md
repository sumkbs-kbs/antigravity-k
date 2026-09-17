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
| ↳ **2차 배치 상태**(2026-09-17T02:1xZ) | 미러 리허설 **재실행 ALL PASS**(14 passed · 이빨 2/2 · 스테이징 잔존 0) · 본 트리 쓰기 **0건** · 본실행은 **동결 가드 때문에 거절**(도는 soak pid 56261 → 이동 0건). 본실행 순서는 `post_harvest_sequence.sh`(대기 → 판정 → 승격 → 새 지문 게이트 23개 → 재장전) | [PROMOTION_PLAN.md §1c](PROMOTION_PLAN.md) · [CLOSURE_RUNBOOK.md §5-6](CLOSURE_RUNBOOK.md) |
| 승격 예약 | 리허설·경보 도구가 모두 `docs/` 안이라 **어느 게이트도 지키지 않는다** → 다음 승격 후보로 등록 | [PROMOTION_PLAN.md §1b](PROMOTION_PLAN.md) |

**지문 불변 확인**: 이 편집들은 `docs/` 안에만 있으므로 3차 실행의 시작 지문 `5c90b637…` 이 그대로 유효하다
(`docs/` 는 정적 게이트 지문 제외 구역 — `scripts/ga_gate.py` 의 `FINGERPRINT_EXCLUDED_PREFIXES`).
**판정은 변하지 않는다**: required red 1(`python-tests`, 타 레인) · CR-14 후보 재선언 없음 · owner 허용 없음.
