import io
from unittest.mock import patch

from antigravity_k.tools.media_gen_tools import (
    GenerateAudioTool,
    GenerateImageTool,
    GenerateVideoTool,
    _download_asset,
)


def test_generate_image_tool_initialization():
    tool = GenerateImageTool()
    assert tool.name == "generate_image"
    assert "prompt" in tool.parameters_schema["properties"]
    assert "output_path" in tool.parameters_schema["properties"]
    assert "aspect_ratio" in tool.parameters_schema["properties"]


def test_generate_audio_tool_initialization():
    tool = GenerateAudioTool()
    assert tool.name == "generate_audio"
    assert "text" in tool.parameters_schema["properties"]
    assert "output_path" in tool.parameters_schema["properties"]
    assert "voice" in tool.parameters_schema["properties"]


def test_generate_video_tool_initialization():
    tool = GenerateVideoTool()
    assert tool.name == "generate_video"
    assert "prompt" in tool.parameters_schema["properties"]
    assert "output_path" in tool.parameters_schema["properties"]


def test_download_asset_uses_validated_egress_boundary(tmp_path):
    destination = tmp_path / "model.bin"
    with patch(
        "antigravity_k.tools.media_gen_tools.safe_urlopen",
        return_value=io.BytesIO(b"model-data"),
    ) as safe_open:
        _download_asset("https://models.example/model.bin", str(destination))

    safe_open.assert_called_once_with("https://models.example/model.bin", allow_local=False)
    assert destination.read_bytes() == b"model-data"


# Note: Actual generation tests are omitted from unit tests as they require
# MLX backend, huge downloads, and take several minutes/seconds.
# We test the schema and initialization instead.
