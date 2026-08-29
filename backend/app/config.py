from functools import lru_cache
import os
from pathlib import Path
from typing import Mapping

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "local", "test"})
DEPLOYED_ENVIRONMENTS = frozenset({"staging", "stage", "production", "prod"})
KNOWN_ENVIRONMENTS = LOCAL_ENVIRONMENTS | DEPLOYED_ENVIRONMENTS
HOSTED_RUNTIME_ENV_VARS = (
    "RENDER",
    "RENDER_SERVICE_ID",
    "K_SERVICE",
    "FLY_APP_NAME",
    "WEBSITE_INSTANCE_ID",
)


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
    admin_identity_registry_json: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("ADMIN_IDENTITY_REGISTRY_JSON"),
    )
    account_separation_audit_targets_json: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("ACCOUNT_SEPARATION_AUDIT_TARGETS_JSON"),
    )
    algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("ALGORITHM"),
    )
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES"),
    )
    csrf_token_expire_minutes: int = Field(
        default=120,
        validation_alias=AliasChoices("CSRF_TOKEN_EXPIRE_MINUTES"),
    )
    auth_rate_limit_window_seconds: int = Field(
        default=60,
        validation_alias=AliasChoices("AUTH_RATE_LIMIT_WINDOW_SECONDS"),
    )
    auth_login_rate_limit: int = Field(
        default=10,
        validation_alias=AliasChoices("AUTH_LOGIN_RATE_LIMIT"),
    )
    auth_password_reset_request_rate_limit: int = Field(
        default=5,
        validation_alias=AliasChoices("AUTH_PASSWORD_RESET_REQUEST_RATE_LIMIT"),
    )
    auth_password_reset_confirm_rate_limit: int = Field(
        default=10,
        validation_alias=AliasChoices("AUTH_PASSWORD_RESET_CONFIRM_RATE_LIMIT"),
    )
    auth_mfa_verify_rate_limit: int = Field(
        default=10,
        validation_alias=AliasChoices("AUTH_MFA_VERIFY_RATE_LIMIT"),
    )
    auth_failure_lockout_threshold: int = Field(
        default=5,
        validation_alias=AliasChoices("AUTH_FAILURE_LOCKOUT_THRESHOLD"),
    )
    auth_failure_lockout_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("AUTH_FAILURE_LOCKOUT_SECONDS"),
    )
    mfa_totp_issuer: str = Field(
        default="Tomb of Light",
        validation_alias=AliasChoices("MFA_TOTP_ISSUER"),
    )
    mfa_challenge_expire_minutes: int = Field(
        default=10,
        validation_alias=AliasChoices("MFA_CHALLENGE_EXPIRE_MINUTES"),
    )
    mfa_backup_code_count: int = Field(
        default=8,
        validation_alias=AliasChoices("MFA_BACKUP_CODE_COUNT"),
    )
    mfa_totp_window: int = Field(
        default=1,
        validation_alias=AliasChoices("MFA_TOTP_WINDOW"),
    )
    link_key_expire_hours: int = Field(
        default=0,
        validation_alias=AliasChoices("LINK_KEY_EXPIRE_HOURS"),
    )
    upload_scan_command: str = Field(
        default="",
        validation_alias=AliasChoices("UPLOAD_SCAN_COMMAND"),
    )
    upload_scan_hook: str = Field(
        default="",
        validation_alias=AliasChoices("UPLOAD_SCAN_HOOK"),
    )
    upload_clamav_host: str = Field(
        default="",
        validation_alias=AliasChoices("UPLOAD_CLAMAV_HOST", "CLAMAV_HOST"),
    )
    upload_clamav_port: int = Field(
        default=3310,
        validation_alias=AliasChoices("UPLOAD_CLAMAV_PORT", "CLAMAV_PORT"),
    )
    upload_clamav_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "UPLOAD_CLAMAV_TIMEOUT_SECONDS",
            "CLAMAV_TIMEOUT_SECONDS",
        ),
    )
    upload_clamav_require_private_network: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "UPLOAD_CLAMAV_REQUIRE_PRIVATE_NETWORK",
            "CLAMAV_REQUIRE_PRIVATE_NETWORK",
        ),
    )
    upload_scan_fail_closed: bool = Field(
        # Files must enter quarantine when malware scanning is unavailable or
        # errors. Production can only accept a file after an explicit clean
        # or configured scanner decision.
        default=True,
        validation_alias=AliasChoices("UPLOAD_SCAN_FAIL_CLOSED"),
    )
    upload_quarantine_dir: str = Field(
        default="storage/quarantine",
        validation_alias=AliasChoices("UPLOAD_QUARANTINE_DIR"),
    )
    upload_allow_admin_quarantine_override: bool = Field(
        default=False,
        validation_alias=AliasChoices("UPLOAD_ALLOW_ADMIN_QUARANTINE_OVERRIDE"),
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
    stripe_nft_lineage_record_price_id: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_NFT_LINEAGE_RECORD_PRICE_ID"),
    )
    stripe_additional_nft_mint_price_id: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_ADDITIONAL_NFT_MINT_PRICE_ID"),
    )
    stripe_nft_metadata_revision_price_id: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_NFT_METADATA_REVISION_PRICE_ID"),
    )
    manual_fulfillment_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices("MANUAL_FULFILLMENT_MODE"),
    )
    password_reset_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"),
    )
    account_activation_token_expire_hours: int = Field(
        default=24,
        validation_alias=AliasChoices("ACCOUNT_ACTIVATION_TOKEN_EXPIRE_HOURS"),
    )
    password_reset_base_url: str = Field(
        default="https://tomboflight.com/account-security.html",
        validation_alias=AliasChoices("PASSWORD_RESET_BASE_URL"),
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
        default="safeMint",
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
    nft_mint_worker_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("NFT_MINT_WORKER_ENABLED"),
    )
    nft_mint_worker_poll_seconds: int = Field(
        default=15,
        ge=2,
        le=300,
        validation_alias=AliasChoices("NFT_MINT_WORKER_POLL_SECONDS"),
    )
    nft_legacy_payment_links_disabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("NFT_LEGACY_PAYMENT_LINKS_DISABLED"),
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

    # Email / Postmark
    postmark_server_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "POSTMARK_SERVER_TOKEN",
            "POSTMARK_API_TOKEN",
            "POSTMARK_TOKEN",
            "POSTMARK_API_KEY",
            "POSTMARK_SERVER_KEY",
            "POSTMARK_SERVER_API_TOKEN",
            "POSTMARK_API_SERVER_TOKEN",
            "POSTMARK_KEY",
        ),
    )
    postmark_server_token_file: str = Field(
        default="",
        validation_alias=AliasChoices(
            "POSTMARK_SERVER_TOKEN_FILE",
            "POSTMARK_API_TOKEN_FILE",
            "POSTMARK_TOKEN_FILE",
        ),
    )
    postmark_from_email: str = Field(
        default="admin@tomboflight.com",
        validation_alias=AliasChoices("POSTMARK_FROM_EMAIL"),
    )
    postmark_from_name: str = Field(
        default="Tomb of Light Security",
        validation_alias=AliasChoices("POSTMARK_FROM_NAME"),
    )
    postmark_message_stream: str = Field(
        default="outbound",
        validation_alias=AliasChoices("POSTMARK_MESSAGE_STREAM"),
    )

    # Private Bridge Event access. Promotion codes are runtime secrets and
    # must never be committed to the repository or returned by an API.
    bridge_paint_promotion_codes_json: str = Field(
        default="",
        validation_alias=AliasChoices("BRIDGE_PAINT_PROMOTION_CODES_JSON"),
    )
    bridge_paint_event_expires_at: str = Field(
        default="2026-08-30T03:59:00+00:00",
        validation_alias=AliasChoices("BRIDGE_PAINT_EVENT_EXPIRES_AT"),
    )
    bridge_paint_access_rate_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        validation_alias=AliasChoices("BRIDGE_PAINT_ACCESS_RATE_LIMIT"),
    )

    allowed_origins: str = Field(
        default=("https://tomboflight.com," "https://www.tomboflight.com"),
        validation_alias=AliasChoices("ALLOWED_ORIGINS"),
    )
    local_dev_cors_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LOCAL_DEV_CORS_ENABLED"),
    )
    local_dev_cors_origins: str = Field(
        default=(
            "http://127.0.0.1:5500,"
            "http://localhost:5500,"
            "http://[::1]:5500,"
            "http://127.0.0.1:8000,"
            "http://localhost:8000,"
            "http://[::1]:8000,"
            "http://127.0.0.1:8081,"
            "http://localhost:8081,"
            "http://[::1]:8081"
        ),
        validation_alias=AliasChoices("LOCAL_DEV_CORS_ORIGINS"),
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

    @staticmethod
    def _parse_origin_list(value: str) -> list[str]:
        parts = str(value or "").replace("\n", ",").replace(";", ",").split(",")
        seen: set[str] = set()
        parsed: list[str] = []
        for raw in parts:
            origin = str(raw).strip().rstrip("/")
            if not origin or origin == "*" or origin in seen:
                continue
            seen.add(origin)
            parsed.append(origin)
        return parsed

    @property
    def is_production_environment(self) -> bool:
        return str(self.environment or "").strip().lower() in {"production", "prod"}

    @property
    def is_local_environment(self) -> bool:
        return str(self.environment or "").strip().lower() in LOCAL_ENVIRONMENTS

    @property
    def admin_identity_registry_json_value(self) -> str:
        value = self.admin_identity_registry_json
        if isinstance(value, SecretStr):
            return value.get_secret_value().strip()
        return str(value or "").strip()

    @property
    def account_separation_audit_targets_json_value(self) -> str:
        value = self.account_separation_audit_targets_json
        if isinstance(value, SecretStr):
            return value.get_secret_value().strip()
        return str(value or "").strip()

    @property
    def local_dev_cors_enabled_effective(self) -> bool:
        # Staging and any other explicitly deployed environment must not
        # inherit browser origins intended only for a developer workstation.
        return self.is_local_environment and (
            self.local_dev_cors_enabled or self.environment.strip().lower() != "test"
        )

    @property
    def allowed_origins_list(self) -> list[str]:
        configured = self._parse_origin_list(self.allowed_origins)
        if self.local_dev_cors_enabled_effective:
            configured.extend(self._parse_origin_list(self.local_dev_cors_origins))

        deduped: list[str] = []
        seen: set[str] = set()
        for origin in configured:
            if origin in seen:
                continue
            seen.add(origin)
            deduped.append(origin)
        return deduped

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
    def upload_quarantine_root_path(self) -> str:
        mount_path = str(self.render_disk_mount_path or "").strip().rstrip("/")
        if mount_path:
            return str(Path(mount_path) / "quarantine")
        return str(Path(self.upload_quarantine_dir))

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


def validate_runtime_environment_on_startup(
    *,
    runtime_settings: Settings | None = None,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Reject ambiguous or development-grade configuration on hosted runtimes.

    Local development remains zero-configuration. Hosted processes must set an
    explicit environment and may never identify themselves as local/dev/test;
    otherwise production-only controls could silently be bypassed.
    """

    configured = runtime_settings or settings
    runtime_environ = environ if environ is not None else os.environ
    normalized_environ = {
        str(key).upper(): str(value or "").strip()
        for key, value in runtime_environ.items()
    }
    normalized_environment = str(configured.environment or "").strip().lower()
    if normalized_environment not in KNOWN_ENVIRONMENTS:
        raise RuntimeError(
            "ENVIRONMENT must be one of development, test, staging, or production."
        )

    hosted = any(
        normalized_environ.get(key, "")
        for key in HOSTED_RUNTIME_ENV_VARS
    )
    explicitly_configured = bool(normalized_environ.get("ENVIRONMENT"))
    if hosted and not explicitly_configured:
        raise RuntimeError("ENVIRONMENT must be explicitly configured on hosted runtimes.")
    if hosted and normalized_environment in LOCAL_ENVIRONMENTS:
        raise RuntimeError(
            "Hosted runtimes cannot use development, local, or test ENVIRONMENT values."
        )

    if normalized_environment in DEPLOYED_ENVIRONMENTS:
        secret_key = str(configured.secret_key or "").strip()
        if secret_key.lower() in {
            "",
            "change-me",
            "changeme",
            "replace-me",
            "secret",
        }:
            raise RuntimeError(
                "SECRET_KEY must be set to a unique value in deployed environments."
            )
        if len(secret_key.encode("utf-8")) < 32:
            raise RuntimeError(
                "SECRET_KEY must contain at least 32 bytes in deployed environments."
            )
        registry_value = getattr(configured, "admin_identity_registry_json_value", "")
        if callable(registry_value):
            registry_value = registry_value()
        if not registry_value:
            raw_registry = getattr(configured, "admin_identity_registry_json", "")
            if isinstance(raw_registry, SecretStr):
                registry_value = raw_registry.get_secret_value().strip()
            else:
                registry_value = str(raw_registry or "").strip()
        if not registry_value:
            raise RuntimeError(
                "ADMIN_IDENTITY_REGISTRY_JSON must be set in deployed environments."
            )
