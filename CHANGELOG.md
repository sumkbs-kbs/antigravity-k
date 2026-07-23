# Changelog

All notable changes to Antigravity-K will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pre-commit hooks configuration (ruff, mypy, trailing-whitespace, etc.)
- EditorConfig for consistent coding styles
- Makefile with development, testing, linting, deployment, and Docker Compose targets
- CONTRIBUTING.md contribution guide
- .env.example environment variables template
- Dockerfile (multi-stage build) for production deployment
- docker-entrypoint.sh with env var passthrough
- docker-compose.yml for local development with healthcheck and volume mounts
- .dockerignore for optimized Docker build context
- config.yaml.example YAML configuration template
- CI workflow for code quality checks (ruff, mypy, pytest, coverage, security-scan, dashboard)
- Coverage configuration with minimum threshold (40%, later raised to 55%)
- py.typed marker for PEP 561 compliance
- LICENSE file (MIT)
- CHANGELOG.md (this file)
- GitHub-Style Alerts rendering (5종: NOTE/TIP/IMPORTANT/WARNING/CAUTION) with colored borders and icons
- Mermaid diagram SVG rendering with loading/error states (Phase 18)
- Carousel slideshow with navigation dots and fade animation (Phase 18)
- `formatContent.ts` preprocessor for GitHub Alert blockquote conversion (Phase 18)
- CSS styling for advanced markdown: tables, mermaid, carousel, code blocks (Phase 18)
- Playwright E2E test framework with 45 tests across 7 spec files (Phase 21)
  - `chat.spec.ts` — 7 tests for chat input, send, typing indicator, history
  - `file-explorer.spec.ts` — 7 tests for file tree, search, toolbar
  - `git.spec.ts` — 9 tests for tabs, branches, graph, history
  - `navigation.spec.ts`, `health.spec.ts`, `command-palette.spec.ts`
- Dashboard page object model (`DashboardPage.ts`) with reusable selectors (Phase 21)
- CI workflow E2E test step (Playwright install + build + test) (Phase 21)
- axe-core accessibility audit integration (Phase 22)
  - ARIA labels on all interactive elements
  - Focus management tests for command palette
  - Keyboard navigation tests for sidebar
- OpenAPI/Swagger metadata: OAuth2 security scheme, servers list, contact info (Phase 24)
- Swagger UI OAuth2/authorize button with password flow (Phase 26)
- User onboarding guide (`ONBOARDING.md`) (Phase 24)
- In-memory API response cache layer (`api_cache.py`) (Phase 28)
  - `ApiCache` class with asyncio.Lock thread safety
  - `@cached` decorator for FastAPI endpoints (sync/async support)
  - Tag-based invalidation (TAG_GIT, TAG_FILESYSTEM, TAG_MODELS, etc.)
  - LRU-approximate max_size eviction (default 1000) with `last_accessed_at` tracking
  - Hit/miss statistics, periodic cleanup (300s interval)
- 19 cached GET endpoints: git(4) / agent(6) / system(6) / filesystem(3) (Phase 28)
- 9 mutation endpoints with cache invalidation (Phase 28)
- Cache statistics widget (`CacheStatsPanel`) with 4 metric cards, progress bar, entry list (Phase 29)
- `GET /api/system/cache-stats` endpoint (Phase 29)
- Dynamic log level management (`log_level_manager.py`) (Phase 30)
  - `LogLevelManager` with thread-safe level changes
  - Debug mode toggle (enable/disable, save/restore original levels)
  - 80+ KNOWN_LOGGERS coverage
- Log level API endpoints (Phase 30):
  - `GET /api/system/log-level` — list all loggers
  - `POST /api/system/log-level` — set specific logger
  - `POST /api/system/log-level/all` — set all loggers
  - `POST /api/system/debug-mode` — toggle debug mode
- `LogLevelSection` UI component in SettingsPage (Phase 30)
  - Debug mode toggle with visual state
  - Quick actions (all DEBUG, all INFO)
  - Per-logger level selector with dropdown
  - Color-coded logger list with expand/collapse
- `useGlobalCommandPalette` hook extracted to `hooks/` directory (Phase 31)
- `SidebarFallback` loading skeleton component (Phase 34)
- E2E Playwright test expansion (Phase 27): chat 전송, file explorer, git 연동 시나리오 (10→45 tests)
- Vitest 394개 단위 테스트 전면 통과 검증 (Phase 36)
- Accessibility E2E (Phase 37): 12 color-contrast tests passing (--text-muted, .status-bar, rgba fixes)
- **Phase 39**: `tests/test_worktree_manager.py` — 16 tests (init, create, remove, get_path)
- **Phase 41**: Coverage gap tests: `cost_guard` (20), `secret_scanner` (12), `artifact_engine` (20) = 52 new tests
- Vitest coverage report (Phase 43): `@vitest/coverage-v8` provider, Statements 58.3%
- **Phase 45**: Coverage push tests: 112 new tests:
  - `test_prompt_builder.py` (40 tests) — 23%→97%
  - `test_error_classifier.py` (+35 tests) — 27%→96%
  - `test_autonomous_qa.py` (+17 tests) — 50%→69%
  - `test_self_evolution_coordinator.py` (30 tests) — 21%→36%
  - `test_log_level_manager.py` (18 tests) — 24%→92%
  - `test_failure_memory.py` (22 tests) — 23%→89%
- `dashboard/coverage/` HTML + LCOV coverage reports configured (Phase 45)
- **Phase 46**: Coverage push tests: 78 new tests:
  - `test_external_brain.py` (20 tests) — 21%→31%
  - `test_harness.py` (12 tests) — 20%→25%
  - `test_autonomous_qa.py` (+10 async method tests)
- **Phase 47**: Dashboard Vitest coverage:
  - `gitStore.test.ts` (30 tests) — 28%→80.7%
  - `PublishTab.test.tsx` (10 tests) — 12%→35%

### Changed
- CORS middleware tightened from wildcard `*` to configurable origin list
- Server startup gracefully handles missing dashboard dist directory
- README updated to match actual project structure and features
- Server: `/api/auth/verify` endpoint added + CORS OPTIONS bypass in auth middleware (Phase 38)
- `test_e2e_smoke.py` default port 8400→8000 (Phase 38)
- `ExternalBrainRouter.__init__` adapters falsy check fixed (`adapters or [...]` → `adapters if adapters is not None else [...]`) (Phase 46)
- CI workflow: coverage threshold increased from 40% to 55% (Phase 21)
- `web_search.py` refactored: 1254 lines → split into `web_search.py` + `web_search_models.py` (Phase 23)
  - `SearchCache` with category-based TTL (weather 0h, finance 0.5h, news 1h, technical 72h)
  - Fallback query generation (6 strategies)
  - `depth` parameter for deep search mode
  - Self-Hosted search methods unified
- `DataExtractor` enhanced with TOP 1 JSON extraction and 종목명 검증 (Phase 23)
- `api_cache.py`: `set()` now calls `_evict_if_over_limit()` with LRU-approximate eviction (Phase 28)
- Dashboard bundle optimization (Phases 31-35):
  - 7 modal/overlay components converted to `React.lazy` (Phase 31)
  - `markdown` chunk split into `markdown-core` + `markdown-highlight` (Phase 32)
  - `dompurify` separated into own chunk (Phase 32)
  - `Sidebar` converted to `React.lazy` (Phase 34)
  - `@tanstack/react-query` separated from `vendor` into `query` chunk (Phase 35)
  - `diff` moved from main bundle to `utils` chunk (Phase 35)
- Main entry chunk reduced from 58 kB → 30 kB (48% reduction across Phases 31-35)

### Fixed
- Bare `except` clauses with proper exception logging in critical paths
- Removed stale `controller_agent` import from tool_guardrails
- Bare `except` clauses converted to specific exception types (Phase 20):
  - `web_search.py`: `httpx.RequestError`, `json.JSONDecodeError`, `ConnectionError` (15 cases)
  - `orchestrator/agent.py`: specific exceptions (10 cases)
  - `engine/autonomous_qa.py`, `skill_installer.py`, `self_evolution_coordinator.py`
- TypeScript type errors 5건 (Phase 33):
  - `ChatMessage.tsx`: `chatMessageAreEqual`에 `export` 키워드 추가
  - `SearchPanel.test.tsx`: `vi.mocked` → `as any` 캐스트 (6곳)
  - `CacheStatsPanel.tsx`: `'stats' in data` / `'error' in data` 타입 가드
  - `plugin_integration.test.ts`: `afterEach` import 추가 + `commit()` 인자 수정
- `CommandPalette.tsx`: dead code (`useGlobalCommandPalette` + `isMonacoFocused`) 제거 (Phase 31)

### Security
- CORS origin list made configurable via `config.yaml`
- Added automated secret scanning in CI pipeline

## [0.1.0] - 2026-04-26

### Added
- Initial release of Antigravity-K Local Autonomous Engineering Agent
- MLX-based local inference engine with model registry
- Multi-agent orchestration with state graph
- RAG pipeline with ChromaDB vector store
- Security policy engine with fail-closed pattern
- Dashboard with chat, wiki, settings, and system monitoring
- Benchmark harness with performance regression testing
- GitHub Actions CI/CD workflows
- Internationalization (ko/en/ja)
- Structured JSON logging with rotation
