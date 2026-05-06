---
id: 27
category: "[[10_Wiki/Projects]]"
tags: ["projects", "패키징", "pyinstaller", "msix", "microsoftstore", "배포"]
created: 2026-05-04T09:42:52.129196
---

# [[Ssak Image — 데스크탑 패키징과 Microsoft Store 배포]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> ```bash

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 단일 실행 파일 생성
  - DLL 경로 자동 등록 필수 (`_init_dll_directories()`)
  - PyTorch/OpenVINO/ONNX Runtime DLL이 패키징 후 경로가 달라짐
  - `os.add_dll_directory()`로 Windows 10 1607+ 대응
  - `package_msix.bat` 스크립트로 MSIX 패키지 빌드

- **세부 내용:**
  - ```bash
  - pyinstaller SsakImage.spec
  - ```
  - ```xml
  - <!-- AppxManifest.xml -->
  - <Identity Name="SsakImage" Publisher="..." Version="..." />
  - ```
  - PyInstaller로 빌드 후 실행하면:

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Projects]]
- **Related:** [[Ssak Reader Windows 호환성 이슈 모음]], [[Ssak Reader Windows 호환성 이슈 모음_1]], [[Ssak Reader 오프라인 모델 배포 전략]]
- **Raw Source:** [[00_Raw/21_SsakImage_패키징_배포.md]]
