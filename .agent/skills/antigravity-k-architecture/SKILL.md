---
name: ANTIGRAVITY-K-ARCHITECTURE
description: Antigravity-K 시스템의 상세 아키텍처 및 코어 모듈 구성
tools:
  - read_file
  - view_file
---

# Antigravity-K Architecture

Antigravity-K는 로컬 환경(Apple Silicon M5 Max 등)에서 고도의 자율 주행 프로그래밍이 가능한 차세대 AI 에이전트 프레임워크입니다. 초기의 다중 에이전트 협업 엔진(Multi-Agent Collaboration)을 기반으로, 최신 상용 및 오픈소스 기술(oh-my-openagent, not-claude-code-emulator, AiShell)의 패턴들을 통합하여 극한의 안정성과 자율성을 갖춘 플랫폼으로 진화했습니다.

## 1. Core Principles (핵심 원칙)

1. **Git-First & Auto-checkpointing**: `vault.py` 엔진 기반으로 설계되어 모든 작업 지식과 상태 변경은 로컬 Git 레포지토리와 Chroma RAG 데이터베이스에 동기화됩니다. 워크플로우 진행 시마다 자동 스냅샷을 생성합니다.
2. **Precision & Safety First (해시 & 보안)**: Lintai 스캐너 및 Declarative SecurityPolicyEngine을 통한 명령어 차단은 물론, `Hash-Anchored Edits`를 통해 코드 오수정(Stale-line)을 원천 차단합니다.
3. **Intent-Driven Routing (의도 기반 라우팅)**: 사용자의 단일 프롬프트를 분석하여 가장 적합한 특화 에이전트(visual-engineering, ultrabrain 등)로 매핑하는 `IntentGate` 패턴을 사용합니다.
4. **Natural Language to OS (자연어 OS 제어)**: 터미널 명령어를 일일이 기억할 필요 없이, 인간과 에이전트 모두 `AiShell` 기술을 활용해 자연어로 운영체제를 자율 제어합니다.

---

## 2. System Architecture & Components

### 2.1 Agent Orchestration & Routing
- `src/antigravity_k/engine/intent_router.py`: **IntentGate**. 사용자 요청(Prompt)의 성격을 분석하여, 일반(quick), 심층(deep), UI/UX(visual-engineering), 아키텍처(ultrabrain) 등 최적의 서브 에이전트로 라우팅합니다.
- `src/antigravity_k/agents/team_manager.py`: 다중 에이전트 토론 엔진. Proposer, Critic, Reviewer가 앙상블로 토론하여 코드를 결정합니다.
- `src/antigravity_k/engine/slash_commands.py`: 슬래시(`/`) 커맨드 중앙 레지스트리. `/qa`, `/project`, `/compact`, `/aishell` 등을 통해 시스템을 직접 제어합니다.

### 2.2 Advanced Tooling & Safety (Oh-My-OpenAgent & AiShell 패턴)
- **`HashlineEditTool` & `ReadHashFileTool`**: 해시 기반 컨텍스트 매핑 도구. 파일을 읽을 때 라인별 해시를 부여하고, 편집 시 이 해시를 검증하여 잘못된 라인이 덮어씌워지는 것을 방지합니다.
- **`ASTGrepTool`**: 의미론적 코드 검색기. 정규식을 넘어서 코드의 AST(추상 구문 트리) 구조를 분석하여 치환/검색을 수행합니다.
- **`InitDeepContextTool`**: 깊은 컨텍스트 생성기. 대규모 프로젝트 디렉토리를 순회하며 로컬 폴더별로 분산된 `AGENTS.md` 지식 문서를 자동 생성/참조합니다.
- **`NaturalLanguageBashTool` (AiShell)**: 에이전트가 복잡한 셸(awk, sed 등) 문법 에러 없이 "자연어 의도"만으로 터미널을 실행하게 해주는 브릿지 도구입니다. 인간 사용자도 `/aishell` 명령어로 접근 가능합니다.

### 2.3 Model Manager & API Proxy (Not-Claude-Code-Emulator 패턴)
- **동적 Thinking Mode 주입기**: 모델명 호출 시 `:high`, `:low`, `:4096` 등 접미사를 통해 Anthropic API 등의 `budget_tokens` 파라미터와 `temperature=1` 설정을 동적으로 주입합니다.
- **지능형 Context Cache 제한 관리자 (Cache Limit Manager)**: Anthropic API의 엄격한 캐시 블록 제한(Max 4)을 회피하기 위해, 최상단 시스템 프롬프트(1개)와 최근 대화(3개)만 캐싱하고 중간 기록은 자동으로 쳐내어 API 크래시를 방지합니다.
- **Agent Footprint & Fingerprinting**: `x-antigravity-k-agent` 헤더와 고유 해시(cch)를 주입하여 다중 에이전트 환경에서 API 트래픽 및 과금 추적성을 확보합니다.

### 2.4 Security & Storage
- `src/antigravity_k/engine/audit_logger.py`: OCSF 준수 감사 로그 및 PII/Secret 마스킹 모듈.
- `src/antigravity_k/engine/vault.py` & `.chroma/`: 모든 아티팩트와 지식을 Git 스냅샷 및 벡터 DB로 듀얼-싱크(Dual-Sync) 처리합니다.
- `src/antigravity_k/engine/tool_guardrails.py`: 런타임에 블랙리스트 패턴, 네트워크 IO, 불법 명령어를 원천 차단합니다.

---

## 3. Workflow Example (End-to-End)
1. **Request Intake**: 사용자가 "자연어로 로그 지워줘" 혹은 복잡한 "기능 구현"을 요청.
2. **Intent Classification**: `IntentRouter`가 요청 성격을 분석하여 적합한 에이전트를 소환. (간단한 터미널 명령은 `/aishell`이 즉각 응답)
3. **Execution & Contextual Awareness**:
   - `InitDeepContextTool`로 현재 위치의 `AGENTS.md` 지역 규칙을 파악.
   - 코드 수정 필요 시 `HashlineEditTool`과 `ASTGrepTool`로 정밀 타격 수정.
4. **API Proxy Optimization**: `ModelManager`가 캐시 블록 오버플로우를 자동 방지하며 추론 깊이(`:high`)를 조율해 API 서버와 통신.
5. **Autopilot Checkout**: 작업 성공 후 `VaultEngine`을 통해 `vault_data/` 및 프로젝트 로컬에 `git commit` 생성.
6. **Review**: 사용자에게 워크플로우 아티팩트(`walkthrough.md`)가 반환되며 보고.

## 4. Usage in Prompts
이 스킬을 참조하면 Antigravity-K 프레임워크 자체를 개선하거나 확장할 때 어떤 파일을 수정해야 하는지 직관적으로 알 수 있습니다.
- "새로운 에이전트 라우팅 패턴 추가" -> `intent_router.py` 및 `team_manager.py` 참조.
- "API 통신 로직 및 핑거프린트 추가" -> `model_manager.py` 참조.
- "코드 정밀 수정 시스템 개선" -> `hashline_tools.py` 및 `ast_grep_tool.py` 참조.
- "자연어 기반 운영체제 제어" -> `slash_commands.py` (`/aishell`) 및 `system_tools.py` 참조.
