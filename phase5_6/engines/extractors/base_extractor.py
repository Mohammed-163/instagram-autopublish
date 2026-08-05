from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseExtractor(ABC):
    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @property
    @abstractmethod
    def feature_name(self) -> str:
        pass

    @abstractmethod
    def extract(self, post: Any, design: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Return dict with 'value' and optionally 'lineage_extras'"""
        pass
