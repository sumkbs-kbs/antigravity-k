# Antigravity-K 종합 테스트 리포트 (v6.5)

> **테스트 일시**: 2026-05-07 20:42 KST
> **테스터**: Antigravity-K 전문 QA 대행 (Codex)
> **테스트 방식**: 실제 8012 서버 API 호출 + DOM/Command Palette 회귀 + 정적 분석 + 전체 pytest + Vite build + 출력 품질 포렌식 + 집단지성 모델 경쟁 검증
> **최종 결과**: **33/33 Phase PASS**, pytest **330 passed**

---

## 1. 테스트 환경

| 항목 | 값 |
|------|----|
| OS | macOS (Apple Silicon) |
| Python | 3.13.12 |
| Node.js/Vite | Vite v6.4.2 |
| 테스트 서버 | `http://127.0.0.1:8012` |
| 보호 인증 | `X-Access-Pin: 1935` |
| 주요 엔진 | `QualityGate`, `SelfCapabilityEngine`, `StreamProcessor`, `AutonomousCapabilityPolicy`, `CodexTransferEngine`, `CollectiveIntelligenceEngine`, `ModelRouter` |

---

## 2. 최종 검증 명령

| 검증 | 결과 | 증거 |
|------|------|------|
| Ruff 정적 분석 | PASS | `python -m ruff check src tests` → `All checks passed!` |
| 전체 pytest | PASS | `330 passed in 8.15s` |
| Python 컴파일 | PASS | `python -m compileall -q src tests` |
| Dashboard build | PASS | `npm run build` → Vite build 102ms |
| 실제 8012 자기소개 API | PASS | `Self Capability Report=True`, `슬래시 명령=21개`, `Thinking Process=False`, `WiFi=False` |
| 실제 8012 Qwen3 API | PASS | Qwen3 30B가 한국어 최종 응답 반환, `think` 미포함 |

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
| 32 | 자기 능력 인식 포렌식 | PASS | `/self`, 자연어 fast path, think block 차단 |
| 33 | 집단지성 모델 경쟁 | PASS | `collective-council`, 제안/비판/합성, Qwen3 `/no_think` 검증 |

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
| 9 | Qwen3 30B가 실제 호출에서 빈 `response`와 `thinking`만 반환 가능 | thinking mode 기본 동작과 짧은 토큰 예산 충돌 | Qwen3 계열 `/no_think` 자동 주입 및 thinking-only 실패 처리 | 완료 |
| 10 | 비스트리밍 결과에 hidden reasoning 블록이 남을 수 있음 | 스트림 필터와 비스트림 후처리 경로가 분리됨 | `ModelManager._strip_hidden_reasoning()` 추가 | 완료 |

---

## 5. 출력 품질 1:1 비교 결론

| 품질 기준 | 기대 수준 | 개선 후 Antigravity-K |
|-----------|-----------|------------------------|
| 자기 능력 인식 | 실제 도구/권한/한계를 기준으로 답변 | `SelfCapabilityEngine`이 ToolRegistry/SkillLoader/Slash registry를 읽어 보고 |
| 내부 추론 비노출 | hidden reasoning은 최종 출력에 없어야 함 | `StreamProcessor` 제거 + `QualityGate` retry |
| 한국어 순도 | 한국어 답변에 중국어/일본어 혼입 0건 | 다국어 오염 및 가독성 붕괴 감지 |
| 최신 정보 | 검색 날짜/출처 또는 capability 한계 명시 | cutoff 기반 답변 감점 |
| 구조화 | 비교 요청 시 표/기준/차이 명확화 | 비교표 누락 감점 |
| 집단지성 | 여러 중급 이상 모델이 제안/비판/합성 수행 | Qwen3 30B + Mistral 24B + DeepSeek 32B `collective-council` |
| 오류 제로화 | 정적 분석/테스트/빌드/컴파일 모두 PASS | Ruff, pytest 330, compileall, Vite build PASS |

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

---

## 7. 최종 판정

2026-05-07 20:42 KST 기준 Antigravity-K v6.5는 사용자가 지적한 “자기 자신이 무엇을 할 수 있는지 명확히 모른다”는 결함과 “하나의 문제를 하나의 모델에 맡기는 구조”를 함께 개선했습니다. 이제 자기소개/능력 설명은 실제 등록된 도구, Skills, 슬래시 명령, 위험도 정책에 근거하며, 주요 추론 경로는 여러 모델의 제안/비판/합성을 통해 단일 모델 편향을 줄입니다.

또한 제공된 저품질 대화 전문에서 확인된 내부 추론 노출, 다국어 오염, 한국어 가독성 붕괴, 최신 정보 미검증 답변을 모두 재현 가능한 테스트로 고정했습니다. 최종 회귀 결과는 `ruff PASS`, `pytest 330 passed`, `compileall PASS`, `dashboard build PASS`, 실제 8012 API 자기소개 및 Qwen3 응답 품질 검증 PASS입니다.
