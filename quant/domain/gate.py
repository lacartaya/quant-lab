from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from quant.domain._validation import (
    as_utc,
    immutable_mapping,
    require_text,
    require_uuid,
)
from quant.domain.validation import ValidationType


class GateDecision(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class GateRuleOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class GateRuleCode(StrEnum):
    MIN_OOS_RETURN = "MIN_OOS_RETURN"
    MIN_OOS_SHARPE = "MIN_OOS_SHARPE"
    MAX_OOS_DRAWDOWN = "MAX_OOS_DRAWDOWN"
    MIN_OOS_TRADE_COUNT = "MIN_OOS_TRADE_COUNT"
    MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO = "MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO"
    MIN_WALK_FORWARD_MEDIAN_SHARPE = "MIN_WALK_FORWARD_MEDIAN_SHARPE"
    MAX_WALK_FORWARD_SHARPE_DISPERSION = "MAX_WALK_FORWARD_SHARPE_DISPERSION"
    MIN_WALK_FORWARD_BENCHMARK_OUTPERFORMANCE_RATIO = (
        "MIN_WALK_FORWARD_BENCHMARK_OUTPERFORMANCE_RATIO"
    )
    MIN_PARAMETER_PROFITABLE_RATIO = "MIN_PARAMETER_PROFITABLE_RATIO"
    MAX_PARAMETER_SHARPE_DISPERSION = "MAX_PARAMETER_SHARPE_DISPERSION"
    MAX_BASELINE_NEIGHBOR_SHARPE_DELTA = "MAX_BASELINE_NEIGHBOR_SHARPE_DELTA"
    MIN_STRESS_PROFITABLE_RATIO = "MIN_STRESS_PROFITABLE_RATIO"
    MIN_WORST_STRESS_RETURN = "MIN_WORST_STRESS_RETURN"
    MAX_WORST_STRESS_DRAWDOWN = "MAX_WORST_STRESS_DRAWDOWN"
    MAX_MONTE_CARLO_LOSS_FREQUENCY = "MAX_MONTE_CARLO_LOSS_FREQUENCY"
    MIN_MONTE_CARLO_P05_RETURN = "MIN_MONTE_CARLO_P05_RETURN"
    MAX_MONTE_CARLO_ADVERSE_DRAWDOWN = "MAX_MONTE_CARLO_ADVERSE_DRAWDOWN"
    MAX_MONTE_CARLO_LOSS_STREAK = "MAX_MONTE_CARLO_LOSS_STREAK"
    MAX_HIGH_ADVERSARIAL_FINDINGS = "MAX_HIGH_ADVERSARIAL_FINDINGS"
    MAX_WARNING_ADVERSARIAL_FINDINGS = "MAX_WARNING_ADVERSARIAL_FINDINGS"
    FORBIDDEN_ADVERSARIAL_FINDING = "FORBIDDEN_ADVERSARIAL_FINDING"


@dataclass(frozen=True, slots=True)
class GateRuleDefinition:
    code: GateRuleCode
    threshold: float | int | str

    def __post_init__(self) -> None:
        if isinstance(self.threshold, bool):
            raise TypeError("gate rule threshold cannot be boolean")
        if self.code is GateRuleCode.FORBIDDEN_ADVERSARIAL_FINDING:
            if not isinstance(self.threshold, str) or not self.threshold.strip():
                raise ValueError("forbidden finding code cannot be empty")
        elif not isinstance(self.threshold, (float, int)):
            raise TypeError("metric gate threshold must be numeric")


@dataclass(frozen=True, slots=True)
class ValidationGatePolicy:
    policy_id: str
    version: int
    name: str
    required_validations: tuple[ValidationType, ...]
    require_adversarial_report: bool
    rules: tuple[GateRuleDefinition, ...]

    def __post_init__(self) -> None:
        require_text(self.policy_id, "policy_id")
        require_text(self.name, "name")
        if self.version <= 0:
            raise ValueError("policy version must be positive")
        if len(self.required_validations) != len(set(self.required_validations)):
            raise ValueError("required validation types must be unique")
        if len(self.rules) != len({(rule.code, rule.threshold) for rule in self.rules}):
            raise ValueError("gate rules must be unique")


@dataclass(frozen=True, slots=True)
class GateRuleResult:
    rule_code: str
    result: GateRuleOutcome
    expected: object
    actual: object
    source_validation_ids: tuple[UUID, ...]
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.rule_code.strip():
            raise ValueError("rule_code cannot be empty")
        object.__setattr__(self, "details", immutable_mapping(self.details))


@dataclass(frozen=True, slots=True)
class ValidationGateResult:
    id: UUID
    experiment_run_id: UUID
    strategy_version_id: UUID
    policy_id: str
    policy_version: int
    decision: GateDecision
    rule_results: tuple[GateRuleResult, ...]
    source_evidence: Mapping[str, object]
    policy: Mapping[str, object]
    evaluator_version: str
    evaluated_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.experiment_run_id, "experiment_run_id")
        require_uuid(self.strategy_version_id, "strategy_version_id")
        require_text(self.policy_id, "policy_id")
        require_text(self.evaluator_version, "evaluator_version")
        require_text(self.fingerprint, "fingerprint")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        object.__setattr__(
            self, "source_evidence", immutable_mapping(self.source_evidence)
        )
        object.__setattr__(self, "policy", immutable_mapping(self.policy))
        object.__setattr__(
            self, "evaluated_at", as_utc(self.evaluated_at, "evaluated_at")
        )
