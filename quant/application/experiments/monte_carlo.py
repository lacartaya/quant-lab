from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from quant.application.experiments.evidence import canonical_value, evidence_fingerprint
from quant.domain import (
    DatasetSnapshot,
    ExperimentRunStatus,
    HistoricalDataset,
    MetricSet,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import DatasetRepository, ExperimentRepository
from quant.validation import (
    MONTE_CARLO_VERSION,
    MonteCarloAnalysis,
    MonteCarloConfiguration,
    SamplingMethod,
    simulate_trade_bootstrap,
    summarize_monte_carlo,
    trade_return_observations,
)


class MonteCarloLineageError(LookupError):
    """Raised when persisted bootstrap lineage is absent or unsupported."""


@dataclass(frozen=True, slots=True)
class MonteCarloValidationResult:
    validation_run_id: UUID
    experiment_run_id: UUID
    dataset_snapshot_id: UUID
    analysis: MonteCarloAnalysis
    fingerprint: str


@dataclass(frozen=True, slots=True)
class MonteCarloReproductionResult:
    validation_run_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    result: MonteCarloValidationResult


@dataclass(frozen=True, slots=True)
class _SourceEvidence:
    experiment_run_id: UUID
    snapshot: DatasetSnapshot
    initial_equity: Decimal
    historical_metrics: MetricSet
    observations: tuple[Decimal, ...]
    observation_fingerprint: str
    source_run_fingerprint: str
    source_validation_id: UUID


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RunMonteCarloValidation:
    experiments: ExperimentRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self, experiment_run_id: UUID, configuration: MonteCarloConfiguration
    ) -> MonteCarloValidationResult:
        source = _resolve_source(
            experiment_run_id, self.experiments, self.datasets, self.dataset_loader
        )
        validation_id = self.validation_id_factory()
        result, evidence = _evaluate(validation_id, source, configuration)
        now = self.clock()
        self.experiments.add_validation(
            ValidationRun(
                id=validation_id,
                experiment_run_id=experiment_run_id,
                validation_type=ValidationType.MONTE_CARLO,
                status=ValidationStatus.PASSED,
                metric_set=None,
                configuration=evidence,
                created_at=now,
                completed_at=now,
            )
        )
        return result


@dataclass(frozen=True, slots=True)
class ReproduceMonteCarloValidation:
    experiments: ExperimentRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def execute(self, validation_run_id: UUID) -> MonteCarloReproductionResult:
        validation = self.experiments.get_validation(validation_run_id)
        if validation is None:
            raise MonteCarloLineageError("Monte Carlo validation not found")
        if validation.validation_type is not ValidationType.MONTE_CARLO:
            raise MonteCarloLineageError("validation is not MONTE_CARLO")
        if validation.status is not ValidationStatus.PASSED:
            raise MonteCarloLineageError("Monte Carlo validation is not completed")
        stored = _mapping(validation.configuration, "Monte Carlo evidence")
        if stored.get("version") != MONTE_CARLO_VERSION:
            raise MonteCarloLineageError("unsupported Monte Carlo version")
        configuration = _configuration(
            _mapping(stored.get("configuration"), "Monte Carlo configuration")
        )
        source = _resolve_source(
            validation.experiment_run_id,
            self.experiments,
            self.datasets,
            self.dataset_loader,
        )
        reproduced, evidence = _evaluate(validation_run_id, source, configuration)
        original_fingerprint = _text(stored, "fingerprint")
        reproduced_fingerprint = _text(evidence, "fingerprint")
        sections = (
            "source",
            "configuration",
            "historical_metrics",
            "path_summaries",
            "distribution",
        )
        mismatches = tuple(
            section
            for section in sections
            if stored.get(section) != evidence.get(section)
        )
        if original_fingerprint != reproduced_fingerprint and not mismatches:
            mismatches = ("fingerprint",)
        return MonteCarloReproductionResult(
            validation_run_id,
            original_fingerprint,
            reproduced_fingerprint,
            not mismatches and original_fingerprint == reproduced_fingerprint,
            mismatches,
            reproduced,
        )


def _resolve_source(
    experiment_run_id: UUID,
    experiments: ExperimentRepository,
    datasets: DatasetRepository,
    dataset_loader: Callable[[UUID], HistoricalDataset],
) -> _SourceEvidence:
    run = experiments.get_run(experiment_run_id)
    if run is None or run.status is not ExperimentRunStatus.COMPLETED:
        raise MonteCarloLineageError("completed experiment run not found")
    experiment = experiments.get(run.experiment_id)
    if experiment is None:
        raise MonteCarloLineageError("experiment for run not found")
    snapshot = datasets.get(experiment.dataset_snapshot_id)
    if snapshot is None:
        raise MonteCarloLineageError("dataset snapshot not found")
    # Loading verifies the immutable artifact checksum and metadata before analysis.
    dataset_loader(snapshot.id)
    run_configuration = _mapping(run.configuration, "experiment run configuration")
    execution = _mapping(run_configuration.get("execution"), "execution configuration")
    backtest_configuration = _mapping(
        execution.get("backtest"), "backtest configuration"
    )
    initial_equity = _decimal_text(backtest_configuration, "initial_cash")
    evidence = _mapping(run_configuration.get("evidence"), "backtest evidence")
    backtest = _mapping(evidence.get("backtest"), "backtest result evidence")
    raw_trades = backtest.get("trades")
    if not isinstance(raw_trades, list):
        raise MonteCarloLineageError("completed trade evidence is missing")
    trades = tuple(_mapping(item, "trade evidence") for item in raw_trades)
    try:
        observations = trade_return_observations(trades)
    except ValueError as error:
        raise MonteCarloLineageError(str(error)) from error
    observation_material = {
        "method": SamplingMethod.TRADE_BOOTSTRAP.value,
        "returns": canonical_value(observations),
    }
    observation_fingerprint = evidence_fingerprint(observation_material)
    source_run_fingerprint = _text(run_configuration, "fingerprint")
    backtests = tuple(
        validation
        for validation in experiments.list_validations(experiment_run_id)
        if validation.validation_type is ValidationType.BACKTEST
        and validation.status is ValidationStatus.PASSED
    )
    if len(backtests) != 1 or backtests[0].metric_set is None:
        raise MonteCarloLineageError(
            "exactly one completed BACKTEST validation with metrics is required"
        )
    return _SourceEvidence(
        experiment_run_id,
        snapshot,
        initial_equity,
        backtests[0].metric_set,
        observations,
        observation_fingerprint,
        source_run_fingerprint,
        backtests[0].id,
    )


def _evaluate(
    validation_id: UUID,
    source: _SourceEvidence,
    configuration: MonteCarloConfiguration,
) -> tuple[MonteCarloValidationResult, dict[str, object]]:
    if configuration.sampling_method is not SamplingMethod.TRADE_BOOTSTRAP:
        raise ValueError("unsupported Monte Carlo sampling method")
    paths = simulate_trade_bootstrap(
        source.observations, source.initial_equity, configuration
    )
    distribution = summarize_monte_carlo(
        paths,
        source.initial_equity,
        configuration,
        source.historical_metrics.total_return,
    )
    analysis = MonteCarloAnalysis(
        configuration,
        len(source.observations),
        source.observation_fingerprint,
        source.historical_metrics,
        paths,
        distribution,
    )
    material: dict[str, object] = {
        "source": {
            "experiment_run_id": str(source.experiment_run_id),
            "backtest_validation_id": str(source.source_validation_id),
            "dataset_snapshot_id": str(source.snapshot.id),
            "dataset_checksum": source.snapshot.checksum,
            "source_run_fingerprint": source.source_run_fingerprint,
            "observation_count": len(source.observations),
            "observation_fingerprint": source.observation_fingerprint,
            "observations": canonical_value(source.observations),
            "return_basis": "net_pnl_over_entry_notional_plus_entry_fees",
        },
        "configuration": canonical_value(configuration),
        "historical_metrics": canonical_value(source.historical_metrics),
        "path_summaries": canonical_value(paths),
        "distribution": canonical_value(distribution),
    }
    fingerprint = evidence_fingerprint(material)
    evidence = {
        "version": MONTE_CARLO_VERSION,
        **material,
        "fingerprint": fingerprint,
    }
    return (
        MonteCarloValidationResult(
            validation_id,
            source.experiment_run_id,
            source.snapshot.id,
            analysis,
            fingerprint,
        ),
        evidence,
    )


def _configuration(values: Mapping[str, object]) -> MonteCarloConfiguration:
    percentiles = values.get("confidence_percentiles")
    if not isinstance(percentiles, list):
        raise MonteCarloLineageError("confidence percentiles are missing")
    try:
        return MonteCarloConfiguration(
            simulation_count=_integer(values, "simulation_count"),
            random_seed=_integer(values, "random_seed"),
            confidence_percentiles=tuple(
                Decimal(_string(item)) for item in percentiles
            ),
            sampling_method=SamplingMethod(_text(values, "sampling_method")),
            drawdown_threshold=_optional_decimal(values, "drawdown_threshold"),
            ruin_equity_fraction=_optional_decimal(values, "ruin_equity_fraction"),
        )
    except (ValueError, TypeError) as error:
        raise MonteCarloLineageError("invalid Monte Carlo configuration") from error


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MonteCarloLineageError(f"{name} is missing")
    return value


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise MonteCarloLineageError(f"{name} is missing")
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise MonteCarloLineageError("canonical decimal value is missing")
    return value


def _integer(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MonteCarloLineageError(f"{name} is missing")
    return value


def _decimal_text(values: Mapping[str, object], name: str) -> Decimal:
    return Decimal(_text(values, name))


def _optional_decimal(values: Mapping[str, object], name: str) -> Decimal | None:
    value = values.get(name)
    return None if value is None else Decimal(_string(value))
