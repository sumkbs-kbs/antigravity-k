---
id: 37
category: "[[10_Wiki/Decisions]]"
tags: ["decisions", "의사결정", "아키텍처", "기술선택"]
created: 2026-05-04T09:42:52.150072
---

# [[Plantler 아키텍처 의사결정 기록]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> - React Native + Express → Python AI 생태계와 통합이 어려움

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - React Native + Express → Python AI 생태계와 통합이 어려움
  - Swift/Kotlin 네이티브 → 두 플랫폼 각각 개발하는 비용이 너무 큼
  - Flutter + Django → Django는 비동기 처리가 FastAPI보다 복잡
  - Provider보다 **컴파일 타임 안전성**이 높음
  - BLoC은 보일러플레이트가 너무 많음

- **세부 내용:**
  - 1. Flutter는 **단일 코드베이스**로 Android/iOS를 동시에 지원
  - 2. FastAPI는 **async/await 네이티브** 지원으로 동시 AI 분석 요청 처리에 유리
  - 3. Python은 **Gemini AI, TFLite, scikit-learn** 등 AI/ML 생태계가 풍부

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Decisions]]
- **Related:** [[Plantler v2.0 프로젝트 회고]], [[Plantler 프로젝트 개요 — 식물 관리 AI 앱]]
- **Raw Source:** [[00_Raw/02_아키텍처_의사결정.md]]
