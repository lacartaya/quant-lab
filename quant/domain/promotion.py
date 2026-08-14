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
