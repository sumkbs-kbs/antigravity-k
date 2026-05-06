import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("antigravity_k.engine.audit_logger")


# OCSF Enums and Constants
class ActivityId:
    UNKNOWN = 0
    OPEN = 1
    EXECUTE = 2
    READ = 3
    WRITE = 4
    CONNECT = 5


class ActionId:
    UNKNOWN = 0
    ALLOWED = 1
    DENIED = 2
    ERROR = 3


class SeverityId:
    UNKNOWN = 0
    INFORMATIONAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5
    FATAL = 6


class StatusId:
    UNKNOWN = 0
    SUCCESS = 1
    FAILURE = 2


class OCSFEventBuilder:
    def __init__(self, class_uid: int, class_name: str):
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
        self.event["activity_id"] = activity_id
        return self

    def action(self, action_id: int):
        self.event["action_id"] = action_id
        return self

    def severity(self, severity_id: int):
        self.event["severity_id"] = severity_id
        return self

    def status(self, status_id: int):
        self.event["status_id"] = status_id
        return self

    def message(self, msg: str):
        self.event["message"] = msg
        return self

    def unmapped(self, key: str, value: Any):
        self.event["unmapped"][key] = value
        return self

    def build(self) -> Dict[str, Any]:
        return self.event


class ToolExecutionActivityBuilder(OCSFEventBuilder):
    def __init__(self):
        super().__init__(1007, "Tool Execution Activity")

    def tool_name(self, name: str):
        self.unmapped("tool_name", name)
        return self


class SecurityDetectionBuilder(OCSFEventBuilder):
    def __init__(self):
        super().__init__(2001, "Security Detection Finding")

    def finding_info(self, title: str, description: str):
        self.event["finding"] = {"title": title, "desc": description}
        return self


class AuditLogger:
    """
    OCSF-compliant Audit Logging System
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (
            self.log_dir / f"audit_ocsf_{datetime.now().strftime('%Y%m')}.jsonl"
        )

    def _mask_sensitive_data(self, data: Any) -> Any:
        if isinstance(data, dict):
            masked = {}
            for k, v in data.items():
                if any(
                    sec in k.lower()
                    for sec in ["key", "token", "password", "secret", "credential"]
                ):
                    masked[k] = "***MASKED***"
                else:
                    masked[k] = self._mask_sensitive_data(v)
            return masked
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        return data

    def log_event(self, event_type: str, details: Dict[str, Any]):
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

    def emit(self, event_dict: Dict[str, Any]):
        """Emit an OCSF structured event dictionary."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# Singleton Instance
audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    return audit_logger
