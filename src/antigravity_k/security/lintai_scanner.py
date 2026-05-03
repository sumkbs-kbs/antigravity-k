import subprocess
import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class LintaiScanner:
    """
    lintai를 이용한 에이전트 아티팩트(스킬, MCP 구성 파일 등)의 정책/보안 검증기.
    """
    def __init__(self, executable_path: str = "lintai"):
        self.executable_path = executable_path

    def is_installed(self) -> bool:
        """lintai 바이너리가 시스템에 설치되어 있는지 확인합니다."""
        try:
            result = subprocess.run(
                [self.executable_path, "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def scan_file(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        주어진 파일을 스캔하여 보안 검증 결과를 반환합니다.
        반환값: (is_safe, scan_results)
        """
        if not Path(file_path).exists():
            return False, {"error": f"File not found: {file_path}"}

        if not self.is_installed():
            # P1 수정: strict 모드 시 Fail-Closed 정책 적용
            strict = os.environ.get("AGK_SEC_LINTAI_STRICT", "false").lower() == "true"
            if strict:
                logger.error("lintai is not installed. BLOCKING under strict mode.")
                return False, {"error": "lintai not installed (strict mode: Fail-Closed)"}
            logger.warning("lintai is not installed. Skipping security scan (Fail-Open).")
            return True, {"warning": "lintai not installed — install for production security"}

        try:
            # json 포맷으로 스캔 결과 요청
            result = subprocess.run(
                [self.executable_path, "scan", file_path, "--format", "json"],
                capture_output=True,
                text=True,
                check=False
            )
            
            # returncode 0: no blocking findings
            # returncode 1: blocking findings were emitted
            # returncode 2: execution or configuration error
            
            is_safe = (result.returncode == 0)
            parsed_output = {}
            if result.stdout.strip():
                try:
                    parsed_output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    parsed_output = {"raw_output": result.stdout}
            
            if not is_safe:
                logger.error(f"Lintai scan failed for {file_path}. Return code: {result.returncode}")
                logger.error(f"Lintai output: {result.stdout}")
            else:
                logger.info(f"Lintai scan passed for {file_path}.")

            return is_safe, parsed_output

        except Exception as e:
            logger.error(f"Error executing lintai scan on {file_path}: {e}")
            return False, {"error": str(e)}

    def scan_mcp_config(self, mcp_config_path: str) -> bool:
        """
        .mcp.json 파일 등의 MCP 설정을 스캔합니다.
        """
        is_safe, results = self.scan_file(mcp_config_path)
        return is_safe

    def scan_skill_file(self, skill_file_path: str) -> bool:
        """
        SKILL.md 등의 스킬/프롬프트 지시사항 파일을 스캔합니다.
        """
        is_safe, results = self.scan_file(skill_file_path)
        return is_safe
