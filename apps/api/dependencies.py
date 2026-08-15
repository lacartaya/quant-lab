from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from infra.persistence.database import create_database_engine, create_session_factory
from infra.persistence.repositories import (
    SQLAlchemyDatasetRepository,
    SQLAlchemyExperimentRepository,
    SQLAlchemyGateRepository,
    SQLAlchemyHypothesisRepository,
    SQLAlchemyKnowledgeRepository,
    SQLAlchemyStrategyRepository,
)
from quant.application import OperatorQueries

_engine = create_database_engine()
_sessions = create_session_factory(_engine)


def get_session() -> Iterator[Session]:
    with _sessions() as session:
        yield session


def get_operator_queries(
    session: Annotated[Session, Depends(get_session)],
) -> OperatorQueries:
    return OperatorQueries(
        hypotheses=SQLAlchemyHypothesisRepository(session),
        strategies=SQLAlchemyStrategyRepository(session),
        datasets=SQLAlchemyDatasetRepository(session),
        experiments=SQLAlchemyExperimentRepository(session),
        gates=SQLAlchemyGateRepository(session),
        knowledge=SQLAlchemyKnowledgeRepository(session),
    )


OperatorDependency = Annotated[OperatorQueries, Depends(get_operator_queries)]
