# NX-09-F03 after — 첨부가 실제 바이트로 모델에 도달한다 (그 턴에만)

계약: `docs/adr/0005-multimodal-attachments.md`. 측정 조건: 작업 트리 소스 + `pnpm build` 로 현재
소스를 서빙 + 실 브라우저 + 실 hermetic 서버 + 가짜 provider.

## 1. 수정(제품 코드)

| # | 수정 | 파일 |
|---|---|---|
| ① | 요청 스키마: `attachments` 를 검증해(형식·크기·개수) 마지막 user 턴에 싣는다. 위반은 **400 + 사유 코드**(`unsupported_attachment_type`·`attachment_too_large`·`too_many_attachments`·`invalid_attachment_encoding`·`attachments_with_tools_unsupported`). tools passthrough 동반 시 명시 거부 | `api/routes/chat.py` |
| ② | 다중모달 단일 계약 신설: 파싱·검증·내부 정규형(`content` 문자열 + `images`/`image_mimes`)·표면 변환(OpenAI 파트 / Ollama `images` / Anthropic `source.base64`)·수집·프롬프트 메시지 | **신규** `engine/multimodal.py` |
| ③ | 관리자 스트림 준비: 파트를 납작하게 만들던 자리를 `normalize_message` 로 교체(텍스트는 접고 이미지는 **끌어올린다**). 프롬프트 문자열 경로도 `images` kwarg 를 싣는다 | `engine/model_manager.py` |
| ④ | provider 어댑터 4종(OpenAI 호환·Ollama 네이티브·Anthropic·Nim/OpenRouter)이 `adapter_messages(surface=...)` 한 곳을 쓰도록 통일 — 각자 풀던 정규화 루프 제거 | `engine/provider_adapters/inference_providers.py` |
| ⑤ | 에이전트 경로: 프롬프트 문자열 옆 **별도 채널**로 이번 턴 이미지를 전달(프롬프트 예산·압축 계산과 분리) | `engine/tool_loop.py` |
| ⑥ | 문자열 가정 코드 방어: 작업 프롬프트·검증 증거 수집·스냅샷에서 `flatten_content` 사용, 메시지를 새 dict 로 갈아치우며 구조화 필드를 버리던 6곳을 `{**기존, ...}` 로 교정, 스냅샷은 텍스트만 저장(파트/base64 금지) | `direct_task_execution.py`, `task_context_snapshot.py`, `orchestrator_context_handlers.py`, `orchestrator_analysis_handlers.py`, `orchestrator_execution_handlers.py`, `orchestrator_verification_handlers.py` |
| ⑦ | 화면: 파일을 실제로 읽어(base64) 첨부 칩으로 보여 주고 요청에 싣는다. 형식·크기는 왕복 전에 빠르게 거부하고, 서버 400 사유를 toast 로 보여 준다. Adaptive 모드에서는 조용히 버리지 않고 명시 거부 | `components/Chat/ChatPage.tsx`, `api/client.ts`, `styles/index.css` |

## 2. after 관측

증인 T4(수정 후 계약 시험, `test.fail` 제거):

```
composerText            : "[첨부 파일: nx09-attach.png] "   (이력 참조 표식 유지)
chipVisible/ chipMime   : true / "image/png"                 (전송 전 화면이 첨부를 보여 준다)
imageReachedProvider    : true
imageSurfaces           : ["/api/chat"]                      (Ollama 네이티브 표면에 images 로 도달)
secondTurnWithImage     : 0                                  (ADR-0005: 바이트는 그 턴에만)
```

추적 탐침(`f03_probe_trace.py` → `f03/probe-trace.json`, 실 uvicorn + 실 provider 대역):

```
attach_to_latest_user_turn : attachments=1 → images_on_last=1
collect_images(messages)   : 1        (상태 그래프를 지나도 살아 있었다)
prompt_message             : [... 1 ...]  (프롬프트 경로에서 이미지 1개가 실렸다)
images_reached_provider    : [{"path": "/api/chat", "body_len": 48156, "has_image": true}]
```

수정 전 같은 탐침은 `prompt_message` **호출 0회** · `normalize_message` 이미지 0개 ·
`images_reached_provider: []` 였다 — 탐침이 없었으면 "왜 아직 안 되지"를 반복했을 것이다.

## 3. 검증

- 계약 시험 `tests/test_nx09_f03_multimodal_attachments.py` **21 passed** — 검증·거부 사유, 내부
  정규형(content 문자열 유지), 파트 끌어올리기, 표면별 payload(ollama `images` / openai 파트 /
  anthropic `source.base64`), 스냅샷 텍스트 정책, 작업 프롬프트 문자열 보장.
- 기존 계약 시험 1건 **갱신**: `test_model_manager_stream.py::test_content_parts_flattened_to_string`
  은 "파트를 전부 텍스트로 납작하게 만든다"를 고정하고 있었다 — 그 동작이 곧 F03 이므로 계약을
  바꿨다(텍스트는 접고 이미지는 `images` 로 살린다).
- 증인 전량: `nx09-user-journey.spec.ts` **8 passed** (더 이상 expected-fail 없음).
- 관련 pytest **254 passed**(inference_providers·model_manager 3종·tool_loop·orchestrator 2종·
  task_context_snapshot·ctx01~03·conversation_api + F03) · 넓은 선택 **408 passed / 0 failed**.
- ruff clean, `tsc -b` clean.

## 4. 남긴 것 (이 결정의 경계)

- **이전 턴 이미지 재전송 없음**: 저장소에 base64 를 넣지 않기로 했으므로(ADR-0005 §2-6) 대화를
  이어 가면 모델은 파일명 표식만 본다. 재전송이 필요하면 저장 정책(압축·저장 크기)과 함께
  별도 카드로 결정해야 한다.
- **압축된 대화에서의 첨부 의미 보존**: 긴 대화의 컨텍스트 압축은 텍스트만 다룬다 — 압축 뒤에도
  이미지가 의미를 갖게 할지는 미정.
- **tools passthrough 경로**: 첨부는 400 으로 거부한다(지원하지 않음을 숨기지 않는다).
- 첨부는 fake provider 로만 측정했다 — cloud/live provider 의 실제 Vision 품질은 이 카드 범위 밖이다.
