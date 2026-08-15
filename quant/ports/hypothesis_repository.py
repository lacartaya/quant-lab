from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from quant.domain import Hypothesis, HypothesisStatus


class HypothesisRepository(Protocol):
    def add(self, hypothesis: Hypothesis) -> None: ...

    def save(self, hypothesis: Hypothesis) -> None: ...

    def get(self, hypothesis_id: UUID) -> Hypothesis | None: ...

    def list_by_status(self, status: HypothesisStatus) -> Sequence[Hypothesis]: ...

    def list_all(self) -> Sequence[Hypothesis]: ...
