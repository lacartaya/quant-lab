from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.persistence.mappers import (
    experiment_from_model,
    experiment_run_from_model,
    experiment_run_to_model,
    experiment_to_model,
    promotion_from_model,
    promotion_to_model,
    validation_from_model,
    validation_to_model,
)
from infra.persistence.models import (
    ExperimentModel,
    ExperimentRunModel,
    PromotionDecisionModel,
    ValidationRunModel,
)
from quant.domain import (
    Experiment,
    ExperimentRun,
    PromotionDecision,
    ValidationRun,
)


class SQLAlchemyExperimentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, experiment: Experiment) -> None:
        self._session.add(experiment_to_model(experiment))
        self._session.flush()

    def get(self, experiment_id: UUID) -> Experiment | None:
        row = self._session.get(ExperimentModel, experiment_id)
        return experiment_from_model(row) if row is not None else None

    def add_run(self, run: ExperimentRun) -> None:
        self._session.add(experiment_run_to_model(run))
        self._session.flush()

    def get_run(self, run_id: UUID) -> ExperimentRun | None:
        row = self._session.get(ExperimentRunModel, run_id)
        return experiment_run_from_model(row) if row is not None else None

    def list_runs(self, experiment_id: UUID) -> Sequence[ExperimentRun]:
        statement = (
            select(ExperimentRunModel)
            .where(ExperimentRunModel.experiment_id == experiment_id)
            .order_by(ExperimentRunModel.started_at, ExperimentRunModel.id)
        )
        return [
            experiment_run_from_model(row) for row in self._session.scalars(statement)
        ]

    def add_validation(self, validation: ValidationRun) -> None:
        self._session.add(validation_to_model(validation))
        self._session.flush()

    def get_validation(self, validation_id: UUID) -> ValidationRun | None:
        row = self._session.get(ValidationRunModel, validation_id)
        return validation_from_model(row) if row is not None else None

    def list_validations(self, run_id: UUID) -> Sequence[ValidationRun]:
        statement = (
            select(ValidationRunModel)
            .where(ValidationRunModel.experiment_run_id == run_id)
            .order_by(ValidationRunModel.created_at, ValidationRunModel.id)
        )
        return [
            validation_from_model(row) for row in self._session.scalars(statement)
        ]

    def add_promotion_decision(self, decision: PromotionDecision) -> None:
        self._session.add(promotion_to_model(decision))
        self._session.flush()

    def list_promotion_decisions(
        self, experiment_id: UUID
    ) -> Sequence[PromotionDecision]:
        statement = (
            select(PromotionDecisionModel)
            .where(PromotionDecisionModel.experiment_id == experiment_id)
            .order_by(PromotionDecisionModel.created_at, PromotionDecisionModel.id)
        )
        return [promotion_from_model(row) for row in self._session.scalars(statement)]
