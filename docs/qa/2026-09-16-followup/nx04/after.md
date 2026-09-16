---
title: NX-04 after (CAS/압축 판정 분리 + 10회 seed 고정)
created: 2026-09-16
tags: [nx-04, after, evidence]
---

# NX-04 after — 분리된 판정식의 관측값

원본 출력: [`after-run-output.json.txt`](after-run-output.json.txt),
SC-2 [`staging-sc2.json`](staging-sc2.json), SC-6 [`staging-sc6.json`](staging-sc6.json),
테스트 [`tests/test_val02_conversation_multiprocess.py`](../../../../tests/test_val02_conversation_multiprocess.py) (14 passed).

## 1. 판정식 분리 (드라이버, 순차 결정적 부하)

| 항목 | 값 |
|---|---|
| 부하 | cap64(제품 기본), 순차 120 append |
| 옛 판정식 | `claimed_lost_messages: 58` → **FAIL(오탐)** |
| 새 판정식 CAS | `originals_lost: 0`, `revision_matches_successes: true`, `originals_in_order: true` |
| 새 판정식 압축 | `view_bounded: true`(62 ≤ 64), `generations: 1`, `compaction_observed: true` |
| 결론 | 같은 저장 결과가 압축과 유실로 **분리 보고**된다 → PASS |

## 2. 두 번째 구성(cap0) — CAS 만 보는 계약

| 항목 | 값 |
|---|---|
| 부하 | cap0(압축 끔), 순차 20 append |
| CAS | `originals_lost: 0`, `revision_matches_successes: true` |
| 압축 | `compaction_enabled: false`, `generations: 0`, `no_compaction_as_configured: true` |
| 결론 | PASS. cap0 은 제품 기본값을 숨기기 위한 것이 아니라 CAS 계약을 단독 관측하는 명시적 두 번째 구성이다 |

## 3. 고정 seed 10회 반복 (cap64, 123 append)

| 항목 | 값 |
|---|---|
| 반복 | 10회, `random.Random(seed)` 로 role/본문만 고정 |
| 판정 | 10/10 PASS, **압축 세대 = 2회**(매 반복 동일) |
| 소요(반복별 보고) | median 0.152s / max 0.158s, 807 appends/s (중앙값) |
| 의미 보존 | 매 반복 `constraint_preserved: true` (초기 제약이 두 번의 압축을 넘겨 유지) |

성능 수치는 반복 수와 함께 보고하며 "완전 무결"을 주장하지 않는다(카드 수용 조건).

## 4. 테스트 계약 (`tests/test_val02_conversation_multiprocess.py`, 14 passed)

| 시험 | cap | 관측 |
|---|---|---|
| `test_cap0_cas_success_set_is_exactly_the_stored_set` | 0 | 4 worker × 8 성공 = 32, stale 거절 > 0, 저장 ID 집합 = 성공 ID 집합, 거절 ID ∩ 저장 = ∅, revision = 32, 압축 0회 |
| `test_cap0_stale_loser_gets_explicit_conflict_not_silent_success` | 0 | stale 는 `StaleConversationRevisionError`(context `current_revision`=2)로 거절 |
| `test_cap64_sequential_123_appends_compact_twice_without_loss` | 64 | 압축 세대 ≥ 2, 원본 ID/본문 123/123 순서 일치, view ≤ 64, revision 123 |
| `test_cap64_multiprocess_distinguishes_loss_from_compaction` | 64 | 6 worker × 25턴 bounded retry: 성공 ≥ 123, 원본 = 성공 집합, 거절 ID 미저장, view ≤ 64, 압축 세대 ≥ 1, revision = 성공 수 |
| `test_seed_fixed_repetition_keeps_invariants[0..9]` | 64 | 10회 반복 모두 같은 불변식 + 초기 제약 유지 |

multiprocess 는 `spawn` + `Barrier`, `join(timeout=120)`, 종료 코드 검사, worker 당
`max_attempts` 상한(bounded retry)을 명시한다. `errors == 0` 이므로 F1(tmp 파일 경합) 재발도 없다.

## 5. SC-2 (staging, cap64)

```json
{"workers": 6, "turns_per_worker": 25, "appended": 150, "stale_rejected": 299,
 "attempts": 449, "unexpected_errors": 0,
 "originals": 150, "lost_originals": 0, "missing_original_ids": [], "rejected_ids_stored": [],
 "view_messages": 34, "view_bounded": true, "compaction_generations": 2,
 "revision": 150, "revision_matches_successes": true, "pass": true}
```

- 옛 SC-2 는 `final_messages`(view) 와 `appended` 만 보고 `lost_messages` 를 계산했다 →
  지금은 **원본 기준 유실(`lost_originals`)** 과 **압축 관측(`view_bounded`/`compaction_generations`)** 을
  별도 필드로 보고한다.
- 거절된 ID 가 나중에 저장되지 않았음(`rejected_ids_stored: []`)과 누락 ID 없음(`missing_original_ids: []`)을 함께 본다.
- `pass` 조건에 `workers_alive_after_join == []`(명시적 종료)와 성공 ≥ 123 을 포함한다.

## 6. SC-6 (staging, 20초 리허설)

```json
{"conversation_revision": 1645, "conversation_originals": 1645,
 "conversation_originals_verification": "full_replay", "conversation_originals_replay_deferred": false,
 "conversation_journal_seq": 1645, "conversation_message_count": 21, "conversation_messages_bounded": true,
 "conversation_compaction_generations": 28, "conversation_constraint_preserved": true,
 "measurement_overhead_s": 0.0023, "measurement_overhead_ratio": 0.00012,
 "rss_growth_mb": 9.4, "fd_growth": 0, "errors": 0,
 "orphan_worktrees": 1, "db_accessible_after": true, "pass": false}
```

- bounded view(21)와 원본(1645)을 **각각** 보고한다. 압축 28세대 이후에도 초기 제약이 유지된다.
- 8h soak 처럼 journal 이 커지면 전수 replay 대신 **스트리밍 줄 수 검증**(`stream_line_count`)으로
  전환하고, 연기 사실을 `conversation_originals_replay_deferred`/`..._verification` 에 남긴다.
- 계측 overhead 를 실측해 보고한다(0.0023s / 20s = 0.012%).
- `pass: false` 의 원인은 **환경**이다: `orphan_worktrees: 1` — 다른 작업 스트림이 남긴
  prunable worktree(`/private/tmp/ssak-runner-gates.ENbZhm/checkout`)가 이 저장소의
  `git worktree list` 에 잡힌다. 이 카드에서 `git worktree prune` 을 실행하지 않았다(공유 체크아웃의
  다른 작업 소유일 수 있고, 파괴적 정리는 요청받지 않았다). NX-04 필드(원본/압축/의미/overhead)는 모두 통과다.
