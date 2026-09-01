from dataclasses import dataclass
from datetime import datetime

from quant.domain._validation import as_utc


@dataclass(frozen=True, slots=True)
class OutOfSampleConfiguration:
    training_start: datetime
    training_end: datetime
    test_start: datetime
    test_end: datetime

    def __post_init__(self) -> None:
        values = {
            name: as_utc(getattr(self, name), name)
            for name in ("training_start", "training_end", "test_start", "test_end")
        }
        if values["training_end"] < values["training_start"]:
            raise ValueError("training_end cannot precede training_start")
        if values["test_end"] < values["test_start"]:
            raise ValueError("test_end cannot precede test_start")
        if values["training_end"] >= values["test_start"]:
            raise ValueError("training and test ranges must be temporally separated")
        for name, value in values.items():
            object.__setattr__(self, name, value)
