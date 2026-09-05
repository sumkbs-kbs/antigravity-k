"""Project Registry & Persistence Engine.
=========================================
Manages real local project workspaces, persists them to data/projects.json,
and coordinates active workspace switching.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity_k.engine.project_registry")

_DEFAULT_STORAGE_PATH = Path("data/projects.json")


class ProjectRecord:
    """Represents a registered local workspace project."""

    def __init__(
        self,
        id: str,
        name: str,
        path: str,
        is_active: bool = False,
        last_accessed_at: str | None = None,
        tasks: list[str] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.path = os.path.abspath(path)
        self.is_active = is_active
        self.last_accessed_at = last_accessed_at or datetime.now().isoformat()
        self.tasks = tasks or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "is_active": self.is_active,
            "last_accessed_at": self.last_accessed_at,
            "tasks": self.tasks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectRecord:
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            name=str(data.get("name") or "Project"),
            path=str(data.get("path") or "."),
            is_active=bool(data.get("is_active", False)),
            last_accessed_at=data.get("last_accessed_at"),
            tasks=list(data.get("tasks") or []),
        )


class ProjectRegistry:
    """Thread-safe persistent registry for workspace projects."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or _DEFAULT_STORAGE_PATH
        self._projects: dict[str, ProjectRecord] = {}
        self._load()

    def _ensure_default_project(self) -> None:
        """Ensure the current working directory / root is registered as default."""
        if not self._projects:
            cwd = os.getcwd()
            name = os.path.basename(cwd) or "Ssak-Ai"
            default_proj = ProjectRecord(
                id="default",
                name=name,
                path=cwd,
                is_active=True,
                tasks=[],
            )
            self._projects[default_proj.id] = default_proj
            self._save()

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._ensure_default_project()
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        rec = ProjectRecord.from_dict(item)
                        self._projects[rec.id] = rec
            self._ensure_default_project()
        except Exception:
            logger.warning("Failed to load projects from %s; resetting", self.storage_path, exc_info=True)
            self._ensure_default_project()

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [p.to_dict() for p in self._projects.values()]
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.warning("Failed to save projects to %s", self.storage_path, exc_info=True)

    def list_projects(self) -> list[dict[str, Any]]:
        self._ensure_default_project()
        return [p.to_dict() for p in sorted(self._projects.values(), key=lambda x: x.last_accessed_at, reverse=True)]

    def get_project(self, project_id: str) -> ProjectRecord | None:
        """Return a registered project by id without activating it."""
        if not project_id:
            return None
        return self._projects.get(project_id)

    def resolve_canonical_root(self, project_id: str) -> str | None:
        """Return the absolute path for a project id, or None if unknown.

        Does not mutate active project state. Callers that need allowlist /
        existence checks must use ``resolve_canonical_project_root`` in
        ``request_execution_context`` (ARC-01).
        """
        record = self.get_project(project_id)
        if record is None:
            return None
        return os.path.abspath(record.path)

    def get_active_project(self) -> ProjectRecord:
        self._ensure_default_project()
        for p in self._projects.values():
            if p.is_active:
                return p
        first = next(iter(self._projects.values()))
        first.is_active = True
        self._save()
        return first

    def add_project(self, name: str, path: str, tasks: list[str] | None = None) -> ProjectRecord:
        abs_path = os.path.abspath(path)
        # Check if already registered by path
        for p in self._projects.values():
            if os.path.abspath(p.path) == abs_path:
                p.name = name or p.name
                p.last_accessed_at = datetime.now().isoformat()
                p.is_active = True
                self._activate_single(p.id)
                self._save()
                return p

        pid = f"proj_{uuid.uuid4().hex[:8]}"
        project = ProjectRecord(
            id=pid,
            name=name.strip() or os.path.basename(abs_path) or "Project",
            path=abs_path,
            is_active=True,
            tasks=tasks or [],
        )
        self._projects[pid] = project
        self._activate_single(pid)
        self._save()
        return project

    def _activate_single(self, active_id: str) -> None:
        for pid, p in self._projects.items():
            p.is_active = pid == active_id
            if p.is_active:
                p.last_accessed_at = datetime.now().isoformat()

    def switch_project(self, project_id_or_path: str) -> ProjectRecord | None:
        target: ProjectRecord | None = None
        if project_id_or_path in self._projects:
            target = self._projects[project_id_or_path]
        else:
            abs_path = os.path.abspath(project_id_or_path)
            for p in self._projects.values():
                if os.path.abspath(p.path) == abs_path:
                    target = p
                    break

        if target is None:
            return None

        self._activate_single(target.id)
        self._save()
        return target

    def remove_project(self, project_id: str) -> bool:
        if project_id not in self._projects:
            return False
        # Do not delete the only project
        if len(self._projects) <= 1:
            return False
        was_active = self._projects[project_id].is_active
        del self._projects[project_id]
        if was_active:
            first = next(iter(self._projects.values()))
            first.is_active = True
        self._save()
        return True


_global_registry: ProjectRegistry | None = None


def get_project_registry() -> ProjectRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ProjectRegistry()
    return _global_registry
