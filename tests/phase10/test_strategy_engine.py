"""Integration test for strategy seeding, evolution, and optimization."""
def test_seed_evolve_evaluate(container):
    parent = container.strategy_engine.seed("strat-1", {"weight": 1.0, "limit": 10})
    children = container.strategy_engine.evolve_generation([parent])
    assert len(children) == 1
    child = children[0]
    assert child.generation == parent.generation + 1
    assert child.parameters["weight"] != parent.parameters["weight"]

    evaluation = container.strategy_engine.evaluate(child, {"accuracy": 0.9, "coverage": 0.8})
    assert evaluation.fitness_score > 0
