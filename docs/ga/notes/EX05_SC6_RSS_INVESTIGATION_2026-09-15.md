---
title: EX-05 SC-6 RSS investigation
date: 2026-09-15
tz: Asia/Seoul
status: DIAGNOSIS
ex: EX-05
evidence: .omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/val02_soak_28800.json
---

# EX-05 SC-6 RSS 조사 (2026-09-15)

## 요약

8h soak **FAIL**은 SC-6만: `rss_growth_mb=1654.9` ≫ threshold `64`. 오류·FD·orphan worktree는 전부 정상. **CR-14 NO-GO 유지.** 임계값(64MB)은 Decision Log 없이 올리지 않음.

## SC-6 루프가 메모리에 남기는 것 (`scripts/val02_staging.py::scenario_soak`)

1. **단일 conversation에 unbounded append** — `conversation_id="soak-conv"`에 매 루프 `conv_store.append(...)` (~150554회). revision만 증가, prune/rotate 없음.
2. **TaskStateStore** — 매 루프 `create_task` + 2 transitions (~150k tasks in soak.db).
3. **Harness sample lists** — `rss_samples` / `fd_samples` every 50 ops → ~3011 floats/ints. 수십 KB 수준 → **1654MB의 원인이 될 수 없음**.
4. **반환 JSON**에 `rss_samples_mb` 전체 배열 포함(디스크; 프로세스 RSS와 별개이나 harness가 샘플을 끝까지 보유).

## 가설 순위

| Rank | Hypothesis | 설명 | 예상 기여 |
|:---:|:---|:---|:---|
| **1 (a)** | **측정 워크로드 = 의도적 conversation 성장** | 한 conversation에 8시간 동안 무한 append. 제품 `ConversationStore`가 메시지 전체를 유지/로드하면 RSS 성장은 **기대 동작**에 가깝다 (measurement artifact vs “leak” 경계). | **주 원인 (매우 유력)** |
| 2 (c) | **제품 쪽 누수/비한정 캐시** | Task DB 행, ORM/캐시, event log, 메시지 리스트를 메모리에 누적. (a)와 겹침 — store가 디스크만 쓰면 RSS는 훨씬 작아야 함. | 중~고 (제품 설계 확인 필요) |
| 3 (b) | **Harness sample 배열** | 3011개 float ≈ 무시 가능. | **기각** |

## Harness artifact vs product leak

- Soak는 **의도적으로** 한 conversation에 영원히 append한다 → 제품이 “장기 conversation을 메모리에 전부 유지”하면 RSS 폭증은 **시나리오가 만든 부하**.
- **Harness**: conversation을 주기적으로 rotate/새 ID로 바꾸거나 prune하여 **bounded retention** 시나리오로 바꾸면 “진짜 누수”만 남는다.
- **Product**: 상용 경로에서 unbounded conversation을 prune/페이지해야 한다면 제품 수정이 맞다.
- **64MB threshold를 이 워크로드에 맞게 올리는 것은 Decision Log + 사용자 승인 없이는 금지.**

## 권장 다음 조치

1. **결정 필요 (사용자)**: (A) “unbounded chat에서도 RSS≤64MB” (제품 책임) vs (B) “steady-state bounded load에서 누수 없음” (시나리오 수정).
2. **단기 재현 (5–10분)**:
   ```bash
   uv run --no-sync python scripts/val02_staging.py \
     --scenarios SC-6 --soak-seconds 600 \
     --workdir .omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/workdir/rss_probe_10m \
     --output .omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/val02_soak_600_probe.json
   ```
3. **Harness-safe 최소 수정 (결정 B)**: N append마다 새 `conversation_id`; sample list는 rolling window. **threshold 미변경.**
4. **제품 조사 (결정 A)**: `ConversationStore.append/get` 메모리 보유, task store index, 관련 캐시 → prune/페이지 정책.

## 참고

- Desktop packaging remains paused (D-09).
- Soak watch routine paused after EX-05 finished.

## ConversationStore 코드 확인 (추가)

`src/antigravity_k/engine/conversation_store.py`:
- `append`는 레코드를 로드한 뒤 `record.messages.append(...)`로 **전체 메시지 리스트를 메모리에 유지**한 채 JSON으로 다시 저장.
- `compact`/요약 prune API는 있으나 **SC-6 soak는 호출하지 않음**.
- 따라서 ~15만 메시지를 한 conversation에 쌓으면 RSS 폭증은 **제품이 전체 히스토리를 메모리에 올리는 설계 + harness의 unbounded append**가 맞물린 결과.
