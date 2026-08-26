from dataclasses import dataclass
from uuid import UUID

from quant.domain import (
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    Strategy,
    StrategyVersion,
    ValidationGateResult,
    ValidationRun,
    ValidationType,
)
from quant.domain.knowledge import KnowledgeQuery, KnowledgeRecord
from quant.ports import (
    DatasetRepository,
    ExperimentRepository,
    GateRepository,
    HypothesisRepository,
    KnowledgeRepository,
    StrategyRepository,
)


class OperatorResourceNotFound(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class ExperimentSummary:
    experiment: Experiment
    latest_run: ExperimentRun | None
    validation_types: tuple[ValidationType, ...]
    latest_gate: ValidationGateResult | None


@dataclass(frozen=True, slots=True)
class ExperimentDetail:
    experiment: Experiment
    hypothesis: Hypothesis
    strategy: Strategy
    strategy_version: StrategyVersion
    dataset: DatasetSnapshot
    runs: tuple[ExperimentRun, ...]


@dataclass(frozen=True, slots=True)
class HypothesisDetail:
    hypothesis: Hypothesis
    experiments: tuple[Experiment, ...]
    knowledge: tuple[KnowledgeRecord, ...]
    derived_hypothesis_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    active_experiments: int
    completed_experiments: int
    rejected_hypotheses: int
    eligible_for_paper: int
    failed_gates: int
    high_findings: int
    warning_findings: int
    knowledge_by_status: dict[HypothesisStatus, int]


@dataclass(frozen=True, slots=True)
class OperatorQueries:
    hypotheses: HypothesisRepository
    strategies: StrategyRepository
    datasets: DatasetRepository
    experiments: ExperimentRepository
    gates: GateRepository
    knowledge: KnowledgeRepository

    def list_datasets(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[DatasetSnapshot, ...]:
        return tuple(self.datasets.list_all()[offset : offset + limit])

    def dataset(self, snapshot_id: UUID) -> DatasetSnapshot:
        return self._required(
            self.datasets.get(snapshot_id), "dataset snapshot", snapshot_id
        )

    def list_experiments(
        self,
        *,
        status: ExperimentStatus | None = None,
        strategy_version_id: UUID | None = None,
        hypothesis_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[ExperimentSummary, ...]:
        values = self.experiments.list_all()
        filtered = [
            value
            for value in values
            if (status is None or value.status is status)
            and (
                strategy_version_id is None
                or value.strategy_version_id == strategy_version_id
            )
            and (hypothesis_id is None or value.hypothesis_id == hypothesis_id)
        ]
        ordered = sorted(
            filtered, key=lambda item: (item.created_at, str(item.id)), reverse=True
        )
        return tuple(
            self._experiment_summary(item) for item in ordered[offset : offset + limit]
        )

    def experiment_detail(self, experiment_id: UUID) -> ExperimentDetail:
        experiment = self._required(
            self.experiments.get(experiment_id), "experiment", experiment_id
        )
        hypothesis = self._required(
            self.hypotheses.get(experiment.hypothesis_id),
            "hypothesis",
            experiment.hypothesis_id,
        )
        version = self._required(
            self.strategies.get_version(experiment.strategy_version_id),
            "strategy version",
            experiment.strategy_version_id,
        )
        strategy = self._required(
            self.strategies.get(version.strategy_id), "strategy", version.strategy_id
        )
        dataset = self._required(
            self.datasets.get(experiment.dataset_snapshot_id),
            "dataset snapshot",
            experiment.dataset_snapshot_id,
        )
        return ExperimentDetail(
            experiment,
            hypothesis,
            strategy,
            version,
            dataset,
            tuple(self.experiments.list_runs(experiment.id)),
        )

    def experiment_run(self, run_id: UUID) -> ExperimentRun:
        return self._required(
            self.experiments.get_run(run_id), "experiment run", run_id
        )

    def validations(
        self, run_id: UUID, validation_type: ValidationType | None = None
    ) -> tuple[ValidationRun, ...]:
        self.experiment_run(run_id)
        values = self.experiments.list_validations(run_id)
        return tuple(
            item
            for item in values
            if validation_type is None or item.validation_type is validation_type
        )

    def validation(self, validation_id: UUID) -> ValidationRun:
        return self._required(
            self.experiments.get_validation(validation_id), "validation", validation_id
        )

    def adversarial_reports(self, run_id: UUID) -> tuple[ValidationRun, ...]:
        return self.validations(run_id, ValidationType.ADVERSARIAL_REVIEW)

    def gate_evaluations(self, run_id: UUID) -> tuple[ValidationGateResult, ...]:
        self.experiment_run(run_id)
        return tuple(self.gates.list_for_run(run_id))

    def gate_evaluation(self, gate_id: UUID) -> ValidationGateResult:
        return self._required(self.gates.get(gate_id), "gate evaluation", gate_id)

    def strategy_version(self, version_id: UUID) -> StrategyVersion:
        return self._required(
            self.strategies.get_version(version_id), "strategy version", version_id
        )

    def list_hypotheses(
        self,
        *,
        status: HypothesisStatus | None = None,
        strategy_family: str | None = None,
        market: str | None = None,
        instrument: str | None = None,
        timeframe: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Hypothesis, ...]:
        hypotheses = self.hypotheses.list_all()
        knowledge_ids: set[UUID] | None = None
        if instrument is not None:
            knowledge_ids = {
                item.hypothesis_id
                for item in self.knowledge.search(KnowledgeQuery(instrument=instrument))
            }
        filtered = [
            item
            for item in hypotheses
            if (status is None or item.status is status)
            and (strategy_family is None or item.strategy_family == strategy_family)
            and (market is None or item.market == market)
            and (timeframe is None or item.timeframe == timeframe)
            and (knowledge_ids is None or item.id in knowledge_ids)
        ]
        ordered = sorted(
            filtered, key=lambda item: (item.created_at, str(item.id)), reverse=True
        )
        return tuple(ordered[offset : offset + limit])

    def hypothesis_detail(self, hypothesis_id: UUID) -> HypothesisDetail:
        hypothesis = self._required(
            self.hypotheses.get(hypothesis_id), "hypothesis", hypothesis_id
        )
        records = tuple(self.knowledge.list_for_hypothesis(hypothesis_id))
        derived_ids = tuple(
            item.hypothesis_id
            for item in self.knowledge.list_all()
            if item.derived_from_hypothesis_id == hypothesis_id
        )
        return HypothesisDetail(
            hypothesis,
            tuple(self.experiments.list_for_hypothesis(hypothesis_id)),
            records,
            derived_ids,
        )

    def search_knowledge(
        self, query: KnowledgeQuery, *, limit: int = 50, offset: int = 0
    ) -> tuple[KnowledgeRecord, ...]:
        values = tuple(reversed(self.knowledge.search(query)))
        return values[offset : offset + limit]

    def dashboard_summary(self) -> DashboardSummary:
        experiments = self.experiments.list_all()
        hypotheses = self.hypotheses.list_all()
        gates = [
            gate
            for experiment in experiments
            for run in self.experiments.list_runs(experiment.id)
            for gate in self.gates.list_for_run(run.id)
        ]
        adversarial = [
            validation
            for experiment in experiments
            for run in self.experiments.list_runs(experiment.id)
            for validation in self.experiments.list_validations(run.id)
            if validation.validation_type is ValidationType.ADVERSARIAL_REVIEW
        ]
        high = sum(self._finding_count(item, "high_count") for item in adversarial)
        warnings = sum(
            self._finding_count(item, "warning_count") for item in adversarial
        )
        return DashboardSummary(
            active_experiments=sum(
                item.status in {ExperimentStatus.CREATED, ExperimentStatus.RUNNING}
                for item in experiments
            ),
            completed_experiments=sum(
                item.status is ExperimentStatus.COMPLETED for item in experiments
            ),
            rejected_hypotheses=sum(
                item.status is HypothesisStatus.REJECTED for item in hypotheses
            ),
            eligible_for_paper=sum(item.decision.value == "pass" for item in gates),
            failed_gates=sum(item.decision.value == "fail" for item in gates),
            high_findings=high,
            warning_findings=warnings,
            knowledge_by_status={
                status: sum(item.status is status for item in hypotheses)
                for status in HypothesisStatus
            },
        )

    def _experiment_summary(self, experiment: Experiment) -> ExperimentSummary:
        runs = self.experiments.list_runs(experiment.id)
        latest = runs[-1] if runs else None
        validations = self.experiments.list_validations(latest.id) if latest else ()
        gates = self.gates.list_for_run(latest.id) if latest else ()
        return ExperimentSummary(
            experiment,
            latest,
            tuple(dict.fromkeys(item.validation_type for item in validations)),
            gates[-1] if gates else None,
        )

    @staticmethod
    def _finding_count(validation: ValidationRun, name: str) -> int:
        report = validation.configuration.get("report")
        if not isinstance(report, dict):
            return 0
        summary = report.get("summary")
        if not isinstance(summary, dict):
            return 0
        value = summary.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    @staticmethod
    def _required[ValueT](value: ValueT | None, kind: str, identity: UUID) -> ValueT:
        if value is None:
            raise OperatorResourceNotFound(f"{kind} {identity} was not found")
        return value
