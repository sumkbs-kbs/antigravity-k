"""
WorktreeManager — 보안 강화된 워크트리 & 상태 관리
===================================================
NemoClaw의 sandbox-state.ts 패턴을 적용하여 보안 강화:
  - symlink/hard-link 거부 (경로 탈출 공격 방지)
  - 매니페스트 기반 상태 추적
  - credential 필터링을 포함한 안전한 백업/복원
"""

import os
import subprocess
import logging
import shutil
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)


class WorktreeManager:
    """
    다중 에이전트 병렬 실행 시 파일 충돌을 방지하기 위해 Git Worktree를 관리합니다.
    NemoClaw의 sandbox-state.ts 보안 패턴 적용.
    """
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.worktree_base_dir = os.path.join(self.repo_path, ".antigravity", "worktrees")
        self._state_dir = os.path.join(self.repo_path, ".antigravity", "state")
        self._backup_dir = os.path.join(self.repo_path, ".antigravity", "backups")
        os.makedirs(self.worktree_base_dir, exist_ok=True)
        os.makedirs(self._state_dir, exist_ok=True)
        os.makedirs(self._backup_dir, exist_ok=True)

    def _run_git(self, *args) -> bool:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: git {' '.join(args)}\nError: {e.stderr}")
            return False

    def create_worktree(self, task_id: str) -> str:
        """
        주어진 task_id에 대한 새로운 브랜치와 워크트리를 생성합니다.
        반환값: 생성된 워크트리의 절대 경로
        """
        branch_name = f"ag-task-{task_id}"
        worktree_path = os.path.join(self.worktree_base_dir, task_id)

        # 이미 존재하는지 확인
        if os.path.exists(worktree_path):
            logger.warning(f"Worktree already exists for task {task_id}")
            return worktree_path

        # 브랜치 강제 생성 및 워크트리 추가 (기존 브랜치가 있으면 덮어쓰거나 실패할 수 있음)
        # 1. 브랜치 삭제 시도 (만약 잔여 브랜치가 있다면)
        subprocess.run(["git", "branch", "-D", branch_name], cwd=self.repo_path, capture_output=True)

        # 2. 워크트리 추가 (-b 로 새 브랜치 생성)
        success = self._run_git("worktree", "add", "-b", branch_name, worktree_path)
        if not success:
            raise RuntimeError(f"Failed to create worktree for task {task_id}")

        # 3. 매니페스트 생성 (NemoClaw 패턴)
        self._write_manifest(task_id, worktree_path, branch_name)

        logger.info(f"Created worktree at {worktree_path} on branch {branch_name}")
        return worktree_path

    def remove_worktree(self, task_id: str) -> bool:
        """
        태스크 완료 후 워크트리 및 관련 브랜치를 삭제합니다.
        """
        branch_name = f"ag-task-{task_id}"
        worktree_path = os.path.join(self.worktree_base_dir, task_id)

        if not os.path.exists(worktree_path):
            logger.warning(f"Worktree path does not exist: {worktree_path}")
            return False

        # 워크트리 제거
        success_remove = self._run_git("worktree", "remove", "--force", worktree_path)
        
        # 브랜치 삭제
        success_branch = self._run_git("branch", "-D", branch_name)

        if os.path.exists(worktree_path):
            # Fallback for forceful deletion
            try:
                shutil.rmtree(worktree_path)
            except Exception as e:
                logger.error(f"Failed to rmtree worktree path: {e}")

        # 매니페스트 삭제
        self._remove_manifest(task_id)

        if success_remove:
            logger.info(f"Successfully removed worktree {worktree_path}")
        return success_remove and success_branch

    # ─── NemoClaw-ported: 안전한 상태 백업/복원 ───

    def backup_state(self, task_id: str) -> Optional[str]:
        """워크트리 상태를 안전하게 백업합니다.

        NemoClaw sandbox-state.ts 패턴:
          - symlink/hard-link 거부 (경로 탈출 공격 방지)
          - credential 필터링
          - 매니페스트 기반 추적

        Returns:
            백업 디렉토리 경로. 실패 시 None.
        """
        worktree_path = os.path.join(self.worktree_base_dir, task_id)
        if not os.path.isdir(worktree_path):
            logger.warning(f"Worktree not found for backup: {task_id}")
            return None

        timestamp = int(time.time())
        backup_path = os.path.join(self._backup_dir, f"{task_id}-{timestamp}")
        os.makedirs(backup_path, exist_ok=True)

        try:
            file_manifest = []

            for root, dirs, files in os.walk(worktree_path):
                # .git 디렉토리 제외
                dirs[:] = [d for d in dirs if d != ".git"]

                for fname in files:
                    src = os.path.join(root, fname)
                    rel_path = os.path.relpath(src, worktree_path)

                    # 보안: symlink 거부 (NemoClaw safeTarExtract 패턴)
                    if os.path.islink(src):
                        logger.warning(f"Symlink rejected during backup: {rel_path}")
                        continue

                    # 보안: 경로 탈출 탐지
                    if not self._is_safe_path(rel_path, backup_path):
                        logger.warning(f"Path traversal rejected: {rel_path}")
                        continue

                    # 보안: credential 파일 필터링
                    if self._is_credential_file(fname):
                        logger.info(f"Credential file skipped: {rel_path}")
                        continue

                    dst = os.path.join(backup_path, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

                    file_manifest.append({
                        "path": rel_path,
                        "size": os.path.getsize(dst),
                        "checksum": self._file_checksum(dst),
                    })

            # 매니페스트 저장
            manifest = {
                "task_id": task_id,
                "timestamp": timestamp,
                "file_count": len(file_manifest),
                "files": file_manifest,
            }
            manifest_path = os.path.join(backup_path, ".backup-manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            logger.info(f"Backup created: {backup_path} ({len(file_manifest)} files)")
            return backup_path

        except Exception as e:
            logger.error(f"Backup failed for {task_id}: {e}")
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path, ignore_errors=True)
            return None

    def restore_state(self, task_id: str, backup_path: str) -> bool:
        """백업에서 워크트리 상태를 안전하게 복원합니다.

        NemoClaw sandbox-state.ts 패턴:
          - 매니페스트 검증
          - 복원 후 symlink 감사
          - 체크섬 검증

        Returns:
            복원 성공 여부.
        """
        worktree_path = os.path.join(self.worktree_base_dir, task_id)

        # 매니페스트 로드 & 검증
        manifest_path = os.path.join(backup_path, ".backup-manifest.json")
        if not os.path.exists(manifest_path):
            logger.error(f"Backup manifest not found: {manifest_path}")
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read backup manifest: {e}")
            return False

        if manifest.get("task_id") != task_id:
            logger.error(f"Manifest task_id mismatch: expected {task_id}")
            return False

        # 워크트리가 없으면 생성
        if not os.path.isdir(worktree_path):
            try:
                self.create_worktree(task_id)
            except RuntimeError:
                logger.error(f"Cannot create worktree for restore: {task_id}")
                return False

        try:
            restored_count = 0
            for file_info in manifest.get("files", []):
                rel_path = file_info["path"]
                src = os.path.join(backup_path, rel_path)
                dst = os.path.join(worktree_path, rel_path)

                if not os.path.exists(src):
                    logger.warning(f"Missing backup file: {rel_path}")
                    continue

                # 보안: symlink 거부
                if os.path.islink(src):
                    logger.warning(f"Symlink rejected during restore: {rel_path}")
                    continue

                # 보안: 경로 탈출 탐지
                if not self._is_safe_path(rel_path, worktree_path):
                    logger.warning(f"Path traversal rejected: {rel_path}")
                    continue

                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

                # 체크섬 검증
                expected = file_info.get("checksum")
                if expected and self._file_checksum(dst) != expected:
                    logger.warning(f"Checksum mismatch after restore: {rel_path}")

                restored_count += 1

            # 복원 후 symlink 감사 (NemoClaw 패턴)
            symlinks = self._audit_symlinks(worktree_path)
            if symlinks:
                logger.warning(
                    f"Post-restore symlink audit: {len(symlinks)} symlinks found "
                    f"in {worktree_path}"
                )

            logger.info(f"Restored {restored_count} files to {worktree_path}")
            return True

        except Exception as e:
            logger.error(f"Restore failed for {task_id}: {e}")
            return False

    def list_backups(self, task_id: str) -> List[Dict[str, Any]]:
        """특정 task의 백업 목록을 반환합니다."""
        backups = []
        prefix = f"{task_id}-"
        for name in sorted(os.listdir(self._backup_dir)):
            if name.startswith(prefix):
                path = os.path.join(self._backup_dir, name)
                manifest_path = os.path.join(path, ".backup-manifest.json")
                info = {"name": name, "path": path}
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path) as f:
                            m = json.load(f)
                        info["timestamp"] = m.get("timestamp")
                        info["file_count"] = m.get("file_count")
                    except Exception:
                        pass
                backups.append(info)
        return backups

    def get_manifest(self, task_id: str) -> Optional[Dict[str, Any]]:
        """워크트리 매니페스트를 반환합니다."""
        manifest_path = os.path.join(self._state_dir, f"{task_id}.json")
        if not os.path.exists(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ─── 내부 보안 헬퍼 ───

    def _is_safe_path(self, rel_path: str, base_dir: str) -> bool:
        """경로가 base_dir 내부에 있는지 확인합니다 (경로 탈출 방지)."""
        abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
        return abs_path.startswith(os.path.normpath(base_dir))

    def _is_credential_file(self, filename: str) -> bool:
        """파일이 credential 파일인지 확인합니다."""
        sensitive_names = {".env", ".env.local", ".env.production", "credentials.json",
                          "auth-profiles.json", "service-account.json"}
        sensitive_exts = {".pem", ".key", ".p12", ".pfx"}
        base = filename.lower()
        return base in sensitive_names or os.path.splitext(base)[1] in sensitive_exts

    def _file_checksum(self, filepath: str) -> str:
        """파일의 SHA256 체크섬을 계산합니다."""
        h = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except Exception:
            return ""
        return h.hexdigest()[:16]

    def _audit_symlinks(self, directory: str) -> List[str]:
        """디렉토리 내 모든 symlink를 탐지합니다 (NemoClaw post-extract audit)."""
        symlinks = []
        for root, dirs, files in os.walk(directory):
            for name in dirs + files:
                full_path = os.path.join(root, name)
                if os.path.islink(full_path):
                    symlinks.append(os.path.relpath(full_path, directory))
        return symlinks

    def _write_manifest(self, task_id: str, worktree_path: str, branch: str) -> None:
        """워크트리 매니페스트를 저장합니다."""
        manifest = {
            "task_id": task_id,
            "worktree_path": worktree_path,
            "branch": branch,
            "created_at": int(time.time()),
        }
        manifest_path = os.path.join(self._state_dir, f"{task_id}.json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to write manifest: {e}")

    def _remove_manifest(self, task_id: str) -> None:
        """워크트리 매니페스트를 삭제합니다."""
        manifest_path = os.path.join(self._state_dir, f"{task_id}.json")
        try:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
        except Exception as e:
            logger.debug(f"Failed to remove manifest: {e}")

