"""
Comprehensive tests for the health-aware Gemini rotation engine.

Covers:
  - Official model list and ordering
  - GEMINI_MODEL_ROTATION configuration parsing
  - Configurable model ordering (env override)
  - Deterministic pair selection (same state → same result)
  - Health-aware selection (prefer healthiest pair)
  - Cooldown handling
  - Retry / backoff handling
  - Quota exhaustion
  - Authentication failure (key disabled)
  - Safety / permanent error propagation
  - Fallback behaviour (multi-key cascade)
  - Persistent state (load / save round-trip)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# ── helpers ────────────────────────────────────────────────────────────────

def _engine(tmp_path, api_keys=None, models=None):
    from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
    return GeminiRotationEngine(
        api_keys=api_keys or ["key1", "key2"],
        models=models or list(FREE_MODELS),
        state_file=tmp_path / "state.json",
    )


def _future_iso(seconds: float) -> str:
    return (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()


def _past_iso(seconds: float) -> str:
    return (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Official model list
# ══════════════════════════════════════════════════════════════════════════════

REQUIRED_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]

BANNED_MODELS = [
    "gemini-2.0-flash-lite", "gemini-2.0-flash",
    "gemini-1.5-flash", "gemini-1.5-flash-8b",
    "gemini-2.5-pro", "gemini-3.1-pro-preview",
    "gemini-3-pro-image", "gemini-3.1-flash-image",
    "gemini-3-flash-preview", "gemini-3.1-flash-live-preview",
    "gemini-3.1-flash-tts-preview", "gemini-omni-flash",
    "gemini-flash-latest",
]


class TestOfficialModelList:
    def test_free_models_exact_contents_and_order(self):
        from operational.gemini_rotation import FREE_MODELS, GEMINI_FREE_MODELS
        assert FREE_MODELS == REQUIRED_MODELS, (
            f"FREE_MODELS must be exactly {REQUIRED_MODELS}, got {FREE_MODELS}"
        )
        assert GEMINI_FREE_MODELS == REQUIRED_MODELS

    def test_no_banned_model_in_free_models(self):
        from operational.gemini_rotation import FREE_MODELS
        found = [m for m in BANNED_MODELS if m in FREE_MODELS]
        assert not found, f"Banned models in FREE_MODELS: {found}"

    def test_no_alias_in_free_models(self):
        from operational.gemini_rotation import FREE_MODELS
        aliases = ["latest", "preview", "experimental"]
        for model in FREE_MODELS:
            for alias in aliases:
                assert alias not in model.lower(), (
                    f"Model {model!r} contains forbidden alias token {alias!r}"
                )

    def test_free_models_all_stable_flash(self):
        from operational.gemini_rotation import FREE_MODELS
        for model in FREE_MODELS:
            assert "flash" in model.lower() or "lite" in model.lower(), (
                f"Unexpected model name (expected flash family): {model!r}"
            )
            assert "pro" not in model.lower(), f"Pro model not allowed: {model!r}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Configuration parsing — GEMINI_MODEL_ROTATION
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigParsing:
    def test_parse_default_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL_ROTATION", raising=False)
        from operational.gemini_rotation import parse_model_rotation, FREE_MODELS
        result = parse_model_rotation()
        assert result == list(FREE_MODELS)

    def test_parse_explicit_value(self):
        from operational.gemini_rotation import parse_model_rotation
        result = parse_model_rotation(
            "gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.6-flash"
        )
        assert result == [
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ]

    def test_parse_strips_whitespace(self):
        from operational.gemini_rotation import parse_model_rotation
        result = parse_model_rotation(
            " gemini-3.1-flash-lite , gemini-3.5-flash-lite "
        )
        assert result == ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

    def test_parse_empty_string_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL_ROTATION", raising=False)
        from operational.gemini_rotation import parse_model_rotation, FREE_MODELS
        result = parse_model_rotation("")
        assert result == list(FREE_MODELS)

    def test_parse_reads_env_var(self, monkeypatch):
        monkeypatch.setenv(
            "GEMINI_MODEL_ROTATION",
            "gemini-3.6-flash,gemini-3.5-flash",
        )
        from operational.gemini_rotation import parse_model_rotation
        result = parse_model_rotation()
        assert result == ["gemini-3.6-flash", "gemini-3.5-flash"]

    def test_engine_uses_model_rotation_env(self, tmp_path, monkeypatch):
        """Engine constructed via from_env() must respect GEMINI_MODEL_ROTATION."""
        monkeypatch.setenv(
            "GEMINI_MODEL_ROTATION",
            "gemini-3.6-flash,gemini-3.5-flash",
        )
        monkeypatch.setenv("GEMINI_API_KEY_1", "k1")
        monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY_3", raising=False)
        monkeypatch.setenv("GEMINI_STATE_FILE", str(tmp_path / "s.json"))
        from operational.gemini_rotation import GeminiRotationEngine
        engine = GeminiRotationEngine.from_env()
        assert engine.models == ["gemini-3.6-flash", "gemini-3.5-flash"]

    def test_single_model_rotation(self):
        from operational.gemini_rotation import parse_model_rotation
        result = parse_model_rotation("gemini-3.5-flash")
        assert result == ["gemini-3.5-flash"]

    def test_config_py_exposes_gemini_model_rotation(self, monkeypatch):
        """phase5_6/lib/config.py must expose GEMINI_MODEL_ROTATION."""
        import importlib
        monkeypatch.delenv("GEMINI_MODEL_ROTATION", raising=False)
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        import lib.config as cfg
        importlib.reload(cfg)
        assert hasattr(cfg, "GEMINI_MODEL_ROTATION"), (
            "config.py must expose GEMINI_MODEL_ROTATION"
        )
        from operational.gemini_rotation import FREE_MODELS
        assert cfg.GEMINI_MODEL_ROTATION == list(FREE_MODELS)

    def test_config_py_primary_model_is_independent_of_rotation(self, monkeypatch):
        """DEFAULT_TEXT_MODEL / GEMINI_MODEL_NAME must NOT be derived from ROTATION_MODELS."""
        import importlib
        # Set ROTATION_MODELS to something different from the default text model
        monkeypatch.setenv("ROTATION_MODELS", "gemini-3.6-flash,gemini-3.5-flash")
        monkeypatch.delenv("DEFAULT_TEXT_MODEL", raising=False)
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        import lib.config as cfg
        importlib.reload(cfg)
        # DEFAULT_TEXT_MODEL must stay at its own default, not change with ROTATION_MODELS
        assert cfg.DEFAULT_TEXT_MODEL == "gemini-3.5-flash-lite"
        assert cfg.GEMINI_MODEL_NAME == "gemini-3.5-flash-lite"
        # Changing ROTATION_MODELS must not affect the text model
        assert cfg.GEMINI_MODEL_NAME != cfg.ROTATION_MODELS[0], (
            "GEMINI_MODEL_NAME must NOT be derived from ROTATION_MODELS[0]"
        )

    def test_config_py_image_model_is_independent_of_rotation(self, monkeypatch):
        """IMAGE_VETTING_MODEL must NOT be derived from ROTATION_MODELS position."""
        import importlib
        # Set ROTATION_MODELS so that [1] is NOT the expected image model
        monkeypatch.setenv("ROTATION_MODELS", "gemini-3.6-flash,gemini-3.5-flash")
        monkeypatch.delenv("IMAGE_VETTING_MODEL", raising=False)
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        import lib.config as cfg
        importlib.reload(cfg)
        # IMAGE_VETTING_MODEL must stay at its own default regardless of rotation order
        assert cfg.IMAGE_VETTING_MODEL == "gemini-3.5-flash-lite"
        assert cfg.IMAGE_VETTING_MODEL_NAME == "gemini-3.5-flash-lite"
        # It must NOT equal ROTATION_MODELS[1] when they differ
        assert cfg.IMAGE_VETTING_MODEL != cfg.ROTATION_MODELS[1], (
            "IMAGE_VETTING_MODEL_NAME must NOT be derived from ROTATION_MODELS[1]"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 3. Deterministic selection
# ══════════════════════════════════════════════════════════════════════════════

class TestDeterministicSelection:
    def test_same_state_same_selection(self, tmp_path):
        """Calling _select_best_pair twice with the same state yields the same result."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        result1 = engine._select_best_pair({}, 2)
        result2 = engine._select_best_pair({}, 2)
        assert result1 == result2

    def test_no_randomness_introduced(self, tmp_path):
        """Run selection 100 times — result must be identical each time."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2", "k3"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        results = {engine._select_best_pair({}, 1) for _ in range(100)}
        assert len(results) == 1, f"Multiple results returned: {results}"

    def test_preferred_pair_is_key0_model0(self, tmp_path):
        """When all pairs are healthy, (key_0, model_0) must be selected first."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2", "k3"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        pair = engine._select_best_pair({}, 2)
        assert pair == (0, FREE_MODELS[0]), (
            f"Expected (0, {FREE_MODELS[0]!r}), got {pair}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. Health-aware selection
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthAwareSelection:
    def test_prefers_pair_with_zero_failures_over_one_with_failures(self, tmp_path):
        """A pair with 0 failures should rank above one with 3 failures."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        models = [FREE_MODELS[0], FREE_MODELS[1]]
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        # Give model[0] 3 consecutive failures (but no cooldown yet)
        h0 = engine._health[f"0:{models[0]}"]
        h0.failures = 3
        h0.error_type = "quota"
        h0.retry_after = None   # expired cooldown so it's selectable

        pair = engine._select_best_pair({}, 2)
        assert pair == (0, models[1]), (
            f"Expected healthier pair (0, {models[1]!r}), got {pair}"
        )

    def test_pair_with_successes_ranks_higher(self, tmp_path):
        """Between two pairs with 0 failures, more successes → higher rank."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        models = [FREE_MODELS[0], FREE_MODELS[1]]
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        h0 = engine._health[f"0:{models[0]}"]
        h0.successes = 10
        h1 = engine._health[f"0:{models[1]}"]
        h1.successes = 1
        pair = engine._select_best_pair({}, 2)
        assert pair == (0, models[0])

    def test_priority_score_healthy_pair(self, tmp_path):
        """Healthy pair (no failures) must have a positive priority score."""
        from operational.gemini_rotation import _Health
        h = _Health()
        score = h.priority_score(0, 0)
        assert score > 0

    def test_priority_score_cooling_pair_is_neg_inf(self, tmp_path):
        """Pair in cooldown must return -inf so it is never selected."""
        from operational.gemini_rotation import _Health
        h = _Health(retry_after=_future_iso(300))
        score = h.priority_score(0, 0)
        assert score == float("-inf")

    def test_priority_score_auth_failed_is_neg_inf(self, tmp_path):
        from operational.gemini_rotation import _Health
        h = _Health(error_type="auth", retry_after=_future_iso(86400))
        score = h.priority_score(0, 0)
        assert score == float("-inf")

    def test_model_position_affects_tiebreaker(self, tmp_path):
        """When two pairs are equally healthy, the one earlier in the model list wins."""
        from operational.gemini_rotation import _Health
        h0 = _Health()   # model index 0
        h1 = _Health()   # model index 1
        assert h0.priority_score(0, 0) > h1.priority_score(1, 0)

    def test_key_position_affects_tiebreaker(self, tmp_path):
        """When two pairs are equally healthy on different keys, key 0 wins."""
        from operational.gemini_rotation import _Health
        h0 = _Health()   # key index 0
        h1 = _Health()   # key index 1
        assert h0.priority_score(0, 0) > h1.priority_score(0, 1)

    def test_engine_skips_to_healthier_pair_after_failure(self, tmp_path):
        """After key1/model0 fails (enters cooldown), engine should try key1/model1 next."""
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError
        models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        call_count = [0]
        tried_models = []

        def side_effect(**kwargs):
            model = kwargs.get("model", "")
            tried_models.append(model)
            call_count[0] += 1
            raise Exception("quota 429")

        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = side_effect
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        assert models[0] in tried_models
        assert models[1] in tried_models


# ══════════════════════════════════════════════════════════════════════════════
# 5. Cooldown handling
# ══════════════════════════════════════════════════════════════════════════════

class TestCooldownHandling:
    def test_cooling_pair_excluded_from_selection(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        models = [FREE_MODELS[0], FREE_MODELS[1]]
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        # Put model[0] into cooldown
        h0 = engine._health[f"0:{models[0]}"]
        h0.retry_after = _future_iso(300)

        pair = engine._select_best_pair({}, 2)
        assert pair == (0, models[1])

    def test_expired_cooldown_is_selectable(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        h = engine._health[f"0:{FREE_MODELS[0]}"]
        h.retry_after = _past_iso(1)   # expired 1 second ago

        pair = engine._select_best_pair({}, 2)
        assert pair == (0, FREE_MODELS[0])

    def test_health_state_is_cooling_down(self):
        from operational.gemini_rotation import _Health, HealthState
        h = _Health(retry_after=_future_iso(30), error_type="unavailable")
        assert h.health_state == HealthState.COOLING_DOWN

    def test_health_state_is_quota_exceeded(self):
        from operational.gemini_rotation import _Health, HealthState
        h = _Health(retry_after=_future_iso(30), error_type="quota")
        assert h.health_state == HealthState.QUOTA_EXCEEDED

    def test_cooldown_remaining_is_positive(self):
        from operational.gemini_rotation import _Health
        h = _Health(retry_after=_future_iso(120))
        assert 100 < h.cooldown_remaining() <= 120

    def test_cooldown_remaining_is_zero_when_expired(self):
        from operational.gemini_rotation import _Health
        h = _Health(retry_after=_past_iso(5))
        assert h.cooldown_remaining() == 0.0

    def test_all_cooling_raises_exhausted(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError
        models = ["gemini-3.1-flash-lite"]
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        # Force all pairs into cooldown
        engine._health[f"0:{models[0]}"].retry_after = _future_iso(300)

        with patch("google.genai.Client"):
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Retry / backoff
# ══════════════════════════════════════════════════════════════════════════════

class TestRetryHandling:
    def test_records_failure_state_after_error(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("quota 429")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert h.failures >= 1
        assert h.error_type == "quota"

    def test_success_resets_failure_count(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        # Manually set failure state
        h = engine._health[f"0:{FREE_MODELS[0]}"]
        h.failures = 5
        h.retry_after = None   # not cooling
        h.error_type = "quota"

        mock_resp = MagicMock()
        mock_resp.text = "ok"
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.return_value = mock_resp
            engine.generate("test")

        assert h.failures == 0
        assert h.error_type == ""
        assert h.retry_after is None

    def test_backoff_increases_with_failures(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine
        engine = GeminiRotationEngine(api_keys=["k1"], models=["gemini-3.1-flash-lite"], state_file=tmp_path/"s.json")
        b1 = engine._backoff(1)
        b2 = engine._backoff(2)
        b3 = engine._backoff(3)
        assert b1 < b2 < b3

    def test_state_persisted_after_failure(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        state_file = tmp_path / "state.json"
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=state_file,
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("quota 429")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        assert state_file.exists()
        saved = json.loads(state_file.read_text())
        assert f"0:{FREE_MODELS[0]}" in saved
        assert saved[f"0:{FREE_MODELS[0]}"]["failures"] >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 7. Quota exhaustion
# ══════════════════════════════════════════════════════════════════════════════

class TestQuotaExhaustion:
    def test_quota_error_sets_cooldown(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("resource_exhausted 429")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert h.error_type == "quota"
        assert h.is_cooling()

    def test_quota_error_on_key1_falls_back_to_key2(self, tmp_path):
        """Quota on Key1/model0 must cause engine to try Key2/model0."""
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError
        models = ["gemini-3.1-flash-lite"]
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        tried_keys = []
        call_count = [0]

        def side_effect(**kwargs):
            # Identify which key is being used by client init order
            call_count[0] += 1
            raise Exception("quota 429")

        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = side_effect
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        # Both keys should have been tried
        assert engine._health[f"0:{models[0]}"].failures >= 1
        assert engine._health[f"1:{models[0]}"].failures >= 1

    def test_all_models_all_keys_quota_exhausted(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("quota 429")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        # All pairs should be in cooldown
        for ki in range(2):
            for m in FREE_MODELS:
                h = engine._health[f"{ki}:{m}"]
                assert h.failures >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 8. Authentication failure
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthFailure:
    def test_auth_error_disables_key_for_all_models(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("invalid_api_key 401")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test")

        for m in FREE_MODELS:
            h = engine._health[f"0:{m}"]
            assert h.error_type == "auth", f"{m} should be auth-disabled"

    def test_auth_health_state_is_auth_failed(self):
        from operational.gemini_rotation import _Health, HealthState
        h = _Health(error_type="auth", retry_after=_future_iso(86400))
        assert h.health_state == HealthState.AUTH_FAILED

    def test_auth_key_disabled_24h(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("permission_denied 403")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test")

        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert h.cooldown_remaining() > 80_000  # close to 86400 seconds

    def test_auth_key_falls_back_to_second_key(self, tmp_path):
        """If key1 auth-fails, engine tries key2 successfully."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        call_count = [0]
        mock_resp = MagicMock()
        mock_resp.text = "success"

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("invalid_api_key 401")
            return mock_resp

        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = side_effect
            result = engine.generate("test")

        assert result == "success"
        # Key 1 must be auth-disabled
        assert engine._health[f"0:{FREE_MODELS[0]}"].error_type == "auth"
        # Key 2 must have succeeded
        assert engine._health[f"1:{FREE_MODELS[0]}"].successes == 1


# ══════════════════════════════════════════════════════════════════════════════
# 9. Safety / permanent error propagation
# ══════════════════════════════════════════════════════════════════════════════

class TestSafetyAndPermanentErrors:
    def test_safety_error_propagates_immediately(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        exc = Exception("safety blocked content_filter")
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = exc
            with pytest.raises(Exception, match="safety"):
                engine.generate("test")

        # Only the first pair should have been attempted (no fallback)
        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert h.error_type == "safety"
        # Second pair should be untouched
        h2 = engine._health[f"0:{FREE_MODELS[1]}"]
        assert h2.failures == 0

    def test_permanent_error_propagates_immediately(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        exc = Exception("invalid_argument 400 bad request")
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = exc
            with pytest.raises(Exception, match="400"):
                engine.generate("test")

    def test_safety_error_no_cooldown_set(self, tmp_path):
        """Safety errors should not set a cooldown (they are caller errors)."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("content blocked safety")
            try:
                engine.generate("test")
            except Exception:
                pass

        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert not h.is_cooling(), "Safety errors must not set cooldown"


# ══════════════════════════════════════════════════════════════════════════════
# 10. Fallback behaviour
# ══════════════════════════════════════════════════════════════════════════════

class TestFallbackBehaviour:
    def test_succeeds_on_second_pair_after_first_fails(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        call_count = [0]
        mock_resp = MagicMock()
        mock_resp.text = "fallback success"

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("quota 429")
            return mock_resp

        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = side_effect
            result = engine.generate("test", max_retries_per_pair=1)

        assert result == "fallback success"

    def test_all_keys_exhausted_raises(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2", "k3"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        with patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = Exception("quota 429")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

    def test_health_report_contains_all_pairs(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        report = engine.health_report()
        assert "key_1" in report["keys"]
        assert "key_2" in report["keys"]
        for m in FREE_MODELS:
            assert m in report["keys"]["key_1"]

    def test_health_report_includes_state_and_priority(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=tmp_path / "s.json",
        )
        report = engine.health_report()
        entry = report["keys"]["key_1"][FREE_MODELS[0]]
        assert "state" in entry
        assert "priority" in entry
        assert "consecutive_failures" in entry
        assert "retry_after" in entry


# ══════════════════════════════════════════════════════════════════════════════
# 11. Persistent state round-trip
# ══════════════════════════════════════════════════════════════════════════════

class TestPersistentState:
    def test_state_survives_reinitialisation(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        state_file = tmp_path / "state.json"
        engine1 = GeminiRotationEngine(
            api_keys=["k1"],
            models=list(FREE_MODELS),
            state_file=state_file,
        )
        h = engine1._health[f"0:{FREE_MODELS[0]}"]
        h.failures = 7
        h.retry_after = _future_iso(500)
        h.error_type = "quota"
        from operational.gemini_rotation import _save_state
        _save_state(state_file, engine1._health)

        engine2 = GeminiRotationEngine(
            api_keys=["k1"],
            models=list(FREE_MODELS),
            state_file=state_file,
        )
        h2 = engine2._health[f"0:{FREE_MODELS[0]}"]
        assert h2.failures == 7
        assert h2.error_type == "quota"
        assert h2.is_cooling()

    def test_legacy_cooldown_until_field_loaded(self, tmp_path):
        """Old state files that use 'cooldown_until' must be loaded correctly."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            f"0:{FREE_MODELS[0]}": {
                "failures": 3,
                "successes": 0,
                "last_failure_at": _past_iso(10),
                "last_success_at": None,
                "cooldown_until": _future_iso(300),   # legacy field name
                "error_type": "quota",
            }
        }))
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=list(FREE_MODELS),
            state_file=state_file,
        )
        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert h.failures == 3
        assert h.is_cooling()

    def test_corrupted_state_file_falls_back_to_fresh(self, tmp_path):
        """If the state file is corrupt, the engine must start with fresh state."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json {{{")
        # Should not raise
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=[FREE_MODELS[0]],
            state_file=state_file,
        )
        h = engine._health[f"0:{FREE_MODELS[0]}"]
        assert h.failures == 0


# ══════════════════════════════════════════════════════════════════════════════
# 12. _Health dataclass completeness
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthDataclass:
    def test_health_state_property_healthy(self):
        from operational.gemini_rotation import _Health, HealthState
        h = _Health()
        assert h.health_state == HealthState.HEALTHY

    def test_consecutive_failures_alias(self):
        from operational.gemini_rotation import _Health
        h = _Health(failures=4)
        assert h.consecutive_failures == 4

    def test_retry_after_alias_cooldown_until(self):
        from operational.gemini_rotation import _Health
        ts = _future_iso(60)
        h = _Health(retry_after=ts)
        assert h.cooldown_until == ts

    def test_to_dict_and_from_dict_round_trip(self):
        from operational.gemini_rotation import _Health
        h = _Health(failures=2, successes=5, error_type="quota")
        h.retry_after = _future_iso(100)
        h.last_failure_at = _past_iso(10)
        d = h.to_dict()
        h2 = _Health.from_dict(d)
        assert h2.failures == 2
        assert h2.successes == 5
        assert h2.error_type == "quota"
        assert h2.is_cooling()

    def test_record_success_resets_all_failure_fields(self):
        from operational.gemini_rotation import _Health
        h = _Health(failures=5, error_type="quota", retry_after=_future_iso(100))
        h.record_success()
        assert h.failures == 0
        assert h.error_type == ""
        assert h.retry_after is None
        assert not h.is_cooling()
        assert h.successes == 1

    def test_record_failure_sets_retry_after(self):
        from operational.gemini_rotation import _Health
        h = _Health()
        h.record_failure("quota", 60)
        assert h.failures == 1
        assert h.error_type == "quota"
        assert h.is_cooling()

    def test_record_failure_zero_backoff_no_cooldown(self):
        from operational.gemini_rotation import _Health
        h = _Health()
        h.record_failure("permanent", 0)
        assert not h.is_cooling()


# ══════════════════════════════════════════════════════════════════════════════
# 13. Configuration independence (Rule 1, Rule 2, Rule 3)
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigurationIndependence:
    """Verify that ROTATION_MODELS never bleeds into DEFAULT_TEXT_MODEL or IMAGE_VETTING_MODEL."""

    def _reload_config(self, monkeypatch, **env_overrides):
        import importlib
        import lib.config as cfg_mod
        for k, v in env_overrides.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        import lib.config as cfg
        importlib.reload(cfg)
        return cfg

    def test_changing_rotation_models_does_not_change_default_text_model(self, monkeypatch):
        """Rule 1: ROTATION_MODELS must NEVER change DEFAULT_TEXT_MODEL."""
        cfg = self._reload_config(
            monkeypatch,
            ROTATION_MODELS="gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite",
            DEFAULT_TEXT_MODEL=None,
        )
        assert cfg.DEFAULT_TEXT_MODEL == "gemini-3.5-flash-lite", (
            "DEFAULT_TEXT_MODEL changed when ROTATION_MODELS changed — must be independent"
        )
        assert cfg.GEMINI_MODEL_NAME == "gemini-3.5-flash-lite"

    def test_changing_rotation_models_does_not_change_image_vetting_model(self, monkeypatch):
        """Rule 2: ROTATION_MODELS must NEVER change IMAGE_VETTING_MODEL."""
        cfg = self._reload_config(
            monkeypatch,
            ROTATION_MODELS="gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite",
            IMAGE_VETTING_MODEL=None,
        )
        assert cfg.IMAGE_VETTING_MODEL == "gemini-3.5-flash-lite", (
            "IMAGE_VETTING_MODEL changed when ROTATION_MODELS changed — must be independent"
        )
        assert cfg.IMAGE_VETTING_MODEL_NAME == "gemini-3.5-flash-lite"

    def test_default_text_model_overridable_independently(self, monkeypatch):
        """DEFAULT_TEXT_MODEL env var sets the text model independently."""
        cfg = self._reload_config(
            monkeypatch,
            DEFAULT_TEXT_MODEL="gemini-3.5-flash",
            ROTATION_MODELS=None,
        )
        assert cfg.DEFAULT_TEXT_MODEL == "gemini-3.5-flash"
        assert cfg.GEMINI_MODEL_NAME == "gemini-3.5-flash"
        # Rotation list must remain at its own default
        from operational.gemini_rotation import FREE_MODELS
        assert cfg.ROTATION_MODELS == list(FREE_MODELS)

    def test_image_vetting_model_overridable_independently(self, monkeypatch):
        """IMAGE_VETTING_MODEL env var sets the image model independently."""
        cfg = self._reload_config(
            monkeypatch,
            IMAGE_VETTING_MODEL="gemini-3.5-flash",
            ROTATION_MODELS=None,
        )
        assert cfg.IMAGE_VETTING_MODEL == "gemini-3.5-flash"
        assert cfg.IMAGE_VETTING_MODEL_NAME == "gemini-3.5-flash"
        from operational.gemini_rotation import FREE_MODELS
        assert cfg.ROTATION_MODELS == list(FREE_MODELS)

    def test_learning_model_overridable_independently(self, monkeypatch):
        """LEARNING_MODEL env var sets the learning model independently."""
        cfg = self._reload_config(
            monkeypatch,
            LEARNING_MODEL="gemini-3.6-flash",
            ROTATION_MODELS=None,
        )
        assert cfg.LEARNING_MODEL == "gemini-3.6-flash"
        from operational.gemini_rotation import FREE_MODELS
        assert cfg.ROTATION_MODELS == list(FREE_MODELS)

    def test_all_four_independent_when_all_set(self, monkeypatch):
        """All four variables may be set to different values simultaneously."""
        cfg = self._reload_config(
            monkeypatch,
            DEFAULT_TEXT_MODEL="gemini-3.5-flash-lite",
            IMAGE_VETTING_MODEL="gemini-3.5-flash-lite",
            LEARNING_MODEL="gemini-3.5-flash",
            ROTATION_MODELS="gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.5-flash,gemini-3.6-flash",
        )
        assert cfg.DEFAULT_TEXT_MODEL == "gemini-3.5-flash-lite"
        assert cfg.IMAGE_VETTING_MODEL == "gemini-3.5-flash-lite"
        assert cfg.LEARNING_MODEL == "gemini-3.5-flash"
        assert cfg.ROTATION_MODELS == [
            "gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
            "gemini-3.5-flash", "gemini-3.6-flash",
        ]

    def test_legacy_gemini_model_rotation_alias_still_works(self, monkeypatch):
        """GEMINI_MODEL_ROTATION env var (legacy) must still configure the rotation engine."""
        cfg = self._reload_config(
            monkeypatch,
            GEMINI_MODEL_ROTATION="gemini-3.6-flash,gemini-3.5-flash",
            ROTATION_MODELS=None,
        )
        assert cfg.ROTATION_MODELS == ["gemini-3.6-flash", "gemini-3.5-flash"]
        assert cfg.GEMINI_MODEL_ROTATION == ["gemini-3.6-flash", "gemini-3.5-flash"]
        # Default text model must be unchanged
        assert cfg.DEFAULT_TEXT_MODEL == "gemini-3.5-flash-lite"


# ══════════════════════════════════════════════════════════════════════════════
# 14. Health-dominates-rotation-order (Rule 3)
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthDominatesRotationOrder:
    """Verify that runtime health always outweighs model/key position in the list."""

    def test_unhealthy_first_model_yields_to_healthy_second_model(self, tmp_path):
        """Rule 3: A healthy model later in the list must beat an unhealthy model earlier."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        models = list(FREE_MODELS)  # [m0, m1, m2, m3]
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        # Give models[0] (index 0, normally preferred) several failures
        h0 = engine._health[f"0:{models[0]}"]
        h0.failures = 3
        h0.error_type = "quota"
        h0.retry_after = None  # expired cooldown — selectable but penalised

        # models[1] is completely healthy
        pair = engine._select_best_pair({}, 2)
        assert pair == (0, models[1]), (
            f"Expected healthier model (0, {models[1]!r}), got {pair}. "
            "Health must dominate over rotation-list position."
        )

    def test_high_successes_last_model_beats_zero_successes_first_model(self, tmp_path):
        """Rule 3: More past successes must beat list position when failures are equal."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        models = [FREE_MODELS[0], FREE_MODELS[3]]  # first and last in list
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        # models[0] (list position 0): 0 successes, 0 failures
        h0 = engine._health[f"0:{models[0]}"]
        h0.successes = 0
        # models[1] (list position 1): 15 successes, 0 failures
        h1 = engine._health[f"0:{models[1]}"]
        h1.successes = 15

        pair = engine._select_best_pair({}, 2)
        assert pair == (0, models[1]), (
            f"Expected model with more successes (0, {models[1]!r}), got {pair}. "
            "Success history must dominate over rotation-list position."
        )

    def test_rotation_order_is_only_tiebreaker_when_health_equal(self, tmp_path):
        """Rule 3 / Rule 4: When health is identical, rotation-list order breaks the tie."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS, _Health
        models = list(FREE_MODELS)
        engine = GeminiRotationEngine(
            api_keys=["k1"],
            models=models,
            state_file=tmp_path / "s.json",
        )
        # All models equally healthy — rotation order (model[0]) should win
        pair = engine._select_best_pair({}, 2)
        assert pair == (0, models[0]), (
            f"Expected rotation-list[0] as tiebreaker, got {pair}"
        )

    def test_tiebreaker_weights_smaller_than_smallest_health_delta(self):
        """The model-index tiebreaker weight must be smaller than the smallest health delta."""
        from operational.gemini_rotation import _Health
        # Smallest health delta: 1 success = 5.0 points
        # Largest model list we support: 100 models → max tiebreaker = 100 × 0.001 = 0.1
        # 0.1 < 5.0 — health wins
        h_no_successes  = _Health(successes=0)
        h_one_success   = _Health(successes=1)
        for model_idx in range(100):
            score_no_success = h_no_successes.priority_score(model_idx, 0)
            score_one_success = h_one_success.priority_score(model_idx + 100, 0)  # much worse position
            assert score_one_success > score_no_success, (
                f"At model_idx={model_idx}: one success (position {model_idx+100}) "
                f"scored {score_one_success} but must beat zero successes (position {model_idx}) "
                f"scored {score_no_success}. Health must dominate position."
            )

    def test_determinism_preserved_health_dominated(self, tmp_path):
        """Rule 4: Same health state → same selection, 100 times in a row."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        engine = GeminiRotationEngine(
            api_keys=["k1", "k2"],
            models=list(FREE_MODELS),
            state_file=tmp_path / "s.json",
        )
        # Give k1/m0 some failures so health is mixed
        engine._health[f"0:{FREE_MODELS[0]}"].failures = 2
        engine._health[f"0:{FREE_MODELS[0]}"].error_type = "quota"
        engine._health[f"0:{FREE_MODELS[0]}"].retry_after = None
        engine._health[f"1:{FREE_MODELS[2]}"].successes = 10

        results = {engine._select_best_pair({}, 2) for _ in range(100)}
        assert len(results) == 1, (
            f"Non-deterministic selection: got multiple results {results}"
        )
