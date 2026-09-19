---
title: Ssak-Ai 최종 전체 통합 및 회귀 검증 기록
tags: [qa, remediation, final-verification, integration, e2e]
date: 2026-09-03
reviewed_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
---

# Ssak-Ai 최종 전체 통합 및 회귀 검증 기록

## 1. 개요 및 배경

F01부터 F15까지 전수 수정·검증된 상태에서, 전체 시스템에 걸친 엔드-투-엔드 통합성 및 잔존 잠재 결함 유무를 판정하기 위해 전체 단위/통합/E2E 테스트 스위트와 배포 패키지 무결성을 전수 실행했다.

검증 과정에서 Vite 번들러의 청크 분할 설정 누락으로 인해 발생하던 휠 패키징 충돌 결함(1건)을 포착하여 근본 수정하고, 전체 4,890개 단위 테스트, 라이브 백엔드 스모크 테스트, 및 59개 브라우저 E2E 테스트의 전수 무결 통과를 달성했다.

---

## 2. 발견된 추가 잠재 결함 및 해결

### [발견] `rehype-sanitize` 및 `unified` 청크 분할에 따른 `index.js` 네이밍 충돌
- **증상**: 전체 Python 비벤치마크 테스트 스위트 실행 중 `test_wheel_contains_dashboard_and_runtime_resources` 실패 (`AssertionError: assert ['index.js'] == []`).
- **원인 분석**:
  - F08 보안 조치 과정에서 Markdown 안전 렌더링을 위해 `rehype-sanitize`가 추가됨.
  - `dashboard/vite.config.ts`의 `manualChunks` 규칙에 `rehype-sanitize`와 `unified`가 명시되지 않아, Rollup이 해당 패키지의 엔트리(`index.js`)를 단독 청크로 분리하면서 청크 이름을 기본값인 `index-[hash].js`로 생성함.
  - 이로 인해 대시보드 메인 엔트리(`index-[hash].js`)와 이름이 겹쳐 2개의 `index.js` 논리 자산이 생성되었고, 배포 휠 무결성 검증기에서 중복 자산으로 거절됨.
- **조치**:
  - `dashboard/vite.config.ts`의 `markdown-core` 그룹에 `id.includes('node_modules/rehype-sanitize')` 및 `id.includes('node_modules/unified')`를 명시적으로 등록.
  - `pnpm --dir dashboard build` 재실행으로 단일 `index-[hash].js` 구조 복원 확인.
- **결과**: `tests/test_dashboard_wheel_assets.py` 1 passed (0.80s), 휠 내 중복 자산 0건 입증.

---

## 3. 종합 검증 실행 결과

### A. Python 전체 단위 및 회귀 스위트 (비벤치마크 전수)
- **실행 명령**:
  ```bash
  uv run --no-sync pytest tests --ignore=tests/benchmarks -q
  ```
- **결과**:
  ```text
  4890 passed, 6 skipped, 1 warning in 182.95s (0:03:02)
  ```
- **판정**: **100% 통과 (0 failures)**

### B. 라이브 백엔드 서버 스모크 테스트
- **실행 명령**:
  ```bash
  uv run --no-sync pytest tests/test_e2e_smoke.py -v
  ```
- **결과**:
  ```text
  tests/test_e2e_smoke.py::test_health_endpoint PASSED
  tests/test_e2e_smoke.py::test_health_returns_backends PASSED
  tests/test_e2e_smoke.py::test_health_returns_version PASSED
  tests/test_e2e_smoke.py::test_cors_headers PASSED
  tests/test_e2e_smoke.py::test_security_headers PASSED
  tests/test_e2e_smoke.py::test_public_paths_accessible PASSED
  tests/test_e2e_smoke.py::test_protected_path_requires_auth PASSED
  tests/test_e2e_smoke.py::test_error_response_has_correlation_id PASSED
  tests/test_e2e_smoke.py::test_server_stable_over_time PASSED
  ============================== 9 passed in 17.39s ==============================
  ```
- **판정**: **PASS (실제 임시 uvicorn 프로세스 및 HTTP/보안 헤더 계약 준수)**

### C. Playwright 브라우저 E2E 전체 스위트
- **환경**: 격리 임시 토큰/인증 경로 지정 하 uvicorn 데몬 기동 (`port 56034`), 실제 Chromium 브라우저 구동
- **실행 명령**:
  ```bash
  AGK_BACKEND_URL=http://127.0.0.1:56034 pnpm --dir dashboard exec playwright test --project=chromium --reporter=list
  ```
- **결과**:
  ```text
  Running 59 tests using 9 workers

  ✓  Accessibility 테스트 10개 전수 통과 (Settings, Chat, Data Extraction, Skills, History, Agent, Wiki, Plugin, Mutation Dashboard, Git, Sidebar, Command Palette)
  ✓  Auth Bootstrap 테스트 4개 전수 통과 (no-auth 부팅, 잘못된 PIN 거절 및 잔여 credential 소거, 올바른 PIN 로그인, 만료 토큰 PIN 다이얼로그 폴백)
  ✓  Chat Interface 테스트 7개 전수 통과 (메시지 전송, 사용자 버블, SSE 어시스턴트 응답, 모델 셀렉터, textarea 개행)
  ✓  Command Palette 테스트 4개 전수 통과 (Cmd+K 열기, 키보드 검색, Escape 닫기)
  ✓  File Explorer 테스트 7개 전수 통과 (IDE 레이아웃, 헤더, 툴바, 트리 렌더링, 새로고침, 검색 토글)
  ✓  Git Integration 테스트 8개 전수 통과 (헤더, 4개 탭, Changes/History/Branches/Graph 전환)
  ✓  Health & Load 테스트 4개 전수 통과 (루트 마운트, 헬스 체크 응답)
  ✓  Navigation 테스트 2개 전수 통과 (사이드바 네비게이션, Chat 이동)
  ✓  Task Execution & Replay 테스트 10개 전수 통과 (375px/768px/1280px 뷰포트 trace, 세션 분기, 라이브 스트림 복구, 불완전 리플레이 처리)
  ✓  Wiki Security 테스트 2개 전수 통과 (안전 마크다운 렌더링, 주입 HTML 비활성화, CSP 보존)

  59 passed (40.3s)
  ```
- **판정**: **PASS (전수 59/59 통과, 0 failed, 0 skipped)**

### D. 배포 패키지 및 공급망 SBOM/메타데이터 검증
- **실행 명령**:
  ```bash
  uv run --no-sync python -m antigravity_k.engine.release_sbom generate --project-root . --release-root src/antigravity_k/release
  uv build
  uv run --no-sync python -m antigravity_k.engine.release_metadata --distribution-root dist --git-ref v0.1.0
  uv run --no-sync python -m antigravity_k.engine.release_sbom verify --distribution-root dist --release-root src/antigravity_k/release
  ```
- **결과**:
  - Wheel 및 SDist 빌드 성공:
    - `dist/antigravity_k-0.1.0-py3-none-any.whl` (SHA-256 일치)
    - `dist/antigravity_k-0.1.0.tar.gz` (SHA-256 일치)
  - `release_metadata`:
    `{"sdist":"antigravity_k-0.1.0.tar.gz","source_version":"0.1.0","version":"0.1.0","wheel":"antigravity_k-0.1.0-py3-none-any.whl"}`
  - `release_sbom`:
    `{"manifest": "dist/release-supply-chain.json", "python_components": 61, "status": "verified"}`
- **판정**: **PASS (공급망 해시 및 143 dashboard + 61 python 의존성 manifest 무결 검증 완료)**

---

## 4. 환경 정리 및 사용자 데이터 보존 확인

1. **임시 프로세스 정리**:
   - Playwright 검증에 사용된 uvicorn 프로세스(task-504, port 56034) 정상 종료.
   - 임시 인증 파일(`/tmp/agk_e2e_token_secret`, `/tmp/agk_e2e_auth_hash`) 삭제 완료.
2. **사용자 데이터 보존**:
   - `data/benchmark_results.json`은 일체 건드리지 않고 원본 그대로 보존됨.
3. **작업 트리 상태**:
   - 의도된 코드/문서 수정 외에 불필요한 임시 빌드 아티팩트 및 캐시 없음.

---

## 5. 결론

QA 수정 항목 F01~F15의 개별 조치뿐만 아니라, 빌드·패키징·단위 테스트(4,890건)·라이브 API 스모크(9건)·실제 브라우저 E2E(59건)에 이르는 전 계층 통합 검증이 완료되었으며 전 스위트 Green 상태를 확인하였다.
