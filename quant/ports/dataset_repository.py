from typing import Protocol
from uuid import UUID

from quant.domain import DatasetSnapshot


class DatasetRepository(Protocol):
    def add(self, snapshot: DatasetSnapshot) -> None: ...

    def get(self, snapshot_id: UUID) -> DatasetSnapshot | None: ...
