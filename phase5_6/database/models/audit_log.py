from datetime import datetime
from typing import Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import String, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    old_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[str] = mapped_column(String, server_default='system', nullable=False)
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        CheckConstraint(action.in_(['INSERT', 'UPDATE', 'DELETE']), name='audit_log_action_check'),
    )
