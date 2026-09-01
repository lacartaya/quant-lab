from datetime import datetime
from decimal import Decimal
from typing import cast

from infra.persistence.models import (
    PaperObservationModel,
    PaperParticipantModel,
    PaperSessionModel,
    PaperSnapshotModel,
)
from quant.domain import AdjustmentPolicy, MarketBar, MetricSet
from quant.domain.paper import (
    PaperObservation,
    PaperParticipant,
    PaperParticipantStatus,
    PaperSession,
    PaperSessionStatus,
    PaperSnapshot,
)


def paper_session_to_model(value: PaperSession) -> PaperSessionModel:
    return PaperSessionModel(
        id=value.id,
        market=value.market,
        instrument=value.instrument,
        timeframe=value.timeframe,
        adjustment_policy=value.adjustment_policy.value,
        provider_name=value.provider_name,
        provider_version=value.provider_version,
        dataset_snapshot_id=value.dataset_snapshot_id,
        dataset_checksum=value.dataset_checksum,
        evaluation_start=value.evaluation_start,
        warmup_bars=[bar_to_json(item) for item in value.warmup_bars],
        status=value.status.value,
        started_at=value.started_at,
        completed_at=value.completed_at,
        last_processed_at=value.last_processed_at,
        last_error=value.last_error,
        created_at=value.created_at,
    )


def paper_session_from_model(value: PaperSessionModel) -> PaperSession:
    return PaperSession(
        id=value.id,
        market=value.market,
        instrument=value.instrument,
        timeframe=value.timeframe,
        adjustment_policy=AdjustmentPolicy(value.adjustment_policy),
        provider_name=value.provider_name,
        provider_version=value.provider_version,
        dataset_snapshot_id=value.dataset_snapshot_id,
        dataset_checksum=value.dataset_checksum,
        evaluation_start=value.evaluation_start,
        warmup_bars=tuple(bar_from_json(item) for item in value.warmup_bars),
        status=PaperSessionStatus(value.status),
        started_at=value.started_at,
        completed_at=value.completed_at,
        last_processed_at=value.last_processed_at,
        last_error=value.last_error,
        created_at=value.created_at,
    )


def paper_participant_to_model(value: PaperParticipant) -> PaperParticipantModel:
    return PaperParticipantModel(
        id=value.id,
        session_id=value.session_id,
        strategy_version_id=value.strategy_version_id,
        source_gate_evaluation_id=value.source_gate_evaluation_id,
        paper_promotion_id=value.paper_promotion_id,
        status=value.status.value,
        initial_capital=str(value.initial_capital),
        execution_configuration=dict(value.execution_configuration),
        paper_engine_version=value.paper_engine_version,
        started_at=value.started_at,
        stopped_at=value.stopped_at,
        last_processed_at=value.last_processed_at,
        last_successful_at=value.last_successful_at,
        last_error=value.last_error,
        created_at=value.created_at,
    )


def paper_participant_from_model(value: PaperParticipantModel) -> PaperParticipant:
    return PaperParticipant(
        id=value.id,
        session_id=value.session_id,
        strategy_version_id=value.strategy_version_id,
        source_gate_evaluation_id=value.source_gate_evaluation_id,
        paper_promotion_id=value.paper_promotion_id,
        status=PaperParticipantStatus(value.status),
        initial_capital=Decimal(value.initial_capital),
        execution_configuration=value.execution_configuration,
        paper_engine_version=value.paper_engine_version,
        started_at=value.started_at,
        stopped_at=value.stopped_at,
        last_processed_at=value.last_processed_at,
        last_successful_at=value.last_successful_at,
        last_error=value.last_error,
        created_at=value.created_at,
    )


def paper_observation_to_model(value: PaperObservation) -> PaperObservationModel:
    return PaperObservationModel(
        id=value.id,
        session_id=value.session_id,
        timestamp=value.bar.timestamp,
        bar=bar_to_json(value.bar),
        content_checksum=value.content_checksum,
        processed_at=value.processed_at,
    )


def paper_observation_from_model(value: PaperObservationModel) -> PaperObservation:
    return PaperObservation(
        value.id,
        value.session_id,
        bar_from_json(value.bar),
        value.content_checksum,
        value.processed_at,
    )


def paper_snapshot_to_model(value: PaperSnapshot) -> PaperSnapshotModel:
    return PaperSnapshotModel(
        id=value.id,
        participant_id=value.participant_id,
        observation_id=value.observation_id,
        observation_timestamp=value.observation_timestamp,
        processed_bar_count=value.processed_bar_count,
        material_result=dict(value.material_result),
        metrics=metric_to_json(value.metrics),
        fingerprint=value.fingerprint,
        created_at=value.created_at,
    )


def paper_snapshot_from_model(value: PaperSnapshotModel) -> PaperSnapshot:
    return PaperSnapshot(
        value.id,
        value.participant_id,
        value.observation_id,
        value.observation_timestamp,
        value.processed_bar_count,
        value.material_result,
        metric_from_json(value.metrics),
        value.fingerprint,
        value.created_at,
    )


def bar_to_json(value: MarketBar) -> dict[str, object]:
    return {
        "timestamp": value.timestamp.isoformat(),
        "open": str(value.open),
        "high": str(value.high),
        "low": str(value.low),
        "close": str(value.close),
        "volume": str(value.volume),
    }


def bar_from_json(value: dict[str, object]) -> MarketBar:
    return MarketBar(
        datetime.fromisoformat(cast(str, value["timestamp"])),
        Decimal(cast(str, value["open"])),
        Decimal(cast(str, value["high"])),
        Decimal(cast(str, value["low"])),
        Decimal(cast(str, value["close"])),
        Decimal(cast(str, value["volume"])),
    )


def metric_to_json(value: MetricSet) -> dict[str, object]:
    return {name: getattr(value, name) for name in value.__dataclass_fields__}


def metric_from_json(value: dict[str, object]) -> MetricSet:
    return MetricSet(**value)  # type: ignore[arg-type]
