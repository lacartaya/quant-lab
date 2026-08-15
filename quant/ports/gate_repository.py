from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from quant.domain import ValidationGateResult


class GateRepository(Protocol):
    def add(self, result: ValidationGateResult) -> None: ...

    def get(self, evaluation_id: UUID) -> ValidationGateResult | None: ...

    def list_for_run(self, run_id: UUID) -> Sequence[ValidationGateResult]: ...
