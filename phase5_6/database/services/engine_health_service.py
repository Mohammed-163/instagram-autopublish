from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import EngineHealth
from core.container import container

logger = logging.getLogger(__name__)


class EngineHealthService:
    def __init__(self, engine_health_repository=None) -> None:
        self.engine_health_repository = engine_health_repository or container.resolve("engine_health_repository")

    def heartbeat(self, engine_name: str, status: str, **metadata: Any) -> None:
        self.engine_health_repository.report_heartbeat(engine_name, status, metadata_info=metadata)

    def get_status(self, engine_name: str) -> Optional[EngineHealth]:
        return self.engine_health_repository.get_by_name(engine_name)

    def get_all_statuses(self) -> List[EngineHealth]:
        return self.engine_health_repository.list_all()

    def list_unhealthy(self) -> List[EngineHealth]:
        return self.engine_health_repository.list_unhealthy()

    def get_health_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for s in self.engine_health_repository.list_all():
            summary[s.status] = summary.get(s.status, 0) + 1
        return summary


engine_health_service = EngineHealthService()
