from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.application.experiments.evidence import canonical_value, evidence_fingerprint
from quant.domain import (
    ExperimentRun,
    ExperimentRunStatus,
    GateRuleCode,
    GateRuleDefinition,
    StrategyVersion,
    ValidationGatePolicy,
    ValidationGateResult,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import (
    DatasetRepository,
    ExperimentRepository,
    GateRepository,
    StrategyRepository,
)
from quant.validation import (
    VALIDATION_GATE_VERSION,
    GateEvaluationContext,
    evaluate_validation_gate,
)


class ValidationGateIntegrityError(RuntimeError):
    """Raised when gate input evidence cannot be trusted or resolved."""


@dataclass(frozen=True, slots=True)
class GateReproductionResult:
    evaluation_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    result: ValidationGateResult


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class EvaluateValidationGate:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    gates: GateRepository
    dataset_loader: Callable[[UUID], object]
    evaluation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self,
        experiment_run_id: UUID,
        policy: ValidationGatePolicy,
        evidence_ids: Mapping[ValidationType, UUID],
    ) -> ValidationGateResult:
        run, strategy = _resolve_lineage(
            experiment_run_id,
            self.experiments,
            self.strategies,
            self.datasets,
            self.dataset_loader,
        )
        validations = _resolve_validations(run, evidence_ids, self.experiments)
        result = _evaluate(
            self.evaluation_id_factory(),
            self.clock(),
            run,
            strategy,
            validations,
            policy,
        )
        self.gates.add(result)
        return result


@dataclass(frozen=True, slots=True)
class ReproduceValidationGate:
    experiments: ExperimentRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    gates: GateRepository
    dataset_loader: Callable[[UUID], object]

    def execute(self, evaluation_id: UUID) -> GateReproductionResult:
        original = self.gates.get(evaluation_id)
        if original is None:
            raise ValidationGateIntegrityError("gate evaluation not found")
        if original.evaluator_version != VALIDATION_GATE_VERSION:
            raise ValidationGateIntegrityError("unsupported gate evaluator version")
        policy = _policy(original.policy)
        evidence_ids = _evidence_ids(original.source_evidence)
        run, strategy = _resolve_lineage(
            original.experiment_run_id,
            self.experiments,
            self.strategies,
            self.datasets,
            self.dataset_loader,
        )
        validations = _resolve_validations(run, evidence_ids, self.experiments)
        reproduced = _evaluate(
            original.id,
            original.evaluated_at,
            run,
            strategy,
            validations,
            policy,
        )
        mismatches: list[str] = []
        for name in (
            "experiment_run_id",
            "strategy_version_id",
            "policy_id",
            "policy_version",
            "decision",
            "rule_results",
            "source_evidence",
            "policy",
            "evaluator_version",
        ):
            if getattr(original, name) != getattr(reproduced, name):
                mismatches.append(name)
        if original.fingerprint != reproduced.fingerprint and not mismatches:
            mismatches.append("fingerprint")
        return GateReproductionResult(
            evaluation_id,
            original.fingerprint,
            reproduced.fingerprint,
            not mismatches and original.fingerprint == reproduced.fingerprint,
            tuple(mismatches),
            reproduced,
        )


def _resolve_lineage(
    run_id: UUID,
    experiments: ExperimentRepository,
    strategies: StrategyRepository,
    datasets: DatasetRepository,
    dataset_loader: Callable[[UUID], object],
) -> tuple[ExperimentRun, StrategyVersion]:
    run = experiments.get_run(run_id)
    if run is None or run.status is not ExperimentRunStatus.COMPLETED:
        raise ValidationGateIntegrityError("completed experiment run not found")
    experiment = experiments.get(run.experiment_id)
    if experiment is None:
        raise ValidationGateIntegrityError("experiment not found")
    strategy = strategies.get_version(experiment.strategy_version_id)
    if strategy is None or datasets.get(experiment.dataset_snapshot_id) is None:
        raise ValidationGateIntegrityError("strategy or dataset lineage not found")
    dataset_loader(experiment.dataset_snapshot_id)
    return run, strategy


def _resolve_validations(
    run: ExperimentRun,
    evidence_ids: Mapping[ValidationType, UUID],
    experiments: ExperimentRepository,
) -> dict[ValidationType, ValidationRun]:
    validations: dict[ValidationType, ValidationRun] = {}
    for expected_type, validation_id in evidence_ids.items():
        validation = experiments.get_validation(validation_id)
        if validation is None:
            raise ValidationGateIntegrityError("source validation not found")
        if validation.experiment_run_id != run.id:
            raise ValidationGateIntegrityError(
                "source validation belongs to another run"
            )
        if validation.validation_type is not expected_type:
            raise ValidationGateIntegrityError("source validation type mismatch")
        if validation.status is not ValidationStatus.PASSED:
            raise ValidationGateIntegrityError("source validation is incomplete")
        _verify_fingerprint(run, validation)
        validations[expected_type] = validation
    return validations


def _verify_fingerprint(run: ExperimentRun, validation: ValidationRun) -> None:
    stored = validation.configuration.get("fingerprint")
    if not isinstance(stored, str) or not stored:
        raise ValidationGateIntegrityError("source fingerprint is missing")
    if validation.validation_type is ValidationType.BACKTEST:
        if stored != run.configuration.get("fingerprint"):
            raise ValidationGateIntegrityError("BACKTEST fingerprint mismatch")
        return
    material = {
        key: value
        for key, value in validation.configuration.items()
        if key not in {"version", "fingerprint"}
    }
    canonical = canonical_value(material)
    if not isinstance(canonical, Mapping) or evidence_fingerprint(canonical) != stored:
        raise ValidationGateIntegrityError("source validation fingerprint mismatch")


def _evaluate(
    evaluation_id: UUID,
    evaluated_at: datetime,
    run: ExperimentRun,
    strategy: StrategyVersion,
    validations: Mapping[ValidationType, ValidationRun],
    policy: ValidationGatePolicy,
) -> ValidationGateResult:
    context = GateEvaluationContext(run, strategy, validations, policy)
    outcome = evaluate_validation_gate(context)
    source_evidence = {
        validation_type.value: {
            "validation_id": str(validation.id),
            "fingerprint": validation.configuration["fingerprint"],
        }
        for validation_type, validation in sorted(
            validations.items(), key=lambda item: item[0].value
        )
    }
    policy_material = canonical_value(policy)
    if not isinstance(policy_material, Mapping):
        raise TypeError("gate policy is not canonical")
    material: dict[str, object] = {
        "experiment_run_id": str(run.id),
        "strategy_version_id": str(strategy.id),
        "policy": policy_material,
        "source_evidence": source_evidence,
        "rule_results": canonical_value(outcome.rule_results),
        "decision": outcome.decision.value,
        "evaluator_version": VALIDATION_GATE_VERSION,
    }
    fingerprint = evidence_fingerprint(material)
    return ValidationGateResult(
        evaluation_id,
        run.id,
        strategy.id,
        policy.policy_id,
        policy.version,
        outcome.decision,
        outcome.rule_results,
        source_evidence,
        policy_material,
        VALIDATION_GATE_VERSION,
        evaluated_at,
        fingerprint,
    )


def _policy(values: Mapping[str, object]) -> ValidationGatePolicy:
    required = values.get("required_validations")
    rules = values.get("rules")
    if not isinstance(required, list) or not isinstance(rules, list):
        raise ValidationGateIntegrityError("persisted gate policy is invalid")
    try:
        return ValidationGatePolicy(
            policy_id=_text(values, "policy_id"),
            version=_integer(values, "version"),
            name=_text(values, "name"),
            required_validations=tuple(ValidationType(str(item)) for item in required),
            require_adversarial_report=_boolean(values, "require_adversarial_report"),
            rules=tuple(_rule(item) for item in rules),
        )
    except (TypeError, ValueError) as error:
        raise ValidationGateIntegrityError(
            "persisted gate policy is invalid"
        ) from error


def _rule(value: object) -> GateRuleDefinition:
    if not isinstance(value, Mapping):
        raise ValidationGateIntegrityError("persisted gate rule is invalid")
    threshold = value.get("threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (str, int, float)):
        raise ValidationGateIntegrityError("persisted gate threshold is invalid")
    return GateRuleDefinition(GateRuleCode(_text(value, "code")), threshold)


def _evidence_ids(values: Mapping[str, object]) -> dict[ValidationType, UUID]:
    result: dict[ValidationType, UUID] = {}
    for name, raw in values.items():
        evidence = raw if isinstance(raw, Mapping) else None
        if evidence is None:
            raise ValidationGateIntegrityError("persisted source evidence is invalid")
        validation_id = evidence.get("validation_id")
        if not isinstance(validation_id, str):
            raise ValidationGateIntegrityError("persisted validation id is invalid")
        result[ValidationType(name)] = UUID(validation_id)
    return result


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise ValidationGateIntegrityError(f"{name} is missing")
    return value


def _integer(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationGateIntegrityError(f"{name} is missing")
    return value


def _boolean(values: Mapping[str, object], name: str) -> bool:
    value = values.get(name)
    if not isinstance(value, bool):
        raise ValidationGateIntegrityError(f"{name} is missing")
    return value
