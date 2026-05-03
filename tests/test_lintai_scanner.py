import os
from pathlib import Path
from antigravity_k.security.lintai_scanner import LintaiScanner

def test_lintai_scanner_initialization():
    scanner = LintaiScanner()
    assert scanner is not None
    assert hasattr(scanner, 'executable_path')
    assert hasattr(scanner, 'is_installed')

def test_lintai_scanner_fallback(tmp_path):
    scanner = LintaiScanner()
    # 임의의 파일을 생성
    test_file = tmp_path / "test_script.py"
    test_file.write_text("print('hello world')")
    
    # scan_skill_file 호출 (실제 lintai 바이너리가 없을 경우 안전하게 True 또는 False 경고를 반환하는지 테스트)
    result = scanner.scan_skill_file(str(test_file))
    # lintai가 없는 환경에서는 fallback 로직에 따라 기본 True를 반환하도록 설계되었다면 통과할 것
    assert isinstance(result, bool)

def test_lintai_scan_mcp_config(tmp_path):
    scanner = LintaiScanner()
    test_config = tmp_path / "mcp_config.json"
    test_config.write_text('{"mcpServers": {}}')
    
    result = scanner.scan_mcp_config(str(test_config))
    assert isinstance(result, bool)
