"""
Autonomous AI System — Unified Bootstrap Entry Point.

Import order is critical: Phase5/6 must be fully bootstrapped first
to cache database.*, core.*, engines.* into sys.modules before Phase8/9
add their own roots (which also contain database/ and config/ dirs).
"""
from __future__ import annotations
import logging
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger("autonomous_ai.main")

# ---------------------------------------------------------------------------
# 1. Phase5/6 FIRST — caches database.*, core.*, engines.* into sys.modules
# ---------------------------------------------------------------------------
logger.info("Bootstrapping Phase5/6 (Strategy/Decision/Execution)…")
import phase5_6  # noqa: F401 — adds phase5_6/ to sys.path

from core.container import container as _p56_container  # triggers full DI bootstrap
from core.event_bus import event_bus as _p56_bus

logger.info("Phase5/6 DI container ready (%d bindings).", len(_p56_container._bindings))

# ---------------------------------------------------------------------------
# 2. Phase7 — observation namespace; no database/ conflict
# ---------------------------------------------------------------------------
logger.info("Bootstrapping Phase7 (Observation)…")
import phase7_observation  # noqa: F401

# ---------------------------------------------------------------------------
# 3. Phase8 and Phase9 — their database/ dirs are now shadowed by cached modules
# ---------------------------------------------------------------------------
logger.info("Bootstrapping Phase8 (Learning)…")
import phase8_learning  # noqa: F401

logger.info("Bootstrapping Phase9 (Knowledge Coverage)…")
import phase9_coverage  # noqa: F401

# ---------------------------------------------------------------------------
# 4. Phase10 — uses relative imports; no flat-namespace conflict
# ---------------------------------------------------------------------------
logger.info("Bootstrapping Phase10 (Intelligence Core)…")
import phase10_intelligence  # noqa: F401


# ---------------------------------------------------------------------------
# 5. Ensure shared runtime tables exist
# ---------------------------------------------------------------------------
def _ensure_runtime_schemas():
    """Create missing ORM tables for the in-process pipeline components."""
    from database.client import get_engine
    from database.models import Base as Phase56Base

    Phase56Base.metadata.create_all(get_engine())

    from observation.config import load_settings as load_observation_settings
    from observation.infrastructure.db.connection import DatabaseConnectionFactory
    from observation.infrastructure.orm.models import Base as ObservationBase

    observation_factory = DatabaseConnectionFactory(
        load_observation_settings().database
    )
    try:
        ObservationBase.metadata.create_all(observation_factory.engine())
    finally:
        observation_factory.dispose()


_ensure_runtime_schemas()


# ---------------------------------------------------------------------------
# 6. Build Phase8 container
# ---------------------------------------------------------------------------
def _bootstrap_phase8():
    from infrastructure.container import Container as P8Container
    c = P8Container()
    c.initialize_schema()
    logger.info("Phase8 schema initialised.")
    return c


# ---------------------------------------------------------------------------
# 7. Build Phase9 container
# ---------------------------------------------------------------------------
def _bootstrap_phase9():
    from application.container import build_container
    c = build_container(ensure_schema=True)
    logger.info("Phase9 schema initialised.")
    return c


# ---------------------------------------------------------------------------
# 8. Build Phase10 application
# ---------------------------------------------------------------------------
def _bootstrap_phase10():
    from phase10_intelligence.bootstrap.app import create_application
    app = create_application(create_schema=True)
    logger.info("Phase10 schema initialised.")
    return app


# ---------------------------------------------------------------------------
# 9. Wire remaining inter-phase bridges (Phase7→8, Phase8→9, Phase9→10)
# ---------------------------------------------------------------------------
def _wire_bridges(p8_container, p9_container, p10_app):
    # Phase7 bootstrap (already wired Phase6→Phase7 inside wiring.py)
    try:
        from observation.config import load_settings as _obs_cfg
        from observation.application.bootstrap import ApplicationBootstrap
        p7 = ApplicationBootstrap(_obs_cfg())
        # Phase7 → Phase8
        from bridges.observation_to_learning import wire as wire_obs_learn
        from phase8_learning.main import run as p8_run
        wire_obs_learn(p7.in_process_publisher, p8_run)
        logger.info("Bridge Phase7→Phase8 wired.")
    except Exception:
        logger.warning("Phase7→Phase8 bridge not wired.", exc_info=True)

    # Phase8 → Phase9
    try:
        from bridges.learning_to_coverage import wire as wire_learn_cov
        from application.main import run as p9_run

        def _p9_adapter(event):
            p9_run(event)

        wire_learn_cov(p8_container.publisher, _p9_adapter)
        logger.info("Bridge Phase8→Phase9 wired.")
    except Exception:
        logger.warning("Phase8→Phase9 bridge not wired.", exc_info=True)

    # Phase9 → Phase10
    try:
        from bridges.coverage_to_intelligence import wire as wire_cov_intel
        wire_cov_intel(p9_container.publisher, p10_app.publisher)
        logger.info("Bridge Phase9→Phase10 wired.")
    except Exception:
        logger.warning("Phase9→Phase10 bridge not wired.", exc_info=True)


# ---------------------------------------------------------------------------
# 10. Main bootstrap
# ---------------------------------------------------------------------------
def bootstrap():
    p8 = _bootstrap_phase8()
    p9 = _bootstrap_phase9()
    p10 = _bootstrap_phase10()
    _wire_bridges(p8, p9, p10)

    logger.info("All phases bootstrapped. Autonomous AI system ready.")
    return {
        "phase5_6_event_bus": _p56_bus,
        "phase5_6_container": _p56_container,
        "phase8_container": p8,
        "phase9_container": p9,
        "phase10_app": p10,
    }


if __name__ == "__main__":
    try:
        components = bootstrap()
        print("\nBootstrap complete. Active components:")
        for name in components:
            print(f"  ✓ {name}")
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
