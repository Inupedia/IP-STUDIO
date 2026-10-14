from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.assets import router as assets_router
from app.api.bibles import router as bibles_router
from app.api.documents import router as documents_router
from app.api.ips import router as ips_router
from app.api.story import router as story_router
from app.api.templates import router as templates_router
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import Base
from app.security import is_valid_jwt_secret
from app.services.auth import create_workspace_admin

health_router = APIRouter(prefix="/api/v1", tags=["system"])


@health_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(
    *,
    database_url: str | None = None,
    jwt_secret_key: str | None = None,
    bootstrap_admin_email: str | None = None,
    bootstrap_admin_password: str | None = None,
    initialize_schema: bool = False,
    asset_storage_dir: Path | str | None = None,
) -> FastAPI:
    settings = Settings()
    resolved_database_url = database_url or settings.database_url
    if initialize_schema and not (resolved_database_url or "").startswith("sqlite"):
        raise ValueError("Automatic schema creation is restricted to explicit SQLite test databases")

    engine = make_engine(resolved_database_url) if resolved_database_url else None
    session_factory = make_session_factory(engine) if engine else None
    if initialize_schema and engine:
        Base.metadata.create_all(engine)
    if (bootstrap_admin_email is None) != (bootstrap_admin_password is None):
        raise ValueError("Both bootstrap administrator email and password are required")
    if bootstrap_admin_email and bootstrap_admin_password:
        if session_factory is None:
            raise ValueError("Database must be configured before creating the workspace administrator")
        create_workspace_admin(session_factory, bootstrap_admin_email, bootstrap_admin_password)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine:
            engine.dispose()

    application = FastAPI(title="IP Studio API", version="0.1.0", lifespan=lifespan)
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.asset_storage_dir = Path(asset_storage_dir or settings.asset_storage_dir).resolve()
    application.state.asset_max_bytes = settings.asset_max_bytes
    application.state.asset_max_pixels = settings.asset_max_pixels
    configured_secret = jwt_secret_key if jwt_secret_key is not None else settings.jwt_secret_key
    application.state.jwt_secret_key = configured_secret if is_valid_jwt_secret(configured_secret) else None
    allowed_origins = [origin.strip() for origin in settings.web_allowed_origins.split(",") if origin.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(assets_router)
    application.include_router(bibles_router)
    application.include_router(ips_router)
    application.include_router(story_router)
    application.include_router(templates_router)
    application.include_router(documents_router)
    return application


app = create_app()
