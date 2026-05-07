from antigravity_k.tools.media_gen_tools import (
    GenerateImageTool,
    GenerateAudioTool,
    GenerateVideoTool,
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


# Note: Actual generation tests are omitted from unit tests as they require
# MLX backend, huge downloads, and take several minutes/seconds.
# We test the schema and initialization instead.
