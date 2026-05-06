---
id: 74
category: "[[10_Wiki/Topics]]"
tags: ["topics", "lazyloading", "최적화", "customtkinter", "모듈화"]
created: 2026-05-04T09:42:52.221653
---

# [[Ssak Language — 프레임 Lazy Loading으로 앱 시작 최적화]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> Ssak Language는 11개의 학습 모듈(프레임)을 가지고 있다.

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 앱 시작 시간: ~5초 → ~1초
  - 메모리 사용량: 사용하지 않는 프레임은 로드되지 않음
  - 사용자 체감: "클릭하면 바로 열린다" (첫 클릭만 약간 느림)
  - `ai_writing_workbook.py` — AI 작문 학습지
  - `free_writing.py` — 자유 작문

- **세부 내용:**
  - Ssak Language는 11개의 학습 모듈(프레임)을 가지고 있다.
  - 모든 프레임을 앱 시작 시 생성하면 CustomTkinter 위젯이 수천 개 만들어지면서 시작이 느려진다.
  - ```python
  - self._frame_classes = {
  - "UserSelectFrame": UserSelectFrame,
  - "HomeFrame": HomeFrame,
  - "AIWritingWorksheetFrame": AIWritingWorksheetFrame,
  - }

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Language — AI 기반 다국어 학습 프로그램]], [[Ssak Language — AI 모델 3단 폴백 전략]], [[Ssak Language — 게이미피케이션과 프리미엄 수익 모델]]
- **Raw Source:** [[00_Raw/25_SsakLanguage_Lazy_Loading_프레임.md]]
