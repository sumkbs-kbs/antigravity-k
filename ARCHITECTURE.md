# Antigravity-K Architecture

## 1. Overview
Antigravity-K is a local-first, autonomous engineering agent system running primarily on Apple Silicon. The system is designed to minimize dependencies on commercial external APIs, relying on a robust, cross-validating MoE (Mixture of Experts) Swarm Architecture.

## 2. The MoE Swarm Architecture
Unlike traditional systems that assign a single model to a single role (e.g., `WORKER` = `qwen-coder`), Antigravity-K assigns **Swarm Combos** to roles. This ensures that no single model's biases or hallucinations dictate the final outcome.

### Core Swarm Combos
- **`orchestrator-swarm`** (CEO / Manager): Combines models like `gemma4` and `qwen3.6` to orchestrate tasks with a balanced, global perspective.
- **`coding-swarm`** (Worker): Employs a round-robin or fallback rotation of top coding models (`qwen2.5-coder`, `llama4`, `deepseek-r1`) to write, review, and test code. This guarantees cross-validation across different training bases.
- **`architect-swarm`** (Architect): Merges logic-heavy models (`deepseek`) with highly critical analysis models (`nemotron`) to establish flawless system structures.
- **`supreme-court`** (Arbiter): Utilizes massive 70B+ parameter models only for resolving agent deadlocks.

## 3. The 9Router Pattern (ModelManager & Router)
The `ModelRouter` dynamically loads combos from `config.yaml` and executes routing strategies:
- **Fallback**: Sequential attempts; if a model fails or OOMs, the next takes over.
- **Round-Robin**: Rotates through models across turns, driving the internal debate and multi-model consensus.
- **Load-Balance**: Selects the lightest model available depending on current RAM pressure.

## 4. Agent Capabilities & Self-Evolution
Agents within Antigravity-K possess "Tools" allowing them to perform system-level tasks:
- **Config Management**: Dynamically altering `config.yaml` to restructure swarms.
- **Wiki Exporting**: Synthesizing session learnings and saving them to the user's Obsidian Vault.
- **Self-Healing**: Scanning codebase health (e.g., namespace hygiene, fixing parser bugs) automatically.

## 5. Plan/Build Mode Separation

Phase 1 introduces explicit **Plan/Build/Interactive** execution modes to replace the previous implicit planning heuristic.

### 5.1 ExecutionMode

```python
class ExecutionMode(str, Enum):
    PLAN = "plan"         # 읽기 전용 도구 + write_artifact만 허용
    BUILD = "build"       # 모든 도구 허용 (Plan 승인 후 자동 진입)
    INTERACTIVE = "interactive"  # 기존 대화형 모드
```

**PLAN 모드 허용 도구:** `read_file`, `glob_search`, `grep_search`, `list_directory`, `hex_dump`, `git_status`, `git_log`, `git_diff`, `web_search`, `web_scrape`, `fetch_dom`, `search_knowledge`, `impact_analyzer`, `write_artifact`

**BUILD 모드 제한 도구:** `db_migration`, `deploy`, `payment`, `computer_use`, `agent_spawn` (추가 approval 필요)

### 5.2 ModeManager

`ModeManager`는 실행 모드의 상태 전이와 자동 Plan→Build 전환을 담당합니다.

```
ModeManager
├── current_mode: ExecutionMode
├── switch_to_plan(reason) / switch_to_build(plan_path) / switch_to_interactive()
├── can_auto_transition_to_build: bool  # Plan 아티팩트 생성 + QualityGate 통과
├── should_enforce_plan_mode(task_type, user_message) → bool
├── check_tool_permission(tool_name) → {allowed, reason, requires_approval}
└── format_status() → str
```

### 5.3 Plan→Build 자동 전환 플로우

```
사용자 요청 (복잡 태스크)
  │
  ▼
CEO 분석 → task_type="complex" 또는 PLAN_TRIGGER_KEYWORDS 매칭
  │
  ▼
switch_to_plan() → PLAN 모드 진입
  │  ├─ 읽기 전용 도구만 허용
  │  └─ Agent가 implementation_plan.md 생성
  │
  ▼
Plan 아티팩트 생성 완료 + QualityGate 통과
  │
  ▼
can_auto_transition_to_build == True → switch_to_build()
  │  ├─ 모든 도구 실행 허용
  │  └─ Plan 태스크 Kanban 자동 등록 (선택)
  │
  ▼
BUILD 모드 → 에이전트 실행
```

### 5.4 Integration Points

| 컴포넌트 | 역할 |
|:---|---|
| `execution_mode.py` | Enum + PLAN_ALLOWED_TOOLS / BUILD_RESTRICTED_TOOLS 정책 |
| `mode_manager.py` | 상태 관리, 전이, 자동 전환, 리스너 |
| `engine_context.py` | ModeManager 인스턴스 DI 등록 |
| `orchestrator/agent.py` | `_requires_planning_mode()` → `mode_manager.should_enforce_plan_mode()` 위임 |
| `plan_guard.py` | `execution_mode` 파라미터로 PLAN/BUILD 도구 제한 |
| `gate_pipeline.py` | `ApprovalGate`가 `ctx.execution_mode` 인지 |
| `quality_gate.py` | BUILD 모드에서 plan 체크 생략 |
| `orchestrator_handlers.py` | 모드에 따른 상태 노드 분기 |
| `slash_commands.py` | `/mode`, `/plan`, `/build` 명령어 |
| `cli.py` | `agk mode [plan|build|interactive|status]` |

#### 5.5 ArtifactEngine Enhancements

Phase 1 D2에서 `ArtifactEngine`에 Plan 검증/태스크 추출 기능을 추가했습니다.

**PlanTask** — Plan에서 추출된 개별 태스크:
| 필드 | 설명 |
|:---|---|
| `title` | 태스크 제목 |
| `description` | 상세 설명 (title에서 `:`, `—`, `-` 구분자 기준 분리) |
| `priority` | 우선순위 (`P0`/`P1`/`🔴`/`🟡`/`normal`) |
| `status` | 체크박스 상태 (`todo`/`done`) |
| `depends_on` | 의존성 태스크 (괄호 안 `depends on ...` 파싱) |
| `section` | 해당 태스크가 속한 Plan 섹션명 |

**PlanValidationResult** — Plan 완전성 검증 결과:
| 필드 | 설명 |
|:---|---|
| `is_complete` | 검증 통과 여부 (`score >= 0.6` + `missing_sections <= 1`) |
| `score` | 0.0~1.0 점수 (5개 섹션 가중치 합계) |
| `missing_sections` | 누락된 필수 섹션 목록 |
| `issues` | 발견된 문제점 (길이 부족, 체크박스 부족, 파일 참조 없음 등) |
| `task_count` | 추출된 태스크 수 |

**5개 필수 섹션 검증 기준:**
| 섹션 | 가중치 | 검증 패턴 |
|:---|---:|---|
| Overview | 0.20 | 개요/배경/목적 |
| Technical Approach | 0.25 | 기술/접근/방법론/아키텍처 |
| Implementation Steps | 0.25 | 구현/단계/Steps/작업 |
| Task List | 0.15 | 태스크/Task/체크리스트/할 일 |
| Timeline / Priority | 0.15 | 일정/기간/우선순위/Timeline/Milestone |

**주요 메서드:**
- `validate_plan_complete(target_file)` → `PlanValidationResult`
- `is_plan_ready_for_build(target_file)` → `bool` (Build 전환 조건 검사)
- `extract_plan_tasks(target_file)` → `list[PlanTask]`
- `auto_create_kanban_tasks(tasks, kanban_engine)` → 태스크 → KanbanBoard 변환
- `inject_planning_prompt()` → Plan→Build 자동 전환 조건을 system prompt에 포함

## 5.6 Mode CLI / Slash Commands

```bash
# CLI
agk mode status              # 현재 모드 확인
agk mode plan                # Plan 모드 전환
agk mode build --plan <path> # Build 모드 전환

# Slash
/mode [plan|build|interactive|status]
/plan [이유]
/build [plan_artifact_path]
```

## 6. Skills Marketplace (npm Registry)

Phase 1 introduces npm Registry-based Skills Marketplace for discovering, installing, and publishing reusable agent skills.

### 6.1 Package Structure

```
@antigravity-k/skill-<name>/
├── package.json              # npm 필수 + antigravityK 커스텀 필드
├── SKILL.md                  # YAML frontmatter + 본문 (기존 포맷 호환)
├── references/               # 참조 문서 (선택)
├── tests/                    # 스킬 테스트 (선택)
└── .agkignore                # 설치 시 제외 파일 (선택)
```

### 6.2 package.json Schema (`antigravityK` 필드)

| 필드 | 타입 | 설명 |
|:---|---|:---|
| `skill` | boolean | AGK 스킬 패키지 식별자 (`true`) |
| `displayName` | string | UI 표시 이름 |
| `categories` | string[] | 검색/탐색용 카테고리 |
| `minAgentVersion` | string | 필요 최소 AGK 버전 (`1.0.0`) |
| `platforms` | string[] | 지원 플랫폼 (`["darwin", "linux"]`) |
| `requiredTools` | string[] | 필수 도구 목록 |
| `optionalTools` | string[] | 선택 도구 목록 |
| `riskLevel` | enum | `safe` / `low` / `medium` / `high` / `critical` |
| `trustLevel` | enum | `local` / `verified` / `partner` / `experimental` |
| `requiresApproval` | boolean | 설치/활성화 시 승인 필요 여부 |
| `autoMatchKeywords` | string[] | CapabilityPolicy auto-match 키워드 |
| `mcp.serverId` | string | (MCP 스킬용) MCPServerRegistry 키 |
| `mcp.transport` | string | MCP transport (stdio/http/sse) |

### 6.3 Install Flow

```
agk market install @antigravity-k/skill-<name>
  │
  ├─ (1) npm install --no-save → node_modules/
  ├─ (2) package.json 검증 (antigravityK.skill, minAgentVersion, platforms)
  ├─ (3) Lintai 보안 스캔 (SKILL.md + references)
  ├─ (4) .agent/skills/market/<name>/ 로 복사
  ├─ (5) (MCP 스킬) .mcp.json 자동 설정
  ├─ (6) SkillLoader.refresh()
  └─ (7) node_modules 정리
```

### 6.4 Install Location

```
.agent/skills/
├── diagnose/              # 기존 로컬 스킬
├── market/                 # ← npm 설치 스킬
│   ├── code-review/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── .agk_meta.json
│   └── rag-pipeline/
└── auto-learned/           # 자동 학습 스킬
```

### 6.5 CLI / Slash Commands

```bash
agk market search <query>
agk market install <package>
agk market list
agk market update [package]
agk market remove <name>
agk market info <package>
agk market publish

/market search <query>
/market install @antigravity-k/skill-<name>
/market list
/market update
/market remove <name>
```

#### 6.7 SkillMarketClient

Phase 1 D8에서 구현된 npm Registry 기반 Marketplace 클라이언트.

**데이터 모델:**

| 모델 | 출처 | 주요 필드 |
|:---|---|:---|
| `SkillListing` | `npm search --json` | name, version, description, keywords, publisher, date, npm_url |
| `SkillDetail` | `npm view --json` | 전체 package.json + `antigravityK` 파싱 + MCP 설정 |
| `InstalledSkill` | `.agk_meta.json` + 상태 파일 | name, version, install_path, risk_level, trust_level |

**주요 메서드:**
- `search(query, limit=20)` — npm search 실행 → AGK 스킬 필터링 → 2-pass 키워드 fallback → 점수 정렬 (AGK:10 + 설명:5 + 이름:3 + 키워드:2)
- `search_by_category(category)` — `keywords:{category}` 래핑
- `get_detail(package_name)` — npm view --json → `antigravityK.skill`, `mcp`, `riskLevel` 등 파싱
- `get_installed(project_root)` — `.agent/skills/market/` 디렉토리 스캔 + 글로벌 상태 파일(`~/.antigravity-k/skills-market.json`) 이중 조회
- `is_installed(skill_name)` — 설치 여부 확인
- `record_installation(package, version, path)` — 상태 파일에 기록
- `remove_installation(skill_name)` — 설치 기록 제거
- `format_search_results(results)` → 마크다운 포맷 출력 (✅ 설치 표시)

**검색 점수 정렬:**
```python
# AGK 스킬 우선, 그 다음 설명/이름/키워드 매칭 순
score  = 10 if is_agk_skill else 0
score +=  5 if query in description else 0
score +=  3 if query in name else 0
score +=  2 if query in keywords else 0
```

## 6.8 npm Publish Workflow

GitHub Actions 기반 자동 publish:
- `npm version patch|minor|major` → 버전 bump
- `npx agk-skill-lint SKILL.md` → YAML frontmatter 검증
- `npm publish --dry-run` → 사전 점검
- `npm publish --access=public --provenance` → 실제 publish
- Git tag + GitHub Release 자동 생성
