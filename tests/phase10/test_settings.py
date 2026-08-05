"""Settings environment-override tests."""
import os

from phase10_intelligence.config.settings import Settings


def test_default_settings_load():
    s = Settings()
    assert s.opportunity_min_score == 0.50


def test_env_override(monkeypatch):
    monkeypatch.setenv("P10_OPPORTUNITY_MIN_SCORE", "0.9")
    s = Settings()
    assert s.opportunity_min_score == 0.9
