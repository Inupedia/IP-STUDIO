from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str | None = None
    jwt_secret_key: str | None = None
    web_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    asset_storage_dir: Path = Path("./var/blobs")
    asset_max_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    asset_max_pixels: int = Field(default=40_000_000, gt=0)
    codex_imagegen_executable_path: Path | None = Field(
        default=None,
        validation_alias="IP_STUDIO_CODEX_IMAGEGEN_EXECUTABLE",
    )
