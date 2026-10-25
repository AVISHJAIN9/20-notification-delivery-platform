"""
Structured JSON Logging for Project 20 (NTF-114).
Provides JSON-formatted log entries with request tracing, contextual metadata,
and automatic sanitization of sensitive tokens and credentials.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional

SENSITIVE_KEYS = {"password", "secret", "api_key", "token", "auth_token", "access_token", "authorization"}


def sanitize_payload(data: Any) -> Any:
    """
    Recursively strips or masks sensitive credentials and secrets.
    """
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_payload(v)
        return cleaned
    elif isinstance(data, list):
        return [sanitize_payload(x) for x in data]
    return data


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom extra fields if present
        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            sanitized = sanitize_payload(record.structured_data)
            log_entry.update(sanitized)

        return json.dumps(log_entry)


class StructuredLogger:
    def __init__(self, name: str = "ntf.structured"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredJsonFormatter())
            self.logger.addHandler(handler)

    def log(
        self,
        level: int,
        event: str,
        message: str,
        tenant_id: Optional[str] = None,
        notification_id: Optional[str] = None,
        channel: Optional[str] = None,
        request_id: Optional[str] = None,
        **extra: Any
    ) -> Dict[str, Any]:
        data = {
            "event": event,
            "tenant_id": tenant_id,
            "notification_id": notification_id,
            "channel": channel,
            "request_id": request_id,
            **extra
        }
        sanitized = sanitize_payload(data)
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
            extra={"structured_data": sanitized}
        )
        self.logger.handle(record)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            **sanitized
        }

    def info(self, event: str, message: str, **kwargs: Any) -> Dict[str, Any]:
        return self.log(logging.INFO, event, message, **kwargs)

    def warning(self, event: str, message: str, **kwargs: Any) -> Dict[str, Any]:
        return self.log(logging.WARNING, event, message, **kwargs)

    def error(self, event: str, message: str, **kwargs: Any) -> Dict[str, Any]:
        return self.log(logging.ERROR, event, message, **kwargs)
