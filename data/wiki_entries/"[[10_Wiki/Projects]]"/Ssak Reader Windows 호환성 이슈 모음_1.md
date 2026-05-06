---
id: 14
category: "[[10_Wiki/Projects]]"
tags: ["projects", "windows", "호환성", "인코딩", "pyinstaller"]
created: 2026-05-04T09:42:52.101624
---

# [[Ssak Reader Windows 호환성 이슈 모음]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> 한국어 Windows는 기본적으로 **CP949** 인코딩을 사용한다.

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 심링크 생성에 관리자 권한 필요
  - `os.readlink()`로 읽은 경로가 상대경로 → `os.path.normpath()`로 정규화 필요

- **세부 내용:**
  - 한국어 Windows는 기본적으로 **CP949** 인코딩을 사용한다.
  - 이모지(🔍, ✅, ❌)가 포함된 출력에서 `UnicodeEncodeError` 발생.
  - ```python
  - if sys.platform == 'win32':
  - import ctypes
  - kernel32 = ctypes.windll.kernel32
  - kernel32.SetConsoleOutputCP(65001)  # UTF-8
  - sys.stdout.reconfigure(encoding='utf-8', errors='replace')

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Projects]]
- **Related:** [[Ssak Reader Windows 호환성 이슈 모음]], [[Ssak Reader 오프라인 모델 배포 전략_1]], [[Ssak Reader 오프라인 모델 배포 전략]]
- **Raw Source:** [[00_Raw/16_SsakReader_Windows_호환성.md]]
