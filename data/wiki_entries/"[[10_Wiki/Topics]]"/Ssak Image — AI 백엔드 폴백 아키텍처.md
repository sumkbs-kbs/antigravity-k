---
id: 73
category: "[[10_Wiki/Topics]]"
tags: ["topics", "ai백엔드", "openvino", "onnx", "pytorch", "폴백시스템"]
created: 2026-05-04T09:42:52.220119
---

# [[Ssak Image — AI 백엔드 폴백 아키텍처]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> - 어떤 PC에는 OpenVINO가 있고, 어떤 PC에는 ONNX Runtime만 있다

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 어떤 PC에는 OpenVINO가 있고, 어떤 PC에는 ONNX Runtime만 있다
  - GPU가 있는 PC도, 없는 PC도 있다
  - PyInstaller로 패키징하면 DLL 로딩이 또 다르게 동작한다

- **세부 내용:**
  - ```python
  - class OpenVINOEmbedder:
  - def __init__(self, onnx_path):
  - core = ov.Core()
  - model = core.read_model(onnx_path)
  - try:
  - self.compiled = core.compile_model(model, "GPU")
  - except:

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Image — AI 중복 이미지 탐지 프로그램]], [[Ssak Reader AI 의미론적 검색 아키텍처_1]], [[Ssak Reader 오프라인 모델 배포 전략_1]]
- **Raw Source:** [[00_Raw/19_SsakImage_AI_백엔드_아키텍처.md]]
