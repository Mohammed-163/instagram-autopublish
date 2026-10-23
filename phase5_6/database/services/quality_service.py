from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import QualityResult
from core.container import container

logger = logging.getLogger(__name__)


class QualityService:
    def __init__(self, quality_results_repository=None) -> None:
        self.quality_results_repository = quality_results_repository or container.resolve("quality_results_repository")

    def record_check(self, post_id: Any, gate_name: str, passed: bool, score: Optional[float] = None, details: Optional[Dict[str, Any]] = None) -> QualityResult:
        return self.quality_results_repository.create(
            post_id=post_id, gate_name=gate_name, passed=passed, score=score, details=details or {}
        )

    def is_post_cleared(self, post_id: Any, required_gates: List[str]) -> bool:
        results = self.quality_results_repository.list_for_post(post_id)
        passed_gates = {r.gate_name for r in results if r.passed}
        return all(g in passed_gates for g in required_gates)

    def get_post_quality_summary(self, post_id: Any) -> Dict[str, Any]:
        results = self.quality_results_repository.list_for_post(post_id)
        return {
            "total_checks": len(results),
            "passed": len([r for r in results if r.passed]),
            "failed": len([r for r in results if not r.passed]),
            "gates": {r.gate_name: r.passed for r in results},
        }

    def get_pass_rates(self, gate_name: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        results = self.quality_results_repository.list_all()
        if gate_name:
            results = [r for r in results if r.gate_name == gate_name]

        total = len(results)
        if not total:
            return {"pass_rate": 0, "total": 0}

        passed = len([r for r in results if r.passed])
        return {"pass_rate": passed / total, "total": total, "passed": passed}


quality_service = QualityService()
