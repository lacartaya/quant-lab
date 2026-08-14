from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quant.domain import MetricSet, ValidationRun, ValidationStatus, ValidationType

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_metric_set_stores_values_without_calculating() -> None:
    metrics = MetricSet(total_return=0.12, sharpe=1.1, trade_count=42)
    assert metrics.total_return == 0.12
    assert metrics.sharpe == 1.1
    assert metrics.trade_count == 42


def test_metric_set_rejects_negative_trade_count() -> None:
    with pytest.raises(ValueError, match="trade_count cannot be negative"):
        MetricSet(trade_count=-1)


@pytest.mark.parametrize("validation_type", list(ValidationType))
def test_validation_run_supports_each_type(validation_type: ValidationType) -> None:
    run = ValidationRun(
        uuid4(),
        uuid4(),
        validation_type,
        ValidationStatus.PENDING,
        None,
        {},
        NOW,
        None,
    )
    assert run.validation_type is validation_type


def test_validation_lifecycle_statuses() -> None:
    assert set(ValidationStatus) == {
        ValidationStatus.PENDING,
        ValidationStatus.RUNNING,
        ValidationStatus.PASSED,
        ValidationStatus.FAILED,
    }
