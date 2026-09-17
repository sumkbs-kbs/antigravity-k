# NX-10 handoff — 후보 고정 · 필수 게이트 실행

상태: **REVIEW/NO-GO**(GO 아님 — not_run **0개**으로 닫혔고, 남은 required red 는 `python-tests` 1개(타 레인)·
CR-14 후보 재선언 없음 · owner 허용 기록 없음. 최신 수치와 경로는 §12)
작성: 2026-09-16 · 최종 갱신: 2026-09-17 · 카드: `docs/18` §NX-10 / `docs/19` §NX-10

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
- **8시간 soak 은 실행됐고 FAIL 이다**(§10, 2026-09-16 21:13 KST → 05:13). 지표 미달은 **하나**: SC-6
  `rss_growth_mb 1683.5`(기준 64) — 원인은 `ConversationJournal.tail()` 이 매 append 3회 호출되면서
  journal **전체**를 파싱하는 것이다(8h 상태에서 append 814ms 중 810ms). **귀속은 성립**(start = end =
  기대 = 지금 트리 = `322b4d3b…`)하므로 이 실패는 제품 결함으로 귀속된다.

## 1.5 마감 절차 (soak 회수 → 커밋 → clean-machine)

**[CLOSURE_RUNBOOK.md](CLOSURE_RUNBOOK.md)** 가 그대로 실행 가능한 순서를 소유한다. 거기서 먼저 봐야 할
두 가지: ① 커밋해도 `python-tests` 빨간 4건은 초록이 되지 않는다(CR-14 울타리 이동·EX-05 승격 — 둘 다
타 레인/오너의 일이고, 우리가 커밋하면 HEAD 가 오히려 멀어진다), ② **커밋은 지문을 옮길 수 있다** —
종전에 “옮기지 않는다”고 적었지만 실측으로 반박했고 `CLOSURE_RUNBOOK` §3.1 을 고쳤다: 파일 내용은 그대로라도
**인덱스에서 사라지는 항목**(추적 중 삭제된 번들 30개)이 지문 맵에서 빠지면서 `0f345d0c… → 92fcaeb5…` 로 이동했다.
그래서 순서는 **커밋 → 재측정 → (필요하면) 재장전** 이다.

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
지문 일치를 한 화면에) · `cancel`(트리 단위 종료 + **검증**) · `orphans` · `preflight`(발화 전 점검 — 예약 11개 ·
즉시 시작 7개) · `run`(지금 시작) · `harvest`(끝날 때까지 기다렸다가 회수 판정까지) ·
`selftest`(**70/70**, 약 3분, 임시 디렉터리에서 사고를 재현 — **진짜 soak 이 도는 중에도** 통과한다). `preflight` 는 **8시간이 끝나도 결과를
후보에 귀속할 수 있는가**를 미리 묻는다 — `현재 트리 지문 == HEAD 트리 지문`(`tree_fingerprint_of_commit`)을
직접 확인하고, 인터프리터·러너 자산·`/tmp` 여유·이미 도는 soak 까지 함께 본다(실측: 10/10 OK). 예약 잠금은 `mkdir` 원자성이고(두 번째 예약은 `exit 2`),
러너에도 별도 실행 잠금이 생겼다(이미 soak 이 돌면 `exit 5`, 리포트 미생성).
사고·한계·자기시험이 잡은 결함 6건(macOS `tac` 부재 · 예약 1건이 프로세스 2개로 보이던 오탐 ·
가짜 프로세스가 파이프를 물고 있는 문제 · heartbeat 중복 · **실행 중 soak 을 ATTENTION 으로 오탐** ·
**시험이 환경에 결합돼 진짜 soak 이 도는 동안 47/50**)은 [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) 가 소유한다.
뒤의 두 결함은 §3d, 8시간 재실행(§17-3) 중에 발견했다 — 도구 결함이므로 그 실행의 기록은 그대로 유효하다.

**세 번째 결함(이 창에서 발견·수정): 회수 판정기가 “첫 예약”을 읽었다.** `soak-schedule.txt` 는 예약할
때마다 블록을 덧붙이는데, `scripts/collect_soak_result.py` 의 `expected_fingerprint()` 가 `re.search`
(= 첫 매치)로 기대값을 잡아 **철 지난 예약**(`157311cf…`, 08:20Z)을 썼다. 그대로면 밤새 정상으로 끝난
8시간 실행이 ③(기대 == 시작)에서 **거짓 FAIL** 로 판정된다 — 이 카드가 반복해서 겪은 “지표는 PASS 인데
귀속이 어긋나 판정 근거가 사라짐”과 같은 종류다. 마지막 예약을 쓰도록 고치고(출처를 출력에 문장으로
남긴다) 계약 시험 1건 + 자기시험 3건으로 고정했다(자기시험 **9/9**). 커밋 **`1bd95e7d`**(코드 2파일만,
`git add -A` 0회, 훅 통과). 판정기가 `scripts/` 라 지문이 `92fcaeb5…` → **`322b4d3b…`** 로 이동했고,
작업 트리 지문 = HEAD 트리 지문(실측) → 그 지문으로 **필수 23개(clean-machine 포함) 재측정**을 돌렸다.

**실제 시작(2026-09-16T12:13:12Z = 21:13 KST):** 오너 지시(“soak 진행해줘”)로 **22:00 발화를 기다리지 않고**
`cancel`(검증: `[OK] 죽음 확인` · 살아 있는 예약 0건) → `run`(즉시 시작 모드 preflight 5/5 OK, 예약과 같은
포장: screen + `caffeinate -i`)으로 시작했다. 시작 지문 `322b4d3b…` = 예약 기대 = HEAD 트리(실측)이라
**이 8시간은 커밋된 후보 `fd16368c` 의 것**으로 귀속될 수 있다(`start_dirty: true` 는 `docs/` 편집과 gitlink
`vault_data` 때문이며, 귀속 판단은 `start_fingerprint` 로 한다). 종료 예정 `20:13Z` = **05:13 KST**.
작업디렉터리 `/tmp/nx10-soak-work-20260916T121312Z` · 실행 잠금 pid 89463(살아 있는 동안 soak 이 돈다).
**이 시점부터 코드를 건드리면 그 8시간이 무효다** — 이 창은 문서만 수정하고, 아침에는 회수 판정을 먼저 끝낸다.

**재장전 이력:** 위 수정 전 상태는 `soak_control.sh arm --at 22:00`(2026-09-16T11:39:27Z, 기대 지문 =
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
| NX-10 수용 “지원 환경별 한계·운영 runbook·복구 기록” | **작성 완료 + 복구 리허설 1건 추가**(2026-09-17: restore 를 임시 경로에서 실시 — §11, `docs/09` 의 복구표도 “미실시” → 절차·증거로 정정. rollback·손상 대화 폐기 실저장소 리허설은 여전히 미실시/미결정). 종전 문구: **작성 완료**(2026-09-16, 이 카드): [09 운영 가이드 §NX 운영 runbook](../../../09_OPERATION_GUIDE.md) — 지원 한계표·런타임 경로·**폐기 경로의 실제 범위**(열린 SSE 는 닫는 경로 없음)·SC-1~6 임계·**복구 리허설 상태**(restore·rollback·손상 대화 폐기 = 미실시/미결정). soak 실행 중에 추가했으며 `docs/` 는 지문 제외 대상이라 안전하다(§4 규칙). **확인:** 편집 뒤 작업 트리 지문을 다시 계산해 시작값 `c65fe0e1…` 과 **동일**함을 실측했다(게이트 제외 프리픽스 `FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")` — `scripts/ga_gate.py`) | 이 카드(완료) |

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

실패 1개(`python-tests`)의 실패 5건은 **전부 타 레인의 결과에 귀속되고, 커밋된 트리만 비교하는
계약 테스트**다(§7 — 실행해서 직접 확인: 후보↔HEAD 사이 코드 스코프 38경로 이동, EX-05 승격 계약).
그래도 **실패는 실패로 센다** — “우리 탓이 아니니 통과” 로 바꾸지 않는다.

**2026-09-17 정정**: 위 “4건”은 오기다 — 실물은 **5건**이고 내역은 **NX-07 문서 정합성 2** +
**CR-14 울타리 3** 이다(“EX-05 2건”은 `test_nx07_doc_consistency.py` 의 실패를 EX-05 대장 행 때문에
그렇게 부른 것이고, 세 번째 CR-14 건은 `promote004` 에서도 이미 빨간색이었다).

**2026-09-17 재측정(attempt `tailfix001`)**: 꼬리 창 수정을 커밋한 지문 `98855031…`(= HEAD)에서
필수 **23개 전수: 22 passed · 1 failed · 0 not_run**(`clean-machine-runtime` passed 43.0s).
마감 도구 지적은 **하나**(`required_red: python-tests`)이고 그 실패 5건은 `promote004` 와
**시험 단위로 동일**하다 → **수정이 만든 새 실패 0건**. 그래도 **판정은 NO-GO 그대로**다
(§9 의 4가지 근거 중 ①·③·④가 그대로다).

## 9. 판정

**NO-GO (REVIEW 유지).** 근거:

1. required 1개가 **failed** 이다(카드 §수용: 실패 0 **그리고** not_run 0). 그 5건의 원인은
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

## 10. 8시간 soak 회수 결과 (2026-09-17) — FAIL, 원인 측정됨

전문: **[SOAK_8H_FINDINGS.md](SOAK_8H_FINDINGS.md)** · 회수 행: [GATE_LEDGER.md §16](GATE_LEDGER.md) ·
판정 원문: `soak-recovery-20260916T121312Z.json` · `soak-recovery-latest.json`.

- **실행**: `soak_control.sh run` → `12:13:12Z` → `20:13:16Z`(28,800.075초, 요청 100%) · exit 1 ·
  리포트 `soak-28800.json` · start = end = 기대 = 지금 트리 = `322b4d3b…`.
- **초록 6가지(거의 전부 8시간 규모 최초)**: `errors 0` · fd 5→5 · `orphan_worktrees 0` · view 19 ≤ 64 ·
  append/revision 일치 · 원본 70,431건 전수 확인 · 제약 보존. SC-1~5 도 전부 pass.
- **빨강 1가지**: SC-6 `rss_growth_mb 1683.5`(66.8 → 1750.2 MB, 기준 64) — 이 하나가 exit 1 과
  `all_pass False` 를 만든다. 처리량도 같이 무너졌다(2.45 ops/s, 70,430 append / 8시간).
- **원인(측정)**: `append()` 1회 = `tail()` 3회(`_authoritative_record` 1 + `_commit_event` 2).
  `tail()` 은 docstring 과 달리 `read_bytes()` → `split(b"\n")` → 모든 줄 `json.loads` +
  `JournalEvent.from_dict` 를 한다. 실물 24.4 MB journal 에서 `tail()` 265~271 ms · append 814~830 ms
  중 **810 ms = 99.5%**. 비용이 파일 크기에 비례 → 실행 전체가 제곱 → 평균 0.41초 × 70,430 = 8시간 전부.
- **누수가 아니다**: 60초 프로브에서 살아 있는 객체 수 평탄(±25) · live object 델타 −292 ·
  일시 할당 peak 52 MB. 즉 “매 호출의 대량 일시 할당이 남긴 high-water”다.
- **정정**: NX-04 의 `stream_line_count` 경로는 이번에도 타지 않았다(8h journal 24.4 MB < 임계 32 MiB).
- **수정 완료(같은 날)**: `ConversationJournal.tail()` 이 꼬리 창(64 KiB)만 읽고, 창으로 판정하지 못하는
  파일만 종전 전체 스캔으로 되돌아간다. 관대한 파싱·`truncated_tail` 의미는 그대로고, **창 경로와 전체
  스캔의 판정이 모든 파일 모양에서 같다**는 것을 계약 시험으로 고정했다(torn tail·손상 줄·창보다 긴 줄 포함).
  실물 8h journal 에서: `tail()` 265~271 ms → **0.04 ms** · `append()` 814~830 ms → **0.5~0.8 ms** ·
  append 3회 `maxrss` 133 MB → **60.9 MB**. 같은 60초 리허설: 2,978 → **29,180 ops**(journal 은 10배 큼) ·
  RSS 증가 21.2 → **16.8 MB**.
- **append 1회의 `tail()` 3회는 남겼다**: 각 호출이 O(꼬리)가 되어 합계 < 1 ms 이고, 프로세스 캐시는
  stale `seq` 위험을 새로 만든다. 본질은 값이 아니라 **읽는 범위**다.
- **10분 규모 확인(같은 날)**: ops `269,087`(448.5 ops/s) · journal **94.1 MB** · `rss_growth_mb` **32.2** ·
  `pass true` · view 26 ≤ 64 · generations 4,639. RSS 기울기는 `0.643 → 0.240 → 0.160 → 0.145 → 0.008 →
  0.015 → 0.004 → 0.008 → 0.000 → 0.004` KB/op 로 **평탄부 진입** — 그 기울기의 8h 외삽은 **+48 MB < 64**
  이고, 과거 다른 후보의 8h 실적(+48.7 MB / 1,210만 append)과 일치한다. 즉 수정된 코드는 10분에
  옛 코드가 8시간에 한 일의 **3.8배**를 했고, 8시간은 종전과 다른 크기(≈1,290만 ops)를 잰다.
- **NX-04 의 `stream_line_count` 가 처음 실행됐다**: 94.1 MB journal 이 32 MiB 임계를 넘어
  `replay_deferred=True` · `journal_lines=269,088` · `originals_complete=True`. 8h soak 이 닫지 못한
  항목이 **임계값을 건드리지 않고** 닫혔다.
- **회귀 확인**: 전체 스위트 `5 failed, 6640 passed, 10 skipped, 20 xfailed`(10분 31초) — **이 수정의 것 0건**
  (benchmark latency 1: 내가 `-m "not benchmark"` 없이 돌렸고 단독 실행은 pass · CR-14 울타리 2: 코드
  스코프 이동의 설계된 빨간색 · NX-07 문서 2: **HEAD 내용으로도 같은 위반** — EX-05 대장 행이 `PASS`
  한 단어인데 그 실행의 귀속이 UNVERIFIED). 대화 저장소 계약 79건 전부 통과 · 문서 검사기 ALL OK.
  **교차 레인 항목은 고치지 않고 증거만 올린다** — 그 대장은 CR-14 레인의 문서다.
- **커밋**: `7d8c25b5`(수정 + 계약 시험 · 경로 명시 스테이징 · 훅이 재포맷해 한 번 재스테이징) ·
  `099cfc8b`(문서 10파일; 1MB 초과 게이트 리포트 6개는 정책대로 디스크에만).
- **지문 `98855031…`** = 작업 트리 = HEAD 트리(soak 시작 때의 `322b4d3b…` 와 다름).
  커밋 전 측정값 `792a7d5d…` 와 달라진 이유는 **커밋이 아니라 훅의 재포맷**(내용 변경)이다 —
  둘을 구별해 두지 않으면 다음 사람이 "커밋은 지문을 안 옮긴다"를 또 잘못 배운다.
- **필수 23개 재측정 완료(`tailfix001`, 22:52:51Z→23:12:20Z)**: **22 passed · 1 failed · 0 not_run**,
  시작 = 종료 = `98855031…`, `clean-machine-runtime` **passed 43.0s**(커밋 덕분에 후보 값). 마감 도구는
  `required_red: python-tests` **하나**를 지적하고, 그 `python-tests` 의 실패 5건은 `promote004` 와
  **시험 단위로 동일**(CR-14 울타리 3 · NX-07 문서 정합성 2) → **이 수정이 만든 새 실패는 0건**.
  기록: `gate-report-tailfix001.json` · `gate_verify-tailfix001.txt` · `promote-runner.log`.
- **정정(오기)**: 종전 “타 레인 4건(EX-05 2 · CR-14 2)” 은 틀렸다 — 실물은 **5건**이고 내역은
  **NX-07 문서 정합성 2 + CR-14 울타리 3** 이다(“EX-05 2건”은 `test_nx07_doc_consistency.py` 의 실패를
  EX-05 대장 행 때문에 그렇게 부른 것이고, 세 번째 CR-14 건은 `promote004` 에서도 이미 빨간색이었다).
- **판정은 여전히 NO-GO**(§9): required red 1(타 레인·오너) · CR-14 울타리는 후보 재선언 전까지 설계상
  빨간색 · owner 허용 기록 없음. “22 passed”를 GO 로 확대 해석하지 않는다.
- **preflight 에 처리량 하한을 넣었다**: 직전 실행은 60초에 2,978 ops(49.6 ops/s)를 내고도
  preflight 를 통과해 8시간을 태웠다. 이제 `run`/`preflight` 가 60초 SC-6 프루브로 **ops/s 비율**을
  재고(`NX10_PREFLIGHT_MIN_OPS_PER_SEC` 기본 133) 미달이면 프루브 로그를 남기고 중단한다.
  자기시험 **43/43**, 실측 443 ops/s. 만들다 걸린 두 함정(SC-6 단독 실행의 exit 1 / 절대 개수 기준)은
  [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) §3b 에 적었다.
- **8시간 재실행 1차 시작(2026-09-16T23:26:23Z) → 48분에 중단**(`2026-09-17T00:13:54Z`, 러너 `exit: 143`,
  `end_fingerprint` = 시작값 — 트리는 안 흔들렸다). 이유는 아래 여섯 번째 결함이다(스스로 끝난 실행이 아니므로
  판정 대상이 아니다).
- **여섯 번째 결함(같은 날, 도구가 잡았다): 내 수정이 만든 새 사각지대 — 쓰기량 > 기본 hard cap.**
  재실행이 47분쯤 돌았을 때 journal 이 **452 MiB**(159 KB/s)였다. ADR-DAT-02 의 기본 hard cap 은
  **512 MiB 이고 자동 prune 이 없다** → **8분 뒤 507 로 모든 append 가 거절**되고, 하네스가 그것을
  `errors` 로 세므로(`SC-6 pass` 에 `errors == 0`) 8시간이 **설정 때문의 거짓 FAIL** 로 끝날 참이었다.
  직전 FAIL 실행의 8시간 journal 은 24.4 MB 였기에 기본 캡과 부딪힐 일이 없었고, 바로 그 때문에
  어제의 리허설·점검이 이 벽을 보지 못했다 — §10 의 처리량 하한과 **쌍둥이 사각지대**다
  (“빠르게 도는가”는 묻고 “그 속도로 쓰면 어디서 멈추는가”는 묻지 않았다).
  조치: ① 중단 ② 러너가 캡을 정하고 **기록**한다(`AGK_CONVERSATION_JOURNAL_HARD_CAP_MB=8192`, soft 는 기본 유지
  — 경고 관측을 살린다; 기록에 `retention_caps: soft=64MiB hard=8192MiB` 를 해석해 남긴다)
  ③ **preflight 에 쓰기량 투영 점검**을 추가해 8시간으로 외삽한 journal 바이트가 cap 의 90% 를 넘으면
  시작 전에 막는다(자기시험 **70/70** — 캡 1 MiB 면 빨개지고 캡 8192 MiB 면 초록).
  전문: [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) §3e.
- **8시간 재실행 2차(2026-09-17T00:15:16Z) → 7분에 중단(00:22:48Z, `exit: 143`)**: 시작 지문 `98855031…` =
  당시 트리 = HEAD(`aa1ead1f`) · preflight **6/6 OK**(처리량 437 ops/s · 투영 4,050 MiB < cap 8,192 MiB).
  원인은 **SC-3 경합 + 하네스 무한 대기**(아래). 둘 다 고쳐 커밋 **`c522b256`** → 필수 23개 재측정
  (attempt `sc3fix001`) → 그 지문에서 다시 시작한다(새 후보 지문 `5c90b637…`).
- **일곱 번째 결함 — 제품 경합(SC-3 이 잡았다)**: `ProjectRegistry` 의 **최초 생성 경로만 공유 flock 밖**이었고
  백업 회전의 임시 파일 이름이 **고정**(`projects.json.bak.tmp`)이었다. 동시에 시작한 프로세스가 같은 이름을 쓰고
  한 쪽이 먼저 `os.replace` 로 옮기면 다른 쪽이 `RegistrySaveError` 로 죽는다 — 실측 traceback:
  `FileNotFoundError: … projects.json.bak.tmp -> … projects.json.bak`. 대화 저장소에서는 **같은 종류**
  (결정론적 tmp 이름, F1)를 이미 고쳤는데 registry 백업 회전에 같은 규칙이 남아 있었다.
  고침: 생성도 `with self._locked()` 안에서(경합에서 진 쪽은 이긴 쪽이 쓴 파일을 읽는다 — 같은 lock 재진입은
  flock 이 막으므로 재귀하지 않는다) + 백업 tmp 이름 `.{name}.tmp-{pid}`. 계약 시험 3건.
- **여덟 번째 결함 — 하네스 무한 대기(더 위험했다)**: SC-3 worker 가 죽자 `q.get()` 에 타임아웃이 없어
  부모가 **영원히** 기다렸다. 러너는 **종료 시에만** 리포트를 쓰므로, 그대로 두면 8시간이 “FAIL”이 아니라
  **아무 결과도 없이** 사라진다 — 이 카드가 하루 종일 다툰 “다른 이유로 빨간 결과”보다 한 단계 나쁘다.
  SC-1·SC-2·SC-3 세 곳 모두 같은 형태였다. 고침: `_collect_worker_results` 가 상한(기본 120초) 안에 안 오는
  worker 를 terminate 하고 **오류 1건**으로 세며 계속하며, 리포트에 `worker_timeouts` 를 남긴다. 계약 시험 2건.
- **판정의 의미**: ⑦은 “SC-3 가 제품 경합을 잡았다”는 뜻이고(시나리오가 제 역할을 했다),
  ⑧은 “하네스가 그 발견을 결과로 못 바꿨다”는 뜻이다. 둘 다 같은 날 닫았다.
  전문: [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) §3f · [GATE_LEDGER.md](GATE_LEDGER.md) §20.
- **회수는 이제 도구가 한다**: `soak_control.sh harvest` — 끝날 때까지 기다렸다가(잠자기 차단 포함)
  판정기까지 돌리고 그 `exit` 를 그대로 전한다. 아직 도는 중에 `--no-wait` 면 `exit 4` 로 거부하는데,
  러너는 **종료 시에만** `end_*`·`exit` 를 쓰므로 그 거부가 곧 “옛 블록을 읽지 않는다”는 보장이다
  (자기시험 11건이 네 경로를 고정: 거부·대기 뒤 판정·완성 블록 없음·판정기 exit 전달).
- **필수 23개 재측정(attempt `sc3fix001`)**: **22 passed · 1 failed · 0 not_run**, 시작 = 종료 =
  `5c90b637…` = HEAD(`c522b256`) · `clean-machine-runtime` passed · 실패 5건은 `promote004` 와 시험 단위 동일
  → **새 실패 0건**, 통과 수 6621 → **6626**(+5 = 이 창의 계약 시험). 마감 도구 문제는 `required_red: python-tests` 하나.
- **8시간 재실행 3차(현재)**: `2026-09-17T01:19:44Z` 시작 → 종료 예정 `09:19:43Z` = **18:19 KST** ·
  지문 `5c90b637…` = 현재 트리 = HEAD · preflight **7/7 OK**(처리량 451 ops/s · 쓰기량 투영 4,282 MiB < cap 8,192 MiB)
  · **SC-1~5 완주·오류 0** — SC-3 경합이 지금 통과했다(하루 전 같은 자리에서 실행이 멈췄다).
  작업디렉터리 `/tmp/nx10-soak-work-20260917T011943Z`.
- **도구에 붙인 문(같은 창)**: `harvest` 의 **무응답 상한**(`NX10_HARVEST_MAX_STALL`, 기본 1800초 —
  살아 있지만 안 쓰는 상태를 “도는 중” 으로 보지 않는다) · `NX10_HARVEST_SETTLE`(러너의 마지막 플러시 대기).
  자기시험 **75/75**.
- **잔여 작업 창(soak 실행 중, 2026-09-17 오전 — `docs/` 만 수정해 지문 불변)**: ① 상위 상태 문서 두 곳이
  **낡아 있었다**(§3 표가 1차 재실행을 아직 “실행 중”으로 적었고 `docs/19` 도 같은 값) → 세 번의 실행·
  중단 사유·수정 커밋·재측정 값으로 정정 ② **NX-01 의 미완 항목 “restore 리허설”을 닫았다** — 임시 저장소
  리허설 4개 경계 exit 0(왕복·최신 변경 손실 방지·멱등·삭제 거절) + 가드를 끄면 원문 3건이 사라지는 이빨 확인,
  그리고 **발견 1건 `NX03-RESTORE-MARKER`**(삭제 표식이 상태 플래그에만 적용되고 원문 읽기 표면은 journal 의
  `delete` 이벤트만 본다 — 운영 절차가 거절로 막는다) ③ 그 도구는 동결 때문에 `docs/qa/…/nx01/` 안에 있고
  승격 후보로 [PROMOTION_PLAN.md](PROMOTION_PLAN.md) §1b 에 등록(동결 해제 뒤 `tests/` 로) ④ NX-04 의
  “`stream_line_count` 미실행” 문구를 실측(10분 실행, 94.1 MB > 32 MiB 임계)으로 정정 — 남은 것은
  시간 규모뿐이고 도는 8시간 soak 의 리포트가 닫는다.
- **다음**: `soak_control.sh harvest --detach` → 결과를 대장(§16 옆)에 반영. 남는 required red 1 과 CR-14
  재선언은 여전히 타 레인/오너의 일이고, `docs/` 도구를 `scripts/`·`tests/` 로 승격하는 일은
  **회수 뒤**다(지금 옮기면 이 8시간의 종료 지문이 갈린다).

## 11. 잔여 작업 창 (2026-09-17 오전, 3차 soak 실행 중 · `docs/` 만 수정)

목적: 8시간이 도는 동안 **멈춰 있는 항목 중 오너·타 레인 없이 닫을 수 있는 것**만 처리하고, 지문은 건드리지 않는다
(`FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")` — 실측 확인).

1. **낡은 문장 정정 3건**(전부 “이미 지나간 상태를 현재로 적고 있던” 것):
   - `docs/20` §3 표·서술과 `docs/19` 의 NX-10 행이 **1차 재실행을 아직 “실행 중”** 으로 적고 있었다 →
     ① 1차(48분, retention hard cap 때문에 중단) ② 2차(7분, SC-3 제품 경합 + 하네스 무한 대기) ③ 3차(현재)
     세 줄로 나누고 중단 사유·수정 커밋·재측정 값을 넣었다.
   - NX-04 의 “`stream_line_count` 는 실측 규모에서 미실행” → **실측으로 정정**(10분 실행의 journal 94.1 MB 가
     임계 32 MiB 를 넘어 `stream_line_count`·`replay_deferred=True`·`journal_lines=269,088`). 남은 미검증은
     **시간 규모**뿐이고 그건 도는 8시간 soak 의 리포트가 닫는다 — 그 전까지 “8h 규모 검증됨”이라고 쓰지 않는다.
   - `docs/09` 복구표의 “백업 → 복구 = 미실시” → 아래 2 의 리허설 결과와 절차로 교체.
2. **NX-01 미완 항목 종결 — restore 리허설**(임시 경로, exit 0): 제품에는 export 만 있고 import/restore API 가
   없으므로 복구는 파일 수준이고 **안전성은 절차가 책임진다.** 그 판정부를 만들어 4개 경계를 실측했다 —
   ① 왕복(지문 동일·revision 5=5·원문 5건 동일·view 재구성) ② **최신 변경 손실 방지**(대상이 더 새로우면 거절,
   그 사이 append 3건 생존) ③ 멱등(같은 바이트는 무동작) ④ 삭제된 대상은 거절. **이빨도 확인**: 가드를 끄면
   revision 이 8→5 로 되돌아가며 원문 3건이 사라진다. 근거 [../nx01/restore-rehearsal.md](../nx01/restore-rehearsal.md).
3. **발견 1건을 제품 결함으로 남김 — `NX03-RESTORE-MARKER`**: 삭제 표식은 `history_state.deleted` 에만 적용되고
   **원문 읽기 표면(`original_history`)은 journal 의 `delete` 이벤트만 본다.** 삭제 전 바이트를 되돌려 놓으면
   `deleted=true` 인데도 원문이 다시 읽힌다(관측 3건; 같은 함수 docstring 은 빈 목록을 약속한다).
   **동결 중이라 코드는 고치지 않았다** — `src/` 를 건드리면 도는 soak 의 종료 지문이 갈린다. 운영 절차는 이
   상태를 거절하며, 수리안은 `original_history`/`export_original_history` 가 표식도 확인하는 것이다.
4. **승격 예약**: 리허설 도구는 `docs/qa/…/nx01/` 안에 있으므로 아직 **어느 게이트도 지키지 않는다** →
   [PROMOTION_PLAN.md](PROMOTION_PLAN.md) §1b 에 다음 승격 후보로 등록(동결 해제 뒤 `tests/`) —
   그 배치는 §1c 로 확정됐다(아래 7·9).
5. **조기 경보 도구를 하나 만들었다(`soak_watch.py`)**: 오늘 두 실패는 모두 **끝나야 알 수 있는** 종류였다
   (1차: 47분에야 cap 초과 투영 · 2차: 멈춘 뒤에도 30분 대기). 돌고 있는 실행을 60초마다 읽어 살아 있음 ·
   마지막 쓰기 · **cap 투영** · **RSS 외삽** · 추정 처리량을 한 화면에 내고 위험하면 exit code 로 말한다
   (읽기 전용·저널을 읽지 않아 측정 간섭이 거의 없다). 자기시험 **3/3**, 돌고 있는 3차 실행에 돌려 **정상**
   판정: journal 290 MiB · 추정 **672 ops/s** · 종료 시 cap 추정 **6,396 MiB < 8,192** · RSS 외삽 +11~40 MB.
   **주목**: preflight 의 사전 투영(4,282 MiB)보다 실측 추세(≈6.4 GiB)가 커서 여유가 사전 계산보다 얇다.
6. **그 감시를 상시로 붙이고 라이브 화면을 만들었다(`soak_watch_loop.py` + `soak-watch-live.html`)**:
   표본을 60초마다 `soak-watch-history.jsonl` 에 쌓고 **자체 완결 HTML**(서버·외부 자산 0, 인라인 SVG,
   30초 자기 새로고침)을 계속 다시 쓴다. 화면에는 경보 등급 배지 · 경고 배너 · journal/RSS/추정 처리량
   추세 · **기준 대비 막대**(cap 사용률·SC-6 RSS 증가율) · 최근 30표본 표가 나온다. 화면은 `docs/` 안이라
   지문을 안 건드리고, 실행은 `screen nx10watch`(로그 `soak-watch-loop.log`, `-u` 필수). 자기시험
   `soak_watch` **7/7** · `soak_watch_loop` **9/9**, 보는 법은 이 창의 Preview 탭(`soak-watch-live.html`
   등록) 또는 같은 파일을 브라우저로.
   **그리고 그 첫 경보가 오탐이어서 규칙을 두 번 고쳤다**(같은 창): 순간 기울기로 외삼해 29분의 작은
   RSS 계단을 “+305 MB, SC-6 빨개진다”로 만들었다 → 누적 평균 → 그 뒤에도 남은 +112~126 MB 경보는
   화면 그림이 **계단 뒤 평탄**임을 보여 줘서 ① **워밍업**(실행 25% 전에는 경보 보류) ② **감속 판정**
   (뒤 구간 상승률 < 앞 구간의 절반)을 넣었다. 지속 증가는 그대로 경보한다(이빨 ⑤·⑥). 임계치를 낮춰
   맞춘 게 아니라 **판단 근거를 늘려** 잘못된 외삼만 보류한 것이다 — 상시 거짓 경보는 경보가 아니다.
7. **2차 승격 배치를 준비했다(본실행은 동결 해제 뒤)** — 오늘 만든 리허설 둘을 `scripts/` 로, 그 계약
   시험 둘을 `tests/` 로 옮기는 이동표·게이트·리허설·본실행을 `promote2/` 에 만들고 **미러에서 ALL PASS**
   (승격 위치 14 passed · 도구 직접 실행 초록 · ruff 초록 · **도구를 치우면 시험이 실패** · 스테이징 잔존 0).
   본실행 스크립트는 **도는 soak 을 발견하면 거절**한다(실측: pid 56261 을 찾아 거절, 이동 0건) —
   `scripts/`·`tests/` 는 지문 대상이라 지금 옮기면 이 8시간이 무효가 된다.
   **그 과정에서 내 리허설의 경합 하나를 계약 시험이 잡았다**: 낡은 인스턴스가 적재하기 전에 삭제가
   끝나면 그 인스턴스가 새 세션을 만들어 다른 것을 재게 된다(3회 중 1회) → 적재 신호(`ready`) 핸드셰이크로
   고쳤고 실측 6/6 · 계약 시험 3회 연속 초록이다.
8. **하지 않은 것**: `src/`·`tests/`·`scripts/` 무수정(지문 불변) · 실사용 store 복구 미실시(운영 결정) ·
   CR-14 후보 재선언·EX-05 대장 행 수정·독립 검토자 지정은 여전히 **타 레인/오너**의 일.
9. **“승격된 위치에서 전부 통과하는지 확인”을 읽는 것 → 기록되는 것으로 바꿨다**: 게이트 `A` 가
   `promote2/promoted-contract-tests.txt` 를 매번 다시 쓴다 — 시각·루트·HEAD·명령·**승격 위치 두 파일의
   sha256**·exit·전문(`-v`) + **수집 노드가 `tests/` 인지**. 종전엔 `pytest \| tail` 요약만 찍혀서 그 통과가
   16분짜리 리포트 안에 묻혔고, 그 파이프는 `pipefail` 없는 셸에서 **실패해도 초록**이 된다 →
   `out="$(…)" \|\| rc=$?` 로 교체했다. 새 확인은 첫 실행에서 **거짓 FAIL 2건**(작은따옴표 정규식에 변수
   미확장 · 요약줄이 `=` 로 시작해 앵커 불일치)을 냈고, 고친 뒤 **14 passed**(노드 검사 초록)다.
   음성 대조군: 승격 **전** 같은 명령은 `exit 4` · 노드 검사 red — 즉 승격 위치에서만 초록이 된다.
   본실행 한 줄은 `promote2/post_harvest_sequence.sh --wait`(대기 → 판정 → 승격 → 새 지문에서 필수 23개 → 재장전)이고,
   **그 한 줄이 `screen nx10promote` 로 지금 걸려 있다**(18:19 KST 종료를 기다리는 중 · 로그 `promote2/post-harvest-sequence.log` ·
   취소 `screen -S nx10promote -X quit`). 무인이라 가드 두 개를 더 넣고 샌드박스 4경로로 확인했다:
   **판정 FAIL 이면 승격을 멈춘다**(트리 무변경 · 강행은 `NX10_PROMOTE_ON_FAIL=1` — FAIL 이면 후보에 손을 대야 해서
   승격 직후 지문이 또 움직인다) · 떠 있는 감시의 **방금 쓰인** 판정 원문을 먼저 집는다(동시 판정은 자물쇠 경합으로
   순서를 끊고, 낡은 원문은 오늘 것으로 안 본다).
   상태: 배치 **준비·리허설 완료** → **오너 지시로 본실행까지 완료**(§12 — 무인 대기는 취소했다).

## 12. 승격 본실행 · 새 지문에서의 재측정 · 4차 soak (2026-09-17, 오너 지시)

지시: “무인 대기를 취소하고 지금 2차 승격을 실행한 뒤, 필수 게이트를 재측정하고 8시간 soak 을 새로 걸어줘.”
§5b 의 순서 규칙(측정 → 지문 확인 → 재장전 → 그 뒤에는 `docs/` 만)을 그대로 밟았다: **중단 → 승격 → 커밋 → 재측정 → 재장전**.

1. **중단(되돌릴 수 없는 것을 먼저 멈춘다)**: 3차 soak 을 경과 1h 04m 32s(`02:24:15Z`)에 `SIGTERM` 으로 내렸다 —
   러너가 `exit: 143` · `end_fingerprint` = 시작값 `5c90b637…` 을 기록해 **트리를 안 흔들었음**이 남았고, 실행 잠금도
   스스로 풀렸다(실측). 무인 대기(`screen nx10promote`)·회수 감시(`nx10harvest`)·감시 루프(`nx10watch`)는
   `screen -X quit` 뒤 **프로세스 생존까지** 확인해 내렸다(`-X quit` 은 취소가 아니다 — §6b 사고).
   대가는 1시간(8시간의 13%)이고, 이 실행은 **판정 대상이 아니다**(8시간 미충족 · 러너는 종료 시에만 리포트를 쓴다).
2. **승격(2026-09-17T02:24Z, `promote2/apply_promotion2.sh`)**: 이동 4건 sha256 동일(백업 `/tmp`) ·
   **승격 위치에서 14 passed**(`promote2/promoted-contract-tests.txt`, 수집 노드 `tests/`) · 도구 직접 실행 초록 ·
   ruff 초록 → 커밋 **`bde261dc`**.
3. **첫 재측정이 새 실패 1개를 냈다 — 그리고 그것이 이 배치의 값이다**: `python-basedpyright` 가 **새로** 빨개졌다
   (`promote2b`: 21 passed · 2 failed). 원인은 회귀가 아니라 **승격의 정의**다 — 승격 전에는 이 두 파일이 `docs/` 안이라
   정적 게이트가 **보지 않았다**. 커밋된 후보로 들어오자 타입 오류 **12건**이 드러났고, 수정 `5c979c0f` 를 커밋했다.
4. **새 지문 재측정**: `promote2c`(02:50Z→03:07Z, 지문 시작 = 종료 = **`b6a74304…`** = HEAD `5c979c0f`) →
   **22 passed · 1 failed · 0 not_run** · `clean-machine-runtime` passed · `python-basedpyright` **초록** ·
   남은 실패는 `python-tests` 하나. 여기서 **승격이 깬 문서 링크 1건**(`tests/test_local_relative_links_resolve` —
   옮겨진 파일을 옛 경로로 가리키는 참조 3곳)을 `docs/` 만 고쳐 닫았다.
5. **깨끗한 수치**: `promote2d`(03:08Z→03:19Z, 같은 지문)에서 `python-tests` 만 다시 재 **5 failed · 6640 passed** —
   실패 5건은 `promote004`/`sc3fix001` 과 **시험 단위 동일**(CR-14 울타리 3 · NX-07 문서 2)이라 **새 실패 0건**이고,
   통과 수 증가분 **6626 → 6640(+14)** 이 곧 승격한 계약 시험 14건이다.
6. **라이브 화면이 가짜 급강하를 그리고 있었다 — 고쳤다**(4차 시작 직후): 새 실행의 journal 은 0 에서 자라므로
   이전 실행(3차)의 표본을 같은 추세선에 이으면 화면이 **“861.8 MiB → 1.4 MiB 로 줄었다”** 을 보여 준다.
   경보 배지는 정상인데 그래프는 재해처럼 보이는 이 모순을, 표본을 **실행(pid) 단위로 가르는** 것으로 닫았다 —
   이전 실행의 표본 40개는 `soak-watch-history-pid56261.jsonl` 로 **옮겨 보존**하고(버리지 않는다) 새 선만 그린다.
   자기시험 **9/9 → 14/14**(이빨: 섞으면 861.8 MiB 급강하를 재현하고 가르면 재현하지 않는다).
7. **4차 soak 시작**(`03:25:56Z` → `11:25:56Z` = **20:25 KST**, 지문 `b6a74304…` = 현재 트리 = HEAD 트리,
   preflight **7/7**: 처리량 474 ops/s · 쓰기량 투영 < cap 8,192 MiB). 36분 시점 실측은 **정상** — journal 504 MiB ·
   추정 703 ops/s · 종료 시 cap 추정 6,696 / 8,192 MiB. 감시·회수 화면을 재부착했다.
   **지켜볼 것 — SC-6 RSS (48분 시점 실측 판정)**: 증가 **+29.4 MB / 기준 64 MB**(기준선 = 이 실행 첫 표본
   71.7 MB — 하네스가 쓰는 자리와 같다) → 남은 7h11m 동안 **허용 +0.080 MB/분** 인데 **최근 실측 +0.210 MB/분**.
   즉 **초과 추세**이고(누적 외삼이면 종료 시 +293 MB), 실행이 워밍업(2h) 전이라 도구가 경보를 보류하며 숫자만 밝힌다.
   **판단 시점 `05:25:56Z` = 14:25 KST** — 상시 감시가 계속 돌므로 그때 배지·로그가 스스로 뒤집힌다.
   최종 판정은 하네스의 `rss_growth_mb` 가 한다 — 이 수치는 “언제 볼지”를 알려 주는 용도이지 판정이 아니다.
   (같은 질문에 답하게 도구를 고쳤다: 허용 증가율·최근 실측을 매 표본 출력하고, `--once` 가 표본 하나로
   판정해 분석을 침묵하던 것도 고쳤다. 자기시험 `soak_watch` **18/18**.)

**판정은 그대로다**: required red 1(`python-tests`, 타 레인) · **CR-14 후보 재선언 없음** · owner 허용 기록 없음.
울타리 3건은 선언 후보 뒤에 코드 스코프 커밋이 있으면 **설계상 빨간색**이고 승격 커밋 2건이 그 뒤에 더해졌다 —
재선언(오너) 없이는 초록이 될 수 없으므로, “22 passed”를 GO 로 읽지 않는다.
**다음**: 종료(20:25 KST) 뒤 `soak_control.sh harvest` 한 줄 — 판정 결과는 `GATE_LEDGER` §16 옆에 반영한다.

## 13. 3차 승격 배치 **준비 완료** — 리허설 ALL PASS, 본실행은 동결 해제 뒤 (2026-09-17, 4차 soak 실행 중)

오너 질문(“테스트가 끝날 때까지 기다려야 하나”)에 대한 답을 행동으로 옮긴 구간이다. **기다려야 하는 것은
8시간 soak 의 판정 하나뿐**이고(자동 — 상시 감시 + 회수 대기 화면), 나머지는 `docs/` 안에서 계속 진행된다.

1. **감시·통제 도구 3종 + 계약 시험 2종을 승격 3차 배치로 묶었다** — 이동표(`promote3/paths3.sh`)·게이트
   (`gates3.sh`)·미러 리허설(`dry_run_promotion3.sh`)·되돌림 가능한 본실행(`apply_promotion3.sh`)·
   승격 뒤 자동 재측정(`after_promotion3.sh`). 왜 옮기는지는 `PROMOTION_PLAN` §1e 에 있다: 이 셋은 오늘
   밤 내내 **판단을 내렸는데** 게이트가 하나도 지키지 않았다.
2. **리허설이 시험 쪽 결함을 잡았다**(`GATE_LEDGER` §23). 자기시험의 “건강하면 preflight 0” 픽스처 넷이
   깨끗한 작업 트리를 가정해 리허설(더러운 트리)에서 거짓 red 가 났다. 처방은 플래그를 박아 넣는 게 아니라
   **환경을 감지해 그 항목만 빼되 생략을 문장으로 밝히는** 것 — 깨끗한 트리 실트리 `75/75`(귀속 검사 그대로
   물림) · 더러운 트리 미러 `76/76`(생략 문장 확인 1건 추가) · `attempt4` **ALL PASS**.
3. **편집 안전 규칙을 지켰다**: `soak_control.sh` 를 고치기 전에 회수 감시(`screen nx10harvest`)를 내리고
   프로세스 0건을 확인한 뒤 재부착했다(돌고 있는 셸 스크립트는 읽히는 중이다).
4. **동결은 그대로다**: 이 창의 모든 편집은 `docs/` 이고 지문 `b6a74304…` 는 불변이다. 본실행 스크립트는
   도는데 soak 이 있으면 **거부**한다(가드 실측 확인). 본실행은 회수 직후 오너 지시로 실행한다.
5. **4차 soak 은 1h41m 시점 정상**: journal 1,373.9 MiB · 추정 687 ops/s(하한 133) · 종료 시 cap 추정
   6,537 / 8,192 MiB · **RSS 증가 +32.4 MB / 64 MB** · 최근 기울기 **+0.016 MB/분(허용 0.083 이내 — 48분의
   +0.210 에서 내려왔다)** · 누적 외삼 +154 MB. 워밍업(2h)이 풀리는 `05:25:56Z` 에 배지가 스스로 판단한다.
6. **산출물**: `promote3/dry-run3-attempt1..4.txt` · `promoted-contract-tests3.txt`(승격 위치 14 passed) ·
   `promoted-selftest3.txt`(생략 문장 + 76/76) · 실트리 자기시험 `selftest-attempt3.txt`(75/75).

**판정 불변**: required red 1(`python-tests`, 타 레인) · CR-14 후보 재선언 없음 · owner 허용 기록 없음 = **NO-GO**.

## 14. 회수 뒤 순서를 **무인으로 걸었다** (2026-09-17, 오너 요청)

한 줄: `screen nx10promote3` 가 `promote3/post_harvest_sequence3.sh --wait` 를 돌린다.

1. **순서**(종료 `11:25:56Z` = 20:25 KST 뒤 자동): 실행 종료 확인 → 회수 판정(기계 판독 원문
   `soak-recovery-latest.json` 의 `verdict`·`runner.exit`·시작/종료 지문) → 감시 도구 정리(프로세스 0건 확인)
   → 승격(`apply_promotion3.sh` · 실패 시 자동 롤백) → **커밋**(`clean-machine-runtime` 이 `--ref HEAD` 를 쓰므로
   커밋된 트리만 후보 값이다) → **새 지문에서 필수 23개 재측정**(약 19분) → 기록
   `promote3/post-harvest-record3.md`.
2. **멈추는 조건을 실측했다**(`rehearse_sequence3.sh`, 미러 3경로, ALL PASS — 본 트리 쓰기 0건):
   판정 FAIL → 멈춤·트리 무변경 · 시작 ≠ 종료 지문 → 멈춤·트리 무변경 · PASS + 지문 일치 → 승격·커밋까지 진행.
   무릅쓰고 강행하려면 `NX10_PROMOTE_ON_FAIL=1`(기본은 멈춘다).
3. **그 리허설이 네 번째 어긋남을 잡았다**: 계약 시험이 “도는 soak” 을 하드코딩된 이름으로 찾고 도구는
   환경변수 이름을 받아, 이름을 바꾼 환경에서 시험과 도구가 **다른 세계를 봤다**(거짓 red → 승격 게이트 A 가
   1 failed 로 멈춤). 고침은 하드코딩 제거(같은 이름 규칙 공유). 기존 규칙대로 “가드를 끄는” 대신
   “대상 이름을 통제하는” 통로를 썼다. 상세: `GATE_LEDGER` §24.
4. **재장전은 기본값이 아니다** — 밤에 두 번째 8시간을 자동으로 태우는 것은 오너 결정이라 `--rearm` 을
   주어야 한다. 취소: `screen -S nx10promote3 -X quit`(승격 전이면 트리 무변경; 승격 뒤에는 커밋이 롤백 지점).
5. **이 창은 20:25 KST 이후 트리를 만지지 않는다** — 옮기는 주체는 그 스크립트이고, 같은 시간에 `docs/` 밖을
   건드리면 새 지문이 흔들려 측정이 후보 값이 되지 못한다.

검증된 바이트: `post_harvest_sequence3.sh` sha256 `a429baa3cb1c…` · 리허설 기록 `sequence3-rehearsal.txt`
`0644abf1dac9…`(이 바이트로 ALL PASS 를 받은 뒤에 걸었다).
