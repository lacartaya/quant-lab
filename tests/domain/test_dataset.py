from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from quant.domain import AdjustmentPolicy, DatasetSnapshot

START = datetime(2025, 1, 1, tzinfo=UTC)


def make_snapshot(*, end_at: datetime) -> DatasetSnapshot:
    return DatasetSnapshot(
        uuid4(),
        "provider",
        "US equities",
        "ABC",
        "daily",
        START,
        end_at,
        "2025-01",
        "sha256:abc",
        "snapshot/bars.parquet",
        AdjustmentPolicy.RAW,
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_valid_snapshot_has_immutable_identity() -> None:
    snapshot = make_snapshot(end_at=START + timedelta(days=1))
    assert snapshot.end_at > snapshot.start_at
    field_name = "checksum"
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, field_name, "different")


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(days=-1)])
def test_invalid_snapshot_date_range_is_rejected(offset: timedelta) -> None:
    with pytest.raises(ValueError, match="end_at must be after start_at"):
        make_snapshot(end_at=START + offset)
