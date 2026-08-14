from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from quant.domain import Strategy, StrategyVersion


class StrategyRepository(Protocol):
    def add(self, strategy: Strategy) -> None: ...

    def get(self, strategy_id: UUID) -> Strategy | None: ...

    def add_version(self, version: StrategyVersion) -> None: ...

    def get_version(self, version_id: UUID) -> StrategyVersion | None: ...

    def list_versions(self, strategy_id: UUID) -> Sequence[StrategyVersion]: ...
