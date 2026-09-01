from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from apps.api.schemas import (
    ExperimentDetailResponse,
    ExperimentRunResponse,
    ExperimentSummaryResponse,
    GateResponse,
    HypothesisResponse,
    KnowledgeResponse,
    PriorArtResponse,
    ValidationResponse,
)
from quant.application import ExperimentDetail, ExperimentSummary
from quant.domain import (
    ExperimentRun,
    Hypothesis,
    MetricSet,
    ValidationGateResult,
    ValidationRun,
)
from quant.domain.knowledge import (
    KnowledgeRecord,
    PriorArtCheckResult,
    PriorArtMatchType,
)


def json_value(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (UUID, datetime)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: json_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence):
        return [json_value(item) for item in value]
    raise TypeError(f"unsupported API value: {type(value).__name__}")


def experiment_summary(value: ExperimentSummary) -> ExperimentSummaryResponse:
    return ExperimentSummaryResponse(
        experiment_id=value.experiment.id,
        hypothesis_id=value.experiment.hypothesis_id,
        strategy_version_id=value.experiment.strategy_version_id,
        dataset_snapshot_id=value.experiment.dataset_snapshot_id,
        status=value.experiment.status.value,
        created_at=value.experiment.created_at,
        latest_run_id=value.latest_run.id if value.latest_run else None,
        latest_run_status=value.latest_run.status.value if value.latest_run else None,
        validation_coverage=[item.value for item in value.validation_types],
        latest_gate_decision=value.latest_gate.decision.value
        if value.latest_gate
        else None,
    )


def experiment_detail(value: ExperimentDetail) -> ExperimentDetailResponse:
    dataset = value.dataset
    return ExperimentDetailResponse(
        experiment=json_value(value.experiment),
        hypothesis=json_value(value.hypothesis),
        strategy=json_value(value.strategy),
        strategy_version=json_value(value.strategy_version),
        dataset_snapshot={
            "id": dataset.id,
            "provider": dataset.provider,
            "market": dataset.market,
            "instrument": dataset.instrument,
            "timeframe": dataset.timeframe,
            "start_at": dataset.start_at,
            "end_at": dataset.end_at,
            "requested_start_at": dataset.start_at,
            "requested_end_at": dataset.end_at,
            "actual_start_at": value.dataset_actual_start_at,
            "actual_end_at": value.dataset_actual_end_at,
            "bar_count": value.dataset_bar_count,
            "version": dataset.version,
            "checksum": dataset.checksum,
            "adjustment_policy": dataset.adjustment_policy.value,
            "created_at": dataset.created_at,
            "storage_managed": True,
        },
        runs=[json_value(item) for item in value.runs],
    )


def experiment_run(value: ExperimentRun) -> ExperimentRunResponse:
    configuration = dict(value.configuration)
    execution = configuration.get("execution")
    analytics = (
        execution.get("analytics")
        if isinstance(execution, Mapping)
        else configuration.get("analytics")
    )
    analytics_version = (
        analytics.get("version") if isinstance(analytics, Mapping) else None
    )
    return ExperimentRunResponse(
        id=value.id,
        experiment_id=value.experiment_id,
        status=value.status.value,
        git_commit=value.git_commit,
        engine_version=value.engine_version,
        fee_model_version=value.fee_model_version,
        slippage_model_version=value.slippage_model_version,
        analytics_version=str(analytics_version)
        if analytics_version is not None
        else None,
        result_fingerprint=_optional_string(
            configuration.get("fingerprint") or configuration.get("result_fingerprint")
        ),
        configuration=json_value(configuration),
        started_at=value.started_at,
        completed_at=value.completed_at,
    )


def validation(value: ValidationRun) -> ValidationResponse:
    return ValidationResponse(
        id=value.id,
        experiment_run_id=value.experiment_run_id,
        validation_type=value.validation_type.value,
        status=value.status.value,
        metrics=metric_set(value.metric_set) if value.metric_set is not None else None,
        evidence=json_value(value.configuration),
        created_at=value.created_at,
        completed_at=value.completed_at,
    )


def metric_set(value: MetricSet) -> dict[str, Any]:
    mapped = json_value(value)
    if not isinstance(mapped, dict):
        raise TypeError("metric mapping must be an object")
    return mapped


def hypothesis(value: Hypothesis) -> HypothesisResponse:
    return HypothesisResponse(
        id=value.id,
        title=value.title,
        description=value.description,
        strategy_family=value.strategy_family,
        market=value.market,
        timeframe=value.timeframe,
        status=value.status.value,
        reconsideration_conditions=value.reconsideration_conditions,
        created_at=value.created_at,
    )


def knowledge(value: KnowledgeRecord) -> KnowledgeResponse:
    return KnowledgeResponse(
        id=value.id,
        hypothesis_id=value.hypothesis_id,
        derived_from_hypothesis_id=value.derived_from_hypothesis_id,
        status=value.status.value,
        signature=json_value(value.signature),
        tested_start_at=value.tested_start_at,
        tested_end_at=value.tested_end_at,
        summary=value.summary,
        rejection_reason=value.rejection_reason,
        reconsideration_conditions=[
            item.value for item in value.reconsideration_conditions
        ],
        reconsideration_rationale=value.reconsideration_rationale,
        evidence_refs=[json_value(item) for item in value.evidence_refs],
        research_fingerprint=value.research_fingerprint,
        created_at=value.created_at,
    )


def prior_art(value: PriorArtCheckResult) -> PriorArtResponse:
    matches = [json_value(item) for item in value.matches]
    exact = [
        item
        for item, source in zip(matches, value.matches, strict=True)
        if source.match_type is PriorArtMatchType.EXACT
    ]
    similar = [
        item
        for item, source in zip(matches, value.matches, strict=True)
        if source.match_type is not PriorArtMatchType.EXACT
    ]
    rejected = [
        item
        for item, source in zip(matches, value.matches, strict=True)
        if source.status.value == "rejected"
    ]
    return PriorArtResponse(
        candidate_fingerprint=value.candidate_fingerprint,
        duplicate_detected=value.duplicate_detected,
        blocked_by_rejected_prior_art=value.blocked_by_rejected_prior_art,
        exact_matches=exact,
        similar_matches=similar,
        rejected_matches=rejected,
        fingerprint=value.fingerprint,
    )


def gate(value: ValidationGateResult) -> GateResponse:
    return GateResponse(
        id=value.id,
        experiment_run_id=value.experiment_run_id,
        strategy_version_id=value.strategy_version_id,
        policy_id=value.policy_id,
        policy_version=value.policy_version,
        decision=value.decision.value,
        rule_results=[json_value(item) for item in value.rule_results],
        source_evidence=json_value(value.source_evidence),
        policy=json_value(value.policy),
        evaluator_version=value.evaluator_version,
        evaluated_at=value.evaluated_at,
        fingerprint=value.fingerprint,
        decision_semantics=(
            "Policy eligibility only; not a profitability, safety, or deployment claim."
        ),
    )


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
