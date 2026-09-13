"""Typed boundary errors for RequestExecutionContext resolution (ARC-01).

HTTP mapping is part of the frozen contract so WS/CTX lanes and the dashboard
share one status/code vocabulary.
"""

from __future__ import annotations

from typing import Final, Mapping

from antigravity_k.api.error_handler import APIError, JsonValue

CONTEXT_ERROR_HTTP_STATUS: Final[dict[str, int]] = {
    "missing_execution_context": 400,
    "invalid_execution_context": 400,
    "invalid_conversation_revision": 400,
    "project_not_found": 404,
    "conversation_not_found": 404,
    "project_root_invalid": 403,
    "stale_conversation_revision": 409,
    "conversation_integrity_error": 409,
    "conversation_storage_migration_required": 503,
}


class ExecutionContextError(APIError):
    """Base class for ARC-01 execution-context boundary failures."""

    status_code: int = 400
    error_code: str = "invalid_execution_context"
    detail: str = "Request execution context is invalid"


class MissingExecutionContextError(ExecutionContextError):
    status_code: int = 400
    error_code: str = "missing_execution_context"
    detail: str = "Required execution context fields are missing"


class InvalidExecutionContextError(ExecutionContextError):
    status_code: int = 400
    error_code: str = "invalid_execution_context"
    detail: str = "Request execution context failed validation"


class ProjectNotFoundError(ExecutionContextError):
    status_code: int = 404
    error_code: str = "project_not_found"
    detail: str = "Project is not registered"


class ProjectRootInvalidError(ExecutionContextError):
    status_code: int = 403
    error_code: str = "project_root_invalid"
    detail: str = "Project canonical root is missing, escaped, or not a directory"


class ConversationNotFoundError(ExecutionContextError):
    status_code: int = 404
    error_code: str = "conversation_not_found"
    detail: str = "Conversation is not found for this project"


class InvalidConversationRevisionError(ExecutionContextError):
    status_code: int = 400
    error_code: str = "invalid_conversation_revision"
    detail: str = "Conversation revision must be a non-negative integer"


class StaleConversationRevisionError(ExecutionContextError):
    status_code: int = 409
    error_code: str = "stale_conversation_revision"
    detail: str = "Conversation revision does not match the authoritative store"


class ConversationIntegrityError(ExecutionContextError):
    """CR-01: stored bytes do not belong to the requested conversation identity.

    Raised instead of returning an empty/other conversation when a storage
    record is corrupt or its embedded ids do not exactly match the request.
    """

    status_code: int = 409
    error_code: str = "conversation_integrity_error"
    detail: str = "Stored conversation data does not match the requested identity"


class ConversationStorageMigrationRequiredError(ExecutionContextError):
    """CR-01: legacy (pre-v2) conversation files must be migrated first.

    The store refuses reads/writes until the one-time, verified migration has
    produced its completion marker, so new writes cannot fork the data set.
    """

    status_code: int = 503
    error_code: str = "conversation_storage_migration_required"
    detail: str = "Conversation storage migration to the v2 layout has not completed"


_ERROR_BY_CODE: Final[dict[str, type[ExecutionContextError]]] = {
    "missing_execution_context": MissingExecutionContextError,
    "invalid_execution_context": InvalidExecutionContextError,
    "project_not_found": ProjectNotFoundError,
    "project_root_invalid": ProjectRootInvalidError,
    "conversation_not_found": ConversationNotFoundError,
    "invalid_conversation_revision": InvalidConversationRevisionError,
    "stale_conversation_revision": StaleConversationRevisionError,
    "conversation_integrity_error": ConversationIntegrityError,
    "conversation_storage_migration_required": ConversationStorageMigrationRequiredError,
}


def execution_context_error_from_code(
    error_code: str,
    *,
    detail: str | None = None,
    context: Mapping[str, JsonValue] | None = None,
) -> ExecutionContextError:
    """Build a typed error from a frozen wire code (dashboard/fixtures)."""
    cls = _ERROR_BY_CODE.get(error_code, InvalidExecutionContextError)
    return cls(detail=detail, context=context)


__all__ = [
    "CONTEXT_ERROR_HTTP_STATUS",
    "ConversationIntegrityError",
    "ConversationNotFoundError",
    "ConversationStorageMigrationRequiredError",
    "ExecutionContextError",
    "InvalidConversationRevisionError",
    "InvalidExecutionContextError",
    "MissingExecutionContextError",
    "ProjectNotFoundError",
    "ProjectRootInvalidError",
    "StaleConversationRevisionError",
    "execution_context_error_from_code",
]
