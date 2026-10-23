"""
Production Gemini Rotation Engine — google-genai SDK (new)
===========================================================
Rotation strategy:
  Health-aware selection: always choose the (Key, Model) pair with the
  highest priority score. Priority is deterministic — same runtime state
  always produces the same next selection.

  Fallback order when all pairs are equally healthy (default config):
    Key-N → gemini-3.1-flash-lite → gemini-3.5-flash-lite → gemini-3.5-flash → gemini-3.6-flash
    (configurable via GEMINI_MODEL_ROTATION — see Configuration below)

Configuration:
  GEMINI_MODEL_ROTATION   Comma-separated list of model names (no spaces).
                          Controls default priority order when all pairs are
                          equally healthy. Changing this requires only an env
                          update — no code changes.

  Default:
    GEMINI_MODEL_ROTATION=gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.5-flash,gemini-3.6-flash

  Example override (put flash first):
    GEMINI_MODEL_ROTATION=gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.6-flash

Features:
  - Health-aware pair selection (priority score, deterministic)
  - Per-(key, model) health tracking: state, failures, cooldown, last success
  - Error classification: auth / quota / unavailable / permanent / safety
  - Auth errors: disable key for 24 h; quota: cooldown only that pair;
    temporary: exponential backoff; permanent/safety: propagate immediately
  - Persistent state (JSON file) — survives across GitHub Actions runs
  - Structured logging
  - Never raises on a single model/key failure
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("operational.gemini_rotation")

# ── Canonical free-tier model list  ───────────────────────────────────────
# Only stable identifiers — no aliases, no Pro, no preview,
# no image/video/audio/TTS/music/embedding/robotics/agent models.
# This is the authoritative default used when GEMINI_MODEL_ROTATION is unset.
FREE_MODELS: List[str] = [
    "gemini-3.1-flash-lite",    # fastest / highest free quota — primary
    "gemini-3.5-flash-lite",    # fast general purpose — fallback 1
    "gemini-3.5-flash",         # standard — fallback 2
    "gemini-3.6-flash",         # last resort
]

# Alias used by tests and callers that import the canonical list
GEMINI_FREE_MODELS = FREE_MODELS


def parse_model_rotation(env_value: Optional[str] = None) -> List[str]:
    """
    Parse GEMINI_MODEL_ROTATION env var into an ordered model list.

    Accepts a comma-separated string of model names (whitespace is stripped).
    Falls back to FREE_MODELS if the env var is unset or results in an empty
    list after parsing.

    Args:
        env_value: Value of GEMINI_MODEL_ROTATION (or None to read from env).

    Returns:
        Ordered list of model name strings.
    """
    raw = env_value if env_value is not None else os.environ.get("GEMINI_MODEL_ROTATION", "")
    if raw:
        parsed = [m.strip() for m in raw.split(",") if m.strip()]
        if parsed:
            return parsed
    return list(FREE_MODELS)


# Default state file location (local dev / ephemeral runner fallback)
_DEFAULT_STATE_FILE = Path(os.environ.get(
    "GEMINI_STATE_FILE",
    str(Path(__file__).parent.parent / "gemini_rotation_state.json"),
))

# ── Error classification ───────────────────────────────────────────────────
_QUOTA   = ("quota", "429", "resource_exhausted", "rate_limit", "too_many", "requests_per_day")
_UNAVAIL = ("unavailable", "503", "502", "not_found", "model_not_found", "404", "deadline_exceeded")
_AUTH    = ("api_key", "invalid_api_key", "401", "403", "permission_denied")
_PERM    = ("invalid_argument", "400",)
_SAFETY  = ("safety", "blocked", "content_filter", "recitation")


def _classify(err: Exception) -> str:
    """
    Classify an API error into one of five categories:

    - ``auth``      : API key rejected — disable key for 24 h.
    - ``quota``     : Rate / daily quota exceeded — cool down (key, model) pair.
    - ``unavailable``: Transient server error — exponential back-off.
    - ``safety``    : Content policy / safety block — propagate; never retry.
    - ``permanent`` : Unrecoverable request error — propagate; never retry.
    - ``unknown``   : Anything else — treated as unavailable.
    """
    msg = str(err).lower()
    if any(s in msg for s in _AUTH):     return "auth"
    if any(s in msg for s in _SAFETY):   return "safety"
    if any(s in msg for s in _QUOTA):    return "quota"
    if any(s in msg for s in _UNAVAIL):  return "unavailable"
    if any(s in msg for s in _PERM):     return "permanent"
    return "unknown"


# ── Health state enum ──────────────────────────────────────────────────────

class HealthState(str, Enum):
    HEALTHY           = "healthy"
    COOLING_DOWN      = "cooling_down"
    QUOTA_EXCEEDED    = "quota_exceeded"
    AUTH_FAILED       = "authentication_failed"
    UNAVAILABLE       = "unavailable"


# ── Per-(key, model) health tracking ──────────────────────────────────────

@dataclass
class _Health:
    """
    Tracks runtime state for a single (API key, model) pair.

    Fields
    ------
    failures          : int   — consecutive failures since last success (reset on success).
    successes         : int   — cumulative successes.
    last_failure_at   : str?  — ISO-8601 UTC timestamp of most recent failure.
    last_success_at   : str?  — ISO-8601 UTC timestamp of most recent success.
    retry_after       : str?  — ISO-8601 UTC timestamp; pair is unavailable until this time.
    error_type        : str   — category of last failure (empty = no failure yet).
    """
    failures:        int            = 0
    successes:       int            = 0
    last_failure_at: Optional[str]  = None
    last_success_at: Optional[str]  = None
    # ``retry_after`` (ISO-8601) replaces the old ``cooldown_until`` name.
    # Both names are accepted by ``from_dict`` for backwards compatibility.
    retry_after:     Optional[str]  = None
    error_type:      str            = ""

    # ── backward-compat alias (old state files used cooldown_until) ──────
    @property
    def cooldown_until(self) -> Optional[str]:
        return self.retry_after

    @cooldown_until.setter
    def cooldown_until(self, value: Optional[str]) -> None:
        self.retry_after = value

    # ── Computed properties ───────────────────────────────────────────────

    @property
    def consecutive_failures(self) -> int:
        """Alias for ``failures`` (reset to 0 on success)."""
        return self.failures

    @property
    def health_state(self) -> HealthState:
        """Current health state as an enum value."""
        if self.error_type == "auth":
            return HealthState.AUTH_FAILED
        if self.is_cooling():
            if self.error_type == "quota":
                return HealthState.QUOTA_EXCEEDED
            return HealthState.COOLING_DOWN
        return HealthState.HEALTHY

    def priority_score(self, model_idx: int, key_idx: int) -> float:
        """
        Compute a deterministic priority score for this pair.

        Higher score → preferred.  Pairs in cooldown or with auth errors
        receive ``-inf`` and are never selected.

        The score is purely a function of the current ``_Health`` state and the
        position of the pair in the configured model/key order.  No randomness
        is introduced — the same runtime state always produces the same score.

        **Health always dominates.**  The rotation-list position (``model_idx``
        and ``key_idx``) contributes only a tiny sub-unit tiebreaker so that
        it can *never* outweigh any runtime health signal.

        Scoring formula:
            base 1000
            - 50     × consecutive failures    (penalises recently-failed pairs)
            + 5      × min(successes, 20)      (rewards historically healthy pairs)
            - 0.001  × model_idx              (tiebreaker only — config list order)
            - 0.0005 × key_idx               (tiebreaker only — key list order)

        Tiebreaker weights (0.001 / 0.0005) are deliberately smaller than the
        smallest health delta (5.0 per success point), guaranteeing that any
        runtime health difference takes absolute precedence over list position.
        Rotation-list order is used *only* when two candidates have exactly the
        same health state.
        """
        if self.error_type == "auth" or self.is_cooling():
            return float("-inf")
        score = 1000.0
        score -= self.failures * 50.0
        score += min(self.successes, 20) * 5.0
        # Tiebreaker only — must never outweigh runtime health signals
        score -= model_idx * 0.001
        score -= key_idx * 0.0005
        return score

    # ── State mutation ────────────────────────────────────────────────────

    def record_success(self) -> None:
        self.successes      += 1
        self.failures        = 0
        self.retry_after     = None
        self.error_type      = ""
        self.last_success_at = datetime.utcnow().isoformat()

    def record_failure(self, error_type: str, backoff_s: float) -> None:
        self.failures        += 1
        self.last_failure_at  = datetime.utcnow().isoformat()
        self.error_type       = error_type
        self.retry_after      = (
            (datetime.utcnow() + timedelta(seconds=backoff_s)).isoformat()
            if backoff_s > 0 else None
        )

    # ── Cooldown helpers ──────────────────────────────────────────────────

    def is_cooling(self) -> bool:
        if not self.retry_after:
            return False
        return datetime.utcnow() < datetime.fromisoformat(self.retry_after)

    def cooldown_remaining(self) -> float:
        if not self.is_cooling():
            return 0.0
        return (
            datetime.fromisoformat(self.retry_after) - datetime.utcnow()
        ).total_seconds()

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "failures":        self.failures,
            "successes":       self.successes,
            "last_failure_at": self.last_failure_at,
            "last_success_at": self.last_success_at,
            "retry_after":     self.retry_after,
            "error_type":      self.error_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "_Health":
        """Load from a serialised dict; accepts both ``retry_after`` and
        the legacy ``cooldown_until`` field name."""
        retry_after = d.get("retry_after") or d.get("cooldown_until")
        return cls(
            failures        = d.get("failures",        0),
            successes       = d.get("successes",       0),
            last_failure_at = d.get("last_failure_at"),
            last_success_at = d.get("last_success_at"),
            retry_after     = retry_after,
            error_type      = d.get("error_type",      ""),
        )


class AllCombinationsExhaustedError(Exception):
    """Every (key × model) combination failed or is in cooldown."""


# ── State persistence ──────────────────────────────────────────────────────

def _load_state(state_file: Path) -> dict:
    try:
        if state_file.exists():
            return json.loads(state_file.read_text())
    except Exception as e:
        logger.warning("Could not load rotation state from %s: %s", state_file, e)
    return {}


def _save_state(state_file: Path, health: dict) -> None:
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        serialized = {k: v.to_dict() for k, v in health.items()}
        state_file.write_text(json.dumps(serialized, indent=2))
    except Exception as e:
        logger.warning("Could not save rotation state to %s: %s", state_file, e)


class GeminiRotationEngine:
    """
    Production Gemini client with health-aware key×model rotation and
    persistent state.

    Selection algorithm (deterministic, health-aware)
    --------------------------------------------------
    On each generation attempt the engine:

    1. Collects all (key_index, model) pairs.
    2. Discards pairs whose key has an active ``auth`` error (disabled 24 h).
    3. Discards pairs still within their ``retry_after`` cooldown window.
    4. Discards pairs already exhausted for this call (>= max_retries_per_pair).
    5. Ranks the remaining candidates by ``_Health.priority_score()``.
    6. Selects the highest-scoring pair — ties broken by model order then key
       order (deterministic, no randomness).
    7. Calls the Gemini API.  On success: returns.  On failure: updates health
       and repeats from step 1.
    8. When no eligible candidates remain: raises ``AllCombinationsExhaustedError``.

    The model rotation order is configured via the ``GEMINI_MODEL_ROTATION``
    environment variable (comma-separated model names).  Changing the order
    requires only an environment update — no source code change.

    Error handling
    --------------
    - ``auth``      → key disabled for 24 h; jump to next key immediately.
    - ``quota``     → (key, model) pair cooled down with exponential backoff.
    - ``unavailable`` → (key, model) pair cooled down with exponential backoff.
    - ``safety``    → propagated to caller immediately; never retried.
    - ``permanent`` → propagated to caller immediately; never retried.
    - ``unknown``   → treated as ``unavailable``.

    Usage::

        engine = GeminiRotationEngine.from_env()
        text = engine.generate("Write a post about...")
    """

    _BACKOFF: List[float] = [5, 15, 30, 60, 120, 300]

    def __init__(
        self,
        api_keys: List[str],
        models: Optional[List[str]] = None,
        image_check_key: str = "",
        state_file: Optional[Path] = None,
    ):
        self.api_keys        = [k for k in api_keys if k]
        self.models          = models if models is not None else parse_model_rotation()
        self.image_check_key = image_check_key
        self._state_file     = state_file or _DEFAULT_STATE_FILE
        if not self.api_keys:
            raise ValueError("GeminiRotationEngine: at least one API key required")

        saved = _load_state(self._state_file)
        self._health: Dict[str, _Health] = {}
        for ki in range(len(self.api_keys)):
            for m in self.models:
                slot_key = f"{ki}:{m}"
                if slot_key in saved:
                    try:
                        self._health[slot_key] = _Health.from_dict(saved[slot_key])
                        continue
                    except Exception:
                        pass
                self._health[slot_key] = _Health()

    @classmethod
    def from_env(cls) -> "GeminiRotationEngine":
        """
        Construct from environment variables.

        Reads:
          GEMINI_API_KEY_1, _2, _3    — rotation keys
          GEMINI_API_KEY_IMAGE_CHECK  — dedicated key for image vetting
          GEMINI_MODEL_ROTATION       — comma-separated model order (optional)
          GEMINI_STATE_FILE           — path to persistent state JSON (optional)
        """
        return cls(
            api_keys=[
                os.environ.get("GEMINI_API_KEY_1", ""),
                os.environ.get("GEMINI_API_KEY_2", ""),
                os.environ.get("GEMINI_API_KEY_3", ""),
            ],
            models=parse_model_rotation(),
            image_check_key=os.environ.get("GEMINI_API_KEY_IMAGE_CHECK", ""),
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _backoff(self, failures: int) -> float:
        """Exponential back-off in seconds, capped at the last bucket."""
        return float(self._BACKOFF[min(max(failures - 1, 0), len(self._BACKOFF) - 1)])

    def _slot(self, ki: int, model: str) -> _Health:
        return self._health[f"{ki}:{model}"]

    def _select_best_pair(
        self,
        seen_pairs: Dict[str, int],
        max_retries: int,
    ) -> Optional[Tuple[int, str]]:
        """
        Return the (key_index, model_name) pair with the highest priority score.

        Pairs are excluded when:
        - The key has an auth error (error_type == "auth").
        - The pair is within its cooldown window (is_cooling()).
        - The pair has already been attempted >= max_retries times this call.

        Selection is fully deterministic: candidates are sorted by
        (priority_score DESC, key_idx ASC, model_idx ASC) — no randomness.

        Returns None when no eligible candidates exist.
        """
        candidates: List[Tuple[float, int, int, str]] = []

        for ki in range(len(self.api_keys)):
            for mi, model in enumerate(self.models):
                slot_key = f"{ki}:{model}"
                health = self._health[slot_key]

                # Exclusion: auth-failed key
                if health.error_type == "auth":
                    continue
                # Exclusion: in cooldown
                if health.is_cooling():
                    continue
                # Exclusion: retries exhausted for this call
                if seen_pairs.get(slot_key, 0) >= max_retries:
                    continue

                score = health.priority_score(mi, ki)
                candidates.append((score, ki, mi, model))

        if not candidates:
            return None

        # Sort: highest score first; ties broken by key_idx then model_idx
        candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
        _, ki, _, model = candidates[0]
        return ki, model

    # ── Main API ──────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        generation_config: Optional[dict] = None,
        max_retries_per_pair: int = 2,
    ) -> str:
        """
        Generate text using the healthiest available (key, model) pair.

        The selection is re-evaluated after each failure so the engine
        always picks the currently healthiest remaining option.

        Raises:
            AllCombinationsExhaustedError  — all pairs failed or in cooldown.
            Exception (re-raised)          — on safety or permanent errors.
        """
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            raise RuntimeError("google-genai is required: pip install google-genai")

        seen_pairs: Dict[str, int] = {}   # slot_key → number of attempts this call
        attempts_log: List[str]    = []

        # Upper bound: all pairs × max retries (prevents infinite loop)
        max_iterations = len(self.api_keys) * len(self.models) * max_retries_per_pair

        for _iteration in range(max_iterations):
            pair = self._select_best_pair(seen_pairs, max_retries_per_pair)
            if pair is None:
                break   # no eligible candidates remain

            ki, model_name = pair
            slot_key = f"{ki}:{model_name}"
            health   = self._slot(ki, model_name)
            attempt  = seen_pairs.get(slot_key, 0) + 1
            seen_pairs[slot_key] = attempt

            logger.info(
                "key#%d model=%s attempt=%d (score=%.1f failures=%d)",
                ki + 1, model_name, attempt,
                health.priority_score(self.models.index(model_name), ki),
                health.failures,
            )

            try:
                client = genai.Client(api_key=self.api_keys[ki])
                cfg = (
                    genai_types.GenerateContentConfig(**(generation_config or {}))
                    if generation_config
                    else None
                )
                kwargs: Dict[str, Any] = {
                    "model":    model_name,
                    "contents": prompt,
                }
                if cfg:
                    kwargs["config"] = cfg

                resp = client.models.generate_content(**kwargs)
                text = resp.text
                health.record_success()
                _save_state(self._state_file, self._health)
                logger.info("✓ key#%d model=%s succeeded", ki + 1, model_name)
                return text

            except Exception as exc:
                err_type = _classify(exc)
                attempts_log.append(f"key{ki+1}/{model_name}/{err_type}/attempt{attempt}")

                # ── Safety / permanent: never retry, propagate immediately ──
                if err_type in ("safety", "permanent"):
                    health.record_failure(err_type, 0)
                    _save_state(self._state_file, self._health)
                    logger.error(
                        "✗ key#%d model=%s err=%s — propagating (no retry)",
                        ki + 1, model_name, err_type,
                    )
                    raise

                # ── Auth: disable key for 24 h ─────────────────────────────
                if err_type == "auth":
                    health.record_failure(err_type, 86_400)
                    _save_state(self._state_file, self._health)
                    logger.error(
                        "✗ key#%d model=%s auth error — key disabled 24 h",
                        ki + 1, model_name,
                    )
                    # Mark ALL models on this key as auth-failed so they are
                    # all excluded from _select_best_pair in subsequent iterations.
                    for m in self.models:
                        sk = f"{ki}:{m}"
                        if sk != slot_key:
                            h = self._health[sk]
                            h.error_type = "auth"
                            h.retry_after = health.retry_after
                    _save_state(self._state_file, self._health)
                    continue   # re-select — all models on this key now excluded

                # ── Quota / unavailable / unknown: exponential back-off ────
                backoff = self._backoff(health.failures + 1)
                health.record_failure(err_type, backoff)
                _save_state(self._state_file, self._health)
                logger.warning(
                    "✗ key#%d model=%s err=%s attempt=%d cooldown=%.0fs — %s",
                    ki + 1, model_name, err_type, attempt, backoff, exc,
                )

                if attempt < max_retries_per_pair:
                    logger.info("Sleeping %.0fs before retry…", backoff)
                    time.sleep(backoff)
                # After the failure is recorded the pair is in cooldown;
                # _select_best_pair will skip it next iteration.

        raise AllCombinationsExhaustedError(
            f"All key×model combinations failed or exhausted: "
            f"{'; '.join(attempts_log) or 'none attempted'}"
        )

    # ── Reporting ─────────────────────────────────────────────────────────

    def health_report(self) -> dict:
        """Return a serialisable health report for all (key, model) pairs."""
        report: dict = {"ts": datetime.utcnow().isoformat(), "keys": {}}
        for ki in range(len(self.api_keys)):
            k_id = f"key_{ki+1}"
            report["keys"][k_id] = {}
            for mi, m in enumerate(self.models):
                h = self._slot(ki, m)
                report["keys"][k_id][m] = {
                    "state":        h.health_state.value,
                    "priority":     round(h.priority_score(mi, ki), 2),
                    "ok":           h.successes,
                    "consecutive_failures": h.consecutive_failures,
                    "error_type":   h.error_type,
                    "cooling":      h.is_cooling(),
                    "wait_s":       round(h.cooldown_remaining(), 1),
                    "last_success": h.last_success_at,
                    "last_failure": h.last_failure_at,
                    "retry_after":  h.retry_after,
                }
        return report

    def log_health(self) -> None:
        logger.info("Gemini health:\n%s", json.dumps(self.health_report(), indent=2))

    # ── Backwards-compat alias ─────────────────────────────────────────────
    def _call_with_fallback(self, prompt: str) -> str:
        return self.generate(prompt)
