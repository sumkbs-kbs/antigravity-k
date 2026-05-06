---
id: 87
category: "[[10_Wiki/Topics]]"
tags: ["topics", "이미지처리", "해싱", "cnn", "hnsw", "알고리즘"]
created: 2026-05-04T09:42:52.249455
---

# [[Ssak Image — 이미지 중복 탐지 알고리즘 설계]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> - aHash(Average Hash): 이미지를 8x8로 축소 → 평균 밝기 기준으로 64비트 해시 생성

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - aHash(Average Hash): 이미지를 8x8로 축소 → 평균 밝기 기준으로 64비트 해시 생성
  - 해밍 거리(Hamming Distance)로 유사도 계산
  - `similarity = 1.0 - hamming_distance / 64.0`
  - 장점: 매우 빠름 (초당 수백 장)
  - 단점: 색상/구도 변경에 취약

- **세부 내용:**
  - Hash로 후보를 좁힌 뒤 → CNN으로 정밀 검증
  - **2단계 필터링**:
  - 1. Hash 유사도 ≥ 임계값 → 후보 그룹 생성
  - 2. 후보 그룹 내 CNN 유사도 ≥ 임계값 → 최종 확정
  - 모든 이미지 쌍을 직접 비교. O(n²)이지만 2000장까지는 충분히 빠르다.
  - ```python
  - import hnswlib
  - [[index]] = hnswlib.Index(space='l2', dim=64)

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Image — AI 중복 이미지 탐지 프로그램]], [[Plantler UIUX 디자인 진화 기록]], [[Ssak Image — AI 백엔드 폴백 아키텍처]]
- **Raw Source:** [[00_Raw/20_SsakImage_중복탐지_알고리즘.md]]
