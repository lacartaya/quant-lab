from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from quant.domain.knowledge import KnowledgeQuery, KnowledgeRecord


class KnowledgeRepository(Protocol):
    def add(self, record: KnowledgeRecord) -> None: ...

    def get(self, record_id: UUID) -> KnowledgeRecord | None: ...

    def list_for_hypothesis(self, hypothesis_id: UUID) -> Sequence[KnowledgeRecord]: ...

    def search(self, query: KnowledgeQuery) -> Sequence[KnowledgeRecord]: ...

    def list_all(self) -> Sequence[KnowledgeRecord]: ...
