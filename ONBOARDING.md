# 🚀 Ssak-Ai 온보딩 가이드

Ssak-Ai는 로컬에서 실행되는 AI 엔지니어링 에이전트입니다.
OpenAI 호환 API를 제공하며, 웹 검색, 파일 조작, Git 연동, 코드 분석 등
다양한 작업을 자동화합니다.

---

## 📋 목차

1. [빠른 시작](#1-빠른-시작)
2. [설정](#2-설정)
3. [핵심 기능](#3-핵심-기능)
4. [API 사용법](#4-api-사용법)
5. [대시보드 사용법](#5-대시보드-사용법)
6. [트러블슈팅](#6-트러블슈팅)
7. [참고 자료](#7-참고-자료)

---

## 1. 빠른 시작

### 필수 요구사항

| 항목 | 버전 | 확인 명령어 |
|------|------|-----------|
| Python | ≥ 3.12 | `python --version` |
| Node.js | ≥ 20 | `node --version` |
| npm | ≥ 10 | `npm --version` |
| Docker (선택) | 최신 | `docker --version` |

### 1분 설치

```bash
# 1. 저장소 클론
git clone https://github.com/antigravity-k/antigravity-k.git
cd antigravity-k

# 2. Python 가상환경 및 의존성 설치
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. 설정 파일 생성
cp config.yaml.example config.yaml

# 4. 대시보드 빌드
cd dashboard
npm install
npm run build
cd ..

# 5. 서버 실행
python -m uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 8000 --reload
```

서버가 실행되면:
- **API**: http://127.0.0.1:8000
- **Swagger UI (권장)**: http://127.0.0.1:8000/docs
  👉 모든 API 엔드포인트를 탐색하고 브라우저에서 바로 테스트해보세요!
- **ReDoc**: http://127.0.0.1:8000/redoc
- **OpenAPI JSON**: http://127.0.0.1:8000/openapi.json
- **대시보드**: http://127.0.0.1:8000 (dashboard/dist가 빌드된 경우)

> **💡 첫걸음**: 브라우저로 http://127.0.0.1:8000/docs 를 열어보세요.
> Swagger UI에서 모든 API를 탐색하고 바로 실행해볼 수 있습니다.
>
> **Swagger UI Authorize 버튼으로 간편 인증**:  
> 1. Swagger UI 우측 상단의 **Authorize** 버튼 클릭  
> 2. **OAuth2Password (password flow)** 영역의 `username` 필드에 액세스 PIN 입력  
> 3. `password` 필드는 비워두고 **Authorize** 클릭  
> 4. 이제 모든 보호된 엔드포인트를 "Try it out"으로 바로 테스트 가능!  
>
> **또는 수동 토큰 발급**:  
> 1. `/api/auth/login` 또는 `/api/auth/token` 엔드포인트로 JWT 토큰 발급  
> 2. **BearerAuth** 영역에 `Bearer <token>` 형식으로 입력  
> 3. 또는 `X-Access-Pin` 헤더를 각 요청에 포함

### 헬스 체크

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","version":"0.2.0","backends":[...],...}
```

---

## 2. 설정

### config.yaml

주요 설정 항목:

```yaml
# API 키 (OpenRouter, NVIDIA NIM, OpenAI 등)
api_keys:
  OPENROUTER_API_KEY: "sk-or-..."
  NVIDIA_API_KEY: "nvapi-..."

# 검색 엔진
search:
  searxng_url: "http://localhost:8080"  # SearxNG 인스턴스 (선택)
  engine: "searxng"                     # 기본 검색 엔진

# 비용 제어
cost_control:
  daily_budget_usd: 50          # 일일 LLM 호출 예산
  hourly_action_limit: 100      # 시간당 최대 액션 수
```

### 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `AGK_SEARCH_ENGINE_URL` | Self-Hosted 검색 엔진 URL | `https://main.search-engine-api.pages.dev` |
| `SEARXNG_URL` | SearxNG 인스턴스 URL | `http://localhost:8080` |
| `JINA_API_KEY` | Jina AI API 키 (선택) | - |
| `TAVILY_API_KEY` | Tavily AI API 키 (선택) | - |
| `AGK_CORS_ORIGINS` | CORS 허용 오리진 (쉼표 구분) | `http://localhost:5173,http://localhost:8000` |
| `AGK_BACKEND_URL` | 백엔드 URL (대시보드용) | `http://127.0.0.1:8012` |

---

## 3. 핵심 기능

### 🤖 AI 채팅 (`/chat`)

OpenAI 호환 채팅 API. 스트리밍 응답, 멀티모달(이미지 분석), Plan 모드 지원.

**빠른 명령어:**
- `/goal <목표>` — 자율 목표 실행
- `/self` — 자기 진단 리포트
- `/benchmark` — 벤치마크 리포트
- `/agentic` — 에이전틱 업그레이드 레이더

### 🔍 웹 검색

다중 엔진 기반 실시간 검색 (SearxNG → Jina → DuckDuckGo 폴백 체인).
종목코드 자동 검증, 구조화 데이터 추출, Perplexity 스타일 인용 포함.

### 📁 파일 시스템

워크스페이스 파일 읽기/쓰기/검색/관리.
Monaco Editor 기반 코드 편집기 내장.

### 🐙 Git 연동

status, diff, commit, branch, stash 등 전체 Git 워크플로우 지원.
시각적 Diff 뷰어 제공.

### 🧬 자가 진화

QualityGate 점수 기반 자동 프롬프트/스킬/코드 개선.
RSI 엔진 + MetaArchitect 파이프라인.

---

## 4. API 사용법

### 인증

```bash
# 1. 로그인 (JWT 토큰 발급)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin":"0000"}'

# 2. 발급 받은 토큰으로 API 호출
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer <token>"

# 또는 X-Access-Pin 헤더 사용 (레거시)
curl http://localhost:8000/v1/models \
  -H "X-Access-Pin: 0000"
```

### 채팅 API (OpenAI 호환)

```python
import httpx

response = httpx.post(
    "http://localhost:8000/v1/chat/completions",
    headers={
        "Authorization": "Bearer <token>",
        "Content-Type": "application/json",
    },
    json={
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Python 3.13의 새로운 기능은?"}
        ],
        "stream": True,
    },
)

for chunk in response.iter_text():
    print(chunk, end="")
```

### 웹 검색

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/search/extract",
    headers={"X-Access-Pin": "0000"},
    json={"query": "한화에어로스페이스 주가"},
)
print(response.json())
# {
#   "ok": true,
#   "extracted": {
#     "stock_prices": [{"name": "한화에어로스페이스", ...}]
#   }
# }
```

### 파일 시스템

```bash
# 파일 읽기
curl "http://localhost:8000/api/fs/read?file=/workspace/main.py" \
  -H "X-Access-Pin: 0000"

# 파일 쓰기
curl -X POST http://localhost:8000/api/fs/write \
  -H "X-Access-Pin: 0000" \
  -H "Content-Type: application/json" \
  -d '{"file_path":"test.py","content":"print(\"hello\")"}'

# 디렉토리 목록
curl "http://localhost:8000/api/fs/list?path=/workspace" \
  -H "X-Access-Pin: 0000"
```

### Git

```bash
# 상태 확인
curl http://localhost:8000/api/git/status \
  -H "X-Access-Pin: 0000"

# 로그
curl -X POST http://localhost:8000/api/git/log \
  -H "X-Access-Pin: 0000" \
  -H "Content-Type: application/json" \
  -d '{"path":".","max_count":10}'

# 커밋
curl -X POST http://localhost:8000/api/git/commit \
  -H "X-Access-Pin: 0000" \
  -H "Content-Type: application/json" \
  -d '{"message":"feat: add new feature"}'
```

---

## 5. 대시보드 사용법

### 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `Cmd+K` | 명령 팔레트 열기 |
| `Cmd+J` / `Ctrl+` `` ` `` | 터미널 토글 |
| `Cmd+Shift+F` | 파일 검색 |
| `?` / `Cmd+/` | 키보드 단축키 가이드 |
| `Cmd+Shift+P` | 새 채팅 세션 |
| `Cmd+S` | 파일 저장 (에디터) |
| `Esc` | 팔레트/모달 닫기 |

### 주요 화면

| 페이지 | 경로 | 설명 |
|--------|------|------|
| AI 채팅 | `/chat` | AI와 대화, 코드 생성 |
| Wiki | `/wiki` | LLM Wiki 문서 탐색 |
| Git | `/git` | Git 상태/로그/Diff |
| 히스토리 | `/history` | 파일 변경 히스토리 |
| 설정 | `/settings` | API 키, 모델, 테마 설정 |
| 스킬 | `/skills` | 스킬 마켓플레이스 |
| 데이터 추출 | `/data-extraction` | 검색 데이터 추출 대시보드 |
| 에이전트 | `/agent` | 에이전트 모니터링 |

---

## 6. 트러블슈팅

### 서버가 시작되지 않아요

```bash
# 포트 충돌 확인
lsof -i :8000

# config.yaml 확인
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 로그 레벨 높이기
AGK_LOG_LEVEL=DEBUG python -m uvicorn antigravity_k.api.server:app
```

### 대시보드가 빈 화면이에요

```bash
cd dashboard
npm install
npm run build
# 서버 재시작
```

### Playwright E2E 테스트가 실패해요

```bash
# 브라우저 설치
cd dashboard
npx playwright install chromium

# 백엔드 서버 실행 후 테스트
# (터미널 1) python -m uvicorn antigravity_k.api.server:app --port 8012
# (터미널 2) cd dashboard && npx playwright test
```

### API 호출이 401을 반환해요

```bash
# 1. PIN 설정 확인
echo $AG_ACCESS_PIN

# 2. JWT 토큰 재발급
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin":"0000"}'

# 3. Authorization 헤더 확인
curl http://localhost:8000/health  # 공개 — 인증 불필요
```

---

## 7. 참고 자료

| 자료 | 링크 |
|------|------|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |
| **소스 코드** | https://github.com/antigravity-k/antigravity-k |
| **아키텍처 문서** | `ARCHITECTURE.md` |
| **변경 로그** | `CHANGELOG.md` |
| **기여 가이드** | `CONTRIBUTING.md` |

### 유용한 명령어 모음

```bash
# 진단 실행
agk doctor

# 전체 테스트 실행
pytest tests/

# 특정 모듈 테스트
pytest tests/test_web_search.py -v

# 린트 검사
ruff check src/

# 타입 검사
mypy src/
```

---

> **💡 Tip**: `ARCHITECTURE.md`에서 시스템 전체 아키텍처를, `CHANGELOG.md`에서
> 최신 변경사항을 확인할 수 있습니다. 질문이나 이슈는 GitHub Issues에 남겨주세요.
