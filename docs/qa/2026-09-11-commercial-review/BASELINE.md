---
title: 2026-09-11 상용 완성도 검토 기준과 신규 발견
status: reviewed-baseline-not-release-approval
date: 2026-09-11
reviewed_sha: 08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f
tags: [commercial-readiness, review, evidence, baseline]
---

# 상용 완성도 개선의 기준 기록

이 문서는 새 에이전트가 이전 대화나 개인 `/tmp` 파일 없이 개선 의도를 이해하기 위한 검토 요약이다. [개발 계획](../../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md), [체크리스트](../../17_COMMERCIAL_RELIABILITY_CHECKLIST.md)와 함께 읽는다. 이전 RP 완료 이력을 지우거나 당시 결과를 부정하는 문서가 아니다. 아래 결함은 2026-09-11 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` 및 당시 작업트리를 기준으로 확인했으며, 구현자는 최신 HEAD에서 먼저 재현해야 한다.

## 판단과 범위

판단: **기능이 풍부한 로컬 고급 베타, 상용 GA 보류**. 자체 ADR-0003의 로컬/자체 호스팅 단일 운영자 범위를 기준으로 한다. Windows, SaaS, 멀티테넌트, 결제 미구현을 현행 제품 결함으로 세지 않는다.

Git 추적 인벤토리는 src 551, dashboard 269, tests 457, docs 94, vscode-extension 13, .github 8, deploy 4파일이었다. src에는 번들 산출물도 포함된다. 전체 영역의 구조와 핵심 경로를 심층 조사했으나 모든 줄/실행 경로를 전수 인증한 것은 아니다. 그래프에서 발견한 심볼과 현재 소스, 임시 합성 데이터 재현을 교차 확인했다.

## 발견 → 새 작업 연결

| 발견 | 관찰과 근거 위치(저장소 루트 기준) | 증거 수준 | 작업 |
|---|---|---|---|
| B01 대화 식별 충돌 | `src/antigravity_k/engine/conversation_store.py:572-575`는 ID 문자 치환+64자 절단. 계약은 `api/contracts/conversation.py:31`의 최대 128자. `a.b` 저장 후 같은 프로젝트의 `a_b` GET이 `a.b` 내용을 200으로 반환 | 실제 임시 store+API router 실행; 인증 우회 주장은 아님 | CR-01 |
| B02 세션 저장 손실 | `engine/session_manager.py:505-514` truncate 후 dump, 예외 로그만. dump에 OSError 주입 시 기존 파일 0바이트 | 실제 파일을 사용하는 오류 주입 | CR-02 |
| B03 신규 세션 충돌 | `engine/session_manager.py:138` 초 단위 ID. 고정 시각 resume=False 두 번에 동일 ID/이력 소실 | 임시 SessionManager 실행 | CR-02 |
| S01 API shell 환경 상속 | `api/routes/agent_tools.py:145-146,251-263` auto-pilot 고정, 최소 env/restrict_reads 미전달. synthetic canary가 sandboxed=True 결과 stdout으로 반환 | 실제 handler 실행, 인증된 호출 권한 전제 | CR-04 |
| S02 macOS 읽기 격리 누락 | `engine/sandbox.py:333-355` restrict_reads에서도 /private/var/folders의 별도 임시 작업 파일 읽기 가능 | 실제 sandbox+합성 파일 실행 | CR-03 |
| F01 API 키 영속 | `dashboard/src/pages/SettingsPage.tsx:125-131` apiKeys를 localStorage 원문 저장, :44-51 재조회 | 현재 소스 확인; 실제 키 유출 공격 미수행 | CR-05 |
| F02 설정 오류 은폐 | `SettingsPage.tsx:105-121` GET 실패 시 loading만 false, 기본값 폼 저장 가능 | 현재 소스 확인 | CR-06 |
| F03 렌더/route 복구 공백 | `App.tsx:95-120,312-330`, `main.tsx:49-68` lazy/Suspense만 있고 ErrorBoundary/404 없음 | 정적 관찰; 구현 전 실패 주입 필요 | CR-07 |
| F04 접근성 | `SettingsPage.tsx:181-192` provider 입력 label 연결 없음. `CommandPalette.tsx:69-75,169` focus 초기화만, trap/복귀 계약 부족 | 정적 관찰; 실제 keyboard 검증 필요 | CR-08 |
| F05 외부 자산 | `dashboard/index.html:16-27` font/CDN CSS/Mermaid 외부 의존; `ChatMessage.tsx:91-95` 라이브러리 부재 시 다이어그램 오류 | 정적 관찰; 전체 앱 오프라인 불가 주장은 아님 | CR-09 |
| F06 고정 운영 지표 | `SystemTelemetricsBar.tsx:112,117` BUILD v0.8.0-RC, UPTIME 14D 08H 12M 고정; :35 healthy 부재를 true 처리 | 소스와 새 QA 서버 화면 교차 확인; CPU/MEM 전체가 가짜라는 뜻 아님 | CR-10 |
| D01 확장 문구 과장 | `vscode-extension/README.md:9` automatic reconnection/offline support, 실제 `src/extension.ts:115-195,224-239`는 다음 editor event 재시도 | 정적 관찰 | CR-12 |
| R01 clean release 실패 | `.github/workflows/release.yml:46-54` 프로젝트 설치 전 `python -m antigravity_k.engine.release_sbom` 실행 | 새 Python 3.12 venv 동일 명령 ModuleNotFoundError; hosted Actions 전체 실행은 아님 | CR-11 |
| R02 CI 감사 대상 누락 | `.github/workflows/ci.yml:469-474` 제품 설치/lock 입력 전 pip-audit, 제품 설치는 이후. 별도 `scripts/audit_python_dependencies.sh`는 lock export 사용 | 설정/스크립트 대조; 프로젝트 전체 감사 부재라고 일반화하지 않음 | CR-11 |
| R03 manifest drift | `.omo/evidence/final-review-remediation/RP-13/attempt-002/release-manifest.json` 11개 중 benchmark-results의 현재 hash 불일치, 나머지 10개 일치 | 현 파일 SHA256 재계산 | CR-13 |
| R04 증거와 현재 SHA | RP-12 gate 후보 4b202113, soak 후보 70875519; 이번 기준 08b8bb2e와 다름 | metadata/원문 gate 대조 | CR-13, CR-14 |
| D02 출시 승인 미완료 | `docs/ga/GA_SUPPORT_MATRIX.md`, `GA_CLAIMS_AND_REVIEW_REGISTER.md`에 지원/약관/운영 승인 미완료 | 문서상의 승인 상태; 법 위반 판정 아님 | CR-12, CR-14 |

## 보존할 강점

ConversationStore의 authoritative read/revision CAS/프로세스 잠금, Vault의 Git·잠금·커밋 실패 보호, 모델 어댑터, 실제 작업·승인·취소·재개 UI, Markdown 정화, production 인증 fail-closed, 모델 shell 최소 환경, Docker non-root는 존재한다. 해당 보호를 유지하면서 빈 경계를 닫는다. `dashboard-vanilla`/`ui` 로컬 잔재는 당시 Git 추적 제품이 아니므로 재구축하거나 중복 런타임으로 처리하지 않는다.

## 당시 실행 결과와 한계

| 검증 | 결과 |
|---|---|
| 명시적 FR 개선 회귀 11파일 | 133 passed / 18.22초 |
| Vault/CAS/다중 프로세스 회귀 | 29 passed / 10.51초 |
| 인증 정책/API 도구/샌드박스 회귀 | 66 passed / 3.61초 |
| Ruff src/tests/scripts | PASS |
| 프론트 TypeScript 검사 및 Vite 새 빌드 | PASS / 빌드 1.96초 |
| Vitest | 70파일, 750 passed / 13.47초 |
| 실제 서버 인증 Playwright | 개발 bootstrap·잘못된 PIN·PIN 로그인·만료 토큰 4 passed / 15.5초 |
| CLI --help | PASS |

테스트 집합은 중복 가능하므로 합산하지 않는다. 브라우저 인증은 번들 dashboard를 대상으로 했으며 새 빌드와 동일 바이트임까지 확인하지 않았다. 전체 Python suite, 모든 GA gate, 8시간 부하, 모든 실제 모델 및 최신 CVE 전수검사는 이 검토가 수행하지 않았다. 두 독립 lane의 최종 응답은 도구 사용량 한계로 중단돼 root가 남은 문서/QA 로그를 확인했다. 5개 lane 전체 독립 승인이라고 쓰지 않는다. 위 수치는 역사적 요약이며 신규 CR 완료 증거로 재사용할 수 없다.

## 확정 결함으로 세지 않은 후속 조사

`model_manager.py` API 오류 문자열→호출 성공 집계 가능성, Vault Git 쓰기 이후 RAG 색인 순서·복구 가능성은 당시 런타임 검증이 미완료였다. CR-14의 실패 주입 점검에서 평가하되 재현 전 자동 수정하지 않는다. 재현되면 새 발견 ID와 소유자를 등록하고 후보를 해제한다.
