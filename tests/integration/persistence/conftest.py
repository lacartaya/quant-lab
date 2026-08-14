from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from infra.persistence.database import create_database_engine


@pytest.fixture
def postgres_session() -> Iterator[Session]:
    engine = create_database_engine()
    try:
        connection = engine.connect()
    except OperationalError as error:
        engine.dispose()
        pytest.skip(f"PostgreSQL is not available: {error}")

    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
