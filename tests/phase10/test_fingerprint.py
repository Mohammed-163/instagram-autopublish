"""Fingerprint determinism tests."""
from phase10_intelligence.fingerprint import compute_fingerprint


def test_fingerprint_is_deterministic_regardless_of_key_order():
    a = {"x": 1, "y": 2, "z": {"b": 2, "a": 1}}
    b = {"z": {"a": 1, "b": 2}, "y": 2, "x": 1}
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_fingerprint_changes_with_payload():
    a = compute_fingerprint({"x": 1})
    b = compute_fingerprint({"x": 2})
    assert a != b


def test_fingerprint_rejects_non_deterministic_fields():
    import pytest
    with pytest.raises(ValueError):
        compute_fingerprint({"timestamp": "2026-01-01"})
