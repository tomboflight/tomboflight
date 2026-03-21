from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tomb of Light API"
    app_version: str = "1.0.0"
    environment: str = "development"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "tomboflight"

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    allowed_origins: str = (
        "http://127.0.0.1:5500,"
        "http://localhost:5500,"
        "http://[::1]:5500,"
        "http://127.0.0.1:8000,"
        "http://localhost:8000,"
        "http://[::1]:8000,"
        "https://tomboflight.com,"
        "https://www.tomboflight.com"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()