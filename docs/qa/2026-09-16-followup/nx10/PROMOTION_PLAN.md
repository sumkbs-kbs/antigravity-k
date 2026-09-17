# NX-10 보조도구 승격 계획 — `docs/` 스테이징 → `scripts/` · `tests/`

작성 2026-09-16 (NX-10 창) · 상태: **승격 완료 — 본실행 성공(2026-09-16T09:46:05Z), 지문 `157311cf…` → `ab980ba5…`**

> **결과(오너 판정 B — 승격 먼저, 그 다음 22:00 재장전)**: 이동 6건 + `.gitignore` 규칙 적용, 게이트 **7/7**,
> 리허설 로그 `promote/dry-run-output.txt`, 실행 기록 `promote/promotion-applied.txt`,
> 새 지문에서 게이트 재측정은 `run_promote_gates.sh`(필수 22개), 예약 soak 은 새 지문으로 **재장전 완료**.
> 첫 두 시도는 이동 0건으로 롤백됐다(§8 참조) — 그 두 번이 표·게이트를 공유하게 만든 계기다.

이 창에서 만든 도구 3종과 그 계약 시험 3종은 `docs/` 안에 있다. `docs/` 는 **아무 게이트도 지키지
않는다** — 릴리스 게이트의 정적 검사는 `src/ tests/ scripts/` 만 훑고, 시험 스위트는 `tests/` 만
수집한다. 그래서 지금 상태에서는 이 도구들이 **조용히 낡아도 아무도 모른다**. 승격은 그 구멍을 닫는다.

## 1. 이동표 (해시 = 이동 전 스테이징본 sha256)

| 스테이징(이제 **없다** — 이동됨) | 승격 위치 | 역할 | sha256(앞 12) |
| --- | --- | --- | --- |
| `nx10/verify_docs_commands.py` | `scripts/verify_docs_commands.py` | 문서가 시키는 CLI·env·경로·링크·비밀 검사기 | `c2337637f906` |
| `nx10/collect_soak_result.py` | `scripts/collect_soak_result.py` | soak 회수 판정기(지표+실행+귀속 3단) | `beeefba23ef6` |
| `nx01/cue_lexicon_probe.py` | `scripts/cue_lexicon_probe.py` | cue lexicon 케이스 표 + 측정기 | `4e08dcbca8be` |
| `nx10/promote/test_docs_toolchain_contract.py` | `tests/test_docs_toolchain_contract.py` | 위 검사기의 계약(정적·hermetic) | `8c34a5b1bff9` |
| `nx10/promote/test_soak_recovery_judge.py` | `tests/test_soak_recovery_judge.py` | 판정기가 PASS 를 남발하지 않는지 | `6eb9f46a3305` |
| `nx10/promote/test_cue_lexicon_contract.py` | `tests/test_cue_lexicon_contract.py` | 작동하는 부분은 고정, 결함은 strict xfail | `2da9b1443ef2` |

`docs/` 의 원본은 **이동(mv)** 이다 — 사본을 남기면 시험이 `scripts/` 를 먼저 찾으므로 낡은 사본이
가려지고, "고쳤는데 안 고쳐진" 상태가 조용히 생긴다. 원본 보존은 이 표의 해시와 `promotion-applied.txt` 가 맡는다.

### 1c. **2차 배치 — 준비 완료, 본실행은 동결 해제 뒤** (2026-09-17, 미러 리허설 ALL PASS)

이동표·게이트·리허설·본실행이 `docs/qa/2026-09-16-followup/nx10/promote2/` 에 있다(1차 배치의
`promote/` 와 같은 구조: `paths2.sh` 공유 이동표 + `gates2.sh` 공유 게이트 + 리허설/본실행 분리).

| 스테이징(지금 `docs/`) | 승격 위치 | 역할 | sha256(앞 12, 리허설 실측) |
| --- | --- | --- | --- |
| `nx01/restore_rehearsal.py` | `scripts/restore_rehearsal.py` | restore 절차 판정부 리허설(왕복·손실 방지·멱등·삭제 거절) | `0a46008bba1b` |
| `nx03/rollback_rehearsal.py` | `scripts/rollback_rehearsal.py` | 구버전 판을 그림자 트리로 돌려 되돌림 창의 노출과 복귀 뒤 거절을 잰다 | `f695df1ee8ab` |
| `nx10/promote2/test_restore_rehearsal_contract.py` | `tests/test_restore_rehearsal_contract.py` | 판정부 5결정 + 4경계 + 미수리 결함 기록 + 위생 | `554d648d1950` |
| `nx10/promote2/test_rollback_rehearsal_contract.py` | `tests/test_rollback_rehearsal_contract.py` | 고정 판이 표식 이전인가 + 3국면 + id 재사용 금지 + 위생 | `98628c86ec9a` |

> 해시는 **마지막 리허설이 실측한 값**이다(이동표 자체가 아니라 이동 직전·직후 sha256 비교가 근거).
> 리허설 도구를 고치면 이 열이 낡는다 — 그래서 표가 아니라 `dry-run2-output.txt` 가 정본이다.

**미러 리허설이 증명한 것**(`promote2/dry-run2-output.txt`, ALL PASS · 본 트리 쓰기 0건):
이동 전 스테이징 초록 → 이동(바이트 동일) → **승격 위치에서 14 passed** → 도구 직접 실행 초록 →
ruff check·format 초록 → **도구를 치우면 그 시험이 실패한다**(이빨) → 스테이징 잔존 0건.

**승격 위치 확인은 이제 기록으로 남는다** — `promote2/promoted-contract-tests.txt` (게이트 `A` 가 매번
다시 쓴다): 타임스탬프 · 루트 · HEAD · 실행 명령 · 승격 위치 두 파일의 sha256 · **exit** · 전문(`-v`) …
그리고 판정 줄에서 **수집 노드가 `tests/` 인지**까지 본다. 왜 이게 필요한가: 종전 게이트는 `pytest | tail`
로 요약만 찍어서, 16분짜리 리포트를 끝까지 읽지 않은 사람에게는 “승격 위치에서 통과했다”가 **없었던 것과
같았다**. 그 파이프는 `pipefail` 이 없는 셸에서 **실패해도 초록**이 된다(이 카드가 계속 쫓는 조용한 초록이다).
이번에 새 확인을 넣자마자 첫 실행이 **거짓 FAIL 2건**을 냈다 — 작은따옴표로 쓴 정규식에 변수가 안
확장됐고(`'^${PROMOTED_TESTS[0]}::'`), 요약줄 grep 이 `==== 14 passed ====` 형태를 못 잡았다.
둘 다 고친 뒤 다시 돌려 **14 passed** 를 받았다. 음성 대조군도 확인했다: 승격 **전**에는 같은 명령이
`exit 4` 이고 노드 검사가 red 다(그래서 이 확인은 승격 뒤에만 초록이 된다 — 빈 껍데기가 아니다).

**실행(한 줄, 권장)**: `bash docs/qa/2026-09-16-followup/nx10/promote2/post_harvest_sequence.sh --wait`
— **현재 이 한 줄이 `screen nx10promote` 로 걸려 있다**(종료 18:19 KST 를 기다리는 중, 로그 `promote2/post-harvest-sequence.log`).
무인 실행이라 두 가드를 더 넣고 샌드박스 4경로로 확인했다: **판정 FAIL 이면 승격을 멈추고**(트리 무변경 ·
`NX10_PROMOTE_ON_FAIL=1` 로만 강행) · 떠 있는 감시의 **방금 쓰인** 판정 원문을 먼저 집는다(동시 판정은 자물쇠 경합으로
순서를 끊고, 낡은 원문은 오늘 것으로 안 본다).
— ① 종료 대기 → ② 회수 판정 → ③ 승격 → ④ **새 지문에서 필수 게이트 재측정**(약 16분, screen) → ⑤ 기록·재장전
을 묶은 것이다(승격을 먼저 하면 8시간이 무효이므로 순서를 사람이 기억하지 않아도 되게 묶었다).
`--plan` 은 무엇을 할지만 보여 주고(부작용 0), 승격만 하고 싶으면 `--skip-gates`.
**승격 단독**: `bash docs/qa/2026-09-16-followup/nx10/promote2/apply_promotion2.sh`
— 이 스크립트는 **도는 soak 을 발견하면 거절**한다(`scripts/`·`tests/` 는 지문 대상이므로 8시간이 무효가 된다).
리허설 기록이 ALL PASS 가 아니어도 거절하고, 실패하면 이동을 **자동으로 되돌린다**(백업은 `/tmp`).
실행 뒤에는 반드시 **필수 게이트 재측정 → soak 재장전**(§3 의 순서 규칙)이다.

### 1b. 다음 승격 후보 (동결 해제 뒤 — 2026-09-17 추가)

| 스테이징(지금 `docs/` 안) | 승격 위치(안) | 역할 | 왜 승격해야 하는가 |
| --- | --- | --- | --- |
| `nx01/restore_rehearsal.py` | `tests/test_restore_rehearsal_contract.py`(+ 필요하면 `scripts/`) | restore 절차 판정부(왕복·최신 변경 손실 방지·멱등·삭제 거절) | 제품에 import/restore API 가 없어 **안전성이 절차에만** 있다. 지금은 `docs/` 라 어느 게이트도 이 판정식을 지키지 않는다 — 규칙이 낡으면 아무도 모른다(§2 의 구멍과 같다) |
| `nx01/restore-rehearsal-output.txt` | `tests/` 승격 뒤에는 raw artifact 로 `docs/` 에 남긴다 | 판정 근거(경계 4 + 이빨 1) | 러너·판정기 승격 때와 같다 |
| `nx03/rollback_rehearsal.py` | `tests/test_rollback_generation_contract.py` | 구버전 판을 그림자 트리로 돌려 되돌림 창의 노출과 **복귀 뒤 거절**을 재는 리허설 | NX-03 의 유일한 남은 항목이던 “실리허설 미실시”를 닫은 증거다. 삭제·도구와 가장 가까운 계약인데 지금은 `docs/` 라 안 지켜진다 |
| `nx03/rollback-rehearsal-output.txt` | raw artifact 로 `docs/` 유지 | 판정 근거(경계 3) | 위와 같다 |
| `nx10/soak_watch.py` | `scripts/soak_watch.py` + hermetic 계약 시험 | 돌고 있는 soak 의 조기 경보(멈춤·cap 투영·RSS 외삽·처리량 하한) | 회수 도구는 **끝나야** 판정하므로 오늘 두 실패를 조기에 못 잡았다. 경보 판정식이 낡으면 아무도 모른다 — 자기시험을 `tests/` 계약으로 올려야 지켜진다 |
| `nx10/soak_watch_loop.py` | `tests/test_soak_watch_view_contract.py`(그림·배지 계약) | 표본 적재 + **자기 새로고침 HTML** 추세 화면(화면이 조용히 틀리는 것을 막는다) | 지금은 `docs/` 라 그림·배지 회귀를 아무도 안 본다. 자기시험 9/9 를 계약으로 올린다 |

승격 시 함께 닫을 것: ① 위 표의 1b 항목 ② `NX03-RESTORE-MARKER` 수리안(`original_history`/
`export_original_history` 가 `read_deletion_marker` 도 확인 — [nx01/restore-rehearsal.md](../nx01/restore-rehearsal.md) §2).
둘 다 `src/` 나 `tests/` 를 건드리므로 **동결 중에는 하지 않는다** — 지문이 움직이면 도는 soak 의
시작/종료 지문 일치가 깨진다.

## 2. 왜 이 위치인가 (선례를 따른다)

* `scripts/` — 이 저장소의 검사기·판정기·러너는 전부 여기 산다(`ga_gate.py` · `ga_gate_verify.py` ·
  `evidence_bundle.py` · `migrate_conversation_storage.py` …). `Makefile`·CI 가 `ruff check src/ tests/ scripts/`
  를 돌리므로 **여기 있어야 정적 게이트가 지킨다**.
* `tests/` — 시험 로더 선례도 같다: `tests/test_fr11_gate_verifier.py` 는 `importlib` 로
  `scripts/ga_gate_verify.py` 를, `tests/test_cr13_evidence_bundle.py` 는 `scripts/evidence_bundle.py` 를
  `parents[1]` 기준으로 읽는다. 승격본 시험은 그 로더를 **양쪽 경로에서** 쓰도록 썼다(승격 전 `docs/`,
  승격 후 `scripts/` — 탐색 순서가 `scripts/` 우선이라 이동 뒤에는 승격 위치로 해석된다).

## 3. 절차 (순서를 지킨다)

```
0) 리허설(지금 가능, 본 트리 쓰기 0건)
   bash docs/qa/2026-09-16-followup/nx10/promote/dry_run_promotion.sh
   → 미러 트리에서 이동·게이트·이빨을 실제로 재현. 결과: promote/dry-run-output.txt

1) soak 회수(§4 의 순서 결정을 먼저 확인)
   python3 scripts/collect_soak_result.py --wait

2) 본실행
   bash docs/qa/2026-09-16-followup/nx10/promote/apply_promotion.sh
   → 전제조건(soak PASS·승격 위치 비어 있음) 확인 → mv → 게이트 5종 → 실패 시 자동 롤백

3) 지문이 바뀌었으므로 **그 지문에서 게이트를 다시 잰다**
   python3 scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json --output gate-report-promote001.json
   python3 scripts/ga_gate_verify.py --report gate-report-promote001.json

4) 문서 참조 갱신(수동 — 문자열 치환으로 하지 않는다, 링크가 조용히 깨진다)
   · CLOSURE_RUNBOOK.md — 회수·점검 명령의 nx10/ 스테이징 경로 → scripts/
   · CLOSURE_RUNBOOK.md §5 — 미룬 코드 작업에서 승격 항목을 완료로
   · docs/09_OPERATION_GUIDE.md · nx01/cue-lexicon-measurement.md — 도구 경로
   · scripts/verify_docs_commands.py — REFERENCED_PATHS·검사 대상 문서 목록에 승격 파일 3종 추가
   · nx10/handoff.md · BATCH_FREEZE.md · docs/19 — 승격 완료 사실과 실행 기록
```

## 4. ⚠ 순서 함정 — soak 과 승격은 같은 트리를 가리켜야 한다

(지문의 범위를 정확히: `scripts/ga_gate.py` 의 `tree_digests()` 는 `git ls-files --cached --others
--exclude-standard` 로 **추적+미추적(무시되지 않은)** 파일을 모으고 `docs/`·`.omo/` 만 제외한다.
그래서 ① 승격(새 파일 6개) ② `.gitignore` 편집(추적 중 파일) ③ `data/auth_hash.bak.pre-0000`
삭제·무시(현재 미추적이라 지문 안에 있다) — **셋 다 지문을 움직인다**. 2026-09-16T09:2xZ 에 현재
지문을 다시 계산해 예약 기대값 `157311cf…` 와 **일치함을 실측**했다(이 창의 `docs/` 작업이
지문 밖이라는 것을 가정이 아니라 측정으로 확인).

지표(soak)와 정적 게이트는 **같은 트리**에서 재야 한다. 그런데 승격은 코드를 옮기므로
**지문을 바꾼다**. 그래서 둘 중 하나를 골라야 한다:

* **(A) soak 뒤에 승격** — 예약된 22:00 soak 을 그대로 돌리고(동결 트리 `157311cf…`), 회수 뒤에 승격한다.
  이동이 쉬운 대신, **그 8시간은 승격된 트리를 잰 것이 아니다.** 판정서에는 "soak 은 승격 전 트리,
  정적 게이트는 승격 후 트리"라고 두 지문을 나란히 적어야 한다(EX-05 가 걸렸던 것과 같은 종류의
  불일치를 문서로 명시하는 셈).
* **(B) 승격 먼저, soak 을 승격 트리에서** — 22:00 전에 승격하고 예약을 다시 걸면 **같은 트리에서
  전부** 잰다. 대가는 재측정이다(게이트 재실행 ~19분 + 예약 재장전). 예약 실행기는 지문 불일치를
  스스로 감지해 중단하므로, 승격하면 **반드시 재장전**해야 한다(안 하면 22:00 에 `aborted_reason:
  fingerprint drift` 로 exit 2).

권고: **B** — 8시간을 이미 두 번 옮긴 상태라, 그 8시간이 최종 후보를 재지 않으면 또 다시 재야 한다.
22:00 까지 약 2시간 여유가 있고 게이트 재측정은 19분이면 끝난다.

## 5. 리허설이 실제로 무엇을 잡았는가 (거짓 FAIL 2건)

첫 리허설은 4건 실패였고 **전부 리허설 설계의 결함**이지 승격 대상의 결함이 아니었다:

1. 미러의 `tests/` 를 `__init__.py`·`conftest.py` 만 남긴 골격으로 줄였다 → 승격본 시험의 링크 검사가
   `docs/qa/**/*.md` 의 상대 링크를 저장소 전체 기준으로 보므로 `nx04/after.md → ../../../../tests/test_val02_…py`
   가 **미러에서만** 깨졌다. → 미러는 `tests/` 전체를 복사한다.
2. "도구를 치웠더니 나머지도 빨갛다"로 이빨 검사가 1:1 이 아니라고 판정했다 → 실제로는 위 1번의
   거짓 FAIL 이 기준선에 섞여 있었다. → 비교 기준을 **제거 전 실제 실패 목록**으로 바꿨다(저장소가
   이미 가진 다른 레인의 실패가 이빨 검사를 오염시키지 않게).

두 번째 리허설은 **ALL PASS**: A(이동 전 초록) · B(승격 위치에서 초록) · ruff check/format · 이빨 3건
(도구별 1:1) · 스테이징 사본 0건. 로그 `promote/dry-run-output.txt`.

## 6. 같이 가는 `.gitignore` 규칙 — WARN 1건의 종결(리허설로 효력 확인)

마감 전 점검의 **유일한 WARN** 은 `data/auth_hash.bak.pre-0000`(인증 해시 사본, 0644)이 무시되지 않아
`git add -A` 로 커밋될 수 있다는 것이었다(`.gitignore` 는 `data/auth_hash` 만 막는다). 승격 배치의 3b 단계로
`data/auth_hash.bak*` 를 `.gitignore` 에 추가한다. 리허설은 그 규칙의 **효력**을 미니 저장소에서 두 방향으로
확인한다(전역 `core.excludesFile` 을 끈다 — 켜 두면 개발자 설정이 판정을 대신한다):

* **음성 대조군**: 현재 규칙으로는 가려지지 않는다(`check-ignore` exit 1) → WARN 이 오탐이 아니다.
* **양성**: 규칙을 넣으면 가려진다(`check-ignore` exit 0).
* **부작용 점검**(본실행): 이 저장소는 **이미 추적 중인데 무시되는 파일이 567건 있다** — 그래서 게이트는
  "0건"이 아니라 "새 규칙으로 **늘어나지 않았다**"이다(`git ls-files -i -c` 전후 비교, 늘어난 이름을 출력).

## 6b. 승격이 실제로 고친 결함 3건(본실행과 리허설이 갈라서 드러난 것)

승격은 "파일 옮기기"가 아니라 **도구가 승격 위치에서도 살아 있는지 재는 일**이었다. 첫 본실행이 롤백된 뒤
리허설이 본실행과 같은 게이트를 돌리게 만들자 세 건이 드러났다 — 전부 **스테이징 위치에서만 참이던 가정**이다:

1. **`parents[4]` 저장소 가정** — 검사기·판정기·측정기가 모두 `Path(__file__).resolve().parents[4]` 를
   저장소로 믿었다. `scripts/` 로 옮기면 `…/program` 을 저장소로 잡아 `FileNotFoundError: …/program/.gitignore`.
   → 셋 다 `pyproject.toml` 을 만날 때까지 올라가는 `_repo_root()` 로 바꿨다.
2. **venv 하드 요구** — 검사기가 `REPO/.venv/bin/python` 을 무조건 subprocess 인터프리터로 썬다.
   → venv 가 있으면 그것을, 없으면 지금 돌고 있는 파이썬을 쓴다(새 클론·CI 샌드박스·미러에서도 돈다).
3. **비밀 스캔이 git 을 하드 요구** — `git status` 가 비-git 트리에서 예외로 죽었다.
   → git 작업 트리가 아니면 **문장으로 건너댐을 말하고** 나머지는 그대로 잰다(조용한 스킵도 가짜 초록도 아니다).

부수적으로 문구 하나도 고쳤다: 인증 해시 사본에 대한 상시 WARN 은 규칙이 들어간 뒤에도 영원히 경고로 남는다.
지금은 **조건을 보고** 가려지면 `[OK] … 무시된다`, 아니면 WARN 이다.

## 7. 리허설 도구가 스스로에게 물은 것(이 창의 실수 하나)

양성 대조군 메시지를 큰따옴표로 쓰면서 그 안에 역따옴표를 넣었다 — bash 에서 그것은 **명령 치환**이라
`data/auth_hash.bak.pre-0000` 이 실제로 실행됐고(`Permission denied`), 결과 줄만 보면 **ALL PASS** 로 위장했다.
그래서 리허설은 자기 출력을 자기 파일에 남기고 마지막 단계에서 **출력 자체를 검사**한다(bash 진단이 섮이면
초록을 주장할 수 없다). "초록의 의미"를 도구가 먼저 의심하게 만든 변경이다.

## 8. 본실행 기록 — 두 번 멈추고 세 번째에 성공했다

| 시도 | 멈춘 지점 | 원인 | 이동 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | `2. 이동 전 해시` | `NXF` 오산(`../../..`) — 리허설은 경로를 하드코딩해서 통과했다 | **0건** | `paths.sh` 로 표·경로를 공유 |
| 2 | `4-4` 검사기 자체 실행 | `parents[4]` 가정(§6b-1) | **0건**(해시까지 대조해 롤백) | 도구 3종 `_repo_root()` + venv 폴백 |
| 3 | — | — | **6건 + .gitignore** | 게이트 7/7 · 지문 `ab980ba5…` · 22:00 재장전 |

리허설도 같은 게이트를 돌리게 바꾼 직후 7개 중 3개가 빨간 것을 확인하고 고쳤다(§6b) — 그 3개가
**본실행에서 처음 발견되면 6건이 이미 옮겨진 상태**였다. 순서를 바꾼 것이 이번 창에서 가장 값싼 개선이었다.

## 8b. 승격 뒤 지문 재측정 — 두 번 재야 했다(그 이유가 규칙이 됐다)

승격 뒤 필수 22개를 새 지문에서 재측정했다(`run_promote_gates.sh`). 첫 실행(`promote001`)은
**시작 지문 ≠ 종료 지문** 으로 끝났는데, 원인은 게이트가 아니라 **이 창이 측정 중에 코드를 고친 것**
이었다(`scripts/verify_docs_commands.py`, 09:52Z). 지문 범위 파일의 mtime 을 세워원인을 확인했다 —
`dashboard-build`·`sbom-generate` 는 추적 중인 번들·SBOM 을 재작성해도 지문을 흔들지 않았다(동결 러너와
같은 관찰, 두 번재 실측). 그래서 무편집 구간에서 `promote002` 를 다시 돌렸고, 그 결과를 값으로 쓴다.

교훈은 _측정 중에는 아무 파일도 만지지 않는다_ 하나로 줄지만, 그 뒤에 **예약도 마지막 측정 뒤에 건다**가
따라붙는다 — 이 창은 순서를 반대로 해서 재장전을 두 번 했다.

## 9. 한계·남는 위험 (승격이 만드는 새 상태)

* **strict xfail 20건이 스위트에 들어온다** — `test_cue_lexicon_contract.py` 는 지금 성립하지 않는
  3결함(바꿔쓰기 누락 · 잉여 승격 · 편집 지시에 의한 무효화)을 strict xfail 로 적는다. 즉 승격 뒤
  스위트 출력에 `20 xfailed` 가 **상시** 나타나고, 어휘를 고치면 그 시험들이 **예상 밖 통과(XPASS)** 로
  실패해 측정 문서·이 파일을 함께 갱신하게 만든다. 의도된 설계지만, 판정서의 "0 failed" 문구에
  `xfailed` 를 어떻게 적을지는 정해 두어야 한다(현재 계획: **xfailed 는 실패가 아니라 미해결 결함의
  등록부**로 적고, 목록과 소유자를 함께 명시).
* **승격 자체가 새 지문을 만든다** — 동결 트리의 `gate-report-freeze002.json`(21/22)은
  옛 지문의 값이다. 승격 뒤 후보로 물려받지 않는다(§3-3).
* **`docs/` 안에 도구를 두지 않게 된다** — `docs/` 만 보는 독자(이 QA 카드 문서)는 이제 `scripts/` 를
  가리키는 링크를 갖는다. §3-4 의 참조 갱신을 빠뜨리면 링크가 깨지고, 승격된 계약 시험의 링크 검사가
  그걸 **실패로 잡는다**(그게 이 승격의 목적이기도 하다).
* **소유자** — 승격 뒤 소유자는 게이트다(사람 아님). 다만 §3-4 의 문서 참조 갱신은 소유자가 없어
  NX-10 창이 맡는다.
* **이 계획이 하지 않는 것** — 어휘 결함 수정 · 마감 절차 편입 · 커밋. 앞의 둘은 동결 해제 뒤
  별도 작업이고, 커밋은 오너 승인(D4) 사항이다.
