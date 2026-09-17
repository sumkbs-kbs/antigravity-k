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

**도구:** [soak_control.sh](../../../../scripts/soak_control.sh) (3차 배치에서 `scripts/` 로 승격됨 — 스테이징 사본은 이동으로 사라졌다) — `arm`(지문을 지금 트리에서 계산) · `status`(단일 예약·고아·
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

**배치 바이트가 그 뒤 한 번 더 움직였고, 그때마다 리허설을 다시 돌렸다**(미러 `attempt6`→`attempt8`):
`soak_control.sh` 에 **셸 오탐 차단**(패턴에 걸린 셸은 하네스가 아니다) + 이빨 ⑧b, 그리고 계약 시험 docstring 의
자기시험 수. `attempt6` 이 **실패 2건**으로 멈췄는데 원인은 도구가 아니라 **내가 새로 넣은 이빨**이었다 —
그 자리만 공용 헬퍼를 안 쓰고 preflight 를 직접 불러 귀속 문을 빠뜨려, **더러운 트리에서만** 빨개졌다(§25-8).
문을 붙이고 “생략은 문장으로 밝힌다” 검사를 함께 넣어 `attempt7`·`attempt8` **ALL PASS**(계약 시험 `14 passed` ·
이동 5건 sha256 동일 · 자기시험 **79/79** · 스테이징 잔존 0). **본실행이 옮기는 바이트**는 이제
`soak_watch.py 88af4a5b5264` · `soak_watch_loop.py d7b1df867443` · `soak_control.sh 00661d6f2152` ·
`test_soak_watch_contract.py f7bf824145b7` · `test_soak_control_contract.py a713185925d4` 다.

## 15. SC-6 기준 정량 검토와 재설계 제안 (2026-09-17, 오너 질문 · 4차 soak 실행 중)

질문: “SC-6 RSS 기준이 워밍업 구간을 포함하는 게 맞나.” 답을 문장이 아니라 **표본으로** 내기 위해 분석기를 만들었다.

1. **산출물**: `analyze_sc6_criterion.py`(재현 가능한 분석기) → `sc6-criterion-analysis.txt`(출력 원문) →
   **[SC6_CRITERION_REVIEW.md](SC6_CRITERION_REVIEW.md)**(기준 설계 문서 = 재설계 제안서). 판정값의 소유자는 여전히
   `GATE_LEDGER.md` §16 이고, 이 작업의 해석·결정 요약은 **§25** 에 있다.
2. **답(한 줄)**: 포함한다 — 첫 표본이 **루프 50 반복 뒤**라 처리량에 따라 **0.08초 ~ 20.45초**로 움직이고,
   그 워밍업이 예산의 **15.2%(4차) · 33%(60초 리허설) · 3.8%(누수 실행)** 를 먹는다.
3. **가장 선명한 결함**: 워밍업 창을 **1분**으로 두면 종료 투영이 모델에 따라 갈리고(41.8~69.5 MB · 64 MB straddle),
   **27분 뒤에는 같은 계산이 갈리지 않는다**(32.1~61.8 MB) — 판정이 “어떤 모델”과 “언제 물었나”에 매달린다(분산 30.7→46.4%).
   창 **5분**이면 두 시각 모두 세 모델이 일치한다, 그 이상은 숫자 폭만 줄고 판정 구간을 잃는다 → 권고 `max(5분, 지속의 5%)`.
4. **률 한계 8 MB/h 는 성립하지 않는다**: 건강한 실행의 창 잡음이 30분 창 **16.2 MB/h** · 10분 창 **23.8 MB/h** 다.
   률 대신 **창 안 바이트**(20 MB/30분, 잡음 8.1 MB 대비 2.5배)로 물으면 누수 실행을 **40.0분**에 잡는다
   (현행 총량 기준은 **70.2분** — 운에 따라 8시간 끝까지 침묵).
5. **시간 예산 vs 반복 예산**: 605회/초에서 “64 MB/8시간” = **3.85 B/회** 인데 정상 creep 이 **2.93 B/회** =
   여유 **0.76배**(593회/초 시점에는 3.93 대 2.67 = **0.68배** — 시간이 갈수록 여유가 줄어든다 · 옛 처리량에서는 952.85 B/회). 처리량이 250배 오르면 고정 바이트 예산은 “누수가 있는가”가 아니라
   “얼마나 빨리 돌렸는가”에 답한다 → **반복당 지표 병기**가 필요하다.
6. **정정**: 중간 보고의 “30 MB 순간 최고치”(3건)는 **다른 pid 표본 6개가 섞여 만든 허상**이었다(§25-5 · 제안서 §3).
   실행 자신의 계열은 사실상 단조(최대 감소 −0.047 MB). 그 허상을 근거로 하던 절대 상한 논의는 취소하고
   대신 **창 길이 결정**을 오너 선택지로 올렸다(D-A).
7. **오너 결정 3건**(승인 전 코드 변경 없음): D-A 창 길이 · D-B 기준값 64 MB 의 지위(유지+병기 / 반복당 주 판정 /
   재산정) · D-C 60초 리허설의 SC-6 행(`not_applicable` 권고).
8. **순서 규칙**: 구현 대상 `scripts/val02_staging.py` 는 **지문 대상**이므로 4차 soak 종료 + 3차 승격 배치 뒤에만
   손댄다. 계약 시험 초안 6건(마지막 하나는 음성 대조군 FAIL 재현)은 제안서 §10 에 있다.
9. **관측된 별개 신호**: 이 실행의 **처리량이 195분에 704 → 516회/초(−26.7%)** 로 내려왔다(누수와 다른 축 —
   저널 증가·compaction 후보). 새 카드로 남긴다. 기준을 고쳐 덮지 않는다.
10. **분석기는 자기 스냅샷 시각을 첫 줄에 인쇄한다** — 진행 중 실행의 값은 매 분 변하고, 문서의 구조적 결론만 남는다.
   값을 다시 볼 때는 분석기를 다시 돌린다(문서·대장의 “진행 중” 숫자는 그 스냅샷의 사본이다).

## 16. SC-6 새 기준을 **코드와 시험으로** 고정했다 — 배치 `SC6` (2026-09-17, 오너 지시)

한 줄: 동결이 풀리는 즉시 한 줄로 적용된다 — `bash nx10/sc6fix/apply_sc6fix.sh`(지금 돌리면 동결 가드가 막는다).

1. **무엇을 옮겼나**: `sc6fix/val02_staging.py` → `scripts/val02_staging.py`(덮어씀) ·
   `sc6fix/test_sc6_criterion_contract.py` → `tests/test_sc6_criterion_contract.py`(신설).
   코드는 상수 셋 + **순수 함수 둘**(`sc6_warmup_window_s` · `sc6_rss_criterion`) + 시나리오 배선이고,
   판정은 `pass` 안의 옛 `growth <= 64` 를 **대체**한다(`not_applicable` 은 통과가 아니다).
2. **계약 시험 8건**(8시간을 태우지 않는다 — 합성 계열 1000표본): 창 안 계단 제외 · 짧은 실행 `not_applicable` ·
   반복당 creep 이 반복 수로 나뉨 · **음성 대조군**(누수 곡선이 두 축 모두 FAIL) · 리포트만으로 재현 ·
   반올림 틈 봉인 · 시나리오가 그 함수를 실제로 부르는지(배선 이빨) · 새 필드 스키마.
3. **가드 셋**: ① 동결 가드(도는 soak 이면 exit 9) ② **사전 이미지 sha256 고정**(다른 바이트 위에는 안 덮음 · exit 8)
   ③ 적용 뒤 검증 실패 시 **자동 롤백**. `--dry-run` 은 무엇을 바꿀지와 지금 가능한지만 말하고 쓰지 않는다.
   지금 dry-run 결론은 “지금은 적용할 수 없다(도는 soak)” 이다.
4. **리허설 ALL PASS 22건**(미러 · 본 트리 쓰기 0건): 사전 이빨(적용 전 계약 시험 실패) · 동결 가드 물림 ·
   ruff/format/basedpyright 0 errors · 계약 시험 8 passed · 기존 val02 시험 · **실제 60초 리허설이
   `not_applicable`+사유를 리포트에 남김** · 도구를 치우면 시험 빨게짐 · 다른 바이트 거부 · 본 트리 무변경.
5. **리허설이 진짜 결함 하나를 잡았다**(첫 회차 자동 롤백): 리포트는 0.1 MB 단위로 싣는데 creep 을 반올림 전
   값으로 계산해 **리포트만으로 재현하면 1e-4 어긋났다**. 반올림을 한 번만 하도록 고치고 그 틈을
   시험으로 봉인했다(`test_report_rounding_does_not_open_a_reproducibility_gap`).
6. **적용 순서**: 4차 soak 회수 → 3차 배치(도구 5건) 승격 → **배치 `SC6`** → 필수 게이트 재측정 →
   새 지문에서 8시간 soak(그 실행이 처음으로 새 기준으로 판정한다). 순서를 바꾸면 지문이 갈려 도는 실행이 무효다.
7. **남는 것**: 통과 경로(`not_applicable` 아님)는 픽스처로만 증명됐다 — 실물 규모는 다음 8시간이 처음이다.
   또 `rss_samples_mb` 는 처리량이 오르면 커진다(600회/초 × 8시간 ≈ 29만 표본 → 그 필드만 ~2 MB) — 다음 회수에서 실측한다.
8. **검증된 바이트**: `val02_staging.py ecd826ce90af…` · `test_sc6_criterion_contract.py cd4ff2da732b…` ·
   `apply_sc6fix.sh ea45db386c96…` · `rehearse_sc6fix.sh b34ef49cfdc1…` · 사전 이미지 `83da9a4885038bac…`.

## 17. 감시 pid 선택을 **엄격**하게 + 재부착 결함 수정 (2026-09-17 · 오너 지시 · 4차 soak 실행 중)

지시: “감시기가 실행 pid를 고를 때 감시 중인 workdir을 가진 하네스만 후보로 삼도록 고쳐서, 리허설 처리량
프루브가 계열에 섞이는 문제를 없애줘.” → 상세 기록 `GATE_LEDGER` §27.

1. **`soak_watch.py` 후보 규칙을 엄격하게**: argv 가 **선언한** `--workdir` 만 읽어 realpath 로 정규화한 뒤
   감시 workdir 과 비교한다. 선언이 없는 같은 이름의 파이썬은 `rejected_no_workdir` 로 빠지고, **맞는 후보가
   하나도 없으면 아무도 채택하지 않는다**(종전에는 “하나도 안 맞으면 전부 남긴다” — 그 틈이 §25-9 의 프루브였다).
   판정 줄이 **왜** 못 찾았는지(뺀 pid · 감시 workdir)까지 말한다.
2. **이빨 확인**: 필터만 무력화한 사본에서 종전 문이면 후보 `[선언없음, 외부]` 에서 **선언없음 pid 를 채택**한다
   = 같은 시험이 빨개진다(픽스처를 고쳐 통과시킨 게 아니다). 자기시험 **24/24** — ⑬ 픽스처도 이제 계약대로
   `--workdir` 로 뜬다(종전 픽스처가 관대한 문을 고정하고 있었다). `docs/` 위치 계약 시험 **17 passed**(169.95s).
3. **재부착 결함 발견·수정**: 새 바이트를 붙이자 루프가 **첫 표본에서 즉사**했다 — 연속 두 표본 확인 때문에
   갓 붙은 감시의 첫 표본은 항상 pid 가 없는데, 루프가 그걸 “실행이 사라졌다”로 읽었다(돌고 있는 soak 에
   감시를 붙이는 정상 운영이 불가능했다). → pid 없는 표본은 **기록하지 않고** 두 번까지 기다린다.
   계약 시험 `test_loop_attaches_to_a_run_already_in_flight`.
4. **지금 상태**: 감시 재부착 완료(`screen nx10watch` · 배지 정상 · `pid 78808` · 이력 247행 — 옛 pid 표본 7건은
   `soak-watch-history-pid*.jsonl` 로 보존 이동). 4차 soak 은 지문 `b6a74304…` 불변으로 계속 돈다.
5. **배치 3차 바이트가 바뀌었다** → 리허설 재실행: `attempt9` 는 `ruff format --check` 1건으로 멈추고(포맷만),
   `attempt10` **ALL PASS**(계약 시험 17 passed · 이빨 3/3 · 스테이징 잔존 0 · 이동 5건 sha256 동일). 본실행이
   옮길 **검증된 바이트**: `soak_watch.py fc8599af9d48` · `soak_watch_loop.py c38d16d58845` ·
   `soak_control.sh 00661d6f2152` · `test_soak_watch_contract.py 263ea2da0777` · `test_soak_control_contract.py a713185925d4`.
6. **미커밋**: 이번 변경도 커밋하지 않았다(`docs/` 전용 = 지문 불변). 요청하면 배치 준비분과 분리해 커밋한다.

## 18. “반복당 2~3 바이트”의 출처 추적 — 셋 다 아니었다 (2026-09-17 · 오너 질문 · 4차 soak 실행 중)

지시: “조작(반복)당 2~3 바이트씩 남는 메모리의 출처를 추적해서 **저널·캐시·인덱스 중 무엇이 붙잡는지** 밝혀줘.”
→ 상세·원자료 `sc6creep/FINDINGS.md` · `GATE_LEDGER` §28.

**답**: 선형으로 커지는 것은 **저널 파일(디스크)** 하나(+348~353 B/회 · 처리량 무관 · 실측 179 KB/s)이고,
메모리 증가는 그 저널을 *붙잡아서*가 아니라 **매 회차 할당·해제가 남기는 몫**이다.

1. **인덱스(sqlite) 기각**: sqlite 단독 국면 11,400회의 4분위 기울기가 871 → 407 → 190 → **15 B/회**(tracemalloc 끔)로
   수렴하고 WAL·shm 은 0 유지 — 디스크의 db 증가(+191 B/회)는 파일이지 메모리가 아니다.
2. **캐시(인메모리 레코드) 기각**: `messages ≤ 64(soft max)` · `summary 1.3 KB` · `carried_summary 900자 고정` ·
   `summarized_ranges 8 고정` · `gc.collect()` 후 객체 수 불변 · tracemalloc 생존 바이트 후반 0.4~3 B/회.
3. **churn 임을 대조군이 증명**: 저장소 코드 0줄의 같은 일감량이 **285~390 B/회**를 재현했고, 같은 일감을
   10배 빠르게 돌리면 반복당 증가가 **1,143 → 659 B/회** 로 줄었다(보유라면 처리량 무관해야 한다).
4. **실측 4차 정상상태**: 최근 1시간 RSS +2.4 MB(0.7 KB/s = 1.2 B/회) vs 저널 +604 MB(179 KB/s) — **0.4%**,
   즉 둘은 분리되어 있다. 초반 몇 분의 fill(≈ +18 MB)이 8시간 총량의 대부분이다.
5. **계측기가 만든 몫도 분리**: 같은 sqlite 국면이 tracemalloc 켬 **219 B/회** · 끔 **15 B/회** (도구에
   `--no-tracemalloc` 을 둔 이유).
6. **다음 행동**: ⓐ SC-6 기준의 워밍업 제외는 옳다(근거가 생겼다) ⓑ 진짜 한계는 **디스크 상한 없음**
   (ADR §8 retention/quota = 릴리스 blocker 확정) ⓒ 남은 churn 의 1순위 후보는 `_persist` 의 view 전체
   재작성(지문 대상 — 동결 해제 뒤 별도 배치).
7. **도구**: `sc6creep/probe_creep_source.py`(`--only abcd` · `--no-tracemalloc` · `--rate`) — `docs/` 전용이라
   지문 불변·**읽기 전용 원칙**(저장소 코드는 import 만, 쓰기는 임시 작업 루트 안에서만).

## 19. 처리량 감소를 **1급 판정 축**으로 — 배치 `PERF` (2026-09-17 · 오너 지시 · 4차 soak 실행 중)

지시: *“처리량 감소를 1급 판정 축으로 삼는 성능 회귀 게이트를 설계해줘 — 8시간 동안 27% 느려진 실행을
RSS 누수와 별개로 잡아내야 해.”* → 설계 전문 `perf/THROUGHPUT_GATE_DESIGN.md` · 대장 `GATE_LEDGER` §29.

**핵심 결론(실측)**: **벽시계 처리량 단독으로는 게이트가 될 수 없다.** 4차 실행 30분 블록은
벽시계 **−26.5%**(요구 임계 27% 와 사실상 같다)인데 효율은 **−5.0%** 이고 이용률만 −22.6% 였다
(오늘 이 기계에서 게이트·리허설·프로브를 돌렸다). 그래서 판정은 다음 분해로 한다:

```
벽시계 처리량 = 효율(ops/CPU초) × 이용률(CPU초/벽초)
   효율↓            → 제품 회귀(fail)
   이용률↓·부하 높음 → 재실행 요구(not_applicable)
   이용률↓·호스트 조용 → 서비스 회귀(fail — “대기가 늘었다”)
```

1. **축 분리** — RSS(§26)와 **완전 독립**임을 계약 시험 #7(네 조합)이 고정한다. 시험 #10 은 **오늘의
   그 실행**(`live-4th-series.json`, 실측 표본 288개)을 “제품 회귀”라 부르지 않는다 — 허용 감소 15% 는
   이 실행의 −26.5% 를 **제품 탓으로 돌리지 않으면서** 27% 회귀와는 12%p 여유를 둔다.
2. **임계는 전부 실측 보정** — 60초 표본 잡음 CV 16.8% → 두 점 비교 금지(블록 `max(5분, 지속×2%)` + 사분위
   중앙값) · 10분 블록 편차 중앙 8.4% · `load1/코어 > 0.5` 면 단정하지 않음.
3. **`not_applicable` 은 통과가 아니다** — 60초 스모그에서 **둘 다 면제인데 `pass=True`** 라는 문을 발견해
   `criteria_gate` 로 막았다(긴 실행의 면제는 재실행 요구).
4. **합성 순서 = SC6 → PERF** — 둘이 같은 파일(`scripts/val02_staging.py`)을 바꾼다. 사전 이미지 해시가
   SC6 적용 뒤 이미지(`ecd826ce90af…`)이고, 동결 트리 바이트(`83da9a48…`)를 만나면 “SC6 먼저”로 멈춘다.
5. **리허설 ALL PASS 17/17**(미러 · 본 트리 쓰기 0건 · §20 의 귀속 사다리 합류 뒤 재측정) — P1 적용 전 이빨 · P2 적용·검증(승격 위치 정적
   검사 포함) · **P2b 승격 위치 타입 오류 → exit 5 + 자동 롤백** · P3 동결 가드(exit 9) · P4 합성 순서(exit 6) ·
   P5 사전 이미지 불일치(exit 8) · P6 지문 대상 전후 동일.

   리허설이 결함 **2건**을 찾았다: 면제인데 `pass=True` 인 문(→ `criteria_gate`)과, 계약 시험 파일이
   `docs/` 안에 있는 동안 **정적 게이트의 시야 밖**이라 `basedpyright` 오류 **5건**을 숨긴 것(승격하면
   `python-basedpyright` 가 빨개지는 부류 — §13/§16 에서 같은 부류를 실제로 겪었다). 후자를 고친 뒤
   `apply_perf_gate.sh` 검증에 **승격 위치 정적 검사**(ruff check/format + basedpyright)를 넣었다.
6. **남은 것 = 오너 결정 3건**(D-P1 허용 15% 확정 · D-P2 경합 시 재실행 요구 · D-P3 최소 2시간).
   승인 뒤 본실행: `bash perf/apply_perf_gate.sh` → 필수 게이트 재측정 → 새 지문에서 8시간 soak.

**지문 불변**: 이번 변경은 전부 `docs/`(`nx10/perf/`)라 `src/`·`scripts/`·`tests/` 쓰기 **0건**(실측).

## 20. 귀속 사다리 — “어느 호출이 느려졌나”를 자동으로 좁힌다 (2026-09-17 · 오너 지시 · 4차 soak 실행 중)

지시: *“처리량 회귀가 잡혔을 때 어느 호출이 느려졌는지 자동으로 좁혀 주는 귀속 사다리를 설계하고 계약
시험으로 고정해줘.”* → 설계·실측 `perf/THROUGHPUT_GATE_DESIGN.md` §9 · 대장 §30. 배치 `PERF` 에 합류.

**사다리는 다섯 칸이고, 올라가는 게 아니라 내려간다** — 게이트가 빨간 실행에서만 돈다:

1. 한 반복을 **세 국면**으로 나눈다(`task.create` · `task.transition` · `conversation.append`). 하네스가
   경계에서 `process_time()` 을 적립하고 반복 끝에서 시계를 청구 없이 리셋한다 → 루프·표본·할당자·GC 는
   어느 국면에도 안 붙고 **잔차**가 된다(그 잔차가 “계측 밖” 판정의 근거다).
2. 분기 단가(µs/반복) 증가분을 국면별로 쪼갠다. **총량은 프로세스 전체 표본에서 따로 잰다** — 국면 합을
   총량으로 쓰면 잔차가 정의상 0 이 되어 세 번째 칸이 영영 안 난다(첫 구현이 그랬다).
3. 판정: 한 국면 ≥ 50% → **이름 지목** / 균등 → `spread` / 잔차 > 50% → `outside_phases` /
   증가가 잡음(2% 미만) → **아무도 지목하지 않음**(`insufficient`) / 게이트 초록·짧은 실행 → 안 돎.
4. 빨라진 국면은 **음수 기여**로 남고 범인으로 안 지목된다.
5. 다음 칸을 문장으로 낸다: `phase` → 그 국면 하위 단계 / `outside_phases` → 프로세스 전체 프로파일.

**이빨**: 계약 시험 **23 passed**(처리량 13 + 사다리 10) · `ruff` · `basedpyright 0 errors` ·
미러 리허설 **ALL PASS 17/17**(P1 이 “사다리 시험도 SC6 도구에서 빨개진다”까지 확인).

**실측(프로브, 60초 실행 3회 · `perf/probe-ladder-output.json`)**: 국면 단가 `create 500 µs` ·
**`transition 980→1,000 µs`(가장 비쌈)** · `append 760 µs` — 그리고 **Σ 국면(2,240 µs/반복) = 전체 표본
총량(2,240 µs/반복)** 으로 정체식이 실측에서 성립한다. A(상수 그대로)는 게이트가 판정하지 않는 이유를,
B(노브)는 게이트가 실제 계열로 판정을 내는 것을, C(게이트 인위 빨강)는 사다리가 실제 계열을 쪼개는 것을 본다.

**남는 한계(먼저 적는다)**: `phase` 칸은 아직 **합성 픽스처로만** 증명됐다 — 그 칸을 실측으로 태우는 것은
다음 8시간 soak 이다(회귀가 없으면 `not_applicable` 로 끝난다). 국면은 경계까지만 보고, 국면 목록은
하드코딩이며, `process_time()` 기반이라 **대기**는 국면 단가에 안 들어간다(대기는 이용률 축이 잡는다).

**검증된 바이트(갱신)**: `val02_staging.py d4771262…` · `test_throughput_gate_contract.py 6dbef041…` ·
`probe_ladder_end_to_end.py c55a266c…`(도구 · 이동 안 함). **지문 불변**(`docs/` 전용).

## 21. 사다리의 다음 칸 — 국면 안의 하위 단계, 그리고 그 칸이 찾아낸 것 (2026-09-17 · 오너 지시)

지시: *“지목된 국면 안의 하위 단계(저널 append · view 재작성 · tail 같은)까지 자동으로 좁히는 사다리 다음
칸을 설계하고 계약 시험으로 고정해줘.”* → 설계·실측 `perf/THROUGHPUT_GATE_DESIGN.md` §10 · 대장 §31.

**왜 창 프로파일인가**: 그 하위 단계는 제품 코드(`src/`) 안에 있고 그 파일은 **지문 대상**이다 — 잴 때마다
제품에 타이머를 심을 수 없다. 그래서 하네스가 **창 단위로 `cProfile`** 을 걸되 ① 창 하나 = 국면 하나(돌려
가며) ② **계측한 반복은 판정 계열에서 제외**(프로파일러가 국면을 1.5~1.57배로 부풀린다 — 실측) ③ 오버헤드·
계측기 몫·음수 잔차를 리포트에 밝힌다.

**판정**: 앞칸이 지목한 국면에만 묻는다 — 한 함수 ≥ 50% → **`function`(이름 지목)** / 퍼짐 →
`spread_within_phase` / 파이썬이 못 본 몫 > 50% → `outside_functions`(syscall·C 스택 도구로) / 창 부족 →
`insufficient`(무지목) / 앞칸 미지목·60초·계측 끔 → `not_applicable`(사유 문장).

**이 칸이 곧바로 답을 냈다(프로브 D · 실제 하네스 60초 · 창 13개)**:

```
task.create        604 µs/반복  ← builtins.next 587 · sqlite commit 555 · execute 203
task.transition  1,085 µs/반복  ← builtins.next 472 · sqlite execute 398 · commit 305
conversation.append 1,223 µs/반복 ← posix.fsync 847(69%) · posix.replace 98 · _io.open 80  → function: posix.fsync
```

즉 `conversation.append` 의 지배 항은 **내구성 flush(`fsync`)** 이고 view 재작성·tail 은 그 뒤다 — 국면
이름만 보면 “JSON 직렬화가 느린가?”로 읽히지만 실제 처방은 **flush 정책·배치**다.

**이빨**: 계약 시험 **35 passed**(처리량 13 + 국면 귀속 10 + 국면 내부 12) · 미러 리허설 **ALL PASS 17/17**.

**계측기를 만들며 네 번 틀렸고 프로브가 셋을, 타입검사가 하나를 잡았다**(대장 §31-4): 창이 닫힌 뒤 꼬리
호출까지 계측해 **창이 두 번 닫힘**(14/26/0 → 세 번째 국면이 영영 안 돌았다) · 호출마다 창 전체 시간을 다시
더해 단가 폭주 · `getstats()` 의 **[3]=cumtime · [4]=tottime** 을 반대로 읽음 · 계측기 자신이 **순위 1위**.
앞의 둘은 계약 시험 ㉝(**창 수 × 창 크기 = 계측 호출 수**)과 ㉞(**음성 대조군: 옛 규칙이면 창 40 → 3,776**)로
고정했다 — ㉞ 는 두 가드를 **모두** 무력화해야 재현된다(한쪽만 풀면 다른 쪽이 막는다는 것도 적어 뒀다).

**검증된 바이트**: `val02_staging.py 84ab2c93…` · `test_throughput_gate_contract.py 64dde41f…` ·
프로브 `731f7f76…`(출력 `d19c44a3…`). **지문 불변**(`docs/` 전용).

## 22. 사다리 네 번째 칸 — 지목된 함수를 **누가·얼마나 자주** 부르는가 (2026-09-17 · 오너 지시)

지시: *“지목된 함수가 어느 호출 경로에서 얼마나 자주 불리는지까지 자동으로 좁히는 사다리 네 번째 칸을
설계하고 계약 시험으로 고정해줘.”* → 설계·실측 `perf/THROUGHPUT_GATE_DESIGN.md` §11 · 대장 §32.
새 바이트: **`val02_staging.py a67695013fde…` · `test_throughput_gate_contract.py e47a4151872d…`**
(앞 절의 `84ab2c93…`/`64dde41f…` 는 이 칸을 넣기 전 값이다 — 승격 전에 반드시 다시 확인할 것).

**핵심 결정**: “누가 부르나”(경로)와 “얼마나 자주 부르나”(빈도)를 **별도 필드로** 낸다. 이유는 하나다 —
처방이 다르다. 반복당 1회면 그 호출 자체를 싸게(정책·배치), 여러 번이면 **호출을 합친다**(코얼리싱).
경로 판정(`path`/`multi_path`/`insufficient`/`not_applicable`)은 빈도에 안 흔들린다.

**자료는 이미 있었다**: 호출자 표는 `cProfile` 이 벌써 만들고 있다. 다만 `Profile.getstats()` 의 6번째 칸은
**callees**(내장 함수는 `None`)이고 호출자가 아니다 — 그걸 호출자로 읽은 첫 구현은 바로 `None` 을 만났다.
`pstats.Stats(profile).stats` 를 쓴다(교체가 숫자를 안 바꿨는지 실측 확인: `pstats.tt`==`raw[4]` ·
`pstats.ct`==`raw[3]` 이 상위 6개 프레임에서 소수점까지 일치). 주의: `Stats(profile)` 는 `profile.stats`
를 **비운다** — 창마다 새 `Profile` 을 쓴다.

**실측(프로브 E · 실제 하네스 60초 · 창 13개)**:

```
판정: path · posix.fsync · 반복당 1.00회 (at_most_once_per_iteration)
호출자: conversation_journal.py:_fsync_fd (몫 1.00 · 호출 325회)
사슬: posix.fsync ← _fsync_fd ← _append_bytes ← conversation_journal.py:append ← _commit_event
```

반복당 **정확히 1회**이므로 코얼리싱으로 줄일 것이 없다 — 처방은 그 한 번을 싸게 만드는 정책·배치다.

**이빨**: 계약 시험 **47 passed**(호출 경로 12개 추가) · 미러 리허설 **ALL PASS 17/17**.

**같이 밝혀진 것 — 셋째 칸(국면 내부)의 *몫*은 흔들린다**: 같은 일감 200 반복을 세 번 재니 `posix.fsync`
자기 시간이 **1,930 µs(54.9%) · 27.5 µs(2.7%) · 27.9 µs(2.6%)** 로 70배 달라졌다(디스크가 더러운가에 달렸다).
그래서 첫 프로브의 “847 µs = 69% → `function`”이 다음 프로브에서 “405 µs = 33% → `spread_within_phase`” 로
바뀌었다 — 둘 다 틀린 값이 아니고 *그 때의 디스크* 값이다. **순위와 호출 횟수**를 읽고 몫은 “그 순간의 크기”로
읽어야 한다(그게 네 번째 칸의 빈도 축이 결정적인 이유다).

**계약을 하나 밟았다**: 창은 `index % DEEP_SAMPLE_EVERY == 0` 인 반복에서만 열리므로, 창 상한 40을 다 쓰려면
반복 인덱스가 `40 × 200` 이상 흘러야 한다. 1,200 반복짜리 시험 구동은 국면당 창이 2개로 끝나 네 번째 칸이
`insufficient` 로 죽는다(실측으로 밟았다) → 시험 구동을 20,000 반복으로 올렸다(실제 8시간·4시간은 무관).

한계: `path` 칸은 프로브 노브에서 나온 것이고 8시간 연쇄는 아직 안 태워졌다 · 앞칸이 `function` 일 때만 돈다 ·
호출자가 C 쪽이면 답하지 못한다 · 호출자 수는 창 안의 호출만 센다.

## 23. flush 배치 설계(`FLUSH`) — fsync 를 어떻게 다룰 것인가 (2026-09-17 · 오너 지시)

지시: *“`conversation.append` 의 fsync 69% 를 근거로 flush 정책·배치 대안들을 동결 해제 뒤 지문에 반영할 수
있는 배치로 설계해줘.”* → 설계 [fsync/FLUSH_BATCH_DESIGN.md](./fsync/FLUSH_BATCH_DESIGN.md) · 대장 §33.
**본실행하지 않았다** — 이 배치가 바꿀 것은 `src/` 이고 그게 바로 **지금 돌고 있는 4차 soak 의 지문 대상**이다.

**한 줄 요약**: 69% 는 *그 때의 디스크* 값이었다(같은 일감 3회에서 70배 흔들림). 곡선을 재보니 fsync 는
“캐시가 더러운가”의 계단 함수이고(0 MB **22 µs** → 8 MB **341 µs**), 일감 크기(저널 271 B/회)와 무관한
**300~350 µs 고정세**다. 그래서 “직렬화를 줄이면 fsync 가 싸진다”는 **성립하지 않는다** — 지렛대는
① sync 를 덜 부른다(정책) ② fsync 주변을 덜 쓴다(예산) 둘뿐이고, 그 둘은 **성격이 달라 다른 부품**으로 나뉘다.

**세 부품**:

| 부품 | 무엇 | 계약 영향 | 상태 |
| --- | --- | --- | --- |
| **F1** | 꼬리 읽기 **3회 → 1회** (+ 통계 최소화) | **없음** | 스테이징 + 미러 리허설 **ALL PASS 16/16** |
| **F2** | view 재작성 **스로틸**(8 KB + rename/회) | 읽기 신선도 | 설계만(D-F2) |
| **F3** | **sync 정책**(`always`/`batched`/`fdatasync`) | **ADR-DAT-02 §2 문장 변경** | 설계만(D-F3) |

**F1 의 근거는 시간이 아니라 개수**다(디스크 상태와 무관한 결정적 실측): append 1회에 `tail()` **3.00회** ·
읽은 바이트 **116,025 B(≈113 KiB)** · `open` 5.00 · `fsync` 1.00 · view 재작성 1.00회·8,021 B. 꼬리 3회의 출처는
네 지점(`_authoritative_record` · `_reconcile_view_with_journal` · `_commit_event` · `journal.append`)인데 **실제로는
같은 flock 임계 구역 안**이다 — 구역에서 쓰지 않으면 꼬리는 변하지 않으므로 **한 번만 읽고 나눠 쓸 수 있다**.
기대: `tail()` 3.00 → **1.00** · 읽은 바이트 ≈113 KiB → **≈38 KiB** · `open` ≤4 · **`fsync` 1.00 불변**.

**F1 의 안전 논변**: 기억의 수명은 **한 임계 구역**이다. 구역 안에서 꼬리를 바꿀 수 있는 것은 우리뿐이고(다른
프로세스는 flock 을 못 잡는다), 우리가 바꾸면 그 자리에서 비운다. 구역이 바뀌면 **진입에서** 비운다 — 그래서
시험 ⑤ 가 “CAS 실패 + 타 writer 전진 뒤에도 revision 이 중복되지 않는가”를 직접 겨냥한다.

**미러 리허설 ALL PASS 16/16**: P1 적용 전 **3 failed**(예산·소스 이빨이 진짜 문다) · P2 적용 뒤 9 passed +
ruff + basedpyright **0 errors** · P2b 심은 타입 결함을 물고 롤백 · P3 기존 시험 **70 passed**(journal·
retention·CR-01 identity·FR-05 authoritative·multiprocess) · P4 동결 **exit 9** · 합성 순서 **exit 6** ·
P5 사전 이미지 **exit 8** · P6 본 트리 무변경.

**이 설계를 만들다 도구 교춘 2건을 실제로 밟았다**(둘 다 리허설이 거짓 FAIL 을 내서 잡았다): ① 저장소 루트에서
절대경로로 정적 검사를 돌리면 임포트 해석이 **진짜 `src/`** 를 집어 미러의 새 시그니처를 못 보고 “No parameter
named tail” 을 거짓 보고한다 — 정적 검사는 **그 바이트를 소유한 뿌리**에서 돈다. ② **`basedpyright` 는 경고만
있어도 exit 1** 이다(errors 0 · warnings 116 · exit 1 실측) — 판정은 종료 코드가 아니라 **파싱한 `errorCount`** 로
한다(안 그러면 깨끗한 패치를 롤백한다). 두 번째는 `apply_flush_batch.sh` 에도 전파해 고쳤다.

**가드·순서**: 동결(exit 9) · 합성 순서(exit 6 — 이 배치는 지문을 움직이므로 **PERF 뒤 맨 마지막**) · 사전
이미지(exit 8) · 검증 실패(exit 5 + 자동 롤백). 순서: **4차 soak 회수 → 3차 배치 → SC6 → PERF → 게이트
재측정 → FLUSH → 게이트 재측정 → 새 8시간 soak**.

**오너 결정**: D-F1 F1 승인(계약 변화 없음) · **D-F2** view 스로틸(읽기 신선도 계약을 어디까지 늦출지) ·
**D-F3** sync 정책 — 바꾼다면 ADR §2 를 먼저 고쳐야 하고 권고는 **보류**(유실 창은 되돌릴 수 없다) ·
**세 대안 → 배치 셋(오너가 고르는 표는 설계 §10-1)**: `FLUSH`(F1 · 계약 불변 · **바로 적용 가능**) ·
`FLUSH2`(F2 · “개수를 줄이고 표시만 늦춘다” — 훅 4개 + 시험 후보 5건, 기본값이 현행 `immediate` 라 무회귀) ·
`FLUSH3`(F3 · “계약을 바꾼다” — **ADR-DAT-02 §2 개정 6문장이 코드보다 먼저**, 시험 후보 6건엔 크래시 시뮬레이션
포함 · 되돌림은 노브 한 줄). 결정 뒤 만드는 조건(훅·시험·사전 이미지·합성 순서 `FLUSH→FLUSH2`·지문에 일어날 일)은
설계 **§10**. 검증된 바이트(2026-09-17T10:01Z): 패처 `e2016ef42ced…` · 시험 `59d469ead4e1…` ·
apply `92fdcef5b0e3…` · rehearse `945250421759…` · **리허설 재확인 ALL PASS 16/16**(P1 이빨 3 failed ·
P2 9 passed+basedpyright 0 · P2b 롤백 · P3 70 passed · P4 exit 9·6 · P5 거부 · P6 본 트리 sha256 동일).

**D-F3′** “durable” 의 플랫폼별 정의(macOS `os.fsync` ≠ `F_FULLFSYNC` — 지금 문구가 덮고 있는 구멍) ·
**D-F4** 지금 GA 후보를 보낼지, 이 배치를 넣고 다시 잴지.

**바이트**: 사전 이미지 `conversation_journal.py a89dfd2d82cc…` · `conversation_store.py 7f3e4605da9d…`.
**지문 불변**(`docs/` 전용 — 리허설 P6 이 실측 확인).

---

## 24. view 신선도 계약 — “방금 쓴 턴이 언제 보여야 하는가”(배치 `FLUSH2` · 2026-09-17 · 오너 지시)

지시: *“view 재작성 스로틸(F2)을 위해 ‘방금 쓴 턴이 언제 보여야 하는가’ 신선도 계약을 정하고, 그 문장을
계약 시험으로 옮겨 둬.”* → **결정문** [fsync2/VIEW_FRESHNESS_CONTRACT.md](./fsync2/VIEW_FRESHNESS_CONTRACT.md) ·
대장 **§34** · 개념은 FLUSH 설계 §10-2. 본실행 전(동결 중).

**한 줄 요약**: 신선도는 **파일이 아니라 반환값**의 성질이다 — 공개 읽기는 모두 `_refresh_latest` 를 지나고
view 가 뒤처지면 journal 로 재생성하므로, 답은 **“커밋 즉시 보인다”** 이고 지연될 수 있는 것은 표시용 **파일**뿐이다.
계약 8문장: C-1 반환값 · C-2 판정은 시퀀스 · C-3 유한 창 · C-4 따라잡기에 저널 재생 금지 · C-5 수렴점 ·
C-6 기본값 현행 · C-7 읽기 수렴 · C-8 삭제는 안 되살아난다.

**이 조사가 드러낸 결함 두 가지(둘 다 실측)**:
① **mtime 판정은 거짓이었다** — 복원·동기화가 옛 view 를 **새 mtime** 으로 놓으면 읽기가 `revision 1` 을 돌려줬다
(저널 tail seq 는 3 — **커밋된 턴 2개를 놓쳤다**). `st_mtime_ns` 를 판정에서 제거하고 시퀀스 비교로 바꿨다(시험 ②③).
② **순진한 미루기는 회귀**였다 — 3회에 1회로 미루면 미룸당 **저널 전체 재생 1.17회**(3 KiB 저널에서도). 8시간
soak 의 저널 크기에서 그 재생이 하루를 날렸던 부류이므로 C-4 로 금지하고 시험 ④가 “지연은 있는데 재생은 0”을 잰다.

**이득(결정적·400턴 실측)**: view 재작성 **402 → 52회**(1/8) · 다시 쓴 view 바이트 **5.6 MB → 0.70 MB** ·
저널 재생 **0**. 같은 400턴에서 저널(내구)은 110 KB 자라는 동안 view(표시용)는 5.6 MB 를 다시 썼다 — **표시용이
내구 기록보다 약 51배** 많이 쓴다. 시간은 주장하지 않는다(F1 과 같은 이유 — 디스크 상태에 흔들린다).

**배치**: `conversation_store.py` **하나**(훅 12개) · 계약 시험 **10건** · 노브 `AGK_CONVERSATION_VIEW_REFRESH`
(기본 `immediate` = **현행 그대로**) · 가드 동결 `exit 9`·사전 이미지 `exit 8`·합성 순서 `exit 6`·자동 롤백 `exit 5` ·
**사전 이미지가 F1 적용 뒤**(`conversation_store.py c9029151ccbd…`)라 F1 이 선행이다. 미러 리허설 **ALL PASS 21/21**:
P0 F1 없이 → `exit 8` · **P1 적용 전 이빨 8 failed/2 passed** · P2 적용 뒤 10 passed + ruff + basedpyright 0 ·
P2b 심은 결함 롤백 · P3 기존 **70 passed** + F1 예산 **9 passed** 무회귀 · P4 `exit 9`·`exit 6` · P5 거부·쓰기 0건 ·
P6 본 트리 sha256 동일. 전문 `fsync2/rehearsal-output.txt`.

**바이트**: 패처 `d9186ad2125b…` · 시험 `3002bc7034bb…` · apply `3ab331ccbe83…` · rehearse `a8fc759be967…`.
**적용 순서**: … → `FLUSH` → 게이트 재측정 → **`FLUSH2`** → 게이트 재측정 → 새 8시간 soak.
**D-F2 의 상태**: 계약으로 **답했다** — 켤 시점만 정하면 되고(옵트인), 되돌림은 환경변수 한 줄이다.
**지문 불변**(`docs/` 전용 — 리허설 P6 이 실측 확인).

---

## 25. ADR-DAT-02 §2 개정 **초안** — sync 정책과 “durable” 의 뜻(배치 `FLUSH3` · 2026-09-17 · 오너 지시)

지시: *“sync 정책 batched 를 위한 ADR-DAT-02 §2 개정 초안을 유실 창 정의·관측·플랫폼별 durable 문장까지 갖춘
리뷰 가능한 형태로 작성해줘.”* → 초안 [fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md](./fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md) ·
대장 **§35** · 근거 [fsync3/probe-durability-output.json](./fsync3/probe-durability-output.json). **코드는 안 썼다**(승인 뒤).
ADR 본문에는 **비규범 포인터 한 줄**만 넣었고 Status 는 `Proposed` 그대로다.

**한 줄 요약**: 현행 §2 는 순서 규칙(정확 — 그대로 둔다)과 “durably committed”(**과대 약속** — macOS 의
`os.fsync` 는 미디어 보장이 아니다)을 섞어 적었다. 그래서 초안은 내구성을 낮추자는 게 아니라 **등급에 이름을 붙이고
유실 창을 정의하고 관측하게 만들자**는 것이다.

**실측(같은 파일 · 271 B/커밋 · 605 ops/s → 커밋당 예산 1,653 µs)**:

| 등급 | 주기 | µs/커밋 | 예산 대비 |
| --- | --- | --- | --- |
| `cache`(`os.fsync`) | 1회/커밋(현행) | **45.37** | **2.74 %** |
| `cache` | 8회에 1회 | **9.82** | 0.59 % |
| `media`(`F_FULLFSYNC`) | 1회/커밋 | **4,008.13** | **242.5 %** |
| `media` | 8회에 1회 | 527.91 | 31.9 % |

단발: `os.fsync` 44.2 µs vs `F_FULLFSYNC` 4,163 µs(**94배**) · 8 MB 를 쌓고 sync 1회 = 1,710 µs(0.055 µs/커밋) ·
플랫폼 `darwin`(+`F_FULLFSYNC`, −`os.fdatasync`).

**이 숫자가 뒤집는 것**: `cache` 등급은 이미 예산의 2.7 % 라 `batched` 로 0.6 % 를 만들자고 **약속(유실 창)을
바꾸는 것은 남는 장사가 아니다**. 반대로 `media` 는 **커밋마다 줄 수 없다**(242 % = 반복 1회의 2.4배) — 진짜
미디어 보장은 **핫패스 밖**에만 있다. 그래서 개정의 핵심은 동기화 주기가 아니라 **등급 이름·창·강등·관측**이다.

**초안이 넣는 문장**: 등급 셋(`process`/`cache`/`media`) · 창 정의(“*가장 최근 성공한 sync 이후 커밋된 줄들만
사라질 수 있다 — 사라짐이지 뒤바뀜이 아니다*”) · `store_usage()` 에 `sync_policy`·`sync_level`·`sync_pending`·
`last_sync_at` · 강등은 **로그 1회 + 조용한 강등 금지** · 플랫폼 표(macOS `F_FULLFSYNC` · Linux `fdatasync` ·
모르면 `media` 요구 거부) · **바뀌지 않는 것**(순서·미결 꼬리·재생 결정성·기본 동작 불변 — F1 계약 시험 ②는
기본 등급의 계약으로 남고 `batched` 는 별도 시험을 갖는다).

**오너 결정 D-F3-1~4**(초안 §8 · 권고와 대가를 함께 적었다): 기본 등급(`cache` 유지 + 이름 정정 권고) ·
`media` 단위(대화별 옵트인 권고) · `batched`(**하지 않는다** 권고) · 관측 위치(`store_usage()`+로그 1회 권고).
계약 시험 후보 7건은 초안 §7. **선행물**: ADR 승인 → 그 뒤 `src/` 적용(지문이 움직이므로 `FLUSH`·`FLUSH2` 뒤).

**바이트**: 초안 `34c58781bd6a…` · 프로브 `f9f44dfb6eff…` / 출력 `80987eb3c978…`.
**지문 불변**(`docs/` + ADR 포인터 한 줄 — `src/`·`scripts/`·`tests/` 쓰기 0건).

## 26. `media` 를 핫패스 밖에서만 — 비용 모델과 간섭 실측(**D-F3-2 결정지 채움** · 2026-09-17 · 오너 지시)

지시: *“media 등급을 핫패스 밖(주기·체크포인트·셧다운)에서만 돌리는 대안을 비용 모델과 함께 비교해서,
D-F3-2 결정지를 채워줘.”* → [fsync4/MEDIA_OFFLOAD_COST_MODEL.md](./fsync4/MEDIA_OFFLOAD_COST_MODEL.md) ·
대장 **§36** · 프로브 [run-a](./fsync4/probe-media-offload-run-a.json)/[run-b](./fsync4/probe-media-offload-run-b.json) ·
계기·문서 계약 시험 **17건 passed**(**[test_media_offload_contract.py](./fsync4/test_media_offload_contract.py)** — 계기 16 + 문서↔픽스처 대조 1).
**코드는 안 썼다** — ADR-DAT-02 §2 승인이 선행물이고, 그 초안(§3-3·§7·§8·§9)을 이 실측으로 갱신했다.

**한 줄 요약**: `media` 를 핫패스 밖으로 옮기는 비용은 **주기만 정하면 사실상 공짜**(T=10 s → 예산의 0.044 %,
T=60 s → 0.0073 %)지만, **배경에서 부르면 쓰는 쪽이 멈춘다** — 200 ms 주기에서 최대 **3.2 s** 밀림, 중앙 −2.2~−27.4 %.
밀림은 **전부 진행 중인 호출과 겹쳤고**(기준선 10블록엔 0건), **다른 파일이어도 멈췄다**. 그래서 결정은 단위가 아니라
**“언제 부르는가”** 로 옮겨 간다: **대화별 옵트인 + 상한 `T_max` 가 있는 정지 감지**(조용한 창의 호출은 4.0–4.1 ms ·
아무도 안 멈춘다. 강행할 때는 스톨을 관측에 남긴다).

**비용 모델**(교차 반복·최소값): 호출은 **부피와 무관한 배리어**다 — 바닥값 4,383/4,216 µs 가 **8.9 MB 호출에서도
67 %/59 %** 를 차지하고, 유휴 호출도 4,119/4,013 µs 다(비용은 호출당). 이웃 dirty 64 MB 도 **0.99×/1.02×**
(남의 바이트를 지불하지 않는다). 부피 항은 **식별되지 않아**(판정이 실행마다 뒤집힘) 상한 0.33/0.43 µs/KB + 민감도 열로만 적는다.

**대안 다섯**: 전역 주기(기각 — 비용 곱셈 + **다른 대화의 호출이 이 대화를 멈춘다**) · 대화별 옵트인(조건부) ·
체크포인트(기각 — 핫한 대화는 회전하지 않아 **창이 무계**) · 셧다운(보조) · **정지 감지 + 상한(권고)**.
`T_max` 값은 오너 선택(권고 60 s). 계약 시험 후보 ⑦→**⑪**(조용한 창·상한 강행·옵트인 격리·스톨 관측 추가).

**계기에서 배운 것**(대장 §36-4): 워커가 `O_CREAT` 없이 열어 **스레드만 죽었고** 리포트는 “0 호출”로 정상처럼 보였다 —
그래서 그 팔은 사실 **media 가 없는 팔**이었다. 이웃 dirty 를 남겨 기준선끼리 13 % 차이가 났고, 순차 실행이 그것을
증폭했다. 셋 다 이제 시험 16건이 문다(음성 대조군: `O_CREAT` 를 빼면 **정확히 그 하나가 빨개짐**).
17번째 시험은 **문서 자신**을 겨눈다 — 프로브를 한 번 더 돌려 픽스처가 바뀐 뒤에도 표가 옛 세대 수치를 들고 있는
것을 실제로 밟았고(①), 그래서 문서의 수치를 픽스처에서 다시 계산해 **문자 단위로 대조**한다.

**지문 불변**: `src/` 두 파일 sha256 이 사전 이미지(`a89dfd2d82cc…` · `7f3e4605da9d…`)와 **동일** ·
`scripts/`·`tests/` 쓰기 0건 · 문서 검사기 **ALL OK**(링크 219).

## 27. 4차 실행은 깨끗했는데 판정은 FAIL 이었다 — 판정기·도구·체인 셋을 고쳤다 (2026-09-17 · 오너 지시)

### 27-1. 한눈에

4차 8시간 실행은 **모든 축에서 깨끗**했다: `exit 0` · 벽시계 **28804s** · 시작==종료==현재 트리(`b6a74304…`) ·
`all_pass=true` · SC-1~6 전부 pass(SC-6 `orphans=0` · `errors=0`). 그런데 3차 배치 체인이 ② 단계에서 **FAIL** 로
멈췄고, FAIL 을 만든 검사는 **단 하나**였다 — `③ 기대 지문 == 시작 지문`. 기대값이 `322b4d3b…` 였는데 그 값은
**한 틱도 돌지 않은 예약**(`aborted: true` · `start_check_fingerprint: UNVERIFIED`)의 것이었다.
전체 원인·증거는 **대장 §37** 에 있다(여기에는 다음 사람이 바로 쓸 것만).

### 27-2. 고친 것(각각 커밋 · 계약 시험으로 고정)

| 커밋 | 무엇 | 왜 그 자리였나 |
|---|---|---|
| `7e632ec7` | `scripts/collect_soak_result.py`: 중단된 예약을 기대값에서 **제외** · 살아 있는 예약이 없으면 **러너가 기록한 시작 지문**으로 내려가되 출처를 문장으로 밝힘 | 판정기가 계속 “없는 근거”를 집지 않게 |
| `e840d07d` | `soak_control.sh`(→`scripts/`): 즉시 실행이 **자기 기대 지문을 스스로 기록**(계산 실패면 “주장하지 않는다”) | 판정기가 쓰는 “마지막 살아 있는 블록”이 **이 실행의 것**이어야 함 |
| `de50af93` | `promote3/post_harvest_sequence3.sh`: 판정을 **내용으로만** 받는다(종료 뒤 수집 · 실행 트리 판정 · 판정 대상 명시) | 종전 규칙은 이미 내려진 정당한 판정을 거부해 **스스로 재판정**했고, 그 재판정이 지문 조건을 깨뜨렸다 |

시험: 판정기 자체 시험 **11/11** · 판정기+통제 도구 계약 시험 **20 passed** · 통제 도구 자기시험 **82/82**
(⑬ 5건 추가) · 판정 수용 리허설 **6케이스 ALL PASS** · 승격 리허설 **ALL PASS**.

### 27-3. 4차 실행의 PASS 는 어떻게 기록됐나(정직하게)

판정기를 고치는 순간 `③ 지금 트리 == 시작 지문` 은 **설계상 거짓**이 된다(그것이 “측정 후 코드 무변경” 의 뜻이다).
그래서 트리를 건드리기 **전에** 판정을 받았고, 그때는 결함이 남아 있었으므로 판정기의 정식 통로
`--expected-fingerprint`(= **그 실행이 스스로 기록한 시작 지문**)를 썼다 — 판정기 자신이 “사람이 지정” 이라 출력한다.
산출물: `soak-recovery-20260917T032556Z.json`(+`latest`) · `collected_at 2026-09-17T11:32:13Z` · 여섯 검사 전부 OK.
원문 txt(`soak-harvest-20260917T112611Z.txt`)는 **그 이전(결함 있는) 판정의 글**이고, **판정의 출처는 JSON** 이다.

### 27-4. 지금 무인으로 도는 것(화면 두 개)

| 화면 | 무엇 | 어디를 보면 아는가 |
|---|---|---|
| `nx10promote3` | 판정 수용 → 승격 5건(sha256 동일) → 커밋 → 필수 23개(~19분) | `promote3/post-harvest-record3.md` · `gate-report-promote3.json` |
| `nx10batchchain` | `SC6 → PERF → FLUSH → FLUSH2` 각각 적용·커밋·게이트 → **새 8시간 soak 재장전** | `batchchain/batchchain-record.md` · `batchchain/batchchain.log` |

재장전은 `soak_control.sh run`(즉시 실행)이고, 이번에는 그 실행이 **자기 기대 지문을 예약 이력에 적는다** —
8시간 뒤 회수가 같은 거짓 FAIL 을 반복하지 않는다(자기시험 ⑬ 이 그 순서를 실제로 확인한다).

### 27-5. 다음 사람이 물릴 수 있는 곳

- **순서 규칙**: `scripts/`·`tests/` 를 건드리는 변경은 **도는 실행과 공존할 수 없다**(지문이 움직인다).
  회수를 받은 뒤에 고치거나, 고친 뒤에 새로 돌린다 — 이번에 그 순서를 코드로 강제했다.
- **mtime 을 쓰기 순서로 믿지 말 것**: 프리커밋 훅이 `git stash`/`restore` 로 파일을 다시 써서 시각을 바꾸고,
  판정기를 직접 돌리면 JSON 만 새로 쓰인다(내가 이 함정에 한 번 걸렸다 — 대장 §37-5).
- **승격이 옮긴 파일을 링크하던 문서**: 이번에 `handoff` 의 `soak_control.sh` 링크가 STALE 이 됐고 고쳤다.
  스테이징 사본이 사라지는 파일을 가리키는 링크가 또 있으면 문서 검사기가 잡는다.

## 28. 이어받기 — 죽은 승격을 커밋하고, 승격이 고아로 만든 호출자를 고쳤다 (2026-09-18 · 오너 지시)

### 28-1. 한눈에

오너 지시는 “8시간 soak 이 끝난 뒤 무인으로 `FLUSH`·`FLUSH2` 를 적용하고 게이트 재측정과 새 soak 재장전까지
묶어 걸어줘” 였다. 그런데 그 체인의 **앞 단계가 죽어 있었다**: 4차 실행 회수 뒤의 무인 체인이 커밋 직전
(`2026-09-17T12:19Z`)에 멈췄고, 재부팅으로 화면·프로세스가 0건이 됐다. 그래서 이번 턴은
**① 승격 커밋 → ② 호출자 경로 수정 → ③ 필수 23개 재측정 → ④ 배치 체인 걸기** 순으로 이어받았다.
전체 근거는 **대장 §38** 이다.

### 28-2. 지금 상태(다음 사람이 먼저 볼 것)

| 무엇 | 어디를 보면 아는가 |
|---|---|
| 승격 커밋 | `a1c6387f` — 감시·통제 도구 3종 + 계약 시험 2종이 `scripts/`·`tests/` 로 들어갔다 |
| 호출자 수정 | `8d762c3e` — 체인 4개·러너북·계약 시험 7건. **지문 불변**(`af462f78…`) |
| 필수 23개 | `promote3/gates3-runner.log` · `gate_verify-promote3.txt` · `gate-report-promote3.json` |
| 배치 체인 | `batchchain/batchchain.log` · `batchchain/batchchain-record.md` (`SC6→PERF→FLUSH→FLUSH2` + 재장전) |
| soak 상태 | `screen -ls` · `bash scripts/soak_control.sh status` (도구는 **승격 위치**에 있다) |

### 28-3. 이번에 찾은 결함 — 승격은 초록이었지만 **부르는 쪽이 죽어 있었다**

`soak_control.sh`·`soak_watch.py`·`soak_watch_loop.py` 는 `docs/` → `scripts/` 로 **옮겨졌는데**(`mv`),
그것을 부르는 체인들은 옛 경로를 그대로 들고 있었다. 가장 나쁜 것은 배치 체인이었다:
그 경로를 **재장전(7단계)에서만** 쓰므로 **4개 배치를 적용·커밋하고 게이트를 네 번 잰 뒤에** 터진다 —
밤을 태우고 트리는 반쯤 옮겨진 채 남는다. 고침은 두 가지다: ① 호출자가 **승격 위치를 먼저 보고
존재를 확인**하게 바꿨다 ② 그 문장을 계약 시험(`batchchain/test_chain_tool_paths_contract.py`, 7건)으로
고정했다(변수 형태·인쇄문 구분·호출 0건 방지까지 이빨로 확인).

### 28-4. 다음 사람이 물릴 수 있는 곳

- **도구의 위치**: 감시·통제 도구는 이제 `scripts/` 다. `docs/qa/2026-09-16-followup/nx10/soak_control.sh` 는
  **없다** — 그 경로를 쓰는 문서·스크립트를 새로 만들면 계약 시험이 빨개진다.
- **무인 체인은 두 겹이다**: 앞은 3차 배치 체인(`post_harvest_sequence3.sh`), 뒤는 배치 체인
  (`batchchain/run_batch_chain.sh`). 뒤 체인은 ②관문에서 **앞 체인의 게이트 리포트 파일**을 요구한다 —
  리포트가 없으면 옳게 멈춘다(이번에 그 문에서 멈춰 있었다).
- **재부팅은 화면을 지운다**: 무인 체인을 걸어 두고 창을 닫으면 다음 세션은 **처음부터 상태를 읽어야** 한다
  (`git status`·인덱스·`batchchain-record.md`·`screen -ls`). 이번엔 인덱스에 스테이징이 남아 있어
  “승격은 됐고 커밋만 안 됐다”를 그대로 복원할 수 있었다.
- **mtime 을 근거로 삼지 말 것**(§37-5) · **기록이 비어 있어야 한다는 검사를 만들지 말 것**(§38-4).

### 28-5. 승격이 코드를 검사 대상 안으로 옮긴다 — 승격 게이트도 같은 검사를 해야 한다

필수 게이트 `python-basedpyright` 는 `src/ scripts/` 를 본다. 그래서 **승격은 곧 “이 파일들을 이제부터
검사한다”** 는 선언인데, 승격 게이트 C 는 `ruff` 만 돌리고 있었다. 그래서 3차 배치는 초록으로 통과했고
**승격 뒤 필수 23개에서 28 errors** 로 빨개졌다(감시 도구가 `docs/` 에 있던 동안 아무도 안 본 타입).
고침은 두 가지다: ① 옮겨진 파일의 타입을 정리 ② **승격 게이트 C 가 필수 게이트와 같은 명령을 돌린다**.

같은 부류가 2차 배치에서도 났었다(`restore_rehearsal.py`·`rollback_rehearsal.py` 타입 12건) — 그때는
고치기만 하고 검사를 안 옮겼고, 그래서 3차에서 다시 났다. **재발 방지는 고침이 아니라 검사를 옮기는 일이다.**

### 28-6. 지금 무인으로 도는 것

| 화면 | 무엇 | 어디를 보면 아는가 |
|---|---|---|
| `nx10batchchain` | `SC6`(적용·커밋 `87a61db4` 완료) → `PERF` → `FLUSH` → `FLUSH2` 각각 적용·커밋·게이트 23개 → **새 8시간 soak 재장전** | `batchchain/batchchain.log` · `batchchain/batchchain-record.md` · `gate-report-batch-*.json` |
| `nx10watch` | (재장전 뒤 자동 부착) 라이브 추세 화면 | `docs/qa/2026-09-16-followup/nx10/soak-watch-live.html` |

재장전은 이번에도 `scripts/soak_control.sh run`(즉시 실행)으로 시작하고, 그 실행이 **자기 기대 지문을 스스로
적는다** — 8시간 뒤 회수가 §37 의 거짓 FAIL 을 반복하지 않는다. 필수 23개의 새 지문 결과는 **22 passed ·
1 failed · 0 not_run**(실패는 기존 5건뿐 · `clean-machine-runtime`·`basedpyright` passed).
