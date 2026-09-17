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

**적용 완료 — 2026-09-17T02:24Z**(오너 지시: 무인 대기를 취소하고 즉시 승격). 승격 **전** 기록: 무인 대기
(`screen nx10promote`)를 취소 → 3차 soak 을 `SIGTERM` 으로 중단(`exit: 143`, 시작=종료 지문 `5c90b637…`) →
본실행. 이동 4건 전부 **sha256 동일**(백업 `/tmp/nx10-promote2-backup-20260917T022400Z`), 승격 위치에서
**14 passed**(`promoted-contract-tests.txt`) · 도구 직접 실행 초록 · ruff check·format 초록. 커밋 `bde261dc`.
(게이트는 커밋 **뒤에** 쟀다 — 결과는 §1d.) 기록: `promote2/promotion2-applied.txt` · `apply2-output.txt`.

| 스테이징(이제 **없다** — 이동됨) | 승격 위치 | 역할 | sha256(앞 12, 리허설 실측) |
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

**다음에 같은 일을 무인으로 하려면(한 줄)**: `bash …/promote2/post_harvest_sequence.sh --wait`
— ① 종료 대기 → ② 회수 판정 → ③ 승격 → ④ **새 지문에서 필수 게이트 재측정**(약 16분, screen) → ⑤ 기록·재장전
을 묶은 것이다(승격을 먼저 하면 8시간이 무효이므로 순서를 사람이 기억하지 않아도 되게 묶었다).
무인 실행이라 두 가드를 넣고 샌드박스 4경로로 확인했다: **판정 FAIL 이면 승격을 멈추고**(트리 무변경 ·
`NX10_PROMOTE_ON_FAIL=1` 로만 강행) · 떠 있는 감시의 **방금 쓰인** 판정 원문을 먼저 집는다(동시 판정은 자물쇠 경합으로
순서를 끊고, 낡은 원문은 오늘 것으로 안 본다).
`--plan` 은 무엇을 할지만 보여 주고(부작용 0), 승격만 하고 싶으면 `--skip-gates`.
**승격 단독(이번에 쓴 경로)**: `bash docs/qa/2026-09-16-followup/nx10/promote2/apply_promotion2.sh`
— 이 스크립트는 **도는 soak 을 발견하면 거절**한다(`scripts/`·`tests/` 는 지문 대상이므로 8시간이 무효가 된다).
리허설 기록이 ALL PASS 가 아니어도 거절하고, 실패하면 이동을 **자동으로 되돌린다**(백업은 `/tmp`).
실행 뒤에는 반드시 **필수 게이트 재측정 → soak 재장전**(§3 의 순서 규칙)이다.

### 1d. **2차 배치 승격 뒤 재측정** — 승격이 숨은 타입 오류를 드러냈다 (2026-09-17, attempt `promote2b`/`2c`/`2d`)

| attempt | 지문 | 결과 | 이 attempt 가 한 일 |
|---|---|---|---|
| `promote2b` | 시작 = 종료 = `50b82dd1…`(커밋 `bde261dc`) | **21 passed · 2 failed · 0 not_run** | 승격 직후 첫 재측정. **새 실패 1개**: `python-basedpyright` 가 새로 빨개졌다 |
| `promote2c` | 시작 = 종료 = `b6a74304…`(커밋 `5c979c0f`) | **22 passed · 1 failed · 0 not_run** | 타입 12건을 고친 뒤 재측정 — basedpyright **초록** · `clean-machine-runtime` passed |
| `promote2d` | 시작 = 종료 = `b6a74304…` | `python-tests` 단독: **5 failed · 6640 passed**(618.94s) | 승격이 깬 문서 링크 1건을 `docs/` 만 고쳐 닫고 단독 재측정 |

**`promote2b` 의 새 실패는 회귀가 아니라 이 승격의 정의다**: 승격 **전**에는 두 도구가 `docs/` 안이라
`python-basedpyright` 가 **보지 않았다**. 커밋된 후보로 들어온 순간 타입 오류 **12건**이 드러났다
(`scripts/restore_rehearsal.py` · `scripts/rollback_rehearsal.py` — `dict[str, object]` 언패킹 · `Any` 누수 · 시그니처).
즉 **승격 = 파일 이동 + 검사 대상 편입**이고, 편입이 곧 첫 검사다. 수정은 `5c979c0f`(같은 커밋에서 테스트 파일의
`Any` 도 줄였다 — 그대로 두면 그쪽에서 11건이 난다).

**승격이 깬 문서 링크 1건**: `tests/test_local_relative_links_resolve` 가 옮겨진 파일을 옛 경로로 가리키는 참조
3곳을 잡아냈다(`docs/09_OPERATION_GUIDE.md` · `docs/19` NX-01/NX-03 항목 · `nx01/handoff.md` ·
`nx01/restore-rehearsal.md` · `nx03/handoff.md`). 이 참조 갱신은 §9 가 “소유자가 없다”고 적어 둔 항목이고,
예상대로 **게이트가 먼저 실패해서** 알려 줬다(사람이 기억하지 않아도 됐다). 고친 편집은 `docs/` 뿐이라 지문은
`b6a74304…` 그대로다.

**이 지문이 지금의 후보 트리다**: `b6a74304…` = 현재 트리 = HEAD 트리(`5c979c0f`) 에서 4차 8시간 soak 이
돌고 있고(`03:25:56Z` → `11:25:56Z` = 20:25 KST · preflight 7/7), 판정은 여전히 NO-GO 다(required red 1 = 타 레인 ·
CR-14 재선언 없음 · owner 허용 없음). 통과 수 **6626 → 6640(+14)** 이 승격한 계약 시험의 몫이다.

### 1e. **3차 배치 — 준비 완료, 본실행은 동결 해제 뒤** (2026-09-17, 미러 리허설 `attempt1`→`attempt4`)

이번에 옮기는 것은 **오늘 밤 내내 판단을 내린 감시·통제 도구 셋**이다. 도구 위치와 증거 위치는 여전히
분리한다(파생물·이력·화면은 카드 레인인 `docs/…/nx10/` 에 그대로 쓴다).

| 스테이징(지금 `docs/` 안) | 승격 위치 | 역할 |
| --- | --- | --- |
| `nx10/soak_watch.py` | `scripts/soak_watch.py` | 돌고 있는 soak 의 판정식(멈춤·cap 투영·RSS 예산·처리량 하한) |
| `nx10/soak_watch_loop.py` | `scripts/soak_watch_loop.py` | 표본 적재 + 자기 새로고침 라이브 화면 |
| `nx10/soak_control.sh` | `scripts/soak_control.sh` | 예약(`arm`)·실행(`run`)·취소(`cancel`)·회수(`harvest`) 통제 |
| `promote3/test_soak_watch_contract.py` | `tests/test_soak_watch_contract.py` | 판정식·그림의 계약(자기시험 8/14 + 음성 대조군) |
| `promote3/test_soak_control_contract.py` | `tests/test_soak_control_contract.py` | 수명주기 자기시험이 게이트 안에서 매번 돈다 |

**이번 리허설이 잡은 것은 도구가 아니라 시험 쪽 결함이었다** — 그리고 그것이 오늘의 세 번째 “조용한 초록”
부류다. 리허설은 커밋되지 않은 파일을 작업 트리에 두는 것이 정의이므로, 그 트리에서는 `현재 트리 ==
HEAD 트리`(후보 귀속)가 **설계상** 거짓이다. 그런데 자기시험의 “건강하면 `preflight` 0” 픽스처 넷이 그
전제를 공유해 **미러에서 전부 1 을 받았고**, 계약 시험이 그것을 red 로 보고했다.

| attempt | 무엇이 달라졌나 | 결과 |
|---|---|---|
| `attempt1` | 배치 초판 | 실패 2건 — 계약 시험 `1 failed` + “승격 위치 자기시험 실패”. 원문에 `⑧ 넉넉한 캡이면 preflight 0` · `⑨ 예약을 지목` 이 남았다 |
| `attempt2` | 두 픽스처에 `NX10_PF_SKIP_ATTRIBUTION=1` 를 **박아 넣음** | 여전히 실패 — 남은 두 픽스처(`⑧ 건강한 예약이면 preflight 0` · `⑧ 처리량 하한을 넘으면 preflight 0`)가 같은 전제를 공유했다. **박아 넣기가 답이 아니었다** |
| `attempt3` | 규칙으로 바꿈: 트리 ≠ HEAD 면 `attr_skip=1` 을 시험이 **스스로 계산**해 네 픽스처에 적용하고, 생략 사실을 출력에 남긴다 | **ALL PASS** (계약 시험 `14 passed` · 이동 5건 sha256 동일 · 이빨 3/3 · 스테이징 잔존 0) |
| `attempt4` | 게이트 B 가 자기시험 **전문**을 `promoted-selftest3.txt` 로 남기게 함(`tail | grep` 로 판정하던 자리도 exit 직접 수신으로 교체) | **ALL PASS** — 그리고 그 산출물에 `자기시험 환경: 작업 트리 ≠ HEAD — 후보 귀속 검사를 생략한다` · `⑧ (전제) 후보 귀속 생략을 문장으로 밝힌다` · `SOAK_CONTROL_SELFTEST: 76/76 passed` 가 남았다(깨끗한 트리 75/75 + 더러운 트리 전용 확인 1건) |

**고친 방식이 요점이다**: 더러운 트리에서 그 항목만 빼되 **`후보 귀속(생략됨)` 이라는 문장으로 밝히고**,
깨끗한 트리(실제 운영·실제 soak)에서는 종전대로 검사한다 — 실트리 자기시험 **75/75** 에서
`⑧ 후보 귀속(현재 트리 == HEAD)까지 본다` 가 그대로 초록인 것으로 확인했다. 즉 이빨은 깨끗한 트리에서
그대로 물고, 리허설에서는 “무엇을 생략했는지”가 증거로 남는다(조용한 스킵 금지 — 하루 종일 반복된 규칙).

| `attempt5` | 계약 시험 docstring 의 자기시험 수(75 → 75~76, 환경에 따라)를 고침 | **ALL PASS** — 바이트가 바뀌었으므로 리허설을 다시 돌려 이동 바이트 동일을 다시 확인했다 |
| `attempt6` | (배치 바이트 변경) `soak_control.sh` 에 **셸 오탐 차단** + 이빨 ⑧b 추가 — 본 트리 자기시험 **77/77** 을 보고 걸었다 | **실패 2건** — `⑧ (이빨) 셸이 패턴에 걸러도 preflight 0 (기대=0 실제=1)`. 원인은 도구가 아니라 **내 시험**: 그 자리만 preflight 를 직접 호출해 공용 헬퍼의 귀속 문(`NX10_PF_SKIP_ATTRIBUTION`)을 빠뜨려, **더러운 트리(미러)에서만** 빨개졌다 — §25-8 |
| `attempt7` | 그 자리에 같은 문을 붙이고, 생략이면 **문장으로 밝히는** 검사를 함께 넣음(조용한 생략 금지) | **ALL PASS** — 계약 시험 `14 passed in 110.64s` · 이동 5건 sha256 동일 · 이빨 3/3 · 스테이징 잔존 0 · 자기시험 **79/79**(더러운 트리 전용 확인 1건 포함) |
| `attempt8` | 계약 시험 docstring 의 자기시험 수(75~76 → **77/79**)를 고침 — 값을 만드는 코드와 그 값을 말하는 문장을 같은 커밋에 둔다 | **ALL PASS** — `14 passed in 106.77s` · 자기시험 79/79 · 이동 5건 sha256 동일 · 본실행이 옮길 **검증된 바이트**: `soak_watch.py 88af4a5b5264` · `soak_watch_loop.py d7b1df867443` · `soak_control.sh 00661d6f2152` · `test_soak_watch_contract.py f7bf824145b7` · `test_soak_control_contract.py a713185925d4` |

| `attempt9` | (`soak_watch.py`·`soak_watch_loop.py`·계약 시험에 **workdir 엄격 문 + 재부착 수정**을 넣은 바이트 — 오너 지시) | **실패 1건** — `ruff format --check`(포맷만 어긋남 · 계약 시험 17 passed·이빨 A·B·D 초록) → 포맷 뒤 재실행 |
| `attempt10` | 두 파일 포맷 + **재부착 계약 시험** 추가(`test_loop_attaches_to_a_run_already_in_flight`) | **ALL PASS** — 계약 시험 `17 passed in 108.89s` · 이빨 3/3 · 스테이징 잔존 0 · 이동 5건 sha256 동일 · 본실행이 옮길 **검증된 바이트**: `soak_watch.py fc8599af9d48` · `soak_watch_loop.py c38d16d58845` · `soak_control.sh 00661d6f2152` · `test_soak_watch_contract.py 263ea2da0777` · `test_soak_control_contract.py a713185925d4` |

> `attempt10` 의 바이트로 상시 감시를 **재부착까지 마쳤다**(`GATE_LEDGER` §27-3). 리허설이 증명하는 것은
> “동결 해제 뒤 옮길 바이트”이고, 그 바이트가 지금 이미 도는 것은 `docs/` 사본뿐이다(지문 불변).

**두 트리에서 각각 무엇을 물었는지가 남았다**: 깨끗한 트리(실트리) `75/75` — `⑧ 후보 귀속(현재 트리 ==
HEAD)까지 본다` 가 그대로 초록이라 귀속 검사가 살아 있음이 증명된다. 더러운 트리(미러) `76/76` — 같은 항목이
`후보 귀속(생략됨)` 으로 바뀌고 **그 문장을 확인하는 검사가 하나 더 붙는다**. 생략이 조용하지 않다는 뜻이다.

**프로세스 규칙 하나가 더 굳었다**: 돌고 있는 셸 스크립트를 **편집하면 안 된다**. `soak_control.sh` 는 그
순간 회수 감시(`screen nx10harvest`)가 실행 중이었고, bash 는 스크립트를 조금씩 읽으므로 수정이 실행을
깨뜨릴 수 있다. 그래서 편집 전에 감시를 내리고(프로세스 0건 실측) 편집 뒤 재부착했다 — 회수 도구의
`cancel` 이 “취소했다고 기록한 예약이 살아 있었다” 를 겪은 뒤 세운 규칙(죽음 확인)을 이 창에도 적용한 것.

### 1f. **배치 `SC6` — SC-6 기준 구현**(준비 완료, 본실행은 동결 해제 뒤 · 2026-09-17)

오너 지시(“새 기준을 구현하고 계약 시험으로 고정”)에 따라 기준을 **코드와 시험으로** 옮겨 두었다.
이 배치는 도구 이동이 아니라 **기준 변경**이라, 적용 순서가 더 엄격하다(도는 soak 의 지문을 건드린다).

| 위치(지금) | 적용 뒤 | 역할 | 검증된 바이트 |
| --- | --- | --- | --- |
| `sc6fix/val02_staging.py` | `scripts/val02_staging.py` (**덮어씀**) | 기준 구현 — `max(5분, 지속×5%)` 창 밖 증가(P1) + 반복당 creep(P2) + `not_applicable` | `ecd826ce90af…` |
| `sc6fix/test_sc6_criterion_contract.py` | `tests/test_sc6_criterion_contract.py` (신설) | 그 기준을 지키는 계약 시험 8건(음성 대조군 포함) | `cd4ff2da732b…` |
| `sc6fix/apply_sc6fix.sh` | — (도구) | 본실행: 동결 가드 + **사전 이미지 sha256 고정** + 백업 + 실패 시 자동 롤백 | `ea45db386c96…` |
| `sc6fix/rehearse_sc6fix.sh` | — (도구) | 미러 리허설(본 트리 쓰기 0건) | `b34ef49cfdc1…` |

**적용 전 바이트 고정**: `scripts/val02_staging.py` 의 사전 이미지 sha256
`83da9a4885038bac710938a8cfc8bed13ac620dd664975fa86639eb2bc1b16b2` — 다른 바이트 위에는 덮지 않는다.

**리허설 결과(미러, ALL PASS 22건 · `sc6fix/rehearsal-output.txt`)**: 사전 이빨(적용 전 계약 시험이 **실패**한다) ·
동결 가드 물림(exit 9) · 적용 뒤 ruff/format/basedpyright(0 errors)/계약 시험 8 passed/기존 val02 시험 ·
**실제 60초 리허설**이 `rss_criterion="not_applicable"` 과 사유를 리포트에 남김 · 도구를 되돌리면 시험이 빨개짐 ·
다른 바이트 위에는 거부(exit 8) · 본 트리 하네스 바이트 불변·신설 파일 없음·지문 대상 쓰기 0건.

**이 리허설이 잡은 것(여섯 번째 “조용한 어긋남”)**: 첫 회차가 `apply` 단계에서 **자동 롤백**됐다 —
계약 시험이 `반복당 creep` 의 재현성에서 걸렸다. 원인은 기준이 아니라 **반올림 지점이 두 곳**인 것이었다
(리포트는 0.1 MB 단위로 싣는데 creep 은 반올림 전 값으로 계산 → 다음 사람이 리포트만으로 재현하면 1e-4 어긋남).
반올림을 한 번만 하도록 고치고, 그 틈을 고정하는 시험(`test_report_rounding_does_not_open_a_reproducibility_gap`)을
추가했다 — “리포트만으로 같은 판정을 재현한다”는 새 기준의 전제가 시험으로 남는다.

**적용 순서(어기면 지문이 갈린다)**: 4차 soak 회수 → **3차 배치(도구 5건) 승격** → **배치 `SC6` 적용** →
필수 게이트 재측정 → 새 지문에서 8시간 soak(그 실행이 SC-6 를 **새 기준으로** 판정한다).
60초 리허설의 SC-6 행은 이제 `not_applicable` 이다(1분 실행에 8시간 임계값을 물으면 시작 비용을 누수로 본다).

**남는 한계(정직하게)**: `not_applicable` 이 아닌 **통과 경로**는 픽스처로는 증명했지만 실물 규모(700초 이상)에서는
아직 안 돌았다 — 다음 8시간 soak 이 처음으로 그 경로를 실물로 지난다(그 전까지 이 배치는 “리허설 ALL PASS” 상태다).

#### 1e-1. **회수 뒤 순서를 무인으로** — 오너 요청(2026-09-17)

한 줄로 묶었다: `promote3/post_harvest_sequence3.sh --wait` → ① 실행 종료 대기 ② 회수 판정 ③ 감시 도구 정리
④ 승격 ⑤ 커밋 ⑥ **새 지문에서 필수 23개 재측정** ⑦ 기록. 재장전은 `--rearm` 을 준 경우에만 한다(밤에
두 번째 8시간을 자동으로 태우는 것은 오너 결정이지 스크립트의 기본값이 아니다).

**왜 커밋이 이 순서에 들어오나**: `clean-machine-runtime` 은 `--ref HEAD` 를 export 하므로 **커밋된 트리만**
후보 값이 된다. 즉 “승격 → 커밋 → 재측정”은 취향이 아니라 게이트의 요구다. 그래서 이 순서만은 커밋을
사람에게 미루지 않고 **명시 경로만**(`git add -A` 금지) 스테이징해 커밋한다 — 대신 `--skip-commit` 으로
멈출 수 있게 했다.

**멈춰야 할 때 정말 멈추는지 셋 다 미러에서 실측했다**(`rehearse_sequence3.sh` → `sequence3-rehearsal.txt`):

| 경로 | 조건 | 결과 |
|---|---|---|
| A | 판정 PASS · 지문 일치 | 승격 + 커밋까지 진행 · 커밋 뒤 코드 경로 깨끗(게이트 전제 성립) |
| B | 판정 FAIL | **멈춤 · 트리 무변경**(스테이징 sha256 동일) + 중단 기록 |
| C | 시작 ≠ 종료 지문 | **멈춤 · 트리 무변경** + 중단 기록(귀속 불성립 — 승격 근거가 없다) |

그 리허설이 **하나를 더 잡았다**(오늘의 4번째 “조용한 어긋남”): 계약 시험 `test_harvest_refuses_to_judge_a_live_run`
은 “도는 soak 이 있는가”를 `pgrep -f val02_staging.py` 로 **하드코딩**해 판단했는데, 도구는 이름을
`NX10_SOAK_PROC_PATTERN` 으로 받는다. 이름을 바꿔 돌리는 환경(미러 리허설이 정확히 그랬다)에서 **시험은
“있음”(4를 기대), 도구는 “없음”(3을 반환)** 이 되어 계약 시험이 거짓으로 빨개졌다 — 승격 뒤 첫 게이트 A 가
`1 failed` 로 멈춘 이유가 그것이다(승격 자체는 정상이었고 자동 롤백이 트리를 지켰다). 고침: 시험이 **도구와
같은 이름 규칙**으로 찾는다. 같은 이유로 `apply_promotion3.sh` 의 동결 가드도 이름을 받도록 바꿨다 —
가드를 **끄는** 대신 **대상 이름을 통제**하는 것이 이 프로젝트의 규칙이다(취소한 예약이 살아 있던 사고 뒤로).

무인 실행 중 실패하면 트리를 옮기지 않고 멈춘다. 판정 FAIL 을 무릅쓰고 강행하려면 `NX10_PROMOTE_ON_FAIL=1`
— FAIL 원인이 후보 코드면 승격 직후 지문이 또 움직이기 때문이다(오늘 SC-6 로 그것을 계산해 둔 이유다).

### 1g. **배치 `PERF` — 처리량 회귀 축**(준비 완료, 본실행은 동결 해제 + `SC6` 뒤 · 2026-09-17)

오너 지시(“처리량 감소를 1급 판정 축으로 삼는 성능 회귀 게이트 — 8시간에 27% 느려진 실행을 RSS 누수와 별개로”)에
따른 배치. 설계·보정 원자료: [perf/THROUGHPUT_GATE_DESIGN.md](./perf/THROUGHPUT_GATE_DESIGN.md) · 대장 §29.

| 위치(지금) | 적용 뒤 | 역할 | 검증된 바이트 |
| --- | --- | --- | --- |
| `perf/val02_staging.py` | `scripts/val02_staging.py` (**덮어씀**) | RSS 축(SC6) + **처리량 축**(정체식 분해) + **귀속 사다리 4칸**(국면 적립 → 국면 안 함수 창 프로파일 → 호출 경로·빈도) | `a67695013fde…` |
| `perf/test_throughput_gate_contract.py` | `tests/test_throughput_gate_contract.py` (신설) | 계약 시험 **47건**(축 독립 4조합 · 실측 실행 회귀 · 면제는 통과 아님 · **귀속 사다리 10건** · **국면 내부 12건** · **호출 경로 12건**) | `e47a4151872d…` |
| `perf/live-4th-series.json` | `tests/live-4th-series.json` (신설) | 시험 #10 의 **실측 입력**(4차 실행 표본 288개) | `b9f25b218c76…` |
| `perf/apply_perf_gate.sh` | — (도구) | 본실행: 동결 가드 + **사전 이미지(=SC6 적용 뒤)** + 백업·자동 롤백 · **승격 위치 정적 검사** | `59a6c01fd6f0…` |
| `perf/rehearse_perf.sh` | — (도구) | 미러 리허설 7시나리오(본 트리 쓰기 0건) | `c5332d007d1e…` |
| `perf/probe_ladder_end_to_end.py` | — (도구 · `docs/` 전용) | 사다리 **배선 실측** 프로브(실제 하네스 60초 × 4회 · D 국면 내부 창 · **E 호출 경로·빈도**) | `d9f48b3ef0f9…` |
| `perf/probe-ladder-output.json` | — (산출물) | 프로브가 실제 하네스에서 받은 판정·국면 단가·함수 순위·**호출 사슬** | `6ca277f959c3…` |

**합성 순서를 코드로 고정한다**: `SC6` 과 `PERF` 는 **같은 파일**(`scripts/val02_staging.py`)을 바꾸므로
`PERF` 의 사전 이미지는 동결 바이트(`83da9a48…`)가 아니라 **`SC6` 적용 뒤 이미지**(`ecd826ce90af…`)다.
동결 바이트를 만나면 “SC6 를 먼저”로 **exit 6**(쓰기 0건) — 두 배치가 서로 다른 바이트를 검증하는 사고를 막는다.

**귀속 사다리(같은 배치에 합류)**: 게이트가 빨간 실행에서만 돌아 `phase`/`spread`/`outside_phases`/
`insufficient` 로 “어느 국면이 느려졌나”를 좁히고, 초록이면 돌지 않는다(설계 §9 · 대장 §30). 이어 붙은
**세 번째 칸**은 지목된 국면 **안**을 창 단위 `cProfile` 로 열어 `function`(이름 지목)/
`spread_within_phase`/`outside_functions`/`insufficient` 로 한 번 더 좁힌다(설계 §10 · 대장 §31). 계측한
창의 반복은 **판정 계열에서 제외**하고, 계측기 자신의 프레임은 순위에서 빼되 뺐다고 밝힌다.

**네 번째 칸**(오너 지시 2026-09-17)은 지목된 함수를 **누가 부르고 반복당 몇 번** 부르는지 좁힌다(설계 §11 ·
대장 §32): `path`/`multi_path`/`insufficient`/`not_applicable` + `path_calls_per_iteration` ·
`path_callers_top` · `path_chain`. 경로와 빈도를 **나눠 내는 이유는 처방이 다르기 때문**이다(1회 → 그 호출
자체를 싸게 · 여러 번 → 호출을 합친다). 자료는 `cProfile` 이 이미 들고 있는 호출자 표다(새 계측 0).
실측: `posix.fsync` ← `conversation_journal.py:_fsync_fd` ← `_append_bytes` ← `append` ← `_commit_event`,
**반복당 1.00회**.

**리허설 결과(미러, ALL PASS 17/17)**: P1 적용 전 이빨(SC6 이미지에서 계약 시험이 **실패** — 사다리 시험 포함) · P2 적용·검증
(승격 위치 시험 통과 · 60초 스모그가 `throughput_criterion` 을 사유와 함께 리포트에 실음 · 이동 sha256 동일 ·
승격 위치 정적 검사 0 errors) · **P2b 승격 위치에 심은 타입 오류를 exit 5 로 물고 자동 롤백** ·
P3 동결 가드 exit 9 · P4 합성 순서 exit 6 · P5 사전 이미지 불일치 exit 8 · P6 지문 대상 3파일 전후 동일.
P1 은 이제 **세 칸 시험 전부가 SC6 이미지에서 빨개지는 것**까지 본다(시험이 조용히 통과하지 않는다).
리허설이 **결함 2건**을 찾았다: ① 두 축 다 `not_applicable` 인데 시나리오 `pass=True`(게이트를 비울 수 있는 문)
→ `criteria_gate` 로 봉인(긴 실행의 면제는 재실행 요구, 계약 시험 #12) ② 계약 시험 파일이 `docs/` 안에
있는 동안 **정적 게이트의 시야 밖**이라 `basedpyright` 오류 **5건**을 숨기고 있었다(승격하면 정적 게이트가
빨개지는 부류 — §1d 에서 실제로 겪었다) → 고치고, **승격 위치 정적 검사**를 `apply_perf_gate.sh` 검증에 넣었다.

**적용 순서**: 4차 soak 회수 → 3차 배치 → `SC6` → **`PERF`** → 필수 게이트 재측정 → 새 지문에서 8시간 soak
(그 실행이 **처음으로 두 축으로** 판정된다). 오너 결정 3건(D-P1 허용 15% · D-P2 경합 재실행 · D-P3 최소 2시간) 대기.

### 1h. **배치 `FLUSH` — flush 예산**(설계만 완료 · 본실행은 동결 해제 + `PERF` **뒤** · 2026-09-17)

오너 지시(“`conversation.append` 의 fsync 69% 를 근거로 flush 정책·배치 대안들을 동결 해제 뒤 지문에 반영할 수
있는 배치로”)에 따른 배치. 설계·증거: [fsync/FLUSH_BATCH_DESIGN.md](./fsync/FLUSH_BATCH_DESIGN.md) · 대장 §33.
**`src/` 를 바꾸는 첫 배치다** — 지금 돌고 있는 4차 soak 의 지문 대상 그 자체이므로 **항상 맨 마지막**이다.

| 스테이징(`docs/` 안) | 적용 뒤 | 역할 |
| --- | --- | --- |
| `fsync/patch_flush_budget.py` | — (도구) | F1 패처(훅 6개 · 사전 이미지 고정 · `--check/--apply/--revert`) |
| `fsync/test_flush_budget_contract.py` | `tests/test_flush_budget_contract.py` (신설) | 계약 시험 **9건**(예산 결정적 + 내구성 불변) |
| `fsync/apply_flush_batch.sh` | — (도구) | 동결 가드 exit 9 · 합성 순서 exit 6 · 사전 이미지 exit 8 · 자동 롤백 exit 5 |
| `fsync/rehearse_flush.sh` | — (도구) | 미러 리허설 7시나리오(본 트리 쓰기 0건) |
| `fsync/probe_flush_path.py` + `probe-flush-output.json` | — (증거) | append 예산 · fsync 곡선 · 플랫폼 능력 |

**배치의 핵심**: 근거는 시간이 아니라 **개수**다(디스크 상태와 무관). append 1회에 `tail()` 3.00회 ·
읽은 바이트 116 KB · `open` 5.00 · **`fsync` 1.00(불변)**. F1 은 꼬리를 **한 번만** 읽어
(3.00 → 1.00 · 113 KiB → ≈38 KiB · `open` ≤4) 내구성 계약은 **한 글자도 안 바꾼다**. F2(view 스로틸)·
F3(sync 정책 · **ADR §2 개정 필요**)는 **오너 결정 뒤 별도 배치**다(D-F1~F4).

**사전 이미지**(다르면 아무것도 쓰지 않는다): `conversation_journal.py a89dfd2d82cc…` ·
`conversation_store.py 7f3e4605da9d…`. 미러 리허설 **ALL PASS 16/16**(적용 전 이빨 3 failed · 적용 뒤 9 passed ·
기존 시험 70 passed 무회귀 · 심은 타입 결함 롤백 · 동결 exit 9 · 합성 순서 exit 6 · 사전 이미지 exit 8 · 본 트리 무변경).
적용 순서: **회수 → 3차 배치 → `SC6` → `PERF` → 게이트 재측정 → `FLUSH` → 게이트 재측정 → 새 8시간 soak**.

**세 대안을 배치 셋으로 나눈 것**(설계 §10 · 오너가 고르는 표): `FLUSH`(F1 · 계약 불변 · **지금 적용 가능**) ·
`FLUSH2`(F2 view 스로틸 — 훅 4개·시험 후보 5건·기본값은 현행 `immediate` 라 무회귀) · `FLUSH3`(F3 sync 정책 —
**ADR-DAT-02 §2 개정 6문장이 선행물**, 플랫폼 강등·크래시 시뮬레이션 시험 후보 6건, 되돌림은 노브 한 줄).
F2·F3 은 “문장이 정해져야 시험을 쓰는 종류”라 **결정 뒤 배치로 만드는 조건**(훅·시험·사전 이미지·합성 순서)만
지금 적어 두었다 — 승인이 서면 같은 틀(사전 이미지 고정 · 가드 셋 · 승격 위치 정적 검사)로 바로 만든다.
검증된 바이트(2026-09-17T10:01Z): 패처 `e2016ef42ced…` · 시험 `59d469ead4e1…` · apply `92fdcef5b0e3…` ·
rehearse `945250421759…` · 프로브 `0382e99fbcf2…` / `537fa87fbb38…` · **리허설 재확인 ALL PASS 16/16**.

### 1i. **배치 `FLUSH2` — view 신선도**(계약·구현·리허설 완료 · 본실행은 `FLUSH` **뒤** · 2026-09-17)

오너 지시(“신선도 계약을 정하고 계약 시험으로 옮겨 둬”)에 따른 배치. 결정문
[fsync2/VIEW_FRESHNESS_CONTRACT.md](./fsync2/VIEW_FRESHNESS_CONTRACT.md) · 대장 §34.

| 스테이징(`docs/` 안) | 적용 뒤 | 역할 |
| --- | --- | --- |
| `fsync2/patch_view_freshness.py` | — (도구) | F2 패처(훅 12개 · 사전 이미지 = **F1 적용 뒤** · `--check/--apply/--revert`) |
| `fsync2/test_view_freshness_contract.py` | `tests/test_view_freshness_contract.py` (신설) | 계약 시험 **10건**(C-1~C-8) |
| `fsync2/apply_flush2.sh` | — (도구) | 동결 exit 9 · 사전 이미지 exit 8 · 합성 순서 exit 6 · 자동 롤백 exit 5 |
| `fsync2/rehearse_flush2.sh` + `rehearsal-output.txt` | — (증거) | 미러 리허설 7시나리오(ALL PASS **21/21**) |
| `fsync2/probe_view_staleness.py` + `probe_view_throttle_benefit.py` (+ json) | — (증거) | mtime 결함 · 순진한 스로틸의 회귀 · 400턴 이득(1/8 · 재생 0) |

**한 줄**: *읽기는 늦추지 않는다 — 늦출 수 있는 것은 표시용 파일뿐이다.* 그리고 판정을 mtime 에서 **시퀀스**로
바꾸면서 **실제 결함 하나가 닫혔다**(복원된 옛 view + 새 mtime → 읽기가 커밋된 턴 2개를 놓쳤다).
**기본값은 현행(`immediate`)** 이므로 이 배치를 적용해도 켜기 전까지 동작은 그대로다.
**적용 순서**: **… → `FLUSH` → 게이트 재측정 → `FLUSH2` → 게이트 재측정 → 새 8시간 soak**.

### 1j. **배치 `FLUSH3` — sync 정책**(ADR 개정 **초안**까지 완료 · 본실행은 **ADR 승인 + `FLUSH`·`FLUSH2` 뒤** · 2026-09-17)

오너 지시(“sync 정책 batched 를 위한 ADR-DAT-02 §2 개정 초안을 … 리뷰 가능한 형태로”)에 따른 배치.
초안 [fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md](./fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md) · 대장 §35 ·
근거 `fsync3/probe-durability-output.json`. **ADR 본문에는 비규범 포인터 한 줄만** 넣었고 Status 는 `Proposed` 그대로다.

| 스테이징(`docs/` 안) | 적용 뒤 | 역할 |
| --- | --- | --- |
| `fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md` | ADR-DAT-02 §2 를 대체(승인 뒤) | 등급 셋·유실 창·관측·플랫폼 표·결정 D-F3-1~4·시험 후보 7건 |
| `fsync3/probe_durability_semantics.py` + `-output.json` | — (증거) | 등급별 비용 실측(88배·242 %) |

**실측이 뒤집은 것**: `cache`(`os.fsync`) 등급은 이미 **커밋당 예산의 2.74 %** 라 `batched` 로 0.59 % 를 만드는 것은
**약속을 바꿀 값을 못한다**(F2 와 같은 결론을 숫자가 확인). 반대로 `media`(`F_FULLFSYNC`)는 **242.5 %** 로
커밋마다 줄 수 없다 — 진짜 미디어 보장은 **핫패스 밖**에만 있다. 그래서 이 배치는 “배치를 넣는다”가 아니라
**등급·창·강등·관측을 정하는 배치**이고, 선행물은 **ADR 개정 승인**이다(코드가 약속을 앞지르지 않는다).

### 1k. **`FLUSH3` 의 배치 설계 — `media` 를 언제 부르는가**(D-F3-2 결정지 채움 · 2026-09-17)

오너 지시(“media 등급을 핫패스 밖에서만 돌리는 대안을 비용 모델과 함께 비교해서 D-F3-2 결정지를 채워줘”)에 따른
설계. 비용 모델·실측 [fsync4/MEDIA_OFFLOAD_COST_MODEL.md](./fsync4/MEDIA_OFFLOAD_COST_MODEL.md) · 대장 §36 ·
프로브 두 실행([a](./fsync4/probe-media-offload-run-a.json)/[b](./fsync4/probe-media-offload-run-b.json)) ·
계기·문서 계약 시험 **17건 passed**([test_media_offload_contract.py](./fsync4/test_media_offload_contract.py) — 계기 16 + 문서↔픽스처 대조 1). **코드는 안 썼다.**

| 스테이징(`docs/` 안) | 적용 뒤 | 역할 |
| --- | --- | --- |
| `fsync4/MEDIA_OFFLOAD_COST_MODEL.md` | — (설계) | 비용 모델·간섭 실측·대안 다섯·**D-F3-2 답** |
| `fsync4/probe_media_offload_cost.py` (+ run-a/b json) | — (증거) | 누적→호출 비용 · 유휴 호출 · 교차 설계 간섭 |
| `fsync4/test_media_offload_contract.py` | (설계라 적용 없음 — 계기 계약은 `docs/` 에 남는다) | 계기 계약 16건(음성 대조군 포함) + 문서↔픽스처 대조 1건 |

**왜 “단위”가 아니라 “언제”인가**: 주기 T초의 커밋당 상각은 T=10 s 에서 **예산의 0.044 %**, T=60 s 에서 0.0073 % 다 —
비용은 결정을 가르지 않는다. 대신 배경에서 부르면 **쓰는 쪽이 멈춘다**: 200 ms 주기에서 최대 **3.2 s** 밀림, 중앙 −2.2~−27.4 %,
밀림은 **100 % 진행 중인 호출과 겹쳤고**(기준선에서는 0건) **다른 파일이어도 멈췄다**. 그래서 답은
**대화별 옵트인 + 상한 `T_max` 가 있는 정지 감지**이고, 강행할 때는 **스톨을 관측에 남긴다**.
계약 시험 후보가 ⑦→**⑪** 로 늘었다(조용한 창·상한 강행·옵트인 격리·스톨 관측).

### 1l. **3차 배치 본실행 — 적용→커밋→게이트, 그리고 승격이 만든 두 결함**(2026-09-18)

이동 5건(`soak_watch.py`·`soak_watch_loop.py`·`soak_control.sh`·계약 시험 2종)은 `2026-09-17T12:12:11Z` 에
**적용 완료**됐고(sha256 동일 · 백업 `/tmp/nx10-promote3-backup-20260917T121211Z` · 승격 위치 게이트 A·B·C 초록
`18 passed in 258.71s`), 그 직후 **세션이 죽어 커밋이 남지 않았다**. 이어받아 닫은 것이 아래 셋이다.

| 커밋 | 무엇 | 왜 필요했나 |
| --- | --- | --- |
| `a1c6387f` | 승격 커밋(인덱스에 스테이징된 채 남아 있던 그대로) | `clean-machine-runtime` 이 `--ref HEAD` 를 쓰므로 커밋 없이는 후보가 아니다 |
| `8d762c3e` | 호출자 경로 수정 + 계약 시험 7건 | 승격은 `mv` 인데 체인 4개가 **없는 문서 사본**을 부르고 있었다 — 배치 체인이면 **4개 배치를 다 적용한 뒤 재장전에서** 터진다 |
| `22d653c9` | 승격된 감시 도구의 타입 정리 + **승격 게이트 C 에 basedpyright 추가** | 승격이 파일을 `scripts/` 로 옮기면 필수 게이트가 그 파일을 검사한다 — 실제로 `28 errors` 로 빨개졌다 |

**교훈**: 승격의 완료 조건은 “옮겼다”가 아니라 **“부르는 쪽이 살고 검사도 통과한다”** 다. 그래서 이번에
① 호출자 경로를 계약 시험으로 메고 ② 승격 게이트가 **필수 게이트와 같은 명령**(ruff·basedpyright)을
미리 돌리게 했다(빨강이 승격 **전에** 나오도록). 전체 근거: 대장 §38 · handoff §28.

### 1m. 다음 배치 후보 `SC6b` — 판정의 입력을 리포트에 남긴다 (2026-09-18)

새 SC-6 기준을 **기록된 실제 실행**에 다시 물린 결과(대장 §39)가 이 후보를 만들었다: 기준은 실제 자료에서
옳게 갈렸지만(누수 fail · 건강 pass · 리허설 판정 불가), 리포트가 **표본 시각(`sample_times_s`)과 반복
(`sample_ops`)을 남기지 않아** 창 경계를 시간 모델로 세워야 했다(±20% 흔들어 판정 유지 확인).

| 훅 | 내용 | 계약 시험(후보) |
| --- | --- | --- |
| 1 | 하네스 `scenario_soak` 이 `sample_ops`·`sample_times_s` 를 리포트에 쓴다(`rss_samples_mb` 와 같은 길이) | ① 두 필드가 리포트에 있다 ② 세 목록의 길이가 같다 |
| 2 | 판정 함수가 그 두 필드를 **그대로** 쓰도록 유지(시간 모델 불필요) | ③ 그 두 필드만으로 같은 판정이 재현된다 |

`src/` 가 아니라 `scripts/` 만 움직이므로 작지만, **지문 대상**이다 — 도는 배치 체인이 끝난 뒤 다음 창에서.

### 1b. 다음 승격 후보 (동결 해제 뒤 — 2026-09-17 추가)

| 스테이징(지금 `docs/` 안) | 승격 위치(안) | 역할 | 왜 승격해야 하는가 |
| --- | --- | --- | --- |
| `nx01/restore_rehearsal.py` | `tests/test_restore_rehearsal_contract.py`(+ 필요하면 `scripts/`) | restore 절차 판정부(왕복·최신 변경 손실 방지·멱등·삭제 거절) | 제품에 import/restore API 가 없어 **안전성이 절차에만** 있다. 지금은 `docs/` 라 어느 게이트도 이 판정식을 지키지 않는다 — 규칙이 낡으면 아무도 모른다(§2 의 구멍과 같다) |
| `nx01/restore-rehearsal-output.txt` | `tests/` 승격 뒤에는 raw artifact 로 `docs/` 에 남긴다 | 판정 근거(경계 4 + 이빨 1) | 러너·판정기 승격 때와 같다 |
| `nx03/rollback_rehearsal.py` | `tests/test_rollback_generation_contract.py` | 구버전 판을 그림자 트리로 돌려 되돌림 창의 노출과 **복귀 뒤 거절**을 재는 리허설 | NX-03 의 유일한 남은 항목이던 “실리허설 미실시”를 닫은 증거다. 삭제·도구와 가장 가까운 계약인데 지금은 `docs/` 라 안 지켜진다 |
| `nx03/rollback-rehearsal-output.txt` | raw artifact 로 `docs/` 유지 | 판정 근거(경계 3) | 위와 같다 |
| `nx10/soak_watch.py` | `scripts/soak_watch.py` + hermetic 계약 시험 | 돌고 있는 soak 의 조기 경보(멈춤·cap 투영·RSS 외삽·처리량 하한) | 회수 도구는 **끝나야** 판정하므로 오늘 두 실패를 조기에 못 잡았다. 경보 판정식이 낡으면 아무도 모른다 — 자기시험을 `tests/` 계약으로 올려야 지켜진다 |
| `nx10/soak_watch_loop.py` | `tests/test_soak_watch_view_contract.py`(그림·배지 계약) | 표본 적재 + **자기 새로고침 HTML** 추세 화면(화면이 조용히 틀리는 것을 막는다) | 지금은 `docs/` 라 그림·배지 회귀를 아무도 안 본다. 자기시험 9/9 를 계약으로 올린다 |
| `nx10/analyze_sc6_criterion.py` | `scripts/analyze_sc6_criterion.py` + `tests/test_sc6_criterion_analysis_contract.py` | SC-6 기준 **재설계의 근거 산출기**(워밍업 창 감도 · 모델 분산 · 창 잡음 · 반복당 환산) | 기준을 바꾸는 근거가 `docs/` 에만 있으면, 기준을 바꿀 때마다 같은 분석을 다시 손으로 한다(오늘 “30 MB 순간 최고치” 같은 거짓 결론이 그 비용이었다). 승격하면 §1b 의 1e 배치와 같이 가고, **기준 구현(`scripts/val02_staging.py`) 변경의 계약 시험과 쌍**을 이룬다 — 근거 산출기와 판정기가 같은 정의를 쓰는지 시험이 지킨다 |

**아직 카드로만 남긴 것(동결 해제 뒤 손대며, 지금 바이트를 바꾸면 검증이 무효가 된다)**

- `soak_control.sh` 의 `status` 가 **자기 셀프테스트 픽스처**를 “고아 예약”으로 보고한다(실측 2026-09-17 · 대장 §25-7) — 뿌리 pid 의 명령줄·수명을 함께 보고 셀프테스트 픽스처는 제외.
- `soak_watch.py` 의 후보 선택을 **감시 중인 workdir 기준**으로 좁힌다(대장 §25-9) — 하네스는 `--workdir` 로 뜨므로 다른 workdir 의 같은 이름 프로세스(리허설 처리량 프루브)가 계열에 섞이는 것을 막는다. 계약 시험은 “첫 표본에서 남의 workdir 을 채택하지 않는다”를 고정.
- 기준 변경 뒤 **리포트 크기** 확인(대장 §26-4) — `rss_samples_mb` 는 50 반복마다 쌓이므로 처리량 600회/초 × 8시간이면 그 필드만 ~2 MB 다.

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
