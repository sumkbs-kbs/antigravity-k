# EX-05 승격 충돌 — 오너 판정 브리프

작성: 2026-09-16 · 발견: NX-10 게이트 측정 중(교차 레인) · 판정자: **출시 책임자**(이 저장소에서 GO 를
선언할 수 있는 유일한 주체). 이 문서는 **결정을 내리지 않는다** — 결정에 필요한 사실·증거·수리안만 놓는다.

## 1. 한 문장 요약

`docs/ga/CR14_EX_EXECUTION_LEDGER.md` 에서 **EX-05 가 상태 셀에서는 `PASS` 이고, 같은 문서의 본문에서는
`DONE 아님`** 이다. 두 진술이 서로 반대이고, 어느 쪽이 맞는지는 문서 안의 증거만으로는 정해지지 않는다.

## 2. 무엇이 바뀌었나 (커밋 `20d529fc`, 이 카드의 변경이 아니다)

`docs(cr14): record EX-05 PASS after Decision A 8h resoake` (`docs/17…` 6줄, `docs/ga/CR14_EX…` 24줄).

**상태 셀 (변경 전 → 변경 후):**

```
-| EX-05 | 8h soak | **IN_PROGRESS** (resoake after Decision A; prior run **FAIL**) | … prior run **FAIL** … |
+| EX-05 | 8h soak | **PASS** (resoake Decision A) | prior FAIL retained · resoake run28800e · all_pass: true · SC-1..6 PASS · SC-6 rss_growth_mb=48.7 (<64) · … |
```

**같은 커밋이 문서에 함께 추가한 두 진술 (서로 반대):**

- (국문 절) “**이 결과로 EX-05 를 DONE 으로 올리지 않는다.** ④ 가 남아 있다” ·
  “2026-09-16: … **EX-05 는 DONE 아님**”
- (영문 절) “## EX-05 resoake result … — **PASS**” · “`all_pass: true`. SC-1..SC-6 all `pass: true`.”

영문 절은 “Do not claim GO from EX-05 alone” 이라고 스스로 한정하지만, **상태 셀은 그 한정을 담지
않는다** — 그래서 문서를 위에서 훑는 독자(게이트·지원표·판정 문서)에게는 EX-05 가 PASS 로 보인다.

## 3. 증거는 4단계로 나뉜다 (섞으면 안 된다)

| 단계 | 내용 | 증거 | 상태 |
|---|---|---|---|
| ① 1차 8시간 | **FAIL** — RSS `~66.8 → 1721.8 MB`(`rss_growth_mb=1654.9` ≫ 64) | 원본 보존 | 확정 |
| ② 교정 | Decision A: soft-max auto-compact 64(`78012f4a`), **임계값은 올리지 않음** | 커밋 | 확정 |
| ③ 재soak | **JSON 지표 PASS** — `duration_s=28801.318` · ops/revision 12,102,886 · 최종 view 26 · RSS `65.7 → 114.4`(+48.7) · `errors=0` · `fd_growth=0` · `orphan_worktrees=0` · `all_pass: true` | [soak-summary.json](../soak-summary.json) · 원본 JSON | 확정 |
| ④ 종료·귀속 | 래퍼 로그 마지막 줄 `finished exit:141`(원문 명령 미보존) → **INCONCLUSIVE** · 재soak 이 어느 후보 트리에서 돌았는지 **UNVERIFIED** | [soak-summary.json](../soak-summary.json) 필드 **그대로**: `wrapper_log_exit: 141`, `run_sha_binding: "UNVERIFIED"` · [nx00/handoff.md](../nx00/handoff.md) §2 | **미확정** |

즉 `PASS` 라고 쓸 수 있는 것은 **③의 지표**이고, **④는 지표가 아니라 귀속 문제**라서 ③이 ④를
닫지 않는다. NX-00 의 상태 줄도 같은 구분을 쓴다: “지표 재확인 DONE / **종료·후보 귀속 INCONCLUSIVE**”.

## 4. 현재 기계적 결과 (추측이 아니라 실행 결과)

```
tests/test_nx07_doc_consistency.py::test_soak_phases_stay_separated
  AssertionError: EX-05 상태 셀이 종료·귀속 미확정(INCONCLUSIVE)을 말하지 않는다
tests/test_nx07_doc_consistency.py::test_teeth_soak_done_promotion_is_detected
  AssertionError: 기준선이 이미 위반이다
```

NX-07 계약(`soak_phase_violations`)이 요구하는 것은 세 가지뿐이다 — ① 현재 상태 문서에 soak 단계
표식이 있다(`docs/20` §3, 통과). ② EX-05 상태 셀이 “귀속이 미확정”임을 말한다(**현재 실패**).
③ 대장에 `UNVERIFIED` 가 있다(통과). 계약은 “PASS 라고 쓰지 마라”가 아니라 **”PASS 라고 쓰면서
귀속이 미확정이라는 사실을 지우지 마라”** 이다.

**중요 — 이 2건은 게이트 수치에 보이지 않는다.** `python-tests` 게이트가 `not_run` 이라
`GATE_LEDGER.md` 의 “18 passed / 0 failed”에는 드러나지 않는다. 카드 §수용이 not_run 0을 요구하는
이유가 이 지점이다(대장만 보면 놓친다).

## 5. 선택지

| # | 선택 | 무엇을 주장하는가 | 필요한 것 | 평가 |
|---|---|---|---|---|
| **B (권고)** | 상태 셀을 **자격 한정**으로 고친다: `**PASS(JSON 지표)**` + 종료·귀속 `INCONCLUSIVE` 명시 | “지표는 PASS, 판정 근거(귀속)는 아직 아니다” | 아래 §6 수리안 1줄 | **지금 증거로 정확하다.** CR-14 레인의 지표 주장도 지우지 않는다 |
| A | ④를 증거로 닫고 상태를 **DONE/PASS** 로 승격 | “재soak 은 특정 후보의 것이고 정상 종료했다” | 실행 명령 원문 · 시작/종료 지문 · exit 보존 · 후보 SHA 귀속. **현재는 없음**(NX-00 이 복구 불가로 종결) → 사실상 **새 soak(= NX-10 전용 창의 SC-1~6 28,800s)** 이 필요 | 옳은 방향이지만 **지금은 증거가 없다** |
| C | `IN_PROGRESS` 로 되돌린다 | “③ 지표 PASS 도 아직 승격 아님” | 커밋 되돌리기(타 레인 작업 취소) | 지표 PASS 라는 사실까지 지운다 — 과잉 |

**권고: B.** 이유는 하나다 — 서로 다른 두 단계(지표 vs 귀속)를 한 칸에 넣으려 해서 충돌이 생겼고,
B 는 그 둘을 **한 칸 안에서 분리**한다. A 는 B 를 먼저 적용해도 손해가 없다(④가 닫히면 셀에서
`INCONCLUSIVE` 를 떼면 된다).

## 6. 정확한 수리안 (오너가 적용할 1줄 + 확인)

현재 셀:

```
| EX-05 | 8h soak | **PASS** (resoake Decision A) | prior FAIL retained · resoake `run28800e` · …
```

수리안(권고 B) — 셀에 두 단계를 병기하고 귀속 상태를 남긴다:

```
| EX-05 | 8h soak | **PASS(JSON 지표)** / 종료·귀속 **INCONCLUSIVE**(`run_sha_binding: UNVERIFIED`, `wrapper_log_exit: 141`) — DONE 아님 | prior FAIL retained · resoake `run28800e` · `all_pass: true` · SC-1..6 PASS · SC-6 rss_growth_mb=**48.7** (<64) · duration≈28801s · JSON `…/val02_soak_28800_resoake.json` (~2026-09-15 23:08 KST) |
```

확인 명령(적용 후 초록이어야 한다):

```bash
uv run --isolated --frozen --extra dev --extra rag --extra documents pytest \
  tests/test_nx07_doc_consistency.py -q --tb=short      # 두 계약이 통과해야 한다
```

**하지 말아야 할 것:** 계약 테스트를 약화·삭제해 초록으로 만드는 것(그러면 “지표와 귀속을 섞지
않는다”는 보호가 사라진다), 그리고 ④를 닫지 않은 채 `DONE` 을 쓰는 것. ④의 진짜 해소는
NX-10 전용 창의 새 soak이며, 그때는 **시작/종료 지문 + exit 코드를 파일로 보존**해야 한다
([GATE_LEDGER.md](GATE_LEDGER.md) §2 not_run 목록 · [handoff.md](handoff.md) §5).

## 7. 이 브리프가 하지 않은 일

- `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 를 **고치지 않았다**(타 레인 소유 문서, 오너 판정 사항).
- NX-07 계약 테스트를 **약화하지 않았다**(실패는 그대로 남겨 두었다 — 숨기지 않는다).
- EX-05 의 ③(JSON 지표 PASS)을 **부정하지 않는다**. 재soak 의 지표가 좋다는 사실과 그 실행이
  어느 후보의 것인지 안다는 사실은 다른 주장이다.
