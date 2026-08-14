from uuid import UUID

from sqlalchemy.orm import Session

from infra.persistence.mappers import dataset_from_model, dataset_to_model
from infra.persistence.models import DatasetSnapshotModel
from quant.domain import DatasetSnapshot


class SQLAlchemyDatasetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, snapshot: DatasetSnapshot) -> None:
        self._session.add(dataset_to_model(snapshot))
        self._session.flush()

    def get(self, snapshot_id: UUID) -> DatasetSnapshot | None:
        row = self._session.get(DatasetSnapshotModel, snapshot_id)
        return dataset_from_model(row) if row is not None else None
