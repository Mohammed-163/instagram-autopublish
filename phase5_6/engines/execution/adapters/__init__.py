"""
engines.execution.adapters — Platform adapter package.

Contents:
  base_adapter      : BaseExecutionAdapter (abstract interface), AdapterResult
  instagram_adapter : InstagramExecutionAdapter (skeleton)
  youtube_adapter   : YouTubeExecutionAdapter (skeleton)
  registry          : AdapterRegistry, build_default_registry(), adapter_registry singleton
"""
from engines.execution.adapters.base_adapter import AdapterResult, BaseExecutionAdapter
from engines.execution.adapters.instagram_adapter import InstagramExecutionAdapter
from engines.execution.adapters.registry import (
    AdapterRegistry,
    adapter_registry,
    build_default_registry,
)
from engines.execution.adapters.youtube_adapter import YouTubeExecutionAdapter

__all__ = [
    "AdapterResult",
    "BaseExecutionAdapter",
    "InstagramExecutionAdapter",
    "YouTubeExecutionAdapter",
    "AdapterRegistry",
    "adapter_registry",
    "build_default_registry",
]
