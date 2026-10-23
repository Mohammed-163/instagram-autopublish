"""
Unit tests for HookStructureService (mocked repositories — no DB needed).
"""
from __future__ import annotations

import uuid
from unittest.mock import Mock

# NOTE: core.container must finish initializing before database.services
# is imported for the first time in a process, or a pre-existing circular
# import in database/services/__init__.py -> knowledge_service.py ->
# core.container -> (back to) database.services.knowledge_service raises.
# Importing it explicitly first here makes this test file safe to run in
# isolation, independent of whatever other test module pytest happens to
# collect first.
import core.container  # noqa: F401

from database.services.hook_structure_service import HookStructureService


def _service():
    return HookStructureService(
        hook_structures_repository=Mock(),
        hook_feature_values_repository=Mock(),
        hook_feature_statistics_repository=Mock(),
    )


def test_record_hook_structure_defaults_category_to_general():
    service = _service()
    post_id = uuid.uuid4()
    service.record_hook_structure(
        post_id=post_id,
        hook_text="test",
        features={"a": 1},
        explainability={"a": {"extraction_method": "count", "source": "hook_text", "analyzer_version": "1.0.0"}},
        grammar_sequence=["opening"],
        analyzer_versions={"a": "1.0.0"},
        category=None,
        hook_type="curiosity",
    )
    call_kwargs = service.hook_structures_repository.create.call_args[1]
    assert call_kwargs["category"] == "General"
    assert call_kwargs["post_id"] == post_id


def test_record_feature_values_creates_one_row_per_feature():
    service = _service()
    structure_id = uuid.uuid4()
    post_id = uuid.uuid4()
    features = {"word_count": 3, "has_number": {"present": True, "position": 0.1}}
    explainability = {
        "word_count": {"extraction_method": "count", "source": "hook_text", "analyzer_version": "1.0.0"},
        "has_number": {"extraction_method": "regex", "source": "hook_text", "analyzer_version": "1.0.0"},
    }

    service.record_feature_values(structure_id, post_id, features, explainability)

    assert service.hook_feature_values_repository.create.call_count == 2
    created_names = {
        call.kwargs["feature_name"] for call in service.hook_feature_values_repository.create.call_args_list
    }
    assert created_names == {"word_count", "has_number"}


def test_record_feature_observation_creates_new_statistic():
    service = _service()
    service.hook_feature_statistics_repository.get_by_category_hook_type_feature.return_value = None

    service.record_feature_observation("Science", "curiosity", "has_number", contribution_score=0.8)

    service.hook_feature_statistics_repository.create.assert_called_once()
    kwargs = service.hook_feature_statistics_repository.create.call_args[1]
    assert kwargs["sample_size"] == 1
    assert kwargs["category"] == "Science"


def test_record_feature_observation_updates_existing_statistic():
    service = _service()
    existing = Mock(sample_size=4, contribution_sum=2)
    service.hook_feature_statistics_repository.get_by_category_hook_type_feature.return_value = existing

    service.record_feature_observation("Science", "curiosity", "has_number", contribution_score=1)

    service.hook_feature_statistics_repository.update.assert_called_once()
    kwargs = service.hook_feature_statistics_repository.update.call_args[1]
    assert kwargs["sample_size"] == 5
