from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from quant.domain._validation import (
    as_utc,
    immutable_mapping,
    require_enum,
    require_text,
    require_uuid,
)
from quant.domain.dataset import AdjustmentPolicy
from quant.domain.market_data import MarketBar
from quant.domain.validation import MetricSet


class PaperSessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class PaperParticipantStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class PaperSession:
    id: UUID
    market: str
    instrument: str
    timeframe: str
    adjustment_policy: AdjustmentPolicy
    provider_name: str
    provider_version: str
    dataset_snapshot_id: UUID
    dataset_checksum: str
    evaluation_start: datetime
    warmup_bars: tuple[MarketBar, ...]
    status: PaperSessionStatus
    started_at: datetime | None
    completed_at: datetime | None
    last_processed_at: datetime | None
    last_error: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.dataset_snapshot_id, "dataset_snapshot_id")
        for name in (
            "market",
            "instrument",
            "timeframe",
            "provider_name",
            "provider_version",
            "dataset_checksum",
        ):
            require_text(getattr(self, name), name)
        require_enum(self.status, PaperSessionStatus, "status")
        require_enum(self.adjustment_policy, AdjustmentPolicy, "adjustment_policy")
        object.__setattr__(
            self, "evaluation_start", as_utc(self.evaluation_start, "evaluation_start")
        )
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))
        for name in ("started_at", "completed_at", "last_processed_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, as_utc(value, name))
        if any(bar.timestamp >= self.evaluation_start for bar in self.warmup_bars):
            raise ValueError("warm-up bars must precede paper evaluation start")


@dataclass(frozen=True, slots=True)
class PaperParticipant:
    id: UUID
    session_id: UUID
    strategy_version_id: UUID
    source_gate_evaluation_id: UUID
    status: PaperParticipantStatus
    initial_capital: Decimal
    execution_configuration: Mapping[str, object]
    paper_engine_version: str
    started_at: datetime | None
    stopped_at: datetime | None
    last_processed_at: datetime | None
    last_successful_at: datetime | None
    last_error: str | None
    created_at: datetime
    paper_promotion_id: UUID | None = None

    def __post_init__(self) -> None:
        for name in (
            "id",
            "session_id",
            "strategy_version_id",
            "source_gate_evaluation_id",
        ):
            require_uuid(getattr(self, name), name)
        if self.paper_promotion_id is not None:
            require_uuid(self.paper_promotion_id, "paper_promotion_id")
        require_enum(self.status, PaperParticipantStatus, "status")
        require_text(self.paper_engine_version, "paper_engine_version")
        if not self.initial_capital.is_finite() or self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        object.__setattr__(
            self,
            "execution_configuration",
            immutable_mapping(self.execution_configuration),
        )
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))
        for name in (
            "started_at",
            "stopped_at",
            "last_processed_at",
            "last_successful_at",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, as_utc(value, name))


@dataclass(frozen=True, slots=True)
class PaperObservation:
    id: UUID
    session_id: UUID
    bar: MarketBar
    content_checksum: str
    processed_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.session_id, "session_id")
        require_text(self.content_checksum, "content_checksum")
        object.__setattr__(
            self, "processed_at", as_utc(self.processed_at, "processed_at")
        )


@dataclass(frozen=True, slots=True)
class PaperSnapshot:
    id: UUID
    participant_id: UUID
    observation_id: UUID
    observation_timestamp: datetime
    processed_bar_count: int
    material_result: Mapping[str, object]
    metrics: MetricSet
    fingerprint: str
    created_at: datetime

    def __post_init__(self) -> None:
        for name in ("id", "participant_id", "observation_id"):
            require_uuid(getattr(self, name), name)
        if self.processed_bar_count <= 0:
            raise ValueError("processed_bar_count must be positive")
        require_text(self.fingerprint, "fingerprint")
        object.__setattr__(
            self, "material_result", immutable_mapping(self.material_result)
        )
        object.__setattr__(
            self,
            "observation_timestamp",
            as_utc(self.observation_timestamp, "observation_timestamp"),
        )
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class PaperParticipantComparison:
    participant_id: UUID
    strategy_version_id: UUID
    status: PaperParticipantStatus
    processed_bars: int
    metrics: MetricSet | None
    current_equity: Decimal | None
