"""Unit tests for UniversalCompilerBridge."""

from antigravity_k.engine.universal_compiler_bridge import UniversalCompilerBridge


def test_verify_python_syntax():
    good = "def f(): return 1\n"
    bad = "def f(\n"
    assert UniversalCompilerBridge.verify_syntax("test.py", good).is_valid is True
    assert UniversalCompilerBridge.verify_syntax("test.py", bad).is_valid is False


def test_verify_json_syntax():
    good = '{"key": "val", "num": 123}'
    bad = '{"key": "val",}'
    assert UniversalCompilerBridge.verify_syntax("config.json", good).is_valid is True
    assert UniversalCompilerBridge.verify_syntax("config.json", bad).is_valid is False


def test_verify_typescript_syntax():
    good = "function add(a: number, b: number): number { return a + b; }"
    bad = "function add(a: number, b: number { return a + b; }"  # missing closing paren
    assert UniversalCompilerBridge.verify_syntax("app.ts", good).is_valid is True
    assert UniversalCompilerBridge.verify_syntax("app.ts", bad).is_valid is False


def test_verify_rust_syntax():
    good = 'fn main() { println!("hello"); }'
    bad = 'fn main() { println!("hello");'  # missing closing brace
    assert UniversalCompilerBridge.verify_syntax("main.rs", good).is_valid is True
    assert UniversalCompilerBridge.verify_syntax("main.rs", bad).is_valid is False
