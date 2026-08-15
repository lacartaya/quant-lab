from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.domain import Hypothesis, HypothesisStatus, ValidationType
from quant.domain.knowledge import (
    EvidenceKind,
    EvidenceReference,
    HypothesisKnowledgeSummary,
    KnowledgeQuery,
    KnowledgeRecord,
    PriorArtCheckResult,
    PriorArtConfiguration,
    ReconsiderationCondition,
    ResearchSignature,
)
from quant.knowledge import check_prior_art, research_fingerprint
from quant.ports import ExperimentRepository, GateRepository, HypothesisRepository
from quant.ports.knowledge_repository import KnowledgeRepository


class DuplicateHypothesisError(ValueError):
    pass


class RejectedPriorArtError(ValueError):
    pass


class KnowledgeEvidenceError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class CheckPriorArt:
    repository: KnowledgeRepository

    def execute(
        self, signature: ResearchSignature, configuration: PriorArtConfiguration
    ) -> PriorArtCheckResult:
        return check_prior_art(signature, self.repository.list_all(), configuration)


@dataclass(frozen=True, slots=True)
class SearchResearchKnowledge:
    repository: KnowledgeRepository

    def execute(self, query: KnowledgeQuery) -> tuple[KnowledgeRecord, ...]:
        return tuple(self.repository.search(query))

    def history(self, hypothesis_id: UUID) -> HypothesisKnowledgeSummary:
        records = tuple(self.repository.list_for_hypothesis(hypothesis_id))
        if not records:
            raise LookupError(f"knowledge for hypothesis {hypothesis_id} was not found")
        refs = tuple(
            reference for record in records for reference in record.evidence_refs
        )
        return HypothesisKnowledgeSummary(
            hypothesis_id, records, refs, records[-1].status
        )


@dataclass(frozen=True, slots=True)
class RegisterHypothesisWithPriorArt:
    hypotheses: HypothesisRepository
    knowledge: KnowledgeRepository

    def execute(
        self,
        hypothesis: Hypothesis,
        signature: ResearchSignature,
        configuration: PriorArtConfiguration,
        *,
        derived_from_hypothesis_id: UUID | None = None,
        summary: str,
    ) -> KnowledgeRecord:
        result = check_prior_art(signature, self.knowledge.list_all(), configuration)
        if result.duplicate_detected:
            raise DuplicateHypothesisError(
                "identical structured research already exists"
            )
        if result.blocked_by_rejected_prior_art:
            raise RejectedPriorArtError(
                "materially equivalent rejected research already exists"
            )
        if (
            derived_from_hypothesis_id is not None
            and self.hypotheses.get(derived_from_hypothesis_id) is None
        ):
            raise LookupError("derived-from hypothesis does not exist")
        self.hypotheses.add(hypothesis)
        record = KnowledgeRecord(
            id=uuid4(),
            hypothesis_id=hypothesis.id,
            derived_from_hypothesis_id=derived_from_hypothesis_id,
            status=hypothesis.status,
            signature=signature,
            tested_start_at=None,
            tested_end_at=None,
            summary=summary,
            rejection_reason=None,
            reconsideration_conditions=(),
            reconsideration_rationale=None,
            evidence_refs=(),
            research_fingerprint=research_fingerprint(signature),
            created_at=datetime.now(UTC),
        )
        self.knowledge.add(record)
        return record


@dataclass(frozen=True, slots=True)
class RejectHypothesis:
    hypotheses: HypothesisRepository
    knowledge: KnowledgeRepository
    experiments: ExperimentRepository
    gates: GateRepository

    def execute(
        self,
        hypothesis_id: UUID,
        signature: ResearchSignature,
        *,
        reason: str,
        summary: str,
        evidence_refs: tuple[EvidenceReference, ...],
        reconsideration_conditions: tuple[ReconsiderationCondition, ...],
        reconsideration_rationale: str | None = None,
        tested_start_at: datetime | None = None,
        tested_end_at: datetime | None = None,
        now: datetime | None = None,
    ) -> KnowledgeRecord:
        hypothesis = self.hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise LookupError(f"hypothesis {hypothesis_id} was not found")
        if hypothesis.status is not HypothesisStatus.ACTIVE_RESEARCH:
            raise ValueError("only active research can be rejected")
        for reference in evidence_refs:
            self._verify_evidence(reference)
        rejected = replace(
            hypothesis,
            status=HypothesisStatus.REJECTED,
            reconsideration_conditions=reconsideration_rationale,
        )
        history = tuple(self.knowledge.list_for_hypothesis(hypothesis_id))
        derived_from = history[-1].derived_from_hypothesis_id if history else None
        record = KnowledgeRecord(
            id=uuid4(),
            hypothesis_id=hypothesis_id,
            derived_from_hypothesis_id=derived_from,
            status=HypothesisStatus.REJECTED,
            signature=signature,
            tested_start_at=tested_start_at,
            tested_end_at=tested_end_at,
            summary=summary,
            rejection_reason=reason,
            reconsideration_conditions=reconsideration_conditions,
            reconsideration_rationale=reconsideration_rationale,
            evidence_refs=evidence_refs,
            research_fingerprint=research_fingerprint(signature),
            created_at=now or datetime.now(UTC),
        )
        self.hypotheses.save(rejected)
        self.knowledge.add(record)
        return record

    def _verify_evidence(self, reference: EvidenceReference) -> None:
        found = False
        if reference.kind is EvidenceKind.EXPERIMENT:
            found = self.experiments.get(reference.id) is not None
        elif reference.kind is EvidenceKind.EXPERIMENT_RUN:
            found = self.experiments.get_run(reference.id) is not None
        elif reference.kind in {
            EvidenceKind.VALIDATION_RUN,
            EvidenceKind.ADVERSARIAL_REPORT,
        }:
            validation = self.experiments.get_validation(reference.id)
            found = validation is not None
            if (
                validation is not None
                and reference.kind is EvidenceKind.ADVERSARIAL_REPORT
            ):
                found = validation.validation_type is ValidationType.ADVERSARIAL_REVIEW
        elif reference.kind is EvidenceKind.GATE_EVALUATION:
            found = self.gates.get(reference.id) is not None
        if not found:
            raise KnowledgeEvidenceError(
                f"{reference.kind.value} {reference.id} was not found"
            )
