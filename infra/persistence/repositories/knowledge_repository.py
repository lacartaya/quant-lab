from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from infra.persistence.mappers import knowledge_from_model, knowledge_to_model
from infra.persistence.models import KnowledgeRecordModel
from quant.domain.knowledge import KnowledgeQuery, KnowledgeRecord


class SQLAlchemyKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: KnowledgeRecord) -> None:
        self._session.add(knowledge_to_model(record))
        self._session.flush()

    def get(self, record_id: UUID) -> KnowledgeRecord | None:
        row = self._session.get(KnowledgeRecordModel, record_id)
        return knowledge_from_model(row) if row is not None else None

    def list_for_hypothesis(self, hypothesis_id: UUID) -> Sequence[KnowledgeRecord]:
        statement = self._ordered().where(
            KnowledgeRecordModel.hypothesis_id == hypothesis_id
        )
        return [knowledge_from_model(row) for row in self._session.scalars(statement)]

    def list_all(self) -> Sequence[KnowledgeRecord]:
        return [
            knowledge_from_model(row) for row in self._session.scalars(self._ordered())
        ]

    def search(self, query: KnowledgeQuery) -> Sequence[KnowledgeRecord]:
        statement = self._ordered()
        for column, value in (
            (KnowledgeRecordModel.strategy_family, query.strategy_family),
            (KnowledgeRecordModel.market, query.market),
            (KnowledgeRecordModel.instrument, query.instrument),
            (KnowledgeRecordModel.timeframe, query.timeframe),
        ):
            if value is not None:
                statement = statement.where(column == value)
        if query.status is not None:
            statement = statement.where(
                KnowledgeRecordModel.status == query.status.value
            )
        return [knowledge_from_model(row) for row in self._session.scalars(statement)]

    @staticmethod
    def _ordered() -> Select[tuple[KnowledgeRecordModel]]:
        return select(KnowledgeRecordModel).order_by(
            KnowledgeRecordModel.created_at, KnowledgeRecordModel.id
        )
