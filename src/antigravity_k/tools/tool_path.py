"""Canonical tool path resolution under request project root (WS-02).

PermissionGate and tool open/subprocess paths must use the same absolute
resolved path. Relative inputs join the request-scoped canonical root — never
the process cwd. Escapes via ``..``, symlink-out, or mixed separators are
rejected.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

PATH_ARG_KEYS: tuple[str, ...] = (
    "file_path",
    "path",
    "target",
    "dir_path",
    "cwd",
)

SHELL_CWD_TOOLS: frozenset[str] = frozenset(
    {
        "run_bash_command",
        "bash",
        "run_persistent_command",
    }
)

ROOT_DEFAULT_PATH_TOOLS: frozenset[str] = frozenset(
    {
        "list_directory",
        "glob_search",
        "grep_search",
        "git_status",
        "git_diff",
        "git_commit",
        "git_log",
    }
)


class ToolPathError(ValueError):
    """Raised when a tool path escapes the canonical project root."""

    def __init__(self, message: str, *, raw_path: str = "", project_root: str = "") -> None:
        super().__init__(message)
        self.raw_path = raw_path
        self.project_root = project_root


@dataclass(frozen=True, slots=True)
class ResolvedToolPath:
    """One path argument rewritten to an absolute path under the project root."""

    arg_key: str
    raw_path: str
    inspected_path: str
    executed_path: str
    project_root: str

    @property
    def correlated(self) -> bool:
        return self.inspected_path == self.executed_path


_audit_lock = threading.Lock()
_audit_enabled: bool = False
_audit_events: list[dict[str, Any]] = []


def enable_path_audit_capture() -> list[dict[str, Any]]:
    """Enable in-memory path audit capture (tests). Clears prior events."""
    global _audit_enabled
    with _audit_lock:
        _audit_events.clear()
    _audit_enabled = True
    return _audit_events


def disable_path_audit_capture() -> None:
    global _audit_enabled
    _audit_enabled = False


def get_path_audit_events() -> list[dict[str, Any]]:
    with _audit_lock:
        return list(_audit_events)


def record_path_audit(event: Mapping[str, Any]) -> None:
    """Record a correlated inspected/executed path audit event."""
    payload = dict(event)
    if _audit_enabled:
        with _audit_lock:
            _audit_events.append(payload)
    try:
        from antigravity_k.engine.event_bus import global_event_bus

        global_event_bus.publish("ToolPathAudit", **payload)
    except Exception:
        logger.debug("ToolPathAudit event publish skipped", exc_info=True)


def effective_project_root(fallback: str | None = None) -> str:
    """Return request-scoped canonical root, else fallback, else process cwd."""
    try:
        from antigravity_k.api.project_binding import get_request_project_root

        bound = get_request_project_root()
        if bound:
            return os.path.realpath(bound)
    except Exception:
        logger.debug("request project root unavailable", exc_info=True)

    if fallback:
        return os.path.realpath(os.path.abspath(fallback))
    return os.path.realpath(os.getcwd())


def _normalize_separators(raw: str) -> str:
    """Normalize mixed separators so ``\\`` cannot hide ``..`` on POSIX."""
    if os.name == "nt":
        return raw.replace("/", "\\")
    if "\\" in raw:
        return raw.replace("\\", "/")
    return raw


def _is_under_root(resolved: str, root_real: str) -> bool:
    if resolved == root_real:
        return True
    prefix = root_real.rstrip(os.sep) + os.sep
    return resolved.startswith(prefix)


def resolve_tool_path(raw_path: str, project_root: str) -> str:
    """Resolve ``raw_path`` to an absolute real path under ``project_root``.

    Relative paths join ``project_root`` (never process cwd). Absolute paths and
    symlink targets must remain inside the root after ``realpath``. Missing leaf
    paths (writes) resolve via the nearest existing parent.
    """
    if raw_path is None or not str(raw_path).strip():
        raise ToolPathError(
            "Tool path must not be empty",
            raw_path=str(raw_path),
            project_root=project_root,
        )

    raw = str(raw_path)
    if "\x00" in raw:
        raise ToolPathError("Tool path must not contain NUL", raw_path=raw, project_root=project_root)

    root_abs = os.path.abspath(project_root)
    if not os.path.isdir(root_abs):
        raise ToolPathError(
            "Project root is not an existing directory",
            raw_path=raw,
            project_root=project_root,
        )
    root_real = os.path.realpath(root_abs)

    normalized = _normalize_separators(os.path.expanduser(raw))
    if os.path.isabs(normalized):
        candidate = normalized
    else:
        candidate = os.path.join(root_real, normalized)

    lexical = os.path.normpath(candidate)

    if os.path.lexists(lexical):
        resolved = os.path.realpath(lexical)
    else:
        parent = os.path.dirname(lexical)
        trail: list[str] = []
        remainder = os.path.basename(lexical)
        if remainder and remainder != os.curdir:
            trail.append(remainder)
        while parent and parent != os.path.dirname(parent) and not os.path.isdir(parent):
            trail.insert(0, os.path.basename(parent))
            parent = os.path.dirname(parent)
        if parent and os.path.isdir(parent):
            parent_real = os.path.realpath(parent)
        else:
            parent_real = root_real
        resolved = os.path.normpath(os.path.join(parent_real, *trail)) if trail else parent_real

    if not _is_under_root(resolved, root_real):
        raise ToolPathError(
            f"Tool path escapes project root: {raw}",
            raw_path=raw,
            project_root=root_real,
        )
    return resolved


def rewrite_tool_args(
    tool_name: str,
    args: Mapping[str, object],
    project_root: str,
) -> tuple[dict[str, object], list[ResolvedToolPath]]:
    """Rewrite path-bearing tool args to absolute paths under ``project_root``.

    Injects explicit ``cwd`` for shell tools so subprocess never inherits an
    ambient process cwd that differs from the bound project.
    """
    root_real = os.path.realpath(os.path.abspath(project_root))
    rewritten: dict[str, object] = dict(args)
    resolutions: list[ResolvedToolPath] = []

    if tool_name in SHELL_CWD_TOOLS and "cwd" not in rewritten:
        rewritten["cwd"] = root_real

    if tool_name in ROOT_DEFAULT_PATH_TOOLS:
        raw_path = rewritten.get("path", ".")
        if raw_path is None or (isinstance(raw_path, str) and raw_path.strip() in {"", "."}):
            rewritten["path"] = root_real

    for key in PATH_ARG_KEYS:
        if key not in rewritten:
            continue
        value = rewritten[key]
        if not isinstance(value, str) or not value.strip():
            continue
        resolved = resolve_tool_path(value, root_real)
        rewritten[key] = resolved
        item = ResolvedToolPath(
            arg_key=key,
            raw_path=value,
            inspected_path=resolved,
            executed_path=resolved,
            project_root=root_real,
        )
        resolutions.append(item)
        record_path_audit(
            {
                "tool": tool_name,
                "arg_key": key,
                "raw_path": value,
                "inspected_path": resolved,
                "executed_path": resolved,
                "project_root": root_real,
                "correlated": True,
            }
        )

    if tool_name in SHELL_CWD_TOOLS and not any(r.arg_key == "cwd" for r in resolutions):
        cwd_val = str(rewritten.get("cwd", root_real))
        resolved_cwd = resolve_tool_path(cwd_val, root_real)
        rewritten["cwd"] = resolved_cwd
        resolutions.append(
            ResolvedToolPath(
                arg_key="cwd",
                raw_path=cwd_val,
                inspected_path=resolved_cwd,
                executed_path=resolved_cwd,
                project_root=root_real,
            )
        )
        record_path_audit(
            {
                "tool": tool_name,
                "arg_key": "cwd",
                "raw_path": cwd_val,
                "inspected_path": resolved_cwd,
                "executed_path": resolved_cwd,
                "project_root": root_real,
                "correlated": True,
            }
        )

    return rewritten, resolutions


__all__ = [
    "PATH_ARG_KEYS",
    "ROOT_DEFAULT_PATH_TOOLS",
    "SHELL_CWD_TOOLS",
    "ResolvedToolPath",
    "ToolPathError",
    "disable_path_audit_capture",
    "effective_project_root",
    "enable_path_audit_capture",
    "get_path_audit_events",
    "record_path_audit",
    "resolve_tool_path",
    "rewrite_tool_args",
]
