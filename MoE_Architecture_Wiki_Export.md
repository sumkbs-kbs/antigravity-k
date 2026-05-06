---
title: Antigravity-K MoE Swarm 아키텍처 및 안정성 패치 기록
tags: [architecture, antigravity-k, moe, swarm, troubleshooting]
date: 2026-05-04
---

# Antigravity-K 시스템 정비 및 아키텍처 진화 (2026-05-04)

## 1. 개요
단일 모델에 의존하는 에이전트 구조의 한계를 탈피하고, 다국적/다중 모델이 교차 검증하는 **MoE(Mixture of Experts) Swarm 아키텍처**를 도입함. 또한 시스템 장기 구동 시 발생하는 JSON 파싱 에러, 테스트 프레임워크 혼동, 그리고 컨텍스트 폭발 등의 버그를 수정함.

## 2. 주요 트러블슈팅 및 안정성 강화

### A. 파일명 규칙 정비 (pytest 충돌 방지)
- **문제**: `test_harness.py`와 `test_runner_tool.py`라는 프로덕션 코드가 `test_` 접두어를 가져, 테스트 프레임워크(pytest)가 이를 테스트 코드로 오인하여 자동 수집하는 부작용 발생.
- **해결**: 각각 `harness.py`, `ci_tools.py`로 파일명을 리네임하고, 의존성 모듈들의 `import` 경로 4곳을 업데이트하여 시스템 위생(Hygiene)을 복구.

### B. HardwareAnalystAgent JSON 파싱 복원력 확보
- **문제**: Ollama 또는 외부 API 응답이 실패하여 `[API Error...]` 등의 에러 문자열이 반환될 때, 에이전트가 이를 억지로 `json.loads()` 처리하려다 `JSONDecodeError (Expecting value)`를 내며 파이프라인 중단.
- **해결**: 응답이 `[API Error`로 시작하거나 올바른 JSON 블록 `{ ... }`을 찾지 못할 경우, 무리하게 파싱하지 않고 **안전한 기본 Fallback 제안서(오류 보고서)**를 스스로 작성하도록 로직 개선. 파싱 에러 시 `Raw output`을 디코딩 에러 메시지에 명시하여 관찰 가능성(Observability) 증대.

## 3. 집단지성(MoE Swarm) 라우팅 아키텍처 도입

### 철학: "단일 역할 = 단일 모델" 체제의 타파
단일 거대 모델 하나가 처음부터 끝까지 코딩을 수행할 경우 **환각(Hallucination) 및 자기 코드 맹점**에 빠질 확률이 높다. 이를 해결하기 위해 하나의 역할(Role) 내에서도 구글, 메타, 엔비디아, 딥시크, 알리바바의 모델들이 번갈아 가며 사고하는(Round-Robin) **Swarm Combo** 아키텍처를 도입함.

### 다국적 어벤져스 매핑 (config.yaml)
시스템의 128GB RAM 및 100GB 로드 제한과 런타임 언로드(Auto-unload) 기능을 활용하여, 모델별 전문성과 철학이 상호 보완되도록 구성함.

- **CEO/QA/DESIGNER (`orchestrator-swarm`, `qa-swarm`)**
  - **구성**: `gemma4:31b` (Google) + `llama4:latest` (Meta) + `qwen3.6` (Alibaba)
  - **특징**: 서구권의 엄격한 가이드라인 준수와 속도가 빠른 미들급 모델의 조합으로 관제 및 엣지 케이스 테스트.
- **WORKER (`coding-swarm`)**
  - **구성**: `qwen2.5-coder:32b` (중) + `llama4:latest` (미) + `deepseek-r1:32b` (중)
  - **특징**: 최고 성능의 코딩 특화 모델들이 릴레이 형식으로 코드를 작성하고 리뷰하며 버그를 잡음.
- **ARCHITECT / CRITIC (`architect-swarm`, `critic-swarm`)**
  - **구성**: `nemotron-3-super` (Nvidia, 86GB) + `deepseek-r1:32b` (DeepSeek)
  - **특징**: CoT 추론 특화 뇌와 하드웨어 관점의 초거대 비평 뇌가 만나 아키텍처의 구조적 결함을 날카롭게 비판.
- **ARBITER (`supreme-court`)**
  - **구성**: `deepseek-r1:70b` + `nemotron-3-super`
  - **특징**: 교착 상태에서만 깨어나는 대법원 역할의 70B+ 초거대 모델 풀.
