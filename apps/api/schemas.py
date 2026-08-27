from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PageMetadata(BaseModel):
    limit: int
    offset: int
    returned: int


class DatasetSnapshotResponse(BaseModel):
    id: UUID
    provider: str
    feed: str | None
    market: str
    instrument: str
    timeframe: str
    requested_start_at: datetime
    requested_end_at: datetime
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    bar_count: int | None = None
    adjustment_policy: str
    checksum: str
    storage_location: str
    created_at: datetime


class DatasetSnapshotListResponse(BaseModel):
    items: list[DatasetSnapshotResponse]
    page: PageMetadata


class HistoricalImportRequest(BaseModel):
    provider: Literal["ALPACA"] = "ALPACA"
    instrument: str
    market: str = "US_EQUITIES"
    timeframe: Literal["1Day", "1Min"] = "1Day"
    start: datetime
    end: datetime
    feed: Literal["iex"] = "iex"
    adjustment_policy: Literal["raw", "adjusted", "RAW", "ADJUSTED"] = "raw"


class ExperimentSummaryResponse(BaseModel):
    experiment_id: UUID
    hypothesis_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    status: str
    created_at: datetime
    latest_run_id: UUID | None
    latest_run_status: str | None
    validation_coverage: list[str]
    latest_gate_decision: str | None


class ExperimentListResponse(BaseModel):
    items: list[ExperimentSummaryResponse]
    page: PageMetadata


class ExperimentDetailResponse(BaseModel):
    experiment: dict[str, Any]
    hypothesis: dict[str, Any]
    strategy: dict[str, Any]
    strategy_version: dict[str, Any]
    dataset_snapshot: dict[str, Any]
    runs: list[dict[str, Any]]


class ExperimentRunResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    status: str
    git_commit: str
    engine_version: str
    fee_model_version: str
    slippage_model_version: str
    analytics_version: str | None
    result_fingerprint: str | None
    configuration: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None


class ValidationResponse(BaseModel):
    id: UUID
    experiment_run_id: UUID
    validation_type: str
    status: str
    metrics: dict[str, Any] | None
    evidence: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None


class HypothesisResponse(BaseModel):
    id: UUID
    title: str
    description: str
    strategy_family: str
    market: str
    timeframe: str
    status: str
    reconsideration_conditions: str | None
    created_at: datetime


class HypothesisListResponse(BaseModel):
    items: list[HypothesisResponse]
    page: PageMetadata


class CreateHypothesisRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    market: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    parameters: dict[str, Any]
    expected_benefit: str = Field(min_length=1)
    expected_tradeoff: str = Field(min_length=1)
    success_criteria: str = Field(min_length=1)
    rejection_criteria: str = Field(min_length=1)
    reconsideration_conditions: str | None = None
    numeric_parameter_relative_tolerance: float = Field(default=0.02, ge=0, le=1)
    derived_from_hypothesis_id: UUID | None = None


class CreateStrategyVersionRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    version: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    algorithm_key: str = Field(min_length=1)
    parameters: dict[str, Any]


class StrategyVersionCreateResponse(BaseModel):
    strategy_id: UUID
    strategy_version_id: UUID
    name: str
    version: str
    algorithm_key: str
    parameters: dict[str, Any]
    created_at: datetime


class CreateExperimentRequest(BaseModel):
    hypothesis_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID


class CreateExperimentResponse(BaseModel):
    experiment_id: UUID
    hypothesis_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    status: str
    created_at: datetime


class FeeConfigurationRequest(BaseModel):
    model: Literal["zero", "percentage"]
    rate: Decimal | None = Field(default=None, ge=0)


class SlippageConfigurationRequest(BaseModel):
    model: Literal["zero", "basis_points"]
    basis_points: Decimal | None = Field(default=None, ge=0, lt=10_000)


class RunExperimentRequest(BaseModel):
    initial_cash: Decimal = Field(gt=0)
    position_fraction: Decimal = Field(gt=0, le=1)
    fee: FeeConfigurationRequest
    slippage: SlippageConfigurationRequest
    periods_per_year: int = Field(gt=0)
    annual_risk_free_rate: Decimal = Field(default=Decimal(0), gt=-1)


class RunExperimentResponse(BaseModel):
    experiment_id: UUID
    experiment_run_id: UUID
    dataset_snapshot_id: UUID
    strategy_version_id: UUID
    status: str
    configuration: dict[str, Any]
    result_fingerprint: str
    validation_ids: list[UUID]


class HypothesisDetailResponse(BaseModel):
    hypothesis: dict[str, Any]
    experiments: list[dict[str, Any]]
    knowledge: list[dict[str, Any]]
    derived_hypothesis_ids: list[UUID]


class KnowledgeResponse(BaseModel):
    id: UUID
    hypothesis_id: UUID
    derived_from_hypothesis_id: UUID | None
    status: str
    signature: dict[str, Any]
    tested_start_at: datetime | None
    tested_end_at: datetime | None
    summary: str
    rejection_reason: str | None
    reconsideration_conditions: list[str]
    reconsideration_rationale: str | None
    evidence_refs: list[dict[str, Any]]
    research_fingerprint: str
    created_at: datetime


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeResponse]
    page: PageMetadata


class PriorArtRequest(BaseModel):
    strategy_family: str
    market: str
    instrument: str
    timeframe: str
    parameters: dict[str, Any]
    execution_model: str | None = None
    cost_model: str | None = None
    regime_scope: str | None = None
    numeric_parameter_relative_tolerance: float = Field(ge=0, le=1)


class PriorArtResponse(BaseModel):
    candidate_fingerprint: str
    duplicate_detected: bool
    blocked_by_rejected_prior_art: bool
    exact_matches: list[dict[str, Any]]
    similar_matches: list[dict[str, Any]]
    rejected_matches: list[dict[str, Any]]
    fingerprint: str


class GateResponse(BaseModel):
    id: UUID
    experiment_run_id: UUID
    strategy_version_id: UUID
    policy_id: str
    policy_version: int
    decision: str
    rule_results: list[dict[str, Any]]
    source_evidence: dict[str, Any]
    policy: dict[str, Any]
    evaluator_version: str
    evaluated_at: datetime
    fingerprint: str
    decision_semantics: str


class DashboardSummaryResponse(BaseModel):
    active_experiments: int
    completed_experiments: int
    rejected_hypotheses: int
    eligible_for_paper: int
    failed_gates: int
    high_findings: int
    warning_findings: int
    knowledge_by_status: dict[str, int]


class CreatePaperSessionRequest(BaseModel):
    dataset_snapshot_id: UUID
    evaluation_start: datetime
    feed_mode: Literal["replay", "alpaca_iex"] = "replay"


class AddPaperParticipantRequest(BaseModel):
    gate_evaluation_id: UUID


class PaperSessionResponse(BaseModel):
    id: UUID
    market: str
    instrument: str
    timeframe: str
    provider_name: str
    provider_version: str
    dataset_snapshot_id: UUID
    dataset_checksum: str
    evaluation_start: datetime
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    last_processed_at: datetime | None
    last_error: str | None
    created_at: datetime
    participant_count: int
    execution_mode: Literal["internal_paper"] = "internal_paper"


class PaperParticipantResponse(BaseModel):
    id: UUID
    session_id: UUID
    strategy_version_id: UUID
    source_gate_evaluation_id: UUID
    status: str
    initial_capital: float
    paper_engine_version: str
    started_at: datetime | None
    stopped_at: datetime | None
    last_processed_at: datetime | None
    last_successful_at: datetime | None
    last_error: str | None
    processed_bars: int
    current_cash: float | None
    current_equity: float | None
    open_position: dict[str, Any] | None
    latest_signal: dict[str, Any] | None
    latest_fill: dict[str, Any] | None
    metrics: dict[str, Any] | None


class PaperSessionDetailResponse(BaseModel):
    session: PaperSessionResponse
    participants: list[PaperParticipantResponse]


class PaperProcessingResponse(BaseModel):
    session_id: UUID
    observation_timestamp: datetime | None
    processed_participant_ids: list[UUID]
    duplicate: bool
    completed: bool


class PaperArtifactListResponse(BaseModel):
    participant_id: UUID
    items: list[dict[str, Any]]


class AlpacaPaperAccountResponse(BaseModel):
    account_id: str
    account_number: str
    status: str
    currency: str
    cash: Decimal
    buying_power: Decimal
    equity: Decimal
    portfolio_value: Decimal
    trading_blocked: bool
    pattern_day_trader: bool
    simulated: bool


class SubmitAlpacaPaperOrderRequest(BaseModel):
    symbol: str
    quantity: Decimal = Field(gt=0)
    side: Literal["buy", "sell", "BUY", "SELL"]
    type: Literal["market", "MARKET"] = "market"
    time_in_force: Literal["day", "DAY"] = "day"
    client_order_id: str = Field(min_length=1, max_length=128)


class AlpacaPaperOrderResponse(BaseModel):
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    time_in_force: str
    status: str
    quantity: Decimal
    filled_quantity: Decimal
    filled_average_price: Decimal | None
    submitted_at: datetime | None
    filled_at: datetime | None
    simulated: bool


class AlpacaPaperPositionResponse(BaseModel):
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    market_value: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    simulated: bool


class AlpacaPaperFillResponse(BaseModel):
    activity_id: str
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    transaction_time: datetime
    activity_type: str
    simulated: bool
