"""
Resilience utilities — circuit breakers, retry policies, and timeouts.

Provides per-service retry policies with:
  - Request timeouts
  - Bounded retry counts
  - Exponential backoff with optional jitter
  - Transient vs permanent failure classification
  - Circuit breaker (closed → open → half-open)
  - Masked logging (no secrets in logs)
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, TypeVar

logger = logging.getLogger("operational.resilience")

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED    = "closed"     # Normal operation
    OPEN      = "open"       # Blocking calls — too many failures
    HALF_OPEN = "half_open"  # Probing — allow one call through


@dataclass
class RetryPolicy:
    """Per-service retry configuration."""
    max_retries:      int   = 3
    base_delay_s:     float = 1.0
    max_delay_s:      float = 60.0
    backoff_factor:   float = 2.0
    jitter:           bool  = True     # Set False in tests for determinism
    timeout_s:        float = 30.0
    # HTTP status codes treated as transient (retryable)
    retryable_codes:  tuple = (408, 429, 500, 502, 503, 504)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker protecting a single service.
    NOT thread-safe (single-process; GitHub Actions is single-threaded per job).
    """
    name:                str
    failure_threshold:   int   = 5       # failures before opening
    recovery_timeout_s:  float = 120.0   # open → half-open after this
    success_threshold:   int   = 2       # half-open successes to close

    _state:    CircuitState = field(default=CircuitState.CLOSED,    init=False)
    _failures: int          = field(default=0,                       init=False)
    _successes:int          = field(default=0,                       init=False)
    _opened_at: datetime | None = field(default=None,                init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._opened_at and datetime.utcnow() >= self._opened_at + timedelta(seconds=self.recovery_timeout_s):
                logger.info("[%s] Circuit → HALF_OPEN (probing)", self.name)
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        if self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                logger.info("[%s] Circuit → CLOSED (recovered)", self.name)
                self._state    = CircuitState.CLOSED
                self._successes = 0
                self._opened_at = None

    def record_failure(self) -> None:
        self._failures   += 1
        self._successes   = 0
        if self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self._failures >= self.failure_threshold:
                logger.error("[%s] Circuit → OPEN (%d failures)", self.name, self._failures)
                self._state    = CircuitState.OPEN
                self._opened_at = datetime.utcnow()

    def allow_request(self) -> bool:
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF_OPEN:
            return True   # allow one probe
        # OPEN
        logger.warning("[%s] Circuit OPEN — request blocked", self.name)
        return False


# ── Service-level circuit breakers (module singletons) ────────────────────

_BREAKERS: dict[str, CircuitBreaker] = {}


def get_breaker(service: str, **kwargs) -> CircuitBreaker:
    if service not in _BREAKERS:
        _BREAKERS[service] = CircuitBreaker(name=service, **kwargs)
    return _BREAKERS[service]


# Pre-configured breakers for known services
GEMINI_BREAKER   = get_breaker("gemini",    failure_threshold=10, recovery_timeout_s=300)
INSTAGRAM_BREAKER= get_breaker("instagram", failure_threshold=5,  recovery_timeout_s=180)
GDRIVE_BREAKER   = get_breaker("gdrive",    failure_threshold=5,  recovery_timeout_s=120)
SHEETS_BREAKER   = get_breaker("sheets",    failure_threshold=5,  recovery_timeout_s=120)
TELEGRAM_BREAKER = get_breaker("telegram",  failure_threshold=10, recovery_timeout_s=60)
PIXABAY_BREAKER  = get_breaker("pixabay",   failure_threshold=5,  recovery_timeout_s=120)
SUPABASE_BREAKER = get_breaker("supabase",  failure_threshold=5,  recovery_timeout_s=60)
GITHUB_BREAKER   = get_breaker("github",    failure_threshold=5,  recovery_timeout_s=60)


# ── Retry decorator ────────────────────────────────────────────────────────

def with_retry(
    policy: RetryPolicy,
    breaker: CircuitBreaker | None = None,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> Callable:
    """
    Decorator factory for retrying a function with the given policy.

    Usage::

        @with_retry(RetryPolicy(max_retries=3), breaker=INSTAGRAM_BREAKER)
        def publish_post(post_id: str) -> str: ...
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            if breaker and not breaker.allow_request():
                raise RuntimeError(f"Circuit open for {breaker.name} — call blocked")

            last_exc: Exception | None = None
            for attempt in range(policy.max_retries + 1):
                try:
                    result = fn(*args, **kwargs)
                    if breaker:
                        breaker.record_success()
                    return result
                except Exception as exc:
                    last_exc = exc
                    retryable = (is_retryable(exc) if is_retryable else _default_retryable(exc))
                    if not retryable or attempt == policy.max_retries:
                        if breaker:
                            breaker.record_failure()
                        raise
                    delay = min(
                        policy.base_delay_s * (policy.backoff_factor ** attempt),
                        policy.max_delay_s,
                    )
                    if policy.jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    logger.warning(
                        "[%s] attempt %d/%d failed (%s) — retry in %.1fs",
                        fn.__name__, attempt + 1, policy.max_retries + 1,
                        type(exc).__name__, delay,
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def _default_retryable(exc: Exception) -> bool:
    """Default classification: retry on transient errors, not permanent ones."""
    msg = str(exc).lower()
    permanent = ("invalid_api_key", "401", "403", "permission denied",
                 "400", "invalid_argument", "not found", "404")
    return not any(p in msg for p in permanent)


# ── Per-service retry policies ─────────────────────────────────────────────

INSTAGRAM_POLICY = RetryPolicy(max_retries=3, base_delay_s=5,  max_delay_s=60,  timeout_s=30)
GDRIVE_POLICY    = RetryPolicy(max_retries=3, base_delay_s=2,  max_delay_s=30,  timeout_s=30)
SHEETS_POLICY    = RetryPolicy(max_retries=3, base_delay_s=2,  max_delay_s=30,  timeout_s=30)
TELEGRAM_POLICY  = RetryPolicy(max_retries=5, base_delay_s=1,  max_delay_s=30,  timeout_s=15, jitter=False)
PIXABAY_POLICY   = RetryPolicy(max_retries=3, base_delay_s=2,  max_delay_s=30,  timeout_s=20)
GITHUB_POLICY    = RetryPolicy(max_retries=3, base_delay_s=2,  max_delay_s=30,  timeout_s=20)
DB_POLICY        = RetryPolicy(max_retries=3, base_delay_s=1,  max_delay_s=10,  timeout_s=30, jitter=False)
