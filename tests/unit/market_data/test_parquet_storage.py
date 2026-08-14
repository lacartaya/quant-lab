from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from infra.market_data import LocalParquetDatasetStorage, dataset_storage_path
from quant.domain import MarketBar
from quant.ports import DatasetStorageError


def test_parquet_storage_round_trip_is_immutable(tmp_path: Path) -> None:
    storage = LocalParquetDatasetStorage(tmp_path)
    snapshot_id = uuid4()
    bars = (
        MarketBar(
            datetime(2024, 1, 2, tzinfo=UTC),
            Decimal("10.1"),
            Decimal("11.2"),
            Decimal("9.3"),
            Decimal("10.5"),
            Decimal("100"),
        ),
    )
    location = storage.write(snapshot_id, bars)
    assert storage.read(location) == bars
    with pytest.raises(DatasetStorageError, match="already exists"):
        storage.write(snapshot_id, bars)


def test_storage_path_comes_from_environment() -> None:
    assert dataset_storage_path({"DATASET_STORAGE_PATH": "custom/snapshots"}) == Path(
        "custom/snapshots"
    )
