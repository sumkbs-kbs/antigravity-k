---
id: 6
category: note
tags: []
created: 2026-05-04T09:42:52.082980
---

# 아키텍처 가이드 (Architecture)

## 시스템 흐름도 (Data Flow)

tinker-nemogym의 훈련 루프는 크게 3개의 컴포넌트(Trainer, NeMo-Gym, Tinker)가 상호작용하며 진행됩니다.

```
┌──────────────┐    POST /run        ┌──────────────────┐   sample_async    ┌───────────────┐
│  trainer     │ ─────────────────▶  │  nemo-gym        │ ────────────────▶ │  Tinker       │
│  (this repo) │                     │  SimpleAgent     │                   │  (managed GPU)│
│              │ ◀─── {reward,       │  + Resources     │ ◀─── tokens +     │  LoRA client  │
│              │    tokens, lp}      │  server          │    logprobs       │               │
└────┬─────────┘                     └──────────────────┘                   └───────────────┘
     │  forward_backward + optim_step + save_weights
     ▼
  ┌──────────────────────────┐
  │ FastAPI shim :8001       │  ◀── hot-swap SamplingClient after each optim step
  │ (in-process w/ trainer)  │
  └──────────────────────────┘
```

## 핵심 동작 원리

### 1. FastAPI Shim 모델 위장
Trainer 프로세스는 내부에 경량화된 **FastAPI Shim(8001 포트)**을 구동합니다. NeMo-Gym 환경의 `SimpleAgent`는 이 포트에 연결하여 일반적인 정책 모델(`SimpleResponsesAPIModel`)과 통신한다고 인식하지만, 실제로는 모든 텍스트 생성(Completion) 요청이 Tinker의 `SamplingClient`로 우회(Routing)됩니다.

### 2. Zero-Downtime 핫스왑 (Hot-Swap Sampler)
오픈소스 LLM 훈련 환경(예: SGLang 등)에서 가중치 업데이트 후 서버를 재시작하는 다운타임을 해결했습니다.
- Trainer는 내부적으로 `optim_step_async`를 실행하여 GPU에서 역전파(Backpropagation)와 옵티마이저 스텝을 완료합니다.
- 새로운 가중치가 산출되면 즉시 새로운 Sampling Client 객체로 **교체(Hot-swap)** 합니다.
- 이로 인해 다음 단계의 Rollout부터는 서버 재시작 없이 즉시 최신 가중치 기반으로 샘플링이 이루어집니다.

### 3. GRPO 어드밴티지 계산 및 Datum 변환
NeMo-Gym 에이전트로부터 반환된 최종 데이터(reward, tokens, log probabilities)는 `datum_builder`를 거칩니다.
- **GRPO (Group Relative Policy Optimization)** 논리를 적용하여 동일 프롬프트에 대한 그룹(Group) 단위로 어드밴티지를 정규화합니다.
- 보상 편차가 없는 일정한 리워드를 반환한 그룹은 훈련 효율을 위해 자동으로 버려집니다(Dropped).
- 전처리된 최종 데이터 형태인 `tinker.Datum` 형식으로 변환되어 다음 옵티마이저 스텝의 손실(Loss) 계산에 활용됩니다.
