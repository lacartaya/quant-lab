from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest

from quant.domain import (
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_experiment_creation_and_statuses() -> None:
    experiment = Experiment(
        uuid4(), uuid4(), uuid4(), uuid4(), ExperimentStatus.CREATED, NOW
    )
    assert experiment.status is ExperimentStatus.CREATED
    assert set(ExperimentStatus) == set(ExperimentStatus.__members__.values())


def test_experiment_requires_uuid_references() -> None:
    with pytest.raises(TypeError, match="hypothesis_id must be a UUID"):
        Experiment(
            uuid4(),
            cast(UUID, ""),
            uuid4(),
            uuid4(),
            ExperimentStatus.CREATED,
            NOW,
        )


def make_run(*, completed_at: datetime | None = None) -> ExperimentRun:
    return ExperimentRun(
        uuid4(),
        uuid4(),
        "abc123",
        "1",
        "fees-v1",
        "slippage-v1",
        {"seed": 7},
        NOW,
        completed_at,
        ExperimentRunStatus.COMPLETED,
    )


def test_experiment_run_construction_preserves_configuration() -> None:
    run = make_run(completed_at=NOW + timedelta(hours=1))
    assert run.configuration == {"seed": 7}


def test_experiment_run_rejects_completion_before_start() -> None:
    with pytest.raises(ValueError, match="completed_at cannot be before started_at"):
        make_run(completed_at=NOW - timedelta(seconds=1))
