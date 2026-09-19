# lh-001 BoN × AVO 감독축 조합 A/B 실험 리포트

> 실행일: 2026-08-25 · 타겟: `qwen3.8:latest`(27B, Ollama) · 케이스: `lh-001`(난이도 5, 장기 워크플로)
> 원본 데이터: `data/benchmarks/ab-r*.json` · 병합 요약: `data/benchmarks/bon-avo-ab-lh001-summary.json`

## 1. 목적과 가설

lh-001에서 문서화된 frontier 대비 +0.29 격차를 줄이기 위해, 두 증폭 메커니즘의 조합 효과를 분리 측정한다.

- **H1**: 실행 검증 Best-of-N(BoN) 단독으로 격차를 줄인다 (이전 실측 +0.217).
- **H2**: AVO 감독축(동일 시도 반복 차단·유사 오류 클러스터·무진행 윈도우 → STALL 전략수정 지시 주입)이 재시도의 질을 높인다.
- **H3**: 조합(bon_avo)이 단독보다 큰 효과를 낸다.

## 2. 실험 설계 (4팔)

| 팔 | 초기 답 생성 | 재시도 | 생성 상한(형평) |
|---|---|---|---|
| `cascade_off` (baseline) | 단일 생성 | 0 | 1회 |
| `bon_on` | 실행 검증 BoN(n=3, syntax 검증자, early-exit) | 0 | 3회 |
| `avo_on` | 단일 생성 | AVO 감독 예산 2 | ≤3회 |
| `bon_avo` | BoN + AVO 감독 예산 2 | ≤6회 | |

**AVO 감독축 구현** (`benchmark_harness._execute_single(supervised=True)`):
- 실패 결과를 `HarnessEnforcer.record_outcome()`에 적재 (오류 지문 = 누락 키워드/게이트 피드백)
- 무진행 윈도우·유사 오류 클러스터 임계 도달 시 1회용 STALL 전략수정 지시문을 feedback에 주입
- 짧은 예산(2회)에서도 축이 발화하도록 임계값 보정(window=2, cluster=2 — `simulate_stall_supervision.py`의 보정 원칙과 동일)
- 동일 실패 지문의 무개입 재시도에도 `build_stall_message` 주입

생성 횟수 형평: bon_on(≤3) vs avo_on(≤3). bon_avo만 최대 6회 — 조합 비용까지 측정하는 것이 목적.

## 3. 구현·검증

| 변경 | 파일 |
|---|---|
| AVO 모드 2종 추가(`avo_on`, `bon_avo`) + 예산 스왑/원복 | `engine/benchmark_harness.py` |
| `consume_pending_intervention()` 공개 API | `engine/harness_enforcer.py` |
| 임계값 생성자 오버라이드(`no_progress_window`, `error_cluster_threshold`) | `engine/harness_enforcer.py` |
| 다중 팔 `--modes` 지원 | `scripts/run_bon_ab_measurement.py` |
| 신규 테스트 3개 (개입 주입·예산 원복·조합 경로) | `tests/test_amplification_benchmark.py` |

검증: 관련 테스트 **88 passed**, ruff/mypy 0 오류.

## 4. 실행 결과

7회 baseline 관측 포함 전체:

| 팔 | n | mean | Δ vs baseline |
|---|---:|---:|---:|
| cascade_off | 3 | **1.000** | — |
| bon_on | 2 | **1.000** | ±0.000 |
| avo_on | 2 | **1.000** | ±0.000 |
| bon_avo | 2 | **1.000** | ±0.000 |

점수가 실질적인지 출력물 직접 검증: lh-001 단일 생성 결과 **9,800자**(아키텍처+Mermaid+체크포인트 설계),
필수 키워드 5/5 실제 커버(checkpoint/recovery/idempotency/rollback/retry). 가짜 만점 아님.

## 5. 해석 — 천장 효과 (Ceiling Effect)

**결론: qwen3.8에서 lh-001 격차는 더 이상 재현되지 않는다.**

1. 문서화된 +0.29/+0.273 격차는 qwen3.6 시대 측정치다. 현재 기본 타겟(qwen3.8 27B)은
   이 과제를 baseline 만점으로 해결한다.
2. 계측기(lh-001)가 포화되어 증폭 효과를 측정할 수 없다 — delta가 구조적으로 0으로 수렴.
3. 이전 실측(+0.2545, arc-001/lh-001)과 모순이 아니라 **모델 교체로 기준선이 올라간 것**.
   AMPLIFICATION_GUIDE의 "쉬운 과제에서 증폭은 지연만 늘린다"는 결론과 정확히 일치:
   포화된 과제에 BoN/AVO를 켜면 토큰 비용만 3~6배 늘어난다.

## 6. 다음 단계 — 판별력 있는 계측기가 선행 조건

조합 효과(H1~H3)의 검증은 lh-001로는 불가능하다. 필요한 것:

1. **lh-002 신설**: 난이도 6+ 장기 워크플로 (멀티파일 마이그레이션, 부분 실패 주입, checkpoint 재개 요구 등) — qwen3.8 baseline이 0.6~0.8에 위치해야 판별력 발생
2. 새 계측기에서 동일 4팔 실험 반복 (인프라는 이번 사이클에 완성됨)
3. frontier 비교도 동일 계측기로 재측정해 격차 수치 갱신
