from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from infra.alpaca import (
    AlpacaHistoricalMarketDataProvider,
    AlpacaHTTPClient,
    AlpacaPaperBrokerAdapter,
    AlpacaPaperConfiguration,
)
from infra.market_data import (
    LocalParquetDatasetStorage,
    ReplayMarketDataProvider,
    dataset_storage_path,
)
from infra.persistence.database import create_database_engine, create_session_factory
from infra.persistence.repositories import (
    SQLAlchemyAlpacaPaperOrderRepository,
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
    AdvanceLiveSession,
    AdvanceReplaySession,
    ComparePaperParticipants,
    CreateDatasetSnapshot,
    CreatePaperSession,
    EvaluateValidationGate,
    ImportHistoricalDataset,
    LoadDatasetSnapshot,
    OperatorQueries,
    OperatorResearchWorkflow,
    PaperLifecycle,
    ProcessPaperBar,
    RunAdversarialValidation,
    RunMonteCarloValidation,
    RunOutOfSampleValidation,
    RunParameterSensitivityValidation,
    RunStressValidation,
    RunWalkForwardValidation,
)
from quant.domain import HistoricalDataset
from quant.ports import DatasetRepository

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
    datasets = SQLAlchemyDatasetRepository(session)
    return OperatorQueries(
        hypotheses=SQLAlchemyHypothesisRepository(session),
        strategies=SQLAlchemyStrategyRepository(session),
        datasets=datasets,
        experiments=SQLAlchemyExperimentRepository(session),
        gates=SQLAlchemyGateRepository(session),
        knowledge=SQLAlchemyKnowledgeRepository(session),
        dataset_loader=LoadDatasetSnapshot(
            LocalParquetDatasetStorage(dataset_storage_path()), datasets
        ),
    )


OperatorDependency = Annotated[OperatorQueries, Depends(get_operator_queries)]


@dataclass(frozen=True, slots=True)
class DatasetServices:
    repository: DatasetRepository
    loader: Callable[[UUID], HistoricalDataset]


def get_dataset_services(
    session: Annotated[Session, Depends(get_session)],
) -> DatasetServices:
    repository = SQLAlchemyDatasetRepository(session)
    return DatasetServices(
        repository,
        LoadDatasetSnapshot(
            LocalParquetDatasetStorage(dataset_storage_path()), repository
        ),
    )


DatasetDependency = Annotated[DatasetServices, Depends(get_dataset_services)]


def get_research_workflow(
    session: Annotated[Session, Depends(get_session)],
) -> OperatorResearchWorkflow:
    datasets = SQLAlchemyDatasetRepository(session)
    return OperatorResearchWorkflow(
        hypotheses=SQLAlchemyHypothesisRepository(session),
        knowledge=SQLAlchemyKnowledgeRepository(session),
        strategies=SQLAlchemyStrategyRepository(session),
        datasets=datasets,
        experiments=SQLAlchemyExperimentRepository(session),
        dataset_loader=LoadDatasetSnapshot(
            LocalParquetDatasetStorage(dataset_storage_path()), datasets
        ),
    )


ResearchDependency = Annotated[OperatorResearchWorkflow, Depends(get_research_workflow)]


@dataclass(frozen=True, slots=True)
class ValidationServices:
    out_of_sample: RunOutOfSampleValidation
    walk_forward: RunWalkForwardValidation
    sensitivity: RunParameterSensitivityValidation
    stress: RunStressValidation
    monte_carlo: RunMonteCarloValidation
    adversarial: RunAdversarialValidation
    gate: EvaluateValidationGate
    experiments: SQLAlchemyExperimentRepository


def get_validation_services(
    session: Annotated[Session, Depends(get_session)],
) -> ValidationServices:
    datasets = SQLAlchemyDatasetRepository(session)
    experiments = SQLAlchemyExperimentRepository(session)
    strategies = SQLAlchemyStrategyRepository(session)
    loader = LoadDatasetSnapshot(
        LocalParquetDatasetStorage(dataset_storage_path()), datasets
    )
    return ValidationServices(
        RunOutOfSampleValidation(experiments, strategies, datasets, loader),
        RunWalkForwardValidation(experiments, strategies, datasets, loader),
        RunParameterSensitivityValidation(experiments, strategies, datasets, loader),
        RunStressValidation(experiments, strategies, datasets, loader),
        RunMonteCarloValidation(experiments, datasets, loader),
        RunAdversarialValidation(experiments, datasets, loader),
        EvaluateValidationGate(
            experiments,
            strategies,
            datasets,
            SQLAlchemyGateRepository(session),
            loader,
        ),
        experiments,
    )


ValidationDependency = Annotated[
    ValidationServices, Depends(get_validation_services)
]


@dataclass(frozen=True, slots=True)
class PaperServices:
    repository: SQLAlchemyPaperRepository
    create_session: CreatePaperSession
    add_participant: AddPaperParticipant
    lifecycle: PaperLifecycle
    advance: AdvanceReplaySession
    compare: ComparePaperParticipants
    advance_live: AdvanceLiveSession | None = None


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
        advance_live=AdvanceLiveSession(papers, processor),
        compare=ComparePaperParticipants(papers),
    )


PaperDependency = Annotated[PaperServices, Depends(get_paper_services)]


@dataclass(frozen=True, slots=True)
class AlpacaServices:
    client: AlpacaHTTPClient
    broker: AlpacaPaperBrokerAdapter
    historical_import: ImportHistoricalDataset
    historical_import_for_feed: Callable[[str], ImportHistoricalDataset] | None = None


def get_alpaca_services(
    session: Annotated[Session, Depends(get_session)],
) -> Iterator[AlpacaServices]:
    configuration = AlpacaPaperConfiguration.from_environment()
    client = AlpacaHTTPClient.create(configuration)
    datasets = SQLAlchemyDatasetRepository(session)
    storage = LocalParquetDatasetStorage(dataset_storage_path())
    loader = LoadDatasetSnapshot(storage, datasets)
    try:
        def importer(feed: str) -> ImportHistoricalDataset:
            return ImportHistoricalDataset(
                CreateDatasetSnapshot(
                    AlpacaHistoricalMarketDataProvider(client, feed), storage, datasets
                ),
                loader,
            )

        yield AlpacaServices(
            client=client,
            broker=AlpacaPaperBrokerAdapter(
                client, SQLAlchemyAlpacaPaperOrderRepository(session).save
            ),
            historical_import=importer(configuration.market_data_feed),
            historical_import_for_feed=importer,
        )
    finally:
        client.client.close()


AlpacaDependency = Annotated[AlpacaServices, Depends(get_alpaca_services)]
