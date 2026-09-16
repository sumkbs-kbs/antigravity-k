---
title: NX-04 before (HEAD ffb0ebb3, CAS와 압축을 한 assertion 으로 채점)
created: 2026-09-16
tags: [nx-04, before, evidence]
---

# NX-04 before — 옛 판정식이 만든 두 가지 오류

## 1. 계약 원문 (HEAD)

`git show HEAD:tests/test_val02_conversation_multiprocess.py` 의 최종 단언:

```python
final = ConversationStore(storage_dir).get(project_id="proj", conversation_id="conv")
final_count = len(final.messages) if final else 0      # ← 압축된 view 를 계수 기준으로 사용
...
assert errors == 0, "F1 재발: tmp 파일 경합으로 append가 실패했다"
assert final_count >= appended, (
    f"F2 재발: append 성공 {appended}건 중 {appended - final_count}건이 침묵 덮어쓰기로 유실됐다"
)
```

문제는 두 가지다.

- **false positive(오탐):** `appended` 는 성공 append 수인데 `final_count` 는 cap64 로 **압축된 view**
  크기다. 성공이 64를 넘으면 유효한 저장이 "침묵 덮어쓰기로 유실" 로 보고된다.
- **비결정성:** 성공 수가 64 미만이면 같은 결함이 통과한다. 즉 판정이 스케줄링(부하)에 좌우된다.

## 2. 실제 관측된 실패 (기록)

| 출처 | 관측 |
|---|---|
| [nx01/regression.txt](../nx01/regression.txt) (NX-01 시점, HEAD 모듈로도 동일) | 단독 실행 5/5 통과, **대형 `-k` 스윗 안에서는 FAIL** — `append 성공 85건 중 58건이 침묵 덮어쓰기로 유실됐다 / assert 27 >= 85` |
| NX-02 전체 스위트 실행(`nx02/regression.txt` 의 6448 이전 실행) | `append 성공 99건 중 58건이 침묵 덮어쓰기로 유실됐다 / assert 41 >= 99` |

## 3. HEAD 테스트 파일을 그대로 다시 돌린 관측 (2026-09-16)

```sh
git show HEAD:tests/test_val02_conversation_multiprocess.py > /tmp/nx04-before/test_val02_old.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest /tmp/nx04-before/test_val02_old.py -q -p no:randomly
# → 3 passed (5회 반복 모두 통과)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_conversation_store_soft_max_rss.py tests/test_conversation_store_ctx01.py \
  tests/test_fr_context_end_to_end.py tests/test_obs01_operational_metrics.py \
  /tmp/nx04-before/test_val02_old.py -q -p no:randomly
# → 34 passed (3회 반복 모두 통과)
```

즉 가벼운 조건에서는 **결함이 숨어 있고**, 부하가 걸린 대형 스윗에서만 드러난다. 이것이 카드가
말한 "비결정적 검사" 그 자체다. HEAD 파일만으로는 안정적인 재현이 불가능하므로,
결함을 **판정식 수준에서 결정적으로** 재현했다(§4).

## 4. 결정적 재현 — 같은 저장 결과를 두 판정식으로 채점

드라이버 [`repro_nx04_cas_vs_compaction.py`](repro_nx04_cas_vs_compaction.py) 는 순차 결정적 부하
(cap64, 120 append) 하나를 만들고 그 **동일한 관측**을 옛 판정식과 새 판정식으로 각각 채점한다.

```json
"observation": {"soft_max": 64, "successes": 120, "view_messages": 62, "originals": 120,
                "revision": 120, "compaction_generations": 1, "constraint_preserved": true}
"old": {"judge": "old(view_count >= successes)", "claimed_lost_messages": 58, "verdict": "FAIL"}
"new": {"judge": "new(cas+compaction split)",
        "cas": {"originals_lost": 0, "revision_matches_successes": true, "originals_in_order": true},
        "compaction": {"view_bounded": true, "generations": 1, "compaction_observed": true},
        "verdict": "PASS"}
```

유실은 **0건**(원본 120/120, revision 120)인데 옛 판정식은 58건을 유실로 주장한다.
수정 대상은 제품 코드가 아니라 **판정식**이다.
