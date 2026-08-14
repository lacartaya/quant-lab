from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from quant.domain._validation import as_utc, require_enum, require_text, require_uuid


class HypothesisStatus(StrEnum):
    KNOWN_REPLICATED = "known_replicated"
    ACTIVE_RESEARCH = "active_research"
    VALIDATED_INTERNAL = "validated_internal"
    REJECTED = "rejected"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: UUID
    title: str
    description: str
    rationale: str
    strategy_family: str
    market: str
    timeframe: str
    expected_benefit: str
    expected_tradeoff: str
    success_criteria: str
    rejection_criteria: str
    status: HypothesisStatus
    reconsideration_conditions: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_text(self.title, "title")
        require_enum(self.status, HypothesisStatus, "status")
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))
