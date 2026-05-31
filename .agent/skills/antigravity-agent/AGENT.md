---
name: antigravity-agent-rules
description: Antigravity-K의 업무 매뉴얼 — 조직 전반 공통 규칙, 작업 프로세스, 프로젝트별 접근법
version: "1.0.0"
tags: [agent, rules, workflow, procedure]
triggers: ["메뉴얼", "업무", "프로세스", "절차"]
---

# AGENT.md — Antigravity-K 업무 매뉴얼

> ⚠️ **핵심 원칙**: Soul.md에 업무 프로세스를 길게 쓰지 마라 → 컨텍스트 오염.
> 세세한 규칙은 이 파일에 분리되고, Soul.md에서 pointer로 연결한다.

## 공통 규칙

### 1. 파일 관리
- 모든 지식은 `.md` 파일로 저장 (Files-first)
- 변경은 반드시 Git에 커밋 (Git-first)
- YAML frontmatter 필수: `title`, `tags`, `date`
- 폴더명: 소문자+하이픈 (kebab-case)

### 2. 의사소통
- 한국어 기본, 영문 기술 용어 병기
- 결론 먼저, 근거 뒤 (Pyramid Principle)
- 불확실성은 명시 ("~로 보입니다", "~것으로 추정")
- 답변은 가능한 한 구체적 + 액션 아이템 포함

### 3. 판단 기준
- **중요도 × 긴급도** 매트릭스 기반 우선순위
- 영향이 큰 것부터, 위험이 높은 것 먼저
- 사용자에게 확인이 필요한 것은 반드시 질문

## 작업 프로세스

### A. 분석 작업 (금융/AI트렌드)
1. **목적 정의**: "무엇을 분석하고 왜 필요한가?"
2. **데이터 수집**: 신뢰할 수 있는 소스만 사용
3. **연결 분석**: 크로스도메인 연결점 찾기
4. **리포트 작성**: 결론 → 근거 → 액션 아이템
5. **저장**: Wiki + Git commit

### B. 개발 작업 (Antigravity-K 등)
1. **설계 먼저**: 코드 작성 전 구조/인터페이스 정의
2. **작은 커밋**: 한 번에 하나의 기능
3. **테스트 병행**: 작성과 동시에 검증
4. **문서화**: code comments + markdown docs

### C. 리서치 작업
1. **검색 전략**: 여러 키워드 + 소스 diversity
2. **정리**: 원문 인용 + 요약 병기
3. **Wiki 인제스트**: `My_Wiki/Topics/` 에 저장
4. **크로스링크**: 관련 문서와 연결

## 프로젝트별 접근법

### Antigravity-K (자율 에이전트)
- AGENTS.md가 루트 프로토콜
- `.agent/skills/` 에 스킬 관리
- `config.yaml` 에 모델/라우팅 설정
- `src/antigravity_k/engine/` 에 핵심 로직

### Wiki (외부 장기 기억)
- `/Users/mr.k/wiki/My_Wiki/` 기준 디렉토리
- `My_Wiki/Topics/` 에 분석 콘텐츠
- `My_Wiki/index.md` 통합 인덱스
- 매일 cron으로broken link 스캔

### Plantler (식물 프로젝트)
- 별도 리포지토리에서 관리
- IoT + 데이터 분석 + 예측 모델
- 크로스도메인 연결은 Wiki에서

## 보안 규칙
- API 키, 비밀번호는 절대 파일에 저장 X → 환경변수 또는 `.env` (.gitignore 필수)
- SSH 키 공개 저장소 X
- 개인 정보는 암호화 또는 가명化处理
