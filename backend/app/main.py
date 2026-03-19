from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo, get_database

from app.routes.audit_logs import router as audit_logs_router
from app.routes.auth import router as auth_router
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
from app.routes.link_requests import router as link_requests_router
from app.routes.match_candidates import router as match_candidates_router
from app.routes.match_generation import router as match_generation_router
from app.routes.narrative_records import router as narrative_records_router
from app.routes.orders import router as orders_router
from app.routes.projects import router as projects_router
from app.routes.relationships import router as relationships_router
from app.routes.tree import router as tree_router
from app.routes.users import router as users_router
from app.routes.verification_records import router as verification_records_router

# Stripe Webhooks
from app.routes.stripe_webhooks import router as stripe_webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Core Routes
# ----------------------------
app.include_router(health_router)
app.include_router(auth_router)

app.include_router(intake_router)
app.include_router(intake_submissions_router)

app.include_router(projects_router)
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

# Orders
app.include_router(orders_router)

# Stripe Webhooks (public endpoint Stripe calls)
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
        "key_routes": [
            "/health",
            "/auth/signup",
            "/auth/login",
            "/auth/me",
            "/orders/my-orders",
            "/orders/record-checkout",
            "/intake-submissions",
            "/intake-submissions/my-latest",
            "/intake-submissions/my-list?limit=10",
            "/webhooks/stripe",
            "/docs",
        ],
    }