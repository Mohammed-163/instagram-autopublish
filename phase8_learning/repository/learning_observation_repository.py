from __future__ import annotations
from sqlalchemy import desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from phase8_learning.database.models import LearningObservationModel

def save_metrics(session: Session, observation_id: str, subject_id: str, metrics: list[tuple[str, float]], context: dict, media_id: str | None = None) -> None:
    context = dict(context or {})
    resolved_media_id = str(
        media_id or context.get("media_id") or context.get("fingerprint") or ""
    ).strip()
    if not resolved_media_id:
        raise ValueError(
            "learning observation requires media_id or fingerprint for deduplication"
        )
    context["media_id"] = resolved_media_id
    rows = [
        {
            "observation_id": observation_id,
            "media_id": resolved_media_id,
            "subject_id": subject_id,
            "metric_name": name,
            "metric_value": float(value),
            "context": context,
        }
        for name, value in metrics
    ]
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(LearningObservationModel.__table__).values(rows).on_conflict_do_nothing(
            index_elements=["media_id", "metric_name"]
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(LearningObservationModel.__table__).values(rows).on_conflict_do_nothing(
            index_elements=["media_id", "metric_name"]
        )
    else:
        raise RuntimeError(f"Unsupported database dialect for learning observation upsert: {dialect}")
    session.execute(statement)
    session.commit()

def latest_for_pairs(session: Session, pairs: set[tuple[str, str]], limit: int = 100) -> list[LearningObservationModel]:
    rows = []
    for subject_id, metric_name in pairs:
        rows.extend(session.query(LearningObservationModel).filter_by(subject_id=subject_id, metric_name=metric_name).order_by(desc(LearningObservationModel.created_at)).limit(limit).all())
    return rows
