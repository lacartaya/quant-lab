from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from quant.domain._validation import as_utc, require_enum, require_text, require_uuid


class PromotionDecisionType(StrEnum):
    PROMOTE = "promote"
    REJECT = "reject"
    CONTINUE_TESTING = "continue_testing"
    PAUSE = "pause"


class PaperPromotionStatus(StrEnum):
    APPROVED = "approved"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class PaperPromotion:
    """Immutable historical-to-paper approval with one auditable transition."""

    id: UUID
    hypothesis_id: UUID
    strategy_version_id: UUID
    experiment_id: UUID
    experiment_run_id: UUID
    validation_gate_id: UUID
    dataset_snapshot_id: UUID
    gate_policy_id: str
    gate_policy_version: int
    gate_decision: str
    status: PaperPromotionStatus
    reason: str
    approval_actor: str
    requested_at: datetime
    approved_at: datetime
    created_at: datetime
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revocation_reason: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "id",
            "hypothesis_id",
            "strategy_version_id",
            "experiment_id",
            "experiment_run_id",
            "validation_gate_id",
            "dataset_snapshot_id",
        ):
            require_uuid(getattr(self, name), name)
        require_text(self.gate_policy_id, "gate_policy_id")
        require_text(self.gate_decision, "gate_decision")
        require_text(self.reason, "reason")
        require_text(self.approval_actor, "approval_actor")
        require_enum(self.status, PaperPromotionStatus, "status")
        if self.gate_policy_version <= 0:
            raise ValueError("gate_policy_version must be positive")
        for name in ("requested_at", "approved_at", "created_at"):
            object.__setattr__(self, name, as_utc(getattr(self, name), name))
        if self.revoked_at is not None:
            object.__setattr__(
                self, "revoked_at", as_utc(self.revoked_at, "revoked_at")
            )
        if self.status is PaperPromotionStatus.REVOKED and (
            self.revoked_at is None or not self.revoked_by or not self.revocation_reason
        ):
            raise ValueError("revoked promotion requires actor, time, and reason")


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    id: UUID
    experiment_id: UUID
    decision: PromotionDecisionType
    rationale: str
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.experiment_id, "experiment_id")
        require_enum(self.decision, PromotionDecisionType, "decision")
        require_text(self.rationale, "rationale")
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))
