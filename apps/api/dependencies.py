from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from infra.market_data import (
    LocalParquetDatasetStorage,
    ReplayMarketDataProvider,
    dataset_storage_path,
)
from infra.persistence.database import create_database_engine, create_session_factory
from infra.persistence.repositories import (
    SQLAlchemyDatasetRepository,
    SQLAlchemyExperimentRepository,
    SQLAlchemyGateRepository,
    SQLAlchemyHypothesisRepository,
    SQLAlchemyKnowledgeRepository,
    SQLAlchemyPaperRepository,
    SQLAlchemyStrategyRepository,
)
from quant.application import (
    AddPaperParticipant,
    AdvanceReplaySession,
    ComparePaperParticipants,
    CreatePaperSession,
    LoadDatasetSnapshot,
    OperatorQueries,
    PaperLifecycle,
    ProcessPaperBar,
)

_engine = create_database_engine()
_sessions = create_session_factory(_engine)


def get_session() -> Iterator[Session]:
    with _sessions() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


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


@dataclass(frozen=True, slots=True)
class PaperServices:
    repository: SQLAlchemyPaperRepository
    create_session: CreatePaperSession
    add_participant: AddPaperParticipant
    lifecycle: PaperLifecycle
    advance: AdvanceReplaySession
    compare: ComparePaperParticipants


def get_paper_services(
    session: Annotated[Session, Depends(get_session)],
) -> PaperServices:
    datasets = SQLAlchemyDatasetRepository(session)
    papers = SQLAlchemyPaperRepository(session)
    loader = LoadDatasetSnapshot(
        LocalParquetDatasetStorage(dataset_storage_path()), datasets
    )
    processor = ProcessPaperBar(papers, SQLAlchemyStrategyRepository(session))
    return PaperServices(
        repository=papers,
        create_session=CreatePaperSession(datasets, loader, papers),
        add_participant=AddPaperParticipant(
            papers,
            SQLAlchemyGateRepository(session),
            SQLAlchemyExperimentRepository(session),
            SQLAlchemyStrategyRepository(session),
        ),
        lifecycle=PaperLifecycle(papers),
        advance=AdvanceReplaySession(
            papers,
            loader,
            processor,
            lambda dataset, after: ReplayMarketDataProvider(dataset, after=after),
        ),
        compare=ComparePaperParticipants(papers),
    )


PaperDependency = Annotated[PaperServices, Depends(get_paper_services)]
