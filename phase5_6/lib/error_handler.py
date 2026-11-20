"""
Three-tier error handling:

1. CriticalError    — external, unrecoverable (token dead, key invalid).
                       Telegram alert + stop. No auto-fix attempted.
2. RecoverableError — expected, known fix (quota exceeded, transient network).
                       Handled by plain retry/key-rotation logic, no AI involved.
3. UnexpectedError  — anything else. Reported to Telegram for manual investigation.
"""
import sys


class CriticalError(Exception):
    """External failure requiring manual intervention. No auto-fix."""
    pass


class RecoverableError(Exception):
    """Expected, retryable failure. Handled by plain code, not AI."""
    pass


class UnexpectedError(Exception):
    """Unexpected runtime failure."""
    pass


def handle_unexpected(notifier, file_path: str) -> None:
    """Report the failing stage without publishing tracebacks or model output."""
    exc_type = sys.exc_info()[0]
    error_name = exc_type.__name__ if exc_type else "UnknownError"
    notifier.alert_critical("خطأ غير متوقع", f"{file_path}: {error_name}")
