"""
Cross-phase event bridges.

Each bridge connects two adjacent phases by:
  1. Subscribing to the upstream phase's output event on the shared bus
  2. Translating the event into the downstream phase's input shape
  3. Invoking the downstream phase's entry point

Bridges are intentionally thin — they contain NO business logic.
All translation is structural (field mapping only).

Available bridges:
  bridges.execution_to_observation   Phase6  → Phase7
  bridges.observation_to_learning    Phase7  → Phase8
  bridges.learning_to_coverage       Phase8  → Phase9
  bridges.coverage_to_intelligence   Phase9  → Phase10
"""
