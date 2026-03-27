from datetime import UTC, datetime
from typing import Any

from app.core.package_catalog import get_package
from app.database import get_database
from app.schemas.project import ProjectCreate
from app.services.project_entitlement_service import upsert_project_entitlement


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: str | None) -> str:
    return str(value or "").strip()


def list_projects(
    *,
    owner_user_id: str | None = None,
    owner_email: str | None = None,
    is_admin: bool = False,
) -> list[dict[str, Any]]:
    db = get_database()
    if db is None:
        return []

    if is_admin:
        return list(db.projects.find().sort("created_at", -1))

    owner_user_id = _normalize(owner_user_id)
    owner_email = _normalize(owner_email).lower()

    filters: list[dict[str, Any]] = []
    if owner_user_id:
        filters.append({"owner_user_id": owner_user_id})
    if owner_email:
        filters.append({"owner_email": owner_email})

    if not filters:
        return []

    return list(
        db.projects.find({"$or": filters}).sort("created_at", -1)
    )


def create_project(payload: ProjectCreate) -> dict[str, Any]:
    db = get_database()
    data = payload.model_dump()

    now = _now()
    data["created_at"] = now
    data["updated_at"] = now
    data["project_name"] = data["name"]
    data["package_slug"] = data["package_code"]
    data["package_type"] = data["package_code"]

    if db is None:
        data["_id"] = "local-project-preview"
        return data

    result = db.projects.insert_one(data)
    data["_id"] = result.inserted_id
    return data


def create_project_from_paid_order(
    *,
    user: dict[str, Any],
    package_code: str,
    package_name: str,
    stripe_session_id: str | None = None,
    stripe_payment_link_id: str | None = None,
) -> dict[str, Any] | None:
    db = get_database()
    if db is None:
        return None

    package = get_package(package_code)
    if not package:
        return None

    package_lane = str(package.get("package_lane") or "").strip().lower()
    if package_lane not in {"portrait", "household", "network", "organization"}:
        return None

    existing = None
    if stripe_session_id:
        existing = db.projects.find_one({"stripe_session_id": stripe_session_id})
    if existing:
        return existing

    user_id = str(user.get("_id") or user.get("id") or user.get("user_id") or "").strip()
    owner_email = str(user.get("email") or "").strip().lower()
    owner_name = str(user.get("full_name") or user.get("name") or owner_email or "Project Owner").strip()

    project_name = f"{package_name} - {owner_name}"
    now = _now()

    project_doc: dict[str, Any] = {
        "name": project_name,
        "project_name": project_name,
        "project_lane": package_lane,
        "owner_user_id": user_id,
        "owner_email": owner_email,
        "package_code": package_code,
        "package_slug": package_code,
        "package_type": package_code,
        "package_name": package_name,
        "item_type": "package",
        "billing_plan": "one_time",
        "status": "purchased",
        "phase": "checkout_completed",
        "source": "stripe_webhook",
        "family_id": None,
        "household_id": None,
        "organization_id": None,
        "intake_submission_id": None,
        "stripe_session_id": stripe_session_id,
        "stripe_payment_link_id": stripe_payment_link_id,
        "notes": "",
        "created_at": now,
        "updated_at": now,
    }

    result = db.projects.insert_one(project_doc)
    project_doc["_id"] = result.inserted_id

    try:
        upsert_project_entitlement(
            project_id=str(project_doc["_id"]),
            user_id=user_id,
            package_code=package_code,
            active_addons=[],
            maintenance_plan="not_started",
            delivered_at=None,
            status="active",
        )
    except Exception:
        pass

    return project_doc