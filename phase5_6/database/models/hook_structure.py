from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class HookStructure(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One row per learned hook structure: the first line of a post's text,
    decomposed into independent linguistic Features (via the Hook Feature
    Analyzer plugins) plus a lightweight, ordered `grammar_sequence`
    (foundation for the future Hook Grammar Graph — see
    engines/hook_grammar.py for the interfaces this schema was designed
    against).

    Written once by HookStructureLearningEngine and never mutated
    afterwards (append-only, replayable — the same hook_text + the same
    analyzer versions always reproduce the same row).
    """

    __tablename__ = "hook_structures"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[Optional[str]] = mapped_column(Text)
    hook_type: Mapped[Optional[str]] = mapped_column(Text)
    hook_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Every analyzer's {feature_name: value} — the flat, queryable summary.
    features: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Per-feature explainability: extraction method, source, analyzer + version.
    explainability: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Ordered list of grammar components detected in the hook (e.g.
    # ["opening", "curiosity", "question", "number"]). Deliberately simple
    # (a sequence, not a graph) in this phase — see hook_grammar.py.
    grammar_sequence: Mapped[List[str]] = mapped_column(JSONB, nullable=False)

    # {feature_name: analyzer_version} snapshot at analysis time, so old
    # rows remain interpretable even after analyzers evolve.
    analyzer_versions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    schema_version: Mapped[str] = mapped_column(Text, default="1.0.0")

    structural_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feature_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fingerprint_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
