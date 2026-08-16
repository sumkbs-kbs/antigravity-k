from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Permission(str, Enum):
    ALLOW = "allow"
    PROMPT = "prompt"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    risk_level: str
    category: str = "custom"
    description: str = ""
    requires_approval: bool = False
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    spec: ToolSpec
    arguments: Mapping[str, Any]
    objective: str = ""


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    spec: ToolSpec
    permission: Permission
    source: str
    reason: str

    @property
    def allows_execution(self) -> bool:
        return self.permission is Permission.ALLOW

    @property
    def requires_approval(self) -> bool:
        return self.permission is Permission.PROMPT

    @property
    def is_denied(self) -> bool:
        return self.permission is Permission.DENY
