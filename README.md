# Autonomous AI System

A production-ready, event-driven autonomous AI system composed of 10
interdependent phases, fully integrated into one repository.

---

## Architecture

```
Phase 5/6  Strategy Planning, Decision & Execution
    │  DecisionCandidateApproved → ExecutionCompleted
    ▼
Phase 7    Observation Layer
    │  ObservationRecorded
    ▼
Phase 8    Learning Layer
    │  KnowledgeValidated
    ▼
Phase 9    Knowledge Coverage Intelligence Layer
    │  KnowledgeCoverageCalculated
    ▼
Phase 10   Intelligence Core
    │  RuleEvolved / StrategyEvolved / ConfidenceCalibrated (feedback)
    ▼
Phase 5/6  (feedback loop — closes the autonomous cycle)
```

Each phase is an independent Python package. Phases communicate exclusively
through events via the shared event bus or cross-phase bridges. No phase
imports another phase's implementation directly.

---

## Repository Layout

```
autonomous_ai/
├── shared/                    # Shared infrastructure
│   ├── event_bus.py           # Unified inter-phase event bus
│   └── fingerprint.py         # Canonical SHA-256 fingerprint
├── bridges/                   # Cross-phase event translators (no business logic)
│   ├── execution_to_observation.py
│   ├── observation_to_learning.py
│   ├── learning_to_coverage.py
│   ├── coverage_to_intelligence.py
│   └── intelligence_to_strategy.py
├── phase5_6/                  # Phase 5 (Strategy/Decision) + Phase 6 (Execution)
│   ├── core/                  # EventBus, DI container, DomainEvents, wiring
│   ├── database/              # Models, repositories, services, SQL migrations
│   └── engines/               # All Phase 5/6 engines
├── phase7_observation/        # Phase 7 — Observation Layer
│   └── observation/           # Bounded context (DDD layered architecture)
├── phase8_learning/           # Phase 8 — Learning Layer
│   ├── domain/                # Knowledge domain models and fingerprinting
│   ├── engine/                # LearningEngine
│   ├── service/               # LearningService
│   └── repository/            # KnowledgeRepository
├── phase9_coverage/           # Phase 9 — Knowledge Coverage Intelligence
│   ├── domain/                # Coverage models, gap detection, fingerprinting
│   ├── engine/                # KnowledgeCoverageEngine
│   ├── service/               # KnowledgeCoverageService
│   └── repository/            # KnowledgeCoverageRepository
├── phase10_intelligence/      # Phase 10 — Intelligence Core
│   └── phase10_intelligence_core/  # Full DI, all engines and services
├── migrations/
│   ├── sql/                   # Phase 5/6 SQL migrations (0001–0013, Supabase)
│   ├── phase7/                # Phase 7 Alembic migration chain
│   ├── phase8/                # Phase 8 Alembic migration chain
│   ├── phase9/                # Phase 9 Alembic migration chain
│   └── phase10/               # Phase 10 Alembic migration chain
├── tests/                     # Per-phase test directories
├── main.py                    # Single bootstrap entry point
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set SUPABASE_URL, SUPABASE_SECRET_KEY,
# and each phase's DATABASE_URL
```

### 3. Run database migrations

**Phase 5/6 (SQL, applied to Supabase/Postgres):**
```bash
cd phase5_6
python -m database.migrate
```

**Phase 7 (Alembic):**
```bash
alembic -c migrations/phase7/alembic.ini upgrade head
```

**Phase 8 (Alembic):**
```bash
alembic -c migrations/phase8/alembic.ini upgrade head
```

**Phase 9 (Alembic):**
```bash
alembic -c migrations/phase9/alembic.ini upgrade head
```

**Phase 10 (Alembic):**
```bash
alembic -c migrations/phase10/alembic.ini upgrade head
```

### 4. Bootstrap the system

```bash
python main.py
```

---

## Running Tests

```bash
# All tests
pytest

# Per-phase
pytest phase5_6/tests/
pytest tests/phase8/
pytest tests/phase9/
pytest tests/phase10/
```

---

## Database Topology

Each phase uses its own `DATABASE_URL` environment variable. You can:

- **Single database** (recommended): point all `*_DATABASE_URL` variables at
  the same Postgres instance. Table names do not collide across phases.
- **Isolated databases**: give each phase its own database. Each Alembic
  migration chain is self-contained.

Phase 5/6 uses Supabase-managed Postgres (SQL migrations applied via
`database.migrate`). Phases 7–10 use SQLAlchemy + Alembic.

---

## Event Flow Details

| From | Event | To |
|------|-------|----|
| Phase 5 Wiring | `KnowledgeUpdated` | Phase 5/6 internal engines |
| Phase 6 Execution Engine | `ExecutionCompleted` | `bridges/execution_to_observation` → Phase 7 |
| Phase 7 Observation | `ObservationRecorded` | `bridges/observation_to_learning` → Phase 8 |
| Phase 8 Learning | `KnowledgeValidated` | `bridges/learning_to_coverage` → Phase 9 |
| Phase 9 Coverage | `KnowledgeCoverageCalculated` | `bridges/coverage_to_intelligence` → Phase 10 |
| Phase 10 Intelligence | `RuleEvolved` / `StrategyEvolved` | `bridges/intelligence_to_strategy` → Phase 5/6 |

Bridges are thin translators with no business logic. Each maps between
the two adjacent phases' event shapes and handles structural mismatches
(e.g. Phase 7's `ObservationRecorded` has different fields than Phase 8's
expected shape — the bridge normalises them).

---

## Dependency Rules (enforced by convention)

- **Engines** orchestrate → delegate to **Services** only
- **Services** own business rules → delegate to **Repositories** only
- **Repositories** access data → no business logic
- Higher phases never import lower phase implementation details
- Cross-phase calls go only through events / bridges

---

## Adding a New Phase

1. Create `phase_N/` with its own `__init__.py` that adds itself to `sys.path`
2. Add a bridge in `bridges/` connecting the preceding phase's output event
3. Import `phase_N` in `main.py` and call its bootstrap function
4. Add its Alembic chain under `migrations/phase_N/`

---

## Production TODOs

- [ ] Wire Phase 8 knowledge-lookup in `bridges/learning_to_coverage.py` for
      richer Phase 9 input (currently passes minimal data)
- [ ] Replace in-process bridges with async message broker (Kafka/RabbitMQ)
      when horizontal scaling is required
- [ ] Add health-check endpoint that verifies each phase's DB connectivity
- [ ] Configure external secrets manager instead of `.env` for production
- [ ] Add Prometheus metrics instrumentation to each engine

---

## Gemini Rotation Engine

### Overview

The `operational/gemini_rotation.py` module provides a health-aware,
configurable rotation engine for the Google Gemini API.  It manages multiple
API keys and models simultaneously, always selecting the (key, model) pair
with the best health score.

### Approved Model List (free tier only)

Only the following stable identifiers may be used — no aliases (`latest`,
`preview`, `experimental`), no Pro models, no image/video/audio/TTS/music
models:

| Model | Notes |
|-------|-------|
| `gemini-3.1-flash-lite` | Fastest, highest free quota |
| `gemini-3.5-flash-lite` | Fast general purpose |
| `gemini-3.5-flash`      | Standard |
| `gemini-3.6-flash`      | Extended capability |

### Model Configuration — Four Independent Variables

There are **four independent model variables**.  They are **never derived from
each other**.  Changing `ROTATION_MODELS` does **not** affect
`DEFAULT_TEXT_MODEL`, `IMAGE_VETTING_MODEL`, or `LEARNING_MODEL`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEFAULT_TEXT_MODEL` | `gemini-3.5-flash-lite` | All general text generation tasks |
| `IMAGE_VETTING_MODEL` | `gemini-3.5-flash-lite` | Image selection / moderation only |
| `LEARNING_MODEL` | `gemini-3.5-flash` | Learning-layer / analysis tasks |
| `ROTATION_MODELS` | `gemini-3.1-flash-lite,...` | **Rotation engine tiebreaker order only** |

```bash
# .env — all four may be set independently
DEFAULT_TEXT_MODEL=gemini-3.5-flash-lite
IMAGE_VETTING_MODEL=gemini-3.5-flash-lite
LEARNING_MODEL=gemini-3.5-flash
ROTATION_MODELS=gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.5-flash,gemini-3.6-flash
```

#### `ROTATION_MODELS` controls the rotation engine only

`ROTATION_MODELS` (legacy alias: `GEMINI_MODEL_ROTATION`) defines the
**tiebreaker order** used by the health-aware rotation engine when two
candidate pairs have exactly the same health score.

> **Key invariant**: changing `ROTATION_MODELS` **must never** change which
> model is used for text generation, image vetting, or learning tasks.
> Those three are controlled by their own independent env vars.

### Health-Aware Selection Algorithm

On each generation attempt the engine:

1. Collects all `(key_index, model)` pairs.
2. Excludes pairs whose key has an active `auth` error (disabled 24 h).
3. Excludes pairs still within their `retry_after` cooldown window.
4. Excludes pairs already exhausted for this call.
5. **Ranks** the remaining candidates by `priority_score()`.
6. **Selects** the highest-scoring pair — ties broken by `ROTATION_MODELS` order
   then key index (fully deterministic, no randomness).
7. Calls the API.  On success: returns.  On failure: updates health and
   repeats from step 1.

#### Selection order (health always dominates)

1. Healthy state (`health_state == HEALTHY`)
2. Cooldown state (pairs in cooldown are excluded entirely)
3. Authentication state (auth-failed keys excluded for 24 h)
4. Consecutive failures (fewer = higher score)
5. Success history (more = higher score)
6. Retry eligibility (not yet exhausted this call)

`ROTATION_MODELS` position is used **only as a tiebreaker** when two candidates
have exactly the same health score.  It is mathematically impossible for list
position to outweigh any runtime health signal.

Priority score formula (higher = better):

```
score = 1000
      - 50     × consecutive_failures        (health signal — large weight)
      + 5      × min(successes, 20)          (health signal — large weight)
      - 0.001  × model_position_in_rotation  (tiebreaker — tiny weight)
      - 0.0005 × key_index                  (tiebreaker — tiny weight)
```

The tiebreaker weights (`0.001` / `0.0005`) are deliberately smaller than the
smallest health delta (`5.0` per success point), so **any** runtime health
difference — even a single recorded success — overrides list position.

### Error Classification

| Error type | Effect |
|------------|--------|
| `auth` | Key disabled for 24 h; all models on that key excluded |
| `quota` | (key, model) pair cooled down with exponential back-off |
| `unavailable` | (key, model) pair cooled down with exponential back-off |
| `safety` | Propagated to caller immediately; **never retried** |
| `permanent` | Propagated to caller immediately; **never retried** |
| `unknown` | Treated as `unavailable` |

### Runtime Health State per Pair

Each `(key, model)` pair tracks:

- `health_state` — `healthy` / `cooling_down` / `quota_exceeded` / `authentication_failed`
- `consecutive_failures` — reset to 0 on success
- `last_failure_at` / `last_success_at` — ISO-8601 timestamps
- `retry_after` — ISO-8601 timestamp; pair unavailable until this time
- `error_type` — category of last failure
- `priority_score` — computed from the fields above (not stored)

State is persisted to `gemini_rotation_state.json` and survives across
GitHub Actions runs.

### All Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY_1` | — | Primary rotation key |
| `GEMINI_API_KEY_2` | — | Secondary rotation key |
| `GEMINI_API_KEY_3` | — | Tertiary rotation key |
| `GEMINI_API_KEY_IMAGE_CHECK` | — | Dedicated key for image vetting (never competes with text quota) |
| `DEFAULT_TEXT_MODEL` | `gemini-3.5-flash-lite` | Model for all text generation tasks |
| `IMAGE_VETTING_MODEL` | `gemini-3.5-flash-lite` | Model for image selection / moderation |
| `LEARNING_MODEL` | `gemini-3.5-flash` | Model for learning-layer tasks |
| `ROTATION_MODELS` | `gemini-3.1-flash-lite,...` | Rotation engine tiebreaker order **only** |
| `GEMINI_MODEL_ROTATION` | *(alias for `ROTATION_MODELS`)* | Legacy alias — accepted for backwards compat |
| `GEMINI_STATE_FILE` | `./gemini_rotation_state.json` | Path to persistent rotation state |
