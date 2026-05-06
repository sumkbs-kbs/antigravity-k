---
id: 63
category: "[[10_Wiki/Topics]]"
tags: ["topics", "ai", "식물분석", "건강점수", "날씨"]
created: 2026-05-04T09:42:52.203103
---

# [[Plantler AI 식물 분석 시스템]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> - 식물 사진을 빠르게 분류하는 경량 모델

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 식물 사진을 빠르게 분류하는 경량 모델
  - 오프라인 환경에서도 동작
  - GPU 비용 없음
  - Google의 최신 멀티모달 AI
  - 식물 건강 상태 상세 리포트 생성

- **세부 내용:**
  - ```
  - 사진 입력 → TFLite 1차 분류
  - ├─ 단순 분류 → TFLite 결과 반환 (무료)
  - └─ 상세 필요 → Gemini API 호출 (유료)
  - ```

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Plantler 프로젝트 개요 — 식물 관리 AI 앱]], [[Plantler 아키텍처 의사결정 기록]], [[Plantler 커뮤니티 기능 개발 여정]]
- **Raw Source:** [[00_Raw/06_AI_식물분석_시스템.md]]
