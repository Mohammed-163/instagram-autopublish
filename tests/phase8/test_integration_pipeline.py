"""
Integration test: LearningEngine -> LearningService -> KnowledgeRepository.

This is intentionally a single, focused test (not a suite) that exercises
the real pipeline end to end against an in-memory SQLite database. It
verifies existing behavior only — it does not introduce new functionality.

Requires: sqlalchemy (see requirements.txt). Run with:

    pytest tests/test_integration_pipeline.py

or directly:

    python -m tests.test_integration_pipeline
"""

from __future__ import annotations

from phase8_learning.config.settings import Settings
from phase8_learning.database.connection import DatabaseConnectionFactory, UnitOfWork
from phase8_learning.domain.enums import KnowledgeStatus
from phase8_learning.engine.learning_engine import LearningEngine, LearningEngineConfig
from phase8_learning.events.events import ObservationRecorded
from phase8_learning.events.publisher import InProcessEventPublisher
from phase8_learning.repository.knowledge_repository import KnowledgeRepository
from phase8_learning.service.learning_service import LearningService, LearningServiceConfig


def _in_memory_settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        fingerprint_version="1.0.0",
        engine_version="1.0.0",
        schema_version="1.0.0",
        min_confidence_threshold=0.5,
        min_sample_size=2,
        min_consistency_threshold=0.5,
    )


def _observations() -> list[ObservationRecorded]:
    return [
        ObservationRecorded(
            observation_id="obs-0001",
            subject_id="subject-a",
            metric_name="engagement_rate",
            metric_value=0.42,
            context={"channel": "primary"},
        ),
        ObservationRecorded(
            observation_id="obs-0002",
            subject_id="subject-a",
            metric_name="engagement_rate",
            metric_value=0.44,
            context={"channel": "primary"},
        ),
        ObservationRecorded(
            observation_id="obs-0003",
            subject_id="subject-a",
            metric_name="engagement_rate",
            metric_value=0.41,
            context={"channel": "primary"},
        ),
    ]


def test_engine_service_repository_pipeline_is_deterministic() -> None:
    settings = _in_memory_settings()
    connection_factory = DatabaseConnectionFactory(settings)
    connection_factory.create_all()

    publisher = InProcessEventPublisher()
    engine = LearningEngine(
        LearningEngineConfig(
            engine_version=settings.engine_version,
            fingerprint_version=settings.fingerprint_version,
            schema_version=settings.schema_version,
            min_sample_size=settings.min_sample_size,
            min_consistency_threshold=settings.min_consistency_threshold,
        )
    )

    observations = _observations()
    candidates = engine.process(observations)
    assert len(candidates) == 1

    with UnitOfWork(connection_factory) as uow:
        repository = KnowledgeRepository(uow.session)
        service = LearningService(
            repository=repository,
            publisher=publisher,
            config=LearningServiceConfig(
                fingerprint_version=settings.fingerprint_version,
                engine_version=settings.engine_version,
                schema_version=settings.schema_version,
                min_confidence_threshold=settings.min_confidence_threshold,
            ),
        )
        stored = service.process_candidates(list(candidates))
        assert len(stored) == 1

        knowledge = stored[0]
        assert knowledge.status == KnowledgeStatus.ACTIVE
        assert knowledge.version.knowledge_version == 1
        assert len(knowledge.fingerprint.fingerprint_hash) == 64

        fetched = repository.get(knowledge.knowledge_id)
        assert fetched is not None
        assert fetched.fingerprint.fingerprint_hash == knowledge.fingerprint.fingerprint_hash

        by_fingerprint = repository.find_by_fingerprint(knowledge.fingerprint.fingerprint_hash)
        assert len(by_fingerprint) == 1

        active = repository.find_active()
        assert any(k.knowledge_id == knowledge.knowledge_id for k in active)

    # Re-running the exact same observations again must not create a
    # duplicate knowledge row (fingerprint + evidence set are identical).
    with UnitOfWork(connection_factory) as uow:
        repository = KnowledgeRepository(uow.session)
        service = LearningService(
            repository=repository,
            publisher=publisher,
            config=LearningServiceConfig(
                fingerprint_version=settings.fingerprint_version,
                engine_version=settings.engine_version,
                schema_version=settings.schema_version,
                min_confidence_threshold=settings.min_confidence_threshold,
            ),
        )
        candidates_again = engine.process(_observations())
        stored_again = service.process_candidates(list(candidates_again))
        assert len(stored_again) == 1
        assert stored_again[0].knowledge_id == knowledge.knowledge_id
        assert stored_again[0].version.knowledge_version == 1

    print("Integration pipeline test passed.")


if __name__ == "__main__":
    test_engine_service_repository_pipeline_is_deterministic()
