"""
Phase 7 — Observation Layer.

Internal imports use `from observation.X import Y` style.
This __init__ adds the phase7_observation directory to sys.path
so the `observation` sub-package is importable by that flat name.

Entry point: observation.application.bootstrap.ApplicationBootstrap
"""
from __future__ import annotations
import os
import sys

_phase7_root = os.path.dirname(os.path.abspath(__file__))
if _phase7_root not in sys.path:
    sys.path.insert(0, _phase7_root)
