"""
The single dedicated fingerprint module for the entire system.

Fingerprints are SHA-256 hashes computed over a canonical JSON
serialization (sort_keys=True, no whitespace variance) of a payload.
No timestamps, randomness, or UUIDs may ever be included in a payload
passed to this module.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


class FingerprintMismatchError(Exception):
    """Raised when a replayed fingerprint does not match the recorded one."""


_FORBIDDEN_KEYS = {"timestamp", "created_at", "updated_at", "uuid", "random_seed", "nonce"}


def _assert_deterministic_payload(payload: Any) -> None:
    """Best-effort guard against accidentally fingerprinting non-deterministic fields."""
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
    Compute a deterministic SHA-256 fingerprint for the given JSON-serializable payload.

    The payload is canonicalized via json.dumps(..., sort_keys=True, separators=(",", ":"))
    before hashing, guaranteeing that logically identical payloads always yield the same
    fingerprint regardless of key insertion order.
    """
    _assert_deterministic_payload(payload)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_fingerprint(payload: Any, expected_fingerprint: str) -> None:
    """Recompute the fingerprint of payload and raise if it diverges from expected_fingerprint."""
    actual = compute_fingerprint(payload)
    if actual != expected_fingerprint:
        raise FingerprintMismatchError(
            f"Fingerprint mismatch: expected {expected_fingerprint}, got {actual}"
        )
