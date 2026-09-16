# NX-09-F03 handoff — 첨부(이미지)가 실제로 모델에 도달한다 (2026-09-16)

카드: `docs/18` §NX-09 / `docs/19` §NX-09 의 미해결 **F03**. 선행: NX-09 본체(REVIEW), 그 안에서
F06 은 NOT_REPRODUCED 로 닫혔다.
State: **REVIEW** — 실 UI 동선에서 계약 green(증인 T4), 계약 시험·회귀 green. 독립 검토자·출시
판단은 미실시(소유자 미배정).
소유(작업): Buffy. 검토자: 미지정. 결정 문서: **ADR-0005**(수용).

## 1. 무엇이 결함이었나 (측정)

화면은 파일명 텍스트만 넣고 바이트는 보내지 않았다 — 사용자는 붙였다고 믿고 모델은 파일명만
봤다. 손실 지점은 다섯 곳이었고(요청 스키마 부재 · 관리자 납작화 · 에이전트 프롬프트 문자열 경로 ·
어댑터 4종의 개별 재구성 · 문자열 가정 코드), 그래서 "스키마 한 줄 추가"로 끝나지 않았다.
상세·실측 증상: `f03/before.md`, 추적 근거: `f03/probe-trace.json`, 계약: `docs/adr/0005`.

## 2. 무엇을 했나 (요약)

- `engine/multimodal.py` 신설 — 파싱·검증·내부 정규형·표면 변환의 **단일 소유자**.
- 내부 정규형은 `content`(문자열) + `images`/`image_mimes`: 파트 배열을 그대로 흘리면
  `content` 를 문자열로 가정하는 코드가 500 으로 죽는다(실측).
- OpenAI 호환 / Ollama 네이티브 / Anthropic / Nim·OpenRouter 어댑터가 같은 변환 함수를 쓴다.
- 에이전트 경로는 프롬프트 **문자열 옆** 별도 채널로 이미지를 싣는다(압축·예산 계산과 분리).
- 화면은 실제 바이트를 보내고 첨부 칩으로 보여 주며, 서버 거부 사유를 toast 로 노출한다.
- 저장소·스냅샷에는 텍스트만 남는다(정책) — 이미지는 **그 턴에만** 간다.

## 3. 바뀐 파일

```
신규  src/antigravity_k/engine/multimodal.py
신규  tests/test_nx09_f03_multimodal_attachments.py        (21 passed)
신규  docs/adr/0005-multimodal-attachments.md
      src/antigravity_k/engine/model_manager.py            (납작화 제거·images kwarg)
      src/antigravity_k/engine/tool_loop.py                (이번 턴 이미지 별도 채널)
      src/antigravity_k/engine/provider_adapters/inference_providers.py (어댑터 4종 통일)
      src/antigravity_k/engine/direct_task_execution.py    (작업 프롬프트 문자열 보장)
      src/antigravity_k/engine/task_context_snapshot.py    (텍스트만 저장·파트 허용)
      src/antigravity_k/engine/orchestrator_{context,analysis,execution,verification}_handlers.py
                                                           (구조화 필드 보존·텍스트 접기)
      src/antigravity_k/api/routes/chat.py                 (attachments 검증·주입·거부)
      dashboard/src/components/Chat/ChatPage.tsx           (바이트 전송·칩·빠른 거부)
      dashboard/src/api/client.ts                          (400 사유 노출)
      dashboard/src/styles/index.css                       (첨부 칩)
      dashboard/e2e/tests/nx09-user-journey.spec.ts        (T4 를 계약으로 승격)
      tests/test_model_manager_stream.py                   (납작화 계약 → 끌어올리기 계약)
```

## 4. 검증 (재현 명령은 `commands.txt`)

- 증인 `nx09-user-journey.spec.ts` **8 passed** (`--workers=1`): T4 가
  `imageReachedProvider: true` · 표면 `/api/chat` · `secondTurnWithImage: 0`.
- 계약 시험 21 passed · 관련 pytest 254 passed · 넓은 선택 408 passed / 0 failed.
- 추적 탐침이 provider 본문에 PNG base64 도달을 확인(`f03/probe-trace.json`).
- **UI 증인은 `pnpm build` 가 전제**다(NX-09-F04). 번들 표식 검사에 `chat-attachment-chip` 을
  추가해, 낡은 번들이면 "빌드 후 다시 실행하라"로 **명시적으로** 실패한다.

## 5. 다음 소유자에게

1. **이미지 재전송 정책**: 저장소에 base64 를 넣지 않기로 했으므로 이어지는 턴은 파일명 표식만
   본다. 재전송이 필요하면 저장 크기·압축과 함께 결정해야 한다(ADR-0005 §3 후속).
2. **압축과 첨부의 상호작용**: 긴 대화 압축은 텍스트만 다룬다 — 압축 뒤 이미지 의미 보존은 미정.
3. **live/cloud provider 의 실제 Vision 품질**: 이 카드는 fake provider 로 **전달**만 증명했다.
   품질(정확도)은 EX-01 계열 축이다.
4. **NX-10(후보 고정)**: 이 작업이 `model_manager.py`·`tool_loop.py`·`provider_adapters/**`·
   `chat.py`·대시보드 소스를 바꿨으므로 후보 지문을 **새로 고정**해야 한다.
5. 남은 NX-09 항목: `F04`(서빙 번들 신선도 절차), cue lexicon 회수율(소유자 미지정),
   미실시 동선(취소·재시도·disk-full·연타·keyboard-only·작은 화면).
