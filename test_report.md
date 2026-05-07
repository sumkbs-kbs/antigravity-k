# Antigravity-K 종합 테스트 리포트 (v6.8)

> **테스트 일시**: 2026-05-08 02:53 KST
> **테스터**: Antigravity-K 전문 QA 대행 (Codex/Gemini Antigravity)
> **테스트 방식**: 실제 8012 서버 API 호출 + DOM/Command Palette 회귀 + 정적 분석 + 전체 pytest + Vite build + 출력 품질 포렌식 + 채팅 출력 타이포그래피 검증 + Agent Manager 프로젝트별 관리 검증 + 집단지성 모델 경쟁/벤치마크 검증 + DAG 병렬 도구 실행 검증 + E2E 자가 수복 루프 검증
> **최종 결과**: **38/38 Phase PASS**, pytest **359 passed in 7.81s**

---

## 1. 테스트 환경

| 항목 | 값 |
|------|----|
| OS | macOS (Apple Silicon) |
| Python | 3.13.12 |
| Node.js/Vite | Vite v6.4.2 |
| 테스트 서버 | `http://127.0.0.1:8012` |
| 보호 인증 | `X-Access-Pin: 1935` |
| 주요 엔진 | `QualityGate`, `SelfCapabilityEngine`, `StreamProcessor`, `AutonomousCapabilityPolicy`, `CodexTransferEngine`, `CollectiveIntelligenceEngine`, `ModelRouter`, `BenchmarkHarness` |

---

## 2. 최종 검증 명령

| 검증 | 결과 | 증거 |
|------|------|------|
| Ruff 정적 분석 | PASS | `python -m ruff check src tests` → `All checks passed!` |
| 전체 pytest | PASS | `359 passed in 7.81s` |
| Python 컴파일 | PASS | `python -m compileall -q src tests` |
| Dashboard build | PASS | `npm run build` → Vite build 88ms |
| 실제 8012 자기소개 API | PASS | `Self Capability Report=True`, `슬래시 명령=21개`, `Thinking Process=False`, `WiFi=False` |
| 실제 8012 Qwen3 API | PASS | Qwen3 30B가 한국어 최종 응답 반환, `think` 미포함 |
| 실제 8012 Benchmark API | PASS | `/benchmark`, `/benchmark report` 문자열 응답 및 비교표 검증 |
| 실제 8012 Chat Typography | PASS | assistant 문서형 폭/행간 적용, 모바일 표 가로 스크롤 결함 수정 |
| 실제 8012 Agent Manager | PASS | 모바일 패널 열기, 현재 프로젝트 task 표시, 타 프로젝트 task 숨김, 취소 표시 검증 |

---

## 3. Phase별 결과

| Phase | 테스트 항목 | 결과 | 상세 |
|-------|-------------|------|------|
| 1 | 코어 레이어 & 내비게이션 | PASS | 대시보드 DOM 렌더링 및 console error/warning 0 정책 |
| 2 | Command Palette | PASS | `/goal`, `/self`, `/capabilities`, `/codex` discoverable |
| 3 | 채팅 `/goal` 라우팅 | PASS | slash registry 우회, Goal Contract 렌더링 |
| 4 | 파일 탐색기 & 터미널 | PASS | 파일 목록/터미널 WebSocket 경로 검증 |
| 5 | Self-Test Loop | PASS | 보호 PIN 모드 self-test 10/10 |
| 6 | Autonomous QA Dry Loop | PASS | screenshot/responsive 검증 |
| 7 | External Brain 목록 | PASS | 외부 두뇌 어댑터 상태 계약 유지 |
| 8 | Vision Analysis API | PASS | 스크린샷 없음 케이스 400 계열 명확 반환 |
| 9 | Responsive Check | PASS | desktop/tablet/mobile 기준 유지 |
| 10 | Full Integration | PASS | 통합 인텐트 10/10 |
| 11 | 코드 회귀 & 보안 | PASS | Ruff + pytest + compileall + npm build |
| 12 | API-driven E2E | PASS | `/health`, `/v1/health`, `/api/slash`, PIN 인증 |
| 13 | `/goal` 자율 목표 계약 | PASS | 성공 기준/자율 판단/품질 게이트 출력 |
| 14 | 출력 품질 비교 | PASS | `test_output_quality.py` 7개 + planning/rendering 6개 |
| 15 | 병렬 도구 호출 | PASS | batch tool call 처리 유지 |
| 16 | CEO Analyzer & Guardrail | PASS | in-band 문자열 오탐 방지 |
| 17 | Planning Mode & Artifacts | PASS | 복잡/단순 분류 정상 |
| 18 | Advanced Markdown 렌더링 | PASS | Mermaid/Carousel/Link sanitize |
| 19 | MCP Capability Upgrade | PASS | MCP audit/template/radar 회귀 |
| 20 | Autonomous Capability Policy | PASS | Tool/MCP/Skills/PC risk/trust 판단 |
| 21 | RAG 기반 컨텍스트 확장 | PASS | AST 청킹/검색 회귀 |
| 22 | Chain-of-Verification | PASS | 자기검증 루프 회귀 |
| 23 | 웹 검색 도구 통합 | PASS | 최신 정보 보완 경로 유지 |
| 24 | External Brain 자동 위임 | PASS | 반복 실패 시 외부 위임 정책 |
| 25 | 장기 기억 시스템 | PASS | pruning/summary/RAG 기억 보존 |
| 26 | 랜덤화 공정성 테스트 | PASS | 랜덤 입력 12/12 |
| 27 | Browser-Use 자율 브라우징 | PASS | 브라우저 서퍼 단위 테스트 |
| 28 | 글로벌 터널링 & 보안 | PASS | Cloudflare/PIN/SSE 우회 정책 |
| 29 | 오류 제로화 & 보호 모드 | PASS | console error/warning 0, protected API 정상 처리 |
| 30 | Codex Capability Transfer | PASS | `/codex` manifest 및 prompt contract |
| 31 | 출력 품질 심층 검증 | PASS | 다국어 오염/비교표/최신 정보 grounding |
| 33 | 집단지성 모델 경쟁 | PASS | `collective-council`, 제안/비판/합성, Qwen3 `/no_think` 검증 |
| 34 | Artifact-Based Planning Engine | PASS | `write_artifact` 도구 검증 및 Markdown 포맷팅 정제 |
| 35 | DAG 도구 병렬 실행 & E2E 수복 | PASS | `waitForPreviousTools` 파싱 및 TDD Auto-Repair |
| 36 | 집단지성 벤치마크 누적 비교 | PASS | `/benchmark`, 종합점수, 키워드 커버리지, legacy DB 호환 |
| 37 | Codex식 채팅 출력 타이포그래피 | PASS | assistant 본문 폭/폰트/행간/Markdown 표/코드 표시 개선 |
| 38 | Agent Manager 프로젝트별 관리 | PASS | 모바일 접근성, workspace 필터, WebSocket payload, 취소 상태 정합성 |

---

## 4. 핵심 발견 및 개선 반영

| # | 발견 문제 | 원인 | 반영 내용 | 상태 |
|---|-----------|------|-----------|------|
| 1 | 자기소개 답변이 실제 capability와 무관한 WiFi/볼륨/클립보드/OS 제어를 나열 | 런타임 도구 목록과 자기소개 생성이 연결되지 않음 | `SelfCapabilityEngine` 추가, `/self` 및 자연어 자기소개 fast path 구현 | 완료 |
| 2 | `Thinking Process`, 영어 내부 계획, `<think>`류 블록이 사용자 출력으로 노출 | `StreamProcessor`가 thought block을 UI 텍스트로 변환 | thought/think 블록 제거 방식으로 변경, `QualityGate` 내부 추론 유출 패턴 강화 | 완료 |
| 3 | 한국어 답변에 `文件`, `できません`, `업グレード` 등 다국어 오염 발생 | 언어 순도 게이트가 실제 실패 패턴을 충분히 잡지 못함 | `QualityGate._check_language_contamination()` 강화 및 한국어 가독성 검사 추가 | 완료 |
| 4 | 최신 동향 질문에서 검색 없이 `knowledge cutoff`, `October 2023` 일반론으로 답변 | 최신 정보 grounding 규칙 부재 | `QualityGate._check_current_info_grounding()` 및 PromptBuilder 최신 정보 규칙 추가 | 완료 |
| 5 | `/goal`, `/capabilities`가 자기소개 fast path에 오탐 | self capability detector가 slash command를 포함해 너무 넓게 감지 | `/`로 시작하는 명령은 self detector에서 제외 | 완료 |
| 6 | auto-pilot 모드 파일 쓰기 API가 project root 밖 경로를 허용 | 외부 write path를 auto-pilot에서 ALLOW 처리 | `PermissionGate` 외부 write path를 DENY로 변경 | 완료 |
| 7 | `ruff`가 기존 `session_manager.py`의 `Path` 미임포트 발견 | 코드 경로가 테스트 전까지 정적 분석에서 누락 | `from pathlib import Path` 추가 | 완료 |
| 8 | 라운드로빈은 여러 모델 중 하나만 선택해 집단지성 철학을 구현하지 못함 | 후보 경쟁/비판/합성 실행기가 없음 | `RouteStrategy.COLLECTIVE`, `CollectiveIntelligenceEngine`, `generate_collective()` 추가 | 완료 |
| 10 | 비스트리밍 결과에 hidden reasoning 블록이 남을 수 있음 | 스트림 필터와 비스트림 후처리 경로가 분리됨 | `ModelManager._strip_hidden_reasoning()` 추가 | 완료 |
| 11 | 계획 모드에서 단순 텍스트 지시어로 복잡한 마크다운을 강제함 | 구조적 아티팩트 엔진의 부재 | `ArtifactEngine` 구현 및 `write_artifact` 도구 주입 | 완료 |
| 12 | 다중 도구 호출 시 무조건 ThreadPool에서 동시 실행되어 순서 보장 불가 | 도구 간 의존성 파싱 및 동기화 스케줄러 부재 | `waitForPreviousTools` 속성 파싱 및 DAG 방식의 배치 실행 구현 | 완료 |
| 13 | 텍스트 UI에서 GitHub Alerts 렌더링이 깨지거나 지원되지 않을 우려 | 확장 마크다운 포맷팅 후처리 부재 | `StreamProcessor`에 `_format_markdown_extensions` 적용 | 완료 |
| 14 | `/benchmark` help/report가 generator 반환 구조 때문에 유실될 수 있음 | 함수 본문에 `yield`가 있어 모든 분기가 generator화 | run 전용 nested generator로 분리 | 완료 |
| 15 | `/api/slash`가 generator를 JSON에 직접 넣을 수 있음 | legacy slash API의 generator 처리 부재 | generator 결과 문자열 병합 처리 | 완료 |
| 16 | 벤치마크가 과제 필수 요건 충족률을 별도 점수화하지 않음 | QualityGate 중심 채점만 존재 | `benchmark_score`, `keyword_coverage`, passed/missing keyword 추가 | 완료 |
| 17 | 좁은 화면에서 Markdown 표가 글자 단위로 찢어져 읽기 어려움 | bubble의 `word-break`가 table cell에도 영향을 주고 table 최소 폭이 없음 | table 최소 폭/nowrap/가로 스크롤 적용, assistant 출력 타이포그래피 테스트 추가 | 완료 |
| 18 | 모바일 화면에서 Agent Manager 버튼이 숨겨져 접근 불가 | Agent Manager 버튼이 desktop chat header에만 존재 | 모바일 app bar 버튼 추가 및 실제 브라우저 검증 | 완료 |
| 19 | Agent task가 전역 리스트라 프로젝트별 관리가 불가 | task metadata에 project/workspace 정보가 없음 | `project_path/project_name`, workspace API 필터, 프론트엔드 WS 필터 추가 | 완료 |
| 20 | Kanban WebSocket이 `tasks` 배열을 보내지 않아 패널 실시간 갱신과 불일치 | backend grouped state와 frontend 기대 payload가 다름 | flat `tasks` + grouped payload 동시 전송 | 완료 |
| 21 | 취소 task가 완료 task처럼 보임 | cancel endpoint가 `completed`로 상태 변경 | `cancelled` 상태와 `취소됨` UI 표시로 정합화 | 완료 |

---

## 5. 출력 품질 1:1 비교 결론

| 품질 기준 | 기대 수준 | 개선 후 Antigravity-K |
|-----------|-----------|------------------------|
| 자기 능력 인식 | 실제 도구/권한/한계를 기준으로 답변 | `SelfCapabilityEngine`이 ToolRegistry/SkillLoader/Slash registry를 읽어 보고 |
| 내부 추론 비노출 | hidden reasoning은 최종 출력에 없어야 함 | `StreamProcessor` 제거 + `QualityGate` retry |
| 한국어 순도 | 한국어 답변에 중국어/일본어 혼입 0건 | 다국어 오염 및 가독성 붕괴 감지 |
| 최신 정보 | 검색 날짜/출처 또는 capability 한계 명시 | cutoff 기반 답변 감점 |
| 구조화 | 비교 요청 시 표/기준/차이 명확화 | 비교표 누락 감점 |
| 채팅 표시 | 답변이 Codex처럼 문서형 폭, 안정적 행간, Markdown 친화 표시를 가져야 함 | assistant 출력 전용 CSS 변수와 표/코드/목록 스타일 적용 |
| Agent Manager 필요성 | 채팅 중 현재 작업 상태를 빠르게 확인/중단 | 유지 필요. Agent Workspace와 달리 현재 프로젝트 quick view 역할 |
| 기능 중복성 | 전체 Kanban 페이지와 데이터는 공유하되 목적은 분리 | Agent Workspace는 전체 board, Agent Manager는 현재 workspace 패널 |
| 프로젝트별 관리 | 각 프로젝트별 task 조회/표시/취소 분리 | `/api/kanban/tasks?workspace=`, `project_path`, WS client filter |
| 집단지성 | 여러 중급 이상 모델이 제안/비판/합성 수행 | Qwen3 30B + Mistral 24B + DeepSeek 32B `collective-council` |
| 집단지성 벤치마크 | 같은 과제로 collective-council과 단일 모델을 누적 비교 | `/benchmark`, 종합점수, 키워드 커버리지, 우세 타겟 |
| 오류 제로화 | 정적 분석/테스트/빌드/컴파일 모두 PASS | Ruff, pytest 359 passed in 7.81s, compileall, Vite build PASS |

---

## 6. 신규 테스트 커버리지

| 테스트 파일 | 추가/검증 내용 |
|-------------|----------------|
| `tests/test_output_quality.py` | Thinking Process 유출, 다국어 오염, 최신 정보 cutoff 답변 감지 |
| `tests/test_stream_processor.py` | complete/split/unclosed `<think>/<thought>` 블록 제거 |
| `tests/test_self_capability.py` | 자기 능력 요청 감지, `/self`, runtime capability 보고서 |
| `tests/test_api_server.py` | 자연어 자기소개가 LLM 생성 없이 self capability report로 응답 |
| `tests/test_agent_tools_api.py` | project root 밖 파일 쓰기 403 차단 회귀 |
| `tests/test_model_router.py` | `collective` 전략 파싱, legacy fallback compatibility, available model list |
| `tests/test_model_manager_generate.py` | 집단지성 제안/비판/합성, 역할별 콤보, Qwen3 `/no_think`, hidden reasoning 제거 |
| `tests/test_benchmark_harness.py` | 벤치마크 종합점수, 키워드 커버리지, slash/API 반환 경로, Command Palette 노출 |
| `tests/test_planning_and_rendering_quality.py` | Codex식 채팅 출력 폭/폰트/행간/표 가로 스크롤/letter-spacing 회귀 |
| `tests/test_api_server.py` | Kanban task 프로젝트별 필터, 취소 상태, WebSocket flat tasks payload |

---

## 7. 최종 판정

2026-05-08 02:53 KST 기준 Antigravity-K v6.8는 사용자가 지적한 “자기 자신이 무엇을 할 수 있는지 명확히 모른다”는 결함과 “하나의 문제를 하나의 모델에 맡기는 구조”를 함께 개선했습니다. 이제 자기소개/능력 설명은 실제 등록된 도구, Skills, 슬래시 명령, 위험도 정책에 근거하며, 주요 추론 경로는 여러 모델의 제안/비판/합성을 통해 단일 모델 편향을 줄입니다.

또한 제공된 저품질 대화 전문에서 확인된 내부 추론 노출, 다국어 오염, 한국어 가독성 붕괴, 최신 정보 미검증 답변을 모두 재현 가능한 테스트로 고정했습니다. 이번에는 Agent Manager를 “현재 프로젝트 quick view”로 재정의하여 전체 Agent Workspace와의 중복을 줄이고, 프로젝트별 task 분리/취소/실시간 payload 정합성을 추가했습니다. 최종 회귀 결과는 `ruff PASS`, `pytest 359 passed in 7.81s`, `compileall PASS`, `dashboard build PASS`, 실제 8012 UI 기반 Agent Manager 프로젝트별 관리 검증 PASS입니다.
