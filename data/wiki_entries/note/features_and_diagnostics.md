---
id: 7
category: note
tags: []
created: 2026-05-04T09:42:52.086324
---

# 주요 기능 및 진단 도구 (Features & Diagnostics)

tinker-nemogym은 단순한 파이프라인 연동을 넘어, 분산 비동기 훈련 환경에서 발생할 수 있는 문제점들을 추적하고 관측할 수 있는 고급 진단 스칼라(Scalars) 측정 도구들을 내장하고 있습니다. 이 값들은 모두 **Wandb** 대시보드와 로컬 로그에 실시간으로 기록됩니다.

## 1. 훈련 지연 및 지표 관측 (Latency & Staleness)

FastAPI Shim을 통해 훈련이 돌아가는 동안, 각 샘플링 데이터가 현재 정책 가중치로부터 얼마나 뒤쳐져 있는지(Staleness), 그리고 샘플링에 걸리는 지연 시간(Latency)이 지속 추적됩니다. (기본 활성화)

| 측정 항목 (Metrics) | 의미 |
|---|---|
| `staleness_mean` | `현재 가중치 버전(save_count) - 반환된 샘플의 버전`의 평균값. |
| `staleness_max` | 큐잉되거나 지연되어 가장 오래된 정책(Policy)으로 생성된 샘플의 오차 차수. |
| `staleness_n_stale` | 0 이상의 Staleness를 가진 샘플의 개수. |
| `sample_latency_ms_p50/p95` | 단위 Rollout 당 생성되는 소요 시간의 중앙값 및 95 백분위수. |

**해석 방법:**
- Staleness 값이 1 정도면 GRPO 모델에서 정상 허용 범위입니다. 값이 계속 커지면 샘플링 속도보다 옵티마이저 속도가 더 빠르거나 병목이 있다는 의미이므로 `batch_size`를 조절해야 합니다.
- P95 지연율 대비 P50 지연율이 2배 이상 벌어지면 Tinker의 레이트 리밋에 걸렸거나 다른 GPU 연산이 경합 중일 수 있습니다.

## 2. 정밀도 오차 (Precision Gap, β) 측정

HuggingFace의 `BF16-mismatch` 논문에 기반하여 훈련 모드(Trainer)의 Log Probabilities와 추론 모드(Sampler)의 Log Probabilities 간 수치적 드리프트 현상을 감지합니다. 이 기능은 `training.measure_precision_gap: true` 설정으로 활성화(Opt-in)할 수 있습니다.

- **원리:** 매 스텝 본래의 옵티마이저 `forward_backward_async` 직전에, 손실 대리 함수(Cross entropy loss surrogate)를 사용하여 추가 `forward_async`를 1회 실행합니다. 이후 동일한 가중치에서 샘플러가 생성했던 로그 확률과 비교(`trainer_lp - sampler_lp`)하여 오차(β)를 계산합니다.
- **주요 지표:** `beta_abs_mean` (절댓값 평균 오차)
  - `< 0.01` : 완전히 이상적인 수치 (샘플러와 트레이너의 커널 엔진이 소수점 3자리까지 일치함)
  - `0.05 ~ 0.2` : 의심스러운 상태. 커널 오차 노이즈로 인해 PPO/GRPO의 클리핑이 오작동할 수 있음.
  - `> 0.5` : 샘플러와 트레이너가 완전히 다른 정밀도 캐스팅 모델(예: 순수 FP32 vs BF16)을 사용 중이며 호환되지 않음.
- **주의사항:** 스텝 당 forward를 추가로 1회 더 실행하므로 **전체 처리량(Throughput)이 절반으로 감소**합니다. 프로덕션에서는 비활성화하고, 새로운 베이스 모델을 도입하거나 성능 한계 진단 시에만 사용해야 합니다.

## 3. 재현성 에코 데이터 (Reproducibility Echoes)

각 응답(Response) 객체는 `RawTrajectory.metadata` 내에 아래 정보들을 남겨 분석할 수 있도록 합니다.
- `sampling_params_used`: Tinker API 기본값이 주입된 최종 `{temperature, top_p, top_k, seed, max_tokens, stop}`.
- `prompt_logprobs`: 프롬프트 토큰들의 초기 로그 확률값.
