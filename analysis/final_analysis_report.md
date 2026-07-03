# Antigravity-K — 종합 정밀 분석 보고서

> 분석일: 2026-05-12  
> 대상: /Users/mr.k/program/coding/ssak_comp/antigravity-k/src/antigravity_k/  
> 분석 방법: 핵심 파일 소스 코드 직접 읽기 + 정량 지표 산정

---

## 1. 프로젝트 현황 요약

| 지표 | 값 |
|------|---|
| 총 Python 파일 수 | **6,453개** |
| 총 LOC (Lines of Code) | **약 2,006,000줄** |
| 핵심 engine/ 모듈 LOC | 38,766줄 |
| 가장 큰 단일 파일 | engine/slash_commands.py (1,229줄) |
| 두 번째로 큰 파일 | engine/harness.py (1,069줄) |
| 세 번째로 큰 파일 | engine/model_manager.py (1,151줄) |
| config.yaml 콤보 수 | **12개** |
| 설정된 모델 총 수 | 30+ (reasoning/coding/embedding/vision별) |
| agent_roles | 10개 (CEO, ENG_MANAGER, ARCHITECT, WORKER, QA, CRITIC, DESIGNER, PROPOSER, ARBITER, default) |

---

## 2. 아키텍처 고도성 평가

### 2.1 우수한 설계 (High Points)

| 항목 | 평점 | 근거 |
|------|---|---|
| ** FSM 상태 전이** | 8.5/10 | AgentStateGraph가 명시적 전이 + 체크포인트. 설계 의도 vs 구현 일치. |
| **모델 라우팅** | 8/10 | 5전략 (fallback, round-robin, load-balance, collective, cascading) + 지수 백오프. COLLECTIVE 전략의 실제 구현 차이 제외. |
| **도구 가드레일** | 7.5/10 | before_call/after_call 패턴 + 동일 인자 감지 + 누적 실패 감지. 다만 executor와 별도라 통합 의존성 필요. |
| **동적 모델 관리** | 8/10 | 메모리 부족 시 자동 언로드 + LRU + UNAVAILABLE 추적. MLX + Ollama + LM Studio 멀티 백엔드. |
| **컨텍스트 압축** | 7.5/10 | LLM 요약 + 중요도 기반 선별 + RAG 보상. 전략적 접근이 좋아 보임. |
| **컨텍스트 트리** | 7/10 | AST/Markdown 인덱싱 + BFS beam search. 하지만 shallow indexing(depth 2)과 keyword-only scoring이 한계. |
| **시크릿 스캐너** | 7/10 | 10+ 시크릿 패턴 (OpenAI, Anthropic, GitHub, AWS 등). 다만 API 호출 시에만 동적 적용 — 코드 commit 시에는 아님. |
| **권한 게이트** | 8/10 | 3단계 (ALLOW/PROMPT/DENY) + 경로 샌드박스 + 시크릿 차단. Fail-Closed 안전 정책. |
| **자가 수복 (Immune System)** | 6.5/10 | Vault 스냅샷 + AST 유효성 검증 + 세션당 3회 제한. HITL 패턴 준수. |
| **품질 게이트** | 7/10 | A/B/C/F 등급 + 재시도 + 피드백 루프. pydantic BaseModel 기반 정형화. |

### 2.2 전반 아키텍처 고도성: **7.5/10**

**좋은 점:**
- MoE 기반 swarm 아키텍처로 모델 분산 설계
- 9Router 패턴으로 다층 fallback
- StateGraph로 상태 전이 명시적 관리
- 도구 실행 시 multi-layer guardrail (가드레일 + 권한 + 시크릿 + 서킷브레이커)
- 컨텍스트 압축 + RAG 보상 + 트리와크 기반 저장소

---

## 3. 완성도 평정 — 정량 지표

### 3.1 Security Score: **7.0 / 10**

| 하위 항목 | 점수 (0-10) | 근거 |
|-----------|---|---|
| 시크릿 감지 | 7 | 10개 이상의 시크릿 패턴. 하지만 **config.yaml에 API 키가 평문으로 저장됨** (`sk-ant...here`) |
| 시크릿 마스킹 | 8 | redact(), redact_full(), redact_url() 3단계. `is_memory_path()`, `strip_credentials()` |
| 권한 게이트 | 8 | 3단계 (ALLOW/PROMPT/DENY) + path sandbox + fail-closed |
| dangerous command 차단 | 7 | bash 명령어 패턴 차단. 하지만 정적 패턴 기반으로 우회 가능 |
| 네트워크 제한 | 6 | 정책 로드 실패 시 allow (empty allowed_domains). **기본값이 allow**. |
| secret_scanner hard_stop | 6 | `hard_stop_enabled: false`. 감지해도 차단 안 함 (경고만). |
| **종합** | **7.0** | **단, config.yaml에 API 키 평문 저장 + guardrails default allow가 가장 큰 취약점** |

### 3.2 Error Handling Score: **7.5 / 10**

| 하위 항목 | 점수 (0-10) | 근거 |
|-----------|---|---|
| try-except 커버리지 | 6 | 모든 하위 시스템이 try/except로 init. 하지만 **silent fail** 패턴이 많음 (init 실패 시 component=None) |
| 에러 분류 | 7 | error_classifier.py (445줄). classify_tool_failure(). 하지만 단순 regex 기반. |
| 에러 복구 | 7 | ImmuneSystem (self-heal + vault rollback) + CircuitBreaker + max_failures=3 |
| checkpointing | 5.5 | 체크포인트는 저장하지만 **restore 기능이 없음**. write-only. |
| graceful degradation | 7.5 | lazy init, component=None fallback, retry 등. 좋은 패턴 다수. |
| **종합** | **7.5** | **silent fail + checkpoint restore 누락이 주요 감점** |

### 3.3 Resilience Score: **7.0 / 10**

| 하위 항목 | 점수 (0-10) | 근거 |
|-----------|---|---|
| Circuit Breaker | 8 | 3회 실패 → OPEN → 60초 후 HALF-OPEN. 서킷 브레이커 구현. |
| Vault Rollback | 7 | 스냅샷 기반 백업 + rollback. 하지만 세션당 3회 제한. |
| Unavailable Tracking | 8 | 지수 백오프 쿨다운. 자동 cleanup. |
| Memory Management | 7.5 | 메모리 부족 시 자동 언로드. 하지만 **model_registry가 config.yaml에서 이미 로드된 모델 수를 모름**. |
| Thread Safety | 5 | `self.failures` 비원자 증가. `check_same_thread=False` SQLite. Race condition 위험. |
| **종합** | **7.0** | **스레드 세이프니스 + 메모리 관리가 핵심 감점 요소** |

### 3.4 Code Quality Score: **6.5 / 10**

| 하위 항목 | 점수 (0-10) | 근거 |
|-----------|---|---|
| SRP (단일 책임) | 5 | OrchestratorAgent가 15개 부속 시스템 관리. execute()가 8개 책임. worst offender. |
| DRY (중복 없음) | 5 | generate vs stream_generate 95% 중복. platform detection chain 중복. compress vs adaptive_compress 중복. |
| 모듈화 | 6.5 | engine/하위 구조화가 좋음. 하지만 orchestrator_handlers가 orchestrator internals에 직접 접근. |
| 테스트 가능성 | 5.5 | module-level singleton (GLOBAL_RTK_SAVER), hardcode된 paths, tight coupling. 단위 테스트 어려움. |
| docstring 품질 | 7.5 | 대부분 함수에 docstring 있음. 하지만 일부 설계 의도와 코드가 불일치. |
| **종합** | **6.5** | **중복과 god object가 가장 큰 문제. 테스트 가능성도 낮음.** |

### 3.5 전체 완성도 점수

| 항목 | 점수 | 가중치 | 가중치 점수 |
|------|---|---|---|
| 아키텍처 고도성 | 7.5 | 0.25 | 1.875 |
| 보안 | 7.0 | 0.20 | 1.400 |
| 에러 처리 | 7.5 | 0.15 | 1.125 |
| 복원력 | 7.0 | 0.15 | 1.050 |
| 코드 품질 | 6.5 | 0.15 | 0.975 |
| **총점** | | **1.0** | **6.425** |

---

## 4. 종합 완성도: **6.4 / 10** (D+ 수준)

### 요약: "아키텍처는 훌륭하지만 구현이 아직 불완전"

**강점:**
- MoE Swarm 아키텍처, 9Router 패턴, StateGraph 등 설계 패턴이 우수
- 다층 guardrail, dynamic model management, context compression 등 고급 기능 다수
- config.yaml 기반 정책 관리로 확장성 고려됨

**약점:**
- 코드의 중복 (DRY 위반)이 심함 (generate/stream_generate 95% 동점)
- OrchestratorAgent의 God Object화 (SMELL-01)
- 테스트 가능성 낮음 (singleton, hardcode, tight coupling)
- checkpoint write-only (restore 없음)
- config.yaml에 API 키 평문 저장

---

## 5. 핵심 SMELL 코드 및 우선순위

### CRITICAL (즉시 수정 필요)

| No | 문제 | 영향 | 수정 방안 |
|----|------|------|----------|
| C-01 | OrchestratorAgent god object (15+ 컴포넌트 init) | refactoring 위험, 테스트 불가 | Facade 패턴으로 컴포넌트 분리 |
| C-02 | generate() vs stream_generate() 95% 중복 | 변경 시 drift, DRY 위반 | 공통 _route() 메서드로 추출 |
| C-03 | Tool registration single point of failure | 한 도구 import 실패 → 전체 실패 | Plugin-based auto-discovery |
| C-04 | config.yaml API key 평문 저장 | 보안 위험 | vault 또는 env var 사용 |

### HIGH (이번 스프린트 내에서 수정)

| No | 문제 | 영향 | 수정 방안 |
|----|------|------|----------|
| H-01 | generate/stream_duplicate (250+ 줄 중복) | DRY 위반 | 공통 _route_implementation() |
| H-02 | execute() excessive responsibility (8개 책임) | 테스트/수정 어려움 | 단계적 분리 (validator → executor → recorder) |
| H-03 | COLLECTIVE 전략 누락 (route에서 fallback으로 매핑) | 설계-구현 불일치 | CollectiveIntelligenceEngine을 라우터에서 직접 호출 |
| H-04 | checkpoint write-only (restore 없음) | FSM 복구 불가 | restore_checkpoint() 구현 |
| H-05 | handler가 orchestrator 내부 직접 접근 | tight coupling | interface 기반 접근 |

### MEDIUM + LOW

| No | 문제 |
|----|------|
| M-01 | checkpoint의 redundant DDL |
| M-02 | estimate_confidence() heuristic 한계 |
| M-03 | ContextTree shallow AST indexing |
| M-04 | token estimation 부실 (len(text)//4) |
| M-05 | RTKTokenSaver unrelated file |
| M-06 | get_temperature_boost() random jitter |
| M-07 | NON_CRITICAL_STATES hardcoded |
| L-01 | save_checkpoint() redundant DDL |
| L-02 | IDEMPOTENT/MUTATING_TOOL_NAMES hardcoded |

---

## 6. 개선 우선순위 (개발 계획 개요)

1. **1순위**: generate/stream_generate 중복 제거 (50시간)
2. **2순위**: OrchestratorAgent split (80시간)
3. **3순위**: checkpoint restore 구현 (10시간)
4. **4순위**: COLLECTIVE 라우팅 전략 완전 구현 (30시간)
5. **5순위**: Tool registration pluginification (40시간)
6. **6순위**: execute() 단계적 분리 (60시간)
7. **7순위**: 환경/API 키 보안 개선 (10시간)
8. **8순위**: ContextTree deep indexing (30시간)
9. **9순위**: token estimation 개선 (5시간)
10. **10순위**: 테스트 가능성 개선 (단일톤 의존성 제거, 20시간)

**총 예상 개발 기간: 약 30일 (개발자 1인 기준)**

---

*보고서 작성 완료: 2026-05-12*
*분석 대상: src/antigravity_k/ 전체 + analysis/architecture_analysis.md에 상세 분석*
