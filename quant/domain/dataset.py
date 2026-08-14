from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from quant.domain._validation import as_utc, require_text, require_uuid


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    id: UUID
    provider: str
    market: str
    instrument: str
    timeframe: str
    start_at: datetime
    end_at: datetime
    version: str
    checksum: str
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_text(self.provider, "provider")
        require_text(self.instrument, "instrument")
        require_text(self.version, "version")
        require_text(self.checksum, "checksum")
        start_at = as_utc(self.start_at, "start_at")
        end_at = as_utc(self.end_at, "end_at")
        if end_at <= start_at:
            raise ValueError("end_at must be after start_at")
        object.__setattr__(self, "start_at", start_at)
        object.__setattr__(self, "end_at", end_at)
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))
