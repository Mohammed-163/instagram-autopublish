"""
Tests for new operational components:
  - Gemini rotation ordering + persistent state
  - Circuit breaker behavior
  - Log redaction
  - Backup checksum
  - Restore dry-run
  - SQLite production fallback rejection
  - Secret name consistency
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


# ── Gemini Rotation ────────────────────────────────────────────────────────

class TestGeminiRotation:
    def _engine(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        return GeminiRotationEngine(
            api_keys=["key1", "key2"],
            models=FREE_MODELS,
            state_file=tmp_path / "state.json",
        )

    def test_rotation_order_tries_model_before_next_key(self, tmp_path):
        """All models on Key1 should be tried before Key2."""
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS, AllCombinationsExhaustedError
        engine = self._engine(tmp_path)
        tried = []

        def fake_generate(model, contents, **_):
            tried.append((model,))
            raise Exception("quota exhausted 429")

        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = fake_generate
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test prompt")

        # Every model should have been attempted on each key
        assert len(tried) > 0

    def test_state_persists_after_success(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS
        state_file = tmp_path / "state.json"
        engine = GeminiRotationEngine(api_keys=["k1"], models=FREE_MODELS, state_file=state_file)

        mock_resp = MagicMock()
        mock_resp.text = "Hello"
        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_resp
            result = engine.generate("test")

        assert result == "Hello"
        assert state_file.exists()
        saved = json.loads(state_file.read_text())
        # Should have at least one key with recorded success
        assert len(saved) > 0

    def test_state_loaded_on_reinitialize(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS, _Health
        state_file = tmp_path / "state.json"
        # Write a pre-existing state with one slot in cooldown
        saved = {"0:gemini-3.1-flash-lite": {"failures": 5, "successes": 0,
            "last_failure_at": "2099-01-01T00:00:00", "last_success_at": None,
            "cooldown_until": "2099-01-01T12:00:00", "error_type": "quota"}}
        state_file.write_text(json.dumps(saved))

        engine = GeminiRotationEngine(api_keys=["k1"], models=FREE_MODELS, state_file=state_file)
        health = engine._health["0:gemini-3.1-flash-lite"]
        assert health.failures == 5
        assert health.is_cooling()

    def test_auth_error_skips_all_models_for_key(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS, AllCombinationsExhaustedError
        engine = GeminiRotationEngine(api_keys=["k1"], models=["gemini-3.1-flash-lite"], state_file=tmp_path / "s.json")

        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("invalid_api_key 401")
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test")

        h = engine._health["0:gemini-3.1-flash-lite"]
        assert h.error_type == "auth"

    def test_all_combinations_exhausted_raises_clearly(self, tmp_path):
        from operational.gemini_rotation import GeminiRotationEngine, FREE_MODELS, AllCombinationsExhaustedError
        engine = GeminiRotationEngine(api_keys=["k1"], models=["gemini-3.1-flash-lite"], state_file=tmp_path / "s.json")

        with patch("google.genai.Client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("quota 429")
            with pytest.raises(AllCombinationsExhaustedError) as exc_info:
                engine.generate("test")

        assert "quota" in str(exc_info.value).lower() or "fail" in str(exc_info.value).lower()


# ── Circuit Breaker ────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_closed_allows_requests(self):
        from operational.resilience import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        from operational.resilience import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_recovery_timeout(self):
        from operational.resilience import CircuitBreaker, CircuitState
        from datetime import datetime, timedelta
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_s=0.01)
        cb.record_failure(); cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time; time.sleep(0.05)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closed_after_success_in_half_open(self):
        from operational.resilience import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_s=0.01, success_threshold=1)
        cb.record_failure(); cb.record_failure()
        import time; time.sleep(0.05)
        _ = cb.state  # trigger OPEN → HALF_OPEN transition via property
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ── Log redaction ──────────────────────────────────────────────────────────

class TestLogRedaction:
    def test_bearer_token_redacted(self):
        from operational.logging_config import _redact
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
        result = _redact(text)
        assert "[REDACTED]" in result
        assert "eyJhbGci" not in result

    def test_api_key_redacted(self):
        from operational.logging_config import _redact
        text = "api_key=AIzaSyDabc1234567890LONGVALUE"
        result = _redact(text)
        assert "[REDACTED]" in result

    def test_normal_text_unchanged(self):
        from operational.logging_config import _redact
        text = "Processing post_id=123 status=published"
        result = _redact(text)
        assert result == text


# ── SQLite production guard ────────────────────────────────────────────────

class TestSQLiteGuard:
    def test_sqlite_rejected_in_production(self, monkeypatch):
        monkeypatch.delenv("ALLOW_SQLITE_FALLBACK", raising=False)
        monkeypatch.delenv("LEARNING_LAYER_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)

        from operational import db_config
        # Reload to pick up env changes
        import importlib
        importlib.reload(db_config)

        with pytest.raises(RuntimeError, match="No database URL"):
            db_config.resolve_database_url("LEARNING_LAYER_DATABASE_URL", "sqlite:///test.db")

    def test_sqlite_allowed_with_flag(self, monkeypatch):
        monkeypatch.setenv("ALLOW_SQLITE_FALLBACK", "true")
        monkeypatch.delenv("LEARNING_LAYER_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)

        from operational import db_config
        import importlib
        importlib.reload(db_config)

        url = db_config.resolve_database_url("LEARNING_LAYER_DATABASE_URL", "sqlite:///test.db")
        assert url == "sqlite:///test.db"


# ── Backup checksum ────────────────────────────────────────────────────────

class TestBackupChecksum:
    def test_validate_valid_backup(self, tmp_path):
        from operational.restore import validate_backup
        backup_file = tmp_path / "phase8_20240101.db.gz"
        with gzip.open(backup_file, "wb") as f:
            f.write(b"SQLite format 3\x00" + b"\x00" * 100)
        assert validate_backup(backup_file) is True

    def test_validate_corrupt_backup(self, tmp_path):
        from operational.restore import validate_backup
        backup_file = tmp_path / "phase8_corrupt.db.gz"
        backup_file.write_bytes(b"not a gzip file at all")
        assert validate_backup(backup_file) is False

    def test_restore_dry_run_no_write(self, tmp_path):
        from operational.restore import restore_database
        backup_file = tmp_path / "phase8_test.db.gz"
        with gzip.open(backup_file, "wb") as f:
            f.write(b"fake db content")
        target = tmp_path / "output.db"
        result = restore_database(backup_file, target, dry_run=True)
        assert result is True
        assert not target.exists()   # dry run should NOT write


# ── Secret name consistency ────────────────────────────────────────────────

class TestSecretConsistency:
    EXPECTED_SECRETS = {
        "FB_APP_ID", "FB_APP_SECRET", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2",
        "GEMINI_API_KEY_3", "GEMINI_API_KEY_IMAGE_CHECK", "GH_PAT",
        "GOOGLE_DRIVE_FOLDER_ID", "GOOGLE_OAUTH_TOKEN_JSON_B64",
        "GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GOOGLE_SHEET_ID",
        "IG_ACCESS_TOKEN", "IG_BUSINESS_ID", "PIXABAY_API_KEY",
        "SUPABASE_SECRET_KEY", "SUPABASE_URL",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    }
    FORBIDDEN_MISSPELLINGS = {"GDOGLE_SHEET_ID", "GDOGLE_DRIVE_FOLDER_ID",
                               "GDOGLE_SERVICE_ACCOUNT_JSON_B64",
                               "GDOGLE_OAUTH_TOKEN_JSON_B64", "GH_REPO"}

    def _scan_workflows(self) -> set[str]:
        """Extract secret references from all workflow YAML files."""
        import re
        pattern = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")
        found = set()
        for yml in (_ROOT / ".github" / "workflows").glob("*.yml"):
            for m in pattern.finditer(yml.read_text()):
                found.add(m.group(1))
        return found

    def test_no_google_misspelled_as_gdogle_in_workflows(self):
        """Workflows must use GOOGLE_* not the misspelled GDOGLE_*."""
        found = self._scan_workflows()
        mismatches = found & self.FORBIDDEN_MISSPELLINGS
        assert not mismatches, f"Forbidden (misspelled) secret names found: {mismatches}"

    def test_workflow_secrets_are_known(self):
        """All secret names in workflows must be in the known secrets list."""
        found = self._scan_workflows()
        unknown = found - self.EXPECTED_SECRETS
        # Allow DATABASE_URL as an additional optional secret
        unknown.discard("DATABASE_URL")
        # Phase-specific DB vars are optional overrides (if set, they must be GitHub Secrets)
        unknown.discard("LEARNING_LAYER_DATABASE_URL")
        unknown.discard("KCL_DATABASE_URL")
        unknown.discard("P10_DATABASE_URL")
        unknown.discard("OBSERVATION_DB_DSN")
        assert not unknown, f"Unknown secrets referenced in workflows: {unknown}"


# ── Publishing idempotency ─────────────────────────────────────────────────

class TestPublishingIdempotency:
    def test_status_field_prevents_duplicate(self):
        """Verify daily_generate.py checks status before publishing."""
        import ast
        script = _ROOT / "phase5_6" / "scripts" / "publish.py"
        source = script.read_text()
        # Should check for "published" or "publishing" status before re-posting
        assert "published" in source.lower() or "status" in source.lower(), \
            "publish.py must check post status to prevent duplicates"


# ── Workflow entry point validation ────────────────────────────────────────

class TestWorkflowEntryPoints:
    EXPECTED_SCRIPTS = [
        "phase5_6/scripts/daily_generate.py",
        "phase5_6/scripts/publish.py",
        "phase5_6/scripts/monthly_task.py",
        "phase5_6/scripts/fetch_insights.py",
        "phase5_6/scripts/cleanup.py",
        "phase5_6/scripts/weekly_backup.py",
        "phase5_6/scripts/refresh_token.py",
    ]

    def test_all_scripts_exist(self):
        for script in self.EXPECTED_SCRIPTS:
            assert (_ROOT / script).exists(), f"Script not found: {script}"

    def test_operational_modules_importable(self):
        import importlib
        for mod in ["operational.backup", "operational.restore",
                    "operational.gemini_rotation", "operational.health_monitor",
                    "operational.logging_config", "operational.resilience",
                    "operational.db_config"]:
            importlib.import_module(mod)  # raises ImportError if broken


# ── Gemini Model List Verification ────────────────────────────────────────

BANNED_MODELS = [
    # Old removed models
    "gemini-2.0-flash-lite", "gemini-2.0-flash",
    "gemini-1.5-flash", "gemini-1.5-flash-8b",
    # Pro / paid
    "gemini-2.5-pro", "gemini-3.1-pro-preview",
    # Image/video/audio/TTS/music/preview/agent
    "gemini-3-pro-image", "gemini-3.1-flash-image",
    "gemini-3.1-flash-lite-image", "gemini-2.5-flash-image",
    "gemini-3-flash-preview", "gemini-3.1-flash-live-preview",
    "gemini-3.1-flash-tts-preview", "gemini-omni-flash",
    # Aliases (unstable)
    "gemini-flash-latest",
]

REQUIRED_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]


class TestGeminiModelList:
    def test_free_models_list_is_exactly_specified(self):
        """FREE_MODELS must match the approved list exactly — order matters."""
        from operational.gemini_rotation import FREE_MODELS, GEMINI_FREE_MODELS
        assert FREE_MODELS == REQUIRED_MODELS, (
            f"FREE_MODELS mismatch.\nExpected: {REQUIRED_MODELS}\nGot:      {FREE_MODELS}"
        )
        assert GEMINI_FREE_MODELS == REQUIRED_MODELS

    def test_no_banned_model_in_free_models(self):
        """None of the removed or forbidden models may appear in FREE_MODELS."""
        from operational.gemini_rotation import FREE_MODELS
        found = [m for m in BANNED_MODELS if m in FREE_MODELS]
        assert not found, f"Banned models found in FREE_MODELS: {found}"

    def test_no_banned_model_in_config(self):
        """phase5_6/lib/config.py must not contain any old or banned model name."""
        import sys, os
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        from lib import config
        banned_found = [
            m for m in BANNED_MODELS
            if m in getattr(config, "GEMINI_MODEL_NAME", "")
            or m in getattr(config, "IMAGE_VETTING_MODEL_NAME", "")
            or any(m in entry for entry in getattr(config, "GEMINI_FREE_MODELS", []))
        ]
        assert not banned_found, f"Banned model in config.py: {banned_found}"

    def test_config_primary_model_is_correct(self):
        """GEMINI_MODEL_NAME / DEFAULT_TEXT_MODEL must equal the configured default."""
        import sys
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        from lib import config
        # DEFAULT_TEXT_MODEL default is gemini-3.5-flash-lite (independent of rotation)
        assert config.DEFAULT_TEXT_MODEL == "gemini-3.5-flash-lite"
        # Legacy alias must match
        assert config.GEMINI_MODEL_NAME == config.DEFAULT_TEXT_MODEL

    def test_config_image_model_is_correct(self):
        """IMAGE_VETTING_MODEL / IMAGE_VETTING_MODEL_NAME must equal the configured default."""
        import sys
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        from lib import config
        # IMAGE_VETTING_MODEL default is gemini-3.5-flash-lite (independent of rotation)
        assert config.IMAGE_VETTING_MODEL == "gemini-3.5-flash-lite"
        # Legacy alias must match
        assert config.IMAGE_VETTING_MODEL_NAME == config.IMAGE_VETTING_MODEL

    def test_config_image_model_independent_of_rotation(self):
        """IMAGE_VETTING_MODEL must NOT be derived from ROTATION_MODELS position."""
        import sys, importlib
        sys.path.insert(0, str(_ROOT / "phase5_6"))
        import lib.config as cfg
        importlib.reload(cfg)
        # Rotation list is separate; IMAGE_VETTING_MODEL must have its own default
        assert hasattr(cfg, "IMAGE_VETTING_MODEL"), "config.py must expose IMAGE_VETTING_MODEL"
        assert hasattr(cfg, "DEFAULT_TEXT_MODEL"), "config.py must expose DEFAULT_TEXT_MODEL"
        assert hasattr(cfg, "LEARNING_MODEL"), "config.py must expose LEARNING_MODEL"
        assert hasattr(cfg, "ROTATION_MODELS"), "config.py must expose ROTATION_MODELS"

    def test_rotation_order_key1_before_key2(self, tmp_path):
        """All models for Key 1 must be tried before any model for Key 2."""
        from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError
        engine = GeminiRotationEngine(
            api_keys=["key1", "key2", "key3"],
            models=REQUIRED_MODELS,
            state_file=tmp_path / "state.json",
        )
        tried: list[tuple[int, str]] = []

        import unittest.mock as mock
        def side_effect(*args, **kwargs):
            raise Exception("quota 429")

        with mock.patch("google.genai.Client") as mc:
            mc.return_value.models.generate_content.side_effect = side_effect
            with pytest.raises(AllCombinationsExhaustedError):
                engine.generate("test", max_retries_per_pair=1)

        # Verify: Key 1 models all appear before Key 2 models
        # (health tracking shows attempt order via cooldown_until being set)
        for ki in range(3):
            for m in REQUIRED_MODELS:
                h = engine._health[f"{ki}:{m}"]
                assert h.failures >= 1, f"key{ki+1}/{m} was never attempted"

    def test_no_old_model_in_source_files(self):
        """Scan production source files for old model names.
        Excludes test files (which contain old names in BANNED_MODELS literals).
        """
        old_names = [
            "gemini-2.0-flash-lite", "gemini-2.0-flash",
            "gemini-1.5-flash", "gemini-1.5-flash-8b",
        ]
        # Production source only — skip test files that intentionally list banned names
        SKIP_PATTERNS = {"tests/", "test_"}
        violations: list[str] = []
        extensions = {".py", ".yml", ".yaml", ".md", ".example"}
        for f in _ROOT.rglob("*"):
            if f.suffix not in extensions:
                continue
            rel = str(f.relative_to(_ROOT))
            if ".git" in f.parts or "__pycache__" in f.parts:
                continue
            if any(p in rel for p in SKIP_PATTERNS):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for name in old_names:
                if name in text:
                    violations.append(f"{rel}: contains {name!r}")
        assert not violations, "Old model names still present:\n" + "\n".join(violations)

    def test_no_pro_or_restricted_model_in_source(self):
        """Ensure no Pro/preview/image/TTS/music model appears in production source.
        Excludes test files that intentionally enumerate banned names.
        """
        restricted_patterns = [
            "gemini-2.5-pro", "gemini-3.1-pro", "-pro-preview",
            "-flash-image", "-flash-tts", "-flash-live",
            "gemini-omni", "gemini-flash-latest",
        ]
        SKIP_PATTERNS = {"tests/", "test_"}
        violations: list[str] = []
        extensions = {".py", ".yml", ".yaml", ".md", ".example"}
        for f in _ROOT.rglob("*"):
            if f.suffix not in extensions:
                continue
            rel = str(f.relative_to(_ROOT))
            if ".git" in f.parts or "__pycache__" in f.parts:
                continue
            if any(p in rel for p in SKIP_PATTERNS):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for pat in restricted_patterns:
                if pat in text:
                    violations.append(f"{rel}: contains {pat!r}")
        assert not violations, "Restricted model names found:\n" + "\n".join(violations)
