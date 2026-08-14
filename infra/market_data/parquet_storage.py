import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from quant.domain import MarketBar
from quant.ports import DatasetStorageError

_DECIMAL_TYPE = pa.decimal128(38, 12)
_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("open", _DECIMAL_TYPE, nullable=False),
        pa.field("high", _DECIMAL_TYPE, nullable=False),
        pa.field("low", _DECIMAL_TYPE, nullable=False),
        pa.field("close", _DECIMAL_TYPE, nullable=False),
        pa.field("volume", _DECIMAL_TYPE, nullable=False),
    ]
)


class LocalParquetDatasetStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def write(self, snapshot_id: UUID, bars: Sequence[MarketBar]) -> str:
        self._root.mkdir(parents=True, exist_ok=True)
        snapshot_directory = self._root / str(snapshot_id)
        if snapshot_directory.exists():
            raise DatasetStorageError(f"snapshot storage already exists: {snapshot_id}")
        table = pa.Table.from_pylist(
            [
                {
                    "timestamp": bar.timestamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in bars
            ],
            schema=_SCHEMA,
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self._root, prefix=".snapshot-", suffix=".parquet", delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            pq.write_table(
                table,
                temporary_path,
                compression="zstd",
                version="2.6",
                coerce_timestamps="us",
                allow_truncated_timestamps=False,
            )
            snapshot_directory.mkdir()
            target = snapshot_directory / "bars.parquet"
            os.replace(temporary_path, target)
        except (OSError, pa.ArrowException) as error:
            raise DatasetStorageError(f"cannot write snapshot {snapshot_id}") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return f"{snapshot_id}/bars.parquet"

    def read(self, storage_location: str) -> tuple[MarketBar, ...]:
        path = self._resolve(storage_location)
        try:
            table = pq.read_table(path, schema=_SCHEMA)
            rows = cast(list[dict[str, object]], table.to_pylist())
            return tuple(self._row_to_bar(row) for row in rows)
        except (OSError, ValueError, pa.ArrowException) as error:
            raise DatasetStorageError(
                f"cannot read snapshot data: {storage_location}"
            ) from error

    def _resolve(self, storage_location: str) -> Path:
        relative = PurePosixPath(storage_location)
        if relative.is_absolute() or ".." in relative.parts:
            raise DatasetStorageError("snapshot storage location must be relative")
        return self._root.joinpath(*relative.parts)

    @staticmethod
    def _row_to_bar(row: dict[str, object]) -> MarketBar:
        return MarketBar(
            timestamp=cast(datetime, row["timestamp"]),
            open=cast(Decimal, row["open"]),
            high=cast(Decimal, row["high"]),
            low=cast(Decimal, row["low"]),
            close=cast(Decimal, row["close"]),
            volume=cast(Decimal, row["volume"]),
        )


def dataset_storage_path(environment: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    return Path(values.get("DATASET_STORAGE_PATH", "./data/snapshots"))
