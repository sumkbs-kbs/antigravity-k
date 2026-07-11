<div align="center">

# Antigravity-K 🚀

**완전 로컬 자율형 엔지니어링 에이전트 — Apple Silicon 최적화**

[![CI](https://github.com/sumkbs-kbs/antigravity-k/actions/workflows/ci.yml/badge.svg)](https://github.com/sumkbs-kbs/antigravity-k/actions/workflows/ci.yml)
[![Benchmark Dashboard](https://img.shields.io/badge/📊_Benchmark_Dashboard-GitHub_Pages-9C27B0?style=for-the-badge)](https://sumkbs-kbs.github.io/antigravity-k/benchmark/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/badge/code_style-ruff-000000)](https://github.com/astral-sh/ruff)

</div>

---

> 인터넷 의존 없이 Apple Silicon M5 Max (128GB Unified Memory) 위에서 완벽히 로컬로 동작하는 자율형 엔지니어링 에이전트입니다.
> MLX 기반 70B+ 로컬 추론, 다중 모델 Swarm 라우팅, ReAct 패턴 에이전트, RAG 파이프라인을 하나의 시스템으로 통합합니다.

## 기능

| 기능 | 설명 |
|:---|---:|
| 🧠 **로컬 추론 엔진** | MLX/mlx-lm 기반 70B+ 모델, Apple Silicon 네이티브 최적화 |
| 🌐 **집단지성 (MoE Swarm)** | 다중 모델 교차 검증 및 토론 라우팅 |
| 🤖 **자율 에이전트** | ReAct 패턴 + 도구 호출 + 자가 진화 (Self-Evolution) |
| 🔗 **RAG 파이프라인** | ChromaDB + 임베딩 + AST 기반 코드 인덱싱 |
| 👁 **멀티모달 비전** | mlx-vlm 기반 이미지/문서 분석 |
| 🛡️ **보안** | 접근 PIN 인증, 시크릿 스캐너, 선언적 보안 정책, Fail-Closed |
| 📊 **벤치마크 대시보드** | GitHub Pages 자동 배포 + 성능 회귀 테스트 |
| 🌍 **다국어 지원** | 한국어/English/日本語 인터페이스 |
| 📝 **구조화된 로깅** | JSON 기반 로깅 + 일별 로테이션 + 감사 로그 |
| 💰 **비용 제어** | 일일 예산, 시간당 Rate Limit, 모델별 과금 추정 |

## 빠른 시작

### 필수 조건

- **macOS** (Apple Silicon M 시리즈)
- **Python 3.12+**
- **(선택) Docker** — 샌드박스 코드 실행

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/sumkbs-kbs/antigravity-k.git
cd antigravity-k

# 2. 환경 설정
python3 -m venv .venv
source .venv/bin/activate

# 3. 패키지 설치
pip install -e ".[dev,rag,mlx]"   # 모든 기능
pip install -e ".[dev]"            # 기본 개발 환경만

# 4. (선택) Pre-commit 훅 설치
pip install pre-commit
pre-commit install

# 5. (선택) 대시보드 빌드
cd dashboard && npm ci && npm run build && cd ..
```

### 실행

```bash
# API 서버 실행
make dev
# 또는 직접: uvicorn antigravity_k.api.server:app --reload --host 0.0.0.0 --port 8000

# CLI 실행
agk

# 대시보드 개발 서버 (별도 터미널)
make dev-dashboard
# 또는: cd dashboard && npm run dev
```

## 프로젝트 구조

```
antigravity-k/
├── src/antigravity_k/          # 메인 패키지
│   ├── engine/                 # 코어 엔진
│   │   ├── orchestrator.py     # 오케스트레이터 (상태 그래프)
│   │   ├── model_manager.py    # 모델 관리
│   │   ├── model_registry.py   # 모델 레지스트리
│   │   ├── model_router.py     # 모델 라우터 (9Router)
│   │   ├── rag_indexer.py      # AST 기반 RAG 인덱서
│   │   ├── vault.py            # Git-First Vault 엔진
│   │   ├── security_policy.py  # 선언적 보안 정책
│   │   ├── quality_gate.py     # 품질 검증 게이트
│   │   ├── cost_guard.py       # 비용 제어 가드
│   │   ├── secret_scanner.py   # 시크릿 스캐너
│   │   ├── error_classifier.py # API 에러 분류
│   │   ├── tool_guardrails.py  # 도구 호출 가드레일
│   │   ├── tool_loop.py        # 도구 실행 루프
│   │   ├── tool_executor.py    # 도구 실행기
│   │   ├── memory/             # 메모리 프로바이더
│   │   ├── code_intel/         # 코드 인텔리전스
│   │   └── provider_adapters/  # LLM 프로바이더 어댑터
│   ├── agents/                 # 에이전트 구현
│   │   ├── coordinator.py      # 코디네이터
│   │   ├── base_agent.py       # 베이스 에이전트
│   │   ├── scout_agent.py      # 모델 스카우트
│   │   └── trainer_agent.py    # 트레이너
│   ├── api/                    # FastAPI 서버
│   │   ├── server.py           # 메인 서버 (CORS, 미들웨어, 헬스체크)
│   │   ├── models.py           # Pydantic 모델
│   │   ├── routes/             # API 라우트
│   │   └── dependencies.py     # 의존성 주입
│   ├── tools/                  # 도구 구현 (50+)
│   ├── security/               # 보안 모듈
│   ├── knowledge/              # 지식 관리 (Wiki, Memory)
│   ├── cli.py                  # Typer CLI
│   ├── config.py               # Pydantic 설정 관리
│   └── i18n.py                 # 다국어 지원
├── dashboard/                  # 웹 대시보드 (Vite + Vanilla JS)
├── tests/                      # 테스트 스위트 (70+ 파일)
├── scripts/                    # 유틸리티 스크립트
├── docs/                       # 문서
├── .github/workflows/          # GitHub Actions CI/CD
├── Makefile                    # 태스크 러너
├── Dockerfile                  # 컨테이너 배포
└── docker-entrypoint.sh        # Docker 엔트리포인트
```

## 기술 스택

| 계층 | 기술 | 역할 |
|:---|---:|:---|
| 추론 엔진 | MLX / mlx-lm | Apple Silicon 네이티브 LLM 추론 (70B+) |
| 비전 | mlx-vlm | 멀티모달 이미지/문서 분석 |
| 벡터 DB | ChromaDB | 로컬 임베딩 저장/검색 |
| 코드 인덱싱 | AST + RAGIndexer | 소스 코드 그래프 인덱싱 |
| API 서버 | FastAPI + uvicorn | OpenAI 호환 REST API |
| 설정 관리 | Pydantic Settings + YAML | 환경변수/파일 설정 |
| 대시보드 | Vite + Vanilla JS | 시스템 모니터링 UI |
| 로깅 | 구조화된 JSON + 로테이션 | 추적성 (Traceability) |
| i18n | 자체 번역 시스템 | 한국어/English/日本語 |
| CI/CD | GitHub Actions | Lint/Test/Deploy 자동화 |

## 개발 명령어

```bash
# 코드 품질
make lint          # Ruff 린트
make format        # Ruff 포맷
make typecheck     # Mypy 타입 체크
make check         # 전체 코드 품질 검사

# 테스트
make test          # 전체 테스트
make test-quick    # 빠른 테스트 (slow/benchmark 제외)
make coverage      # 커버리지 리포트

# 빌드
make build         # pip 패키지 빌드
make docker-build  # Docker 이미지 빌드
docker compose up -d  # Docker Compose로 실행 (권장)

# 정리
make clean         # 빌드 아티팩트 정리
make pre-commit    # Pre-commit 훅 설치 및 실행
```

## API 문서

서버 실행 후:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 환경 변수

`.env.example` 파일을 참조하세요:

```bash
cp .env.example .env
# .env 파일을 편집하여 설정
```

주요 환경 변수:

| 변수 | 기본값 | 설명 |
|:---|---:|:---|
| `AGK_HOST` | `127.0.0.1` | 바인딩 호스트 |
| `AGK_PORT` | `8000` | API 서버 포트 |
| `AGK_ACCESS_PIN` | `0000` | API 접근 PIN |
| `AGK_CORS_ORIGINS` | `localhost:5173,8000` | CORS 허용 오리진 |
| `AGK_LOG_LEVEL` | `INFO` | 로그 레벨 |
| `AGK_DAILY_BUDGET_USD` | `50.0` | 일일 비용 예산 |
| `AGK_HOURLY_ACTION_LIMIT` | `100` | 시간당 액션 제한 |
| `OPENROUTER_API_KEY` | — | OpenRouter API 키 |
| `NVIDIA_API_KEY` | — | NVIDIA NIM 무료 API 키 ([build.nvidia.com](https://build.nvidia.com/) 발급) |

### 멀티 프로바이더 설정 (Ollama + OpenRouter + NVIDIA NIM)

Antigravity-K는 **로컬 Ollama + OpenRouter + NVIDIA NIM**을 단일 폴백 체인으로 통합합니다.
이는 단일 백엔드(Codex=OpenAI, Cursor=폐쇄형)인 경쟁사 대비 핵심 차별점입니다.

```bash
# 1. 로컬 Ollama (무제한, 프라이버시 보장)
ollama pull qwen3.6:latest

# 2. OpenRouter (다중 모델聚合)
# https://openrouter.ai/에서 API 키 발급
echo 'OPENROUTER_API_KEY=sk-or-...' >> .env

# 3. NVIDIA NIM (무료, 80+ 모델)
# https://build.nvidia.com/에서 무료 키 발급 (40rpm/1000req-day)
echo 'NVIDIA_API_KEY=nvapi-...' >> .env
```

`config.yaml`의 `combos:` 섹션에서 각 역할별 폴백 체인을 정의합니다.
예: `reasoning-swarm` = [NIM 대형모델 → OpenRouter → 로컬 Ollama] 3단계 폴백.

### 보안: 승인 흐름 & 샌드박스

- **승인(Approval) UX**: 위험 도구 실행 시 diff 미리보기와 함께 승인 요청
  - `GET /api/approval/pending` — 대기 중인 승인 목록
  - `POST /api/approval/{id}/resolve` — 수락/거부/항상허용
- **샌드박스**: macOS `sandbox-exec`(seatbelt)로 명령 격리 (config `sandbox_enabled: true`)

## 기여

[CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

## 라이선스

MIT License — 자유롭게 사용, 수정, 배포하세요.
