from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.application.experiments.evidence import canonical_value, evidence_fingerprint
from quant.domain import (
    ExperimentRun,
    ExperimentRunStatus,
    HistoricalDataset,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.ports import DatasetRepository, ExperimentRepository
from quant.validation import (
    ADVERSARIAL_ANALYZER_VERSION,
    AdversarialAnalysisConfiguration,
    AdversarialValidationReport,
    analyze_adversarial_evidence,
)


class AdversarialLineageError(LookupError):
    """Raised when report source evidence is absent, corrupt, or unsupported."""


@dataclass(frozen=True, slots=True)
class AdversarialReproductionResult:
    validation_run_id: UUID
    original_fingerprint: str
    reproduced_fingerprint: str
    matches: bool
    mismatches: tuple[str, ...]
    report: AdversarialValidationReport


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RunAdversarialValidation:
    experiments: ExperimentRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]
    validation_id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def execute(
        self,
        experiment_run_id: UUID,
        configuration: AdversarialAnalysisConfiguration,
    ) -> AdversarialValidationReport:
        run, validations = _resolve_sources(
            experiment_run_id, self.experiments, self.datasets, self.dataset_loader
        )
        report, evidence = _evaluate(run, validations, configuration)
        now = self.clock()
        self.experiments.add_validation(
            ValidationRun(
                id=self.validation_id_factory(),
                experiment_run_id=experiment_run_id,
                validation_type=ValidationType.ADVERSARIAL_REVIEW,
                status=ValidationStatus.PASSED,
                metric_set=None,
                configuration=evidence,
                created_at=now,
                completed_at=now,
            )
        )
        return report


@dataclass(frozen=True, slots=True)
class ReproduceAdversarialValidation:
    experiments: ExperimentRepository
    datasets: DatasetRepository
    dataset_loader: Callable[[UUID], HistoricalDataset]

    def execute(self, validation_run_id: UUID) -> AdversarialReproductionResult:
        validation = self.experiments.get_validation(validation_run_id)
        if validation is None:
            raise AdversarialLineageError("adversarial report not found")
        if validation.validation_type is not ValidationType.ADVERSARIAL_REVIEW:
            raise AdversarialLineageError("validation is not ADVERSARIAL_REVIEW")
        if validation.status is not ValidationStatus.PASSED:
            raise AdversarialLineageError("adversarial report is not completed")
        stored = _mapping(validation.configuration, "adversarial evidence")
        if stored.get("version") != ADVERSARIAL_ANALYZER_VERSION:
            raise AdversarialLineageError("unsupported adversarial analyzer version")
        config = _configuration(
            _mapping(stored.get("configuration"), "adversarial configuration")
        )
        source = _mapping(stored.get("sources"), "source fingerprints")
        source_ids = tuple(UUID(value) for value in source)
        run = self.experiments.get_run(validation.experiment_run_id)
        if run is None or run.status is not ExperimentRunStatus.COMPLETED:
            raise AdversarialLineageError("completed experiment run not found")
        _verify_dataset(run, self.experiments, self.datasets, self.dataset_loader)
        validations = tuple(
            _required_validation(self.experiments, validation_id)
            for validation_id in source_ids
        )
        _verify_source_integrity(run, validations)
        current_sources = _source_fingerprints(validations)
        if current_sources != dict(source):
            raise AdversarialLineageError("source validation fingerprint mismatch")
        report, evidence = _evaluate(run, validations, config)
        original_fingerprint = _text(stored, "fingerprint")
        reproduced_fingerprint = _text(evidence, "fingerprint")
        sections = ("sources", "configuration", "report")
        mismatches = tuple(
            section
            for section in sections
            if stored.get(section) != evidence.get(section)
        )
        if original_fingerprint != reproduced_fingerprint and not mismatches:
            mismatches = ("fingerprint",)
        return AdversarialReproductionResult(
            validation_run_id,
            original_fingerprint,
            reproduced_fingerprint,
            not mismatches and original_fingerprint == reproduced_fingerprint,
            mismatches,
            report,
        )


def _resolve_sources(
    run_id: UUID,
    experiments: ExperimentRepository,
    datasets: DatasetRepository,
    dataset_loader: Callable[[UUID], HistoricalDataset],
) -> tuple[ExperimentRun, tuple[ValidationRun, ...]]:
    run = experiments.get_run(run_id)
    if run is None or run.status is not ExperimentRunStatus.COMPLETED:
        raise AdversarialLineageError("completed experiment run not found")
    _verify_dataset(run, experiments, datasets, dataset_loader)
    validations = tuple(
        validation
        for validation in experiments.list_validations(run_id)
        if validation.validation_type is not ValidationType.ADVERSARIAL_REVIEW
        and validation.status is ValidationStatus.PASSED
    )
    _verify_source_integrity(run, validations)
    _source_fingerprints(validations)
    return run, validations


def _verify_dataset(
    run: ExperimentRun,
    experiments: ExperimentRepository,
    datasets: DatasetRepository,
    dataset_loader: Callable[[UUID], HistoricalDataset],
) -> None:
    experiment = experiments.get(run.experiment_id)
    if experiment is None or datasets.get(experiment.dataset_snapshot_id) is None:
        raise AdversarialLineageError("experiment dataset lineage not found")
    dataset_loader(experiment.dataset_snapshot_id)


def _evaluate(
    run: ExperimentRun,
    validations: tuple[ValidationRun, ...],
    configuration: AdversarialAnalysisConfiguration,
) -> tuple[AdversarialValidationReport, dict[str, object]]:
    report = analyze_adversarial_evidence(run, validations, configuration)
    report_material = {
        "experiment_run_id": str(report.experiment_run_id),
        "generated_from_validation_ids": canonical_value(
            report.generated_from_validation_ids
        ),
        "coverage": canonical_value(report.coverage),
        "findings": canonical_value(report.findings),
        "summary": canonical_value(report.summary),
        "analyzer_version": report.analyzer_version,
    }
    material: dict[str, object] = {
        "sources": _source_fingerprints(validations),
        "configuration": canonical_value(configuration),
        "report": report_material,
    }
    fingerprint = evidence_fingerprint(material)
    completed = replace(report, fingerprint=fingerprint)
    return completed, {
        "version": ADVERSARIAL_ANALYZER_VERSION,
        **material,
        "fingerprint": fingerprint,
    }


def _source_fingerprints(validations: tuple[ValidationRun, ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for validation in sorted(validations, key=lambda item: str(item.id)):
        fingerprint = validation.configuration.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise AdversarialLineageError(
                f"validation {validation.id} has no reproducibility fingerprint"
            )
        result[str(validation.id)] = fingerprint
    return result


def _verify_source_integrity(
    run: ExperimentRun, validations: tuple[ValidationRun, ...]
) -> None:
    run_fingerprint = run.configuration.get("fingerprint")
    for validation in validations:
        stored = validation.configuration.get("fingerprint")
        if not isinstance(stored, str) or not stored:
            raise AdversarialLineageError("source validation fingerprint is missing")
        if validation.validation_type is ValidationType.BACKTEST:
            if stored != run_fingerprint:
                raise AdversarialLineageError("BACKTEST fingerprint mismatch")
            continue
        material = {
            key: value
            for key, value in validation.configuration.items()
            if key not in {"version", "fingerprint"}
        }
        canonical_material = canonical_value(material)
        if not isinstance(canonical_material, Mapping):
            raise AdversarialLineageError("source evidence is not canonical")
        if evidence_fingerprint(canonical_material) != stored:
            raise AdversarialLineageError(
                f"{validation.validation_type.value} evidence fingerprint mismatch"
            )


def _required_validation(
    experiments: ExperimentRepository, validation_id: UUID
) -> ValidationRun:
    validation = experiments.get_validation(validation_id)
    if validation is None or validation.status is not ValidationStatus.PASSED:
        raise AdversarialLineageError("source validation is missing or incomplete")
    return validation


def _configuration(values: Mapping[str, object]) -> AdversarialAnalysisConfiguration:
    try:
        return AdversarialAnalysisConfiguration(
            max_oos_sharpe_drop=_float(values, "max_oos_sharpe_drop"),
            max_oos_return_drop=_float(values, "max_oos_return_drop"),
            max_oos_drawdown_worsening=_float(
                values, "max_oos_drawdown_worsening"
            ),
            min_profitable_fold_ratio=_float(values, "min_profitable_fold_ratio"),
            max_fold_return_dispersion=_float(values, "max_fold_return_dispersion"),
            max_fold_sharpe_dispersion=_float(values, "max_fold_sharpe_dispersion"),
            max_neighbor_sharpe_delta=_float(values, "max_neighbor_sharpe_delta"),
            min_profitable_parameter_ratio=_float(
                values, "min_profitable_parameter_ratio"
            ),
            max_parameter_sharpe_dispersion=_float(
                values, "max_parameter_sharpe_dispersion"
            ),
            max_stress_return_drop=_float(values, "max_stress_return_drop"),
            max_stress_drawdown_worsening=_float(
                values, "max_stress_drawdown_worsening"
            ),
            max_bootstrap_loss_frequency=_float(values, "max_bootstrap_loss_frequency"),
            max_adverse_bootstrap_drawdown=_float(
                values, "max_adverse_bootstrap_drawdown"
            ),
            max_bootstrap_losing_streak=_integer(values, "max_bootstrap_losing_streak"),
            max_historical_return_percentile=_float(
                values, "max_historical_return_percentile"
            ),
            min_trade_count_for_interpretation=_integer(
                values, "min_trade_count_for_interpretation"
            ),
            max_top_trade_profit_share=_float(values, "max_top_trade_profit_share"),
            max_top_three_profit_share=_float(values, "max_top_three_profit_share"),
        )
    except (TypeError, ValueError) as error:
        raise AdversarialLineageError("invalid adversarial configuration") from error


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AdversarialLineageError(f"{name} is missing")
    return value


def _text(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise AdversarialLineageError(f"{name} is missing")
    return value


def _float(values: Mapping[str, object], name: str) -> float:
    value = values.get(name)
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise AdversarialLineageError(f"{name} is missing")
    return float(value)


def _integer(values: Mapping[str, object], name: str) -> int:
    value = values.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdversarialLineageError(f"{name} is missing")
    return value
