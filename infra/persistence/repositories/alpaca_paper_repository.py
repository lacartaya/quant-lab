from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from infra.persistence.models import AlpacaPaperOrderModel
from quant.domain import AlpacaPaperOrder


class SQLAlchemyAlpacaPaperOrderRepository:
    """Append-oriented identity plus latest reconciliation snapshot."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, order: AlpacaPaperOrder) -> None:
        now = datetime.now(UTC)
        existing = self._session.get(AlpacaPaperOrderModel, order.order_id)
        payload = {key: _json_value(value) for key, value in asdict(order).items()}
        if existing is None:
            existing = AlpacaPaperOrderModel(
                order_id=order.order_id,
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                status=order.status,
                order_snapshot=payload,
                first_seen_at=now,
                last_reconciled_at=now,
            )
            self._session.add(existing)
        else:
            existing.status = order.status
            existing.order_snapshot = payload
            existing.last_reconciled_at = now
        self._session.flush()


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
