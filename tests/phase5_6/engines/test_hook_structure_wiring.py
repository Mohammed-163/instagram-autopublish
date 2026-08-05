"""
Tests that the Phase 4 Part 2 pipeline is correctly wired onto the event
bus: HookAnalyzed -> HookStructureLearningEngine, alongside the existing
HookAnalyzed -> HookKnowledgeEngine subscriber from Phase 4 Part 1 (both
must coexist; wiring a new engine must never replace an existing one).
"""
from __future__ import annotations

from unittest.mock import patch

from core.event_bus import EventBus
from core.events import HookAnalyzed
from core.wiring import wire_default_subscribers


def test_hook_analyzed_is_wired_to_both_hook_knowledge_and_structure_learning():
    bus = EventBus()
    wire_default_subscribers(bus)

    handlers = bus._subscribers.get(HookAnalyzed, [])
    handler_qualnames = {h.__qualname__ for h in handlers}

    assert any("HookKnowledgeEngine" in name for name in handler_qualnames)
    assert any("HookStructureLearningEngine" in name for name in handler_qualnames)


def test_wiring_does_not_raise():
    bus = EventBus()
    # Should not raise even though nothing publishes events in this test.
    wire_default_subscribers(bus)
