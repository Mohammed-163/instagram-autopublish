"""
Hook Grammar — foundation interfaces only.
===========================================
Per Phase 4 Part 2 scope, no full Hook Grammar Graph is built yet. This
module defines the data model / interfaces so a future
`HookGrammarGraphEngine` can be added without redesigning
`hook_structures.grammar_sequence` (JSONB) or the engine's contract.

What exists TODAY:
    HookStructureLearningEngine.build_grammar_sequence() produces a simple
    ORDERED LIST of component names present in the hook, e.g.:
        ["opening", "curiosity", "question", "number"]
    This is stored as-is in HookStructure.grammar_sequence.

What a future Graph engine would do, using the interfaces below:
    Read many `grammar_sequence` lists, build a `HookGrammarGraph` of
    `HookGrammarNode`s connected by `HookGrammarEdge`s, and learn which
    paths correlate with success (once success scores are available).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class HookGrammarNode:
    """A single component in a hook's grammar (e.g. 'curiosity', 'number')."""

    name: str


@dataclass(frozen=True)
class HookGrammarEdge:
    """A directed transition observed between two consecutive components,
    with an observation count (purely descriptive — no success judgment)."""

    source: str
    target: str
    observed_count: int = 0


@dataclass
class HookGrammarGraph:
    """In-memory representation a future engine would build from many
    `grammar_sequence` rows. Not persisted in this phase."""

    nodes: Dict[str, HookGrammarNode] = field(default_factory=dict)
    edges: Dict[tuple, HookGrammarEdge] = field(default_factory=dict)

    def add_sequence(self, sequence: List[str]) -> None:
        """Fold one hook's grammar_sequence into the graph as nodes + edges."""
        for name in sequence:
            self.nodes.setdefault(name, HookGrammarNode(name=name))
        for source, target in zip(sequence, sequence[1:]):
            key = (source, target)
            existing = self.edges.get(key)
            if existing is None:
                self.edges[key] = HookGrammarEdge(source=source, target=target, observed_count=1)
            else:
                self.edges[key] = HookGrammarEdge(
                    source=source, target=target, observed_count=existing.observed_count + 1
                )
