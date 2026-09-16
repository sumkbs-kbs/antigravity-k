# NX-10 handoff — 후보 고정 · 필수 게이트 실행

상태: **REVIEW** (GO 아님 — required 5개 not_run, owner 허용 기록 없음)
작성: 2026-09-16 · 카드: `docs/18` §NX-10 / `docs/19` §NX-10

## 1. 30초 요약

- 후보를 고정하고(HEAD `20d529fc`) 필수 게이트 **23개를 전부 실행**했다: **22 passed · 1 failed · 0 not_run**.
  실패 1개는 `python-tests` 전량(`4 failed, 6562 passed, 14 skipped`)이고 **그 4건은 모두 타 레인
  커밋에 귀속된다**(§7 — 실행해서 확인: 커밋된 트리만 비교하는 계약 테스트).
- `clean-machine-runtime` 은 SCOPE 가 `BLOCKED_EXTERNAL` 로 적었지만 **그 사유가 틀렸다** — 호스트 청결
  검사가 아니라 **클린룸 재현 검사**다. 실제로 돌려 **passed**(8단계: uv sync · CLI · API E2E 24s · wheel ·
  신규 venv 설치 · 아티팩트 검증). 단 이 green 은 **HEAD 의 것**(스크립트가 `--ref HEAD` 를 export)이다.
- 게이트가 **이 카드 이전 NX 작업이 만든 순환 임포트 6건**과 중복 cast 7건, bandit 1건을
  잡아냈고, 셋 다 고쳤다(§4 — 억제가 아니라 의존 방향 분리).
- NX-09 가 남긴 **F04(서빙 번들 신선도)를 원인 확정 + 해소**했다: 커밋된 `dashboard_dist`
  가 낡아 `dashboard-build` 가 `tree_moved` 로 끝났고, 번들을 다시 만드니 같은 게이트가
  통과했다(§5).
- 판정은 **NO-GO 로 남긴다**(§9). 이 attempt 는 “출시 준비 완료”가 아니라 “판정 가능한
  상태 + 대장”을 만든 것이다.

## 1.5 마감 절차 (soak 회수 → 커밋 → clean-machine)

**[CLOSURE_RUNBOOK.md](CLOSURE_RUNBOOK.md)** 가 그대로 실행 가능한 순서를 소유한다. 거기서 먼저 봐야 할
두 가지: ① 커밋해도 `python-tests` 빨간 4건은 초록이 되지 않는다(CR-14 울타리 이동·EX-05 승격 — 둘 다
타 레인/오너의 일이고, 우리가 커밋하면 HEAD 가 오히려 멀어진다), ② 그럼에도 **커밋은 지문을 옮기지
않는다**(`worktree_fingerprint` 는 코드 파일 **내용** 해시라 커밋으로 변하지 않는다) — 22:00 soak 의
기대 지문이 그대로 유효하다.

## 2. 산출물 (읽는 순서)

| 파일 | 내용 |
|---|---|
| `nx10/SCOPE.md` | **측정 전** 동결한 범위·게이트·skip 사유·전제조건(수정하지 않았다) |
| `nx10/SCOPE_ADDENDUM.md` | 동결 **이후** 바뀐 것과 그 이유(코드 수정·번들 재생성·추가 실행) |
| `nx10/GATE_LEDGER.md` | 23개 게이트의 attempt별 대장 · 결함 귀속표 · **단일 창 재실행(§9)** · **soak 리허설과 차단 요소(§10)** |
| `nx10/EX05_PROMOTION_CONFLICT.md` | EX-05 승격 충돌 **오너 판정 브리프**(증거 4단계 · 선택지 A/B/C · 적용할 1줄 수리안) |
| `nx10/gate-report-attempt001~015.json` · `gate-report-full001.json` | 러너 원본 리포트(지우지 않았다). `full001` = 전용 창 22개 한 번에 |
| `nx10/run_remaining_gates.sh` · `run_ambient_gate.sh` · `run_full_gates.sh` · `run_nx10_soak.sh` | 전용 창 실행기(게이트별 exit 를 `runner-exit.txt` 에 별도 보존) |
| `nx10/soak-60.json` · `soak-exit.txt` | 60초 soak 리허설(시작·종료 HEAD/지문 + exit 보존) |
| `nx10/gate_verify-boundary.txt` · `gate_verify-full001.txt` | 마감 도구(`ga_gate_verify.py`)가 지적한 경계 |
| `nx10/commands.txt` | 실행한 명령 전문(재현용) |

## 3. 이 카드가 마감 형태로 남긴 것 (단일 창 재측정 + 마감 도구)

쪼갠 측정(attempt 001~015)과 **별도로**, 전용 창에서 22개 게이트를 한 번에 돌려 **리포트 1개**를 만들었다:
`gate-report-full001.json` → **21 passed · 1 failed**(같은 지문 `da54e07b…`, 약 19분). 쪼갠 측정과 일치했다.
`ga_gate_verify.py` 를 그 리포트에 돌리면 **실패 이유가 정확히 2개로 나온다**:
`missing_required: clean-machine-runtime` · `required_red: python-tests`. 실행 명령은 `run_full_gates.sh`.

## 4. 이 카드에서 바꾼 코드 (후보 지문에 포함)

| 파일 | 변경 | 이유(게이트가 지적) |
|---|---|---|
| `engine/atomic_write.py` **(신규)** | `write_text_atomically` + fsync/replace seam 이동 | `vault ↔ vault_privacy` 순환 |
| `engine/vault.py` | 함수·헬퍼 제거, leaf 에서 재바인딩 | 위와 동일(동작·이름 유지) |
| `engine/vault_privacy.py` | 마스킹 저장을 leaf 에서 임포트(모듈 수준) | 위와 동일 |
| `security/ws_registry.py` **(신규)** | 인증 WS 레지스트리 + 폐기 헬퍼 이동 | `auth_routes ↔ session_state` 순환 |
| `api/routes/session_state.py` | 레지스트리 제거, 재내보내기 + `__all__` | 위와 동일(기존 이름 유지) |
| `api/auth_routes.py` | 폐기 헬퍼를 leaf 에서 임포트 | 위와 동일 |
| `engine/model_manager.py` | `from . import multimodal` → 직접 이름 5개, 중복 cast 1건 제거 | `engine/__init__ ↔ model_manager` 순환 + mypy |
| `engine/provider_adapters/inference_providers.py` | 동일(직접 이름) + 중복 cast 6건 제거 | 순환 4건 + mypy |
| `engine/tool_loop.py` | 동일(직접 이름) | 순환 예방(같은 패턴) |
| `api/routes/network_access_api.py` | `isinstance(ip, str)` 가드 2줄 | **기준선에서도 실패하던** mypy/basedpyright 2건 — 다른 레인 파일, 기록 남김 |
| `engine/summary_memory.py` | sha1 에 `usedforsecurity=False` | bandit B324(보안 용도 아님: 결정론적 id) |
| `tests/test_nx08_vault_durability.py` | seam 패치 대상 → `engine.atomic_write` | 위 이동에 따른 **시험 배선** 수정(의미 불변) |
| `src/antigravity_k/dashboard_dist/**` (61개) | 소스에서 **재빌드** | F04(§5) |
| `scripts/val02_staging.py` | SC-6 의 `orphan_wt` 를 제품 worktree 루트(`.ag_worktrees`)로 **범위 확정** + 헬퍼 추가 | NX-10-B4: 검사가 저장소 전역을 세어 타 작업의 `/tmp` worktree 로 fail(§7). **지문 이동 원인** |

**동작 변경은 없다** — 리팩터 + 타입 가드 + 해시 플래그 + 번들 재생성이다. 이것을 확인한
시험: `tests/test_nx08_vault_durability.py` · `test_nx05_auth_epoch_revocation.py` ·
`test_nx09_f03_multimodal_attachments.py` · `test_model_manager_stream.py` ·
`test_session_state.py` · `test_auth.py` · `test_sec03_ws_origin_ticket.py` ·
`test_auth_policy_truth_table.py` · `test_vault*.py` **192 passed**. 전량 스위트는 §6 에서 전용 창으로
돌렸고 결과가 나왔다(attempt 012·full001: `4 failed, 6562 passed, 14 skipped` — 실패 4건 모두 타 레인 귀속, §7).

## 5. F04 확정 — 커밋된 번들이 낡았다

- attempt 006: `dashboard-build` 가 빌드 자체는 성공(exit 0)했지만 상태가 **`tree_moved`**
  — 추적 중인 `dashboard_dist` 61개 파일을 덮어썼다.
- attempt 007(같은 명령 재실행): **passed**. 즉 빌드는 결정론적이고, **커밋된 번들이
  소스의 산출물과 달랐던 것**이 원인이다.
- 조치: 번들을 소스에서 다시 만들어 후보에 포함했다. 이제 서빙되는 SPA == 소스다.
  이 상태에서 `dashboard-e2e-witnesses` **30/30 passed**(attempt 008) — NX-09 가 “낡은
  번들 때문에 실 UI 증인이 흔들린다”고 남긴 조건이 제거됐다.
- **규칙(다음 카드가 지켜야 함)**: 대시보드 소스를 고치는 카드는 후보 동결 **직전에**
  `pnpm build` 를 다시 돌려 `dashboard_dist` 를 소스와 일치시킨다. 그렇지 않으면
  `dashboard-build` 가 `tree_moved` 로 끝나고, 동결된 지문이 실제 서빙물과 어긋난다.

## 6. 전용 창에서 돌린 게이트 (남은 not_run **없음**)

긴 게이트 3개는 `screen` 세션으로 분리 실행했다(게이트별 exit 를 `runner-exit.txt` 에 별도 보존):

```bash
screen -dmS nx10gates bash docs/qa/2026-09-16-followup/nx10/run_remaining_gates.sh
```

| 게이트 | 결과 | 값 |
|---|---|---|
| python-tests | **failed** (608s, exit 1) | `4 failed, 6562 passed, 14 skipped, 16 deselected` — 실패 4건은 전부 타 레인 귀속(§7) |
| python-benchmark | **passed** | `16 passed, 6580 deselected` (18.4s) |
| master-e2e | **passed** | 하네스 6단계 **6/6** (2.4s) |
| dashboard-e2e-ambient | **passed** (46.3s, exit 0) | main **16/16** · disclosure healthy 1 · exhausted 1 · hub 2 — 게이트가 **자유 포트 + 격리 서버**를 세우므로 상시 8012 와 경합하지 않는다 |

| clean-machine-runtime | **passed** (42.6s, exit 0) | 8단계 클린룸 재현 성공 — uv sync(locked) · 임포트 · CLI smoke · doctor · API E2E 24s · wheel 6.5M · 신규 venv pip install · 아티팩트 검증. **경계: `--ref HEAD` 를 export 하므로 이 green 은 HEAD(`20d529fc`)의 것이고, dirty 후보는 들어가지 않는다 — 커밋 뒤 재실행이 필요하다.** |

**not_run 0** 이다. 따라서 “돌릴 게 남았다”가 아니라 **“실패 1개를 어떻게 처리할지”만 남았다**.
그 실패(`python-tests` 4건)는 제품 결함이 아니라 거버넌스/계약 충돌이고, 처리 주체는
오너(EX-05 브리프)와 CR-14 레인(울타리 재선언)이다 — [EX05_PROMOTION_CONFLICT.md](EX05_PROMOTION_CONFLICT.md).

**이월(merge) 규칙**: `--merge-into` 는 **같은 SHA · 같은 manifest sha · 같은 지문**에서만
허용된다. 다음 창에서 코드를 한 줄이라도 고치면 지문이 바뀌므로 새 리포트로 남기고
이전 green 을 합산하지 않는다.

## 6b. 예약 통제 (2026-09-16 후속 창 — 사고 조치 + 도구)

**사고:** `pgrep -fl schedule_nx10_soak` 로 보니 **취소됐다고 기록한 예약 3건이 살아서 대기 중**이었다
(08:20Z·09:47Z·10:26Z). 취소 수단이었던 `screen -S nx10soak -X quit` 은 화면만 닫았고 `login -pflq`
래퍼가 SIGHUP 을 무시했으므로, 위쪽 cancel 기록 3건의 “시작하지 않았다”는 **사실이 아니었다**.
그대로 두면 22:00 에 4개가 동시에 깨어났다(그중 3개는 기대 지문이 낡아 드리프트로 멈췄겠지만,
같은 기록 파일에 동시에 append 하고, 같은 지문 예약이 둘이면 **soak 두 개가 동시에** 돌 수 있었다).
조치: 세 트리를 SIGTERM 으로 종료하고 `ps` 로 소멸 확인 · 10:47Z 예약도 함께 내림(대기 중 스크립트
편집은 그 자체로 위험) · 그 뒤 도구를 만들어 **재장전**.

**같은 점검에서 나온 두 번째 결함:** 예약 스크립트의 시작 지문 검사가 PATH 의 `python` 에 의존했다.
이 기기의 `/usr/bin/python3` 는 3.9.6 이라 `ga_gate.py` 의 3.12 문법을 파싱하지 못해 지문이
`UNVERIFIED` 가 된다 — 그 PATH 였다면 **22:00 에 아무것도 하지 않고 중단**(8시간 창 손실). 지문 계산을
`.venv/bin/python` 으로 고정하고, `UNVERIFIED` 는 드리프트보다 **먼저** 막도록 바꿨다(`exit 3`).

**도구:** [soak_control.sh](soak_control.sh) — `arm`(지문을 지금 트리에서 계산) · `status`(단일 예약·고아·
지문 일치를 한 화면에) · `cancel`(트리 단위 종료 + **검증**) · `orphans` · `preflight`(발화 전 10개 점검) ·
`selftest`(**32/32**, 약 2분, 임시 디렉터리에서 사고를 재현). `preflight` 는 **8시간이 끝나도 결과를
후보에 귀속할 수 있는가**를 미리 묻는다 — `현재 트리 지문 == HEAD 트리 지문`(`tree_fingerprint_of_commit`)을
직접 확인하고, 인터프리터·러너 자산·`/tmp` 여유·이미 도는 soak 까지 함께 본다(실측: 10/10 OK). 예약 잠금은 `mkdir` 원자성이고(두 번째 예약은 `exit 2`),
러너에도 별도 실행 잠금이 생겼다(이미 soak 이 돌면 `exit 5`, 리포트 미생성).
사고·한계·자기시험이 잡은 결함 4건(macOS `tac` 부재 · 예약 1건이 프로세스 2개로 보이던 오탐 ·
가짜 프로세스가 파이프를 물고 있는 문제 · heartbeat 중복)은
[SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) 가 소유한다.

**세 번째 결함(이 창에서 발견·수정): 회수 판정기가 “첫 예약”을 읽었다.** `soak-schedule.txt` 는 예약할
때마다 블록을 덧붙이는데, `scripts/collect_soak_result.py` 의 `expected_fingerprint()` 가 `re.search`
(= 첫 매치)로 기대값을 잡아 **철 지난 예약**(`157311cf…`, 08:20Z)을 썼다. 그대로면 밤새 정상으로 끝난
8시간 실행이 ③(기대 == 시작)에서 **거짓 FAIL** 로 판정된다 — 이 카드가 반복해서 겪은 “지표는 PASS 인데
귀속이 어긋나 판정 근거가 사라짐”과 같은 종류다. 마지막 예약을 쓰도록 고치고(출처를 출력에 문장으로
남긴다) 계약 시험 1건 + 자기시험 3건으로 고정했다(자기시험 **9/9**). 커밋 **`1bd95e7d`**(코드 2파일만,
`git add -A` 0회, 훅 통과). 판정기가 `scripts/` 라 지문이 `92fcaeb5…` → **`322b4d3b…`** 로 이동했고,
작업 트리 지문 = HEAD 트리 지문(실측) → 그 지문으로 **필수 23개(clean-machine 포함) 재측정**을 돌렸다.

**재장전:** 위 수정 전 상태는 `soak_control.sh arm --at 22:00`(2026-09-16T11:39:27Z, 기대 지문 =
당시 트리 = `92fcaeb5…`, 단일 예약 pid 79230, 종료 예정 `~06:00 KST`, `status` exit 0)이었다.
판정기 수정이 지문을 옮겼으므로 그 예약은 **재측정 뒤 `cancel`(검증) → 새 지문으로 `arm`** 으로 다시 세운다
(취소 기록은 `soak-exit.txt`, 새 기대 지문·대기는 `soak-schedule.txt` 가 소유 — 이 문서에 값을 쓰지 않는다).
이 창은 이후 `docs/` 만 수정한다.

## 7. 아직 열려 있는 것 (이 카드가 건드리지 않음)

| 항목 | 상태 | 소유자 |
|---|---|---|
| owner 허용 기록(NX-00 INCONCLUSIVE · NX-01~06/08 REVIEW · NX-06 cluster BLOCKED · NX-09 F03 수정·F04 닫힘) | **없음** — 기록 전에는 GO 선언 불가 | 사용자/오너 |
| 손상된 대화의 격리·폐기 절차 | **문서화 + 프로브 완료**(2026-09-16, 이 카드): 제품은 읽기·삭제 모두 fail-closed 라 **삭제도 409**로 거절됨을 실측(view 손상 `ConversationIntegrityError` / journal 손상 `ConversationHistoryCorruptError`), 운영 절차 = 서비스 정지 → 파일 2개를 **저장소 루트 밖**으로 격리 이동 → `write_deletion_marker` → 기동(실측: `deleted=True`·`get()=None`·id 재사용 금지·원본 바이트 보존). **⚠ 루트 안에 격리하면 `legacy_requires_migration` 이 되어 무관한 대화까지 읽기 실패**(실측). 근거 [nx02/damaged-conversation-disposal.md](../nx02/damaged-conversation-disposal.md) · `repro_corrupt_disposal.py` · `corrupt-disposal-output.txt` · [09 운영 가이드](../../../09_OPERATION_GUIDE.md). 남은 것은 사람: **실저장소 리허설·소유자 지정·제품 flag(A안) 채택 여부·격리본 보존 기간** | 미정(절차는 이 카드가 마감) |
| cue lexicon 회수율 | NX-01 이 넘긴 그대로 | 미정 |
| SC-1~6 soak(28,800s) | **오늘 22:00 KST 예약 실행(커밋된 후보 트리)** — `soak_control.sh arm` 으로 걸었다(`screen nx10soak`). 목표 `2026-09-16T13:00:00Z`, 기대 지문 = 현재 트리 = `92fcaeb5…`, 종료 예정 `~06:00 KST`. 시작 전 지문이 기대값과 다르면 **8시간을 쓰지 않고 중단**(exit 2), 계산 자체가 실패하면(`UNVERIFIED`) 더 먼저 중단(exit 3). 기록: `soak-schedule.txt`·`soak-schedule.log`·`soak-exit.txt`·`soak-28800.json`. **그때까지 코드를 건드리지 않는다.** 예약 확인·취소는 `soak_control.sh status`/`cancel` 로만 한다(§6b — `screen -X quit` 은 취소가 아니었다). 1·2차 실행은 아래처럼 중단됐다 |
| (1·2차) SC-1~6 soak | **1차 중단(오너 판정, 19분 51초)** · **2차 중단(오너 지시로 22:00 예약 실행으로 이동, 3분 39초)** — `2026-09-16T07:41:42Z` 에 SIGTERM, 러너가 `exit: 143` 을 기록(러너 줄과 운영자 중단 기록을 구분해 `soak-exit.txt` 에 남김). 사유: 후보 코드를 더 고치므로(SSE 폐기·quota·GC) 종료 지문이 최종 후보와 달라져 카드의 지문 일치 조건을 못 맞춘다 — 8시간을 써도 판정 근거가 안 된다. 러너는 종료 시에만 리포트를 쓴다(중단 시점 부분 산출물 없음). **작업디렉터리는 유지**: `/tmp/nx10-soak-work-20260916T072151Z` | **동결 후 1회 재실행**(러너 그대로) |
| 보조도구 승격(`docs/` → `scripts/`·`tests/`), **승격 트리에서 필수 게이트 재측정** | **완료**(2026-09-16, 오너 판정 B): 이동·게이트 7/7(09:46:05Z) → 필수 22개 재측정 **`gate-report-promote002.json`: 21 passed · 1 failed(타 레인 4건) · 0 not_run**, 시작 = 종료 = `0f345d0c…`, 마감 도구 문제는 옛 지문과 동일한 2개(→ 승격이 만든 새 실패 0). `.gitignore` 규칙 포함(GP 검사기 WARN 종결). 첫 두 시도는 **이동 0건으로 롤백**됐고(스테이징 루트 오산 · 검사기의 `parents[4]` 가정), 그 과정에서 리허설·본실행이 표·게이트를 공유하게 됐다. 기록 `promote/promotion-applied.txt`. (이전 상태: 계획 + 리허설 완료, 본실행은 동결 해제 뒤) — 도구 3종(`verify_docs_commands.py`·`collect_soak_result.py`·`cue_lexicon_probe.py`)과 계약 시험 3종이 `docs/` 안에 있어 **어떤 게이트도 지키지 않는다**(정적 검사는 `scripts/`, 스위트는 `tests/`). 이동표·해시·순서 함정: [PROMOTION_PLAN.md](PROMOTION_PLAN.md). **미러 트리 리허설 ALL PASS**(`promote/dry-run-output.txt`: 이동 전 초록 · 승격 위치 초록 · ruff check/format · 이빨 3건 1:1 · 스테이징 사본 0건) — 리허설이 **거짓 FAIL 2건**을 먼저 잡았다(미러 `tests/` 를 골격으로 줄여 링크 검사가 깨짐 · 그 오염이 이빨 판정을 1:1 이 아니라고 오판). 본실행: `promote/apply_promotion.sh`(전제조건·롤백·증거 기록 포함) | 이 카드(계획·리허설) → 실행은 순서 결정 뒤 |
| **승격 vs soak 순서** | **결정: B**(오너, 2026-09-16 18:35 KST) — 지금 승격하고 22:00 예약을 승격 트리로 재장전했다. **재장전은 두 번**(`soak-schedule.txt` 블록 2·3): `09:47:11Z`(`ab980ba5…`), 그리고 게이트 재측정 뒤 `10:26:34Z`(**`0f345d0c…`**, 대기 9,205초). 두 번째 재장전의 이유는 측정 중 편집으로 지문이 갈렸기 때문이고(순서 교훈은 [CLOSURE_RUNBOOK.md](CLOSURE_RUNBOOK.md) §5b), 그 사실을 `soak-exit.txt` 에 러너 기록과 구분해 남겼다. 취소된 옛 예약·이유는 `soak-exit.txt` 에 러너 기록과 구분해 남겼다. (이전 상태: **결정 필요** — 승격은 지문을 바꾸므로 예약 22:00 soak 과 순서를 정해야 한다: **(A)** soak 뒤 승격(쉽지만 그 8시간은 승격 전 트리를 잰 것) / **(B)** 승격 먼저 + 22:00 재장전(같은 트리에서 전부 잼, 대가는 게이트 재측정 ~19분). 권고 **B** — [PROMOTION_PLAN.md](PROMOTION_PLAN.md) §4. 승격하면 예약 실행기는 지문 불일치로 스스로 중단하므로 **반드시 재장전**해야 한다 | 오너(이 카드가 선택지를 준비) |
| **커밋**(오너 지시) | **완료**(2026-09-16): 3분할 — `d929da01`(후보 코드+계약+승격 도구+`.gitignore`) · `6417690e`(대시보드 소스·번들·SBOM) · `89dd383b`(증거·문서). 경로 명시 스테이징(`git add -A` 0회) · 훅 우회 0회 · 1MB 초과 게이트 리포트 4개는 정책을 우회하지 않고 `large-evidence-manifest.md` 에 sha256 으로 식별 · `vault_data`(gitlink·소유 불명)는 **미커밋 유지**. 커밋이 지문을 옮겼다(`0f345d0c…`→`92fcaeb5…`: 삭제된 옛 번들 항목이 인덱스에서 빠짐) — 종전 문장을 실측으로 정정하고 재측정·재장전했다([CLOSURE_RUNBOOK.md](CLOSURE_RUNBOOK.md) §3.1·§3.1b) | 이 카드(완료) |
| `clean-machine-runtime`(커밋 전제) | **완료** — 커밋된 후보 `89dd383b` 에서 attempt `promote003` 이 이 게이트를 포함해 23개 완주: **22 passed · 1 failed · 0 not_run**, `clean-machine-runtime` **passed(43.7s)**. `ga_gate_verify` 문제는 이제 **`required_red: python-tests` 하나**([GATE_LEDGER.md](GATE_LEDGER.md) §14) | 이 카드(완료) |
| 코드 동결 배치(오너 판정) | **완료** — ① NX-05 SSE 실연결 폐기(실서버 before/after: 9프레임→폐기 1.112초+EOF, 계약 10 passed) ② NX-02 journal retention(soft 64 MiB 경고 / hard 512 MiB 507 거절, 자동 prune 없음, 계약 9 passed) ③ NX-03 tombstone GC(자동 만료 없음, 아카이브 이동 + 감사 JSON, 계약 6 passed). 지문 `c65fe0e1…`→**`157311cf…`** 로 이동. 이 지문에서 정적 4개 + 전량 스위트(4 failed·6587 passed, 실패는 타 레인) + 벤치 + 대시보드(888 tests, 빌드 결정론적) 재측정 — [BATCH_FREEZE.md](BATCH_FREEZE.md) | 이 카드(완료) |
| **교차 레인 충돌**: HEAD `20d529fc`(CR-14 문서 커밋)가 EX-05 를 PASS 로 승격하며 “귀속 UNVERIFIED” 문구를 지웠고, NX-07 계약 테스트 2건이 그 때문에 실패한다 | **미해결 — 오너 판정 대기**. 되돌리지 않았다(타 레인 소유 문서). 결정 브리프: **[EX05_PROMOTION_CONFLICT.md](EX05_PROMOTION_CONFLICT.md)**(증거 4단계 분리 · 선택지 A/B/C · 적용할 1줄 수리안 · 권고 B) | **출시 책임자(강병석)** |
| **CR-14 울타리 이동** — `test_cr14_fence_movement_detection` 2건: 선언된 후보 `b6003205`(지문 `02349a8d…`) 뒤에 코드 스코프 **38개 경로**를 건드린 커밋들이 생겨 HEAD(`20d529fc`, 지문 `2068e72b…`)와 달라졌다 | **미해결** — 커밋된 트리 비교라 이 카드의 미커밋 변경과 무관. CR-14 후보 재선언 또는 울타리 규칙 조정 필요(거버넌스) | CR-14 레인/오너 |
| F1(NFS flock/fsync)·G1(tombstone GC) | INCONCLUSIVE 유지(로컬 관측을 NFS 로 일반화하지 않는다) | — |
| NX-10 수용 “지원 환경별 한계·운영 runbook·복구 기록” | **작성 완료**(2026-09-16, 이 카드): [09 운영 가이드 §NX 운영 runbook](../../../09_OPERATION_GUIDE.md) — 지원 한계표·런타임 경로·**폐기 경로의 실제 범위**(열린 SSE 는 닫는 경로 없음)·SC-1~6 임계·**복구 리허설 상태**(restore·rollback·손상 대화 폐기 = 미실시/미결정). soak 실행 중에 추가했으며 `docs/` 는 지문 제외 대상이라 안전하다(§4 규칙). **확인:** 편집 뒤 작업 트리 지문을 다시 계산해 시작값 `c65fe0e1…` 과 **동일**함을 실측했다(게이트 제외 프리픽스 `FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")` — `scripts/ga_gate.py`) | 이 카드(완료) |

## 8. 필수 게이트 최종 상태

**동결 지문 `157311cf…` 에서 22개 중 21 passed · 1 failed · 0 not_run** (`gate-report-freeze002.json`,
`screen nx10freeze`, `2026-09-16T08:27:10Z`→`08:45:49Z` = 18분 39초; `clean-machine-runtime` 은 커밋을
전제하므로 제외). **러너가 기록한 지문은 시작·종료 모두 `157311cf…`** — 즉 22:00 예약 soak 의 기대
지문이 그대로 유효하고, 이 재측정이 후보를 움직이지 않았다. 마감 도구는 문제 **정확히 2개**를 지적한다:
`missing_required: clean-machine-runtime` · `required_red: python-tests`(`gate_verify-freeze002.txt`).
같은 창에서 `tests/test_nx07_doc_consistency.py` 를 다시 돌려 **2 failed / 24 passed** — 내 `docs/`
편집이 문서 정합성 실패를 새로 만들지도, 가리지도 않았다는 것을 확인했다.

이전(배치 이전 트리) 값은 **22 passed · 1 failed · 0 not_run**(23개 전부 required)이었다. 지문 주의: 22개 중 `python-tests` 는
**지문 `da54e07b…`** 에서 측정된 failed 이고(새 지문에서 재측정 안 함 — 실패 4건이 커밋된 트리의
계약 테스트라 결과가 지문에 의존하지 않는다), 나머지와 `clean-machine-runtime` 은 아래와 같다.
`da54e07b…` 기준 값은 아래와 같다(참고: full001 단일 창은 21/1/1 — 그때는 clean-machine 을 제외했다).
§7 의 하네스 수정으로 지문이 `c65fe0e1…` 로 이동했으므로, 그 지문에서의 재측정이 필요하다
(정적 4개 + `test_val02_conversation_multiprocess.py` 14 passed 는 이미 재측정 green,
`gate-report-newfp-static.json`). **E2E·대시보드·전량 스위트는 soak 종료 후**에 돌린다 —
동시에 돌리면 latency·RSS 측정이 서로를 오염시킨다.

실패 1개(`python-tests`)의 실패 4건은 **전부 타 레인의 커밋에 귀속되고, 커밋된 트리만 비교하는
계약 테스트**다(§7 — 실행해서 직접 확인: 후보↔HEAD 사이 코드 스코프 38경로 이동, EX-05 승격 계약).
그래도 **실패는 실패로 센다** — “우리 탓이 아니니 통과” 로 바꾸지 않는다.

## 9. 판정

**NO-GO (REVIEW 유지).** 근거:

1. required 1개가 **failed** 이다(카드 §수용: 실패 0 **그리고** not_run 0). 그 4건의 원인은
   다른 레인이지만, **카드는 원인별 면제를 제공하지 않는다.**
2. `not_run` 은 0 이지만, 그 대신 `clean-machine-runtime` 의 green 이 **HEAD 의 것**이라
   (dirty 후보는 그 스크립트에 들어가지 않는다) 후보 귀속은 커밋 뒤 재실행으로만 성립한다.
3. 카드 §선행의 비차단 허용 기록이 **없다**.
4. worktree 가 **dirty** 라 공식 후보 SHA 가 없다 — 커밋은 사용자 승인 사항이다.

남은 required 는 **둘뿐**이다: 커밋 뒤 `clean-machine-runtime` 재실행, 그리고 `python-tests` 의 빨간 4건
(오너 판정 + CR-14 후보 재선언). 둘 다 이 창이 코드로 닫을 수 있는 것이 아니다. 참고로 **손상 대화
격리·폐기 절차**는 이 창에서 문서화 + 프로브로 마감했다(§7, [nx02/damaged-conversation-disposal.md](../nx02/damaged-conversation-disposal.md)) —
남은 것은 실저장소 리허설·소유자 지정이다.

clean-machine 창이 열리고, 타 레인의 실패 4건이 정리되고(오너 판정 + CR-14 후보 재선언),
8시간 soak 의 판정 기준이 먼저 초록이 되면(§7) 그때 §9 를 GO/NO-GO 로 다시 쓴다. **측정된 green 을 “출시 준비 완료”로 확대 해석하지 않는다.**
