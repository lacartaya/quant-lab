from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.persistence.mappers import (
    gate_evaluation_from_model,
    gate_evaluation_to_model,
)
from infra.persistence.models import GateEvaluationModel
from quant.domain import ValidationGateResult


class SQLAlchemyGateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, result: ValidationGateResult) -> None:
        self._session.add(gate_evaluation_to_model(result))
        self._session.flush()

    def get(self, evaluation_id: UUID) -> ValidationGateResult | None:
        row = self._session.get(GateEvaluationModel, evaluation_id)
        return gate_evaluation_from_model(row) if row is not None else None

    def list_for_run(self, run_id: UUID) -> Sequence[ValidationGateResult]:
        statement = (
            select(GateEvaluationModel)
            .where(GateEvaluationModel.experiment_run_id == run_id)
            .order_by(GateEvaluationModel.evaluated_at, GateEvaluationModel.id)
        )
        return [
            gate_evaluation_from_model(row) for row in self._session.scalars(statement)
        ]
