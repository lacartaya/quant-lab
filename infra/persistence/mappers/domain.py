from infra.persistence.models import (
    DatasetSnapshotModel,
    ExperimentModel,
    ExperimentRunModel,
    HypothesisModel,
    PromotionDecisionModel,
    StrategyModel,
    StrategyVersionModel,
    ValidationRunModel,
)
from quant.domain import (
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    MetricSet,
    PromotionDecision,
    PromotionDecisionType,
    Strategy,
    StrategyVersion,
    ValidationRun,
    ValidationStatus,
    ValidationType,
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
        parameters=dict(value.parameters),
        created_at=value.created_at,
    )


def strategy_version_from_model(value: StrategyVersionModel) -> StrategyVersion:
    return StrategyVersion(
        id=value.id,
        strategy_id=value.strategy_id,
        version=value.version,
        git_commit=value.git_commit,
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
