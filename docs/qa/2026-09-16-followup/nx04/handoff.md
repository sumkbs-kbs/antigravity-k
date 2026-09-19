---
title: NX-04 CAS 검증과 압축 검증의 분리 — 구현 인계
created: 2026-09-16
state: REVIEW (구현·시험 green, 독립 검토 대기)
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
depends_on: docs/qa/2026-09-16-followup/nx01/handoff.md, docs/qa/2026-09-16-followup/nx02/handoff.md
tags: [nx-04, test-contract, val02, handoff]
---

# NX-04 인계 기록 (구현 완료 / REVIEW)

```text
Task ID / attempt: NX-04 / attempt-001
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토 필요)
State: REVIEW — 판정식 분리·계측 분리 완료. 커밋하지 않았다.
Baseline full SHA: ffb0ebb312b76d86742d3e4065628a9704f8268e
Dirty paths (secret contents excluded): tests/test_val02_conversation_multiprocess.py(재작성),
  scripts/val02_staging.py(SC-2/SC-6), docs/qa/2026-09-16-followup/nx04/** (신규)
Scope / files / symbols: tests/test_val02_conversation_multiprocess.py(`_cas_worker`, `_run_race`, 5개 시험),
  scripts/val02_staging.py(`_sc2_worker`, `scenario_conversation_cas`, `scenario_soak`,
  `_conversation_soft_max`, `_journal_line_stats`, 상수 ORIGINALS_REPLAY_MAX_BYTES/SOAK_CONSTRAINT_TEXT).
Preconditions / dependency evidence: NX-01/NX-02 저장 계약(원본 journal = 정본 계수 기준).
  nx01/regression.txt 40행(옛 계약의 비결정 실패), nx02/regression.txt(같은 실패 재관측).
Observed failure before / exact reproduction: before.md §3~4 — HEAD 테스트 파일은 단독/경량 배치에서
  통과하고 대형 스윗에서만 실패(비결정). 같은 저장 결과를 옛 판정식으로 채점하면 결정적으로 재현:
  유실 0건(원본 120/120)인데 옛 판정식은 58건 유실로 주장(FALSE POSITIVE).
Change and invariant: 한 assertion 에서 CAS 계약과 압축 계약을 섞지 않는다.
  (a) CAS: 성공 message id 집합 = 저장(원본/view) 집합, 거절 id 는 미저장, revision = 성공 수.
  (b) 압축: view ≤ cap, 압축 세대 ≥ 1, 원본은 성공 수와 정확히 일치(유실 0).
  cap0(압축 끔)과 cap64(제품 기본)를 **두 구성으로 분리**해 각각 검증한다. 제품 설정은 우회하지 않는다.
Commands / cwd / exit codes / environment: commands.txt, regression.txt (cwd = 레포 루트).
Runtime expected vs observed: after.md §1~6. 드라이버 exit 0(PASS), SC-2 pass=true,
  SC-6 은 NX-04 필드 전부 통과 + pass=false 는 환경(prunable worktree 1건).
Regression results / raw log paths / hashes: regression.txt
  - tests/test_val02_conversation_multiprocess.py 14 passed (5회 반복 안정: 14 passed ×5)
  - 관련 6파일 61 passed
  - ruff All checks passed!
  - 전체 스위트 6459 passed / 9 skipped (NX-04 이전 6448, +11 = val02 계약 분리·seed 반복)
    — 전체 스위트 안에서도 옛 비결정 실패가 재발하지 않음
Data migration / backup / rollback observed: 데이터 변경 없음(시험·계측 계약만 수정).
  rollback = 이 파일을 HEAD 버전으로 되돌리면 옛 판정식으로 복귀하며, 그 경우 비결정 실패가 재발한다.
Unverified / reason / impact: (1) ~~8h soak 의 `stream_line_count` 경로는 실측 규모에서 미실행~~ →
  **2026-09-17 정정: 경로가 처음 실행됐고 통과했다**(꼬리 창 수정 뒤 10분 하네스 실행의 journal 94.1 MB 가
  임계 32 MiB 를 넘어 `conversation_originals_verification=stream_line_count` · `replay_deferred=True` ·
  `journal_lines=269,088` · `terminated=True` · `originals_complete=True`). 남은 미검증은 **시간 규모**뿐이다:
  이 실측은 10분 실행이므로 ”8시간 보고서의 그 필드”는 지금 도는 8시간 soak(종료 예정 2026-09-17 18:19 KST)이
  닫는다. 근거: [../nx10/SOAK_8H_FINDINGS.md §5·§6](../nx10/SOAK_8H_FINDINGS.md) ·
  [../nx10/GATE_LEDGER.md §16-1](../nx10/GATE_LEDGER.md). 아래 20초 리허설 기록은 그대로 보존한다. (2) SC-6 의 `orphan_worktrees` 는 저장소 전역 상태를 읽으므로
  공유 체크아웃에서는 다른 작업이 남긴 prunable worktree 때문에 pass 가 막힌다(이번 카드에서 prune 하지 않음).
  (3) 성능 수치는 10회 반복의 median/max 만 보고하며 절대 상한을 주장하지 않는다.
Reviewer verdict / reviewed SHA / artifact: 미지정 — 독립 검토 필요.
Next owner / exact next action: NX-05(인증 폐기)·NX-06(readiness)·NX-07(문서 정합성)·NX-08(영속화 의혹) 중
  19번 체크리스트 순서대로 진행. NX-10 전에는 NX-04 의 cap64 결정적 시험과 SC-2/SC-6 필드를 그대로 사용한다.
```

## 1. 왜 "판정식"이 결함이었는가

`appended`(성공 append 수)와 `len(view.messages)`(cap64 로 압축된 view)는 서로 다른 것을 센다.
성공이 64를 넘으면 둘은 필연적으로 벌어지므로, 옛 단언 `final_count >= appended` 는
**정상 압축을 유실로 보고**한다. 반대로 성공이 64 미만이면 결함이 보이지 않는다 → 비결정.

NX-02 가 정본 계수 기준(journal 원본)을 만들었으므로 이제 두 계약을 각각 셀 수 있다.
이 카드는 그 분리를 시험·staging 계약에 반영한 것이다.

## 2. 시험 ↔ 카드 수용 조건 매핑

| 카드 절차/수용 | 구현 |
|---|---|
| 1) cap0 CAS만 검증 (성공 ID 집합 = 저장 ID 집합, rejected 미반영, revision = 성공) | `test_cap0_cas_success_set_is_exactly_the_stored_set` |
| 2) cap64 결정적 123 이상, 두 번 압축 보장 | `test_cap64_sequential_123_appends_compact_twice_without_loss`(세대 ≥ 2), 드라이버 10 seed(세대 = 2 고정) |
| 3) multiprocess barrier + bounded retry + 종료/timeout 명시 | `_run_race`(spawn + Barrier(workers), `join(timeout=120)`, worker 당 `max_attempts`, 종료 코드 검사) |
| 4) 원본 exact set/순서 vs view bound 분리 | 위 두 시험 + `original_ids_in_order`(드라이버) |
| 5) SC-6 원본/제약 보존 + 업무량·계측 overhead 기록 | `scenario_soak` 의 `conversation_originals*`, `conversation_constraint_preserved`, `measurement_overhead_s/ratio`, `completed_ops` |
| 수용: CAS 유실과 정상 압축이 별도 결과로 식별 | SC-2 `lost_originals` vs `view_bounded`/`compaction_generations`, 시험의 (a)/(b) 단언 분리 |
| 수용: 10회 고정 seed 반복 동일 불변식 | `test_seed_fixed_repetition_keeps_invariants[0..9]` + 드라이버 `seeded_repetitions` |
| 수용: 성능 수치는 반복 수와 함께 보고 | 드라이버 `elapsed_s[]`/median/max, SC-2 `attempts`/`stale_rejected` |

## 3. 금지 사항 준수 확인

- assertion 삭제: 옛 계약의 두 성질(침묵 덮어쓰기 0 / stale 은 명시적 거절)은 **더 강한 형태로** 남아 있다.
- 하한 0 완화: 성공 하한은 오히려 123 으로 올렸고, `pass` 조건에 `revision == 성공 수`를 추가했다.
- cap 무한 고정으로 제품 설정 회피: cap64(제품 기본)를 별도 시험이 검증하며, cap0 은 CAS 단독 관측용
  두 번째 구성이다(둘 다 보고된다).
- 무관한 과거 fail 수치를 성공에 합산: SC-2/SC-6 는 각 실행의 시나리오 결과만 담고, 이전 실행 수치는
  증거 문서(regression.txt/before.md)에만 인용한다.

## 4. 잔여 위험

- **SC-6 gate 는 공유 체크아웃에서 통과할 수 없다**: `orphan_worktrees` 가 `git worktree list` 의
  prunable 항목을 세는데, 다른 작업 스트림의 `/private/tmp/ssak-runner-gates.ENbZhm/checkout` 이
  잡힌다. 이 카드에서 `git worktree prune` 을 실행하지 않았다(파괴적·타 작업 소유 가능).
  NX-06(readiness) 또는 NX-10 전에 소유자가 정리하거나, "이 실행이 만든 worktree" 만 세도록
  좁히는 결정이 필요하다. **주장을 약화시키기 위해 검사를 삭제하지 않았다.**
- `stream_line_count` 검증 경로는 **2026-09-17 처음 실행·통과**했다(94.1 MB journal, 위 §Unverified). 남은 것은
  실측 **시간 규모**(10분 → 8시간)의 확인뿐이며 2026-09-17 18:19 KST 종료 예정인 8시간 soak 이 닫는다.
  그 전까지는 “8h 보고서에서 확인됨”이라고 쓰지 않는다.
- 시험은 `pytest -p no:randomly` 로 확인했다. 기본 addopts(랜덤 순서)에서도 파일 단독 5회 반복은 안정적이나,
  전 스위트에서의 반복 안정성은 1회만 확인했다.
