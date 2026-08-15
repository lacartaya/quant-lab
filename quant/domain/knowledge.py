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
from quant.domain.hypothesis import HypothesisStatus


class ReconsiderationCondition(StrEnum):
    NEW_MARKET = "new_market"
    NEW_TIMEFRAME = "new_timeframe"
    NEW_EXECUTION_MODEL = "new_execution_model"
    MATERIALLY_NEW_EVIDENCE = "materially_new_evidence"
    MATERIALLY_NEW_STRATEGY_LOGIC = "materially_new_strategy_logic"
    DIFFERENT_COST_MODEL = "different_cost_model"
    DIFFERENT_REGIME_SCOPE = "different_regime_scope"


class EvidenceKind(StrEnum):
    EXPERIMENT = "experiment"
    EXPERIMENT_RUN = "experiment_run"
    VALIDATION_RUN = "validation_run"
    ADVERSARIAL_REPORT = "adversarial_report"
    GATE_EVALUATION = "gate_evaluation"


class PriorArtMatchType(StrEnum):
    EXACT = "exact"
    SAME_DOMAIN = "same_domain"
    SIMILAR_PARAMETERS = "similar_parameters"
    SAME_STRATEGY_FAMILY = "same_strategy_family"


class PriorArtDisposition(StrEnum):
    DUPLICATE = "duplicate"
    REJECTED_PRIOR_ART = "rejected_prior_art"
    RECONSIDERATION_CONDITION_MET = "reconsideration_condition_met"
    POTENTIAL_PRIOR_ART = "potential_prior_art"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    kind: EvidenceKind
    id: UUID

    def __post_init__(self) -> None:
        require_enum(self.kind, EvidenceKind, "kind")
        require_uuid(self.id, "id")


@dataclass(frozen=True, slots=True)
class ResearchSignature:
    strategy_family: str
    market: str
    instrument: str
    timeframe: str
    parameters: Mapping[str, object]
    execution_model: str | None = None
    cost_model: str | None = None
    regime_scope: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("strategy_family", "market", "instrument", "timeframe"):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "parameters", immutable_mapping(self.parameters))


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    id: UUID
    hypothesis_id: UUID
    derived_from_hypothesis_id: UUID | None
    status: HypothesisStatus
    signature: ResearchSignature
    tested_start_at: datetime | None
    tested_end_at: datetime | None
    summary: str
    rejection_reason: str | None
    reconsideration_conditions: tuple[ReconsiderationCondition, ...]
    reconsideration_rationale: str | None
    evidence_refs: tuple[EvidenceReference, ...]
    research_fingerprint: str
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.hypothesis_id, "hypothesis_id")
        if self.derived_from_hypothesis_id is not None:
            require_uuid(self.derived_from_hypothesis_id, "derived_from_hypothesis_id")
            if self.derived_from_hypothesis_id == self.hypothesis_id:
                raise ValueError("a hypothesis cannot derive from itself")
        require_enum(self.status, HypothesisStatus, "status")
        require_text(self.summary, "summary")
        require_text(self.research_fingerprint, "research_fingerprint")
        if self.status is HypothesisStatus.REJECTED and not self.rejection_reason:
            raise ValueError("rejected knowledge requires a rejection reason")
        if self.status is HypothesisStatus.REJECTED and not self.evidence_refs:
            raise ValueError("rejected knowledge requires evidence references")
        if self.tested_start_at is not None:
            object.__setattr__(
                self, "tested_start_at", as_utc(self.tested_start_at, "tested_start_at")
            )
        if self.tested_end_at is not None:
            object.__setattr__(
                self, "tested_end_at", as_utc(self.tested_end_at, "tested_end_at")
            )
        if (
            self.tested_start_at
            and self.tested_end_at
            and self.tested_end_at <= self.tested_start_at
        ):
            raise ValueError("tested_end_at must be after tested_start_at")
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class PriorArtConfiguration:
    numeric_parameter_relative_tolerance: float

    def __post_init__(self) -> None:
        if not 0 <= self.numeric_parameter_relative_tolerance <= 1:
            raise ValueError("numeric parameter tolerance must be between zero and one")


@dataclass(frozen=True, slots=True)
class PriorArtMatch:
    hypothesis_id: UUID
    knowledge_record_id: UUID
    match_type: PriorArtMatchType
    disposition: PriorArtDisposition
    similarity_evidence: Mapping[str, object]
    status: HypothesisStatus
    reconsideration_conditions: tuple[ReconsiderationCondition, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "similarity_evidence", immutable_mapping(self.similarity_evidence)
        )


@dataclass(frozen=True, slots=True)
class PriorArtCheckResult:
    candidate_fingerprint: str
    configuration: PriorArtConfiguration
    matches: tuple[PriorArtMatch, ...]
    fingerprint: str

    @property
    def duplicate_detected(self) -> bool:
        return any(
            match.disposition is PriorArtDisposition.DUPLICATE for match in self.matches
        )

    @property
    def blocked_by_rejected_prior_art(self) -> bool:
        return any(
            match.disposition is PriorArtDisposition.REJECTED_PRIOR_ART
            for match in self.matches
        )


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    strategy_family: str | None = None
    market: str | None = None
    instrument: str | None = None
    timeframe: str | None = None
    status: HypothesisStatus | None = None


@dataclass(frozen=True, slots=True)
class HypothesisKnowledgeSummary:
    hypothesis_id: UUID
    records: tuple[KnowledgeRecord, ...]
    evidence_refs: tuple[EvidenceReference, ...]
    latest_status: HypothesisStatus
