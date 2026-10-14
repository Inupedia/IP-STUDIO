from fastapi import APIRouter, FastAPI

health_router = APIRouter(prefix="/api/v1", tags=["system"])


@health_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    application = FastAPI(title="IP Studio API", version="0.1.0")
    application.include_router(health_router)
    return application


app = create_app()
