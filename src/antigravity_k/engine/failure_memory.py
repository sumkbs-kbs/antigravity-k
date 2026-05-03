"""
Antigravity-K: 실패 학습 메모리 (FailureMemory)
===============================================
E-3: 실패 패턴을 기록하고 동일 실수를 방지합니다.
"""
import json
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_LOG = ".antigravity/failure_log.jsonl"


class FailureMemory:
    """
    에이전트의 실패를 기억하고, 같은 실수를 반복하지 않도록 합니다.
    
    동작:
    1. record(): 실패 발생 시 패턴/원인/해결책을 기록
    2. find_similar(): 새 작업 전 유사 실패 이력 검색
    3. build_prompt(): 에이전트에게 "이전 실패" 컨텍스트 주입
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self._log_path = os.path.join(project_root, _DEFAULT_LOG)
        self._session_failures: List[Dict] = []  # 현재 세션 내 실패
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
    
    def record(
        self,
        tool: str,
        error_text: str,
        args_summary: str = "",
        fix_applied: str = "",
        success_after_fix: bool = False,
    ):
        """실패를 기록합니다."""
        entry = {
            "tool": tool,
            "error_pattern": self._extract_pattern(error_text),
            "error_text": error_text[:500],
            "args_summary": args_summary[:200],
            "fix_applied": fix_applied,
            "success_after_fix": success_after_fix,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._session_failures.append(entry)
        
        # 디스크에 영속 저장 (JSONL)
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[FailureMemory] Failed to write log: {e}")
    
    def find_similar(self, task_or_error: str, max_results: int = 3) -> List[Dict]:
        """유사한 과거 실패를 검색합니다."""
        results = []
        keywords = set(re.findall(r'[a-zA-Z_]{3,}', task_or_error.lower()))
        
        # 세션 내 실패 우선 검색
        for entry in reversed(self._session_failures):
            if self._is_similar(entry, keywords):
                results.append(entry)
                if len(results) >= max_results:
                    return results
        
        # 영속 로그 검색
        if os.path.exists(self._log_path):
            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if self._is_similar(entry, keywords):
                                results.append(entry)
                                if len(results) >= max_results:
                                    return results
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
        
        return results
    
    def build_prompt(self, task: str) -> str:
        """에이전트에게 주입할 실패 학습 컨텍스트를 생성합니다."""
        similar = self.find_similar(task)
        if not similar:
            return ""
        
        lines = ["\n<failure_memory>"]
        lines.append("⚠️ 과거 유사 작업에서의 실패 기록 (같은 실수를 반복하지 마세요):")
        for f in similar:
            fix_info = f" → 해결: {f['fix_applied']}" if f.get("fix_applied") else ""
            lines.append(f"- [{f['tool']}] {f['error_pattern']}{fix_info}")
        lines.append("</failure_memory>")
        return "\n".join(lines)
    
    def get_session_stats(self) -> Dict:
        """현재 세션의 실패 통계를 반환합니다."""
        total = len(self._session_failures)
        if total == 0:
            return {"total": 0, "unique_tools": 0, "fixed": 0}
        
        tools = set(f["tool"] for f in self._session_failures)
        fixed = sum(1 for f in self._session_failures if f.get("success_after_fix"))
        return {"total": total, "unique_tools": len(tools), "fixed": fixed}
    
    def _extract_pattern(self, error_text: str) -> str:
        """에러 텍스트에서 핵심 패턴을 추출합니다."""
        # Python 에러 타입 추출
        match = re.search(r'(\w+Error|\w+Exception):\s*(.{0,100})', error_text)
        if match:
            return f"{match.group(1)}: {match.group(2).strip()}"
        
        # 일반적인 에러 메시지
        if "command not found" in error_text.lower():
            return "command_not_found"
        if "permission denied" in error_text.lower():
            return "permission_denied"
        if "no such file" in error_text.lower():
            return "file_not_found"
        
        # 첫 줄만 반환
        first_line = error_text.strip().split("\n")[0]
        return first_line[:100]
    
    def _is_similar(self, entry: Dict, keywords: set) -> bool:
        """키워드 기반 유사도 판단."""
        entry_text = f"{entry.get('tool', '')} {entry.get('error_pattern', '')} {entry.get('args_summary', '')}".lower()
        entry_words = set(re.findall(r'[a-zA-Z_]{3,}', entry_text))
        overlap = len(keywords & entry_words)
        return overlap >= 2
