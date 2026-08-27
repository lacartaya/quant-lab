from unittest.mock import Mock
from uuid import UUID

import pytest

from quant.application import OperatorResearchWorkflow, ResearchResourceNotFound
from quant.application.experiments.registry import UnsupportedVersionError


def workflow() -> OperatorResearchWorkflow:
    return OperatorResearchWorkflow(
        hypotheses=Mock(),
        knowledge=Mock(),
        strategies=Mock(),
        datasets=Mock(),
        experiments=Mock(),
        dataset_loader=Mock(),
        id_factory=iter(UUID(int=index) for index in range(1, 20)).__next__,
    )


def test_strategy_version_rejects_unknown_algorithm_without_persisting() -> None:
    service = workflow()
    with pytest.raises(UnsupportedVersionError, match="unsupported strategy algorithm"):
        service.create_strategy_version(
            name="Unsafe",
            description="Unknown executable",
            strategy_family="unknown",
            version="v1",
            git_commit="abc",
            algorithm_key="python.module.Class",
            parameters={},
        )
    service.strategies.add.assert_not_called()  # type: ignore[attr-defined]
    service.strategies.add_version.assert_not_called()  # type: ignore[attr-defined]


def test_strategy_version_rejects_invalid_moving_average_parameters() -> None:
    service = workflow()
    with pytest.raises(ValueError, match="short_window must be less than long_window"):
        service.create_strategy_version(
            name="Invalid",
            description="Invalid windows",
            strategy_family="moving_average_trend",
            version="v1",
            git_commit="abc",
            algorithm_key="moving_average_trend",
            parameters={"short_window": 200, "long_window": 50},
        )


def test_experiment_rejects_missing_hypothesis_before_persistence() -> None:
    service = workflow()
    service.hypotheses.get.return_value = None  # type: ignore[attr-defined]
    with pytest.raises(ResearchResourceNotFound, match="hypothesis"):
        service.create_experiment(
            hypothesis_id=UUID(int=1),
            strategy_version_id=UUID(int=2),
            dataset_snapshot_id=UUID(int=3),
        )
    service.experiments.add.assert_not_called()  # type: ignore[attr-defined]
