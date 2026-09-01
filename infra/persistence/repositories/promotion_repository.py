from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.persistence.models import PaperPromotionModel
from quant.domain import PaperPromotion, PaperPromotionStatus


def _domain(row: PaperPromotionModel) -> PaperPromotion:
    return PaperPromotion(
        id=row.id,
        hypothesis_id=row.hypothesis_id,
        strategy_version_id=row.strategy_version_id,
        experiment_id=row.experiment_id,
        experiment_run_id=row.experiment_run_id,
        validation_gate_id=row.validation_gate_id,
        dataset_snapshot_id=row.dataset_snapshot_id,
        gate_policy_id=row.gate_policy_id,
        gate_policy_version=row.gate_policy_version,
        gate_decision=row.gate_decision,
        status=PaperPromotionStatus(row.status),
        reason=row.reason,
        approval_actor=row.approval_actor,
        requested_at=row.requested_at,
        approved_at=row.approved_at,
        created_at=row.created_at,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        revocation_reason=row.revocation_reason,
    )


def _model(value: PaperPromotion) -> PaperPromotionModel:
    return PaperPromotionModel(
        id=value.id,
        hypothesis_id=value.hypothesis_id,
        strategy_version_id=value.strategy_version_id,
        experiment_id=value.experiment_id,
        experiment_run_id=value.experiment_run_id,
        validation_gate_id=value.validation_gate_id,
        dataset_snapshot_id=value.dataset_snapshot_id,
        gate_policy_id=value.gate_policy_id,
        gate_policy_version=value.gate_policy_version,
        gate_decision=value.gate_decision,
        status=value.status.value,
        reason=value.reason,
        approval_actor=value.approval_actor,
        requested_at=value.requested_at,
        approved_at=value.approved_at,
        created_at=value.created_at,
        revoked_at=value.revoked_at,
        revoked_by=value.revoked_by,
        revocation_reason=value.revocation_reason,
    )


class SQLAlchemyPaperPromotionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: PaperPromotion) -> None:
        self._session.add(_model(value))
        self._session.flush()

    def save(self, value: PaperPromotion) -> None:
        self._session.merge(_model(value))
        self._session.flush()

    def get(self, promotion_id: UUID) -> PaperPromotion | None:
        row = self._session.get(PaperPromotionModel, promotion_id)
        return _domain(row) if row else None

    def get_for_lineage(
        self, run_id: UUID, strategy_version_id: UUID, gate_id: UUID
    ) -> PaperPromotion | None:
        row = self._session.scalar(
            select(PaperPromotionModel).where(
                PaperPromotionModel.experiment_run_id == run_id,
                PaperPromotionModel.strategy_version_id == strategy_version_id,
                PaperPromotionModel.validation_gate_id == gate_id,
            )
        )
        return _domain(row) if row else None

    def list_all(self) -> Sequence[PaperPromotion]:
        rows = self._session.scalars(
            select(PaperPromotionModel).order_by(
                PaperPromotionModel.created_at, PaperPromotionModel.id
            )
        )
        return [_domain(row) for row in rows]
