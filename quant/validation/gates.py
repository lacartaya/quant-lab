from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from quant.domain import (
    ExperimentRun,
    GateDecision,
    GateRuleCode,
    GateRuleDefinition,
    GateRuleOutcome,
    GateRuleResult,
    StrategyVersion,
    ValidationGatePolicy,
    ValidationRun,
    ValidationType,
)

VALIDATION_GATE_VERSION = "validation-gate-v1"
MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class GateEvaluationContext:
    experiment_run: ExperimentRun
    strategy_version: StrategyVersion
    validations_by_type: Mapping[ValidationType, ValidationRun]
    policy: ValidationGatePolicy

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validations_by_type",
            MappingProxyType(dict(self.validations_by_type)),
        )


@dataclass(frozen=True, slots=True)
class GateEvaluationOutcome:
    decision: GateDecision
    rule_results: tuple[GateRuleResult, ...]


class ValidationGateRule(Protocol):
    def evaluate(self, context: GateEvaluationContext) -> GateRuleResult: ...


@dataclass(frozen=True, slots=True)
class RequiredValidationRule:
    validation_type: ValidationType

    def evaluate(self, context: GateEvaluationContext) -> GateRuleResult:
        validation = context.validations_by_type.get(self.validation_type)
        available = validation is not None
        return GateRuleResult(
            f"REQUIRED_{self.validation_type.name}",
            GateRuleOutcome.PASS if available else GateRuleOutcome.FAIL,
            "AVAILABLE",
            "AVAILABLE" if available else MISSING,
            (validation.id,) if validation is not None else (),
            {"validation_type": self.validation_type.value},
        )


@dataclass(frozen=True, slots=True)
class ThresholdRule:
    definition: GateRuleDefinition

    def evaluate(self, context: GateEvaluationContext) -> GateRuleResult:
        source_type, actual = _metric_value(self.definition.code, context)
        validation = context.validations_by_type.get(source_type)
        threshold = self.definition.threshold
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise TypeError("threshold rule requires a numeric threshold")
        if actual is None or validation is None:
            return GateRuleResult(
                self.definition.code.value,
                GateRuleOutcome.FAIL,
                _expected(self.definition.code, threshold),
                MISSING,
                (),
                {"reason": "REQUIRED_EVIDENCE_MISSING"},
            )
        passed = _compare(self.definition.code, actual, float(threshold))
        return GateRuleResult(
            self.definition.code.value,
            GateRuleOutcome.PASS if passed else GateRuleOutcome.FAIL,
            _expected(self.definition.code, threshold),
            actual,
            (validation.id,),
            {"evidence_type": source_type.value},
        )


@dataclass(frozen=True, slots=True)
class AdversarialRule:
    definition: GateRuleDefinition

    def evaluate(self, context: GateEvaluationContext) -> GateRuleResult:
        validation = context.validations_by_type.get(ValidationType.ADVERSARIAL_REVIEW)
        if validation is None:
            return GateRuleResult(
                self.definition.code.value,
                GateRuleOutcome.FAIL,
                self.definition.threshold,
                MISSING,
                (),
                {"reason": "REQUIRED_EVIDENCE_MISSING"},
            )
        report = _mapping(validation.configuration.get("report"))
        findings = report.get("findings")
        summary = _mapping(report.get("summary"))
        if self.definition.code is GateRuleCode.FORBIDDEN_ADVERSARIAL_FINDING:
            forbidden = str(self.definition.threshold)
            codes: set[object] = set()
            if isinstance(findings, list):
                codes = {_mapping(raw).get("code") for raw in findings}
            actual: object = forbidden in codes
            passed = not actual
            expected: object = f"ABSENT:{forbidden}"
        else:
            field = (
                "high_count"
                if self.definition.code is GateRuleCode.MAX_HIGH_ADVERSARIAL_FINDINGS
                else "warning_count"
            )
            value = _number(summary.get(field))
            threshold = self.definition.threshold
            if value is None or not isinstance(threshold, (int, float)):
                return GateRuleResult(
                    self.definition.code.value,
                    GateRuleOutcome.FAIL,
                    threshold,
                    MISSING,
                    (validation.id,),
                    {"reason": "ADVERSARIAL_SUMMARY_MISSING"},
                )
            actual = value
            passed = value <= float(threshold)
            expected = f"<= {threshold}"
        return GateRuleResult(
            self.definition.code.value,
            GateRuleOutcome.PASS if passed else GateRuleOutcome.FAIL,
            expected,
            actual,
            (validation.id,),
            {"evidence_type": ValidationType.ADVERSARIAL_REVIEW.value},
        )


def evaluate_validation_gate(context: GateEvaluationContext) -> GateEvaluationOutcome:
    rules: list[ValidationGateRule] = [
        RequiredValidationRule(validation_type)
        for validation_type in context.policy.required_validations
    ]
    if context.policy.require_adversarial_report:
        rules.append(RequiredValidationRule(ValidationType.ADVERSARIAL_REVIEW))
    for definition in context.policy.rules:
        if definition.code in _ADVERSARIAL_CODES:
            rules.append(AdversarialRule(definition))
        else:
            rules.append(ThresholdRule(definition))
    results = tuple(rule.evaluate(context) for rule in rules)
    decision = (
        GateDecision.PASS
        if all(result.result is GateRuleOutcome.PASS for result in results)
        else GateDecision.FAIL
    )
    return GateEvaluationOutcome(decision, results)


_ADVERSARIAL_CODES = {
    GateRuleCode.MAX_HIGH_ADVERSARIAL_FINDINGS,
    GateRuleCode.MAX_WARNING_ADVERSARIAL_FINDINGS,
    GateRuleCode.FORBIDDEN_ADVERSARIAL_FINDING,
}

_MINIMUM_CODES = {
    GateRuleCode.MIN_OOS_RETURN,
    GateRuleCode.MIN_OOS_SHARPE,
    GateRuleCode.MIN_OOS_TRADE_COUNT,
    GateRuleCode.MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO,
    GateRuleCode.MIN_WALK_FORWARD_MEDIAN_SHARPE,
    GateRuleCode.MIN_WALK_FORWARD_BENCHMARK_OUTPERFORMANCE_RATIO,
    GateRuleCode.MIN_PARAMETER_PROFITABLE_RATIO,
    GateRuleCode.MIN_STRESS_PROFITABLE_RATIO,
    GateRuleCode.MIN_WORST_STRESS_RETURN,
    GateRuleCode.MIN_MONTE_CARLO_P05_RETURN,
}

_SIGNED_DRAWDOWN_MAX_CODES = {
    GateRuleCode.MAX_OOS_DRAWDOWN,
    GateRuleCode.MAX_WORST_STRESS_DRAWDOWN,
    GateRuleCode.MAX_MONTE_CARLO_ADVERSE_DRAWDOWN,
}


def _compare(code: GateRuleCode, actual: float, threshold: float) -> bool:
    if code in _MINIMUM_CODES or code in _SIGNED_DRAWDOWN_MAX_CODES:
        return actual >= threshold
    return actual <= threshold


def _expected(code: GateRuleCode, threshold: float | int) -> str:
    operator = ">=" if code in _MINIMUM_CODES | _SIGNED_DRAWDOWN_MAX_CODES else "<="
    return f"{operator} {threshold}"


def _metric_value(
    code: GateRuleCode, context: GateEvaluationContext
) -> tuple[ValidationType, float | None]:
    if code in {
        GateRuleCode.MIN_OOS_RETURN,
        GateRuleCode.MIN_OOS_SHARPE,
        GateRuleCode.MAX_OOS_DRAWDOWN,
        GateRuleCode.MIN_OOS_TRADE_COUNT,
    }:
        validation = context.validations_by_type.get(ValidationType.OUT_OF_SAMPLE)
        metrics = validation.metric_set if validation is not None else None
        value = {
            GateRuleCode.MIN_OOS_RETURN: metrics.total_return if metrics else None,
            GateRuleCode.MIN_OOS_SHARPE: metrics.sharpe if metrics else None,
            GateRuleCode.MAX_OOS_DRAWDOWN: metrics.max_drawdown if metrics else None,
            GateRuleCode.MIN_OOS_TRADE_COUNT: metrics.trade_count if metrics else None,
        }[code]
        return ValidationType.OUT_OF_SAMPLE, _number(value)
    sources: dict[GateRuleCode, tuple[ValidationType, str, str]] = {
        GateRuleCode.MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO: (
            ValidationType.WALK_FORWARD,
            "aggregate",
            "profitable_fold_ratio",
        ),
        GateRuleCode.MIN_WALK_FORWARD_MEDIAN_SHARPE: (
            ValidationType.WALK_FORWARD,
            "aggregate",
            "median_sharpe",
        ),
        GateRuleCode.MAX_WALK_FORWARD_SHARPE_DISPERSION: (
            ValidationType.WALK_FORWARD,
            "aggregate",
            "sharpe_std_across_folds",
        ),
        GateRuleCode.MIN_WALK_FORWARD_BENCHMARK_OUTPERFORMANCE_RATIO: (
            ValidationType.WALK_FORWARD,
            "aggregate",
            "benchmark_outperformance_ratio",
        ),
        GateRuleCode.MIN_PARAMETER_PROFITABLE_RATIO: (
            ValidationType.PARAMETER_SENSITIVITY,
            "summary",
            "profitable_combination_ratio",
        ),
        GateRuleCode.MAX_PARAMETER_SHARPE_DISPERSION: (
            ValidationType.PARAMETER_SENSITIVITY,
            "summary",
            "sharpe_dispersion",
        ),
        GateRuleCode.MAX_BASELINE_NEIGHBOR_SHARPE_DELTA: (
            ValidationType.PARAMETER_SENSITIVITY,
            "summary",
            "sharpe_neighbor_delta",
        ),
        GateRuleCode.MIN_STRESS_PROFITABLE_RATIO: (
            ValidationType.STRESS,
            "aggregate",
            "profitable_scenario_ratio",
        ),
        GateRuleCode.MIN_WORST_STRESS_RETURN: (
            ValidationType.STRESS,
            "aggregate",
            "worst_total_return",
        ),
        GateRuleCode.MAX_WORST_STRESS_DRAWDOWN: (
            ValidationType.STRESS,
            "aggregate",
            "worst_max_drawdown",
        ),
        GateRuleCode.MAX_MONTE_CARLO_LOSS_FREQUENCY: (
            ValidationType.MONTE_CARLO,
            "distribution",
            "empirical_loss_frequency",
        ),
        GateRuleCode.MIN_MONTE_CARLO_P05_RETURN: (
            ValidationType.MONTE_CARLO,
            "distribution.total_return_percentiles",
            "p05",
        ),
        GateRuleCode.MAX_MONTE_CARLO_ADVERSE_DRAWDOWN: (
            ValidationType.MONTE_CARLO,
            "distribution.max_drawdown_percentiles",
            "p05",
        ),
        GateRuleCode.MAX_MONTE_CARLO_LOSS_STREAK: (
            ValidationType.MONTE_CARLO,
            "distribution.max_losing_streak_percentiles",
            "p95",
        ),
    }
    validation_type, section, field = sources[code]
    validation = context.validations_by_type.get(validation_type)
    current: object = validation.configuration if validation is not None else None
    for name in section.split("."):
        current = _mapping(current).get(name)
    return validation_type, _number(_mapping(current).get(field))


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
