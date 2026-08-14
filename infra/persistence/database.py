import os
from collections.abc import Mapping

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def build_database_url(environment: Mapping[str, str] | None = None) -> URL:
    values = os.environ if environment is None else environment
    return URL.create(
        drivername="postgresql+psycopg",
        username=values.get("POSTGRES_USER", "quant_lab"),
        password=values.get("POSTGRES_PASSWORD", "quant_lab_dev"),
        host=values.get("POSTGRES_HOST", "localhost"),
        port=int(values.get("POSTGRES_PORT", "5432")),
        database=values.get("POSTGRES_DB", "quant_lab"),
    )


def create_database_engine(url: URL | str | None = None) -> Engine:
    return create_engine(url or build_database_url(), pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
