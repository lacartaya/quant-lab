from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from quant.domain import MarketBar


class DatasetStorageError(RuntimeError):
    """Raised when snapshot data cannot be safely stored or read."""


class DatasetStorage(Protocol):
    def write(self, snapshot_id: UUID, bars: Sequence[MarketBar]) -> str: ...

    def read(self, storage_location: str) -> tuple[MarketBar, ...]: ...
