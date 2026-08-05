"""
tests/services/conftest.py
==========================
Isolates unit tests from the full application container bootstrap.

Problem
-------
`database/services/__init__.py` eagerly imports *every* service singleton.
Several of those singletons (e.g. OpportunityScoringService) call
`container.resolve(...)` at module-load time, which requires a live
database + settings context that is not available in a plain unit-test run.

Fix
---
Before any test module in this directory is collected, we inject two
lightweight stubs into `sys.modules`:

1. `database.services`  — a bare package stub with no eager imports.
   Python then lets individual submodule imports (e.g.
   `from database.services.decision_scoring_service import ...`) load
   only the specific .py file they need.

2. `core.container`     — a stub that exposes a do-nothing Container
   object, satisfying the `from core.container import container` lines
   inside service modules without triggering `_build_default_container`.
"""
from __future__ import annotations

import sys
import types


# ------------------------------------------------------------------ core.container stub
class _StubContainer:
    """Minimal container that satisfies lazy-resolution patterns in services.
    Any eagerly resolved dependency will raise KeyError (same as the real
    container would if the dependency were missing).
    """
    def resolve(self, name: str):
        raise KeyError(f"[test stub] No binding for '{name}' — inject via constructor.")

    def register(self, name: str, value) -> None:
        pass


def _stub_core_container() -> None:
    if "core.container" not in sys.modules:
        mod = types.ModuleType("core.container")
        mod.container = _StubContainer()
        sys.modules["core.container"] = mod


# ------------------------------------------------------------------ database.services package stub
def _stub_database_services_package() -> None:
    """Replace the package __init__ with an empty stub so that submodule
    imports (database.services.X) load only that submodule's .py file,
    skipping the eager all-services import chain in __init__.py.
    """
    if "database.services" not in sys.modules:
        pkg = types.ModuleType("database.services")
        pkg.__path__ = ["database/services"]
        pkg.__package__ = "database.services"
        sys.modules["database.services"] = pkg


# Apply stubs immediately at conftest-collection time.
_stub_core_container()
_stub_database_services_package()
