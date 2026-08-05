"""
EngineBase
==========
Abstract base class for all pipeline engines.

Provides two shared capabilities that would otherwise be copy-pasted into
every engine:

1. heartbeat(status, **kwargs)
   Delegates to EngineHealthService so engines never touch the health
   repository directly.

2. settings: EngineSettingsReader (property)
   Lazy-initialised reader backed by SettingsService.  Engines access
   configuration through typed properties (e.g. self.settings.score_weight_engagement)
   instead of magic strings or hard-coded literals.

Usage
-----
    class MyEngine(EngineBase):
        ENGINE_NAME = "my_engine"

        def __init__(self, event_bus, my_service, health_service=None, settings_service=None):
            super().__init__(health_service=health_service, settings_service=settings_service)
            self.event_bus = event_bus
            self.my_service = my_service

        def handle_something(self, event):
            try:
                threshold = self.settings.hypothesis_min_confidence
                ...
                self.heartbeat("healthy")
            except Exception as e:
                logger.exception(...)
                self.heartbeat("error", error=str(e))
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from engines.shared.settings_reader import EngineSettingsReader

logger = logging.getLogger(__name__)


class EngineBase:
    """
    Base class for pipeline engines.

    Subclasses MUST define:
        ENGINE_NAME: str  — used for heartbeat reporting and log prefixes
    """

    ENGINE_NAME: str = "engine"

    def __init__(
        self,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        self._health_service = health_service
        self._settings_service = settings_service
        self._settings_reader: Optional[EngineSettingsReader] = None

    # ------------------------------------------------------------------ settings
    @property
    def settings(self) -> EngineSettingsReader:
        """Lazy-initialised EngineSettingsReader backed by SettingsService."""
        if self._settings_reader is None:
            svc = self._resolve_settings_service()
            self._settings_reader = EngineSettingsReader(svc)
        return self._settings_reader

    def _resolve_settings_service(self) -> Any:
        if self._settings_service is not None:
            return self._settings_service
        try:
            from database.services.settings_service import settings_service
            return settings_service
        except Exception:
            # Return a no-op stub so defaults in EngineSettingsReader are used
            return _NullSettingsService()

    # ------------------------------------------------------------------ heartbeat
    def heartbeat(self, status: str, **kwargs: Any) -> None:
        """
        Report engine health via EngineHealthService.

        status  — "healthy" | "error" | "warning" | "degraded"
        kwargs  — arbitrary extra fields forwarded to the health service
                  (e.g. error="message text")
        """
        svc = self._resolve_health_service()
        if svc is None:
            return
        try:
            svc.heartbeat(self.ENGINE_NAME, status, **kwargs)
        except Exception:
            logger.exception(
                "[%s] Failed to report heartbeat status=%s", self.ENGINE_NAME, status
            )

    def _resolve_health_service(self) -> Any:
        if self._health_service is not None:
            return self._health_service
        try:
            from database.services.engine_health_service import engine_health_service
            return engine_health_service
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Internal no-op stub (used when settings DB is unavailable, e.g. in tests)
# ---------------------------------------------------------------------------

class _NullSettingsService:
    """Returns None for every key, allowing EngineSettingsReader to use defaults."""

    def get(self, key: str, default: Any = None) -> Any:  # noqa: D401
        return default
