---
id: 60
category: note
tags: []
created: 2026-05-04T09:42:52.197451
---

# Plantler Skills Map of Content

> [!NOTE]
> 이 문서는 `Plantler` 프로젝트(`C:\Python\project\Plantler\.agents\skills`) 내에 종속된 에이전트 스킬들을 분류 및 체계적으로 관리하기 위한 메인 허브(Map of Content)입니다. Plantler의 도메인 특화 유지보수, 리뷰, 배포, 테스트 작업을 담당합니다.

## 🏗️ 1. 핵심 아키텍처 및 유지보수 규칙 (Core Architecture & Maintenance)
- **[[project-architecture]]**: Plantler 앱의 전체 프로젝트 구조, 모듈 조직도, DB 스키마, API 라우트, 기술 스택 등 종합 참고 가이드
- **[[feature-maintenance]]**: 기능 유지보수 체크리스트 — 버전 업그레이드 시 문제 방지, 의존성 관리 및 시스템 정합성 검증
- **[[confirmed-logic-registry]]**: 반복된 수정 및 복구 끝에 확정된 중요 로직들의 영구 기록소 (리팩터링 시 필수 참조 사항 보존)
- **[[frontend-backend-consistency]]**: 신규 컴포넌트(페이/탭) 생성 시 FE/BE 간 데이터 반환 규격(1:1) 정합성 검증 및 라우터 등록 워크플로우

## ⚙️ 2. 세부 시스템 및 기능 특화 (System & Feature Specifics)
- **[[health-score-system]]**: 건강 대시보드 점수 자동 산정 로직, 아키텍처 및 트러블슈팅 전용 가이드
- **[[badge-system]]**: 뱃지/업적 시스템 설계, 신규 뱃지 확장, Tier 체계 및 시즌 운영 가이드
- **[[billing-iap-maintenance]]**: 인앱 결제(In-App Purchase) 및 구독 시스템의 아키텍처, 주의사항 및 결제 오류 분석표
- **[[admin-page-maintenance]]**: 관리자 페이지 전용 유지보수 가이드 (레이아웃, 팁 구성, API 연동, 보안 및 배포 단계)
- **[[organization-chart]]**: 프로젝트 유지보수를 위한 가상 조직도 (임원진, 부서, 과, 유저 그룹 분류)

## 🐛 3. 리뷰, 디버깅 및 QA (QA, Review & Debugging)
- **[[server-error-diagnosis]]**: 서버사이드 오류 (500 Error 등) 발생 시 최소 시간 내 추적 프로세스 및 원인 파악 시스템
- **[[gstack-review]]**: 수석 엔지니어 아이덴티티. 아키텍처, 성능, 보안 및 코드 유지보수성 측면을 깊이 있게 검토
- **[[gstack-qa]]**: 전문 QA 매니저 아이덴티티. 일반적인 유저 플로우부터 극한의 엣지 케이스까지 꼼꼼하게 테스트
- **[[gstack-design-review]]**: 수석 디자이너 아이덴티티. 애니메이션, 다크모드, 여백 일관성 등 Ohouse 프리미엄 UI 품질 통제

## 🚀 4. 배포 및 퍼블리싱 (Release & Publishing)
- **[[play-store-publishing]]**: Google Play Store 앱 최초 등록, 버전 업데이트(비공개/공개 트랙), 정책 위반 방지 체크리스트 등 런칭 전체 프로세스
- **[[release-notes-format]]**: 배포 시 필수로 적용해야 하는 다국어(ko-KR, en-US, ja-JP, zh-TW) 릴리즈 노트 포맷 가이드
