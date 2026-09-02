from __future__ import annotations
from sqlalchemy import desc
from sqlalchemy.orm import Session
from phase8_learning.database.models import LearningObservationModel

def save_metrics(session: Session, observation_id: str, subject_id: str, metrics: list[tuple[str, float]], context: dict) -> None:
    for name, value in metrics:
        if session.query(LearningObservationModel).filter_by(observation_id=observation_id, metric_name=name).first() is None:
            session.add(LearningObservationModel(observation_id=observation_id, subject_id=subject_id, metric_name=name, metric_value=float(value), context=dict(context)))
    session.commit()

def latest_for_pairs(session: Session, pairs: set[tuple[str, str]], limit: int = 100) -> list[LearningObservationModel]:
    rows = []
    for subject_id, metric_name in pairs:
        rows.extend(session.query(LearningObservationModel).filter_by(subject_id=subject_id, metric_name=metric_name).order_by(desc(LearningObservationModel.created_at)).limit(limit).all())
    return rows
