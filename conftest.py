"""
Root pytest conftest.

IMPORT ORDER MATTERS: Phase5/6 must be fully bootstrapped FIRST because it
uses flat namespace imports (`database`, `core`, `engines`) that would be
shadowed by Phase8/9 flat imports if their roots were added to sys.path first.

Phase5/6 importing `core.container` caches all `database.*`, `core.*`, and
`engines.*` modules into sys.modules before Phase8/9 add their directories.
"""
from __future__ import annotations
import os
import sys

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 1. Phase5/6 first: bootstraps database.*, core.*, engines.* into sys.modules
import phase5_6  # noqa: F401 — adds phase5_6/ to sys.path
from core.container import container as _p56_container  # noqa: F401 — triggers full DI bootstrap

# 2. Phase7 — adds phase7_observation/ to sys.path (observation.* namespace)
import phase7_observation  # noqa: F401

# 3. Phase8 and Phase9 add their roots; by now database.* is cached from Phase5/6
import phase8_learning   # noqa: F401
import phase9_coverage   # noqa: F401

# 4. Phase10 uses relative imports, no namespace conflict
import phase10_intelligence  # noqa: F401
