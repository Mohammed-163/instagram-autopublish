from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import MemoryEntry
from core.container import container

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(self, memory_repository=None) -> None:
        self.memory_repository = memory_repository or container.resolve("memory_repository")

    def remember(self, key: str, value: Any, category: Optional[str] = None, importance: float = 0.5) -> None:
        self.memory_repository.remember(memory_key=key, memory_value=value, category=category, importance=importance)

    def recall(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self.memory_repository.get_by_key(key)
        return entry.memory_value if entry else None

    def recall_by_category(self, category: str) -> List[MemoryEntry]:
        return self.memory_repository.list_by_category(category)

    def forget(self, key: str) -> bool:
        entry = self.memory_repository.get_by_key(key)
        if entry:
            return self.memory_repository.delete(entry.id)
        return False

    def get_important_memories(self, min_importance: float = 0.7) -> List[MemoryEntry]:
        entries = self.memory_repository.list_all()
        return [e for e in entries if e.importance and e.importance >= min_importance]

    def cleanup_expired(self) -> int:
        return 0


memory_service = MemoryService()
