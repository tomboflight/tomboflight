from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo, get_database

from app.routes.admin_intake_submissions import (
    router as admin_intake_submissions_router,
)
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
from app.routes.identity_links import router as identity_links_router
from app.routes.intake import router as intake_router
from app.routes.intake_submissions import router as intake_submissions_router
from app.routes.issued_certificates import router as issued_certificates_router
from app.routes.lineage_certificate import router as lineage_certificate_router
from app.routes.lineage_graph import router as lineage_graph_router
from app.routes.lineage_nodes import router as lineage_nodes_router
from app.routes.lineage_proof import router as lineage_proof_router
from app.routes.lineage_query import router as lineage_query_router
from app.routes.link_keys import router as link_keys_router
from app.routes.link_requests import router as link_requests_router
from app.routes.match_candidates import router as match_candidates_router
from app.routes.match_generation import router as match_generation_router
from app.routes.mint_jobs import router as mint_jobs_router
from app.routes.mint_policy import router as mint_policy_router
from app.routes.mint_records import router as mint_records_router
from app.routes.narrative_records import router as narrative_records_router
from app.routes.orders import router as orders_router
from app.routes.package_catalog import router as package_catalog_router
from app.routes.projects import router as projects_router
from app.routes.project_entitlements import router as project_entitlements_router
from app.routes.relationships import router as relationships_router
from app.routes.stripe_webhooks import router as stripe_webhooks_router
from app.routes.tree import router as tree_router
from app.routes.uploads import router as uploads_router
from app.routes.users import router as users_router
from app.routes.verification_records import router as verification_records_router
from app.routes.viewer_manifest import router as viewer_manifest_router
from app.services.nft_runtime_validation_service import (
    validate_nft_runtime_configuration_on_startup,
)


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

    return [
        "https://tomboflight.com",
        "https://www.tomboflight.com",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ]


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.lower() == "https":
        return True
    return request.url.scheme == "https"


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_nft_runtime_configuration_on_startup()
    connect_to_mongo()
    app.state.db = get_database()
    print("Connected to MongoDB database.")
    yield
    close_mongo_connection()
    print("MongoDB connection closed.")


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


# ----------------------------
# Core Routes
# ----------------------------
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(intake_router)
app.include_router(intake_submissions_router)
app.include_router(admin_intake_submissions_router)
app.include_router(projects_router)
app.include_router(project_entitlements_router)
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
app.include_router(graph_integrity_router)
app.include_router(orders_router)
app.include_router(package_catalog_router)
app.include_router(uploads_router)
app.include_router(viewer_manifest_router)
app.include_router(mint_policy_router)
app.include_router(mint_records_router)
app.include_router(mint_jobs_router)

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
    return {
        "message": "Tomb of Light backend is running.",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "allowed_origins": _resolve_allowed_origins(),
        "routes": [
            "/health",
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
            "/uploads/member/{member_id}",
            "/uploads/family/{family_id}",
            "/uploads/{upload_id}/download",
            "/viewer/manifest",
            "/mint-policy/packages",
            "/projects/{project_id}/mint-eligibility",
            "/projects/{project_id}/mint-records/prepare",
            "/projects/{project_id}/mint-records",
            "/projects/{project_id}/mint-status",
            "/admin/mint-records/maintenance/backfill",
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
