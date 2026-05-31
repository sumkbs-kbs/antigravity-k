---
name: antigravity-agent-reporting
description: Antigravity-K의 보고 채널 설정 — Telegram/Slack 연동, 리포트 형식, 알림 규칙
version: "1.0.0"
tags: [reporting, telegram, slack, notification]
triggers: ["보고", "채널", "연동", "알림"]
---

# REPORTING.md — 보고 채널

## 채널별 역할

| 채널 | 용도 | 자동연동 |
|-----|------|--|
| **Telegram (주요)** | 금리/시장 리포트, AI트렌드, 리서치 요약 | ✅ Cron 자동 |
| **Slack** | 개발 관련 협업, 팀 공유 | 기본 X (필요시 설정) |

## 리포트 형식

### 금리/시장 리포트 (매일 10:00)
```
📊 금리/시장 현황 (YYYY-MM-DD)

◆ KOSPI: XXXX (±X.XX%)
◆ 환율: XXXX원 (±XXX원)
◆ 주요 금리: 기준금리 X.X%, 대출금리 X.X%

◆ 주요 기업:
  - SK하이닉스: $XXXX (±X%)
  -삼성전자: $XXXX (±X%)

◆ 크로스도메인 연결:
  AI ↔ [연결사항]

◆ 분석:
  핵심 요약 (2~3문장)

◆ 액션:
  [필요한 경우]
```

### AI 트렌드 리포트 (매주 목요일 09:00)
```
🤖 AI 트렌드 (W43)

◆ 주요 뉴스:
  1. [출처] 뉴스 요약
  2. [출처] 뉴스 요약
  3. [출처] 뉴스 요약

◆ Antigravity-K 관련성:
  - [관련성 설명]

◆ Wiki 상태:
  - 신규 분석: X개
  - broken link: X개

◆ 크로스도메인:
  AI ↔金融: [연결사항]
```

### 포트폴리오 분석 (매일 자정)
```
📈 포트폴리오 영향 분석

◆ Today's Impact:
  - 긍정/A부정 기업: [이유]

◆ 관련 기업:
  - [기업명]: 영향도 [높음/중간/낮음]

◆ 제안:
  [필요한 경우]
```

## 연동 설정

### Telegram
- 기본 채널 연결
- Cron deliver: `origin` (현재 채팅) 또는 `telegram` 지시
- 리포트 자동 발송: 메시지 길이 X, 리포트 형식 준수

### Slack (선택사항)
- `config.yaml` 에서 `integrations.slack.enabled: true`
- `slack.pre_response_channels: [channel_ids]` 추가
- 필요시만 활성화 (기본값: X)

## 알림 규칙
- **중요**: 금리 급변, 시장 폭등/폭락 → 즉시 알림
- **정기**: 리포트는 Cron 자동, 별도 알림 X
- **silent: true** → 결과 내용이 없는 cron은 알림 X
