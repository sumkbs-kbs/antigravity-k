---
id: 25
category: "[[10_Wiki/Projects]]"
tags: ["projects", "프로젝트", "버전관리", "진화"]
created: 2026-05-04T09:42:52.124613
---

# [[Ssak File — 버전 진화 기록 (1.0 → 1.1)]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> Ssak File(ssakfile_pro)은 기업 환경에서 문서를 AI로 검색·관리하는 데스크탑 프로그램이다.

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - 기본적인 파일 검색 기능
  - 단순 키워드 매칭 기반
  - 단일 스레드 처리
  - 기본적인 GUI
  - **KR-SBERT 의미론적 검색** 추가 (키워드가 아닌 '의미'로 검색)

- **세부 내용:**
  - Ssak File(ssakfile_pro)은 기업 환경에서 문서를 AI로 검색·관리하는 데스크탑 프로그램이다.
  - v1.0에서 v1.1로 진화하면서 핵심 아키텍처가 크게 개선되었다.
  - `ssakfile_pro javascript test` 폴더가 존재 → Electron 등으로 웹 기반 UI를 시도한 흔적.
  - 결국 Python 네이티브(CustomTkinter)로 귀결.
  - | 항목 | v1.0 | v1.1 |
  - |------|------|------|
  - | 검색 방식 | 키워드 매칭 | KR-SBERT 의미론적 검색 |
  - | 인덱싱 | 단일 스레드 | 멀티프로세스 + 배치 |

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Projects]]
- **Related:** [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램_1]], [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램]], [[Ssak Reader AI 의미론적 검색 아키텍처_1]]
- **Raw Source:** [[00_Raw/17_SsakFile_버전_진화.md]]
