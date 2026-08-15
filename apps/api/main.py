from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from apps.api.dependencies import OperatorDependency
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
    DashboardSummaryResponse,
    ExperimentDetailResponse,
    ExperimentListResponse,
    ExperimentRunResponse,
    GateResponse,
    HypothesisDetailResponse,
    HypothesisListResponse,
    KnowledgeListResponse,
    PageMetadata,
    PriorArtRequest,
    PriorArtResponse,
    ValidationResponse,
)
from quant.application import CheckPriorArt, OperatorResourceNotFound
from quant.domain import ExperimentStatus, HypothesisStatus, ValidationType
from quant.domain.knowledge import (
    KnowledgeQuery,
    PriorArtConfiguration,
    ResearchSignature,
)

app = FastAPI(
    title="Quant Lab Operator API",
    version="1.0.0",
    description="Read-oriented access to deterministic Quant Lab research evidence.",
)


@app.exception_handler(OperatorResourceNotFound)
async def not_found_handler(
    request: Request, error: OperatorResourceNotFound
) -> JSONResponse:
    del request
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


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


_dashboard = Path(__file__).resolve().parents[1] / "dashboard"
app.mount("/dashboard", StaticFiles(directory=_dashboard, html=True), name="dashboard")
