from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from antigravity_k.engine.sandbox import SandboxRunner


class VoiceUnavailableError(RuntimeError):
    pass


class VoiceExecutionError(RuntimeError):
    pass


Transcriber = Callable[[bytes, str], str]
Synthesizer = Callable[[str], bytes]


class VoiceService:
    def __init__(
        self,
        transcriber: Transcriber | None = None,
        synthesizer: Synthesizer | None = None,
    ):
        self._transcriber = transcriber or _configured_transcriber
        self._synthesizer = synthesizer or _macos_synthesizer

    def transcribe(self, audio: bytes, suffix: str = ".wav") -> str:
        transcript = self._transcriber(audio, suffix).strip()
        if not transcript:
            raise VoiceExecutionError("speech transcription returned no text")
        return transcript

    def synthesize(self, text: str) -> bytes:
        normalized = text.strip()
        if not normalized:
            raise ValueError("speech text must not be blank")
        return self._synthesizer(normalized)


def _configured_transcriber(audio: bytes, suffix: str) -> str:
    raw_command = os.environ.get("AGK_STT_COMMAND_JSON", "").strip()
    if not raw_command:
        raise VoiceUnavailableError("speech-to-text is not configured; set AGK_STT_COMMAND_JSON to a JSON argv array")
    try:
        command = json.loads(raw_command)
    except json.JSONDecodeError as error:
        raise VoiceUnavailableError("AGK_STT_COMMAND_JSON is not valid JSON") from error
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise VoiceUnavailableError("AGK_STT_COMMAND_JSON must be a non-empty JSON string array")

    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
            audio_file.write(audio)
            path = audio_file.name
        result = SandboxRunner(
            project_root=os.getcwd(),
            enabled=True,
            network="none",
            timeout=600,
        ).execute(shlex.join([*command, path]))
        if not result.success:
            raise VoiceExecutionError((result.stderr or result.error).strip() or "speech transcription command failed")
        return result.stdout
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def _macos_synthesizer(text: str) -> bytes:
    say = shutil.which("say")
    if say is None:
        raise VoiceUnavailableError("local text-to-speech requires the macOS say command")
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as audio_file:
            path = audio_file.name
        result = SandboxRunner(
            project_root=os.getcwd(),
            enabled=True,
            network="none",
            timeout=120,
        ).execute(shlex.join([say, "-o", path, text]))
        if not result.success:
            raise VoiceExecutionError((result.stderr or result.error).strip() or "text-to-speech command failed")
        return Path(path).read_bytes()
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


__all__ = ["VoiceExecutionError", "VoiceService", "VoiceUnavailableError"]
