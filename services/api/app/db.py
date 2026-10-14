from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def make_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool
    return create_engine(database_url, **options)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    session_factory: sessionmaker[Session] | None = request.app.state.session_factory
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    with session_factory() as session:
        yield session
