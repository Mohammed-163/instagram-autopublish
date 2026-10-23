from __future__ import annotations

from phase9_coverage.domain.inbound_events import KnowledgeValidated


def make_knowledge_validated(
    *,
    knowledge_id: str = "knowledge-1",
    knowledge_versions: tuple[str, ...] = ("v1",),
    topics: tuple[str, ...] = ("topic-a", "topic-b"),
    categories: tuple[str, ...] = ("category-a",),
    evidence_count: int = 4,
    confidence_scores: tuple[float, ...] = (0.6, 0.7, 0.8),
    freshness_timestamps: tuple[str, ...] = ("2026-01-01T00:00:00Z",),
    relationships: tuple[str, ...] = ("rel-a",),
) -> KnowledgeValidated:
    return KnowledgeValidated(
        knowledge_id=knowledge_id,
        knowledge_versions=knowledge_versions,
        topics=topics,
        categories=categories,
        evidence_count=evidence_count,
        confidence_scores=confidence_scores,
        freshness_timestamps=freshness_timestamps,
        relationships=relationships,
    )
