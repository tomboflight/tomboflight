from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import (
    DatabaseUnavailableError,
    close_mongo_connection,
    connect_to_mongo,
    get_service_state,
)

from app.routes.admin_intake_submissions import (
    router as admin_intake_submissions_router,
)
from app.routes.admin_continuity_preview import router as admin_continuity_preview_router
from app.routes.asset_delivery import router as asset_delivery_router
from app.routes.admin_control_center import router as admin_control_center_router
from app.routes.admin_maintenance import router as admin_maintenance_router
from app.routes.audit_logs import router as audit_logs_router
from app.routes.auth import router as auth_router
from app.routes.billing import router as billing_router
from app.routes.canonical_persons import router as canonical_persons_router
from app.routes.certificate_versions import router as certificate_versions_router
from app.routes.consistency import router as consistency_router
from app.routes.db_bootstrap import router as db_bootstrap_router
from app.routes.families import router as families_router
from app.routes.family_graph import router as family_graph_router
from app.routes.family_members import router as family_members_router
from app.routes.family_networks import router as family_networks_router
from app.routes.graph_integrity import router as graph_integrity_router
from app.routes.health import router as health_router
from app.routes.household_links import router as household_links_router
from app.routes.households import router as households_router
from app.routes.identity_anchor import router as identity_anchor_router
from app.routes.experience import router as experience_router
from app.routes.identity_links import router as identity_links_router
from app.routes.intake import router as intake_router
from app.routes.intake_options import router as intake_options_router
from app.routes.intake_submissions import router as intake_submissions_router
from app.routes.issued_certificates import router as issued_certificates_router
from app.routes.lineage_certificate import router as lineage_certificate_router
from app.routes.lineage_graph import router as lineage_graph_router
from app.routes.lineage_nodes import router as lineage_nodes_router
from app.routes.lineage_proof import router as lineage_proof_router
from app.routes.lineage_query import router as lineage_query_router
from app.routes.legacy_messages import router as legacy_messages_router
from app.routes.link_keys import router as link_keys_router
from app.routes.link_requests import router as link_requests_router
from app.routes.linked_network import router as linked_network_router
from app.routes.vault import router as vault_router
from app.routes.match_candidates import router as match_candidates_router
from app.routes.match_generation import router as match_generation_router
from app.routes.mint_jobs import (
    initialize_mint_job_indexes,
    router as mint_jobs_router,
)
from app.routes.mint_policy import router as mint_policy_router
from app.routes.mint_fees import router as mint_fees_router
from app.routes.mint_records import (
    initialize_mint_record_indexes,
    router as mint_records_router,
)
from app.routes.narrative_records import router as narrative_records_router
from app.routes.orders import (
    initialize_order_indexes,
    router as orders_router,
)
from app.routes.organizations import router as organizations_router
from app.services.project_entitlement_service import ensure_project_entitlement_indexes
from app.services.admin_access_bootstrap_service import bootstrap_admin_access_controls
from app.services.admin_control_service import ensure_finance_event_indexes
from app.services.organization_service import ensure_organization_indexes
from app.routes.package_catalog import router as package_catalog_router
from app.routes.package_catalog_public import router as package_catalog_public_router
from app.routes.presence import router as presence_router
from app.routes.projects import router as projects_router
from app.routes.project_entitlements import router as project_entitlements_router
from app.routes.project_workflow import router as project_workflow_router
from app.routes.client_review import router as client_review_router
from app.routes.relationships import router as relationships_router
from app.routes.stripe_webhooks import (
    ensure_stripe_event_indexes,
    router as stripe_webhooks_router,
)
from app.routes.tree import router as tree_router
from app.routes.uploads import router as uploads_router
from app.routes.users import router as users_router
from app.routes.verification_records import router as verification_records_router
from app.routes.viewer_manifest import router as viewer_manifest_router
from app.routes.workspace_access import (
    legacy_router as workspace_access_legacy_router,
    router as workspace_access_router,
)
from app.services.nft_runtime_validation_service import (
    validate_nft_runtime_configuration_on_startup,
)


logger = logging.getLogger(__name__)


def _resolve_allowed_origins() -> list[str]:
    configured = getattr(settings, "allowed_origins_list", []) or []

    cleaned: list[str] = []
    for origin in configured:
        value = str(origin).strip().rstrip("/")
        if not value or value == "*":
            continue
        cleaned.append(value)

    if cleaned:
        return list(dict.fromkeys(cleaned))

    defaults = [
        "https://tomboflight.com",
        "https://www.tomboflight.com",
    ]
    if getattr(settings, "local_dev_cors_enabled_effective", False):
        defaults.extend(
            [
                "http://127.0.0.1:5500",
                "http://localhost:5500",
                "http://[::1]:5500",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
                "http://[::1]:8000",
                "http://127.0.0.1:8081",
                "http://localhost:8081",
                "http://[::1]:8081",
            ]
        )
    return defaults


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.lower() == "https":
        return True
    return request.url.scheme == "https"


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_nft_runtime_configuration_on_startup()
    db = connect_to_mongo()
    app.state.db = db
    if db is not None:
        initialize_order_indexes()
        ensure_project_entitlement_indexes()
        initialize_mint_record_indexes()
        initialize_mint_job_indexes()
        ensure_stripe_event_indexes()
        ensure_finance_event_indexes()
        ensure_organization_indexes()
        try:
            bootstrap_admin_access_controls()
        except Exception as exc:
            logger.warning("Admin access bootstrap sync skipped: %s", exc)
        logger.info("Connected to MongoDB database.")
    else:
        logger.warning("MongoDB unavailable at startup; running in degraded mode.")
    yield
    close_mongo_connection()
    logger.info("MongoDB connection closed.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    response.headers["Cache-Control"] = "no-store"

    if _is_secure_request(request):
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    return response


@app.exception_handler(DatabaseUnavailableError)
async def handle_database_unavailable(_: Request, exc: DatabaseUnavailableError):
    service_state = get_service_state()
    payload = {
        "error": {
            "code": "database_unavailable",
            "message": str(exc) or "Database is currently unavailable.",
            "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
        },
        **service_state,
    }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )


# ----------------------------
# Core Routes
# ----------------------------
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(intake_router)
app.include_router(intake_options_router)
app.include_router(intake_submissions_router)
app.include_router(admin_intake_submissions_router)
app.include_router(admin_continuity_preview_router)
app.include_router(admin_control_center_router)
app.include_router(projects_router)
app.include_router(project_entitlements_router)
app.include_router(project_workflow_router)
app.include_router(client_review_router)
app.include_router(experience_router)
app.include_router(presence_router)
app.include_router(families_router)
app.include_router(family_graph_router)
app.include_router(users_router)
app.include_router(family_members_router)
app.include_router(lineage_nodes_router)
app.include_router(tree_router)
app.include_router(family_networks_router)
app.include_router(households_router)
app.include_router(household_links_router)
app.include_router(relationships_router)
app.include_router(db_bootstrap_router)
app.include_router(admin_maintenance_router)
app.include_router(graph_integrity_router)
app.include_router(orders_router)
app.include_router(organizations_router)
app.include_router(package_catalog_router)
app.include_router(package_catalog_public_router)
app.include_router(uploads_router)
app.include_router(workspace_access_router)
app.include_router(workspace_access_legacy_router)
app.include_router(viewer_manifest_router)
app.include_router(mint_policy_router)
app.include_router(mint_fees_router)
app.include_router(mint_records_router)
app.include_router(mint_jobs_router)
app.include_router(asset_delivery_router)

# Stripe Webhooks
app.include_router(stripe_webhooks_router)

# ----------------------------
# Identity System
# ----------------------------
app.include_router(canonical_persons_router)
app.include_router(match_candidates_router)
app.include_router(identity_links_router)
app.include_router(match_generation_router)
app.include_router(identity_anchor_router)

# ----------------------------
# Records
# ----------------------------
app.include_router(verification_records_router)
app.include_router(narrative_records_router)

# ----------------------------
# Linking + Requests
# ----------------------------
app.include_router(link_keys_router)
app.include_router(link_requests_router)
app.include_router(linked_network_router)
app.include_router(vault_router)
app.include_router(legacy_messages_router)

# ----------------------------
# Intelligence
# ----------------------------
app.include_router(consistency_router)
app.include_router(lineage_graph_router)
app.include_router(lineage_proof_router)
app.include_router(lineage_certificate_router)
app.include_router(issued_certificates_router)
app.include_router(certificate_versions_router)
app.include_router(lineage_query_router)

# ----------------------------
# Audit
# ----------------------------
app.include_router(audit_logs_router)


@app.get("/")
def root():
    service_state = get_service_state()
    status_label = "ok" if service_state["ready"] else service_state["service_mode"]
    environment = str(settings.environment or "development").strip().lower()
    is_production = environment in {"production", "prod"}
    if is_production:
        return {
            "message": "Tomb of Light backend is running.",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": status_label,
            **service_state,
        }
    return {
        "message": "Tomb of Light backend is running.",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": status_label,
        **service_state,
        "allowed_origins": _resolve_allowed_origins(),
        "routes": [
            "/health",
            "/health/live",
            "/health/ready",
            "/auth/signup",
            "/auth/login",
            "/auth/logout",
            "/auth/me",
            "/auth/password-reset/request",
            "/auth/password-reset/confirm",
            "/auth/password-change",
            "/intake",
            "/intake-submissions",
            "/intake-submissions/my-latest",
            "/intake-submissions/my-list?limit=10",
            "/uploads/member-photo",
            "/uploads/verification-evidence",
            "/uploads/private-media",
            "/uploads/member/{member_id}",
            "/uploads/family/{family_id}",
            "/uploads/{upload_id}/download",
            "/workspace-access/my-memberships",
            "/workspace-access/project/{project_id}/members",
            "/workspace-access/project/{project_id}/invites",
            "/workspace-access/invites/accept",
            "/workspace-access/invites/{invite_id}/resend",
            "/viewer/manifest",
            "/mint-policy/packages",
            "/projects/{project_id}/experience-lane",
            "/experience/chamber/{project_id}",
            "/experience/session",
            "/lineage-chamber/{family_id}/summary",
            "/experience-story/family/{family_id}",
            "/presence/status",
            "/projects/{project_id}/mint-eligibility",
            "/projects/{project_id}/mint-records/prepare",
            "/projects/{project_id}/mint-records",
            "/projects/{project_id}/mint-status",
            "/admin/mint-records/maintenance/backfill",
            "/admin/maintenance/drop-legacy-indexes",
            "/admin/maintenance/backfill-project-members",
            "/admin/maintenance/backfill-workspace-anchors",
            "/mint-jobs/run-next",
            "/tokens/{public_token_id}",
            "/link-keys/my-list",
            "/link-keys/my-active?project_id={project_id}",
            "/link-keys/project/{project_id}/generate",
            "/link-keys/{key_id}/revoke",
            "/link-requests",
            "/link-requests/my-list",
            "/link-requests/{request_id}/approve",
            "/link-requests/{request_id}/reject",
            "/link-requests/{request_id}/revoke",
            "/webhooks/stripe",
            "/orders/record-checkout",
            "/orders/my-orders",
            "/orders/health",
            "/billing/config",
            "/billing/overview",
            "/billing/setup-intent",
            "/billing/payment-methods/{payment_method_id}/default",
            "/billing/payment-methods/{payment_method_id}",
            "/billing/portal-session",
            "/audit-logs",
            "/docs",
        ],
    }
