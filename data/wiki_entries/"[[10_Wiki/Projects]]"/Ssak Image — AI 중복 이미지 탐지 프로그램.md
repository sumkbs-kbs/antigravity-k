---
id: 11
category: "[[10_Wiki/Projects]]"
tags: ["projects", "프로젝트", "이미지처리", "중복탐지", "ai"]
created: 2026-05-04T09:42:52.095637
---

# [[Ssak Image — AI 중복 이미지 탐지 프로그램]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> Ssak Image는 대량의 이미지 폴더에서 **중복/유사 이미지**를 AI로 찾아주는 데스크탑 프로그램이다.

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - **언어:** Python
  - **GUI:** CustomTkinter (모던 다크모드 UI)
  - **CNN 모델:** MobileNet V3 Small (경량 딥러닝 모델)
  - **해싱:** aHash (Average Hash), pHash (Perceptual Hash)
  - **유사도 검색:** HNSW (hnswlib — Approximate Nearest Neighbor)

- **세부 내용:**
  - Ssak Image는 대량의 이미지 폴더에서 **중복/유사 이미지**를 AI로 찾아주는 데스크탑 프로그램이다.
  - 수천~수만 장의 사진 속에서 같거나 비슷한 이미지를 자동으로 그룹핑하고, 어떤 것을 삭제할지 추천한다.

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Projects]]
- **Related:** [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램_1]], [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램]], [[Ssak File — 버전 진화 기록 (1.0 → 1.1)]]
- **Raw Source:** [[00_Raw/18_SsakImage_프로젝트_개요.md]]
