from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.application import RegisterExperiment
from quant.domain import (
    Experiment,
    ExperimentRun,
    ExperimentStatus,
    PromotionDecision,
    ValidationRun,
)


class RecordingExperimentRepository:
    def __init__(self) -> None:
        self.added: list[Experiment] = []

    def add(self, experiment: Experiment) -> None:
        self.added.append(experiment)

    def get(self, experiment_id: UUID) -> Experiment | None:
        return None

    def list_all(self) -> Sequence[Experiment]:
        return list(self.added)

    def list_for_hypothesis(self, hypothesis_id: UUID) -> Sequence[Experiment]:
        return [item for item in self.added if item.hypothesis_id == hypothesis_id]

    def add_run(self, run: ExperimentRun) -> None:
        raise NotImplementedError

    def save_run(self, run: ExperimentRun) -> None:
        raise NotImplementedError

    def get_run(self, run_id: UUID) -> ExperimentRun | None:
        return None

    def list_runs(self, experiment_id: UUID) -> Sequence[ExperimentRun]:
        return []

    def add_validation(self, validation: ValidationRun) -> None:
        raise NotImplementedError

    def get_validation(self, validation_id: UUID) -> ValidationRun | None:
        return None

    def list_validations(self, run_id: UUID) -> Sequence[ValidationRun]:
        return []

    def add_promotion_decision(self, decision: PromotionDecision) -> None:
        raise NotImplementedError

    def list_promotion_decisions(
        self, experiment_id: UUID
    ) -> Sequence[PromotionDecision]:
        return []


def test_register_experiment_delegates_to_repository() -> None:
    repository = RecordingExperimentRepository()
    use_case = RegisterExperiment(repository)
    experiment = Experiment(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        ExperimentStatus.CREATED,
        datetime(2026, 8, 15, tzinfo=UTC),
    )
    use_case(experiment)
    assert repository.added == [experiment]
