"""Infrastructure-independent domain model for Quant Lab."""

from quant.domain.dataset import AdjustmentPolicy, DatasetSnapshot
from quant.domain.experiment import (
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
)
from quant.domain.gate import (
    GateDecision,
    GateRuleCode,
    GateRuleDefinition,
    GateRuleOutcome,
    GateRuleResult,
    ValidationGatePolicy,
    ValidationGateResult,
)
from quant.domain.hypothesis import Hypothesis, HypothesisStatus
from quant.domain.market_data import HistoricalDataRequest, HistoricalDataset, MarketBar
from quant.domain.promotion import PromotionDecision, PromotionDecisionType
from quant.domain.signal import Signal, SignalAction
from quant.domain.strategy import Strategy, StrategyVersion
from quant.domain.validation import (
    MetricSet,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)

__all__ = [
    "DatasetSnapshot",
    "AdjustmentPolicy",
    "Experiment",
    "ExperimentRun",
    "ExperimentRunStatus",
    "ExperimentStatus",
    "GateDecision",
    "GateRuleCode",
    "GateRuleDefinition",
    "GateRuleOutcome",
    "GateRuleResult",
    "Hypothesis",
    "HypothesisStatus",
    "HistoricalDataRequest",
    "HistoricalDataset",
    "MarketBar",
    "MetricSet",
    "PromotionDecision",
    "PromotionDecisionType",
    "Signal",
    "SignalAction",
    "Strategy",
    "StrategyVersion",
    "ValidationRun",
    "ValidationGatePolicy",
    "ValidationGateResult",
    "ValidationStatus",
    "ValidationType",
]
