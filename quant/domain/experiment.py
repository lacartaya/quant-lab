from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from quant.domain._validation import (
    as_utc,
    immutable_mapping,
    require_enum,
    require_text,
    require_uuid,
)


class ExperimentStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ExperimentRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Experiment:
    id: UUID
    hypothesis_id: UUID
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    status: ExperimentStatus
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.hypothesis_id, "hypothesis_id")
        require_uuid(self.strategy_version_id, "strategy_version_id")
        require_uuid(self.dataset_snapshot_id, "dataset_snapshot_id")
        require_enum(self.status, ExperimentStatus, "status")
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ExperimentRun:
    id: UUID
    experiment_id: UUID
    git_commit: str
    engine_version: str
    fee_model_version: str
    slippage_model_version: str
    configuration: Mapping[str, object]
    started_at: datetime
    completed_at: datetime | None
    status: ExperimentRunStatus

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.experiment_id, "experiment_id")
        require_text(self.git_commit, "git_commit")
        require_text(self.engine_version, "engine_version")
        require_text(self.fee_model_version, "fee_model_version")
        require_text(self.slippage_model_version, "slippage_model_version")
        require_enum(self.status, ExperimentRunStatus, "status")
        started_at = as_utc(self.started_at, "started_at")
        completed_at = (
            as_utc(self.completed_at, "completed_at")
            if self.completed_at is not None
            else None
        )
        if completed_at is not None and completed_at < started_at:
            raise ValueError("completed_at cannot be before started_at")
        object.__setattr__(self, "configuration", immutable_mapping(self.configuration))
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "completed_at", completed_at)
