from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import Experiment, Hypothesis
from database.repositories.base_repository import BaseRepository


class HypothesesRepository(BaseRepository[Hypothesis]):
    model = Hypothesis

    def list_by_status(self, status: str) -> List[Hypothesis]:
        with get_session() as session:
            stmt = select(Hypothesis).where(Hypothesis.status == status)
            return list(session.scalars(stmt).all())


class ExperimentsRepository(BaseRepository[Experiment]):
    model = Experiment

    def list_for_hypothesis(self, hypothesis_id: uuid.UUID) -> List[Experiment]:
        with get_session() as session:
            stmt = select(Experiment).where(Experiment.hypothesis_id == hypothesis_id)
            return list(session.scalars(stmt).all())

    def list_by_status(self, status: str) -> List[Experiment]:
        with get_session() as session:
            stmt = select(Experiment).where(Experiment.status == status)
            return list(session.scalars(stmt).all())


hypotheses_repository = HypothesesRepository()
experiments_repository = ExperimentsRepository()
