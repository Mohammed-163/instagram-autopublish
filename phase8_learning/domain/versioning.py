"""
Versioning value object.

Every Knowledge object must carry a KnowledgeVersion describing:
    - knowledge_version   (monotonic version number of this knowledge item)
    - fingerprint_version (version of the fingerprinting algorithm used)
    - engine_version      (version of the LearningEngine that produced it)
    - schema_version      (version of the domain schema / contract)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeVersion:
    knowledge_version: int
    fingerprint_version: str
    engine_version: str
    schema_version: str

    def __post_init__(self) -> None:
        if self.knowledge_version < 1:
            raise ValueError("knowledge_version must be >= 1")
        if not self.fingerprint_version:
            raise ValueError("fingerprint_version is required")
        if not self.engine_version:
            raise ValueError("engine_version is required")
        if not self.schema_version:
            raise ValueError("schema_version is required")

    def next(self) -> "KnowledgeVersion":
        """Return a new KnowledgeVersion with knowledge_version incremented."""
        return KnowledgeVersion(
            knowledge_version=self.knowledge_version + 1,
            fingerprint_version=self.fingerprint_version,
            engine_version=self.engine_version,
            schema_version=self.schema_version,
        )

    def as_dict(self) -> dict:
        return {
            "knowledge_version": self.knowledge_version,
            "fingerprint_version": self.fingerprint_version,
            "engine_version": self.engine_version,
            "schema_version": self.schema_version,
        }
