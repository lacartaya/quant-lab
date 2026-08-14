from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from infra.market_data import CsvMarketDataProvider, LocalParquetDatasetStorage
from infra.persistence.repositories import SQLAlchemyDatasetRepository
from quant.application import (
    CreateDatasetSnapshot,
    DatasetIntegrityError,
    LoadDatasetSnapshot,
    canonical_bars_checksum,
)
from quant.domain import AdjustmentPolicy, HistoricalDataRequest

pytestmark = pytest.mark.integration

FIXTURE = Path("tests/fixtures/market_data/sample_ohlcv.csv")


def make_request() -> HistoricalDataRequest:
    return HistoricalDataRequest(
        "US equities",
        "ABC",
        "daily",
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 4, tzinfo=UTC),
        AdjustmentPolicy.RAW,
    )


def test_snapshot_creation_and_reload_after_service_recreation(
    postgres_session: Session, tmp_path: Path
) -> None:
    repository = SQLAlchemyDatasetRepository(postgres_session)
    storage = LocalParquetDatasetStorage(tmp_path)
    provider = CsvMarketDataProvider(FIXTURE)
    normalized = provider.load_historical(make_request())

    snapshot = CreateDatasetSnapshot(provider, storage, repository)(make_request())
    stored_path = tmp_path / snapshot.storage_location
    assert stored_path.exists()
    assert snapshot.checksum == canonical_bars_checksum(normalized.bars)
    assert snapshot.provider == "csv"
    assert snapshot.adjustment_policy is AdjustmentPolicy.RAW
    assert repository.get(snapshot.id) == snapshot

    reloaded = LoadDatasetSnapshot(
        LocalParquetDatasetStorage(tmp_path),
        SQLAlchemyDatasetRepository(postgres_session),
    )(snapshot.id)
    assert reloaded.bars == normalized.bars
    assert reloaded.market == normalized.market
    assert reloaded.instrument == normalized.instrument
    assert reloaded.timeframe == normalized.timeframe


def test_corrupted_snapshot_is_never_loaded(
    postgres_session: Session, tmp_path: Path
) -> None:
    repository = SQLAlchemyDatasetRepository(postgres_session)
    storage = LocalParquetDatasetStorage(tmp_path)
    snapshot = CreateDatasetSnapshot(
        CsvMarketDataProvider(FIXTURE), storage, repository
    )(make_request())
    (tmp_path / snapshot.storage_location).write_bytes(b"not a parquet file")

    with pytest.raises(DatasetIntegrityError, match="cannot be read"):
        LoadDatasetSnapshot(storage, repository)(snapshot.id)
