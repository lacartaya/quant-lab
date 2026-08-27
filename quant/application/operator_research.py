from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.analytics import AnalyticsConfiguration
from quant.application.experiments.models import ExperimentExecutionResult
from quant.application.experiments.registry import build_strategy
from quant.application.experiments.run_experiment import RunExperiment
from quant.application.research_memory import RegisterHypothesisWithPriorArt
from quant.backtest import BacktestConfiguration
from quant.domain import (
    Experiment,
    ExperimentStatus,
    HistoricalDataset,
    Hypothesis,
    HypothesisStatus,
    Strategy,
    StrategyVersion,
)
from quant.domain.knowledge import PriorArtConfiguration, ResearchSignature
from quant.ports import (
    DatasetRepository,
    ExperimentRepository,
    HypothesisRepository,
    KnowledgeRepository,
    StrategyRepository,
)


class ResearchResourceNotFound(LookupError):
    """Raised when an operator workflow references missing research lineage."""


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class OperatorResearchWorkflow:
    hypotheses: HypothesisRepository
    knowledge: KnowledgeRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    experiments: ExperimentRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _now

    def create_hypothesis(
        self,
        *,
        title: str,
        description: str,
        rationale: str,
        strategy_family: str,
        market: str,
        instrument: str,
        timeframe: str,
        parameters: Mapping[str, object],
        expected_benefit: str,
        expected_tradeoff: str,
        success_criteria: str,
        rejection_criteria: str,
        reconsideration_conditions: str | None,
        numeric_parameter_relative_tolerance: float,
        derived_from_hypothesis_id: UUID | None = None,
    ) -> Hypothesis:
        hypothesis = Hypothesis(
            id=self.id_factory(),
            title=title,
            description=description,
            rationale=rationale,
            strategy_family=strategy_family,
            market=market,
            timeframe=timeframe,
            expected_benefit=expected_benefit,
            expected_tradeoff=expected_tradeoff,
            success_criteria=success_criteria,
            rejection_criteria=rejection_criteria,
            status=HypothesisStatus.ACTIVE_RESEARCH,
            reconsideration_conditions=reconsideration_conditions,
            created_at=self.clock(),
        )
        RegisterHypothesisWithPriorArt(self.hypotheses, self.knowledge).execute(
            hypothesis,
            ResearchSignature(
                strategy_family=strategy_family,
                market=market,
                instrument=instrument,
                timeframe=timeframe,
                parameters=parameters,
            ),
            PriorArtConfiguration(numeric_parameter_relative_tolerance),
            derived_from_hypothesis_id=derived_from_hypothesis_id,
            summary=description,
        )
        return hypothesis

    def create_strategy_version(
        self,
        *,
        name: str,
        description: str,
        strategy_family: str,
        version: str,
        git_commit: str,
        algorithm_key: str,
        parameters: Mapping[str, object],
    ) -> tuple[Strategy, StrategyVersion]:
        strategy = Strategy(
            self.id_factory(), name, description, strategy_family, self.clock()
        )
        strategy_version = StrategyVersion(
            self.id_factory(),
            strategy.id,
            version,
            git_commit,
            algorithm_key,
            parameters,
            self.clock(),
        )
        # The executable registry is authoritative for algorithm keys and parameters.
        build_strategy(strategy_version)
        self.strategies.add(strategy)
        self.strategies.add_version(strategy_version)
        return strategy, strategy_version

    def create_experiment(
        self,
        *,
        hypothesis_id: UUID,
        strategy_version_id: UUID,
        dataset_snapshot_id: UUID,
    ) -> Experiment:
        if self.hypotheses.get(hypothesis_id) is None:
            raise ResearchResourceNotFound(f"hypothesis {hypothesis_id} was not found")
        if self.strategies.get_version(strategy_version_id) is None:
            raise ResearchResourceNotFound(
                f"strategy version {strategy_version_id} was not found"
            )
        if self.datasets.get(dataset_snapshot_id) is None:
            raise ResearchResourceNotFound(
                f"dataset snapshot {dataset_snapshot_id} was not found"
            )
        experiment = Experiment(
            self.id_factory(),
            hypothesis_id,
            strategy_version_id,
            dataset_snapshot_id,
            ExperimentStatus.CREATED,
            self.clock(),
        )
        self.experiments.add(experiment)
        return experiment

    def run_experiment(
        self,
        experiment_id: UUID,
        backtest: BacktestConfiguration,
        analytics: AnalyticsConfiguration,
    ) -> ExperimentExecutionResult:
        return RunExperiment(
            self.experiments,
            self.hypotheses,
            self.strategies,
            self.datasets,
            self.dataset_loader,
        ).execute(experiment_id, backtest, analytics)
