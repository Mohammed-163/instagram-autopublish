"""
Phase 5 (Strategy Planning & Decision) + Phase 6 (Execution Layer).

These two phases share the same codebase. Phase 6 extends Phase 5's
database, repositories, services, and engines.

Internal imports within this package use flat-style paths
(e.g. `from core.event_bus import event_bus`), which requires this
package root directory to be on sys.path.
"""
from __future__ import annotations

import os
import sys

_phase56_root = os.path.dirname(os.path.abspath(__file__))
if _phase56_root not in sys.path:
    sys.path.insert(0, _phase56_root)
