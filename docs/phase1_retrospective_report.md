# Phase 1 회고 보고서 — D1–D17 (포함 D20)

> **작성일**: 2026-07-06  
> **대상**: Phase 1 (Day 1 ~ Day 17, Day 20)  
> **프로젝트**: Antigravity-K  
> **전체 소스코드**: 223 Python 파일, 69개 테스트 파일  
> **전체 테스트**: 894개 (890 passed, 4 skipped) — 45.29s

---

## 1. 구현 현황 요약

| Day | 영역 | 핵심 파일 | 테스트 클래스 | 테스트 수 | 상태 |
|:---:|:---:|:---|:---|:---:|:---:|
| **D1** | ExecutionMode + ModeManager | `execution_mode.py`, `mode_manager.py` | `TestD1_ExecutionMode`, `TestD1_ModeManager` | 58 | ✅ |
| **D2** | ArtifactEngine | `artifact_engine.py` | `TestD2_ArtifactEngine` | (week1 통합) | ✅ |
| **D3** | ToolPermissions | `tool_executor.py`, `gate_pipeline.py` | `TestD3_ToolPermissions` | (week1 통합) | ✅ |
| **D4** | PlanToBuildPipeline | `plan_to_build.py`, `plan_guard.py` | `TestD4_PlanToBuildPipeline` | (week1 통합) | ✅ |
| **D5** | QualityGate | `quality_gate.py` | `TestD5_QualityGate` | (week1 통합) | ✅ |
| **D6** | FormatStatus | (CLI format status) | `TestD6_FormatStatus` | (week1 통합) | ✅ |
| **D7** | EventBus + Mode Indicator | `event_bus.py`, `dashboard/main.js` | `TestD7_EventBusPublish` | (week1 통합) | ✅ |
| | **Week1 E2E** | 통합 흐름 | `TestWeek1_E2E_FullFlow` | — | ✅ |
| **D8** | SkillMarketClient DataModels | `skill_market_client.py` | `TestD8_SkillMarketClient_DataModels` | 55 | ✅ |
| **D9** | SkillInstaller | `skill_installer.py` | `TestD9_SkillInstaller` | (week2 통합) | ✅ |
| **D10** | SkillMarketRegistry | `skill_market_registry.py` | `TestD10_SkillMarketRegistry_Integration` | (week2 통합) | ✅ |
| **D11** | MCPServerRegistry | `mcp_tool_loader.py` | `TestD11_MCPServerRegistry_Advanced` | (week2 통합) | ✅ |
| **D12** | CLI/Slash Market | `cli.py`, `slash_commands.py` | `TestD12_CLI_Slash_Market` | (week2 통합) | ✅ |
| **D13** | SkillLoader Market | `skill_loader.py`, `skills_registry.py` | `TestD13_SkillLoader_Market_Advanced` | (week2 통합) | ✅ |
| **D14** | E2E Marketplace Lifecycle | 통합 흐름 | `TestWeek2_E2E_MarketplaceLifecycle` | — | ✅ |
| **D15-D16** | Dashboard Mode Indicator + Skills Browser | `system_api.py`, `skills.js`, `main.js`, `index.css` | `TestPhase1_E2E_FullIntegration` | 24 | ✅ |
| **D17** | Skill Publisher (npm + GitHub PR) | `skill_publisher.py` | 8개 테스트 클래스 | 28 | ✅ |
| **D20** | Skills 검색/설치 UI 고도화 | `skills.js`, `system_api.py` | (D16 통합) | — | ✅ |

---

## 2. 파일별 코드 규모

### 2.1 Phase 1 엔진 소스 (15개 파일, 8,295 lines)

| 파일 | 라인 수 | 역할 |
|:---|---:|:---|
| `slash_commands.py` | 1,493 | Slash 명령어 레지스트리 (market install/search 연동) |
| `skill_publisher.py` | 880 | Skill npm publish + GitHub PR |
| `skill_installer.py` | 868 | npm 패키지 → .agent/skills/market/ 설치 |
| `mcp_tool_loader.py` | 710 | MCP 서버 레지스트리 + 스킬-MCP 연동 |
| `skill_market_registry.py` | 618 | SkillMarketRegistry — 검색/설치/제거 통합 |
| `skill_market_client.py` | 586 | npm Registry 클라이언트 — search/view |
| `gate_pipeline.py` | 557 | PLAN/BUILD 모드 게이트 파이프라인 |
| `tool_executor.py` | 468 | 도구 실행기 — PLAN/BUILD 권한 검사 |
| `skills_registry.py` | 435 | 스킬 레지스트리 — 로드/활성화 |
| `mode_manager.py` | 413 | 실행 모드 상태 기계 (PLAN/BUILD/INTERACTIVE) |
| `skill_auto_learner.py` | 365 | 자동 스킬 학습 |
| `skill_loader.py` | 331 | 스킬 로더 — source별 로드 |
| `skill_generator.py` | 300 | 스킬 생성기 |
| `plan_guard.py` | 137 | PLAN 모드 도구 차단 규칙 |
| `execution_mode.py` | 134 | ExecutionMode enum + 툴 권한 매트릭스 |

### 2.2 Phase 1 테스트 (4개 파일, 3,009 lines)

| 파일 | 라인 수 | 테스트 수 | 대상 |
|:---|---:|:---:|:---|
| `test_week1_e2e.py` | 875 | 58 | D1–D7 + E2E |
| `test_week2_e2e.py` | 1,162 | 55 | D8–D14 + E2E |
| `test_phase1_e2e.py` | 536 | 24 | D8–D16 통합 |
| `test_skill_publisher.py` | 436 | 28 | D17 |

### 2.3 Phase 1 Dashboard (4개 파일, 3,903 lines)

| 파일 | 라인 수 | 역할 |
|:---|---:|:---|
| `dashboard/src/styles/index.css` | 2,424 | 전체 스타일 (Skills/Mode 포함) |
| `dashboard/src/main.js` | 720 | 라우팅 + Mode Indicator + 시스템 상태 |
| `dashboard/src/pages/skills.js` | 623 | Skills Browser 4탭 (D16 + D20) |
| `dashboard/index.html` | 136 | HTML 구조 + 네비게이션 |

---

## 3. 품질 메트릭

### 3.1 테스트

| 항목 | 값 |
|:---|---:|
| 전체 테스트 수 | 894 (890 passed, 4 skipped) |
| Phase 1 E2E 테스트 수 | 165 (100% 통과) |
| Week 1 (D1–D7) | 58 tests ✅ |
| Week 2 (D8–D14) | 55 tests ✅ |
| Phase 1 통합 (D8–D16) | 24 tests ✅ |
| Skill Publisher (D17) | 28 tests ✅ |
| 최대 실행 시간 | 45.29s |

### 3.2 린트 (ruff)

| 항목 | 값 |
|:---|---:|
| Phase 1 엔진 파일 | **0 errors** ✅ |
| Phase 1 테스트 파일 | **0 errors** ✅ |
| ruff 설정 | target py312, line-length 120, ignore E402/E701/E702 |

### 3.3 코드 기여

| 항목 | 값 |
|:---|---:|
| Phase 1 관련 커밋 | 33개 |
| 신규 생성 파일 | ~20개 (소스 + 테스트 + 대시보드) |
| 발견 및 수정된 버그 | 3개 (InstalledSkill mcp_server_id 갭, mkdtemp 타입 에러, API skill_name 불일치) |

---

## 4. Day별 상세 분석

### 4.1 Week 1: Core Infrastructure (D1–D7)

**구현:** 실행 모드 상태 기계, PLAN/BUILD 게이트, 아티팩트 엔진, 툴 권한, 퀄리티 게이트, 이벤트 버스, 대시보드 모드 인디케이터.

**강점:**
- `ExecutionMode` enum + `ModeManager` 상태 기계 — PLAN/BUILD/INTERACTIVE 모드 전환, 히스토리 추적, 리스너 패턴
- `GatePipeline` — PLAN 모드 읽기 전용 도구 차단, BUILD 모드 제한 도구 승인
- `PlanGuard` — 모드별 도구 권한 매트릭스
- EventBus를 통한 모드 변경 이벤트 발행 (D7)

**약점/갭:**
- **D2 ArtifactEngine**: `plan.md` 기반 자동 아티팩트 생성 테스트만 존재, 실제 Plan → Build 전환 시 Artifact 검증 부족
- **D5 QualityGate**: 출력 품질 점수 매기기 로직이 단순함 — 정보 밀도, 중복, 장황도 측정 정교화 필요
- **D7 EventBus**: 테스트는 있지만 실제 Dashboard WebSocket과의 연동 End-to-End 검증 부족

### 4.2 Week 2: Skill Ecosystem (D8–D14)

**구현:** npm Registry 클라이언트, 스킬 설치기, 마켓플레이스 레지스트리, MCP 연동, CLI/Slash 명령어, 스킬 로더.

**강점:**
- `SkillMarketClient` — `npm search`/`npm view` 파싱, AGK/비AGK 감지
- `SkillInstaller` — npm install → 검증 → 보안스캔 → 설치 (6종 검증 + 2종 보안)
- `SkillMarketRegistry` — 설치/제거/검색/업데이트 통합 API
- `MCPServerRegistry` — .mcp.json 생성/관리, `list_skills_with_mcp()`
- `SkillLoader` — global/local/market 3-source 스킬 로드
- `slash_commands.py` — `/skill-market install/search/list/remove` 등 Slash 명령어

**약점/갭:**
- **백엔드 의존성**: `SkillMarketRegistry` 인스턴스 생성 시 모든 의존성 필요 — Dashboard API에서 매번 새 인스턴스 생성 (비효율)
- **npm CLI 의존**: `npm search`/`npm view`/`npm install`이 모두 외부 npm CLI에 의존 — 오프라인/제한환경 fallback 부족
- **보안**: `npm view`의 raw JSON을 그대로 파싱 — 악의적인 패키지 응답에 대한 방어 부족
- **D13 SkillLoader**: market 소스 스킬 디렉토리 변경(package.json 이동) 감지 로직 부족

### 4.3 Week 3: Dashboard + Publish (D15–D17, D20)

**구현:** Dashboard Skills Browser, API 엔드포인트, Mode Indicator 호버 향상, Skill Publisher (npm/GitHub PR).

**강점:**
- `system_api.py` — 7개 API 엔드포인트 (skills/installed/mcp/search/install/remove/mode/history)
- `skills.js` — 4탭 UI (All Skills/Marketplace/Search npm/MCP Servers) + 로딩/에러/빈 상태
- `SkillPublisher` — npm publish (package.json 생성 → README 자동 생성 → npm publish) + GitHub PR (clone → branch → commit → push → PR create)
- Toast 알림, Refresh 버튼, 실시간 개수 업데이트

**약점/갭:**
- **D15 문서**: Day 15(phase1_e2e.py 생성)의 명시적 테스트 클래스 부재 — D16에 통합됨
- **D18–D19 미구현**: SkillLoader MCP 통합 + SkillGenerator 강화는 아직 구현되지 않음
- **Browser E2E 테스트 부재**: Dashboard Skills UI는 unit test로만 검증 — 실제 브라우저 렌더링 테스트 없음
- **npm/GitHub 실제 연동**: `publish_to_npm`과 `publish_to_github` dry-run으로만 테스트 — 실제 배포 검증 필요
- **로딩 상태 개선 필요**: `skills.js`에서 `window.showToast` 의존 — Toast 시스템 전체에 의존

---

## 5. 테스트 현황

### 5.1 커버리지 분석 (테스트 범위)

| 영역 | 테스트 | 엣지 케이스 | 비고 |
|:---|:---|:---|:---|
| ExecutionMode enum | ✅ 모든 값 검증 | ✅ | |
| ModeManager 상태 전이 | ✅ 모든 전이 | ⚠️ 동시 전환 레이스 | |
| ArtifactEngine | ✅ 생성 | ❌ Plan-Build 연동 검증 | |
| ToolPermissions (PLAN/BUILD) | ✅ 차단/허용 | ⚠️ 복합 권한 | |
| PlanToBuildPipeline | ✅ 기본 흐름 | ❌ 예외/중단 복구 | |
| QualityGate | ✅ 기본 | ❌ 정교화 필요 | |
| SkillMarketClient | ✅ search/view/parse | ✅ | |
| SkillInstaller | ✅ install/validate/security | ✅ 6종 validation | |
| SkillMarketRegistry | ✅ CRUD + format | ✅ | |
| MCPServerRegistry | ✅ register/list/unregister | ✅ setup_method 격리 | |
| CLI/Slash | ✅ 도움말/에러/alias | ✅ | |
| SkillLoader | ✅ load/list/refresh | ✅ | |
| SkillPublisher | ✅ validate/prepare/json | ✅ 28 tests | |
| Dashboard Skills.js | ❌ browser E2E 부재 | ❌ | UI 테스트 필요 |

### 5.2 미비점 (Gap Analysis)

| # | 갭 | 영향 | 우선순위 |
|:---:|:---|:---|---:|
| 1 | **D18–D19 미구현** (SkillLoader MCP 통합 + SkillGenerator) | 기능 공백 | 🔴 P0 |
| 2 | **Browser E2E 부재** — Dashboard UI 테스트 없음 | 회귀 탐지 불가 | 🔴 P0 |
| 3 | **GitHub/npm 실제 연동 미검증** — dry-run only | 배포 신뢰도 낮음 | 🟡 P1 |
| 4 | **D15 명시적 테스트 부재** | 추적성 부족 | 🟢 P2 |
| 5 | **QualityGate 정교화 필요** | 출력 품질 제어 약함 | 🟡 P1 |
| 6 | **SkillMarketRegistry 싱글톤 부재** — API 호출마다 인스턴스 생성 | 성능/리소스 낭비 | 🟡 P1 |
| 7 | **npm CLI fallback 부재** | 오프라인/제한환경 대응 불가 | 🟡 P1 |
| 8 | **coverage threshold 40%** | 신규 코드 품질 보증 취약 | 🟢 P2 |
| 9 | **mypy type checking 미적용** | 타입 안정성 보증 부족 | 🟢 P2 |

---

## 6. Day별 구현 로드맵 vs 현황

| Day | 계획 | 구현 상태 | 비고 |
|:---:|:---|:---:|:---|
| D1 | ExecutionMode + ModeManager | ✅ | |
| D2 | ArtifactEngine | ✅ | |
| D3 | ToolPermissions | ✅ | |
| D4 | PlanToBuildPipeline | ✅ | |
| D5 | QualityGate | ✅ | |
| D6 | FormatStatus | ✅ | |
| D7 | EventBus + Mode Indicator | ✅ | |
| D8 | SkillMarketClient | ✅ | SkillDetail + InstalledSkill dataclass |
| D9 | SkillInstaller | ✅ | npm install → validate → security → copy |
| D10 | SkillMarketRegistry | ✅ | search/install/remove/update + format |
| D11 | MCPServerRegistry | ✅ | .mcp.json config + tools list |
| D12 | CLI/Slash Commands | ✅ | `/skill-market` commands |
| D13 | SkillLoader | ✅ | 3-source market scanning |
| D14 | Week 2 E2E | ✅ | Marketplace lifecycle |
| D15 | phase1_e2e.py | ✅* | D16에 통합되어 명시적 분리 부족 |
| D16 | Dashboard Skills Browser | ✅ | 3탭 (All/Marketplace/MCP) + Mode Tooltip |
| D17 | Skill Publisher | ✅ | npm publish + GitHub PR |
| D18 | SkillLoader MCP 통합 | ❌ | **미구현** |
| D19 | SkillGenerator 강화 | ❌ | **미구현** |
| D20 | Skills 검색/설치 UI | ✅ | Search npm tab + Install/Remove |

---

## 7. 발견된 버그 요약

| 버그 | 발견일 | 파일 | 영향 |
|:---|:---:|:---|:---|
| `InstalledSkill`에 `mcp_server_id` 필드 누락 | D14 | `skill_market_client.py` | `.agk_meta.json`의 `mcp_server_id`가 `RegistrySkillInfo`로 전파되지 않음 |
| `tempfile.mkdtemp()` 반환값 `str` 타입 문제 | D17 | `skill_publisher.py` | `Path / str` 타입 에러로 publish 실패 |
| `installedNames` API 필드명 불일치 (`skill_name` vs `name`) | D20 | `skills.js` | 검색 결과에서 설치된 스킬의 버튼 상태 미표시 |

---

## 8. 권장 사항 (Actions)

### P0 (즉시 필요)
1. **D18–D19 구현**: SkillLoader MCP 통합, SkillGenerator 강화
2. **Browser E2E 테스트 추가**: Dashboard Skills 페이지 렌더링 검증 (Playwright)

### P1 (다음 Sprint)
3. **npm CLI fallback 구현**: `npm search`/`npm view` 실패 시 로컬 캐시 사용
4. **SkillMarketRegistry 싱글톤 도입**: API 호출 간 인스턴스 공유
5. **SkillPublisher 실제 배포 검증**: 스테이징 환경에서 npm publish + GitHub PR E2E 테스트

### P2 (지속적 개선)
6. **Coverage threshold 상향**: 40% → 60%
7. **mypy 타입 체킹 활성화**: Phase 1 엔진 파일에 대해 strict 모드
8. **D15 독립 테스트 클래스 추가**: phase1_e2e.py 분리

---

## 9. 결론

Phase 1 (D1–D17, D20)은 **Skills Ecosystem의 핵심 인프라**를 성공적으로 구축했습니다:

- **3주 + 1일** 동안 **15개 엔진 파일(~8,295줄)**, **4개 E2E 테스트 파일(165개 테스트)**, **Dashboard UI 4개 파일(~3,900줄)** 개발
- **3개의 버그를 조기 발견 및 수정** (모두 E2E 테스트가 발견)
- **린트 0 errors**, **165/165 테스트 100% 통과**
- **33개 커밋**으로 점진적 구현

주요 미비점은 D18–D19 (SkillLoader MCP + Generator) 미구현과 Browser E2E 테스트 부재이며, 이는 P0 우선순위로 즉시 보완이 필요합니다. 전체적인 아키텍처 설계와 테스트 품질은 양호하며, 발견된 3개 버그 모두 테스트가 조기 발견하여 수정된 점은 테스트 전략이 효과적으로 작동하고 있음을 증명합니다.
