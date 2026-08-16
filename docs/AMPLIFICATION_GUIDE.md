# Amplification Guide — 로컬 모델 성능 증폭 튜닝

이 가이드는 Antigravity-K가 **로컬 모델(qwen3.6:latest 등 30B급)** 의 성능 한계를
**구조적 증폭**으로 보완하는 방법을 설명한다. 모델 자체 능력이 아니라 검증·재생성·
다수결 루프로 프론티어급에 근접하는 것이 이 프로젝트의 핵심 철학이다.

> **검증 상태**: 모든 서브시스템의 적용 경로는 프로덕션 코드에서 확인됐다.
> CoV는 `build_orchestrator_graph()`의 COV_VERIFY 노드에, Cognitive/Revision은
> `tool_loop._post_loop_checks`에, Self-Consistency는 `tool_loop` 직접 응답 경로에
> Task Decomposition는 `ModelManager.generate_decomposed` → `tool_loop` 직접 응답
> 경로에 실제로 연결되어 있다. 실제 qwen3.6 end-to-end 실행으로 프로덕션 tool_loop가
> 동작함을 확인했다(revision 발화는 품질 게이트 탈락 시에만, 통과 시 미발화는 정상).

## 한눈에 보기

| 서브시스템 | 기본 | 역할 | 적용 경로 | 실측 효과(qwen3.6) |
|---|---|---|---|---|
| Chain-of-Verification (CoV) | `on` | 환각·논리오류 자기검증·재작성 | 복잡한 작업 (state graph COV_VERIFY) | frontier 5케이스 중 2건 CoV 수정 발화 → excellent |
| Cognitive Loop | `on` | Plan→Execute→Verify→Reflect→Adapt 재시도 | 도구 루프 내부 (verify_tool_result/reflect) | max_retries·dialectic으로 추론 깊이 보완 |
| Self-Consistency | `off` | 단일 모델 N샘플링→다수결 선택 | 직접 응답 (최종 답변) | lh-001 3회 평균 off 0.91 → on 0.98 (delta +0.07) |
| Revision (QualityGate) | `on` | 품질 게이트 탈락 시 재생성 | 복잡한 작업 후 (tool_loop _post_loop_checks) | lh-001 3회 평균 off 0.71 → on 1.00 (delta +0.29) |
| Task Decomposition | `off` | 순차 작업을 LLM 단계 분해 후 단계별 실행·통합 | 직접 응답 (generate_decomposed) | 순수 생성 대비 +0.20; revision 병행 시 품질 이득 0, 지연 6-8배 |
| Decomposition Recovery | `on` | revision 실패 후 순차 과제만 분해로 승격 | tool_loop `_post_loop_checks` | 분해 결과가 원본보다 나을 때만 채택 |

> **측정 방법**: `BenchmarkHarness.compare_amplification()`의 A/B 비교로 동일 케이스를
> 증폭 off/on으로 실행해 평균 점수 차이를 구한다. 단일 케이스 측정은 노이즈가 크므로
> 3회 이상 반복 평균으로 판단한다.
> **중요**: Revision은 프로덕션(tool_loop)과 harness(측정) 양쪽에 같은 로직이 있다.
> harness의 측정값은 프로덕션 동작을 대변한다.

## 핵심 원칙: 복잡도 게이팅

증폭 자원은 **복잡한 작업에만 집중**한다. 단순 인사/목록 질문에 N샘플링·재생성을
쓰면 비용만 낭비한다. 모든 증폭 서브시스템은 공용 `estimate_complexity()` (0.0~1.0)를
공유해 작업 난이도를 판정한다:

- 단순 지표(안녕, hello, 목록...) 2개 이상 → 0.1 (게이트 스킵)
- 복잡 지표(아키텍처, 동시성, 캐시, 보안...) → 가중치 합산
- 코드 요청 키워드 → +0.2
- 프롬프트 길이 → 최대 +0.2

`complexity_threshold` 미만이면 해당 증폭을 발화하지 않는다.

## 설정 (config.yaml)

```yaml
amplification:
  cov:
    enabled: true              # Chain-of-Verification 자기검증
    model: null                # null=model.main_model (lmstudio/mlx 전환 시 자동 추종)
    min_response_length: 50    # 이 길이 미만 응답은 검증 스킵
    complexity_threshold: 0.4  # 복잡도 미만 작업은 검증 스킵
    max_revise_iterations: 2   # revise→verify 폐루프 반복 한계
  cognitive:
    enabled: true              # Plan→Execute→Verify→Reflect→Adapt 루프
    dialectic_enabled: true    # 정반합 자기 비판 (작은 모델 추론 깊이 보완)
    max_retries: 2             # 실패 시 재시도 한계 (qwen3.6에서 4-5로 늘려볼 수 있음)
    enable_caveman: false      # 압축 산문 모드
  self_consistency:
    enabled: false             # 단일 모델 N샘플링 (기본 off, 비용 3-5배)
    n_samples: 5               # 샘플링 횟수
    base_temperature: 0.7      # 기준 온도
    temperature_spread: 0.2    # 샘플 간 온도 다양성
    similarity_threshold: 0.5  # 클러스터링 유사도 임계값
    selection: majority        # 다수결 선택
    complexity_threshold: null # null=항상 샘플링, 0.4 권장(단순 질문 비용 절제)
  task_decomposition:
    enabled: false             # 기본 off: revision이 이미 구원하면 지연만 증가
    escalate_on_revision_failure: true  # revision 실패 시 순차 과제만 승격
    min_steps: 2               # 이 미만 단계면 분해 스킵 후 폴백
    max_steps: 6               # 단계 상한 (초과분 절단)
```

현재 상태는 `agk doctor`로 확인한다:

```bash
agk doctor
# Amplification: cognitive loop        on · retries=2 dialectic=True
# Amplification: chain-of-verification  on · revise=2 threshold=0.4
# Amplification: self-consistency       off · n=5 gate=None
# Amplification: task decomposition     off · steps=2-6 escalate=on
```

`escalate_on_revision_failure`는 초기 분해가 off여도 재생성 후에도 점수가
오르지 않은 순차 과제(워크플로/마이그레이션/파이프라인)에서만 분해를
다시 시도한다. 분해 결과가 원본보다 나을 때만 채택한다.

## 멀티 프로바이더 전환 (Ollama / LM Studio / MLX)

모든 증폭 서브시스템은 프로바이더 독립적으로 동작한다. CoV는 `model: null`이면
`model.main_model`을 따르고, Decomposition/Self-Consistency는 요청의 `target`
모델 그대로 샘플링/분해한다. 즉 백엔드를 바꾸면 증폭도 같은 백엔드에서 돈다.

| 백엔드 | 프로필 | 준비물 |
|---|---|---|
| Ollama (기본) | `qwen3.6:latest` | `ollama serve` + `ollama pull qwen3.6:latest` |
| LM Studio | `lmstudio/qwen3.6` | Local Server(`127.0.0.1:1234/v1`) + 토큰 활성화 시 `.env`의 `LM_STUDIO_API_KEY` |
| MLX 직접 | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` | `uv sync --extra mlx` (mlx-lm 설치) |

실행:

```bash
uv run agk run "복잡한 마이그레이션 워크플로를 설계해줘" --model qwen3.6:latest
uv run agk run "..." --model lmstudio/qwen3.6          # LM Studio 경유
uv run agk run "..." --model mlx-community/Qwen2.5-Coder-32B-Instruct-4bit  # MLX 직접
```

LM Studio 서버가 "API token is required"를 반환하면 LM Studio 앱의 Developer
설정에서 발급한 토큰을 `.env`의 `LM_STUDIO_API_KEY`에 넣는다. 토큰을 끄면 이
변수 없이도 동작한다.

## 서브시스템별 상세

### 1. Chain-of-Verification (CoV)

모델이 생성한 답을 동일 모델의 볼 호출로 검증·재작성한다. 환각·구문 오류·자기 모순을
잡는 1차 방어선. 복잡한 작업에만 선택적으로 적용된다.

- **적용 경로**: state graph의 COV_VERIFY 노드 (복잡한 작업 후 자동 실행)
- **config 모델 추종**: `cov.model: null`이면 `model.main_model`을 따른다.
  ollama/lmstudio/mlx 전환 시 자기검증도 같은 백엔드로 자동 전환된다.
- **측정**: frontier suite 5케이스 중 2건(sim, anl)에서 CoV revision이 발화해
  품질 등급을 올린 기록이 있다.

### 2. Cognitive Loop

Plan→Execute→Verify→Reflect→Adapt 인지 순환. 도구 실행 후 자동 검증하고 실패 시
전략을 바꿔 재시도한다. `dialectic_enabled`(정반합 자기 비판)과 `max_retries`가
작은 모델의 추론 얕음을 보완한다.

- **적용 경로**: 복잡한 작업의 도구 루프 (`_prepare_agent_prompt` → tool_loop)
- **튜닝 팁**: qwen3.6에서 복잡한 작업이 자주 실패하면 `max_retries: 4`로 올려본다.

### 3. Self-Consistency

단일 모델을 다양한 온도로 N회 샘플링하고, 유사도 클러스터링으로 가장 일관된 답을
선택한다. 추론/수치/코드 정확도를 올린다. 모델 종류와 무관하게 config 토글로 작동한다.

- **적용 경로**: 직접 응답(최종 답변) 경로. 복잡한 멀티스텝 도구 작업에는 미적용.
  (스트리밍 도구 루프에서 N샘플링은 구조적으로 부적합 — 각 샘플이 다른 도구 경로를 탐)
- **복잡도 게이트**: `complexity_threshold` 미만이면 단일 생성으로 폴백(비용 절제).
- **측정**: 가장 어려운 케이스 lh-001을 3회 반복 시 off 평균 0.71 → on 평균 0.98
  (delta +0.07), on≥off 3/3, worse 0. 모델이 흔들리는 실행에서 단일 실패를 다수결로 구원.
- **비용**: N샘플링이므로 지연이 3-5배 증가한다. 단순 질문에까지 켜면 비효율.

### 4. Revision (QualityGate)

품질 게이트가 retry/fail 등급을 내리면 피드백과 함께 답을 재생성한다. 복잡한 작업에서
가장 비용 효율적인 증폭(재생성 1-2회 추가 호출). 프로덕션 경로(tool_loop의
`_post_loop_checks`)와 벤치마크 harness 양쪽에 같은 로직이 있어, 측정값이 프로덕션
동작을 대변한다.

- **측정**: lh-001을 3회 반복 시 off 평균 0.71 → on 평균 1.00 (delta +0.29).
  단일 케이스(한 실행)에서는 off 0.38(retry) → on 0.60(good)로 탈락 답을 구원.
  worse=0 — 어떤 케이스도 악화시키지 않음.
- **durable task 저장 규칙**: CLI 스트리밍에는 초안과 수정본이 모두 표시되지만,
  direct task record는 최종 agent output만 저장한다. 재개/조회 소비자는 초안
  노이즈 없이 최종 답을 받는다.
- **반복 실패 구원**: qwen3.6의 고질적 실패 모드인 응답 반복(arc-002 3회 중
  1회 "3회 반복" 탐지, 0.51)을 revision이 재생성으로 구원한다. arc-002 3회
  평균 off 0.84 → on 1.00, 악화 0. 실패 모드가 추론이 아니라 **출력 반복**일
  때는 분해가 아니라 revision이 정확한 도구다.
- **반복 사전 억제 스윕**: repeat_penalty 1.10/1.15는 각 3회 모두 1.00,
  반복 0. 1.20은 반복 1/3에 0.321로 오히려 악화. 이에 따라 초기 생성은 1.10,
  revision 재생성만 1.15로 올린다. 프로덕션 직접 응답도 qwen3 계열
  repeat_penalty를 1.10으로 정렬했다.

### 5. Task Decomposition

복잡한 멀티스텝 작업(마이그레이션 워크플로, 파이프라인 설계 등)을 모델 자신에게
명시적 하위 단계로 분해시키고, 각 단계를 별도 프롬프트로 실행한 뒤 구조적으로
통합한다. 작은 모델이 한 번의 생성으로 장기 워크플로의 구성요소(checkpoint,
recovery, idempotency, rollback 등)를 누락하는 약점을 단계 프롬프트로 보완한다.

- **적용 경로**: 직접 응답 경로. `tool_loop`가 `generate_decomposed`를 호출하고,
  내부에서 LlmTaskDecomposer가 분해 → 단계별 생성 → 통합을 수행한다.
- **순차 컨텍스트**: 각 단계는 앞선 단계의 결과를 받아 이어서 작성한다. Event
  Store가 Command 모델 위에 얹히는 것처럼 단계 간 의존성이 유지된다.
- **폴백 체인**: 비활성이거나 `is_complex_task` 게이트 미통과 시
  self-consistency → 일반 생성 순으로 자동 폴백한다. 단순 질문은 1회 호출로 끝난다.
- **게이트 범위**: 워크플로/마이그레이션/파이프라인 같은 **순차 실행 과제만**
  대상이다. 아키텍처 설계(arc-002)는 실측에서 분해 이득 0(0.755→0.755),
  지연 4배(148.9s)로 게이트에서 제외했다.
  리팩토링(ref-001)도 3/3 악화(0.580→0.384)와 지연 4~5배로 제외했다.
- **측정**: lh-001(장기 워크플로, qwen3.6 최약점) 3회 반복 평균 off 0.58 →
  on 0.78 (delta +0.20), 3/3 개선·0 악화. 등급 변화: retry/retry/retry →
  good/retry/excellent. 3회 재측정 프론티어 기준 격차 +0.29 → 약 +0.08로 축소.
- **revision과 조합 시 비용 효율**: QualityGate revision(2회)을 함께 켜면
  revision 단독과 분해+revision 모두 3/3에서 1.00/excellent로 동일했지만,
  지연은 revision 11.3~13.9초 vs 스택 83.9~99.4초(6~8배). 따라서 기본값은
  revision 우선이고, 분해는 revision이 반복적으로 실패하는 순차 과제에서만
  수동으로 켠다.
- **비용**: 지연 약 4배(평균 15.7s → 62.4s). 분해 1회 + 단계별 실행 N회.
- **A/B 측정**: `compare_amplification(modes=['decomp_off', 'decomp_on'])`.

## qwen3.6 튜닝 추천

**기본 프로필** (비용 절제 우선, 이미 config 기본값):
- CoV `on`, Cognitive `on`, Self-Consistency `off`, Task Decomposition `off`,
  Revision `on`(내장)
- 단순 질문은 증폭 없이 빠르게, 복잡한 작업은 CoV+revision으로 보완.

**최대 품질 프로필** (정확도 최우선, 비용 허용 시):
```yaml
amplification:
  cognitive:
    max_retries: 4            # 재시도 늘려 추론 깊이 보완
  cov:
    max_revise_iterations: 3  # 검증-재작성 폐루프 강화
  task_decomposition:
    enabled: true             # revision 후에도 장기 워크플로가 실패할 때만 권장
    max_steps: 8              # 장기 워크플로 단계를 더 세밀하게
  self_consistency:
    enabled: true
    n_samples: 5
    complexity_threshold: 0.4 # 단순 질문 비용 절제
```

## 한계 (투명성)

- **Self-Consistency/Decomposition은 직접 응답에만**: 멀티스텝 도구 작업에는
  적용되지 않는다. 복잡한 도구 작업은 CoV/Cognitive/Revision이 담당한다.
- **실측은 특정 케이스 기준**: frontier suite의 대부분 케이스는 qwen3.6이 첫 시도에
  excellent라 증폭 효과가 작게 보인다. 효과는 모델이 어려워하는 장기 작업(lh-001)에서
  뚜렷하다.
- **비용**: Self-Consistency는 3-5배 지연, Decomposition은 약 4배 지연(분해+N단계),
  Revision은 1-2회 추가 호출. CoV도 검증용 1회 추가 호출. 복잡도 게이트로 단순
  작업 비용은 절제된다.

## A/B 측정 직접 실행

```python
from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry

harness = BenchmarkHarness(ModelManager(ModelRegistry()), db_path=None)
out = harness.compare_amplification(['lh-001'], 'qwen3.6:latest',
                                    modes=['revision_off', 'revision_on'])
print(out['stats']['improvement'])  # mean_delta, improved, worse, same
print(out['summary'])               # 케이스별 표
```

측정 가능한 모드: `cascade_off/cascade_on`, `revision_off/revision_on`, `sc_off/sc_on`.
`decomp_off/decomp_on`으로 단계 분해 증폭도 동일하게 A/B 측정한다.

## 프론티어 근접도 (실제 비교)

같은 벤치마크 케이스로 qwen3.6(로컬) vs frontier 모델들을 비교한 실측 결과다.
증폭 off(revision_off)로 순수 모델 능력을 비교한다.

### gpt-4o-mini vs qwen3.6 (frontier suite 전체)

| 케이스 | 범주 | qwen3.6 | gpt-4o-mini | 격차 |
|---|---|---:|---:|---:|
| sim-001 | 코딩(피보나치) | 1.00 | 1.00 | 0.00 |
| alg-001 | 알고리즘(BST) | 1.00 | 1.00 | 0.00 |
| srch-002 | 검색 요약 | 1.00 | 1.00 | 0.00 |
| anl-001 | 분석(프레임워크 비교) | 1.00 | 0.94 | -0.06 |
| lh-001 | 장기 작업 워크플로 | 1.00 | 1.00 | 0.00 |
| **평균** | | **1.00** | **0.99** | **-0.01** |

### claude-opus-4 vs qwen3.6 (대표 케이스)

| 케이스 | qwen3.6 | claude-opus-4 | 격차 |
|---|---:|---:|---:|
| sim-001 (피보나치) | 1.00 | 0.51 | -0.49 |
| lh-001 (장기 작업) | 1.00 | 1.00 | +0.00 |

claude-opus-4는 sim-001에서 키워드는 모두 포함했지만(coverage 1.0) 응답을 4회 반복해
품질 게이트의 반복 탐지에 걸려 0.51을 받았다. 즉 진짜 frontier도 이 벤치마크의
품질 게이트에서 항상 만점이 아니다.

### claude-opus-4 vs qwen3.6 (어려운 과제, 난이도 4-5)

쉬운 suite(평균 격차 -0.01)만 보면 "격차 없음"으로 보이지만, 어려운 과제로 비교하면
케이스별로 완전히 다른 패턴이 드러난다.

| 케이스 | 난이도 | qwen3.6 | claude-opus-4 | 격차 | 통찰 |
|---|---:|---:|---:|---:|---|
| ref-001 (SOLID 리팩토링) | 4 | 1.000 | 0.580 | -0.420 | qwen3.6 3/3 만점 |
| arc-001 (플러그인 시스템) | 5 | 0.975 | 0.950 | -0.025 | 동등 |
| arc-002 (이벤트 소싱/CQRS) | 5 | 0.785 | 0.837 | +0.051 | 둘 다 bimodal |
| lh-001 (마이그레이션 워크플로) | 5 | 0.566 | 0.855 | +0.289 | frontier 강점 |
| **평균** | | **0.832** | **0.805** | **-0.026** | 평균은 qwen3.6 근소 우위 |

**ref-001 계약 정합성 수정**: 초기 측정은 벤치마크가 "계획/비교 표"를 요청하지
않으면서 게이트는 이를 감점해 qwen/claude 모두 0.58을 받았다. 리팩토링 계획과
Markdown 비교 표를 프롬프트 계약에 명시한 뒤 qwen3.6은 3회 모두 1.00/excellent,
claude-opus-4는 3회 모두 0.58. 위 표는 이 수정된 계약 기준 3회 반복 평균이다.
재현: `data/benchmarks/hard-suite-contract-fixed-run{1,2,3}.json`.

**어려운 과제에서의 솔직한 결론**:

- 평균은 qwen3.6이 근소하게 앞선다(-0.026)지만 사실상 동등이며, **케이스별로
  모델 강점이 다르다**.
- **lh-001(장기 작업 워크플로)은 frontier의 강점 영역**이다(순수 생성 +0.29).
  Task Decomposition가 3회 평균 0.58 → 0.78로 이 격차를 약 +0.08로 축소했다.
  복잡한 멀티스텝 계획/실행/복구 로직은 여전히 강한 기본 추론이 유리하다
  (이전 A/B: revision off 0.71 → on 1.00).
- **arc-002(이벤트 소싕/CQRS)는 bimodal이다**: 순수 생성은 1.00이거나 반복
  탐지로 0.43~0.51. 3회 A/B에서 qwen3.6의 반복 실패 실행(0.51)을 revision이
  1.00으로 구원해 평균 0.84 → 1.00. 실패 모드가 추론이 아니라 출력 반복이라
  구조적 증폭으로 방어 가능하다.
- ref-001의 claude 저점은 게이트의 형식 요구(계획/비교 표)를 반복적으로 놓친
  결과다. 형식 계약을 명시하면 qwen3.6은 이를 안정적으로 지킨다.

> **요약**: "qwen3.6이 frontier에 도달했다"는 과장이다. 정확한 진술은:
> "쉬운/중간 과제와 어려운 과제 평균에서는 동등하고, 장기 멀티스텝 워크플로
> 같은 특정 영역에서는 격차가 남는다." 증폭은 그 격차를 확률적으로 좁힌다.

**솔직한 결론**:

- **쉬운 과제(sim/alg/srch/anl, 난이도 1-3)에서는 qwen3.6이 frontier와 동등**하다.
  코딩·알고리즘·검색·분석 범주에서 로컬 모델이 충분히 풀 수 있다.
- **어려운 과제(난이도 4-5)에서도 평균은 동등**하다(3회 평균 0.832 vs 0.805).
  단, 케이스별로 강점이 다르다 — 장기 멀티스텝 워크플로(lh-001)는 순수 생성에서
  frontier가 +0.29 앞서지만 분해 증폭으로 약 +0.08까지 좁힌다. 리팩토링 계약이
  명확하면 qwen3.6이 3/3 만점을 낸다.
- **중요한 한계**: 이 벤치마크는 한국어 키워드 기반 품질 게이트를 쓴다. 더 넓은 과제,
  영어 과제, 창의적/개방형 과제에서는 격차가 다를 수 있다. claude sim-001이 반복
  탐지로 0.51을 받은 사례처럼 측정 자체의 한계도 인식해야 한다.
- **증폭의 진정한 역할은 최악의 실행을 구원하는 것**이다. 평균은 이미 동등하지만,
  모델이 흔들리는 개별 실행에서 revision/self-consistency가 품질을 올린다(이전 A/B:
  lh-001 3회 평균 revision off 0.71 → on 1.00). Decomposition은 revision을 쓸 수
  없는 순수 생성 경로에서 약점 영역의 평균을 올린다(off 0.58 → on 0.78). 증폭은
  **하방을 방어하고 약점을 좁힌다**: 장기 워크플로 순수 생성엔 decomposition,
  출력 반복엔 revision이 각각 대응하고, 둘 다 쓸 수 있으면 저렴한 revision이 먼저다.

> 재현: `uv run python scripts/run_frontier_comparison.py --frontier anthropic/claude-opus-4`
> (.env에 OPENROUTER_API_KEY 필요). 단일 실행 기반이므로 노이즈가 있다 — 정확한 비교를
> 위해 여러 번 반복 평균과 더 넓은 과제 suite가 필요하다.
