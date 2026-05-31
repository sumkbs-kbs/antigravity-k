---
name: antigravity-agent-cron
description: Antigravity-K의 Cron 스케줄 설정 — 금리/시장 리포트, 포트폴리오 분석, Memory 정리 등 자동화된 업무
version: "1.0.0"
tags: [cron, schedule, automation, workflow]
triggers: ["cron", "스케줄", "자동", "정기작업"]
---

# CRON.md — Cron 업무 스케줄

## 금리/시장 리포트 (매일 10:00)
```yaml
schedule: 0 10 * * *
name: 금리/시장 현황 리포트
prompt: "오늘의 주요 금리, 환율, KOSPI/KOSDAQ 동향을 수집하여 요약 리포트 작성"
deliver: telegram
script: ""
context_from: ["previous-cron-job-id"]  # 이전 리포트 이어받기
```

## 포트폴리오 영향 분석 (매일 자정)
```yaml
schedule: 0 0 * * *
name: 포트폴리오 영향 분석
prompt: "오늘의 금융시장 동향이 Antigravity-K의 관련 기업에 미칠 영향 분석"
deliver: telegram
```

## Wiki broken link 스캔 (매주 월요일 09:00)
```yaml
schedule: 0 9 * * 1
name: Wiki broken link 정기 스캔
prompt: "/Users/mr.k/wiki/My_Wiki/ 내 broken link 스캔 및 정리"
deliver: local  # 파일만 저장
```

## Memory 정리 (매월 1일 11:00)
```yaml
schedule: 0 11 1 * *
name: Memory/User 정리
prompt: "/Users/mr.k/program/coding/ssak_comp/antigravity-k/.agent/skills/antigravity-agent/MEMORY.md 검토 및 정리 요청"
deliver: local
```

## AI 트렌드 리포트 (매주 목요일 09:00)
```yaml
schedule: 0 9 * * 4
name: AI 트렌드 주간 수집
prompt: "최근 1周内 AI/LLM 관련 주요 뉴스 및 트렌드 수집"
deliver: telegram
```

## 사용 옵션
- **`deliver: local`** → 파일만 저장 (확인 필요 없는 작업)
- **`silent: true`** → 결과 내용이 없으면 알림 X
- **`no_agent: true`** → 스크립트만 실행 (에이전트 불필요)
- **`context_from: [job_id]`** → 이전 cron 결과 이어받기 (체인)
