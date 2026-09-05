# Phase 1: Plan/Build Mode Separation & Skills Marketplace

## Objective
Replace implicit planning heuristic with explicit Plan/Build/Interactive execution modes, and establish npm Registry-based Skills Marketplace for skill discovery and distribution.

## Duration: 21 Days (3 Weeks)

## Deliverables

### Week 1: Plan/Build Mode (Days 1-7)

| Day | Task | Files |
|:---|:---|---|
| **D1** | ✅ `ExecutionMode` enum + `ModeManager` | `execution_mode.py` (NEW), `mode_manager.py` (NEW) |
| **D2** | ✅ `ArtifactEngine` 강화 (plan 검증/태스크 추출) | `artifact_engine.py` (MODIFY) |
| **D3** | ✅ `PlanGuard` + `GatePipeline` 모드 연동 + CI 강화 | `tool_executor.py` (MODIFY), `engine_context.py` (MODIFY), `ci.yml` (MODIFY) |
| **D4** | ✅ Plan→Build 전이 파이프라인 | `plan_to_build.py` (NEW) |
| **D5** | ✅ `OrchestratorAgent` 모드 분기 + `QualityGate` 연동 | `orchestrator/agent.py` (MODIFY), `quality_gate.py` (MODIFY) |
| **D6** | ✅ CLI + TUI 모드 인디케이터 + `/plan` `/build` `/status` | `cli.py` (MODIFY), `tui/app.py` (MODIFY), `tui/widgets.py` (MODIFY) |
| **D7** | ✅ Dashboard 모드 상태 표시 + WebSocket 연동 | `mode_manager.py` (MODIFY), `events.py` (MODIFY), `system_api.py` (MODIFY), `dependencies.py` (MODIFY), `dashboard/index.html` (MODIFY), `dashboard/src/main.js` (MODIFY) |

### Week 2: Skills Marketplace (Days 8-14)

| Day | Task | Files |
|:---|:---|---|
| **D8** | ✅ `SkillMarketClient` (npm search/view 래핑) | `skill_market_client.py` (NEW) |
| **D9** | `SkillInstaller` (npm install → .agent/skills/) | `skill_installer.py` (NEW) |
| **D10** | `SkillMarketRegistry` (설치된 마켓 스킬 관리) | `skill_market_registry.py` (NEW) |
| **D11** | ✅ MCP → Skill 마운트 (`MCPServerRegistry` 통합) | `mcp_tool_loader.py` (MODIFY), `skill_installer.py` (MODIFY) |
| **D12** | CLI + 슬래시 명령어 (`agk market ...`, `/market ...`) | `cli.py` (MODIFY), `slash_commands.py` (MODIFY) |
| **D13** | `SkillLoader` market 디렉토리 연동 + 통합 테스트 | `skill_loader.py` (MODIFY) |
| **D14** | 버퍼: Week 2 누락/지연 작업 마무리 | — |

### Week 3: Integration & Polish (Days 15-21)

| Day | Task |
|:---|---|
| **D15** | ✅ Plan/Build + Skills 통합 시나리오 E2E 테스트 |
| **D16** | Dashboard 모드 인디케이터 + Skills 브라우저 UI |
| **D17** | Skill publish (로컬 → GitHub PR / npm publish) |
| **D18** | Skill 평점/리뷰 시스템 베이스 (GitHub Issues) |
| **D19** | `SkillAutoLearner` publish 연동 |
| **D20** | 성능 최적화 + 문서화 |
| **D21** | 최종 리뷰 + 데모 준비 |

## Timeline Visualization

```
Week 1: Plan/Build Mode (D1-D7)
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ D1  │ D2  │ D3  │ D4  │ D5  │ D6  │ D7  │
│Mode │Artf │Guard│P→B  │Orch │CLI/ │통합  │
│Enum │Eng  │연동 │Pipe │분기 │TUI  │테스트│
│+Mgr │강화 │     │     │+QG  │     │     │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┘

Week 2: Skills Marketplace (D8-D14)
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ D8  │ D9  │ D10 │ D11 │ D12 │ D13 │ D14 │
│Mkt  │Inst │Reg  │MCP  │CLI/ │Skill│버퍼  │
│Client│aller│istry│마운트│Slash│Loadr│     │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┘

Week 3: 통합 + 고도화 (D15-D21)
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ D15 │ D16 │ D17 │ D18 │ D19 │ D20 │ D21 │
│E2E  │Dash │Skill│GitH │Auto │성능 │최종 │
│통합 │보드 │publ │ub   │Learn│최적 │리뷰 │
│테스 │UI   │ish  │Issu │publ │화+  │+    │
│트   │     │     │es   │ish  │문서 │데모 │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

## Architecture Decisions

### ADR 1: Plan→Build 자동 전환
- Plan 아티팩트(`implementation_plan.md`) 생성 완료 + `QualityGate` 통과 시 자동 Build 모드 진입
- 별도 사용자 승인 불필요 (config.yaml에서 `auto_transition: false`로 비활성화 가능)
- Build 실패 시 `mode_manager.auto_revert_on_failure()`로 자동 Plan 모드 복원

### ADR 2: npm Registry 기반 Marketplace
- 스킬 패키지: `@antigravity-k/skill-<name>` scoped package
- 검색: `npm search` keywords 매칭 → AGK 스킬 점수 정렬
- 설치: `npm install --no-save` → `.agent/skills/market/` 복사 → `node_modules` 정리
- publish: GitHub Actions (`npm publish --provenance`)
- 보안: Lintai 스캔 + `requiresApproval: true` 기본값

### ADR 3: SkillLoader 호환성
- `SKILL.md` 포맷은 기존과 100% 동일 유지 → 추가 파싱 코드 불필요
- `package.json`의 `antigravityK` 필드가 메타데이터 소스
- 설치 위치: `.agent/skills/market/<name>/` (기존 로컬 스킬과 충돌 방지)
- 설치된 마켓 스킬은 `SkillLoader`가 자동 로드

## Risk Management

| 리스크 | 영향 | 완화 전략 |
|:---|:---|:---|
| Plan→Build 자동 전환으로 인한 원치 않는 코드 변경 | 사용자 데이터 손실 | `mode_manager.auto_revert_on_failure()` — Build 실패 시 자동 복원 |
| npm 패키지 스킬의 보안 위험 | 악의적인 SKILL.md 실행 | Lintai 보안 스캔 + `requires_approval: true` 기본값 |
| 스킬 호환성 (구버전 AGK) | 설치 실패 | package.json의 `minAgentVersion` 필드로 호환성 검증 |
| MCP 서버 중단 | 스킬 기능 불능 | `skill_installer`에 헬스 체크 + 폴백 메시지 |

## Completed Tasks

### D1 ✅ ExecutionMode + ModeManager
- `src/antigravity_k/engine/execution_mode.py` — `ExecutionMode` enum + `PLAN_ALLOWED_TOOLS` / `BUILD_RESTRICTED_TOOLS`
- `src/antigravity_k/engine/mode_manager.py` — `ModeManager` (상태 전이, 자동 전환, 리스너)
- Integration: 8 modified files (engine_context, agent.py, plan_guard, gate_pipeline, quality_gate, slash_commands, cli, orchestrator/setup)
- Lint: 0 errors

### D2 ✅ ArtifactEngine 강화
- `PlanTask`, `PlanValidationResult` dataclass 추가
- `validate_plan_complete()` — 5개 필수 섹션 검증 (Overview, Technical Approach, Implementation Steps, Task List, Timeline)
- `extract_plan_tasks()` — 체크박스 파싱 + 섹션 그룹화 + 우선순위/의존성 감지
- `auto_create_kanban_tasks()` — Plan → KanbanBoard 자동 변환
- `list_artifacts()`, `delete_artifact()`, `summarize_plan()` 보조 메서드
- Lint: 0 errors

### D3 ✅ PlanGuard + GatePipeline 모드 연동 + CI 강화
- `ToolExecutor.execute()`에 `execution_mode` 파라미터 추가
- `PlanGuard.evaluate_tool_call()` wiring (PLAN: 읽기전용 도구만 허용, BUILD: restricted 도구 승인 필요)
- `GatePipeline` wiring (RateLimitGate → ApprovalGate → SecurityPolicyGate 순차 평가)
- `EngineContext`에서 PlanGuard + GatePipeline 생성 및 ToolExecutor 주입
- `OrchestratorAgent._execute_tool()` → execution_mode 전달
- CI 워크플로우 강화: build job, coverage PR comment, scheduled trigger, workflow_call
- Lint: 0 errors

### D4 ✅ Plan→Build 자동 전환 파이프라인
- `TransitionPhase`, `TransitionStep`, `TransitionResult` 데이터 모델
- `run()` 4단계: plan 검증 → quality check → mode 전환 → kanban 생성
- `quick_check()` 건식 검증 + `format_status()` 상태 리포트
- ModeManager + QualityGate + ArtifactEngine 통합
- Lint: 0 errors

### D5 ✅ OrchestratorAgent 모드 분기 + QualityGate 연동
- `_inject_mode_prompt()` 신규 — PLAN/BUILD/INTERACTIVE별 system prompt 분기
- `_get_execution_mode()` 신규 — mode_manager에서 현재 모드 문자열 반환
- `QualityGate.evaluate()` + `_check_output_contract()` execution_mode 파라미터 추가
- Plan 검증 시 코드 블록 체크 생략 (execution_mode="plan" early return)
- `orchestrator_handlers.py`, `plan_to_build.py`에 execution_mode 전파
- Lint: 0 errors

### D6 ✅ CLI + TUI 모드 인디케이터
- `cli.py status()` — ModeManager.format_status()를 Rich Panel에 표시
- `tui/widgets.py StatusFooter` — `mode_name` reactive 추가 (📋 PLAN / 🔨 BUILD / 💬 INTERACTIVE)
- `tui/app.py ChatScreen` — ModeManager 생성 + SlashCommandRegistry에 전달
- TUI 피드백 루프: `/plan` → ModeManager → StatusFooter.mode_name 자동 업데이트
- `/plan`, `/build`, `/status` slash commands 동작 확인
- Lint: 0 errors

### D7 ✅ Dashboard 모드 상태 표시 + WebSocket 연동
- ModeManager._publish_to_eventbus() — 모드 변경 시 EventBus로 ModeChanged 이벤트 발행
- WebSocket `/v1/ws/events` — ModeChanged 이벤트 구독 추가 (Dashboard 실시간 전달)
- API `GET /api/system/mode` — 현재 실행 모드 반환 (ModeManager 싱글톤 기반)
- Dashboard sidebar — `#mode-indicator` UI (📋 PLAN yellow / 🔨 BUILD green / 💬 INTERACTIVE cyan)
- Dashboard WebSocket 핸들러 — ModeChanged 수신 시 실시간 모드 표시 업데이트 + 토스트 알림
- Dashboard 자동 재연결 — WebSocket 끊김 시 10초 후 자동 재연결
- Lint: 0 errors

### D8 ✅ SkillMarketClient
- `SkillListing`, `SkillDetail`, `InstalledSkill` 데이터 모델
- `search(query, limit)` — npm search 실행 → AGK 스킬 필터링 → 점수 정렬
- `search_by_category(category)` — 카테고리별 검색
- `get_detail(package_name)` — npm view 실행 → `antigravityK` 필드 파싱
- `get_installed()`, `is_installed()` — 로컬 설치 상태 관리
- `record_installation()`, `remove_installation()` — 상태 파일 입출력
- Lint: 0 errors

### D9 ✅ SkillInstaller
- `InstallValidation`, `SecurityReport`, `InstallResult` 데이터 모델
- 9단계 설치 플로우: npm install → 검증 → 보안 스캔 → market 복사 → MCP 설정 → 메타 → 기록 → 로더 갱신 → 정리
- `install()`, `update()`, `remove()` 메서드
- 엣지 케이스: npm CLI 미설치, 타임아웃, non-AGK 패키지 거절, 버전/플랫폼 검증
- Lint: 0 errors

### D10 ✅ SkillMarketRegistry
- `RegistrySkillInfo` 통합 데이터 모델
- 3개 서브시스템 통합 API: SkillMarketClient + SkillInstaller + SkillLoader
- `search()`, `get_detail()`, `install()`, `remove()`, `update()`, `update_all()`, `list_installed()`, `get_info()`, `check_updates()`
- `format_list()`, `format_info()`, `summary()` UI 포맷 함수
- Lint: 0 errors

### D11 ✅ MCP → Skill 마운트 (MCPServerRegistry 통합)
- `MCPServerRegistry._skill_servers` (클래스 레벨) — 스킬 등록 MCP 서버 저장소
- `register_skill_mcp()`, `unregister_skill_mcp()`, `get_skill_mcp_servers()`, `list_skills_with_mcp()` 신규
- `get_all()`, `get_by_category()`, `generate_config()` — 스킬 서버 포함하도록 확장
- `generate_config_with_skills()` — 추천 + 스킬 서버 통합 .mcp.json 생성
- `MCPToolLoader.load_skill_servers` 파라미터 — 스킬 등록 MCP 서버에서 도구 로드
- `_load_skill_mcp_servers()` — MCPServerRegistry → MCPToolLoader 도구 자동 로드
- `_connect_and_load_servers()` 리팩토링 — 표준/스킬 서버 공통 연결 로직
- `SkillInstaller._setup_mcp()` — MCPServerRegistry 등록 + 3가지 case 처리 (카탈로그/package.json 직접/미발견)
- `SkillInstaller._write_meta()` — mcp_config 추출 저장
- Lint: 0 errors

### D12 ✅ CLI + 슬래시 명령어 (agk market ..., /market ...)
- `cli.py` — `agk market` 명령어 7개 옵션: `--search/-s`, `--install/-i`, `--remove/-r`, `--info`, `--list/-l`, `--update/-u`, `--update-all/-U`
- `slash_commands.py` — `/market` 슬래시 명령어 6개 서브커맨드: `search`, `install`, `remove`, `list`/`ls`, `info`, `update` (name 생략 시 전체 업데이트)
- CLI는 `SkillMarketClient` + `SkillMarketRegistry` 의존성 직접 생성 (기존 패턴 준수)
- Slash 명령어는 `SkillMarketRegistry`에 `skill_loader` 전달 (로드 상태 연동)
- 엣지 케이스 처리: ImportError graceful fallback, 미설치 스킬 info → npm 직접 조회 fallback
- Lint: 0 errors

### D13 ✅ SkillLoader market 디렉토리 연동 + 통합 테스트
- `skill_loader.py` — `include_market` 파라미터 추가, `refresh()` 3개 소스 스캔 (글로벌 → 로컬 → 마켓)
- `_load_from_dir()` — `skip_dir` 파라미터 추가 (로컬 스캔 시 market/ 제외), `source` 메타데이터 태깅
- `_load_market_skills()` 신규 — `.agent/skills/market/<name>/SKILL.md` 자동 로드, source="market" 태깅
- `list_skills_by_source(source)` 신규 — 소스별 스킬 필터링
- `get_market_skills()` 신규 — 마켓 스킬만 조회
- `skills_registry.py` — `_load_dynamic_skills()`에 market/ 디렉토리 스캔 추가
- Lint: 0 errors, tests: 64/64 passed

### D15 ✅ Plan/Build + Skills 통합 시나리오 E2E 테스트
- `tests/test_phase1_e2e.py` (신규) — D8~D15 Phase 1 전체 통합 E2E 24개 테스트
- **D8-D10 SkillMarketRegistry** (6 tests): list_installed/empty, get_info nonexistent, installer 미설치 에러, format_list/format_info, summary
- **D9 SkillInstaller** (4 tests): parse_skill_name, version_compare, security_scan safe/suspicious, write_meta
- **D11 MCPServerRegistry** (7 tests): register/get/unregister/list/get_all+skill/generate_config_with_skills
- **D13 SkillLoader Market** (5 tests): market_dir, load_market_skills, list_skills_by_source, load_order (market wins), include_market=False
- **D13 SkillsRegistry Market** (1 test): market SKILL.md → SkillProfile 로드 확인
- **E2E FullLifecycle** (1 test): Interactive→Plan→Build→SkillLoader→MCP→MarketRegistry→Interactive
- Lint: 0 errors, tests: 24/24 passed
