from __future__ import annotations

from phase9_coverage.application.container import Container
from phase9_coverage.events.publisher import InMemoryEventPublisher
from phase9_coverage.events.events import CoverageGapDetected, CoverageUpdated, KnowledgeCoverageCalculated
from tests.phase9.factories import make_knowledge_validated


def test_engine_calculates_coverage_and_persists(container: Container):
    knowledge = make_knowledge_validated()

    calculated_event = container.engine.handle(knowledge)

    assert isinstance(calculated_event, KnowledgeCoverageCalculated)
    assert calculated_event.coverage.knowledge_id == knowledge.knowledge_id
    assert 0.0 <= calculated_event.coverage.coverage_score <= 1.0

    persisted = container.repository.get_by_id(calculated_event.coverage.coverage_id)
    assert persisted is not None
    assert persisted.coverage_id == calculated_event.coverage.coverage_id


def test_deduplication_returns_existing_coverage_for_identical_input(container: Container):
    knowledge = make_knowledge_validated()

    first = container.engine.handle(knowledge)
    second = container.engine.handle(knowledge)

    assert first.coverage.coverage_id == second.coverage.coverage_id
    assert first.coverage.fingerprint_hash == second.coverage.fingerprint_hash

    all_rows = container.repository.list_by_knowledge_id(knowledge.knowledge_id)
    assert len(all_rows) == 1


def test_coverage_calculation_produces_all_eight_dimensions(container: Container):
    knowledge = make_knowledge_validated()

    result = container.engine.handle(knowledge)

    dimension_names = {d.name.value for d in result.coverage.coverage_dimensions.dimensions}
    assert len(dimension_names) == 8


def test_weak_knowledge_produces_gaps(container: Container):
    weak_knowledge = make_knowledge_validated(
        knowledge_id="weak-knowledge",
        topics=(),
        categories=(),
        evidence_count=0,
        confidence_scores=(0.1,),
        freshness_timestamps=(),
        relationships=(),
    )

    result = container.engine.handle(weak_knowledge)

    assert not result.coverage.detected_gaps.is_empty()
    gap_types = {g.gap_type.value for g in result.coverage.detected_gaps.gaps}
    assert "missing_topic" in gap_types
    assert "weak_evidence" in gap_types
    assert "low_confidence" in gap_types


def test_new_version_triggers_coverage_updated_event(container: Container):
    publisher: InMemoryEventPublisher = container.publisher  # type: ignore[assignment]

    knowledge_v1 = make_knowledge_validated(
        knowledge_id="evolving-knowledge", knowledge_versions=("v1",), evidence_count=2
    )
    knowledge_v2 = make_knowledge_validated(
        knowledge_id="evolving-knowledge", knowledge_versions=("v2",), evidence_count=8
    )

    container.engine.handle(knowledge_v1)
    container.engine.handle(knowledge_v2)

    updated_events = [e for e in publisher.published_events if isinstance(e, CoverageUpdated)]
    assert len(updated_events) == 1
    assert updated_events[0].knowledge_id == "evolving-knowledge"


def test_events_are_published_for_calculation_and_gaps(container: Container):
    publisher: InMemoryEventPublisher = container.publisher  # type: ignore[assignment]

    knowledge = make_knowledge_validated(knowledge_id="gappy-knowledge", topics=())
    container.engine.handle(knowledge)

    calculated = [e for e in publisher.published_events if isinstance(e, KnowledgeCoverageCalculated)]
    gap_detected = [e for e in publisher.published_events if isinstance(e, CoverageGapDetected)]

    assert len(calculated) == 1
    assert len(gap_detected) == 1
    assert gap_detected[0].knowledge_id == "gappy-knowledge"


def test_repository_holds_no_business_logic_transition_history(container: Container):
    knowledge_v1 = make_knowledge_validated(
        knowledge_id="tracked-knowledge", knowledge_versions=("v1",), evidence_count=1
    )
    knowledge_v2 = make_knowledge_validated(
        knowledge_id="tracked-knowledge", knowledge_versions=("v2",), evidence_count=9
    )

    container.engine.handle(knowledge_v1)
    container.engine.handle(knowledge_v2)

    transitions = container.repository.list_transitions("tracked-knowledge")
    assert len(transitions) == 2
    assert transitions[0].previous_coverage_id is None
    assert transitions[1].previous_coverage_id is not None
