"""
Hook Feature Analyzer Plugin Architecture
==========================================
Every analyzer under `engines.hook_feature_analyzers.plugins` is an
independent, self-contained plugin (a subclass of `HookFeatureAnalyzer`).
`HookStructureLearningEngine` never imports a specific analyzer by name —
it discovers all of them at startup via `pkgutil.walk_packages`, exactly
like `engines/extractors` does for FeatureExtractionEngine.

To add a new Hook Feature: drop a new module in `plugins/` defining a
`HookFeatureAnalyzer` subclass. Nothing else needs to change.
"""
