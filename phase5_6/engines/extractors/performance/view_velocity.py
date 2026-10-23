from engines.extractors.base_extractor import BaseExtractor
from typing import Any, Dict

class ViewVelocityExtractor(BaseExtractor):
    @property
    def version(self) -> str: return "1.0.0"
    
    @property
    def feature_name(self) -> str: return "view_velocity"
    
    def extract(self, post: Any, design: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
        views_2h = metrics.get("views_2h", 0)
        views_24h = metrics.get("views_24h", 1)
        velocity = views_24h / (views_2h + 1)
        return {"value": velocity, "lineage_extras": {"metric_used": "views_2h,views_24h"}}
