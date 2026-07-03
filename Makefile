# Antigravity-K Makefile
# =======================
# Commercial-grade task runner for development, testing, and deployment

.PHONY: help install dev test lint format clean build docker-build \
        docker-run coverage check ci-setup pre-commit

SHELL := /bin/bash
PYTHON := python3
PACKAGE := antigravity-k
VENV := .venv

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Environment ─────────────────────────────────────────────────

install: ## Install the package in development mode
	$(PYTHON) -m pip install -e ".[dev,rag,mlx]"

venv: ## Create virtual environment
	$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created. Activate with: source $(VENV)/bin/activate"

# ─── Development ──────────────────────────────────────────────────

dev: ## Start the development server with hot reload
	uvicorn antigravity_k.api.server:app --reload --host 0.0.0.0 --port 8000

dev-dashboard: ## Start the dashboard dev server
	cd dashboard && npm run dev

# ─── Linting & Formatting ─────────────────────────────────────────

lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/ scripts/

lint-fix: ## Run ruff linter with auto-fix
	$(PYTHON) -m ruff check --fix src/ tests/ scripts/

format: ## Format code with ruff
	$(PYTHON) -m ruff format src/ tests/ scripts/

format-check: ## Check formatting without changing files
	$(PYTHON) -m ruff format --check src/ tests/ scripts/

typecheck: ## Run mypy type checking
	$(PYTHON) -m mypy src/ --ignore-missing-imports --no-strict-optional || true

check: lint format-check typecheck ## Run all code quality checks

# ─── Testing ───────────────────────────────────────────────────────

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-quick: ## Run fast tests (exclude slow/benchmark)
	$(PYTHON) -m pytest tests/ -v --tb=short -m 'not slow and not benchmark'

test-benchmark: ## Run benchmark tests
	$(PYTHON) -m pytest tests/ -v --tb=short -m benchmark

coverage: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ -v --tb=short \
		--cov=src/antigravity_k \
		--cov-report=term-missing \
		--cov-report=html:coverage_html
	@echo "Coverage report generated: coverage_html/index.html"

# ─── Pre-commit ───────────────────────────────────────────────────

pre-commit: ## Install pre-commit hooks
	$(PYTHON) -m pip install pre-commit
	pre-commit install
	pre-commit run --all-files

pre-commit-run: ## Run pre-commit on all files
	pre-commit run --all-files

# ─── CI (local simulation) ────────────────────────────────────────

ci-setup: ## Simulate CI setup locally
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,rag]"

ci-check: lint format-check typecheck test-quick ## Simulate CI checks locally

# ─── Build & Package ──────────────────────────────────────────────

build: ## Build wheel and sdist
	$(PYTHON) -m pip install build
	$(PYTHON) -m build

clean: ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info
	rm -rf .coverage coverage_html/
	rm -rf .mypy_cache .ruff_cache
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

# ─── Docker ────────────────────────────────────────────────────────

docker-build: ## Build Docker image
	docker build -t antigravity-k:latest .

docker-run: ## Run Docker container
	docker run -d --name antigravity-k \
		-p 8000:8000 \
		-v $(PWD)/vault_data:/app/vault_data \
		antigravity-k:latest

docker-up: ## Start all services with Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Follow logs
	docker compose logs -f
