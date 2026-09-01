from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.domain import (
    ExperimentRunStatus,
    GateDecision,
    HistoricalDataset,
    PaperPromotion,
    PaperPromotionStatus,
)
from quant.ports import (
    DatasetRepository,
    ExperimentRepository,
    GateRepository,
    PaperPromotionRepository,
    StrategyRepository,
)

HISTORICAL_TO_PAPER_POLICY = "HISTORICAL_TO_PAPER"


class PaperPromotionError(RuntimeError):
    pass


class PaperPromotionEligibilityError(PaperPromotionError):
    pass


@dataclass(frozen=True, slots=True)
class PaperPromotionEligibility:
    eligible: bool
    reason: str
    experiment_run_id: UUID
    validation_gate_id: UUID | None
    strategy_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class PaperPromotionService:
    promotions: PaperPromotionRepository
    experiments: ExperimentRepository
    gates: GateRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    load_dataset: Callable[[UUID], HistoricalDataset]
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def eligibility(
        self, run_id: UUID, gate_id: UUID | None = None
    ) -> PaperPromotionEligibility:
        run = self.experiments.get_run(run_id)
        if run is None:
            raise LookupError(f"experiment run {run_id} was not found")
        if run.status is not ExperimentRunStatus.COMPLETED:
            return PaperPromotionEligibility(
                False, "experiment run is not completed", run_id, gate_id, None
            )
        experiment = self.experiments.get(run.experiment_id)
        if experiment is None:
            return PaperPromotionEligibility(
                False, "experiment lineage is missing", run_id, gate_id, None
            )
        candidates = (
            [self.gates.get(gate_id)]
            if gate_id
            else list(self.gates.list_for_run(run_id))
        )
        gate = next(
            (
                item
                for item in reversed(candidates)
                if item is not None and item.policy_id == HISTORICAL_TO_PAPER_POLICY
            ),
            None,
        )
        if gate is None:
            return PaperPromotionEligibility(
                False,
                "required HISTORICAL_TO_PAPER gate is missing",
                run_id,
                gate_id,
                experiment.strategy_version_id,
            )
        if gate.experiment_run_id != run_id:
            return PaperPromotionEligibility(
                False,
                "gate belongs to another experiment run",
                run_id,
                gate.id,
                gate.strategy_version_id,
            )
        if gate.decision is not GateDecision.PASS:
            return PaperPromotionEligibility(
                False,
                "validation gate decision is not PASS",
                run_id,
                gate.id,
                gate.strategy_version_id,
            )
        if gate.strategy_version_id != experiment.strategy_version_id:
            return PaperPromotionEligibility(
                False,
                "strategy lineage does not match the experiment",
                run_id,
                gate.id,
                gate.strategy_version_id,
            )
        if self.strategies.get_version(gate.strategy_version_id) is None:
            return PaperPromotionEligibility(
                False,
                "strategy version lineage is missing",
                run_id,
                gate.id,
                gate.strategy_version_id,
            )
        if self.datasets.get(experiment.dataset_snapshot_id) is None:
            return PaperPromotionEligibility(
                False,
                "dataset snapshot lineage is missing",
                run_id,
                gate.id,
                gate.strategy_version_id,
            )
        try:
            self.load_dataset(experiment.dataset_snapshot_id)
        except Exception as error:
            return PaperPromotionEligibility(
                False,
                f"historical dataset evidence is invalid: {error}",
                run_id,
                gate.id,
                gate.strategy_version_id,
            )
        return PaperPromotionEligibility(
            True,
            "eligible under current historical-to-paper policy",
            run_id,
            gate.id,
            gate.strategy_version_id,
        )

    def approve(
        self,
        run_id: UUID,
        gate_id: UUID,
        *,
        confirm: bool,
        reason: str,
        actor: str = "local-operator",
    ) -> PaperPromotion:
        if confirm is not True:
            raise PaperPromotionError(
                "explicit Paper promotion confirmation is required"
            )
        eligibility = self.eligibility(run_id, gate_id)
        if not eligibility.eligible:
            raise PaperPromotionEligibilityError(eligibility.reason)
        gate = self.gates.get(gate_id)
        run = self.experiments.get_run(run_id)
        assert gate is not None and run is not None
        experiment = self.experiments.get(run.experiment_id)
        assert experiment is not None
        existing = self.promotions.get_for_lineage(
            run_id, gate.strategy_version_id, gate_id
        )
        if existing is not None:
            if existing.status is PaperPromotionStatus.APPROVED:
                return existing
            raise PaperPromotionError(
                "this lineage has a revoked promotion; a new gate decision is required"
            )
        now = self.clock()
        promotion = PaperPromotion(
            id=self.id_factory(),
            hypothesis_id=experiment.hypothesis_id,
            strategy_version_id=gate.strategy_version_id,
            experiment_id=experiment.id,
            experiment_run_id=run.id,
            validation_gate_id=gate.id,
            dataset_snapshot_id=experiment.dataset_snapshot_id,
            gate_policy_id=gate.policy_id,
            gate_policy_version=gate.policy_version,
            gate_decision=gate.decision.value,
            status=PaperPromotionStatus.APPROVED,
            reason=reason,
            approval_actor=actor,
            requested_at=now,
            approved_at=now,
            created_at=now,
        )
        self.promotions.add(promotion)
        return promotion

    def revoke(
        self,
        promotion_id: UUID,
        *,
        confirm: bool,
        reason: str,
        actor: str = "local-operator",
    ) -> PaperPromotion:
        if confirm is not True:
            raise PaperPromotionError("explicit revocation confirmation is required")
        promotion = self.promotions.get(promotion_id)
        if promotion is None:
            raise LookupError(f"paper promotion {promotion_id} was not found")
        if promotion.status is PaperPromotionStatus.REVOKED:
            return promotion
        updated = replace(
            promotion,
            status=PaperPromotionStatus.REVOKED,
            revoked_at=self.clock(),
            revoked_by=actor,
            revocation_reason=reason,
        )
        self.promotions.save(updated)
        return updated
