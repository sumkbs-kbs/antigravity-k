"""Tests for DeterministicCodeVerifier module."""

from antigravity_k.engine.code_verifier import DeterministicCodeVerifier


def test_verify_valid_python():
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = DeterministicCodeVerifier.verify_file("math_utils.py", content=code)
    assert res.is_valid is True


def test_verify_invalid_python_syntax():
    code = "def broken(\n    return 42"
    res = DeterministicCodeVerifier.verify_file("broken.py", content=code)
    assert res.is_valid is False
    assert res.error_type == "SyntaxError"
    feedback = res.format_feedback("broken.py")
    assert "SyntaxError Detected" in feedback


def test_verify_valid_json():
    json_str = '{"name": "antigravity", "version": "1.0"}'
    res = DeterministicCodeVerifier.verify_file("config.json", content=json_str)
    assert res.is_valid is True


def test_verify_invalid_json():
    json_str = '{"name": "antigravity", "version": }'
    res = DeterministicCodeVerifier.verify_file("config.json", content=json_str)
    assert res.is_valid is False
    assert res.error_type == "JSONDecodeError"


def test_verify_valid_yaml():
    yaml_str = "models:\n  - name: qwen\n    role: worker\n"
    res = DeterministicCodeVerifier.verify_file("config.yaml", content=yaml_str)
    assert res.is_valid is True


def test_verify_invalid_yaml_reports_line():
    yaml_str = "models: [qwen\n"
    res = DeterministicCodeVerifier.verify_file("config.yaml", content=yaml_str)
    assert res.is_valid is False
    assert res.error_type == "YAMLParseError"
    assert res.line_number == 2
