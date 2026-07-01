"""Audit Logger module."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity_k.engine.audit_logger")


# OCSF Enums and Constants
class ActivityId:
    """Activityid."""

    UNKNOWN = 0
    OPEN = 1
    EXECUTE = 2
    READ = 3
    WRITE = 4
    CONNECT = 5


class ActionId:
    """Actionid."""

    UNKNOWN = 0
    ALLOWED = 1
    DENIED = 2
    ERROR = 3


class SeverityId:
    """Severityid."""

    UNKNOWN = 0
    INFORMATIONAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5
    FATAL = 6


class StatusId:
    """Statusid."""

    UNKNOWN = 0
    SUCCESS = 1
    FAILURE = 2


class OCSFEventBuilder:
    """Ocsfeventbuilder."""

    def __init__(self, class_uid: int, class_name: str):
        """Initialize the OCSFEventBuilder.

        Args:
            class_uid (int): int class uid.
            class_name (str): str class name.

        """
        self.event = {
            "metadata": {
                "version": "1.1.0",
                "product": {"name": "Antigravity-K", "vendor_name": "Antigravity"},
            },
            "class_uid": class_uid,
            "class_name": class_name,
            "severity_id": SeverityId.INFORMATIONAL,
            "status_id": StatusId.SUCCESS,
            "time": int(time.time() * 1000),
            "unmapped": {},
        }

    def activity(self, activity_id: int):
        """Activity.

        Args:
            activity_id (int): int activity id.

        """
        self.event["activity_id"] = activity_id
        return self

    def action(self, action_id: int):
        """Set the action.

        Args:
            action_id (int): int action id.

        """
        self.event["action_id"] = action_id
        return self

    def severity(self, severity_id: int):
        """Severity.

        Args:
            severity_id (int): int severity id.

        """
        self.event["severity_id"] = severity_id
        return self

    def status(self, status_id: int):
        """Status.

        Args:
            status_id (int): int status id.

        """
        self.event["status_id"] = status_id
        return self

    def message(self, msg: str):
        """Message.

        Args:
            msg (str): str msg.

        """
        self.event["message"] = msg
        return self

    def unmapped(self, key: str, value: Any):
        """Unmapped.

        Args:
            key (str): str key.
            value (Any): value.

        """
        self.event["unmapped"][key] = value
        return self

    def build(self) -> dict[str, Any]:
        """Build.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self.event


class ToolExecutionActivityBuilder(OCSFEventBuilder):
    """Toolexecutionactivitybuilder.

    Bases: OCSFEventBuilder
    """

    def __init__(self):
        """Initialize the ToolExecutionActivityBuilder."""
        super().__init__(1007, "Tool Execution Activity")

    def tool_name(self, name: str):
        """Tool Name.

        Args:
            name (str): str name.

        """
        self.unmapped("tool_name", name)
        return self


class SecurityDetectionBuilder(OCSFEventBuilder):
    """Securitydetectionbuilder.

    Bases: OCSFEventBuilder
    """

    def __init__(self):
        """Initialize the SecurityDetectionBuilder."""
        super().__init__(2001, "Security Detection Finding")

    def finding_info(self, title: str, description: str):
        """Set finding info.

        Args:
            title (str): str title.
            description (str): str description.

        """
        self.event["finding"] = {"title": title, "desc": description}
        return self


class AuditLogger:
    """OCSF-compliant Audit Logging System."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize the AuditLogger.

        Args:
            log_dir (str): str log dir.

        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"audit_ocsf_{datetime.now().strftime('%Y%m')}.jsonl"

    def _mask_sensitive_data(self, data: Any) -> Any:
        if isinstance(data, dict):
            masked = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in ["key", "token", "password", "secret", "credential"]):
                    masked[k] = "***MASKED***"
                else:
                    masked[k] = self._mask_sensitive_data(v)
            return masked
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        return data

    def log_event(self, event_type: str, details: dict[str, Any]):
        """Legacy compatibility method. Routes to OCSF format where possible."""
        masked_details = self._mask_sensitive_data(details)
        builder = OCSFEventBuilder(9999, "Legacy Event")
        builder.message(f"Legacy Event: {event_type}")
        for k, v in masked_details.items():
            builder.unmapped(k, v)
        event = builder.build()
        event["event_type"] = event_type
        event["details"] = masked_details
        event["timestamp"] = datetime.fromtimestamp(event["time"] / 1000).isoformat()
        self.emit(event)

    def emit(self, event_dict: dict[str, Any]):
        """Emit an OCSF structured event dictionary.

        JSONL 파일 + SQLite 듀얼 싱크 (Sidabari audit_log.rs 패턴).
        SQLite 실패 시 JSONL만으로 폴백 — 데이터 손실 방지.
        """
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write audit log")

        # SQLite 듀얼 싱크
        try:
            from antigravity_k.engine.audit_db import get_audit_db

            db = get_audit_db()
            if db._initialized:
                db.insert_from_dict(event_dict)
        except ImportError:
            pass
        except Exception as e:
            logger.exception("Unhandled exception")
            # SQLite 실패는 JSONL 적재를 막지 않음
            logger.debug("SQLite dual-sync failed (non-blocking): %s", e)


# Singleton Instance
audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Retrieve audit logger.

    Returns:
        AuditLogger: The auditlogger result.

    """
    return audit_logger
