import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from quant.domain import (
    DatasetSnapshot,
    HistoricalDataRequest,
    HistoricalDataset,
    MarketBar,
)
from quant.ports import (
    DatasetRepository,
    DatasetStorage,
    DatasetStorageError,
    MarketDataProvider,
)


class DatasetSnapshotNotFoundError(LookupError):
    """Raised when requested snapshot metadata does not exist."""


class DatasetIntegrityError(RuntimeError):
    """Raised when stored data does not match its immutable identity."""


def _canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def canonical_bars_checksum(bars: tuple[MarketBar, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"quant-lab:ohlcv:v1\n")
    for bar in bars:
        fields = (
            bar.timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            _canonical_decimal(bar.open),
            _canonical_decimal(bar.high),
            _canonical_decimal(bar.low),
            _canonical_decimal(bar.close),
            _canonical_decimal(bar.volume),
        )
        digest.update(",".join(fields).encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateDatasetSnapshot:
    provider: MarketDataProvider
    storage: DatasetStorage
    repository: DatasetRepository
    id_factory: Callable[[], UUID] = uuid4
    clock: Callable[[], datetime] = _utc_now

    def __call__(self, request: HistoricalDataRequest) -> DatasetSnapshot:
        dataset = self.provider.load_historical(request)
        self._validate_response(dataset, request)
        checksum = canonical_bars_checksum(dataset.bars)
        snapshot_id = self.id_factory()
        storage_location = self.storage.write(snapshot_id, dataset.bars)
        snapshot = DatasetSnapshot(
            id=snapshot_id,
            provider=self.provider.name,
            market=request.market,
            instrument=request.instrument,
            timeframe=request.timeframe,
            start_at=request.start_at,
            end_at=request.end_at,
            version="ohlcv-v1",
            checksum=checksum,
            storage_location=storage_location,
            adjustment_policy=request.adjustment_policy,
            created_at=self.clock(),
        )
        self.repository.add(snapshot)
        return snapshot

    @staticmethod
    def _validate_response(
        dataset: HistoricalDataset, request: HistoricalDataRequest
    ) -> None:
        if (
            dataset.market != request.market
            or dataset.instrument != request.instrument
            or dataset.timeframe != request.timeframe
            or dataset.adjustment_policy is not request.adjustment_policy
        ):
            raise ValueError("provider response does not match historical data request")
        dataset.validate_range(request.start_at, request.end_at)


@dataclass(frozen=True, slots=True)
class LoadDatasetSnapshot:
    storage: DatasetStorage
    repository: DatasetRepository

    def __call__(self, snapshot_id: UUID) -> HistoricalDataset:
        snapshot = self.repository.get(snapshot_id)
        if snapshot is None:
            raise DatasetSnapshotNotFoundError(
                f"dataset snapshot {snapshot_id} not found"
            )
        try:
            bars = self.storage.read(snapshot.storage_location)
        except DatasetStorageError as error:
            raise DatasetIntegrityError(
                f"dataset snapshot {snapshot_id} cannot be read"
            ) from error
        checksum = canonical_bars_checksum(bars)
        if checksum != snapshot.checksum:
            raise DatasetIntegrityError(
                f"dataset snapshot {snapshot_id} checksum mismatch"
            )
        dataset = HistoricalDataset.from_bars(
            market=snapshot.market,
            instrument=snapshot.instrument,
            timeframe=snapshot.timeframe,
            adjustment_policy=snapshot.adjustment_policy,
            bars=bars,
            metadata={"provider": snapshot.provider, "snapshot_id": str(snapshot.id)},
        )
        dataset.validate_range(snapshot.start_at, snapshot.end_at)
        return dataset
