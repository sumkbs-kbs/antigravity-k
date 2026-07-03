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
- Coverage configuration with minimum threshold (40%)
- py.typed marker for PEP 561 compliance
- LICENSE file (MIT)
- CHANGELOG.md (this file)

### Changed
- CORS middleware tightened from wildcard `*` to configurable origin list
- README updated to match actual project structure and features
- Server startup gracefully handles missing dashboard dist directory

### Fixed
- Bare `except` clauses with proper exception logging in critical paths
- Removed stale `controller_agent` import from tool_guardrails

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
