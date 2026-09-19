---
title: 에이전틱 AI를 위한 런타임 에러 진단 저널 (Agent Error Journal)
tags: [architecture, agentic-ai, diagnostics, logging, self-healing]
date: 2026-09-03
---

# 에이전틱 AI를 위한 런타임 에러 진단 저널 (Agent Error Journal)

Ssak-Ai (Ssak-Ai) 구동 중 발생하는 모든 예외와 런타임 에러를 차후 **자율 코딩 AI(Agentic AI)가 스스로 분석하고 개선할 수 있도록 설계된 지능형 에러 저널 시스템**입니다.

---

## 1. 아키텍처 개요

단순한 텍스트 로그나 잘린 스택트레이스는 AI 에이전트가 버그를 수정하기에 정보가 부족합니다.
본 시스템은 에러 발생 즉시 다음 정보가 포함된 **구조화된 진단 스냅샷(Diagnostic Snapshot)**을 수집합니다:

1. **실패 코드 컨텍스트**: 디스크 상의 소스 파일에서 실패 지점 앞뒤 5줄을 읽어 실패 라인(`>>>`)을 강조한 스니펫 생성
2. **런타임 요청 컨텍스트**: HTTP 메서드, 경로, 쿼리, 클라이언트 IP (Authorization, Cookie, API Key 등 민감 정보는 자동 `[REDACTED]` 마스킹)
3. **시스템 환경 스냅샷**: Python 버전, Ssak-Ai 버전, OS 플랫폼
4. **AI 에이전트 개선 프롬프트 (AI Fix Prompt)**: 에이전트가 읽고 즉시 버그 수정 및 회귀 테스트 작성을 시작할 수 있는 정형화된 프롬프트 자동 생성

```
[Runtime Error / 5xx Exception]
            │
            ▼
┌────────────────────────────────────────────────────────┐
│               AgentErrorJournal Engine                 │
│  - Traceback & App Frame Parsing                       │
│  - Disk Code Context Extraction (5 lines before/after) │
│  - Sensitive Key & Token Redaction                     │
│  - AI Fix Prompt Generation                            │
└──────────────────────────┬─────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│ Machine-Readable JSONL  │   │  Markdown Incident Card │
│ logs/agent_errors.jsonl │   │ logs/agent_diagnostics/ │
│                         │   │   ERR-YYYYMMDD-*.md     │
└─────────────────────────┘   └─────────────────────────┘
```

---

## 2. 저장 위치 및 파일 포맷

### 1) 기계 판독용 JSONL 저널
- **경로**: `logs/agent_errors.jsonl`
- **특징**: 한 줄에 하나의 JSON 레코드로 기록되어 `jq`나 파이썬 스크립트, 에이전트가 고속으로 파싱 및 스트리밍 처리 가능.

### 2) 에이전트/인간 검토용 마크다운 카드
- **경로**: `logs/agent_diagnostics/{error_id}.md`
- **구조**:
  - YAML Frontmatter (`error_id`, `error_type`, `failing_file`, `failing_line`, `status: open`)
  - 코드 컨텍스트 및 하이라이트
  - 전체 스택트레이스
  - 요청 및 환경 컨텍스트 (JSON)
  - `### 🤖 [Agentic AI Code Fix Task]` 액션 가이드

---

## 3. CLI 및 API 사용법

### 1) CLI 명령어 (`agk error`)

```bash
# 1. 최근 기록된 에러 목록 조회
uv run agk error list

# 2. 특정 에러 상세 진단 및 소스 코드 스니펫 확인
uv run agk error inspect ERR-20260903-151230-a1b2c3

# 3. AI 에이전트에게 전달할 개선 프롬프트 출력 (파이프라인 연계 가능)
uv run agk error prompt ERR-20260903-151230-a1b2c3
```

### 2) REST API 엔드포인트

- `GET /api/system/errors?limit=20&component=api`: 최근 에러 목록 조회
- `GET /api/system/errors/{error_id}`: 단일 에러 상세 진단 및 AI 프롬프트 JSON 조회

---

## 4. 보안 및 무결성

- 모든 요청 헤더 및 쿼리/바디 내의 `Authorization`, `X-API-Key`, `Cookie`, `Secret`, `Password`는 정규표현식 기반으로 검출되어 로그 및 마크다운 파일에 `[REDACTED]`로 치환되므로 외부 유출 위험이 없습니다.
- 클라이언트에게는 내부 소스나 환경 정보가 노출되지 않고 오직 `correlation_id` 및 `error_id`만 안전하게 반환됩니다.
