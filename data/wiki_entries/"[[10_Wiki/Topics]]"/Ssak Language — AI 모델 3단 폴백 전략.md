---
id: 62
category: "[[10_Wiki/Topics]]"
tags: ["topics", "ai모델", "gemini", "openai", "ollama", "폴백시스템"]
created: 2026-05-04T09:42:52.201631
---

# [[Ssak Language — AI 모델 3단 폴백 전략]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> - Gemini API 키가 없을 수 있다

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - Gemini API 키가 없을 수 있다
  - OpenAI API는 유료다
  - 사내 환경에서는 외부 API 접속이 차단될 수 있다
  - 무료 Tier로 시작 가능
  - 한국어 생성 품질이 좋음

- **세부 내용:**
  - `ai_model.py`의 `UnifiedModel` 클래스가 3개 AI 백엔드를 통합:
  - ```python
  - class UnifiedModel:
  - ```
  - ```python
  - import google.generativeai as genai
  - genai.configure(api_key=gemini_key)
  - ```

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Language — AI 기반 다국어 학습 프로그램]], [[Plantler AI 식물 분석 시스템]], [[Plantler AI 식물 분석 시스템_1]]
- **Raw Source:** [[00_Raw/23_SsakLanguage_AI_모델_폴백.md]]
