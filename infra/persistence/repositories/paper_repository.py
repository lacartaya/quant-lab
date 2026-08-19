from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.persistence.mappers import (
    paper_observation_from_model,
    paper_observation_to_model,
    paper_participant_from_model,
    paper_participant_to_model,
    paper_session_from_model,
    paper_session_to_model,
    paper_snapshot_from_model,
    paper_snapshot_to_model,
)
from infra.persistence.models import (
    PaperObservationModel,
    PaperParticipantModel,
    PaperSessionModel,
    PaperSnapshotModel,
)
from quant.domain.paper import (
    PaperObservation,
    PaperParticipant,
    PaperSession,
    PaperSnapshot,
)


class SQLAlchemyPaperRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_session(self, value: PaperSession) -> None:
        self._session.add(paper_session_to_model(value))
        self._session.flush()

    def save_session(self, value: PaperSession) -> None:
        self._session.merge(paper_session_to_model(value))
        self._session.flush()

    def get_session(self, session_id: UUID) -> PaperSession | None:
        row = self._session.get(PaperSessionModel, session_id)
        return paper_session_from_model(row) if row else None

    def list_sessions(self) -> Sequence[PaperSession]:
        statement = select(PaperSessionModel).order_by(
            PaperSessionModel.created_at, PaperSessionModel.id
        )
        return [
            paper_session_from_model(row) for row in self._session.scalars(statement)
        ]

    def add_participant(self, value: PaperParticipant) -> None:
        self._session.add(paper_participant_to_model(value))
        self._session.flush()

    def save_participant(self, value: PaperParticipant) -> None:
        self._session.merge(paper_participant_to_model(value))
        self._session.flush()

    def get_participant(self, participant_id: UUID) -> PaperParticipant | None:
        row = self._session.get(PaperParticipantModel, participant_id)
        return paper_participant_from_model(row) if row else None

    def list_participants(self, session_id: UUID) -> Sequence[PaperParticipant]:
        statement = (
            select(PaperParticipantModel)
            .where(PaperParticipantModel.session_id == session_id)
            .order_by(PaperParticipantModel.created_at, PaperParticipantModel.id)
        )
        return [
            paper_participant_from_model(row)
            for row in self._session.scalars(statement)
        ]

    def add_observation(self, value: PaperObservation) -> None:
        self._session.add(paper_observation_to_model(value))
        self._session.flush()

    def get_observation(
        self, session_id: UUID, timestamp: datetime
    ) -> PaperObservation | None:
        statement = select(PaperObservationModel).where(
            PaperObservationModel.session_id == session_id,
            PaperObservationModel.timestamp == timestamp,
        )
        row = self._session.scalar(statement)
        return paper_observation_from_model(row) if row else None

    def list_observations(self, session_id: UUID) -> Sequence[PaperObservation]:
        statement = (
            select(PaperObservationModel)
            .where(PaperObservationModel.session_id == session_id)
            .order_by(PaperObservationModel.timestamp, PaperObservationModel.id)
        )
        return [
            paper_observation_from_model(row)
            for row in self._session.scalars(statement)
        ]

    def add_snapshot(self, value: PaperSnapshot) -> None:
        self._session.add(paper_snapshot_to_model(value))
        self._session.flush()

    def latest_snapshot(self, participant_id: UUID) -> PaperSnapshot | None:
        statement = (
            select(PaperSnapshotModel)
            .where(PaperSnapshotModel.participant_id == participant_id)
            .order_by(
                PaperSnapshotModel.observation_timestamp.desc(),
                PaperSnapshotModel.id.desc(),
            )
            .limit(1)
        )
        row = self._session.scalar(statement)
        return paper_snapshot_from_model(row) if row else None

    def list_snapshots(self, participant_id: UUID) -> Sequence[PaperSnapshot]:
        statement = (
            select(PaperSnapshotModel)
            .where(PaperSnapshotModel.participant_id == participant_id)
            .order_by(PaperSnapshotModel.observation_timestamp, PaperSnapshotModel.id)
        )
        return [
            paper_snapshot_from_model(row) for row in self._session.scalars(statement)
        ]
