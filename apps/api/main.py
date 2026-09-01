from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from apps.api.dependencies import (
    AlpacaDependency,
    DatasetDependency,
    OperatorDependency,
    PaperDependency,
    ResearchDependency,
    ValidationDependency,
)
from apps.api.mappers import (
    experiment_detail,
    experiment_run,
    experiment_summary,
    gate,
    hypothesis,
    json_value,
    knowledge,
    prior_art,
    validation,
)
from apps.api.schemas import (
    AddPaperParticipantRequest,
    AdversarialRequest,
    AlpacaPaperAccountResponse,
    AlpacaPaperFillResponse,
    AlpacaPaperOrderResponse,
    AlpacaPaperPositionResponse,
    BacktestVisualizationResponse,
    CreateExperimentRequest,
    CreateExperimentResponse,
    CreateHypothesisRequest,
    CreatePaperSessionRequest,
    CreateStrategyVersionRequest,
    DashboardSummaryResponse,
    DatasetQualityResponse,
    DatasetSnapshotListResponse,
    DatasetSnapshotResponse,
    ExperimentDetailResponse,
    ExperimentListResponse,
    ExperimentRunResponse,
    GateEvaluationRequest,
    GateResponse,
    HistoricalImportRequest,
    HypothesisDetailResponse,
    HypothesisListResponse,
    HypothesisResponse,
    KnowledgeListResponse,
    MonteCarloRequest,
    OutOfSampleRequest,
    PageMetadata,
    PaperArtifactListResponse,
    PaperParticipantResponse,
    PaperProcessingResponse,
    PaperSessionDetailResponse,
    PaperSessionResponse,
    ParameterSensitivityRequest,
    PriorArtRequest,
    PriorArtResponse,
    RunExperimentRequest,
    RunExperimentResponse,
    StrategyVersionCreateResponse,
    StressRequest,
    SubmitAlpacaPaperOrderRequest,
    ValidationResponse,
    WalkForwardRequest,
)
from infra.alpaca import (
    AlpacaAPIError,
    AlpacaConfigurationError,
    AlpacaLiveMarketDataProvider,
)
from quant.analytics import AnalyticsConfiguration
from quant.application import (
    MAX_VISUALIZATION_BARS,
    BacktestVisualizationService,
    CheckPriorArt,
    DuplicateHypothesisError,
    OperatorResourceNotFound,
    PaperArenaError,
    RejectedPriorArtError,
    UnsupportedVersionError,
    dataset_quality,
)
from quant.backtest import (
    BacktestConfiguration,
    BasisPointsSlippageModel,
    FeeModel,
    PercentageFeeModel,
    SlippageModel,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import (
    AdjustmentPolicy,
    ExperimentStatus,
    GateRuleCode,
    GateRuleDefinition,
    HypothesisStatus,
    PaperOrderSide,
    PaperOrderType,
    PaperParticipant,
    PaperSession,
    PaperTimeInForce,
    SubmitAlpacaPaperOrder,
    ValidationGatePolicy,
    ValidationType,
)
from quant.domain.knowledge import (
    KnowledgeQuery,
    PriorArtConfiguration,
    ResearchSignature,
)
from quant.validation import (
    AdversarialAnalysisConfiguration,
    MonteCarloConfiguration,
    OutOfSampleConfiguration,
    ParameterSensitivityConfiguration,
    SamplingMethod,
    StressScenario,
    StressTestingConfiguration,
    StressType,
    WalkForwardConfiguration,
    WalkForwardMode,
)

app = FastAPI(
    title="Quant Lab Operator API",
    version="1.0.0",
    description=(
        "Deterministic research evidence, immutable market-data import, internal "
        "Paper Arena, and explicitly simulated Alpaca PAPER operations. No "
        "real-money execution capability."
    ),
)


@app.exception_handler(DuplicateHypothesisError)
@app.exception_handler(RejectedPriorArtError)
async def research_conflict_handler(request: Request, error: Exception) -> JSONResponse:
    del request
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.exception_handler(UnsupportedVersionError)
@app.exception_handler(ValueError)
async def invalid_research_request_handler(
    request: Request, error: Exception
) -> JSONResponse:
    del request
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(OperatorResourceNotFound)
async def not_found_handler(
    request: Request, error: OperatorResourceNotFound
) -> JSONResponse:
    del request
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(LookupError)
async def lookup_error_handler(request: Request, error: LookupError) -> JSONResponse:
    del request
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(PaperArenaError)
async def paper_error_handler(request: Request, error: PaperArenaError) -> JSONResponse:
    del request
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.exception_handler(AlpacaConfigurationError)
async def alpaca_configuration_handler(
    request: Request, error: AlpacaConfigurationError
) -> JSONResponse:
    del request
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(AlpacaAPIError)
async def alpaca_api_handler(request: Request, error: AlpacaAPIError) -> JSONResponse:
    del request
    status = error.status_code if error.status_code in {403, 404, 429, 504} else 502
    return JSONResponse(
        status_code=status,
        content={"detail": str(error), "alpaca_request_id": error.request_id},
    )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


def _dataset_response(
    snapshot: Any,
    *,
    bar_count: int | None = None,
    actual_start_at: Any = None,
    actual_end_at: Any = None,
) -> DatasetSnapshotResponse:
    provider, separator, feed = snapshot.provider.partition(":")
    return DatasetSnapshotResponse(
        id=snapshot.id,
        provider=provider.upper(),
        feed=feed if separator else None,
        market=snapshot.market,
        instrument=snapshot.instrument,
        timeframe=snapshot.timeframe,
        requested_start_at=snapshot.start_at,
        requested_end_at=snapshot.end_at,
        actual_start_at=actual_start_at,
        actual_end_at=actual_end_at,
        bar_count=bar_count,
        adjustment_policy=snapshot.adjustment_policy.value,
        checksum=snapshot.checksum,
        storage_location=snapshot.storage_location,
        created_at=snapshot.created_at,
    )


@app.get(
    "/api/v1/datasets",
    response_model=DatasetSnapshotListResponse,
    tags=["market-data"],
    summary="List immutable dataset snapshots",
)
def list_datasets(
    datasets: DatasetDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DatasetSnapshotListResponse:
    items = datasets.repository.list_all()[offset : offset + limit]
    return DatasetSnapshotListResponse(
        items=[
            _dataset_response(
                item,
                bar_count=len(loaded.bars),
                actual_start_at=loaded.bars[0].timestamp,
                actual_end_at=loaded.bars[-1].timestamp,
            )
            for item in items
            for loaded in (datasets.loader(item.id),)
        ],
        page=PageMetadata(limit=limit, offset=offset, returned=len(items)),
    )


@app.get(
    "/api/v1/datasets/{snapshot_id}",
    response_model=DatasetSnapshotResponse,
    tags=["market-data"],
    summary="Get dataset lineage and immutable identity",
)
def get_dataset(
    snapshot_id: UUID, datasets: DatasetDependency
) -> DatasetSnapshotResponse:
    snapshot = datasets.repository.get(snapshot_id)
    if snapshot is None:
        raise LookupError(f"dataset snapshot {snapshot_id} was not found")
    loaded = datasets.loader(snapshot_id)
    return _dataset_response(
        snapshot,
        bar_count=len(loaded.bars),
        actual_start_at=loaded.bars[0].timestamp,
        actual_end_at=loaded.bars[-1].timestamp,
    )


@app.get(
    "/api/v1/datasets/{snapshot_id}/quality",
    response_model=DatasetQualityResponse,
    tags=["market-data"],
    summary="Inspect deterministic structural dataset quality",
)
def get_dataset_quality(
    snapshot_id: UUID, datasets: DatasetDependency
) -> DatasetQualityResponse:
    snapshot = datasets.repository.get(snapshot_id)
    if snapshot is None:
        raise LookupError(f"dataset snapshot {snapshot_id} was not found")
    quality = dataset_quality(snapshot_id, datasets.loader(snapshot_id).bars)
    return DatasetQualityResponse(
        snapshot_id=snapshot_id,
        requested_start_at=snapshot.start_at,
        requested_end_at=snapshot.end_at,
        actual_start_at=quality.actual_start_at,
        actual_end_at=quality.actual_end_at,
        total_bars=quality.total_bars,
        duplicate_timestamps=quality.duplicate_timestamps,
        non_monotonic_timestamps=quality.non_monotonic_timestamps,
        ordering_valid=quality.ordering_valid,
        ordering_failure_examples=[
            dict(item) for item in quality.ordering_failure_examples
        ],
        ohlc_validity_failures=quality.ohlc_validity_failures,
        missing_ohlcv_values=quality.missing_ohlcv_values,
        ohlcv_integrity_valid=quality.ohlcv_integrity_valid,
        ohlcv_failure_examples=[dict(item) for item in quality.ohlcv_failure_examples],
        bars_by_calendar_year=dict(quality.bars_by_calendar_year),
        exchange_calendar_verified=False,
        completeness_note=(
            "Observed bars by calendar year only; coverage was not verified against "
            "an authoritative exchange calendar."
        ),
        has_structural_errors=quality.has_structural_errors,
    )


@app.post(
    "/api/v1/market-data/import",
    response_model=DatasetSnapshotResponse,
    status_code=201,
    tags=["market-data"],
    summary="Import Alpaca IEX daily bars into an immutable Parquet snapshot",
)
def import_market_data(
    request: HistoricalImportRequest, alpaca: AlpacaDependency
) -> DatasetSnapshotResponse:
    if request.provider.upper() != "ALPACA":
        raise ValueError("the HTTP import workflow currently supports ALPACA only")
    importer = (
        alpaca.historical_import_for_feed(request.feed)
        if alpaca.historical_import_for_feed is not None
        else alpaca.historical_import
    )
    result = importer.execute(
        market=request.market,
        instrument=request.instrument,
        timeframe=request.timeframe,
        start_at=request.start,
        end_at=request.end,
        adjustment_policy=AdjustmentPolicy(request.adjustment_policy.lower()),
    )
    return _dataset_response(
        result.snapshot,
        bar_count=result.bar_count,
        actual_start_at=result.actual_start_at,
        actual_end_at=result.actual_end_at,
    )


@app.get(
    "/api/v1/experiments", response_model=ExperimentListResponse, tags=["experiments"]
)
def list_experiments(
    queries: OperatorDependency,
    status: ExperimentStatus | None = None,
    strategy_version_id: UUID | None = None,
    hypothesis_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperimentListResponse:
    items = queries.list_experiments(
        status=status,
        strategy_version_id=strategy_version_id,
        hypothesis_id=hypothesis_id,
        limit=limit,
        offset=offset,
    )
    return ExperimentListResponse(
        items=[experiment_summary(item) for item in items],
        page=PageMetadata(limit=limit, offset=offset, returned=len(items)),
    )


@app.post(
    "/api/v1/experiments",
    response_model=CreateExperimentResponse,
    status_code=201,
    tags=["experiments"],
    summary="Create an experiment from immutable research lineage",
    description=(
        "Binds one existing hypothesis, StrategyVersion, and DatasetSnapshot. "
        "No backtest is executed by this operation."
    ),
)
def create_experiment(
    request: CreateExperimentRequest, workflow: ResearchDependency
) -> CreateExperimentResponse:
    experiment = workflow.create_experiment(
        hypothesis_id=request.hypothesis_id,
        strategy_version_id=request.strategy_version_id,
        dataset_snapshot_id=request.dataset_snapshot_id,
    )
    return CreateExperimentResponse(
        experiment_id=experiment.id,
        hypothesis_id=experiment.hypothesis_id,
        strategy_version_id=experiment.strategy_version_id,
        dataset_snapshot_id=experiment.dataset_snapshot_id,
        status=experiment.status.value,
        created_at=experiment.created_at,
    )


@app.post(
    "/api/v1/experiments/{experiment_id}/runs",
    response_model=RunExperimentResponse,
    status_code=201,
    tags=["experiments"],
    summary="Run a deterministic historical experiment",
    description=(
        "Delegates to the existing RunExperiment application service and persists "
        "the ExperimentRun plus its BACKTEST validation evidence."
    ),
)
def run_experiment(
    experiment_id: UUID,
    request: RunExperimentRequest,
    workflow: ResearchDependency,
) -> RunExperimentResponse:
    fee_model: FeeModel
    if request.fee.model == "zero":
        if request.fee.rate not in (None, 0):
            raise ValueError("zero fee model cannot include a non-zero rate")
        fee_model = ZeroFeeModel()
    else:
        if request.fee.rate is None:
            raise ValueError("percentage fee model requires rate")
        fee_model = PercentageFeeModel(request.fee.rate)
    slippage_model: SlippageModel
    if request.slippage.model == "zero":
        if request.slippage.basis_points not in (None, 0):
            raise ValueError("zero slippage model cannot include basis_points")
        slippage_model = ZeroSlippageModel()
    else:
        if request.slippage.basis_points is None:
            raise ValueError("basis_points slippage model requires basis_points")
        slippage_model = BasisPointsSlippageModel(request.slippage.basis_points)
    result = workflow.run_experiment(
        experiment_id,
        BacktestConfiguration(
            initial_cash=request.initial_cash,
            position_fraction=request.position_fraction,
            fee_model=fee_model,
            slippage_model=slippage_model,
        ),
        AnalyticsConfiguration(
            periods_per_year=request.periods_per_year,
            annual_risk_free_rate=request.annual_risk_free_rate,
        ),
    )
    run = workflow.experiments.get_run(result.experiment_run_id)
    if run is None:
        raise RuntimeError("completed experiment run was not persisted")
    validations = workflow.experiments.list_validations(result.experiment_run_id)
    return RunExperimentResponse(
        experiment_id=result.experiment_id,
        experiment_run_id=result.experiment_run_id,
        dataset_snapshot_id=result.dataset_snapshot_id,
        strategy_version_id=result.strategy_version_id,
        status=run.status.value,
        configuration=json_value(run.configuration),
        result_fingerprint=result.fingerprint,
        validation_ids=[item.id for item in validations],
    )


@app.get(
    "/api/v1/experiments/{experiment_id}",
    response_model=ExperimentDetailResponse,
    tags=["experiments"],
)
def get_experiment(
    experiment_id: UUID, queries: OperatorDependency
) -> ExperimentDetailResponse:
    return experiment_detail(queries.experiment_detail(experiment_id))


@app.get(
    "/api/v1/experiment-runs/{run_id}",
    response_model=ExperimentRunResponse,
    tags=["experiments"],
)
def get_run(run_id: UUID, queries: OperatorDependency) -> ExperimentRunResponse:
    return experiment_run(queries.experiment_run(run_id))


@app.get(
    "/api/v1/experiment-runs/{run_id}/backtest-visualization",
    response_model=BacktestVisualizationResponse,
    tags=["experiments"],
    summary="Read bounded persisted BACKTEST visualization evidence",
)
def get_backtest_visualization(
    run_id: UUID,
    queries: OperatorDependency,
    datasets: DatasetDependency,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    maximum_bars: Annotated[
        int, Query(ge=1, le=MAX_VISUALIZATION_BARS)
    ] = MAX_VISUALIZATION_BARS,
) -> BacktestVisualizationResponse:
    payload = BacktestVisualizationService(
        experiments=queries.experiments,
        strategies=queries.strategies,
        datasets=queries.datasets,
        dataset_loader=datasets.loader,
    ).build(run_id, start_at=start_at, end_at=end_at, maximum_bars=maximum_bars)
    return BacktestVisualizationResponse.model_validate(json_value(payload))


@app.get(
    "/api/v1/experiment-runs/{run_id}/validations",
    response_model=list[ValidationResponse],
    tags=["validations"],
)
def list_validations(
    run_id: UUID,
    queries: OperatorDependency,
    validation_type: ValidationType | None = None,
) -> list[ValidationResponse]:
    return [validation(item) for item in queries.validations(run_id, validation_type)]


@app.get(
    "/api/v1/validations/{validation_id}",
    response_model=ValidationResponse,
    tags=["validations"],
)
def get_validation(
    validation_id: UUID, queries: OperatorDependency
) -> ValidationResponse:
    return validation(queries.validation(validation_id))


def _created_validation(
    services: ValidationDependency, validation_id: UUID
) -> ValidationResponse:
    created = services.experiments.get_validation(validation_id)
    if created is None:
        raise RuntimeError("created validation evidence is unavailable")
    return validation(created)


@app.post(
    "/api/v1/experiment-runs/{run_id}/validations/out-of-sample",
    response_model=ValidationResponse,
    status_code=201,
    tags=["validations"],
)
def run_out_of_sample(
    run_id: UUID, request: OutOfSampleRequest, services: ValidationDependency
) -> ValidationResponse:
    result = services.out_of_sample.execute(
        run_id, OutOfSampleConfiguration(**request.model_dump())
    )
    return _created_validation(services, result.validation_run_id)


@app.post(
    "/api/v1/experiment-runs/{run_id}/validations/walk-forward",
    response_model=ValidationResponse,
    status_code=201,
    tags=["validations"],
)
def run_walk_forward(
    run_id: UUID, request: WalkForwardRequest, services: ValidationDependency
) -> ValidationResponse:
    result = services.walk_forward.execute(
        run_id,
        WalkForwardConfiguration(
            WalkForwardMode(request.mode),
            request.training_window,
            request.test_window,
            request.step,
        ),
    )
    return _created_validation(services, result.validation_run_id)


@app.post(
    "/api/v1/experiment-runs/{run_id}/validations/parameter-sensitivity",
    response_model=ValidationResponse,
    status_code=201,
    tags=["validations"],
)
def run_parameter_sensitivity(
    run_id: UUID,
    request: ParameterSensitivityRequest,
    services: ValidationDependency,
) -> ValidationResponse:
    result = services.sensitivity.execute(
        run_id,
        ParameterSensitivityConfiguration(
            {name: tuple(values) for name, values in request.parameters.items()},
            request.maximum_combinations,
        ),
    )
    return _created_validation(services, result.validation_run_id)


@app.post(
    "/api/v1/experiment-runs/{run_id}/validations/stress",
    response_model=ValidationResponse,
    status_code=201,
    tags=["validations"],
)
def run_stress(
    run_id: UUID, request: StressRequest, services: ValidationDependency
) -> ValidationResponse:
    scenarios = tuple(
        StressScenario(
            item.id,
            item.name,
            StressType(item.stress_type),
            _stress_configuration(StressType(item.stress_type), item.configuration),
        )
        for item in request.scenarios
    )
    result = services.stress.execute(run_id, StressTestingConfiguration(scenarios))
    return _created_validation(services, result.validation_run_id)


def _stress_configuration(
    stress_type: StressType, configuration: dict[str, Any]
) -> dict[str, Any]:
    normalized = dict(configuration)
    decimal_field = {
        StressType.FEE_MULTIPLIER: "multiplier",
        StressType.SLIPPAGE_MULTIPLIER: "multiplier",
        StressType.ADVERSE_PRICE: "additional_basis_points",
    }.get(stress_type)
    if decimal_field is not None and decimal_field in normalized:
        normalized[decimal_field] = Decimal(str(normalized[decimal_field]))
    return normalized


@app.post(
    "/api/v1/experiment-runs/{run_id}/validations/monte-carlo",
    response_model=ValidationResponse,
    status_code=201,
    tags=["validations"],
)
def run_monte_carlo(
    run_id: UUID, request: MonteCarloRequest, services: ValidationDependency
) -> ValidationResponse:
    result = services.monte_carlo.execute(
        run_id,
        MonteCarloConfiguration(
            request.simulation_count,
            request.random_seed,
            tuple(request.confidence_percentiles),
            SamplingMethod(request.sampling_method),
            request.drawdown_threshold,
            request.ruin_equity_fraction,
        ),
    )
    return _created_validation(services, result.validation_run_id)


@app.post(
    "/api/v1/experiment-runs/{run_id}/validations/adversarial-review",
    response_model=ValidationResponse,
    status_code=201,
    tags=["validations"],
)
def run_adversarial_review(
    run_id: UUID, request: AdversarialRequest, services: ValidationDependency
) -> ValidationResponse:
    before = {item.id for item in services.experiments.list_validations(run_id)}
    services.adversarial.execute(
        run_id, AdversarialAnalysisConfiguration(**request.model_dump())
    )
    created = [
        item
        for item in services.experiments.list_validations(run_id)
        if item.id not in before
        and item.validation_type is ValidationType.ADVERSARIAL_REVIEW
    ]
    if len(created) != 1:
        raise RuntimeError("created adversarial evidence is unavailable")
    return validation(created[0])


@app.post(
    "/api/v1/experiment-runs/{run_id}/gate-evaluations",
    response_model=GateResponse,
    status_code=201,
    tags=["gates"],
)
def evaluate_gate(
    run_id: UUID, request: GateEvaluationRequest, services: ValidationDependency
) -> GateResponse:
    policy = ValidationGatePolicy(
        request.policy_id,
        request.policy_version,
        request.policy_name,
        tuple(ValidationType(value) for value in request.required_validations),
        request.require_adversarial_report,
        tuple(
            GateRuleDefinition(GateRuleCode(item.code), item.threshold)
            for item in request.rules
        ),
    )
    evidence = {
        ValidationType(name): identity
        for name, identity in request.evidence_ids.items()
    }
    return gate(services.gate.execute(run_id, policy, evidence))


@app.get(
    "/api/v1/experiment-runs/{run_id}/adversarial-report",
    response_model=list[ValidationResponse],
    tags=["validations"],
)
def get_adversarial_reports(
    run_id: UUID, queries: OperatorDependency
) -> list[ValidationResponse]:
    return [validation(item) for item in queries.adversarial_reports(run_id)]


@app.get(
    "/api/v1/experiment-runs/{run_id}/gate-evaluations",
    response_model=list[GateResponse],
    tags=["gates"],
)
def list_gate_evaluations(
    run_id: UUID, queries: OperatorDependency
) -> list[GateResponse]:
    return [gate(item) for item in queries.gate_evaluations(run_id)]


@app.get(
    "/api/v1/gate-evaluations/{gate_id}", response_model=GateResponse, tags=["gates"]
)
def get_gate_evaluation(gate_id: UUID, queries: OperatorDependency) -> GateResponse:
    return gate(queries.gate_evaluation(gate_id))


@app.get(
    "/api/v1/strategy-versions/{version_id}",
    response_model=dict[str, Any],
    tags=["strategies"],
)
def get_strategy_version(
    version_id: UUID, queries: OperatorDependency
) -> dict[str, Any]:
    mapped = json_value(queries.strategy_version(version_id))
    if not isinstance(mapped, dict):
        raise TypeError("strategy version mapping must be an object")
    return mapped


@app.post(
    "/api/v1/strategy-versions",
    response_model=StrategyVersionCreateResponse,
    status_code=201,
    tags=["strategies"],
    summary="Create an immutable executable StrategyVersion",
    description=(
        "Creates the strategy container and its first immutable version after "
        "validating the algorithm key and parameters against the executable registry."
    ),
)
def create_strategy_version(
    request: CreateStrategyVersionRequest, workflow: ResearchDependency
) -> StrategyVersionCreateResponse:
    strategy, version = workflow.create_strategy_version(
        name=request.name,
        description=request.description,
        strategy_family=request.strategy_family,
        version=request.version,
        git_commit=request.git_commit,
        algorithm_key=request.algorithm_key,
        parameters=request.parameters,
    )
    return StrategyVersionCreateResponse(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        name=strategy.name,
        version=version.version,
        algorithm_key=version.algorithm_key,
        parameters=json_value(version.parameters),
        created_at=version.created_at,
    )


@app.get(
    "/api/v1/hypotheses", response_model=HypothesisListResponse, tags=["hypotheses"]
)
def list_hypotheses(
    queries: OperatorDependency,
    status: HypothesisStatus | None = None,
    strategy_family: str | None = None,
    market: str | None = None,
    instrument: str | None = None,
    timeframe: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HypothesisListResponse:
    items = queries.list_hypotheses(
        status=status,
        strategy_family=strategy_family,
        market=market,
        instrument=instrument,
        timeframe=timeframe,
        limit=limit,
        offset=offset,
    )
    return HypothesisListResponse(
        items=[hypothesis(item) for item in items],
        page=PageMetadata(limit=limit, offset=offset, returned=len(items)),
    )


@app.post(
    "/api/v1/hypotheses",
    response_model=HypothesisResponse,
    status_code=201,
    tags=["hypotheses"],
    summary="Register an active research hypothesis",
    description=(
        "Runs deterministic prior-art checks before persisting the hypothesis and "
        "its initial knowledge record. Exact duplicates return HTTP 409."
    ),
)
def create_hypothesis(
    request: CreateHypothesisRequest, workflow: ResearchDependency
) -> HypothesisResponse:
    created = workflow.create_hypothesis(
        title=request.title,
        description=request.description,
        rationale=request.rationale,
        strategy_family=request.strategy_family,
        market=request.market,
        instrument=request.instrument,
        timeframe=request.timeframe,
        parameters=request.parameters,
        expected_benefit=request.expected_benefit,
        expected_tradeoff=request.expected_tradeoff,
        success_criteria=request.success_criteria,
        rejection_criteria=request.rejection_criteria,
        reconsideration_conditions=request.reconsideration_conditions,
        numeric_parameter_relative_tolerance=(
            request.numeric_parameter_relative_tolerance
        ),
        derived_from_hypothesis_id=request.derived_from_hypothesis_id,
    )
    return hypothesis(created)


@app.get(
    "/api/v1/hypotheses/{hypothesis_id}",
    response_model=HypothesisDetailResponse,
    tags=["hypotheses"],
)
def get_hypothesis(
    hypothesis_id: UUID, queries: OperatorDependency
) -> HypothesisDetailResponse:
    detail = queries.hypothesis_detail(hypothesis_id)
    return HypothesisDetailResponse(
        hypothesis=json_value(detail.hypothesis),
        experiments=[json_value(item) for item in detail.experiments],
        knowledge=[json_value(item) for item in detail.knowledge],
        derived_hypothesis_ids=list(detail.derived_hypothesis_ids),
    )


@app.get("/api/v1/knowledge", response_model=KnowledgeListResponse, tags=["knowledge"])
def list_knowledge(
    queries: OperatorDependency,
    status: HypothesisStatus | None = None,
    strategy_family: str | None = None,
    market: str | None = None,
    instrument: str | None = None,
    timeframe: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KnowledgeListResponse:
    items = queries.search_knowledge(
        KnowledgeQuery(strategy_family, market, instrument, timeframe, status),
        limit=limit,
        offset=offset,
    )
    return KnowledgeListResponse(
        items=[knowledge(item) for item in items],
        page=PageMetadata(limit=limit, offset=offset, returned=len(items)),
    )


@app.post(
    "/api/v1/knowledge/prior-art-check",
    response_model=PriorArtResponse,
    tags=["knowledge"],
)
def post_prior_art(
    request: PriorArtRequest, queries: OperatorDependency
) -> PriorArtResponse:
    result = CheckPriorArt(queries.knowledge).execute(
        ResearchSignature(
            strategy_family=request.strategy_family,
            market=request.market,
            instrument=request.instrument,
            timeframe=request.timeframe,
            parameters=request.parameters,
            execution_model=request.execution_model,
            cost_model=request.cost_model,
            regime_scope=request.regime_scope,
        ),
        PriorArtConfiguration(request.numeric_parameter_relative_tolerance),
    )
    return prior_art(result)


@app.get(
    "/api/v1/operator-summary",
    response_model=DashboardSummaryResponse,
    tags=["operator"],
)
def operator_summary(queries: OperatorDependency) -> DashboardSummaryResponse:
    summary = queries.dashboard_summary()
    return DashboardSummaryResponse(
        active_experiments=summary.active_experiments,
        completed_experiments=summary.completed_experiments,
        rejected_hypotheses=summary.rejected_hypotheses,
        eligible_for_paper=summary.eligible_for_paper,
        failed_gates=summary.failed_gates,
        high_findings=summary.high_findings,
        warning_findings=summary.warning_findings,
        knowledge_by_status={
            key.value: value for key, value in summary.knowledge_by_status.items()
        },
    )


def _paper_participant(
    value: PaperParticipant, papers: PaperDependency
) -> PaperParticipantResponse:
    snapshot = papers.repository.latest_snapshot(value.id)
    current_equity = None
    current_cash = None
    open_position = None
    latest_fill = None
    latest_signal = None
    metrics = None
    processed_bars = 0
    if snapshot is not None:
        processed_bars = snapshot.processed_bar_count
        mapped_metrics = json_value(snapshot.metrics)
        if isinstance(mapped_metrics, dict):
            metrics = mapped_metrics
        backtest = snapshot.material_result.get("backtest")
        if isinstance(backtest, dict) and backtest.get("final_equity") is not None:
            current_equity = float(str(backtest["final_equity"]))
            current_cash = float(str(backtest["final_cash"]))
            raw_position = backtest.get("open_position")
            if isinstance(raw_position, dict):
                open_position = raw_position
            fills = backtest.get("fills")
            if isinstance(fills, list) and fills and isinstance(fills[-1], dict):
                latest_fill = fills[-1]
        signals = snapshot.material_result.get("signals")
        if isinstance(signals, list) and signals and isinstance(signals[-1], dict):
            latest_signal = signals[-1]
    return PaperParticipantResponse(
        id=value.id,
        session_id=value.session_id,
        strategy_version_id=value.strategy_version_id,
        source_gate_evaluation_id=value.source_gate_evaluation_id,
        status=value.status.value,
        initial_capital=float(value.initial_capital),
        paper_engine_version=value.paper_engine_version,
        started_at=value.started_at,
        stopped_at=value.stopped_at,
        last_processed_at=value.last_processed_at,
        last_successful_at=value.last_successful_at,
        last_error=value.last_error,
        processed_bars=processed_bars,
        current_cash=current_cash,
        current_equity=current_equity,
        open_position=open_position,
        latest_signal=latest_signal,
        latest_fill=latest_fill,
        metrics=metrics,
    )


def _paper_session(
    value: PaperSession, papers: PaperDependency
) -> PaperSessionResponse:
    return PaperSessionResponse(
        id=value.id,
        market=value.market,
        instrument=value.instrument,
        timeframe=value.timeframe,
        provider_name=value.provider_name,
        provider_version=value.provider_version,
        dataset_snapshot_id=value.dataset_snapshot_id,
        dataset_checksum=value.dataset_checksum,
        evaluation_start=value.evaluation_start,
        status=value.status.value,
        started_at=value.started_at,
        completed_at=value.completed_at,
        last_processed_at=value.last_processed_at,
        last_error=value.last_error,
        created_at=value.created_at,
        participant_count=len(papers.repository.list_participants(value.id)),
    )


@app.get(
    "/api/v1/paper/sessions", response_model=list[PaperSessionResponse], tags=["paper"]
)
def list_paper_sessions(papers: PaperDependency) -> list[PaperSessionResponse]:
    return [_paper_session(item, papers) for item in papers.repository.list_sessions()]


@app.post("/api/v1/paper/sessions", response_model=PaperSessionResponse, tags=["paper"])
def create_paper_session(
    request: CreatePaperSessionRequest, papers: PaperDependency
) -> PaperSessionResponse:
    return _paper_session(
        papers.create_session.execute(
            request.dataset_snapshot_id, request.evaluation_start, request.feed_mode
        ),
        papers,
    )


@app.get(
    "/api/v1/paper/sessions/{session_id}",
    response_model=PaperSessionDetailResponse,
    tags=["paper"],
)
def get_paper_session(
    session_id: UUID, papers: PaperDependency
) -> PaperSessionDetailResponse:
    session = papers.repository.get_session(session_id)
    if session is None:
        raise LookupError(f"paper session {session_id} was not found")
    participants = papers.repository.list_participants(session_id)
    return PaperSessionDetailResponse(
        session=_paper_session(session, papers),
        participants=[_paper_participant(item, papers) for item in participants],
    )


@app.post(
    "/api/v1/paper/sessions/{session_id}/participants",
    response_model=PaperParticipantResponse,
    tags=["paper"],
)
def add_paper_participant(
    session_id: UUID,
    request: AddPaperParticipantRequest,
    papers: PaperDependency,
) -> PaperParticipantResponse:
    return _paper_participant(
        papers.add_participant.execute(session_id, request.gate_evaluation_id), papers
    )


@app.post(
    "/api/v1/paper/sessions/{session_id}/start",
    response_model=PaperSessionResponse,
    tags=["paper"],
)
def start_paper_session(
    session_id: UUID, papers: PaperDependency
) -> PaperSessionResponse:
    return _paper_session(papers.lifecycle.start_session(session_id), papers)


@app.post(
    "/api/v1/paper/sessions/{session_id}/pause",
    response_model=PaperSessionResponse,
    tags=["paper"],
)
def pause_paper_session(
    session_id: UUID, papers: PaperDependency
) -> PaperSessionResponse:
    return _paper_session(papers.lifecycle.pause_session(session_id), papers)


@app.post(
    "/api/v1/paper/sessions/{session_id}/process-next",
    response_model=PaperProcessingResponse,
    tags=["paper"],
)
def process_next_replay_bar(
    session_id: UUID, papers: PaperDependency
) -> PaperProcessingResponse:
    result = papers.advance.execute(session_id)
    return PaperProcessingResponse(
        session_id=result.session.id,
        observation_timestamp=(
            result.observation.bar.timestamp if result.observation else None
        ),
        processed_participant_ids=[item.participant_id for item in result.snapshots],
        duplicate=result.duplicate,
        completed=result.completed,
    )


@app.post(
    "/api/v1/paper/sessions/{session_id}/poll-alpaca-iex",
    response_model=PaperProcessingResponse,
    tags=["paper"],
    summary="Poll one forward Alpaca IEX bar into INTERNAL paper simulation",
)
def poll_alpaca_paper_bar(
    session_id: UUID,
    papers: PaperDependency,
    alpaca: AlpacaDependency,
) -> PaperProcessingResponse:
    session = papers.repository.get_session(session_id)
    if session is None:
        raise LookupError(f"paper session {session_id} was not found")
    if papers.advance_live is None:
        raise PaperArenaError("Alpaca live paper processing is not configured")
    result = papers.advance_live.execute(
        session_id,
        AlpacaLiveMarketDataProvider(
            alpaca.client, session.instrument, session.last_processed_at
        ),
    )
    return PaperProcessingResponse(
        session_id=result.session.id,
        observation_timestamp=(
            result.observation.bar.timestamp if result.observation else None
        ),
        processed_participant_ids=[item.participant_id for item in result.snapshots],
        duplicate=result.duplicate,
        completed=result.completed,
    )


@app.get(
    "/api/v1/paper/participants/{participant_id}",
    response_model=PaperParticipantResponse,
    tags=["paper"],
)
def get_paper_participant(
    participant_id: UUID, papers: PaperDependency
) -> PaperParticipantResponse:
    participant = papers.repository.get_participant(participant_id)
    if participant is None:
        raise LookupError(f"paper participant {participant_id} was not found")
    return _paper_participant(participant, papers)


@app.post(
    "/api/v1/paper/participants/{participant_id}/pause",
    response_model=PaperParticipantResponse,
    tags=["paper"],
)
def pause_paper_participant(
    participant_id: UUID, papers: PaperDependency
) -> PaperParticipantResponse:
    return _paper_participant(
        papers.lifecycle.pause_participant(participant_id), papers
    )


@app.post(
    "/api/v1/paper/participants/{participant_id}/stop",
    response_model=PaperParticipantResponse,
    tags=["paper"],
)
def stop_paper_participant(
    participant_id: UUID, papers: PaperDependency
) -> PaperParticipantResponse:
    return _paper_participant(papers.lifecycle.stop_participant(participant_id), papers)


def _paper_artifacts(
    participant_id: UUID, key: str, papers: PaperDependency
) -> PaperArtifactListResponse:
    if papers.repository.get_participant(participant_id) is None:
        raise LookupError(f"paper participant {participant_id} was not found")
    snapshot = papers.repository.latest_snapshot(participant_id)
    items: list[dict[str, Any]] = []
    if snapshot is not None:
        backtest = snapshot.material_result.get("backtest")
        raw = backtest.get(key) if isinstance(backtest, dict) else None
        if isinstance(raw, list):
            items = [item for item in raw if isinstance(item, dict)]
    return PaperArtifactListResponse(participant_id=participant_id, items=items)


@app.get(
    "/api/v1/paper/participants/{participant_id}/orders",
    response_model=PaperArtifactListResponse,
    tags=["paper"],
)
def get_paper_orders(
    participant_id: UUID, papers: PaperDependency
) -> PaperArtifactListResponse:
    return _paper_artifacts(participant_id, "orders", papers)


@app.get(
    "/api/v1/paper/participants/{participant_id}/trades",
    response_model=PaperArtifactListResponse,
    tags=["paper"],
)
def get_paper_trades(
    participant_id: UUID, papers: PaperDependency
) -> PaperArtifactListResponse:
    return _paper_artifacts(participant_id, "trades", papers)


@app.get(
    "/api/v1/paper/participants/{participant_id}/metrics",
    response_model=PaperParticipantResponse,
    tags=["paper"],
)
def get_paper_metrics(
    participant_id: UUID, papers: PaperDependency
) -> PaperParticipantResponse:
    return get_paper_participant(participant_id, papers)


@app.get(
    "/api/v1/brokers/alpaca/paper/connectivity",
    response_model=dict[str, Any],
    tags=["alpaca-paper"],
    summary="Verify the configured Alpaca simulated account",
)
def alpaca_paper_connectivity(alpaca: AlpacaDependency) -> dict[str, Any]:
    account = alpaca.broker.get_account()
    return {
        "status": "ok",
        "broker": "alpaca",
        "execution_environment": "paper",
        "simulated": True,
        "account_status": account.status,
    }


@app.get(
    "/api/v1/brokers/alpaca/paper/account",
    response_model=AlpacaPaperAccountResponse,
    tags=["alpaca-paper"],
    summary="Read Alpaca PAPER account balances",
)
def alpaca_paper_account(alpaca: AlpacaDependency) -> AlpacaPaperAccountResponse:
    return AlpacaPaperAccountResponse(**asdict(alpaca.broker.get_account()))


@app.post(
    "/api/v1/brokers/alpaca/paper/orders",
    response_model=AlpacaPaperOrderResponse,
    status_code=201,
    tags=["alpaca-paper"],
    summary="Submit an Alpaca PAPER market order",
)
def submit_alpaca_paper_order(
    request: SubmitAlpacaPaperOrderRequest, alpaca: AlpacaDependency
) -> AlpacaPaperOrderResponse:
    try:
        command = SubmitAlpacaPaperOrder(
            symbol=request.symbol,
            quantity=request.quantity,
            side=PaperOrderSide(request.side.lower()),
            order_type=PaperOrderType(request.type.lower()),
            time_in_force=PaperTimeInForce(request.time_in_force.lower()),
            client_order_id=request.client_order_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return AlpacaPaperOrderResponse(**asdict(alpaca.broker.submit_order(command)))


@app.get(
    "/api/v1/brokers/alpaca/paper/orders",
    response_model=list[AlpacaPaperOrderResponse],
    tags=["alpaca-paper"],
    summary="List Alpaca PAPER orders",
)
def list_alpaca_paper_orders(
    alpaca: AlpacaDependency,
    status: str = Query("open", pattern="^(open|closed|all)$"),
) -> list[AlpacaPaperOrderResponse]:
    return [
        AlpacaPaperOrderResponse(**asdict(item))
        for item in alpaca.broker.list_orders(status)
    ]


@app.get(
    "/api/v1/brokers/alpaca/paper/orders/{order_id}",
    response_model=AlpacaPaperOrderResponse,
    tags=["alpaca-paper"],
    summary="Get one Alpaca PAPER order",
)
def get_alpaca_paper_order(
    order_id: str, alpaca: AlpacaDependency
) -> AlpacaPaperOrderResponse:
    return AlpacaPaperOrderResponse(**asdict(alpaca.broker.get_order(order_id)))


@app.get(
    "/api/v1/brokers/alpaca/paper/positions",
    response_model=list[AlpacaPaperPositionResponse],
    tags=["alpaca-paper"],
    summary="List Alpaca PAPER positions",
)
def list_alpaca_paper_positions(
    alpaca: AlpacaDependency,
) -> list[AlpacaPaperPositionResponse]:
    return [
        AlpacaPaperPositionResponse(**asdict(item))
        for item in alpaca.broker.list_positions()
    ]


@app.get(
    "/api/v1/brokers/alpaca/paper/positions/{symbol}",
    response_model=AlpacaPaperPositionResponse,
    tags=["alpaca-paper"],
    summary="Get one Alpaca PAPER position",
)
def get_alpaca_paper_position(
    symbol: str, alpaca: AlpacaDependency
) -> AlpacaPaperPositionResponse:
    return AlpacaPaperPositionResponse(**asdict(alpaca.broker.get_position(symbol)))


@app.delete(
    "/api/v1/brokers/alpaca/paper/positions/{symbol}",
    response_model=AlpacaPaperOrderResponse,
    tags=["alpaca-paper"],
    summary="Close one Alpaca PAPER position",
)
def close_alpaca_paper_position(
    symbol: str,
    alpaca: AlpacaDependency,
    confirm: bool = Query(False, description="Must be true for this PAPER write"),
) -> AlpacaPaperOrderResponse:
    if not confirm:
        raise HTTPException(
            status_code=409, detail="confirm=true is required to close a PAPER position"
        )
    return AlpacaPaperOrderResponse(**asdict(alpaca.broker.close_position(symbol)))


@app.get(
    "/api/v1/brokers/alpaca/paper/fills",
    response_model=list[AlpacaPaperFillResponse],
    tags=["alpaca-paper"],
    summary="List recent Alpaca PAPER fill activities",
)
def list_alpaca_paper_fills(
    alpaca: AlpacaDependency,
) -> list[AlpacaPaperFillResponse]:
    return [
        AlpacaPaperFillResponse(**asdict(item)) for item in alpaca.broker.list_fills()
    ]


_dashboard = Path(__file__).resolve().parents[1] / "dashboard"
app.mount("/dashboard", StaticFiles(directory=_dashboard, html=True), name="dashboard")
