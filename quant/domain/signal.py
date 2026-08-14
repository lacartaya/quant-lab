from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from quant.domain._validation import as_utc, require_enum


class SignalAction(StrEnum):
    LONG = "long"
    FLAT = "flat"


@dataclass(frozen=True, slots=True)
class Signal:
    """Intended strategy state known at the associated completed bar."""

    timestamp: datetime
    action: SignalAction

    def __post_init__(self) -> None:
        require_enum(self.action, SignalAction, "action")
        object.__setattr__(self, "timestamp", as_utc(self.timestamp, "timestamp"))
