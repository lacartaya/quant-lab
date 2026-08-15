from uuid import UUID

from infra.persistence.models import (
    DatasetSnapshotModel,
    ExperimentModel,
    ExperimentRunModel,
    GateEvaluationModel,
    HypothesisModel,
    KnowledgeRecordModel,
    PromotionDecisionModel,
    StrategyModel,
    StrategyVersionModel,
    ValidationRunModel,
)
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    GateDecision,
    GateRuleOutcome,
    GateRuleResult,
    Hypothesis,
    HypothesisStatus,
    MetricSet,
    PromotionDecision,
    PromotionDecisionType,
    Strategy,
    StrategyVersion,
    ValidationGateResult,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.domain.knowledge import (
    EvidenceKind,
    EvidenceReference,
    KnowledgeRecord,
    ReconsiderationCondition,
    ResearchSignature,
)


def hypothesis_to_model(value: Hypothesis) -> HypothesisModel:
    return HypothesisModel(
        id=value.id,
        title=value.title,
        description=value.description,
        rationale=value.rationale,
        strategy_family=value.strategy_family,
        market=value.market,
        timeframe=value.timeframe,
        expected_benefit=value.expected_benefit,
        expected_tradeoff=value.expected_tradeoff,
        success_criteria=value.success_criteria,
        rejection_criteria=value.rejection_criteria,
        status=value.status.value,
        reconsideration_conditions=value.reconsideration_conditions,
        created_at=value.created_at,
    )


def hypothesis_from_model(value: HypothesisModel) -> Hypothesis:
    return Hypothesis(
        id=value.id,
        title=value.title,
        description=value.description,
        rationale=value.rationale,
        strategy_family=value.strategy_family,
        market=value.market,
        timeframe=value.timeframe,
        expected_benefit=value.expected_benefit,
        expected_tradeoff=value.expected_tradeoff,
        success_criteria=value.success_criteria,
        rejection_criteria=value.rejection_criteria,
        status=HypothesisStatus(value.status),
        reconsideration_conditions=value.reconsideration_conditions,
        created_at=value.created_at,
    )


def knowledge_to_model(value: KnowledgeRecord) -> KnowledgeRecordModel:
    return KnowledgeRecordModel(
        id=value.id,
        hypothesis_id=value.hypothesis_id,
        derived_from_hypothesis_id=value.derived_from_hypothesis_id,
        status=value.status.value,
        strategy_family=value.signature.strategy_family,
        market=value.signature.market,
        instrument=value.signature.instrument,
        timeframe=value.signature.timeframe,
        parameters=dict(value.signature.parameters),
        execution_model=value.signature.execution_model,
        cost_model=value.signature.cost_model,
        regime_scope=value.signature.regime_scope,
        tested_start_at=value.tested_start_at,
        tested_end_at=value.tested_end_at,
        summary=value.summary,
        rejection_reason=value.rejection_reason,
        reconsideration_conditions=[
            item.value for item in value.reconsideration_conditions
        ],
        reconsideration_rationale=value.reconsideration_rationale,
        evidence_refs=[
            {"kind": item.kind.value, "id": str(item.id)}
            for item in value.evidence_refs
        ],
        research_fingerprint=value.research_fingerprint,
        created_at=value.created_at,
    )


def knowledge_from_model(value: KnowledgeRecordModel) -> KnowledgeRecord:
    return KnowledgeRecord(
        id=value.id,
        hypothesis_id=value.hypothesis_id,
        derived_from_hypothesis_id=value.derived_from_hypothesis_id,
        status=HypothesisStatus(value.status),
        signature=ResearchSignature(
            strategy_family=value.strategy_family,
            market=value.market,
            instrument=value.instrument,
            timeframe=value.timeframe,
            parameters=value.parameters,
            execution_model=value.execution_model,
            cost_model=value.cost_model,
            regime_scope=value.regime_scope,
        ),
        tested_start_at=value.tested_start_at,
        tested_end_at=value.tested_end_at,
        summary=value.summary,
        rejection_reason=value.rejection_reason,
        reconsideration_conditions=tuple(
            ReconsiderationCondition(item) for item in value.reconsideration_conditions
        ),
        reconsideration_rationale=value.reconsideration_rationale,
        evidence_refs=tuple(
            EvidenceReference(EvidenceKind(str(item["kind"])), UUID(str(item["id"])))
            for item in value.evidence_refs
        ),
        research_fingerprint=value.research_fingerprint,
        created_at=value.created_at,
    )


def strategy_to_model(value: Strategy) -> StrategyModel:
    return StrategyModel(
        id=value.id,
        name=value.name,
        description=value.description,
        strategy_family=value.strategy_family,
        created_at=value.created_at,
    )


def strategy_from_model(value: StrategyModel) -> Strategy:
    return Strategy(
        id=value.id,
        name=value.name,
        description=value.description,
        strategy_family=value.strategy_family,
        created_at=value.created_at,
    )


def strategy_version_to_model(value: StrategyVersion) -> StrategyVersionModel:
    return StrategyVersionModel(
        id=value.id,
        strategy_id=value.strategy_id,
        version=value.version,
        git_commit=value.git_commit,
        algorithm_key=value.algorithm_key,
        parameters=dict(value.parameters),
        created_at=value.created_at,
    )


def strategy_version_from_model(value: StrategyVersionModel) -> StrategyVersion:
    return StrategyVersion(
        id=value.id,
        strategy_id=value.strategy_id,
        version=value.version,
        git_commit=value.git_commit,
        algorithm_key=value.algorithm_key,
        parameters=value.parameters,
        created_at=value.created_at,
    )


def dataset_to_model(value: DatasetSnapshot) -> DatasetSnapshotModel:
    return DatasetSnapshotModel(
        id=value.id,
        provider=value.provider,
        market=value.market,
        instrument=value.instrument,
        timeframe=value.timeframe,
        start_at=value.start_at,
        end_at=value.end_at,
        version=value.version,
        checksum=value.checksum,
        storage_location=value.storage_location,
        adjustment_policy=value.adjustment_policy.value,
        created_at=value.created_at,
    )


def dataset_from_model(value: DatasetSnapshotModel) -> DatasetSnapshot:
    return DatasetSnapshot(
        id=value.id,
        provider=value.provider,
        market=value.market,
        instrument=value.instrument,
        timeframe=value.timeframe,
        start_at=value.start_at,
        end_at=value.end_at,
        version=value.version,
        checksum=value.checksum,
        storage_location=value.storage_location,
        adjustment_policy=AdjustmentPolicy(value.adjustment_policy),
        created_at=value.created_at,
    )


def experiment_to_model(value: Experiment) -> ExperimentModel:
    return ExperimentModel(
        id=value.id,
        hypothesis_id=value.hypothesis_id,
        strategy_version_id=value.strategy_version_id,
        dataset_snapshot_id=value.dataset_snapshot_id,
        status=value.status.value,
        created_at=value.created_at,
    )


def experiment_from_model(value: ExperimentModel) -> Experiment:
    return Experiment(
        id=value.id,
        hypothesis_id=value.hypothesis_id,
        strategy_version_id=value.strategy_version_id,
        dataset_snapshot_id=value.dataset_snapshot_id,
        status=ExperimentStatus(value.status),
        created_at=value.created_at,
    )


def experiment_run_to_model(value: ExperimentRun) -> ExperimentRunModel:
    return ExperimentRunModel(
        id=value.id,
        experiment_id=value.experiment_id,
        git_commit=value.git_commit,
        engine_version=value.engine_version,
        fee_model_version=value.fee_model_version,
        slippage_model_version=value.slippage_model_version,
        configuration=dict(value.configuration),
        started_at=value.started_at,
        completed_at=value.completed_at,
        status=value.status.value,
    )


def experiment_run_from_model(value: ExperimentRunModel) -> ExperimentRun:
    return ExperimentRun(
        id=value.id,
        experiment_id=value.experiment_id,
        git_commit=value.git_commit,
        engine_version=value.engine_version,
        fee_model_version=value.fee_model_version,
        slippage_model_version=value.slippage_model_version,
        configuration=value.configuration,
        started_at=value.started_at,
        completed_at=value.completed_at,
        status=ExperimentRunStatus(value.status),
    )


def validation_to_model(value: ValidationRun) -> ValidationRunModel:
    metrics = value.metric_set
    return ValidationRunModel(
        id=value.id,
        experiment_run_id=value.experiment_run_id,
        validation_type=value.validation_type.value,
        status=value.status.value,
        configuration=dict(value.configuration),
        created_at=value.created_at,
        completed_at=value.completed_at,
        has_metric_set=metrics is not None,
        total_return=metrics.total_return if metrics else None,
        cagr=metrics.cagr if metrics else None,
        max_drawdown=metrics.max_drawdown if metrics else None,
        volatility=metrics.volatility if metrics else None,
        sharpe=metrics.sharpe if metrics else None,
        sortino=metrics.sortino if metrics else None,
        calmar=metrics.calmar if metrics else None,
        profit_factor=metrics.profit_factor if metrics else None,
        win_rate=metrics.win_rate if metrics else None,
        expectancy=metrics.expectancy if metrics else None,
        trade_count=metrics.trade_count if metrics else None,
    )


def validation_from_model(value: ValidationRunModel) -> ValidationRun:
    metrics = (
        MetricSet(
            total_return=value.total_return,
            cagr=value.cagr,
            max_drawdown=value.max_drawdown,
            volatility=value.volatility,
            sharpe=value.sharpe,
            sortino=value.sortino,
            calmar=value.calmar,
            profit_factor=value.profit_factor,
            win_rate=value.win_rate,
            expectancy=value.expectancy,
            trade_count=value.trade_count,
        )
        if value.has_metric_set
        else None
    )
    return ValidationRun(
        id=value.id,
        experiment_run_id=value.experiment_run_id,
        validation_type=ValidationType(value.validation_type),
        status=ValidationStatus(value.status),
        metric_set=metrics,
        configuration=value.configuration,
        created_at=value.created_at,
        completed_at=value.completed_at,
    )


def gate_evaluation_to_model(value: ValidationGateResult) -> GateEvaluationModel:
    return GateEvaluationModel(
        id=value.id,
        experiment_run_id=value.experiment_run_id,
        strategy_version_id=value.strategy_version_id,
        policy_id=value.policy_id,
        policy_version=value.policy_version,
        decision=value.decision.value,
        rule_results=[_gate_rule_to_json(item) for item in value.rule_results],
        source_evidence=dict(value.source_evidence),
        policy=dict(value.policy),
        evaluator_version=value.evaluator_version,
        evaluated_at=value.evaluated_at,
        fingerprint=value.fingerprint,
    )


def gate_evaluation_from_model(value: GateEvaluationModel) -> ValidationGateResult:
    return ValidationGateResult(
        id=value.id,
        experiment_run_id=value.experiment_run_id,
        strategy_version_id=value.strategy_version_id,
        policy_id=value.policy_id,
        policy_version=value.policy_version,
        decision=GateDecision(value.decision),
        rule_results=tuple(_gate_rule_from_json(item) for item in value.rule_results),
        source_evidence=value.source_evidence,
        policy=value.policy,
        evaluator_version=value.evaluator_version,
        evaluated_at=value.evaluated_at,
        fingerprint=value.fingerprint,
    )


def _gate_rule_to_json(value: GateRuleResult) -> dict[str, object]:
    return {
        "rule_code": value.rule_code,
        "result": value.result.value,
        "expected": value.expected,
        "actual": value.actual,
        "source_validation_ids": [str(item) for item in value.source_validation_ids],
        "details": dict(value.details),
    }


def _gate_rule_from_json(value: dict[str, object]) -> GateRuleResult:
    source_ids = value.get("source_validation_ids")
    details = value.get("details")
    if not isinstance(source_ids, list) or not isinstance(details, dict):
        raise ValueError("persisted gate rule is invalid")
    return GateRuleResult(
        rule_code=str(value["rule_code"]),
        result=GateRuleOutcome(str(value["result"])),
        expected=value.get("expected"),
        actual=value.get("actual"),
        source_validation_ids=tuple(UUID(str(item)) for item in source_ids),
        details=details,
    )


def promotion_to_model(value: PromotionDecision) -> PromotionDecisionModel:
    return PromotionDecisionModel(
        id=value.id,
        experiment_id=value.experiment_id,
        decision=value.decision.value,
        rationale=value.rationale,
        created_at=value.created_at,
    )


def promotion_from_model(value: PromotionDecisionModel) -> PromotionDecision:
    return PromotionDecision(
        id=value.id,
        experiment_id=value.experiment_id,
        decision=PromotionDecisionType(value.decision),
        rationale=value.rationale,
        created_at=value.created_at,
    )
