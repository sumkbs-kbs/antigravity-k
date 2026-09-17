# NX-10 마감 절차 (soak 회수 → 커밋 → clean-machine → 판정)

작성: 2026-09-16. 커밋 전에는 동결 지문 `157311cf…` 기준이었고, 지금은 **커밋된 후보
`92fcaeb5…`** 기준이다. 이 문서는 **다음 사람(또는 다음 창)이 그대로 따라 실행할 수 있는 순서**만
담는다. 값의 소유자는 [GATE_LEDGER.md](GATE_LEDGER.md) §12 와 [BATCH_FREEZE.md](BATCH_FREEZE.md) 다.
예약을 걸고·확인하고·취소하는 일의 소유자는 [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) 다.

## 0. 현재 상태 (2026-09-17T00:2xZ, 커밋 뒤 기준)

| 항목 | 값 |
|---|---|
| 후보 지문 | `5c90b63761159253b10662711b29d1f8cd7a4357174ec3ce952f150d5f6ddff9` (`c522b256` — SC-3 경합·하네스 무한 대기 수정 커밋; 그 전 후보는 `aa1ead1f`/`98855031…` · `7691ccc5`/`322b4d3b…`) |
| 필수 게이트 | `sc3fix001`(23개 · `clean-machine-runtime` 포함) **22 passed · 1 failed · 0 not_run**; 시작 = 종료 = `5c90b637…` — 상세는 [GATE_LEDGER.md](GATE_LEDGER.md) §20-1 |
| 마감 도구(`ga_gate_verify`) | **FAIL** — 문제는 정확히 1개: `required_red: python-tests`(실패 5건 = NX-07 문서 정합성 2 · CR-14 울타리 3 · `promote004` 와 시험 단위 동일) |
| soak | **실행 중** — `2026-09-17T01:19:44Z` 시작 → 종료 예정 `09:19:43Z` = **18:19 KST**(§0b). preflight **7/7 OK** · SC-1~5 완주·오류 0 |
| 코드 | 커밋 완료(`c522b256`) — 이 창은 이제 **`docs/` 만** 수정한다(문서는 지문 제외 경로다) |

### 0a. 8시간 재실행이 두 번 걸렸다(둘 다 도구가 잡았다)

1. `2026-09-16T23:26:23Z` 실행 → **48분에 중단**(`exit: 143`). 이유: 수정으로 빨라진 append 가
   journal 을 160 KB/s 로 키워 **기본 hard cap 512 MiB 를 50분에 넘긴다**(중단 시점 439 MiB) —
   넘기면 모든 append 가 507 로 거절되고 하네스가 그것을 `errors` 로 세서 **설정 때문의 거짓 FAIL**
   이 된다. 상세: [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md) §3e.
2. `2026-09-17T00:15:16Z` 실행 → **7분에 중단**(`00:22:48Z`, `exit: 143`). 이유: **SC-3 의 worker 하나가
   죽자 하네스가 영원히 대기**했다(`q.get()` 타임아웃 없음 → 8시간을 주면 결과 0). worker 를 죽인 것은
   제품 경합(`ProjectRegistry` 최초 생성이 lock 밖 + 고정 백업 tmp 이름)이다 — 둘 다 고쳐
   커밋 `c522b256` 했고, 23개 재측정 → 재시작 순서로 다시 세운다. 상세: §3f.
3. 러너가 `AGK_CONVERSATION_JOURNAL_HARD_CAP_MB=8192` 를 export 하고 그 사실을 기록에 남긴다
   (`retention_caps: soft=64MiB hard=8192MiB`) — 이것은 §0a-1 의 조치이고 새 실행에도 그대로 적용된다.

## 0b. soak 실행/회수 순서 (현재: **실행 중** — 2026-09-17T01:19:44Z 시작)

```bash
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh preflight   # exit 0 이어야 시작한다
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh run         # 같은 preflight 를 통과해야 뜨다
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh harvest --detach   # 끝날 때까지 기다렸다가 회수 판정까지
```

**지금 상태**: 3차 실행이 **돌고 있고**(`screen nx10soak`) 회수 감시도 **이미 떠 있다**(`screen nx10harvest`,
`2026-09-17T01:23Z` 부터 대기). 그러므로 아침에 할 일은 **감시 로그를 읽는 것**이지 다시 띄우는 것이 아니다:

```bash
tail -20 docs/qa/2026-09-16-followup/nx10/soak-harvest.log   # 대기 중이면 “마지막 쓰기 N초 전”
ls -t docs/qa/2026-09-16-followup/nx10/soak-harvest-*.txt   # 끝나면 판정 원문이 생긴다
```

**돌고 있는 동안에도 물어볼 수 있다(조기 경보, 2026-09-17 추가)**:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/qa/2026-09-16-followup/nx10/soak_watch.py --once   # exit 0 정상 · 2 경고 · 6 멈춤
```

한 표본에 살아 있음 · 마지막 쓰기 · **journal 증가율 vs 보존 cap 투영** · **RSS 외삽 vs SC-6 64 MB** ·
추정 처리량 vs 하한(133 ops/s)이 나온다. **읽기 전용이고 저널을 읽지 않아** 이 8시간의 측정을 건드리지 않는다
(`--selftest` 3/3: 정상 · 멈춤 · cap 초과 투영). 왜 필요한가는 오늘 기록이 답한다 — 1차는 47분에야 cap 초과를,
2차는 멈춘 뒤 30분을 더 기다려야 알았다(GATE_LEDGER §21). `harvest` 는 **끝나야** 판정하는 도구이고,
이쪽은 **돌고 있는 동안** 말하는 도구라고 구분해 쓴다.

감시가 끝나면 판정 `exit` 를 그대로 전하고, 그 출력을 `soak-harvest-<UTC>.txt` 로도 남긴다.
`exit 6` 이면 **멈춘 실행**을 만난 것이니 §1-0 의 정리 절차를 보고 다시 시작한다.

### 0b-1. 시작했던 실행(이제 종료됨)의 기록

- 상태 보기: `bash docs/qa/2026-09-16-followup/nx10/soak_control.sh status`(한 화면에 모드·지문·관은 초·종료 예정)
  · `tail -3 …/nx10/soak-run.log` · `screen -ls` · 실행 잠금 `pid` 는 `.soak-run.lock/owner`.
- **이 시점부터 코드를 건드리면 8시간이 무효다**(종료 지문이 시작과 갈린다 — `src/`·`tests/`·`scripts/`·`dashboard/`).
  이 창은 `docs/` 만 수정한다(측정 도구(`soak_control.sh`·`run_nx10_soak.sh`)도 `docs/` 안이라 안전하다).
- 회수는 **`harvest` 한 줄**이다(§1). 끝나기 전에 코드를 만지면 “이 8시간은 후보의 것이다”라는 근거가 사라진다.
- 시작 기록: `soak-exit.txt`(러너 블록 `start_time 00:15:16Z` · `start_head aa1ead1f` ·
  `start_fingerprint 98855031…` · `retention_caps: soft=64MiB hard=8192MiB`) ·
  작업디렉터리 `/tmp/nx10-soak-work-20260917T001516Z` ·
  `start_dirty: true`(이 창의 `docs/` 편집과 gitlink `vault_data` 때문 — 귀속은 지문으로 본다).

기록이 길어진 이유도 적어 둔다: **일부러 일찍 시작하지 않는다.** 한 번은 `tail()` 결함 때문에,
한 번은 그 수정이 만든 쓰기량 때문에 밤을 버리는 것을 막았고(§0a), 이제 발화 전 `preflight` 가
둘 다(처리량 하한 · 쓰기량 투영)를 문장으로 답한다.

## 1-0. 예약 상태·취소 (도구가 있다)

```bash
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh status     # exit 0 = 단일 예약 · 고아 0 · 지문 일치
                                                                 #   (즉시 실행 중이면 모드: RUNNING — 시작 지문 == 현재 트리)
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh preflight  # exit 0 = 밤을 태울 준비가 됐다(예약 11개 · 즉시 시작 7개 점검)
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh cancel     # 취소 — 죽었는지 검증하고 기록한다
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh harvest    # 끝날 때까지 기다렸다가 회수 판정까지(06:00 에 깨어 있을 필요 없음)
```

`status` 는 모드를 먼저 가른다 — 종전에는 도는 soak 을 보면서도 `ATTENTION` 을 냈다(예약 잠금이 없는
즉시 실행을 "예약 아님"으로 본 탓; 2026-09-17 수정, [SOAK_SCHEDULING.md](./SOAK_SCHEDULING.md) §3d).
실행 중이면 그 줄이 곧 **이 8시간이 후보에 붙는가**의 답이다(시작 지문 vs 현재 트리).

`preflight` 가 답하는 것 중 가장 중요한 것은 **후보 귀속**이다: `현재 트리 지문 == HEAD 트리 지문`
(`tree_fingerprint_of_commit`)이면 8시간이 끝났을 때 그 값을 **커밋된 후보**의 것으로 쓸 수 있다.
아니면(예: 커밋 뒤에 코드를 더 만졌다) 결과를 귀속할 수 없으므로 지금 고친다 — 06:00 에 알면 밤을 버린다.

**`screen -X quit` 을 취소 수단으로 쓰지 않는다** — 2026-09-16 에 그것으로 "취소했다"고 기록한 예약
3건이 실제로는 살아 있었다(취소를 검증하지 않았다). `cancel` 은 트리 단위로 종료하고
`검증: 살아 있는 예약 0건` 을 출력한다. 상세·자기시험 증거: [SOAK_SCHEDULING.md](SOAK_SCHEDULING.md).

## 1. soak 회수 (아침, 순서 중요)

**한 줄로 끝낸다(권장)** — 판정 로직이 코드로 고정돼 있어 손으로 tail 하다 지표만 보고 승격하는 실수를 막는다:

```bash
cd <repo>
# 기다렸다가 판정까지 — 도구가 실행 종료·블록 완성을 확인한 뒤에만 판정한다.
bash docs/qa/2026-09-16-followup/nx10/soak_control.sh harvest
#   `--detach` 면 화면 세션(`nx10harvest`)에 띄워 창이 재시작돼도 살아남는다(대기 중 잠자기 차단 포함).
#   `--no-wait` 는 “지금 끝난 실행만 판정” 이다 — 아직 돌면 `exit 4` 로 거부한다.
# 대안(같은 판정을 직접): 판정기는 scripts/ 에 있다(증거는 계속 nx10/ 에 쓴다).
python3 scripts/collect_soak_result.py            # 지표 + 실행 + 귀속 3단계 판정
python3 scripts/collect_soak_result.py --wait     # 아직 돌고 있으면 기다린다(기본 30분 상한)
```

판정은 셋을 **모두** 통과해야 PASS 다: ① 지표(`all_pass`·`missing_required`) ② 실행(러너 `exit==0` **그리고**
벽시계 ≥ 요청 시간 — 즉시 실패한 실행도 리포트는 쓴다) ③ 귀속(예약 기대 지문 == 시작 == 종료 == **지금 트리**).
지표만 통과하면 판정은 `METRICS_PASS / 실행·귀속 INCONCLUSIVE — DONE 아님` 이다(EX-05 가 겪은 상태).
산출물: `soak-recovery-<실행시작>.json`(실행별 보존) · `soak-recovery-latest.json` · `soak-recovery.log`.
판정 로직 자체는 `--selftest` 로 검증된다(**9/9** — 중단·지문불일치·지표실패·측정 후 코드변경·리포트 없음·
예약 이력이 쌓였을 때 **마지막 예약**을 쓰는가).

원문을 직접 보려면(대안, 같은 사실을 눈으로 확인):

```bash
python3 -m json.tool docs/qa/2026-09-16-followup/nx10/soak-28800.json | tail -25   # ① 지표
tail -12 docs/qa/2026-09-16-followup/nx10/soak-exit.txt                             # ②③ 귀속·exit
```

- **지표만 보고 “soak 통과”라고 쓰지 않는다.** 카드가 요구하는 것은 지표 + **시작/종료 지문 동일**이다.
  지문이 다르면 그 실행은 이 후보의 것이 아니다(과거 1·2차 실행이 정확히 이 이유로 중단됐다).
- 8h 규모에서 처음 타는 `stream_line_count` 경로(NX-04 가 남긴 미실측)도 이 리포트에서 확인한다.
- 결과는 `GATE_LEDGER.md` §12 에 **회수 행으로 추가**하고, 통과가 아니면 그대로 적는다.

## 2. ⚠ 커밋해도 빨간 5건은 초록이 되지 않는다 (먼저 알아야 할 사실)

`python-tests` 의 실패 **5건**(2026-09-17 실물 리포트로 정정 — 종전 “4건” 표기는 오기다)은
**우리 후보의 결함이 아니라 거버넌스 상태**다:

| 시험 | 왜 빨간가 | 우리 커밋이 고치나 |
|---|---|---|
| `test_cr14_fence_movement_detection.py::test_no_code_scope_commit_after_the_declared_candidate` | 선언된 후보 `b6003205`(지문 `02349a8d…`) 이후 코드 스코프 **38개 경로**가 움직였다(HEAD `20d529fc`, 지문 `2068e72b…`) | **아니다** — 우리가 커밋하면 HEAD 가 더 멀어진다 |
| `test_cr14_fence_movement_detection.py::test_declared_fingerprint_is_the_fingerprint_of_head_within_the_fence` | 선언 지문과 HEAD 지문이 다르다 | **아니다** — 같은 이유 |
| `test_cr14_fence_movement_detection.py::test_worktree_matches_the_declared_fingerprint…` (실물 리포트의 **세 번째** 건) | 작업 트리도 선언 지문과 다르다 | **아니다** — 같은 이유 |
| `test_nx07_doc_consistency.py::test_soak_phases_stay_separated` · `::test_teeth_soak_done_promotion_is_detected` | 타 레인이 `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 의 EX-05 상태 셀을 승격(PASS)하면서 “종료·귀속 미확정” 문구를 지웠다 | **아니다** — 타 레인 문서 소유 |

즉 **`python-tests` 는 우리 창에서 초록이 될 수 없다.** 카드 §수용(“실패 0”)은
**CR-14 후보 재선언 + EX-05 승격 판정**(둘 다 오너/타 레인)이 끝나야 성립한다. 이 사실을 먼저
받아들이고 나머지를 진행해야, 커밋 뒤 “왜 아직 FAIL 인가”를 다시 조사하는 시간을 쓰지 않는다.

## 3. 커밋 (사용자 승인 사항)

### 3.1 지문과 커밋의 관계 (실측 근거)

`worktree_fingerprint()` 는 **추적+미커밋(무시되지 않은) 코드 파일의 내용 해시**다(`scripts/ga_gate.py`
`tree_digests` — `git ls-files --cached --others --exclude-standard`). 한동안 이 문서는 “커밋은 파일
내용을 바꾸지 않으므로 지문도 변하지 않는다”고 적었는데, **2026-09-16 실측이 그것을 반박했다**:
커밋하면서 **맵에서 사라지는 항목**이 생긴다: 추적 중이지만 작업 트리에서 삭제된 파일은 맵에
`MISSING_CONTENT` 로 남아 있었는데, 그 삭제를 커밋하면 인덱스에서도 빠져 항목 자체가 없어진다 —
이번 배치의 번들 교체(추적 중이던 옛 번들 30개 삭제)가 정확히 그 경우였고, 지문이
`0f345d0c…` → `92fcaeb5…` 로 옮겼다.
그래서 규칙은 이렇다: **커밋 뒤에는 지문을 다시 재고, 예약은 그 뒤에 건다**(실제로 재장전했다).
커밋 전후로 확인해 기록한다:

```bash
.venv/bin/python -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))"
```

### 3.1b 실제로 커밋됐다 — 3분할, 2026-09-16 (오너 지시 "수정 사항들 모두 커밋")

| # | SHA | 범위 |
| --- | --- | --- |
| 1 | `d929da01` | 후보 코드 + 계약 + **승격된 도구 3종**(`scripts/`)·계약 시험 3종(`tests/`) + `.gitignore` 규칙 — 67 파일 |
| 2 | `6417690e` | 대시보드 소스·e2e + `dashboard_dist/**`(재번들) + `release/**`(SBOM·notices) — 50 파일 |
| 3 | `89dd383b` | 증거·문서(`docs/**`, `README.md`) — 216 파일 |

- **`git add -A` 를 쓰지 않았다**(경로 명시). `data/auth_hash.bak.pre-0000` 은 승격 배치가 넣은
  `.gitignore` 규칙으로 이제 **무시되어 스테이징되지 않았고**(`git check-ignore` 로 확인),
  **`vault_data` 는 의도적으로 제외**해 미커밋으로 남겼다(소유 불명 gitlink — 이 카드의 것이 아니다).
- **pre-commit 훅을 우회하지 않았다**(`--no-verify` 0회). 대신 커밋 전에 훅을 먼저 돌렸다 — 실제로
  문서 묶음에서 `ruff --fix`·trailing-whitespace·EOF-fixer 가 파일을 고쳤고, 그 뒤 재스테이징해 훅을
  전건 PASS 로 통과시켰다. **1MB 초과 4개**(`gate-report-*.json`)는 `check-added-large-files --maxkb=1024`
  을 넘어 커밋하지 않았다: 정책을 우회하는 대신 원본은 디스크에 두고
  [`large-evidence-manifest.md`](./large-evidence-manifest.md) 에 sha256 을 남겼다.
- 커밋이 **지문을 옮겼다**(§3.1 의 정정) → 그 뒤 필수 게이트를 다시 쟀다(attempt `promote003`,
  `clean-machine-runtime` 포함). 예약 soak 은 그 뒤에 재장전했다.

### 3.2 제안하는 분할 (3개)

| # | 범위 | 이유 |
|---|---|---|
| 1 | 후보 코드 + 계약 시험: `src/antigravity_k/**`(신규 leaf 2 + 동결 배치 3), `tests/test_nx0*.py`, `tests/fixtures/...` | 리뷰어가 **동작 변경**을 심사하는 커밋 |
| 2 | 대시보드: `dashboard/src/**`, `dashboard/e2e/**`, `src/antigravity_k/dashboard_dist/**` | 번들은 생성물 — 소스와 **같은 커밋**에 두면 “서빙물 == 소스”가 커밋 단위로 검증된다(§F04) |
| 3 | 증거·문서: `docs/**` | 지문 **밖**(`docs/` 제외)이라 판정 수치를 옮기지 않는다 |

- **스테이징에서 제외할 것**(소유 불명·타 레인 산출물): `data/auth_hash.bak.pre-0000`, `vault_data`.
  `git add -A` 를 쓰지 않는다 — 경로를 명시해 스테이징한다.
  **이유는 실측됐다(WARN)**: `data/auth_hash.bak.pre-0000`(0644, 인증 해시 사본)과 `vault_data`(gitlink/submodule)는
  *무시되지 않은* 상태다. `.gitignore` 는 `data/auth_hash` 만 막으므로 `git add -A` 는 **인증 해시 사본을 커밋**한다.
  `.gitignore` 에 `data/auth_hash.bak*` 를 추가하는 수정은 **지문 대상**이라 동결 중에는 하지 않았고,
  동결 해제 뒤 후속 작업으로 남긴다(§5-1).
- 커밋 후 **`clean-machine-runtime` 만** 다시 돌린다(그 게이트는 `--ref HEAD` 를 export 한다):

```bash
bash docs/qa/2026-09-16-followup/nx10/run_clean_machine_gate.sh   # HEAD 기준 클린룸 재현
```

## 3.3 마감 전 점검 결과 (2026-09-16, `verify_docs_commands.py`)

이 문서와 `docs/09` 가 시키는 것이 **실제로 존재하는지**를 실행 전에 검사했다
(증거: `docs-command-verification.txt`, 결과 **ALL OK** — 커밋 대상 121개 파일 비밀 스캔 포함):

| 검사 | 결과 |
|---|---|
| 문서에 적힌 CLI 플래그 6개 스크립트 13개 | 전부 `--help` 로 확인 |
| 문서의 `AGK_*` 환경변수 13개 | 전부 코드에 직접 존재 또는 파생(`AGK_SERVER_PORT` = `env_prefix="AGK_SERVER_"` + `port`) |
| 문서가 참조하는 경로 21개 | 전부 존재 |
| 커밋 대상 비밀 스캔(121파일) | 패턴 일치 없음 |
| `.gitignore` (`vault_data`, `data/auth_hash`) | 규칙 있음 |
| 문서 로컬 상대 링크 98개 | 전부 실재(6번 섹션으로 검사 추가) |

링크 검사는 **추가하다가 깨뜨린 것을 스스로 잡았다**: `docs/19`§·`docs/18`§·nx10 handoff·EX05 문서에
`../` 깊이가 틀린 링크 7건이 있었다(그 중 4건은 이 세션에서 내가 추가한 것 — `docs/` 안에서 `../ga/` 는
존재하지 않는 경로다). 모두 실제 파일 기준으로 고쳤고, `REPORT.md` 의 `goals.md` 참조는 **저장소에 없어**
링크 대신 “저장소에 없다”는 사실로 바꿨다(없는 파일을 가리키는 링크를 남기지 않는다).

**남은 WARN 1건**: `data/auth_hash.bak.pre-0000` 이 무시되지 않은 채 untracked(→ 위 §3.2 의 명시 스테이징 규칙).

검사기 자체의 교훈도 적어 둔다: 첫 실행에서 두 건을 STALE 로 보고했지만 **둘 다 검사기가 틀렸다**
(pydantic 이 `env_prefix` + 필드명으로 만드는 변수를 모르는 문자열 검색이었고, 테스트 자리표시자
`api_key="test-key"` 를 비밀로 셌다). 검사기를 고쳤지 문서를 고치지 않았다 — 이런 검사는 **첫 출력을
그대로 믿으면 안 된다**.

## 4. 그 다음 (사람의 일)

선택지·영향·권고·의존 순서를 한 장으로 모은 오너용 문서: **[GA owner decision packet](../../../ga/GA_OWNER_DECISION_PACKET.md)** (D1~D8).
아래는 그 중 이 절차와 직접 이어지는 항목이다.

1. **CR-14 후보 재선언** — 새 후보 SHA·지문을 울타리에 선언해야 `test_cr14_fence_movement_detection`
   2건이 초록이 된다.
2. **EX-05 승격 판정** — [EX05_PROMOTION_CONFLICT.md](EX05_PROMOTION_CONFLICT.md) 의 선택지 A/B/C
   중 하나를 오너가 고른다(권고 B: 상태 셀을 “PASS(JSON 지표) / 종료·귀속 INCONCLUSIVE — DONE 아님”으로 한정).
3. **독립 검토자 지정·판정 + owner 허용 기록** — 없으면 GO 선언 불가.
4. **NX-02 격리 절차 소유자 지정 · 제품 flag(A안) 채택 여부 · 격리본 보존 기간**
   ([nx02/damaged-conversation-disposal.md](../nx02/damaged-conversation-disposal.md) §6). 리허설 자체는
   **이미 실시됐다** — 실데이터 사본에서 migration + 격리 절차를 연속 실행해 형제 대화 정상·원본 해시 불변까지
   확인했다(`rehearse_real_store_quarantine.py`). **실제 저장소 자체**에 migration 을 적용하는 것만 남았고,
   이는 서비스 정지·운영 결정 사항이다.
5. **NX-11 재개 여부**(사용자 pause 유지 중) · NX-06 kube context 확보 여부.

## 5. 동결 해제 뒤로 미룬 코드 작업 (지금 하면 soak 의 지문이 깨진다)

1. ~~`.gitignore` 에 `data/auth_hash.bak*` 추가~~ → **2026-09-16 완료**(승격 배치 3b 단계): 규칙이 들어갔고
   검사기가 WARN 대신 `[OK] data/auth_hash.bak.pre-0000 이 무시된다` 를 출력한다(추적 중 파일 기준선 567건 불변).
   규칙의 효력은 미니 저장소 음성/양성 대조군으로 확인했고(`promote/dry-run-output.txt`),
   부작용 기준선도 기록해 두었다: 이 저장소는 **이미 추적 중인데 무시되는 파일이 567건** 있으므로 게이트는
   "0건"이 아니라 "새 규칙으로 **늘어나지 않았다**"이다(`git ls-files -i -c` 전후 비교).
2. NX-01 cue lexicon 개선 5건 — [nx01/cue-lexicon-measurement.md](../nx01/cue-lexicon-measurement.md) §6
   (단어 경계 매칭 · supersede 발동 조건 강화 · approval cue 확장 · 바꾸기 정규식 · 합성 회귀의 `tests/` 승격).
3. ~~**승격 본실행**~~ → **2026-09-16 완료**(오너 판정 **B**: 승격 먼저, 그 다음 22:00 재장전).
   `promote/apply_promotion.sh` 가 도구 3종 + 계약 시험 3종을 `scripts/`·`tests/` 로 옮겼고 게이트 ⑦은 **7/7**,
   지문 **`157311cf…` → `ab980ba5…`**. 기록: `promote/promotion-applied.txt` · 계획 [PROMOTION_PLAN.md](./PROMOTION_PLAN.md).
   첫 두 시도는 **이동 전에 멈췄고 롤백까지 깨끗했다**(① 스테이징 루트 오산 ② 검사기가 `parents[4]` 로
   저장소를 잡아 `scripts/` 로 옮기자 죽었다 → 셋 다 루트를 `pyproject.toml` 로 찾도록 고쳤고, 그 뒤 세 번의
   리허설이 7/7 이었다). 그 과정에서 리허설·본실행이 **표와 게이트를 공유**하게 됐다(`promote/paths.sh` ·
   `promote/gates.sh`) — 그 전에는 리허설이 본실행과 다른 게이트를 돌려 사각지대가 있었다.
   실패한 두 시도의 로그도 `promotion-applied.txt` 에 남는다.
4. ~~승격 뒤 문서 참조 갱신~~ → **2026-09-16 완료**: `CLOSURE_RUNBOOK` · `docs/09` · `nx01/cue-lexicon-measurement.md`
   · `docs/19` · `docs/20` · `handoff` · `BATCH_FREEZE` 를 새 `scripts/` 경로로 갱신했고,
   검사기 자신의 `DOCS`/`REFERENCED_PATHS` 에도 승격본을 등록해 **다음 사람이 스테이징 경로를 다시 안내하면
   그 검사기가 잡는다**(§3-4 가 말한 "문자열 치환 금지"를 도구로 대신한다).

5. **`soak_control.sh` 승격 + 검사기 등록**(2026-09-16 추가 — soak 회수 뒤). 예약 통제 도구는 지금
   `docs/qa/2026-09-16-followup/nx10/` 에 있어서 **어떤 게이트도 지키지 않는다**(정적 검사는 `scripts/`,
   스위트는 `tests/`). 승격할 것: ① `scripts/soak_control.sh` 로 이동 ② `--selftest` 22개를 계약 시험으로
   고정(`tests/test_soak_schedule_control.py` — 리허설·본실행이 표를 공유하지 않도록 `promote/paths.sh`·
   `gates.sh` 에 등록) ③ 검사기 `DOCS` 에 [SOAK_SCHEDULING.md](./SOAK_SCHEDULING.md) 추가 · `REFERENCED_PATHS`
   에 `soak_control.sh` 추가 · `DOCUMENTED_CLI` 에 `--at`·`--fp` 추가. **지금 하면 안 되는 이유**:
   `scripts/` 는 지문 대상이라 편집하면 22:00 예약이 드리프트로 스스로 중단된다(이 창은 그래서
   검사기 등록을 미뤘다 — `docs/` 만 수정했다).

## 5a. 회수 판정이 **어느 예약**을 기준으로 하는가 (2026-09-16 수정)

`soak-schedule.txt` 는 예약할 때마다 블록을 **덧붙인다**(재장전·취소 기록도 쌓인다). 회수 판정기
(`scripts/collect_soak_result.py`)는 이제 **마지막** `expected_fingerprint` 를 쓰고, 판정 출력에
“예약 이력 N건 중 마지막”을 문장으로 남긴다. 종전에는 첫 매치를 써서 재장전 뒤에 **철 지난 예약의
지문**으로 판정했고, 그대로 두면 정상으로 끝난 8시간 실행이 ③에서 거짓 FAIL 이 된다(실측·수정·재측정:
[GATE_LEDGER.md](GATE_LEDGER.md) §15). 사람이 특정 지문으로 판정하려면 `--expected-fingerprint` 를 쓴다
(그 경우 판정 출력이 “사람이 지정”으로 적는다).

## 5b. ⚠ 예약과 측정의 순서 (2026-09-16 에 실제로 물린 두 규칙)

두 번의 지문 이동을 겪고 얻은 순서 규칙이다. 둘 다 "그때는 맞았는데 나중에 틀린" 종류라
문장으로 남긴다.

1. **측정이 끝난 뒤에 예약을 건다.** 승격 직후 예약을 먼저 걸고(09:47Z) 게이트를 돌렸는데,
   그 측정이 끝난 지문(`0f345d0c…`)이 예약의 기대값(`ab980ba5…`)과 달라져 22:00 에 그대로 두면
   실행기가 `fingerprint drift` 로 멈출 뻔했다(그게 설계대로지만, 8시간을 잃는 것은 의도가 아니다).
   순서: **마지막 측정 → 지문 확인 → 예약 재장전 → 그 뒤에는 `docs/` 만 수정**.
2. **측정 중에는 코드를 만지지 않는다.** attempt `promote001` 은 돌고 있는 동안(09:52Z) 이 창이
   `scripts/verify_docs_commands.py` 를 고쳐 **시작 지문 ≠ 종료 지문**이 됐다(게이트가 트리를 흔든 것이
   아니라 — 동결 러너와 이번 러너 모두 `dashboard-build`·`sbom-generate` 의 재작성이 지문을 흔들지
   않았다(실측)). 값은 유효하지만 "그 시작 지문의 값"이고, 무편집 구간에서 `promote002` 를 다시 돌렸다.
   지문 불일치를 발견했을 때 **원인을 게이트로 단정하지 않고 지문 범위 파일의 mtime 을 먼저 보는 이유**가
   이것이다: `git ls-files --cached --others --exclude-standard` 안에서 최근에 쓰인 파일을 세우면
   범인이 바로 드러난다.

## 5c. 22:00 실행 전 마지막 확인(soak 자체가 지문을 흔들지 않는가)

회수 판정의 ③(시작 지문 = 종료 지문)은 **soak 이 스스로 트리를 안 흔든다**는 전제 위에 있다.
그 전제는 60초 리허설로 확인되어 있다(`soak-exit.txt`): 시작 = 종료 = `da54e07b…`, `all_pass: true`,
리허설 작업디렉터리는 `docs/` 안(지문 제외), 8시간 러너는 `/tmp`(역시 제외). 그래서 22:00 판정에서
지문 불일치가 나오면 그것은 **soak 이 아니라 그 사이에 누군가 코드를 만졌다**는 뜻이다.

실행 직전 상태(2026-09-16T12:04Z 기준, `soak_control.sh status` 출력): 예약 기대 지문 = 현재 트리
지문 = `322b4d3b…`, 단일 예약 · 고아 0 · 실행 잠금 none, 대기 3,339초, 종료 예정 `~06:00 KST`.
이 시점 이후 이 창은 **`docs/` 만** 수정한다(코드 수정은 예약을 무효로 만든다 — 12:0xZ 에 실제로 한 번
그렇게 됐고, 그 때는 커밋 → 재측정 → 재장전으로 다시 세웠다: [GATE_LEDGER.md](GATE_LEDGER.md) §15).

또 하나의 전제(2026-09-16 추가): 시작 지문 계산은 **`.venv/bin/python`** 으로만 한다. 시스템
`/usr/bin/python3`(3.9.6)는 `ga_gate.py` 의 3.12 문법을 파싱하지 못해 지문이 `UNVERIFIED` 가 되고,
예약 실행기는 이제 그것을 **드리프트보다 먼저** 막는다(`exit 3`, 기록 사유 `fingerprint unverifiable`).

## 6. 이 절차를 쓰는 사람에게

- “초록”을 늘리는 방향의 수정만 했다: 분류 오류(`clean-machine-runtime`)는 **실행해서** 바로잡았고,
  SCOPE 는 동결 문서라 고치지 않고 애덤덤에 적었다. 기준을 낮춰 통과를 만든 적은 없다.
- 실패한 attempt(001~003·006·012)와 중단한 soak(1·2차)를 **지우지 않고** 남긴 이유: “돌리다 만 것”과
  “의도적으로 끊은 것”이 섞이면 판정 근거가 흔들린다.
