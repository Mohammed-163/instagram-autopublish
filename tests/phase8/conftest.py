"""conftest for Phase8 tests."""
from __future__ import annotations
import os, sys

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _project_root)

import phase5_6
from core.container import container as _c
import phase8_learning
