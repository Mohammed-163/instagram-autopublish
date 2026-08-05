from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import HookFeatureStatistic, HookFeatureValue, HookStructure
from database.repositories.base_repository import BaseRepository


class HookStructuresRepository(BaseRepository[HookStructure]):
    model = HookStructure

    def list_for_post(self, post_id: uuid.UUID) -> List[HookStructure]:
        with get_session() as session:
            stmt = select(HookStructure).where(HookStructure.post_id == post_id)
            return list(session.scalars(stmt).all())

    def list_for_category(self, category: str, limit: int = 200) -> List[HookStructure]:
        with get_session() as session:
            stmt = (
                select(HookStructure)
                .where(HookStructure.category == category)
                .order_by(HookStructure.created_at.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def list_all(self, limit: int = 200) -> List[HookStructure]:
        with get_session() as session:
            stmt = select(HookStructure).order_by(HookStructure.created_at.desc()).limit(limit)
            return list(session.scalars(stmt).all())


class HookFeatureValuesRepository(BaseRepository[HookFeatureValue]):
    model = HookFeatureValue

    def list_for_structure(self, hook_structure_id: uuid.UUID) -> List[HookFeatureValue]:
        with get_session() as session:
            stmt = select(HookFeatureValue).where(HookFeatureValue.hook_structure_id == hook_structure_id)
            return list(session.scalars(stmt).all())

    def list_for_feature(self, feature_name: str, limit: int = 500) -> List[HookFeatureValue]:
        with get_session() as session:
            stmt = (
                select(HookFeatureValue)
                .where(HookFeatureValue.feature_name == feature_name)
                .order_by(HookFeatureValue.created_at.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())


class HookFeatureStatisticsRepository(BaseRepository[HookFeatureStatistic]):
    model = HookFeatureStatistic

    def get_by_category_hook_type_feature(
        self, category: str, hook_type: str, feature_name: str
    ) -> Optional[HookFeatureStatistic]:
        with get_session() as session:
            stmt = select(HookFeatureStatistic).where(
                HookFeatureStatistic.category == category,
                HookFeatureStatistic.hook_type == hook_type,
                HookFeatureStatistic.feature_name == feature_name,
            )
            return session.scalars(stmt).first()

    def list_for_category(self, category: str) -> List[HookFeatureStatistic]:
        with get_session() as session:
            stmt = select(HookFeatureStatistic).where(HookFeatureStatistic.category == category)
            return list(session.scalars(stmt).all())

    def list_low_confidence(self, threshold: float) -> List[HookFeatureStatistic]:
        with get_session() as session:
            stmt = select(HookFeatureStatistic).where(HookFeatureStatistic.confidence < threshold)
            return list(session.scalars(stmt).all())


hook_structures_repository = HookStructuresRepository()
hook_feature_values_repository = HookFeatureValuesRepository()
hook_feature_statistics_repository = HookFeatureStatisticsRepository()
