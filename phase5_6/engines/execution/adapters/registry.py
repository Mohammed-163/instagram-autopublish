"""
AdapterRegistry — Phase 6 Part 2 (Adapter Registry).

Single source of truth for platform → adapter mapping.

Responsibility:
  - Register BaseExecutionAdapter subclasses keyed by PLATFORM string.
  - Resolve the correct adapter for a given target_platform.
  - Eliminate scattered if/elif chains from ExecutionOrchestrator.

Architectural rules:
  - Registry holds adapter instances (singletons per platform).
  - No repository access.
  - No knowledge of Decision — only platform string.
  - Registrations are deterministic (dict keyed by PLATFORM constant).

Usage:
    registry = AdapterRegistry()
    registry.register(YouTubeExecutionAdapter())
    registry.register(InstagramExecutionAdapter())

    adapter = registry.resolve("youtube")   # → YouTubeExecutionAdapter
    adapter = registry.resolve("instagram") # → InstagramExecutionAdapter
"""
from __future__ import annotations

import logging
from typing import Dict, List

from engines.execution.adapters.base_adapter import BaseExecutionAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry that maps platform identifiers to adapter instances.

    Replaces ad-hoc if/elif blocks in the Orchestrator with a clean
    lookup so adding a new platform only requires one register() call.
    """

    def __init__(self) -> None:
        # Keyed by PLATFORM string (e.g. "youtube", "instagram").
        # Dict insertion order is preserved (Python 3.7+) — deterministic.
        self._adapters: Dict[str, BaseExecutionAdapter] = {}

    # ------------------------------------------------------------------ registration

    def register(self, adapter: BaseExecutionAdapter) -> None:
        """Register an adapter instance for its declared PLATFORM.

        Raises ValueError if adapter.PLATFORM is empty or already registered.
        """
        platform = adapter.PLATFORM
        if not platform:
            raise ValueError(
                f"Cannot register adapter {adapter!r}: PLATFORM attribute is empty."
            )
        if platform in self._adapters:
            logger.warning(
                "[AdapterRegistry] Replacing existing adapter for platform '%s' with %r.",
                platform,
                adapter,
            )
        self._adapters[platform] = adapter
        logger.debug(
            "[AdapterRegistry] Registered adapter %r for platform '%s'.",
            adapter,
            platform,
        )

    # ------------------------------------------------------------------ resolution

    def resolve(self, target_platform: str) -> BaseExecutionAdapter:
        """Return the adapter registered for *target_platform*.

        Raises KeyError if no adapter is registered for the given platform,
        so callers get an explicit error instead of a silent None.
        """
        adapter = self._adapters.get(target_platform)
        if adapter is None:
            registered = sorted(self._adapters.keys())  # deterministic sort for error message
            raise KeyError(
                f"No adapter registered for platform '{target_platform}'. "
                f"Registered platforms: {registered}"
            )
        return adapter

    # ------------------------------------------------------------------ introspection

    def registered_platforms(self) -> List[str]:
        """Return a sorted, deterministic list of registered platform names."""
        return sorted(self._adapters.keys())

    def has_platform(self, target_platform: str) -> bool:
        """Return True if an adapter is registered for *target_platform*."""
        return target_platform in self._adapters

    def __repr__(self) -> str:
        return f"AdapterRegistry(platforms={self.registered_platforms()})"


# ---------------------------------------------------------------------------
# Default registry — pre-loaded with all built-in platform adapters.
# Consumed by container.py / ExecutionOrchestrator.
# ---------------------------------------------------------------------------

def build_default_registry() -> AdapterRegistry:
    """Build and return an AdapterRegistry with all built-in adapters registered.

    Order of registration is alphabetical (deterministic).
    """
    from engines.execution.adapters.instagram_adapter import InstagramExecutionAdapter
    from engines.execution.adapters.youtube_adapter import YouTubeExecutionAdapter

    registry = AdapterRegistry()
    # Alphabetical order — deterministic, no priority implied
    registry.register(InstagramExecutionAdapter())
    registry.register(YouTubeExecutionAdapter())
    return registry


# Module-level singleton consumed by container.py
adapter_registry = build_default_registry()
