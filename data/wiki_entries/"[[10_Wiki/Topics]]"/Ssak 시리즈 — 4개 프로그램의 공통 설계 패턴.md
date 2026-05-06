---
id: 76
category: "[[10_Wiki/Topics]]"
tags: ["topics", "공통패턴", "시리즈", "아키텍처", "디자인패턴"]
created: 2026-05-04T09:42:52.225356
---

# [[Ssak 시리즈 — 4개 프로그램의 공통 설계 패턴]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> 1. **Ssak File** (ssakfile_pro) — AI 문서 검색/관리

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - **Ssak File**: 온라인 KR-SBERT → 오프라인 모델 → 키워드 검색
  - **Ssak Image**: OpenVINO → ONNX Runtime → PyTorch
  - **Ssak Language**: Gemini → OpenAI → Ollama (로컬)
  - **패턴**: 항상 "최선 → 차선 → 최소한" 3단계
  - PyInstaller: 직접 배포용 `.exe`

- **세부 내용:**
  - 1. **Ssak File** (ssakfile_pro) — AI 문서 검색/관리
  - 2. **Ssak Image** — AI 중복 이미지 탐지
  - 3. **Ssak Language** — AI 다국어 학습 도구
  - 4. **Ssak Delete** — (삭제 유틸리티)
  - 네 프로그램 모두 CustomTkinter를 사용한 다크모드 기본 데스크탑 UI.
  - Material Design 스타일의 모던한 외관을 유지.
  - > "같은 패턴을 반복하면 개발 속도가 기하급수적으로 빨라진다."
  - > "4개 프로그램의 가장 큰 공통점: '인터넷 없이도 동작해야 한다'는 제약이 설계를 지배한다."

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak File — 버전 진화 기록 (1.0 → 1.1)]], [[Ssak Image — 데스크탑 패키징과 Microsoft Store 배포]], [[Ssak Language — 프레임 Lazy Loading으로 앱 시작 최적화]]
- **Raw Source:** [[00_Raw/26_Ssak_시리즈_공통_패턴.md]]
