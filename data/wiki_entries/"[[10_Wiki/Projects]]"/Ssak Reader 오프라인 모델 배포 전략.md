---
id: 12
category: "[[10_Wiki/Projects]]"
tags: ["projects", "배포", "오프라인", "huggingface", "기업환경"]
created: 2026-05-04T09:42:52.098332
---

# [[Ssak Reader 오프라인 모델 배포 전략]]

## 📌 한 줄 통찰 (The Karpathy Summary)
> 사내 네트워크에서 HuggingFace에 접속할 수 없다. SSL 인증서 검증 실패, 방화벽 차단 등으로 모델 다운로드가 불가능하다. 그런데 AI 검색 기능은 반드시 동작해야...

## 📖 구조화된 지식 (Synthesized Content)
- **추출된 패턴:**
  - KR-SBERT 모델(~892MB)을 `C:\ssakfile_models\kr-sbert\`에 저장
  - [[config.json]] 포함 11개 파일 완전 복사 확인
  - USB 드라이브로 사내 PC에 복사
  - 또는 네트워크 공유 드라이브를 통해 배포

- **세부 내용:**
  - 사내 네트워크에서 HuggingFace에 접속할 수 없다. SSL 인증서 검증 실패, 방화벽 차단 등으로 모델 다운로드가 불가능하다. 그런데 AI 검색 기능은 반드시 동작해야 한다.
  - `download_offline_model.py` 스크립트를 외부 환경에서 실행:
  - 앱 시작 시 `_get_model_path()` 메서드가 로컬 모델을 자동 감지하여 사용
  - HuggingFace 캐시는 **심링크(symlink)**를 사용한다. 단순 파일 복사로는 심링크의 타겟이 복사되지 않아 `[[config.json]]`이 빠진다.
  - 초기에는 알파벳순으로 스냅샷을 선택했지만, 불완전한 스냅샷이 선택되는 문제 발생.
  - → **파일이 가장 많은 스냅샷**을 선택하도록 개선하여 완전한 모델 복사 보장
  - ```python
  - if os.path.islink(src):

## ⚠️ 모순 및 업데이트 (Contradictions & RL Update)
- **과거 데이터와의 충돌:** 현재까지 발견된 모순 없음.
- **정책 변화:** 이 문서를 통해 분류 정책에 변화 없음.

## 🔗 지식 연결 (Graph)
- **Parent:** [[Projects]]
- **Related:** [[Ssak Reader (ssakfile_pro) — AI 기반 문서 관리 프로그램]], [[Plantler 배포 워크플로우 — SCP 직접 전송 방식_1]], [[Plantler 배포 워크플로우 — SCP 직접 전송 방식]]
- **Raw Source:** [[00_Raw/13_SsakReader_오프라인_모델_배포.md]]
