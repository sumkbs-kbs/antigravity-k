---
id: 69
category: "[[10_Wiki/Topics]]"
tags: ["topics", "데이터베이스", "sqlite", "동시성", "멀티프로세스"]
created: 2026-05-04T09:42:52.213864
---

# [[Ssak Reader 데이터베이스 동시성 문제와 해결]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> 백그라운드 인덱서가 멀티프로세스로 파일을 처리하면서, 여러 워커가 동시에 SQLite에 쓰기를 시도했다.

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - `database is locked` 에러 반복
  - `database disk image is malformed` (최악의 경우)
  - 인덱싱 속도 저하 또는 실패

- **세부 내용:**
  - 백그라운드 인덱서가 멀티프로세스로 파일을 처리하면서, 여러 워커가 동시에 SQLite에 쓰기를 시도했다.
  - 결과:
  - ```python
  - conn.execute("PRAGMA journal_mode=WAL")
  - ```
  - 읽기와 쓰기를 동시에 처리할 수 있게 해주는 SQLite의 핵심 옵션.
  - ```python
  - conn.execute("PRAGMA busy_timeout=30000")  # 30초 대기

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Topics]]
- **Related:** [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램]], [[Ssak Reader AI 의미론적 검색 아키텍처]], [[Ssak Reader 경고 억제 시스템 — 깨끗한 터미널의 기술]]
- **Raw Source:** [[00_Raw/15_SsakReader_데이터베이스_동시성.md]]
