#!/usr/bin/env python3
"""Compatibility wrapper for the k-skill-cleaner skill-local helper.

The standalone skill install includes ``k-skill-cleaner/scripts/k_skill_cleaner.py``.
This repository-root wrapper preserves existing checkout workflows and tests while
keeping the executable payload inside the skill directory.
"""

from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import NotRequired, Protocol, TypedDict, runtime_checkable

_HELPER_PATH = Path(__file__).resolve().parents[1] / "k-skill-cleaner" / "scripts" / "k_skill_cleaner.py"
_SPEC = importlib.util.spec_from_file_location("_k_skill_cleaner_impl", _HELPER_PATH)


class _AgentUsageSource(TypedDict):
    agent: str
    paths: list[str]
    method: str
    confidence: str
    fallback: NotRequired[str]


class _CleanupCandidate(TypedDict):
    skill: str
    action: str
    trigger_count: int
    score: int
    reasons: list[str]


@runtime_checkable
class _CleanerModule(Protocol):
    AGENT_USAGE_SOURCES: list[_AgentUsageSource]
    collect_skill_usage: Callable[..., dict[str, int]]
    find_skill_dirs: Callable[[Path | str], list[str]]
    rank_cleanup_candidates: Callable[..., list[_CleanupCandidate]]
    load_usage_json: Callable[..., dict[str, int]]
    expand_default_log_paths: Callable[[], list[Path]]
    parse_csv: Callable[[str | None], set[str]]
    build_parser: Callable[[], argparse.ArgumentParser]
    main: Callable[..., int]


def _load_module() -> _CleanerModule:
    if _SPEC is None or _SPEC.loader is None:
        raise ImportError(f"Unable to load k-skill-cleaner helper from {_HELPER_PATH}")
    module = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(module)
    if not isinstance(module, _CleanerModule):
        raise ImportError(f"Loaded k-skill-cleaner helper has an incompatible interface: {_HELPER_PATH}")
    return module


_MODULE = _load_module()

AGENT_USAGE_SOURCES = _MODULE.AGENT_USAGE_SOURCES
collect_skill_usage = _MODULE.collect_skill_usage
find_skill_dirs = _MODULE.find_skill_dirs
rank_cleanup_candidates = _MODULE.rank_cleanup_candidates
load_usage_json = _MODULE.load_usage_json
expand_default_log_paths = _MODULE.expand_default_log_paths
parse_csv = _MODULE.parse_csv
build_parser = _MODULE.build_parser
main = _MODULE.main

__all__ = [
    "AGENT_USAGE_SOURCES",
    "collect_skill_usage",
    "find_skill_dirs",
    "rank_cleanup_candidates",
    "load_usage_json",
    "expand_default_log_paths",
    "parse_csv",
    "build_parser",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
