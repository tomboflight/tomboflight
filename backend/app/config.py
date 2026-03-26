from functools import lru_cache
from pathlib import Path

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

    # Upload / storage
    upload_storage_dir: str = "storage/uploads"
    render_disk_mount_path: str = ""
    upload_max_image_mb: int = 10
    upload_max_document_mb: int = 25

    upload_image_content_types: str = (
        "image/jpeg,"
        "image/png,"
        "image/webp"
    )

    upload_document_content_types: str = (
        "application/pdf,"
        "image/jpeg,"
        "image/png,"
        "image/webp"
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

    @property
    def upload_image_content_types_list(self) -> list[str]:
        return [
            value.strip().lower()
            for value in self.upload_image_content_types.split(",")
            if value.strip()
        ]

    @property
    def upload_document_content_types_list(self) -> list[str]:
        return [
            value.strip().lower()
            for value in self.upload_document_content_types.split(",")
            if value.strip()
        ]

    @property
    def upload_max_image_bytes(self) -> int:
        return self.upload_max_image_mb * 1024 * 1024

    @property
    def upload_max_document_bytes(self) -> int:
        return self.upload_max_document_mb * 1024 * 1024

    @property
    def upload_root_path(self) -> str:
        mount_path = str(self.render_disk_mount_path or "").strip().rstrip("/")
        if mount_path:
            return str(Path(mount_path) / "uploads")
        return str(Path(self.upload_storage_dir))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()