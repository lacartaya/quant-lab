from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from quant.domain._validation import (
    as_utc,
    immutable_mapping,
    require_enum,
    require_uuid,
)


class ValidationType(StrEnum):
    BACKTEST = "backtest"
    OUT_OF_SAMPLE = "out_of_sample"
    WALK_FORWARD = "walk_forward"
    STRESS = "stress"
    MONTE_CARLO = "monte_carlo"


class ValidationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MetricSet:
    total_return: float | None = None
    cagr: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    profit_factor: float | None = None
    win_rate: float | None = None
    expectancy: float | None = None
    trade_count: int | None = None

    def __post_init__(self) -> None:
        if self.trade_count is not None and self.trade_count < 0:
            raise ValueError("trade_count cannot be negative")


@dataclass(frozen=True, slots=True)
class ValidationRun:
    id: UUID
    experiment_run_id: UUID
    validation_type: ValidationType
    status: ValidationStatus
    metric_set: MetricSet | None
    configuration: Mapping[str, object]
    created_at: datetime
    completed_at: datetime | None

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.experiment_run_id, "experiment_run_id")
        require_enum(self.validation_type, ValidationType, "validation_type")
        require_enum(self.status, ValidationStatus, "status")
        created_at = as_utc(self.created_at, "created_at")
        completed_at = (
            as_utc(self.completed_at, "completed_at")
            if self.completed_at is not None
            else None
        )
        if completed_at is not None and completed_at < created_at:
            raise ValueError("completed_at cannot be before created_at")
        object.__setattr__(self, "configuration", immutable_mapping(self.configuration))
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "completed_at", completed_at)
