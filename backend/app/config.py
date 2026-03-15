from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Tomb of Light API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    database_name: str = Field(default="tomboflight", alias="DATABASE_NAME")

    allowed_origins: str = Field(
        default="http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000",
        alias="ALLOWED_ORIGINS",
    )

    jwt_secret_key: str = Field(
        default="change-this-to-a-long-random-secret-for-tomb-of-light",
        alias="JWT_SECRET_KEY",
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


settings = Settings()