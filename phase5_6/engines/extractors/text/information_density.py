from engines.extractors.base_extractor import BaseExtractor
from typing import Any, Dict

class InformationDensityExtractor(BaseExtractor):
    @property
    def version(self) -> str: return "1.0.0"
    
    @property
    def feature_name(self) -> str: return "information_density"
    
    def extract(self, post: Any, design: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
        text = str(getattr(post, "final_text", "") or "")
        words = len(text.split())
        chars = len(text)
        density = chars / words if words > 0 else 0
        return {"value": density, "lineage_extras": {"words": words, "chars": chars}}
