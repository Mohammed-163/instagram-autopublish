from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from core.container import container

logger = logging.getLogger(__name__)


class SettingsService:
    def __init__(self, settings_repository=None) -> None:
        self.settings_repository = settings_repository or container.resolve("settings_repository")

    def get(self, key: str, default: Any = None) -> Any:
        value = self.settings_repository.get(key)
        return value if value is not None else default

    def set(self, key: str, value: Any, description: Optional[str] = None) -> None:
        self.settings_repository.set(key, value, description=description)

    def get_all(self) -> Dict[str, Any]:
        return {s.key: s.value for s in self.settings_repository.list_all()}

    def delete(self, key: str) -> bool:
        return self.settings_repository.delete(key)


settings_service = SettingsService()
