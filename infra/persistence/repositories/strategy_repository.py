from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.persistence.mappers import (
    strategy_from_model,
    strategy_to_model,
    strategy_version_from_model,
    strategy_version_to_model,
)
from infra.persistence.models import StrategyModel, StrategyVersionModel
from quant.domain import Strategy, StrategyVersion


class SQLAlchemyStrategyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, strategy: Strategy) -> None:
        self._session.add(strategy_to_model(strategy))
        self._session.flush()

    def get(self, strategy_id: UUID) -> Strategy | None:
        row = self._session.get(StrategyModel, strategy_id)
        return strategy_from_model(row) if row is not None else None

    def add_version(self, version: StrategyVersion) -> None:
        self._session.add(strategy_version_to_model(version))
        self._session.flush()

    def get_version(self, version_id: UUID) -> StrategyVersion | None:
        row = self._session.get(StrategyVersionModel, version_id)
        return strategy_version_from_model(row) if row is not None else None

    def list_versions(self, strategy_id: UUID) -> Sequence[StrategyVersion]:
        statement = (
            select(StrategyVersionModel)
            .where(StrategyVersionModel.strategy_id == strategy_id)
            .order_by(StrategyVersionModel.created_at, StrategyVersionModel.id)
        )
        return [
            strategy_version_from_model(row) for row in self._session.scalars(statement)
        ]
