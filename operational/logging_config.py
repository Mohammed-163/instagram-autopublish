"""
Centralized structured JSON logging with correlation ID support.

Every pipeline run gets a unique correlation_id that propagates through:
  - Workflow invocation (set from GH_RUN_ID or generated)
  - All log records via ContextFilter
  - External API calls (as X-Correlation-ID header when applicable)
  - Database records (where the schema supports it)
  - Telegram alerts

Usage::

    from operational.logging_config import setup, get_correlation_id, set_correlation_id
    setup()
    set_correlation_id("my-run-id")  # or let it auto-generate
    logger.info("starting", extra={"component": "scheduler", "operation": "start"})
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

# Thread-local-like storage using a simple module-level variable
# (GitHub Actions runs are single-process)
_correlation_id: str = ""
_run_id: str = ""


def generate_correlation_id() -> str:
    return str(uuid.uuid4())[:12]


def set_correlation_id(cid: str) -> None:
    global _correlation_id
    _correlation_id = cid


def get_correlation_id() -> str:
    global _correlation_id
    if not _correlation_id:
        _correlation_id = generate_correlation_id()
    return _correlation_id


def set_run_id(rid: str) -> None:
    global _run_id
    _run_id = rid


def get_run_id() -> str:
    return _run_id or os.environ.get("GITHUB_RUN_ID", "")


# ── JSON formatter ─────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    RESERVED = {"message", "asctime", "levelname", "name", "pathname",
                 "lineno", "funcName", "exc_info", "exc_text", "stack_info"}

    def format(self, record: logging.LogRecord) -> str:
        # Redact potential secrets from message
        msg = self.formatMessage(record)
        msg = _redact(msg)

        entry: dict[str, Any] = {
            "ts":           datetime.now(tz=timezone.utc).isoformat(),
            "level":        record.levelname,
            "logger":       record.name,
            "msg":          msg,
            "correlation_id": get_correlation_id(),
            "run_id":       get_run_id(),
        }

        # Optional structured fields from extra={}
        for k, v in record.__dict__.items():
            if k.startswith("_") or k in self.RESERVED or k in entry:
                continue
            if k in ("args", "created", "exc_info", "exc_text", "filename",
                     "levelno", "lineno", "module", "msecs", "name",
                     "pathname", "process", "processName", "relativeCreated",
                     "stack_info", "taskName", "thread", "threadName"):
                continue
            entry[k] = v

        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str, ensure_ascii=False)


# ── Secret redaction ───────────────────────────────────────────────────────

_REDACT_PATTERNS = [
    # API keys: long hex/base64 strings after common prefixes
    ("api_key", 8),
    ("access_token", 8),
    ("secret", 6),
    ("password", 4),
    ("token", 8),
]


def _redact(text: str) -> str:
    """Replace potential secret values with [REDACTED]."""
    import re
    # Redact anything that looks like a Bearer token or key=value secret
    text = re.sub(
        r"(Bearer\s+)[A-Za-z0-9+/=._-]{20,}",
        r"\1[REDACTED]",
        text,
    )
    # Redact key=<long_value> patterns
    text = re.sub(
        r"((?:api_key|access_token|secret|password|token)\s*[=:]\s*)[^\s&\"']{10,}",
        r"\1[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    return text


# ── Setup ──────────────────────────────────────────────────────────────────

def setup(
    level: str | None = None,
    log_dir: str | None = None,
    json_format: bool = True,
) -> None:
    """
    Configure root logger.

    Args:
        level:      Log level (default: LOG_LEVEL env or INFO).
        log_dir:    Directory for rotating log files (default: LOG_DIR env or ./logs).
        json_format: Use JSON formatter (default True; use False in tests for readability).
    """
    # Derive correlation ID from GitHub Actions run if available
    gh_run = os.environ.get("GITHUB_RUN_ID", "")
    gh_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    if gh_run:
        set_correlation_id(f"{gh_run}-{gh_attempt}")
        set_run_id(gh_run)
    else:
        set_correlation_id(generate_correlation_id())

    log_level = getattr(logging, (level or os.environ.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    fmt = JsonFormatter() if json_format else logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    # Console handler
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
               for h in root.handlers):
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)

    # File handler (optional)
    _log_dir = log_dir or os.environ.get("LOG_DIR", "./logs")
    if _log_dir:
        import pathlib
        pathlib.Path(_log_dir).mkdir(parents=True, exist_ok=True)
        log_file = f"{_log_dir}/autonomous_ai.log"
        fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        fh.setFormatter(fmt)
        root.addHandler(fh)
