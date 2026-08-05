"""
Phase 9 — Knowledge Coverage Intelligence Layer.

Internal imports within this sub-package use flat-style paths
(e.g. `from config.settings import Settings`). This __init__ adds
the package root to sys.path so those imports resolve correctly
in an integrated deployment.
"""
from __future__ import annotations

import os
import sys

_phase9_root = os.path.dirname(os.path.abspath(__file__))
if _phase9_root not in sys.path:
    sys.path.insert(0, _phase9_root)
