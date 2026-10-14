from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str | None = None
    jwt_secret_key: str | None = None
    web_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
