from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.persistence.mappers import hypothesis_from_model, hypothesis_to_model
from infra.persistence.models import HypothesisModel
from quant.domain import Hypothesis, HypothesisStatus


class SQLAlchemyHypothesisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, hypothesis: Hypothesis) -> None:
        self._session.add(hypothesis_to_model(hypothesis))
        self._session.flush()

    def save(self, hypothesis: Hypothesis) -> None:
        self._session.merge(hypothesis_to_model(hypothesis))
        self._session.flush()

    def get(self, hypothesis_id: UUID) -> Hypothesis | None:
        row = self._session.get(HypothesisModel, hypothesis_id)
        return hypothesis_from_model(row) if row is not None else None

    def list_by_status(self, status: HypothesisStatus) -> Sequence[Hypothesis]:
        statement = (
            select(HypothesisModel)
            .where(HypothesisModel.status == status.value)
            .order_by(HypothesisModel.created_at, HypothesisModel.id)
        )
        return [hypothesis_from_model(row) for row in self._session.scalars(statement)]

    def list_all(self) -> Sequence[Hypothesis]:
        statement = select(HypothesisModel).order_by(
            HypothesisModel.created_at, HypothesisModel.id
        )
        return [hypothesis_from_model(row) for row in self._session.scalars(statement)]
