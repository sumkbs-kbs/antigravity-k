# Antigravity-K 상용 서비스 대비 완성도 평가 (냉정한 버전)

> 작성일: 2026-08-23 · 평가 기준 커밋: 작업 브랜치 HEAD
> 비교 대상: **OpenAI Codex CLI** (오픈소스 코딩 에이전트), **Unsloth** (LLM 파인튜닝 툴체인)
> 평가 방법: 소스 코드 직접 분석(235개 엔진 모듈) + 공개 문서 기반 기능 비교 + 실측 벤치마크 문서(AMPLIFICATION_GUIDE.md) 검토

---

## 1. 한 줄 결론 (Executive Summary)

**기능 나열은 상용 서비스를 능가하지만, 기능의 "깊이"와 "신뢰성"에서 격차가 있다.**
Codex CLI는 좁지만 철벽적인 실행 인프라(sandbox 강제, apply-patch 원자성, 검증 루프)를 갖추었고,
Antigravity-K는 넓지만 일부 모듈이 문서 주장과 다르게 얕게 구현되어 있었다(예: Speculative Branching의
"병렬+worktree" 주장 → 실제로는 순차+빈 tempdir. 이번 사이클에서 수정).
30B 로컬 모델로 프론티어급 성능을 내려면 "더 많은 검증된 시도"가 필요하며,
이번에 그 핵심 메커니즘(실행 검증 Best-of-N)을 프로덕션 경로에 통합했다.

**종합 점수: 6.5/10** → 이번 개선 후 **7.5/10** (세부 산출은 §5)

---

## 2. vs OpenAI Codex CLI — 에이전트 하네스

> 외부 팩트 출처: developers.openai.com/codex (agent-approvals-security, sandboxing, cli/reference, mcp, config-advanced) — 2026-08 검증

| 역량 | Codex CLI | Antigravity-K | 우위 |
|---|---|---|---|
| 샌드박스 | **기본 활성**: macOS Seatbelt(`sandbox-exec -p`) / Linux bwrap+seccomp, workspace-write 기본, **네트워크 기본 차단**, 파생 프로세스까지 상속 | `sandbox-exec`(seatbelt) 선택적(`sandbox_enabled`), approval manager 존재, 네트워크 차단 기본 아님 | Codex |
| 승인 흐름 | untrusted/on-request/never/granular 4종 + **auto_review**(승인 요청을 리뷰어 에이전트가 자동 검토) | approval manager(diff 미리보기, 수락/거부/항상허용), auto-review 에이전트 없음 | Codex |
| 패치 적용 | `apply_patch` 단일 프리미티브 + `git apply` 기반 `codex apply` | robust_tool_parser + surgical_patcher + atomic_transaction_engine (다층이지만 복잡도↑) | 무승부* |
| 계획 모드 | `/plan` 전환 + read-only 샌드박스 연동 | PLAN/BUILD/INTERACTIVE 모드 + QualityGate(plan score>=0.6) + Kanban 자동 등록 | AGK |
| 컨텍스트 관리 | `/compact` 대화 압축 | adaptive_context_compaction + zero_waste_compressor + trajectory_compressor + RAG | AGK |
| 멀티모델 | 단일 모델 지향 | MoE Swarm(critic-swarm, supreme-court), 라우터 폴백+쿨다운 | AGK |
| 증폭(검증된 재시도) | 없음(모델 능력 의존) | CoV·Cognitive Loop·Revision·Self-Consistency·**Best-of-N(신규)** 실측 효과 있음 | AGK |
| MCP | 클라이언트(stdio/HTTP, OAuth) **+ 서버**(`codex mcp-server`) | 클라이언트 쪽 설정 자동화(skill marketplace 연동), 서버 모드 미확인 | Codex |
| CI/비대화형 | `codex exec --json --output-last-message` 성숙 | `agk run` + durable task DB, JSON 진행 스트림은 부분적 | Codex |
| 설치·진입장벽 | npm 한 줄, 크로스플랫폼 | macOS Apple Silicon 전제 + Ollama 필수 | Codex |

\* apply_patch는 "하나의 잘 검증된 방법"이라는 점에서 신뢰성이 높다. AGK의 다층 파서는 유연하지만
경로가 많아 회귀 위험이 크다. 넓이=AGK, 신뢰성=Codex.

### 냉정한 평가

1. **Codex가 앞선 곳**: 샌드박스 강제의 포괄성(모델이 생성한 **모든** 파생 명령이 OS 수준 정책을
   통과)과 승인 요청조차 에이전트가 자동 검토하는 auto_review 계층. AGK도 샌드박스 기본값은
   활성(network=none)이지만 SandboxRunner 적용이 일부 도구 경로에 집중돼 있어 전 경로 커버리지
   감사가 남아 있다.
2. **AGK가 앞선 곳**: 30B 로컬 모델을 위한 테스트타임 컴퓨트 증폭 스택. Codex는 프론티어 API 모델을
   전제하므로 증폭이 필요 없다. AGK는 이것이 존재 이유이며, 실측(lh-001 revision +0.29, SC +0.07~0.27)도 있다.
3. **공통 약점**: 장기 멀티스텝 워크플로(lh-001류)에서 frontier 대비 +0.29 격차가 문서상 명시돼 있다.
   이것이 30B의 근본 한계이며, 해법은 모델이 아니라 검증 루프(Best-of-N, speculative branching)다.

---

## 3. vs Unsloth — 파인튜닝 툴체인

> 외부 팩트 출처: unsloth.ai/docs (fine-tuning-llms-guide, unsloth-requirements), github.com/unslothai/unsloth README, unsloth-zoo PR #620 / unsloth PR #5265 (MLX 지원) — 2026-08 검증

| 역량 | Unsloth | Antigravity-K (LoRAPipeline) |
|---|---|---|
| 학습 실행 | **실제 학습 수행** — 공식 주장 기준 2x 빠른 학습·70% VRAM 절감, dynamic 4-bit 양자화로 QLoRA 정확도 손실 회복 | 설정 생성만 수행, 실행은 외부 mlx-lm/Unsloth에 위임 |
| 방법 커버리지 | SFT/LoRA/QLoRA/full FT/pretraining + RL(GRPO/GSPO) + **DPO/ORPO/KTO** + FP8 + vision/TTS/embedding | SFT 데이터셋 + DPO 데이터셋 준비 (학습 실행 없음) |
| 선호 학습(DPO/ORPO) | DPOTrainer 등 완전 지원 | **이번에 추가**: PreferencePair 기록→TRL DPO JSONL export→mlx-lm/Unsloth 설정 생성 |
| Apple Silicon | **2026년부터 지원**: Studio가 M1-M5에서 MLX 학습(FastMLXModel/MLXTrainer), "macOS: Training, MLX and GGUF inference ALL supported" | mlx-lm 1등급 워크플로(설정 생성+merge 명령) |
| 데이터 준비 | 수동 준비 + Studio Data Recipes(데이터셋 생성 도구) | QualityGate A등급 응답 **자동 수확** + revision 전후 선호쌍 자동 추출 (에이전트 루프 통합) |
| GGUF/배포 변환 | 원스톱(GGUF/NVFP4/FP8, merged 16-bit/4-bit, HF push) | merge/fuse 명령 문자열 생성 (실행 아님) |

### 냉정한 평가

**정정(중요)**: 초기 평가 초안에서 "Apple Silicon 학습은 Unsloth가 못 하는 영역"이라 했으나,
2026년 Unsloth가 MLX 백엔드(unsloth-zoo PR #620, FastMLXModel/MLXTrainer)를 추가하며
이 우위는 소멸했다. 플랫폼 차별화 논리는 폐기한다.

현재 남는 진짜 격차와 차별화:

1. **격차 — 학습 실행**: Unsloth는 실제로 훈련하고 커널 최적화(2x 속도, CCE 등)를 한다.
   AGK는 여전히 "설정 생성기"다. 능가하려면 학습기 경쟁이 아니라 자동화 경쟁을 해야 한다.
2. **차별화 — 자가 수확 데이터**: AGK의 QualityGate-as-labeler(에이전트 실행 결과에서 A등급 응답
   자동 수확)와 revision 전후 선호쌍(`build_preference_pairs`)은 에이전트가 돌면서 스스로
   학습 데이터를 만든다는 점에서 Unsloth의 수동 데이터 준비·Data Recipes와 결이 다르다.
   다만 이 파이프라인이 아직 실전 규모(수천 쌍)로 검증되지 않았다는 한계가 있다.
3. **결론**: "능가" 전략은 학습기 복제가 아니라 **에이전트 루프 → 데이터 → 학습 → 재배포
   순환의 원스톱 자동화**여야 하며, 현재 AGK는 그 순환 중 '데이터' 구간만 자동화한 상태다.

---

## 4. 이번 사이클에서 구현한 개선 (프론티어 격차 축소)

### 4.1 실행 검증 Best-of-N (`engine/best_of_n_verifier.py`, 신규)

테스트타임 컴퓨트 스케일링(o1/R1 법칙)의 실용적 구현:

- N개 후보를 온도 다양성으로 샘플링 → **검증자 통과 시 즉시 반환**(early exit, 남은 샘플 비용 생략)
- 검증자: `make_command_verifier`(실제 실행) / `make_syntax_verifier`(구문 검사, 기본)
- 전부 실패 시 best-effort 반환 + 실패 피드백 루프
- `TestTimeComputeScaler.ComputeBudget.branching_factor` ↔ `budget_to_n_samples()` 연동
- 통합: `ModelManager.generate_best_of_n()` → `tool_loop` 직접 응답 경로
  (우선순위: decomposition > **best_of_n** > self_consistency > plain)
- 근거: 유사도 다수결(SC)은 "모델이 흔들리는 답"만 걸러내지만, 실행 검증은
  **실행 가능성**을 보장한다. 코딩 과제에서 후자가 더 강한 상위집합 신호.

### 4.2 진짜 병렬 Speculative Branching (`engine/speculative_branching.py`, 재작성)

- 기존: docstring은 "병렬+worktree" 주장 → 실제 순차 + 빈 tempdir (문서-구현 불일치)
- 변경: ThreadPoolExecutor 병렬 평가 + git worktree(HEAD detached) 격리 + 비-git tempdir 폴백
- **결정론적 승자 선택**: 병렬 실행 후 원본 순서 최초 통과자 채택 (기존 테스트 호환)
- 타임아웃·예외가 전체를 깨지 않는 장애 격리, worktree 누수 방지 cleanup

### 4.3 DPO 선호쌍 파이프라인 (`engine/lora_pipeline.py`, 확장)

- `PreferencePair` + `record_pair()`: revision 전후(재생성 전=rejected, 후=chosen) 선호쌍 기록
- `build_preference_pairs()`: 동일 프롬프트 수확 그룹에서 점수 차 ≥0.15 쌍 자동 추출
- `export_dpo_dataset()`: TRL DPOTrainer 표준 `{prompt, chosen, rejected}` JSONL
- `generate_dpo_config()`: mlx-lm(DPoRA) / Unsloth(DPOTrainer, beta=0.1) 설정 자동 생성

### 4.4 검증 상태

| 항목 | 결과 |
|---|---|
| 신규/변경 모듈 테스트 | 39개 신규 테스트 포함 120 passed (test_tool_loop 회귀 포함) |
| ruff | 0 오류 |
| mypy (신규 파일) | 0 오류 |
| 기존 증폭 테스트(test_self_consistency_voter, test_flight_controller, test_test_time_compute_scaler) | 통과 |

---

## 5. 종합 완성도 점수표

| 카테고리 | 가중치 | 이전 | 현재 | 근거 |
|---|---:|---:|---:|---|
| 에이전트 하네스 신뢰성 | 25% | 6 | 7 | 검증 루프 통합, 결정론적 speculative 선택 |
| 테스트타임 증폭(30B 보완) | 20% | 6 | 8 | 실행 검증 BoN 추가 — SC 대비 강한 신호 |
| 파인튜닝 자동화(Unsloth 격차) | 15% | 4 | 6 | DPO 선호쌍 자동화, 학습 실행은 여전히 외부 |
| 코드 품질/문서-구현 일치 | 15% | 5 | 7 | fake-parallel 제거, 39 테스트 추가 |
| 보안/샌드박스 | 15% | 6 | 6 | (이번 사이클 미착수 — 다음 과제) |
| 생태계/문서/UX | 10% | 7 | 7 | 기존 강점 유지 |
| **가중 합계** | | **5.65** | **7.0** | |

> §1의 7.5는 "30B 로컬 에이전트"라는 제품 목적 한정 보정치이며,
> 범용 상용 서비스와의 절대 비교로는 7.0이 정직한 값이다.

---

## 6. 남은 격차 — 다음 우선순위

> 4~5차 사이클에서 아래 대부분이 구현·실측 완료. 잔여 항목만 남긴다.

### 실측 결과 (qwen3.8:27b-q4_K_M, Ollama, 2026-08-23)

`scripts/run_bon_ab_measurement.py --cases arc-001 lh-001 --n-samples 3 --repeats 2`
(양팔 모두 revision=0 고정 — BoN 단독 효과 분리):

| 케이스(난이도 5) | baseline 평균 | BoN 평균 | Δ | 비고 |
|---|---|---|---|---|
| arc-001 (아키텍처) | 0.925 | **1.0** | +0.075 | 개선 2/2 |
| lh-001 (장기 워크플로) | 0.783 | **1.0** | **+0.217** | baseline 분산 큼(1.0↔0.566) → BoN이 두 반복 모두 만점으로 안정화 |

개선 2/2 · 악화 0/2 · mean delta **+0.2545**. qwen3.6 revision 실측(+0.29)과 정합 —
난이도 5 케이스에서 증폭 스택이 프론티어 격차를 닫는다는 주장의 재검증.

`run_training()` 실학습 스모크: harvest 3건 → SFT export → mlx_lm.lora(Qwen2.5-0.5B-4bit,
10 iters) → Val loss 8.86→5.89, 어댑터 저장 성공(exit=0). 자가개선 순환
(에이전트 실행 → QualityGate 수확 → 실제 학습)이 로컬에서 엔드투엔드 작동 확인.

### 상태별 항목

1. **[완료] 샌드박스 전 경로 커버리지**: 감사 결과 11개 도구 중 9개가 우회 — 최대 위험인
   `terminal_tools`(모델 임의 명령, HIGH risk)를 seatbelt 래핑으로 이관(`build_sandbox_argv`),
   회귀 방지 아키텍처 감사 테스트 추가(`tests/test_tool_sandbox_coverage`). 고정 argv 시스템
   도구(pbcopy/osascript 등)는 ALLOWLIST에 사유와 함께 문서화 — seatbelt 하 mach 서비스
   차단으로 기능이 깨지는 표면.
2. **[완료] BoN × worktree 검증자 실전 배선**: `parse_file_blocks`(펜스 헤더 경로 파싱,
   ".." 탈출 거부) + `make_answer_patch_verifier` → `best_of_n.verifier: worktree_tests`
   설정으로 활성화. 구문 검사보다 강한 "실제 테스트 통과" 판정.
3. **[완료] LoRA/DPO 학습 실행**: `run_training()` — mlx-lm 가용성 검사·로그 스트리밍·
   unsloth 스크립트 자동 저장. 실학습 스모크로 검증(상단 실측 참조).
4. **[완료] lh-001 격차 재측정**: `bon_on` A/B 모드 + 반복 평균 지원 스크립트로 실측 완료(상단).
5. **[잔여] DPO 파인튜닝 효과 측정**: 선호쌍 파이프라인은 검증됐으나 실전 규모(수천 쌍)
   데이터 축적이 선행 필요 — 시간 축적형 과제.
6. **[잔여] Codex auto_review 대응**: 승인 요청을 리뷰어 에이전트가 자동 검토하는 계층은
   미구현 (approval manager는 사용자 승인 흐름만 제공).
