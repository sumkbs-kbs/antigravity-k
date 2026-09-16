"""NX-09-F03 — 첨부(이미지)가 **실제로 모델에게 가는가**의 계약 시험.

무엇을 고정하는가
----------------
1. 계약(`engine/multimodal.py`): 형식·크기·개수 검증과 거부 사유, 표면별 변환.
2. 내부 정규형: `content` 는 **문자열**, 이미지는 message-level `images` — 텍스트 전용
   코드(정규식·`.strip()`·SQLite 바인딩·스냅샷 스키마)가 깨지지 않게 하는 계약이다.
3. 회귀: `model_manager` 가 이미지를 버리지도, `content` 를 파트 배열로 바꾸지도 않는다
   (F03 의 실제 형태는 \"사용자는 붙였다고 믿는데 모델은 파일명만 봤다\" 였다).
4. 표면별 payload: OpenAI 호환은 파트, Ollama 네이티브는 `images`, Anthropic 은 `source.base64`.
5. 저장 정책: 스냅샷(텍스트 전용 모델)에 파트/base64 가 들어가지 않는다.
"""

from __future__ import annotations

import base64
import json
from typing import cast

import pytest

from antigravity_k.engine import multimodal
from antigravity_k.engine.model_manager import ModelManager

PNG_BYTES = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes").decode("ascii")


def attachment(
    *,
    name: str = "shot.png",
    mime_type: str = "image/png",
    data_base64: str = PNG_BYTES,
) -> dict[str, object]:
    return {"name": name, "mime_type": mime_type, "data_base64": data_base64}


def message_with_image(text: str = "image") -> dict[str, object]:
    parsed = multimodal.parse_attachments([attachment()])
    return multimodal.attach_to_latest_user_turn([{"role": "user", "content": text}], parsed)[0]


# ── 1. 계약: 검증·거부 ────────────────────────────────────────────────


class TestAttachmentContract:
    def test_parses_and_summarizes_without_bytes(self) -> None:
        parsed = multimodal.parse_attachments([attachment()])
        summary = multimodal.summarize(parsed)
        assert summary == [{"name": "shot.png", "mime_type": "image/png", "bytes": len(base64.b64decode(PNG_BYTES))}]
        assert "data_base64" not in json.dumps(summary)

    def test_missing_field_is_rejected(self) -> None:
        raw = [{"name": "shot.png", "mime_type": "image/png"}]
        with pytest.raises(multimodal.AttachmentError) as excinfo:
            multimodal.parse_attachments(raw)
        assert excinfo.value.code == "invalid_attachment"

    def test_unsupported_type_is_rejected_with_reason(self) -> None:
        with pytest.raises(multimodal.AttachmentError) as excinfo:
            multimodal.parse_attachments([attachment(mime_type="image/svg+xml")])
        assert excinfo.value.code == "unsupported_attachment_type"
        assert "image/png" in excinfo.value.detail

    def test_invalid_base64_is_rejected(self) -> None:
        with pytest.raises(multimodal.AttachmentError) as excinfo:
            multimodal.parse_attachments([attachment(data_base64="not base64!!")])
        assert excinfo.value.code == "invalid_attachment_encoding"

    def test_byte_size_and_count_limits(self) -> None:
        big = base64.b64encode(b"x" * (multimodal.MAX_ATTACHMENT_BYTES + 1)).decode("ascii")
        with pytest.raises(multimodal.AttachmentError) as too_large:
            multimodal.parse_attachments([attachment(data_base64=big)])
        assert too_large.value.code == "attachment_too_large"

        with pytest.raises(multimodal.AttachmentError) as too_many:
            multimodal.parse_attachments([attachment()] * (multimodal.MAX_ATTACHMENTS + 1))
        assert too_many.value.code == "too_many_attachments"

    def test_path_components_are_stripped_from_name(self) -> None:
        parsed = multimodal.parse_attachments([attachment(name="../../etc/passwd.png")])
        assert parsed[0].name == "passwd.png"

    def test_absent_attachments_are_empty_not_error(self) -> None:
        assert multimodal.parse_attachments(None) == []
        assert multimodal.parse_attachments([]) == []


# ── 2. 내부 정규형과 표면 변환 ───────────────────────────────────────


class TestMessageConversion:
    def test_attach_keeps_content_a_string_and_carries_images(self) -> None:
        """content 는 문자열, 이미지는 message-level — 텍스트 전용 코드가 깨지지 않는다."""
        parsed = multimodal.parse_attachments([attachment()])
        messages = multimodal.attach_to_latest_user_turn(
            [{"role": "system", "content": "s"}, {"role": "user", "content": "look"}],
            parsed,
        )
        target = messages[1]
        text = cast(str, target["content"])
        assert text.startswith("look")
        assert target["images"] == [PNG_BYTES]
        assert target["image_mimes"] == ["image/png"]
        # 파일명 표식은 이력 참조용으로 남는다.
        assert multimodal.marker_text("shot.png") in text
        # 원본은 변하지 않는다(이력/스냅샷을 함께 들고 있다).
        assert "images" not in messages[0]

    def test_attach_without_user_turn_appends_one(self) -> None:
        parsed = multimodal.parse_attachments([attachment()])
        messages = multimodal.attach_to_latest_user_turn([{"role": "system", "content": "s"}], parsed)
        assert messages[-1]["role"] == "user"
        assert multimodal.has_images(messages[-1])

    def test_attach_does_not_duplicate_marker(self) -> None:
        parsed = multimodal.parse_attachments([attachment()])
        first = multimodal.attach_to_latest_user_turn([{"role": "user", "content": "look"}], parsed)
        second = multimodal.attach_to_latest_user_turn(first, parsed)
        assert cast(str, second[0]["content"]).count(multimodal.marker_text("shot.png")) == 1
        assert second[0]["images"] == [PNG_BYTES, PNG_BYTES]

    def test_content_parts_are_lifted_not_dropped(self) -> None:
        parts_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "parts request"},
                {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{PNG_BYTES}"}},
            ],
        }
        normalized = multimodal.normalize_message(parts_message)
        assert normalized["content"] == "parts request"
        assert normalized["images"] == [PNG_BYTES]
        assert normalized["image_mimes"] == ["image/webp"]

    def test_flatten_content_handles_both_forms(self) -> None:
        assert multimodal.flatten_content([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a b"
        assert multimodal.flatten_content("plain") == "plain"

    def test_ollama_surface_moves_images_into_images_field(self) -> None:
        converted = multimodal.to_ollama_messages([message_with_image("explain")])
        assert converted[0]["content"] == f"explain\n{multimodal.marker_text('shot.png')}"
        assert converted[0]["images"] == [PNG_BYTES]
        assert "image_mimes" not in converted[0]

    def test_openai_surface_uses_image_url_parts(self) -> None:
        converted = multimodal.to_openai_messages([message_with_image("explain")])
        parts = cast(list[dict[str, object]], converted[0]["content"])
        assert parts[0]["type"] == "text"
        assert parts[1]["type"] == "image_url"
        assert cast(dict[str, str], parts[1]["image_url"])["url"].startswith("data:image/png;base64,")
        assert "images" not in converted[0]

    def test_anthropic_surface_uses_base64_source(self) -> None:
        converted = multimodal.to_anthropic_messages([message_with_image("explain")])
        blocks = cast(list[dict[str, object]], converted[0]["content"])
        assert blocks[0]["type"] == "text"
        source = cast(dict[str, object], blocks[1]["source"])
        assert source == {"type": "base64", "media_type": "image/png", "data": PNG_BYTES}


# ── 3. 표면 payload 회귀 (F03 의 실제 형태) ──────────────────────────


class _StubProfile:
    name = "stub-model"


class _StubLoaded:
    profile = _StubProfile()


def _build_manager(monkeypatch: pytest.MonkeyPatch) -> ModelManager:
    monkeypatch.setattr(
        ModelManager,
        "_apply_dynamic_inference_config",
        lambda self, profile, messages, kwargs: (profile.name, 0.7, None, ""),
    )
    return ModelManager.__new__(ModelManager)


def test_stream_messages_keep_images_and_string_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """핵심 회귀 — 예전 `_prepare_stream_messages` 는 파트를 텍스트로 납작하게 만들었다."""
    manager = _build_manager(monkeypatch)
    prepared = manager._prepare_stream_messages(
        cast(object, _StubLoaded()),
        "prompt",
        {"raw_messages": [message_with_image("look")]},
    )
    assert isinstance(prepared[0]["content"], str), "content 가 문자열이 아니면 하위 텍스트 코드가 깨진다"
    assert multimodal.has_images(prepared[0]), "이미지가 사라졌다(F03 재발)"
    assert prepared[0]["images"] == [PNG_BYTES]


def test_stream_request_payload_per_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _build_manager(monkeypatch)
    loaded = cast(object, _StubLoaded())
    api_msgs = manager._prepare_stream_messages(loaded, "prompt", {"raw_messages": [message_with_image("look")]})

    native_request, _ = manager._build_stream_request(loaded, api_msgs, {}, is_openrouter=False)
    native_body = json.loads(native_request.data.decode("utf-8"))
    assert native_body["messages"][0]["images"] == [PNG_BYTES]
    assert "/api/chat" in native_request.full_url

    openai_request, _ = manager._build_stream_request(loaded, api_msgs, {}, is_openrouter=True)
    openai_body = json.loads(openai_request.data.decode("utf-8"))
    parts = openai_body["messages"][0]["content"]
    assert isinstance(parts, list), "OpenAI 호환 표면에서 파트가 사라졌다"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


# ── 4. 저장 정책: base64 는 저장소로 가지 않는다 ─────────────────────


def test_snapshot_flattens_multimodal_content_and_drops_bytes() -> None:
    from antigravity_k.engine.task_context_snapshot import _snapshot_message

    snapshot_message = _snapshot_message(cast(dict[str, str], message_with_image("snapshot")))
    assert snapshot_message.content == f"snapshot\n{multimodal.marker_text('shot.png')}"
    assert base64.b64encode(b"fake") not in snapshot_message.content.encode("utf-8")
    assert PNG_BYTES not in snapshot_message.content


def test_snapshot_still_accepts_parts_content() -> None:
    """파트 배열로 온 요청도 스냅샷 단계에서 실패하지 않아야 한다(예전에는 ValidationError)."""
    from antigravity_k.engine.task_context_snapshot import _snapshot_message

    parts_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "parts"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_BYTES}"}},
        ],
    }
    assert _snapshot_message(cast(dict[str, str], parts_message)).content == "parts"


def test_durable_message_check_tolerates_multimodal_content() -> None:
    from antigravity_k.engine.task_context_snapshot import _is_durable_message

    assert _is_durable_message(cast(dict[str, str], message_with_image("snapshot"))) is True
    transient = {
        "role": "system",
        "content": [{"type": "text", "text": "[Recalled Memory]\n..."}],
    }
    assert _is_durable_message(cast(dict[str, str], transient)) is False


def test_direct_task_latest_user_text_flattens_attachment_turns() -> None:
    """첨부 턴에서 작업 생성 프롬프트는 문자열이어야 한다(아니면 state_store 바인딩이 터진다)."""
    from antigravity_k.engine.direct_task_execution import DirectTaskExecution

    messages = [message_with_image("task prompt")]
    text = DirectTaskExecution._latest_user_text(cast(list[dict[str, str]], messages))
    assert isinstance(text, str)
    assert text.startswith("task prompt")
