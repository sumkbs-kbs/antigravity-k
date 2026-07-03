# Antigravity-K — Local Engine for SHI

[![Benchmark Dashboard](https://img.shields.io/badge/📊_Benchmark_Dashboard-GitHub_Pages-9C27B0?style=for-the-badge)](https://sumkbs-kbs.github.io/antigravity-k/benchmark/)

> 인터넷 의존 없이 완벽히 로컬로 동작하는 자율형 엔지니어링 에이전트

## 개요

Antigravity-K는 Apple Silicon M5 Max (128GB Unified Memory) 위에서 동작하는
완전 로컬 AI 에이전트 파이프라인입니다.

**핵심 역량:**
- 🧠 **추론 (Reasoning)**: MLX 기반 70B+ 모델 로컬 추론
- 🌐 **집단지성 (MoE Swarm)**: 다국적 다중 모델이 교대로 토론하며 교차 검증하는 Swarm 라우팅 체계
- 🤖 **행동 (Agent)**: ReAct 패턴 기반 자율 도구 호출 및 자가 진화(Self-Evolution)
- 🔒 **보안 (Privacy)**: 완전 에어갭 운영, Docker 샌드박스
- 👁 **시각 (Vision)**: mlx-vlm 기반 이미지/문서 분석

## 빠른 시작

```bash
# 1. 환경 설치 (최초 1회)
chmod +x setup_env.sh && ./setup_env.sh

# 2. 가상환경 활성화
source .venv/bin/activate

# 3. MLX 검증
python verify_mlx.py
```

## 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| 추론 엔진 | MLX / mlx-lm | Apple Silicon 네이티브 LLM 추론 |
| 비전 | mlx-vlm | 멀티모달 이미지 분석 |
| 벡터 DB | ChromaDB | 로컬 임베딩 저장/검색 |
| API | FastAPI + uvicorn | OpenAI 호환 로컬 서버 |
| 샌드박스 | Docker | 코드 실행 격리 환경 |
| CLI | Typer + Rich | 터미널 인터페이스 |

## 디렉토리 구조

```
antigravity-k/
├── setup_env.sh          # 환경 설치 스크립트
├── requirements.txt      # Python 의존성
├── verify_mlx.py         # MLX 설치 검증
├── pyproject.toml        # 프로젝트 메타데이터
├── src/antigravity_k/    # 메인 패키지
│   ├── engine/           # 추론 엔진
│   ├── rag/              # RAG 파이프라인
│   ├── agent/            # 에이전트 코어
│   ├── vision/           # 비전 모듈
│   ├── security/         # 보안 & 샌드박스
│   └── tools/            # 에이전트 도구
├── models/               # 로컬 모델 저장소
├── data/                 # 문서 & 벡터 저장소
├── logs/                 # 감사 로그
├── tests/                # 테스트
└── dashboard/            # 웹 대시보드
```

## 라이선스

MIT License
