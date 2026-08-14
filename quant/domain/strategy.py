from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from quant.domain._validation import (
    as_utc,
    immutable_mapping,
    require_text,
    require_uuid,
)


@dataclass(frozen=True, slots=True)
class Strategy:
    id: UUID
    name: str
    description: str
    strategy_family: str
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_text(self.name, "name")
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class StrategyVersion:
    id: UUID
    strategy_id: UUID
    version: str
    git_commit: str
    parameters: Mapping[str, object]
    created_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.strategy_id, "strategy_id")
        require_text(self.version, "version")
        require_text(self.git_commit, "git_commit")
        object.__setattr__(self, "parameters", immutable_mapping(self.parameters))
        object.__setattr__(self, "created_at", as_utc(self.created_at, "created_at"))
