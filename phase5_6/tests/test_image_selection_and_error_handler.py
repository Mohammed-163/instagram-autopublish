"""
Focused tests for:
  - GeminiClient.select_best_image()  (image vetting via Gemini Vision)
  - error_handler._coerce_diagnosis_to_str()
  - error_handler.handle_unexpected()  (traceback preservation, non-str diagnosis)

No real API keys or network calls are made.
All google-genai SDK calls are injected via sys.modules patching so the tests
work even when google-genai is not installed in the test environment.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — makes phase5_6 importable without installation
# ---------------------------------------------------------------------------
_HERE       = os.path.dirname(os.path.abspath(__file__))
_PHASE56    = os.path.dirname(_HERE)
_PROJECT    = os.path.dirname(_PHASE56)
for _p in (_PHASE56, _PROJECT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# google-genai SDK mock factory
#
# select_best_image() does `from google import genai` / `from google.genai
# import types` inside the function body.  When google-genai is not installed
# those imports raise ImportError which the method re-raises as
# ImageVettingError.  To bypass this without needing the real SDK we inject
# mock modules into sys.modules BEFORE calling the method; Python's import
# machinery finds them there and skips the real package lookup.
#
# We deliberately do NOT use patch("google.genai") because that helper
# requires the attribute to already exist on the parent module.
# ---------------------------------------------------------------------------

@contextmanager
def _mock_genai_sdk(generate_content_return=None, generate_content_side_effect=None):
    """
    Context manager that temporarily stubs the google-genai SDK in sys.modules.

    Inside the block:
      - `from google import genai`          → mock_genai
      - `from google.genai import types`    → mock_types
      - genai.Client(api_key=...)           → mock_client_instance
      - client.models.generate_content(...) → returns / raises as configured
    """
    mock_types = MagicMock()
    mock_types.Part.from_bytes.side_effect = lambda data, mime_type: MagicMock(name="part-bytes")
    mock_types.Part.from_text.side_effect  = lambda text:            MagicMock(name="part-text")

    mock_client_instance = MagicMock()
    if generate_content_side_effect is not None:
        mock_client_instance.models.generate_content.side_effect = generate_content_side_effect
    else:
        resp      = MagicMock()
        resp.text = generate_content_return
        mock_client_instance.models.generate_content.return_value = resp

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client_instance
    mock_genai.types = mock_types

    # The real google namespace package must stay in sys.modules so other
    # imports that depend on it (google.auth, etc.) keep working.
    # We only inject google.genai and google.genai.types.
    extra = {
        "google.genai":       mock_genai,
        "google.genai.types": mock_types,
    }
    import google

    with patch.dict(sys.modules, extra), patch.object(google, "genai", mock_genai, create=True):
        yield mock_client_instance   # yield the inner client so tests can inspect calls


def _make_engine(image_check_key="fake-image-key", api_keys=None):
    engine = MagicMock()
    engine.image_check_key = image_check_key
    engine.api_keys        = api_keys or ["fake-key-1"]
    return engine


def _make_client(image_check_key="fake-image-key", api_keys=None):
    """Return a GeminiClient instance with a fully mocked rotation engine."""
    from lib.gemini_client import GeminiClient
    client         = GeminiClient.__new__(GeminiClient)
    client._engine = _make_engine(image_check_key=image_check_key, api_keys=api_keys)
    return client


# ---------------------------------------------------------------------------
# TestSelectBestImage
# ---------------------------------------------------------------------------

class TestSelectBestImage:

    # ── 1. Valid candidates → selected path ──────────────────────────────────

    def test_valid_candidates_returns_selected_path(self, tmp_path):
        """Gemini picks index 2 (1-based) → function returns the second path."""
        p1 = tmp_path / "bg_0.jpg"
        p2 = tmp_path / "bg_1.jpg"
        p1.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)
        p2.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)

        gemini_response = json.dumps({"selected_index": 2, "reason": "best match"})

        client = _make_client()
        with _mock_genai_sdk(generate_content_return=gemini_response):
            from lib.gemini_client import GeminiClient
            result = GeminiClient.select_best_image(client, [str(p1), str(p2)], "stress and focus")

        assert result == str(p2), (
            f"Expected second candidate path ({p2}), got {result!r}"
        )

    # ── 2. Empty candidate list → None, no API call ──────────────────────────

    def test_no_candidates_returns_none_without_api_call(self):
        """Empty list must return None immediately; the SDK must never be called."""
        client = _make_client()

        # No sys.modules injection needed — the function returns before any import
        with _mock_genai_sdk() as mock_client_instance:
            from lib.gemini_client import GeminiClient
            result = GeminiClient.select_best_image(client, [], "any topic")

        assert result is None
        mock_client_instance.models.generate_content.assert_not_called()

    # ── 3. All candidates rejected (selected_index == -1) → None ─────────────

    def test_all_candidates_rejected_returns_none(self, tmp_path):
        """When Gemini returns selected_index: -1 every candidate was refused."""
        p1 = tmp_path / "bg_0.jpg"
        p1.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)

        gemini_response = json.dumps({"selected_index": -1, "reason": "none acceptable"})

        client = _make_client()
        with _mock_genai_sdk(generate_content_return=gemini_response):
            from lib.gemini_client import GeminiClient
            result = GeminiClient.select_best_image(client, [str(p1)], "topic")

        assert result is None

    # ── 4. Gemini API failure → ImageVettingError, NOT silent first-image ─────

    def test_gemini_api_failure_raises_image_vetting_error(self, tmp_path):
        """An SDK exception during generate_content must surface as
        ImageVettingError.  The old code swallowed this with a bare
        `except Exception: pass` and returned images[0]; that must not happen."""
        from lib.gemini_client import ImageVettingError

        p1 = tmp_path / "bg_0.jpg"
        p1.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)

        client = _make_client()
        with _mock_genai_sdk(generate_content_side_effect=ConnectionError("network timeout")):
            from lib.gemini_client import GeminiClient
            with pytest.raises(ImageVettingError) as exc_info:
                GeminiClient.select_best_image(client, [str(p1)], "topic")

        msg = str(exc_info.value).lower()
        assert "vetting" in msg or "failed" in msg or "network" in msg, (
            f"Exception should describe the API failure; got: {exc_info.value}"
        )
        # Critically: the original exception must be chained (not swallowed)
        assert exc_info.value.__cause__ is not None, (
            "ImageVettingError must chain the original exception via 'from exc'"
        )

    # ── 4b. Unreadable candidate file → ImageVettingError ────────────────────

    def test_unreadable_file_raises_image_vetting_error(self):
        """A missing/unreadable candidate path must raise ImageVettingError."""
        from lib.gemini_client import ImageVettingError

        client = _make_client()
        with _mock_genai_sdk():
            from lib.gemini_client import GeminiClient
            with pytest.raises(ImageVettingError) as exc_info:
                GeminiClient.select_best_image(
                    client, ["/nonexistent/does_not_exist.jpg"], "topic"
                )

        msg = str(exc_info.value).lower()
        assert "cannot read" in msg or "read" in msg, (
            f"Exception should mention file reading; got: {exc_info.value}"
        )
        assert exc_info.value.__cause__ is not None, (
            "ImageVettingError must chain the original OSError"
        )

    # ── 4c. No API keys available → ImageVettingError ────────────────────────

    def test_no_api_key_raises_image_vetting_error(self, tmp_path):
        """When neither image_check_key nor any rotation key is configured the
        method must raise ImageVettingError rather than silently do nothing."""
        from lib.gemini_client import ImageVettingError

        p1 = tmp_path / "bg_0.jpg"
        p1.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)

        client = _make_client(image_check_key="", api_keys=["", ""])
        with _mock_genai_sdk():
            from lib.gemini_client import GeminiClient
            with pytest.raises(ImageVettingError) as exc_info:
                GeminiClient.select_best_image(client, [str(p1)], "topic")

        assert "key" in str(exc_info.value).lower(), (
            f"Exception should mention API key; got: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# TestErrorHandler
# ---------------------------------------------------------------------------

class TestErrorHandler:

    @staticmethod
    def _eh():
        import importlib, lib.error_handler as eh
        importlib.reload(eh)
        return eh

    def test_unexpected_error_keeps_secrets_and_model_output_private(self):
        eh = self._eh()
        notifier = MagicMock()
        try:
            raise ValueError("secret connection detail")
        except ValueError:
            eh.handle_unexpected(notifier, "scripts/publish.py")
        notifier.alert_critical.assert_called_once()
        _, body = notifier.alert_critical.call_args.args
        assert body == "scripts/publish.py: ValueError"
