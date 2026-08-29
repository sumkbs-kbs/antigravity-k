---
title: README 대비 구현 확인 매트릭스
tags: [diagnosis, evaluation, readme, verification, antigravity-k]
date: 2026-08-17
---

# README 주장 ↔ 구현 실측 매트릭스

> 기준: repo 루트 `README.md` 기능 표·구조·명령어 vs 코드 실측 (2026-08-17).
> 상태 범례: ✅ 구현 확인(실측) · 🟡 구현 확인이나 동작 미검증 · ⚠️ 주장과 실측 불일치 · 🔴 미확인(검증 수단 없음) · ⚠️+ 과소/과대 표기

## 1. 기능 표

| README 주장 | 상태 | 실측 근거 | 비고 |
|:--|:--:|:--|:--|
| 🧠 로컬 추론 엔진 — Ollama Qwen3.6 36B 기본, 직접 MLX/LM Studio 선택 | ✅ | `ollama list`: qwen3.6:latest(23GB) 실존. doctor: `native_tools=supported`. 레지스트리 38개 모델, provider 자동 추론(`model_registry.py`) | LM Studio 경로는 401(environ 미설정) — README에 안내대로 env 필요 |
| 🌐 집단지성 MoE Swarm — 다중 모델 교차 검증/토론 라우팅 | 🟡 | `model_router.py` COLLECTIVE/CASCADING 전략 + orchestrator swarm 구조 확인 | 실제 교차 검증 발동 조건·성능 실측 미검증 |
| 🤖 자율 에이전트 — ReAct + 도구 호출 + 자가 진화 | 🟡 | ReAct 루프(`tool_loop.py`), self_evolution_coordinator/evolution 모듈 존재 | 자가 진화의 실기여도 미검증. **회귀 확인**: 도구 실패 시 인지 복구(adapt_strategy)가 ErrorDistiller 포맷 우회로 비활성화 — ReAct 증폭 구조 일부가 죽어 있음 |
| 🔗 RAG 파이프라인 — ChromaDB + 임베딩 + AST 코드 인덱싱 | 🟡 | vault/chunker/벡터/rag_indexer/AST 인덱서 구현 확인 | 검색 품질(리콜@k) 실측 미검증 |
| 👁 멀티모달 비전 — mlx-vlm | 🟡 | 레지스트리 vision 프로필, Ollama에 llava·llama3.2-vision 풀림 | mlx-vlm 직접 경로 실행 미검증 |
| 🛡️ 보안 — PIN 인증, 시크릿 스캐너, 선언적 정책, Fail-Closed | ✅ | `security_policy.py`(fail-closed), secret_scanner, 승인 API, egress 검증, 샌드박스 확정. 보안 테스트 전부 통과 | 승인 흐름 UX·샌드박스 실동작 미검증 |
| 📊 벤치마크 대시보드 — GitHub Pages 자동 배포 + 성능 회귀 | 🔴 | CI 워크플로·대시보드 빌드 구성 존재 | 원격 배포 상태는 로컬에서 검증 불가 |
| 🌍 다국어 지원 — 한국어/English/日本語 | ✅ | `i18n.py` 존재, CLI 출력 한국어 확인 | |
| 📝 구조화 로깅 — JSON + 일별 로테이션 + 감사 | ✅ | 로깅/감사 모듈 확인, doctor 로그 디렉터리 정상 | |
| 💰 비용 제어 — 일일 예산, Rate Limit, 과금 추정 | ✅ | `cost_guard.py` 구현, env 기본값(50 USD/일) 확인 | 실동작 미검증 |

## 2. 수치 주장

| README 주장 | 실측 | 상태 |
|:--|:--|:--:|
| 테스트 스위트 **70+ 파일** | `tests/` **250+ 파일** (퀵 스위트: 3,637 pass / 4 fail / 4 skip) | ⚠️ 과소 표기 |
| 도구 **50+** | `src/antigravity_k/tools/` 51개 파일 | ✅ |
| 모델 레지스트리 | doctor 실측 **38개** 등록 | ✅ |
| 증폭 실측 수치(0.832 vs 0.805, lh-001 +0.29, revision 지연 6-8배) | README 문서로만 확인 | 🟡 재현 절차·하드웨어 조건 문서화는 AMPLIFICATION_GUIDE.md에 존재, 로컬 재현 미실행 |

## 3. 구조 주장 (README 프로젝트 구조 표)

| 주장 경로 | 실측 | 상태 |
|:--|:--|:--:|
| engine/orchestrator/agent.py, model_manager, model_registry, model_router, rag_indexer, vault, security_policy, quality_gate, cost_guard, secret_scanner, error_classifier, tool_guardrails, tool_loop, tool_executor, memory/, code_intel/, provider_adapters/ | 전부 존재 | ✅ |
| `agents/` base/scout/trainer 모듈 및 레거시 coordinator/team_manager | 일부 유지·일부 삭제 | 🟡 | 현재 실행 경로는 `engine/orchestrator/`와 `model_router.py`를 사용하며, coordinator/team_manager 삭제 근거는 `docs/DELETE_AUDIT_REPORT.md`에 기록됨 |
| api/ (server.py, models.py, routes/, dependencies.py) | 존재, routes 14개 모듈 | ✅ |
| dashboard/ (Vite + Vanilla JS) | 존재 | ✅ 빌드·시각 미검증 |
| Makefile, Dockerfile, docker-entrypoint.sh, .github/workflows | 존재 | ✅ |
| "CLI: agk doctor, run, task, memory" | doctor/run/task/memory 실측 동작 확인 | ✅ |

## 4. 퀵스타트 명령어 대비

| README 명령 | 실측 | 상태 |
|:--|:--|:--:|
| `uv run agk doctor` | 17 pass / 2 warn 정상 출력 | ✅ |
| `uv run agk run "..." --model qwen3.6:latest` | 왕복 성공 ×2 | ✅ (단 답변 품질 불안정 — 별도 이슈) |
| `uv run agk task status/output/resume` | CLI 구현 확인 (`cli.py` task 서브커맨드) | 🟡 resume 경로 실측 미검증 |
| `uv run agk memory alias-set/aliases` | CLI 구현 확인 (project_aliases.json) | 🟡 실측 미검증 |
| `make smoke-cli` | Makefile 타깃 존재 | 🟡 미실행 |
| `ollama pull qwen3.6:latest` | 이미 설치됨(23GB) | ✅ |

## 5. 발견 요약

1. **과소 표기 1건**: 테스트 수 70+ → 실측 250+ (과장이 아니라 오히려 적게 씀 — 신뢰에 유리)
2. **불일치/위험 2건**: ① 자가 진화·인지 복구 증폭 구조 일부가 실제로 죽어 있음(ErrorDistiller 회귀) ② 벤치마크 대시보드 원격 상태 미확인
3. **검증 공백**: RAG 품질, MoE 교차 검증, 샌드박스, 비용 가드 실동작, 재현 벤치마크 — 전부 후속 실측 대상

> 매트릭스 유지 규칙: 이 표는 PR/변경 시 갱신할 것. 실측 날짜(2026-08-17) 기준이며, 항목 상태는 Phase 0 이후 진행에 따라 갱신한다.
