"""
Shared fingerprint utilities.

This is the canonical fingerprint implementation for the entire system.
All phases SHOULD use this when computing cross-phase fingerprints.
Each phase may still have its own internal fingerprint module for
domain-specific payloads — those are intentionally preserved untouched.

Rules (enforced here):
  - SHA-256 only.
  - json.dumps(..., sort_keys=True) for canonicalization.
  - No timestamps, UUIDs, randomness in payload.
  - Same logical input → same fingerprint, forever.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


class FingerprintMismatchError(Exception):
    """Raised when a replayed fingerprint does not match the recorded one."""


_FORBIDDEN_KEYS = {"timestamp", "created_at", "updated_at", "uuid", "random_seed", "nonce"}


def _assert_deterministic_payload(payload: Any) -> None:
    """Guard against accidentally fingerprinting non-deterministic fields."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in _FORBIDDEN_KEYS:
                raise ValueError(
                    f"Non-deterministic field '{key}' must not participate in a fingerprint."
                )
            _assert_deterministic_payload(value)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            _assert_deterministic_payload(item)


def compute_fingerprint(payload: Any) -> str:
    """
    Compute a deterministic SHA-256 fingerprint for any JSON-serializable payload.
    """
    _assert_deterministic_payload(payload)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_fingerprint(payload: Any, expected_fingerprint: str) -> None:
    """Recompute the fingerprint and raise if it diverges."""
    actual = compute_fingerprint(payload)
    if actual != expected_fingerprint:
        raise FingerprintMismatchError(
            f"Fingerprint mismatch: expected {expected_fingerprint}, got {actual}"
        )
