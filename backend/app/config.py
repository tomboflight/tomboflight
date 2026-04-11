from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_name: str = Field(
        default="Tomb of Light API",
        validation_alias=AliasChoices("APP_NAME"),
    )
    app_version: str = Field(
        default="1.0.0",
        validation_alias=AliasChoices("APP_VERSION"),
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT"),
    )

    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("MONGODB_URI"),
    )
    mongodb_db_name: str = Field(
        default="tomboflight",
        validation_alias=AliasChoices("MONGODB_DB_NAME", "DATABASE_NAME"),
    )

    secret_key: str = Field(
        default="change-me",
        validation_alias=AliasChoices("SECRET_KEY"),
    )
    algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("ALGORITHM"),
    )
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES"),
    )

    stripe_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_SECRET_KEY"),
    )
    stripe_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PUBLISHABLE_KEY"),
    )
    stripe_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_WEBHOOK_SECRET"),
    )
    stripe_billing_portal_configuration_id: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_BILLING_PORTAL_CONFIGURATION_ID"),
    )
    stripe_billing_portal_return_url: str = Field(
        default="https://tomboflight.com/billing.html",
        validation_alias=AliasChoices("STRIPE_BILLING_PORTAL_RETURN_URL"),
    )
    stripe_payment_method_max_cards: int = Field(
        default=3,
        validation_alias=AliasChoices("STRIPE_PAYMENT_METHOD_MAX_CARDS"),
    )
    password_reset_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"),
    )
    password_reset_base_url: str = Field(
        default="https://tomboflight.com/account-security.html",
        validation_alias=AliasChoices("PASSWORD_RESET_BASE_URL"),
    )
    password_reset_preview_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("PASSWORD_RESET_PREVIEW_ENABLED"),
    )

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
    nft_auto_mint_on_review_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("NFT_AUTO_MINT_ON_REVIEW_ENABLED"),
    )
    nft_token_name_prefix: str = Field(
        default="Tomb of Light Legacy Anchor",
        validation_alias=AliasChoices("NFT_TOKEN_NAME_PREFIX"),
    )
    nft_schema_version: str = Field(
        default="tol-nft-1.0",
        validation_alias=AliasChoices("NFT_SCHEMA_VERSION"),
    )
    nft_default_external_url: str = Field(
        default="https://tomboflight.com",
        validation_alias=AliasChoices("NFT_DEFAULT_EXTERNAL_URL"),
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
        default="https://posters.tomboflight.com/v1",
        validation_alias=AliasChoices("POSTER_BASE_URL"),
    )
    public_token_external_base_url: str = Field(
        default="https://tomboflight-api.onrender.com/tokens",
        validation_alias=AliasChoices(
            "PUBLIC_TOKEN_EXTERNAL_BASE_URL",
            "NFT_DEFAULT_EXTERNAL_URL",
        ),
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

    # Email / SMTP
    email_sender: str = Field(
        default="admin@tomboflight.com",
        validation_alias=AliasChoices("EMAIL_SENDER"),
    )
    smtp_host: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=0,
        validation_alias=AliasChoices("SMTP_PORT"),
    )
    smtp_username: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_USERNAME"),
    )
    smtp_password: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_PASSWORD"),
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias=AliasChoices("SMTP_USE_TLS"),
    )

    allowed_origins: str = Field(
        default=(
            "http://127.0.0.1:5500,"
            "http://localhost:5500,"
            "http://[::1]:5500,"
            "http://127.0.0.1:8000,"
            "http://localhost:8000,"
            "http://[::1]:8000,"
            "https://tomboflight.com,"
            "https://www.tomboflight.com"
        ),
        validation_alias=AliasChoices("ALLOWED_ORIGINS"),
    )

    upload_storage_dir: str = Field(
        default="storage/uploads",
        validation_alias=AliasChoices("UPLOAD_STORAGE_DIR"),
    )
    render_disk_mount_path: str = Field(
        default="",
        validation_alias=AliasChoices("RENDER_DISK_MOUNT_PATH"),
    )
    upload_max_image_mb: int = Field(
        default=10,
        validation_alias=AliasChoices("UPLOAD_MAX_IMAGE_MB"),
    )
    upload_max_document_mb: int = Field(
        default=25,
        validation_alias=AliasChoices("UPLOAD_MAX_DOCUMENT_MB"),
    )

    upload_image_content_types: str = Field(
        default="image/jpeg,image/png,image/webp",
        validation_alias=AliasChoices("UPLOAD_IMAGE_CONTENT_TYPES"),
    )
    upload_document_content_types: str = Field(
        default="application/pdf,image/jpeg,image/png,image/webp",
        validation_alias=AliasChoices("UPLOAD_DOCUMENT_CONTENT_TYPES"),
    )

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_ENV_PATH), str(ROOT_ENV_PATH)),
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

    @property
    def metadata_base_url_clean(self) -> str:
        return str(self.metadata_base_url or "").strip().rstrip("/")

    @property
    def poster_base_url_clean(self) -> str:
        return str(self.poster_base_url or "").strip().rstrip("/")

    @property
    def public_token_external_base_url_clean(self) -> str:
        return str(self.public_token_external_base_url or "").strip().rstrip("/")

    @property
    def stripe_billing_portal_return_url_clean(self) -> str:
        return str(self.stripe_billing_portal_return_url or "").strip().rstrip("/")

    @property
    def password_reset_base_url_clean(self) -> str:
        return str(self.password_reset_base_url or "").strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
