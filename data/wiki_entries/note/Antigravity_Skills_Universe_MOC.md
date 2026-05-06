---
id: 59
category: note
tags: []
created: 2026-05-04T09:42:52.195698
---

# 🧠 Antigravity Skills Universe (MOC)

> **안티그래비티(AI 에이전트)에 탑재된 스킬 생태계의 중앙 허브 지도입니다.**
> 이 지도에 정의된 스킬들을 호출하여 자동화된 워크플로우부터 코드 리뷰, 디자인, 시스템 디버깅까지 수행할 수 있습니다.

## 🏆 1. 기획 및 제품 전략 (Planning & Product)
아이디어 스케치부터 최고경영자(CEO), 기술책임자(CTO) 수준의 아키텍처 리뷰를 자동화합니다.
- [[office-hours]] : 새로운 제품이나 아이디어에 대한 강도 높은 브레인스토밍 및 설계 모드
- [[plan-ceo-review]] : CEO 관점의 기획 리뷰 (목표 상향, 스코프 조정, 제품 본질 탐구)
- [[plan-eng-review]] : 엔지니어 매니저 관점의 기술 구조, 데이터 흐름, 예외 처리 설계 리뷰
- [[plan-design-review]] : 디자이너 관점의 UI/UX 사전 리뷰 및 개선점 제안
- [[autoplan]] : 복잡한 중간 질문 없이 CEO/Design/Eng 리뷰 파이프라인을 자동으로 연속 실행

## 🎨 2. 디자인 및 프론트엔드 (Design & UI/UX)
프리미엄 UI 시스템을 구축하고, 디자인 병목을 AI 파이프라인으로 해결합니다.
- [[design-consultation]] : 프로덕트 분석을 바탕으로 한 통합 디자인 시스템(DESIGN.md) 제안
- [[design-shotgun]] : 여러 가지 AI 디자인 시안을 한 번에 생성하고 시각적 아이디어 도출
- [[design-html]] : 승인된 목업(Mockup)을 바탕으로 동적이고 반응성 있는 실제 프로덕션용 HTML/CSS 구현
- [[design-review]] : 운영 중인 사이트의 시각적 불일치, 여백, 상하구조 오류 등을 스캔하고 자동으로 수정
- [[ui-expert-mcp]] : React/Vue 기반의 접근성 높고 세련된 모던 UI 컴포넌트 생성 전문가

## 🛠️ 3. 개발, 배포 및 리뷰 (Execution & CI/CD)
Pull Request 생성부터 배포, 그리고 기술 문서화까지 개발 사이클을 완성합니다.
- [[review]] : 코드 병합(Merge) 전에 보안, 사이드 이펙트, 구조적 오류를 사전 검토하는 PR 자동 리뷰
- [[ship]] : 테스트 실행, 버전 범프(Version Bump), PR 생성 등을 아우르는 배포 준비 워크플로우
- [[setup-deploy]] : 프로젝트 환경(Vercel, GitHub Actions, Fly.io 등)에 맞춘 배포 세팅 자동 구성
- [[land-and-deploy]] : 병합 이후 CI를 대기하고 릴리즈 환경까지 최종 배포(Deploy) 감독
- [[document-release]] : 배포 완료 후 코드 변화를 추적하여 README, CHANGELOG 등 문서 자동 동기화
- [[retro]] : 일주일간의 Git 커밋 역사를 분석하여 팀원별 기여도와 주간 개발일지를 자동 작성

## 🛡️ 4. 시스템 보호 및 보안 (Security & Guardrails)
수정 범위를 통제하고 파괴적 명령어를 통제하는 인프라 보안 시스템입니다.
- [[cso]] : 최고보안책임자(CSO) 모드로 시크릿, 의존성 공격, LLM 보안 등에 대해 종합 펜테스트 수행
- [[careful]] : DB Drop이나 rm -rf 같은 위험 명령어 실행 직전에 경고를 띄워주는 안전망
- [[freeze]] : 특정 디렉토리로만 파일 수정을 엄격하게 제한하여 버그 발생 시 격리 처리
- [[unfreeze]] : 세션 내에 설정된 수정 제한(Freeze) 상태를 해제
- [[guard]] : Careful + Freeze를 결합한 라이브 배포 및 디버깅 시의 완전 보안(Maximum Safety) 모드

## 🐛 5. 품질 보증 및 문제 해결 (QA & Debugging)
실시간 런타임 디버깅과 통합 QA 테스트를 수행합니다.
- [[investigate]] : 에러 로그나 버그를 토대로 '근본 원인(Root Cause)'까지 파고드는 4단계 체계적 디버깅
- [[qa]] : 웹 애플리케이션의 전반을 브라우저로 통합 테스트하고 발견된 버그를 자동으로 수정까지 진행
- [[qa-only]] : 자동 수정 없이 깔끔한 리포트와 스크린샷 증거만 생성하는 QA 보고서 모드
- [[benchmark]] : PR 마다 페이지 렌더링 속도, 크기 등을 기록하여 성능 이력을 추적
- [[canary]] : 라이브 서버 배포 직후 이상 징후나 에러가 떨어지는지 모니터링하는 카나리아 감시

## 🌐 6. 브라우저 및 헤드리스 테스트 (Automation & Browser)
AI가 직접 브라우저를 띄워 화면을 보고 상호작용합니다.
- [[gstack]] / [[browse]] : 보이지 않는 백그라운드 크롬을 100ms만에 띄워 사이트와 상호작용 및 스크린샷 촬영
- [[connect-chrome]] : 사용자 화면에 실제 크롬을 띄우고 AI가 동작하는 것을 실시간으로 관전하는 툴
- [[setup-browser-cookies]] : 사용자 본인의 크롬 쿠키를 AI 브라우저로 이관하여 로그인 세션 그대로 테스트

## 🧑‍🔬 7. 에이전트 지능, 기억 및 진화 (Memory & Evolution)
AI가 스스로 과거의 실수를 기억하고 지능을 진화시킵니다.
- [[learn]] : 여러 세션에 걸쳐 익힌 패턴이나 지식을 요약, 검색, 정리하는 기억 관리 모듈
- [[gbrain]] : 자율 에이전트 영구 기억 시스템 (Hybrid Search 및 지식 강화 담당)
- [[evolver]] : AI 에이전트 자신을 스스로 진화시키는 GEP 자가발전 엔진
- [[awesome-agent-evolution]] : AI 시스템 진화 기술 논문 및 아키텍처 방법론 오라클
- [[hermes-for-web]] : 커스텀 UI 및 통신 파이프라인 관리를 위한 Hermes 에이전트 오케스트레이션 환경

## 💎 8. 핵심 연동 플러그인 (Obsidian & Ecosystem)
- [[nanobanana-pro-obsidian]] : 옵시디언 NanoBanana PRO 플러그인 유지보수 전문가
- [[obsidian-code]] : Obsidian Code 플러그인 및 Claude Code SDK 구조 이해 전문가
- [[nlwflow-research]] : NotebookLM 연구 자료를 옵시디언 위키로 즉시 구조화하는 파이프라인
- [[claude-code-source-code-full]] : 1,900+ 내부 시스템(내부 로직)을 꿰뚫고 있는 소스 분석가

## 🏢 9. 특화 도메인 스킬 (Domain Specific Skills)
- [[Plantler_Skills_MOC]] : Plantler 전용 아키텍처, 유지보수, 기획 및 디버깅 스킬 허브 모음
