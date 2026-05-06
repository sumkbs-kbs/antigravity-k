---
id: 82
category: "[[10_Wiki/Topics]]"
tags: ["topics", "ai", "의미검색", "sbert", "성능최적화"]
created: 2026-05-04T09:42:52.238332
---

# [[Ssak Reader AI 의미론적 검색 아키텍처]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> KR-SBERT 모델은 로딩에 ~15-20초가 걸린다. 앱 시작마다 이 시간을 잡아먹으면 사용자가 떠난다.

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 모델은 앱 수명 동안 **한 번만** 로드
  - 스레드 안전한 초기화 (Double-checked locking)
  - 검색 결과를 `vector_cache.pkl`에 디스크 캐싱
  - 재검색 시 인코딩 스킵 → **50배 속도 향상**
  - 가용 메모리에 따른 동적 배치 크기 조정

- **세부 내용:**
  - KR-SBERT 모델은 로딩에 ~15-20초가 걸린다. 앱 시작마다 이 시간을 잡아먹으면 사용자가 떠난다.
  - → Lazy Loading으로 시작 시간을 **2-3초**로 단축 (83% 개선)
  - ```python
  - class AIFeatures:
  - _instance = None
  - _lock = threading.Lock()
  - def __new__(cls):
  - if cls._instance is None:

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램]]
- **Raw Source:** [[00_Raw/12_SsakReader_AI_의미검색_아키텍처.md]]
