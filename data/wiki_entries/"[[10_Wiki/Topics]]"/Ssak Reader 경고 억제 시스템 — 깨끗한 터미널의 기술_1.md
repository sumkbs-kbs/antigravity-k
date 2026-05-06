---
id: 77
category: "[[10_Wiki/Topics]]"
tags: ["topics", "경고억제", "터미널관리", "c라이브러리", "클린코드"]
created: 2026-05-04T09:42:52.228047
---

# [[Ssak Reader 경고 억제 시스템 — 깨끗한 터미널의 기술]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> 프로그램을 실행하면 수십 줄의 경고 메시지가 터미널을 덮었다:

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - MuPDF의 `cmsOpenProfileFromMem` 에러
  - OpenPyXL의 스타일/확장 경고
  - HuggingFace의 FutureWarning
  - libpng의 iCCP 프로파일 경고
  - Bad CRC-32 for Office 파일

- **세부 내용:**
  - 프로그램을 실행하면 수십 줄의 경고 메시지가 터미널을 덮었다:
  - 이 메시지들은 모두 **기능에 영향 없는 비치명적 경고**였지만, 진짜 중요한 에러를 찾기 어렵게 만들었다.
  - ```python
  - warnings.filterwarnings("ignore", message=".*cmsOpenProfileFromMem.*")
  - warnings.filterwarnings("ignore", category=UserWarning, module="fitz")
  - warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
  - ```
  - Python 레벨 경고는 이것으로 해결.

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Reader 경고 억제 시스템 — 깨끗한 터미널의 기술]], [[Ssak Reader 데이터베이스 동시성 문제와 해결]]
- **Raw Source:** [[00_Raw/14_SsakReader_경고억제_기술.md]]
