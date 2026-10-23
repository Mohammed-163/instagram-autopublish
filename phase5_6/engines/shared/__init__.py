"""
engines.shared
==============
Shared infrastructure for all pipeline engines.

- EngineSettingsReader: safe typed settings access with defaults
- EngineBase: base class supplying heartbeat() + settings to every engine
"""
from engines.shared.settings_reader import EngineSettingsReader
from engines.shared.engine_base import EngineBase

__all__ = ["EngineSettingsReader", "EngineBase"]
