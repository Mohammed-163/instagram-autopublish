"""
Dependency injection container.

Wires:

    Repository
        v
    Service
        v
    Engine

The container owns the DatabaseConnectionFactory and EventPublisher, and
exposes factory methods that build a fully wired LearningEngine +
LearningService pair, scoped to a single UnitOfWork/session.
"""

from __future__ import annotations

from dataclasses import dataclass

from phase8_learning.config.settings import Settings
from phase8_learning.database.connection import DatabaseConnectionFactory, UnitOfWork
from phase8_learning.engine.learning_engine import LearningEngine, LearningEngineConfig
from phase8_learning.events.publisher import EventPublisher, InProcessEventPublisher
from phase8_learning.repository.knowledge_repository import KnowledgeRepository
from phase8_learning.service.learning_service import LearningService, LearningServiceConfig


@dataclass
class WiredLearningStack:
    unit_of_work: UnitOfWork
    repository: KnowledgeRepository
    service: LearningService
    engine: LearningEngine


class Container:
    """
    Application composition root for the Learning Layer.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.connection_factory = DatabaseConnectionFactory(self.settings)
        self.publisher: EventPublisher = InProcessEventPublisher()

    def initialize_schema(self) -> None:
        """Create tables for local/dev usage. Production deployments should
        apply migrations/ instead."""
        self.connection_factory.create_all()

    def build_stack(self) -> WiredLearningStack:
        """
        Build a fully wired Repository -> Service -> Engine stack, scoped
        to a fresh UnitOfWork. The caller is responsible for entering and
        exiting the returned UnitOfWork as a context manager.
        """
        unit_of_work = UnitOfWork(self.connection_factory)
        unit_of_work.__enter__()
        assert unit_of_work.session is not None

        repository = KnowledgeRepository(unit_of_work.session)

        service = LearningService(
            repository=repository,
            publisher=self.publisher,
            config=LearningServiceConfig(
                fingerprint_version=self.settings.fingerprint_version,
                engine_version=self.settings.engine_version,
                schema_version=self.settings.schema_version,
                min_confidence_threshold=self.settings.min_confidence_threshold,
            ),
        )

        engine = LearningEngine(
            config=LearningEngineConfig(
                engine_version=self.settings.engine_version,
                fingerprint_version=self.settings.fingerprint_version,
                schema_version=self.settings.schema_version,
                min_sample_size=self.settings.min_sample_size,
                min_consistency_threshold=self.settings.min_consistency_threshold,
            ),
        )

        return WiredLearningStack(
            unit_of_work=unit_of_work,
            repository=repository,
            service=service,
            engine=engine,
        )
