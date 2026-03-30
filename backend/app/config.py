from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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

    nft_chain: str = Field(
        default="base-mainnet",
        validation_alias=AliasChoices("NFT_CHAIN"),
    )
    nft_contract_address: str = Field(
        default="",
        validation_alias=AliasChoices("NFT_CONTRACT_ADDRESS"),
    )
    nft_contract_abi_json: str = Field(
        default="",
        validation_alias=AliasChoices(
            "NFT_CONTRACT_ABI_JSON",
            "NFT_CONTRACT_ABI",
            "NFT_ABI_JSON",
        ),
    )
    nft_mint_function_name: str = Field(
        default="mintAnchor",
        validation_alias=AliasChoices("NFT_MINT_FUNCTION_NAME"),
    )
    nft_minter_private_key: str = Field(
        default="",
        validation_alias=AliasChoices("NFT_MINTER_PRIVATE_KEY"),
    )
    nft_default_recipient_wallet: str = Field(
        default="",
        validation_alias=AliasChoices("NFT_DEFAULT_RECIPIENT_WALLET"),
    )
    nft_rpc_url: str = Field(
        default="",
        validation_alias=AliasChoices("NFT_RPC_URL"),
    )
    nft_mint_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("NFT_MINTING_ENABLED", "NFT_MINT_ENABLED"),
    )
    nft_org_mint_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("NFT_ORG_MINT_ENABLED"),
    )
    hash_salt: str = Field(
        default="",
        validation_alias=AliasChoices("HASH_SALT"),
    )
    metadata_base_url: str = Field(
        default="https://metadata.tomboflight.com/v1",
        validation_alias=AliasChoices("METADATA_BASE_URL"),
    )
    poster_base_url: str = Field(
        default="https://metadata.tomboflight.com/v1/posters",
        validation_alias=AliasChoices("POSTER_BASE_URL"),
    )
    public_token_external_base_url: str = Field(
        default="https://tomboflight.com/token",
        validation_alias=AliasChoices("PUBLIC_TOKEN_EXTERNAL_BASE_URL"),
    )
    ipfs_mirror_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("IPFS_MIRROR_ENABLED"),
    )
    ipfs_gateway_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("IPFS_GATEWAY_BASE_URL"),
    )
    pinata_jwt: str = Field(
        default="",
        validation_alias=AliasChoices("PINATA_JWT"),
    )

    r2_account_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_ACCOUNT_ID",
            "CLOUDFLARE_ACCOUNT_ID",
            "R2_ACCOUNT",
        ),
    )
    r2_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_ACCESS_KEY_ID",
            "R2_ACCESS_KEY",
            "CLOUDFLARE_R2_ACCESS_KEY_ID",
            "AWS_ACCESS_KEY_ID",
        ),
    )
    r2_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_SECRET_ACCESS_KEY",
            "R2_SECRET_KEY",
            "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY",
        ),
    )
    r2_endpoint_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_ENDPOINT_URL",
            "R2_S3_ENDPOINT",
            "R2_ENDPOINT",
            "CLOUDFLARE_R2_ENDPOINT_URL",
            "AWS_S3_ENDPOINT",
        ),
    )
    r2_region: str = Field(
        default="auto",
        validation_alias=AliasChoices("R2_REGION", "AWS_REGION"),
    )
    r2_bucket: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_BUCKET",
            "R2_BUCKET_NAME",
            "CLOUDFLARE_R2_BUCKET",
        ),
    )
    r2_private_bucket: str = Field(
        default="",
        validation_alias=AliasChoices("R2_PRIVATE_BUCKET"),
    )
    r2_metadata_bucket: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_METADATA_BUCKET",
            "R2_PUBLIC_METADATA_BUCKET",
            "R2_METADATA_BUCKET_NAME",
        ),
    )
    r2_poster_bucket: str = Field(
        default="",
        validation_alias=AliasChoices(
            "R2_POSTER_BUCKET",
            "R2_PUBLIC_POSTER_BUCKET",
            "R2_POSTER_BUCKET_NAME",
        ),
    )
    r2_force_path_style: bool = Field(
        default=True,
        validation_alias=AliasChoices("R2_FORCE_PATH_STYLE"),
    )
    public_storage_dir: str = Field(
        default="storage/public",
        validation_alias=AliasChoices("PUBLIC_STORAGE_DIR"),
    )

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

    @property
    def r2_resolved_endpoint_url(self) -> str:
        explicit = str(self.r2_endpoint_url or "").strip().rstrip("/")
        if explicit:
            return explicit

        account_id = str(self.r2_account_id or "").strip()
        if account_id:
            return f"https://{account_id}.r2.cloudflarestorage.com"

        return ""

    @property
    def public_storage_root_path(self) -> str:
        mount_path = str(self.render_disk_mount_path or "").strip().rstrip("/")
        if mount_path:
            return str(Path(mount_path) / "public")
        return str(Path(self.public_storage_dir))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
