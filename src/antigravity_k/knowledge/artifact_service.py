import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class ArtifactService:
    """
    Google AI Studio / Stitch 패턴을 반영하여,
    에이전트가 생성하는 시각적/구조적 산출물(Markdown, UI Component 등)을
    단순 채팅이 아닌 전용 디렉토리에 파일로 분리 저장하고 버전을 관리합니다.
    """
    def __init__(self, artifacts_dir: Optional[str] = None):
        if artifacts_dir is None:
            base_dir = Path(__file__).resolve().parent.parent / "data" / "artifacts"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.artifacts_dir = str(base_dir)
        else:
            self.artifacts_dir = artifacts_dir
            Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
            
        self._task_dirs = {}

    def create_artifact(self, name: str, content: str, extension: str = "md") -> str:
        """새로운 아티팩트 생성 (파일 이름이 겹치면 타임스탬프로 구분)"""
        safe_name = "".join([c if c.isalnum() else "_" for c in name]).strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.{extension}"
        filepath = os.path.join(self.artifacts_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Artifact created: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to create artifact {filename}: {e}")
            return f"Error: {e}"

    def get_artifact(self, filename: str) -> Optional[str]:
        """아티팩트 내용 조회"""
        filepath = os.path.join(self.artifacts_dir, filename)
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read artifact {filename}: {e}")
            return None

    def list_artifacts(self) -> list:
        """저장된 아티팩트 목록 반환"""
        try:
            return os.listdir(self.artifacts_dir)
        except Exception as e:
            logger.error(f"Failed to list artifacts: {e}")
            return []

    def _get_task_dir(self, task_id: str) -> str:
        """작업 ID별 별도 디렉토리 경로 반환 및 생성 (충돌 방지를 위해 타임스탬프 추가)"""
        if task_id in self._task_dirs:
            return self._task_dirs[task_id]
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"task_{task_id}_{timestamp}"
        task_dir = os.path.join(self.artifacts_dir, dir_name)
        Path(task_dir).mkdir(parents=True, exist_ok=True)
        self._task_dirs[task_id] = task_dir
        return task_dir

    def create_auto_artifact(self, task_id: str, doc_type: str, content: str) -> str:
        """Autopilot 모드에서 생성하는 자동 산출물 저장"""
        task_dir = self._get_task_dir(task_id)
        filepath = os.path.join(task_dir, f"{doc_type}.md")
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Auto artifact generated: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to generate auto artifact {doc_type} for task {task_id}: {e}")
            return ""

    def generate_plan(self, task_id: str, description: str, approach: str) -> str:
        content = f"# Implementation Plan (Task: {task_id})\n\n"
        content += f"## Description\n{description}\n\n"
        content += f"## Approach\n{approach}\n"
        return self.create_auto_artifact(task_id, "plan", content)

    def generate_checklist(self, task_id: str, steps: list) -> str:
        content = f"# Task Checklist (Task: {task_id})\n\n"
        for step in steps:
            content += f"- [ ] {step}\n"
        return self.create_auto_artifact(task_id, "checklist", content)

    def generate_review(self, task_id: str, review_notes: str) -> str:
        content = f"# Implementation Review (Task: {task_id})\n\n"
        content += f"## Review Notes\n{review_notes}\n"
        return self.create_auto_artifact(task_id, "implementation_review", content)

    def generate_result(self, task_id: str, summary: str, status: str = "COMPLETED") -> str:
        content = f"# Final Result (Task: {task_id})\n\n"
        content += f"**Status:** {status}\n\n"
        content += f"## Summary\n{summary}\n"
        return self.create_auto_artifact(task_id, "result", content)

    def generate_error_report(self, task_id: str, error_message: str) -> str:
        content = f"# Error Report (Task: {task_id})\n\n"
        content += f"## Error Message\n{error_message}\n\n"
        content += "## Status\nFAILED\n"
        return self.create_auto_artifact(task_id, "error_report", content)
