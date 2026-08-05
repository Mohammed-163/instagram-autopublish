"""
SQLAlchemy ORM models for the Observation bounded context.
These are persistence models only; never expose them to the domain layer.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ObservationORM(Base):
    """
    Persistence model for an Observation aggregate.
    Schema version is stored per-row to support forward compatibility.
    """
    __tablename__ = "observations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    fingerprint = Column(String(64), nullable=False, unique=True, index=True)
    execution_id = Column(String(255), nullable=False)
    workflow_id = Column(String(255), nullable=False)
    node_id = Column(String(255), nullable=False)
    tenant_id = Column(String(255), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    context_extra = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="pending")
    schema_version = Column(String(32), nullable=False)
    observation_version = Column(String(32), nullable=False)

    __table_args__ = (
        Index("ix_observations_tenant_fingerprint", "tenant_id", "fingerprint"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ObservationORM id={self.id} fingerprint={self.fingerprint!r} "
            f"status={self.status!r}>"
        )
