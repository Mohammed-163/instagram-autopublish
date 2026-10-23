"""Manual end-to-end test for the Phase 6 -> Phase 7 -> Phase 8 pipeline."""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_METRICS = ("reach", "saved", "likes", "comments", "shares")


def main() -> int:
    print("[1/5] Importing main bootstrap and building Phase 5/6, 7, and 8...")
    import main as unified_main

    print("    Initialising Phase 5/6 event-log schema...")
    from database.client import get_engine
    from database.models.event_log import EventLog

    EventLog.__table__.create(get_engine(), checkfirst=True)

    print("    Initialising Phase 7 observation schema...")
    from observation.config import load_settings as load_observation_settings
    from observation.infrastructure.db.connection import DatabaseConnectionFactory
    from observation.infrastructure.orm.models import Base as ObservationBase

    observation_factory = DatabaseConnectionFactory(
        load_observation_settings().database
    )
    try:
        ObservationBase.metadata.tables["observations"].create(
            observation_factory.engine(), checkfirst=True
        )
    finally:
        observation_factory.dispose()

    p8_container = unified_main._bootstrap_phase8()
    p9_container = unified_main._bootstrap_phase9()
    p10_app = unified_main._bootstrap_phase10()

    print("[2/5] Temporarily wrapping Phase 8 run to capture translated metrics...")
    import phase8_learning.main as phase8_main

    original_p8_run = phase8_main.run
    captured_events = []
    p8_results = []

    def capturing_p8_run(observations, settings=None):
        batch = list(observations)
        captured_events.extend(batch)
        print(
            "    Phase 8 received "
            f"{len(batch)} event(s): "
            f"{[getattr(item, 'metric_name', None) for item in batch]}"
        )
        result = original_p8_run(batch, settings=settings)
        p8_results.extend(result)
        return result

    phase8_main.run = capturing_p8_run
    unified_main._wire_bridges(p8_container, p9_container, p10_app)

    from phase9_coverage.events.events import KnowledgeCoverageCalculated
    p9_container.publisher.subscribe(
        lambda event: print(
            "[EVENT-TRACE] Phase 9 received and published KnowledgeCoverageCalculated"
        ) if isinstance(event, KnowledgeCoverageCalculated) else None
    )
    p10_app.publisher.subscribe(
        "opportunity.discovered",
        lambda event: print("[EVENT-TRACE] Phase 10 received coverage update"),
    )

    print("    Injecting two synthetic Phase 8 observations for test-topic...")
    from phase8_learning.events.events import ObservationRecorded

    mock_results = capturing_p8_run([
        ObservationRecorded(
            observation_id="test-obs-1",
            subject_id="test-topic",
            metric_name="likes",
            metric_value=120.0,
            context={"media_id": "test-media", "topic_slug": "test-topic"},
        ),
        ObservationRecorded(
            observation_id="test-obs-2",
            subject_id="test-topic",
            metric_name="likes",
            metric_value=135.0,
            context={"media_id": "test-media", "topic_slug": "test-topic"},
        ),
    ])
    if mock_results:
        from phase8_learning.events.events import KnowledgeValidated
        for knowledge in mock_results:
            print("[EVENT-TRACE] Phase 8 published KnowledgeValidated")
            p8_container.publisher.publish(KnowledgeValidated(
                knowledge_id=knowledge.knowledge_id,
                fingerprint_hash=knowledge.fingerprint.fingerprint_hash,
            ))
    print(f"    Mock Phase 8 knowledge result count: {len(mock_results)}")
    mock_candidate_created = len(mock_results) > 0
    # The mock observations intentionally contain the same metric twice. Do
    # not let those deliberate inputs affect the real Phase 6→7→8 assertion.
    captured_events.clear()

    print("[3/5] Creating synthetic Phase 6 ExecutionCompleted event...")
    from core.events import ExecutionCompleted
    from core.event_bus import event_bus

    execution_id = uuid.uuid4()
    event = ExecutionCompleted(
        execution_id=execution_id,
        decision_candidate_id=None,
        execution_type="test_manual_pipeline",
        result={
            "reach": 1234,
            "saved": 87,
            "likes": 210,
            "comments": 15,
            "shares": 4,
            "topic_slug": "test-topic",
            "hook_line": "هل تعلم أن هذا اختبار؟",
        },
    )

    print(f"    Publishing execution_id={execution_id} through Phase 6 event bus...")
    event_bus.publish(event)
    time.sleep(0.1)
    phase8_main.run = original_p8_run

    print("[4/5] Verifying Phase 7 and Phase 8 results...")
    observation_ids = sorted(
        {str(getattr(item, "observation_id", "")) for item in captured_events}
    )
    metric_names = [getattr(item, "metric_name", "") for item in captured_events]
    real_metrics = [name for name in metric_names if name in EXPECTED_METRICS]
    fallback_detected = "observation_recorded" in metric_names

    print(f"    Phase 7 observation_id(s): {observation_ids or 'none'}")
    print(f"    Phase 8 metric count: {len(captured_events)}")
    print(f"    Phase 8 metric names: {metric_names}")
    print(f"    Phase 8 knowledge result count: {len(p8_results)}")
    print(f"    Synthetic candidate result count: {len(mock_results)}")

    passed = (
        len(observation_ids) == 1
        and len(real_metrics) == 5
        and sorted(real_metrics) == sorted(EXPECTED_METRICS)
        and not fallback_detected
        and mock_candidate_created
        and len(p8_results) > 0
    )

    print("[5/5] Final result...")
    if passed:
        print(f"✅ PIPELINE TEST PASSED: {len(real_metrics)} real metrics processed")
        return 0

    print(
        "❌ PIPELINE TEST FAILED: "
        f"fallback metric detected or invalid results: "
        f"observation_ids={observation_ids}, metrics={metric_names}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
