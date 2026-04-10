from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.package_catalog import get_package, normalize_package_code
from app.core.package_type_catalog import normalize_package_type
from app.database import get_database
from app.schemas.project import ProjectCreate
from app.services.entitlement_service import can_upgrade
from app.services.project_membership_service import (
    ensure_project_owner_membership,
    get_project_access_snapshot,
    list_accessible_project_ids,
)
from app.services.project_entitlement_service import (
    get_project_entitlement,
    upsert_project_entitlement,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: str | None) -> str:
    return str(value or "").strip()


def _sort_projects(project_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    def _sort_key(item: dict[str, Any]) -> datetime:
        value = item.get("updated_at") or item.get("created_at")
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.min.replace(tzinfo=UTC)

    return sorted(
        project_map.values(),
        key=_sort_key,
        reverse=True,
    )


def _find_project_by_identifier(db, project_id: str) -> dict[str, Any] | None:
    if not project_id:
        return None
    if ObjectId.is_valid(project_id):
        project = db.projects.find_one({"_id": ObjectId(project_id)})
        if project is not None:
            return project
    return db.projects.find_one({"id": project_id})


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

    project_map: dict[str, dict[str, Any]] = {}
    for project_id in list_accessible_project_ids(
        user_id=owner_user_id,
        email=owner_email,
    ):
        project = _find_project_by_identifier(db, project_id)
        if project is not None:
            project_map[str(project.get("_id") or project.get("id"))] = project

    filters: list[dict[str, Any]] = []
    if owner_user_id:
        filters.append({"owner_user_id": owner_user_id})
    if owner_email:
        filters.append({"owner_email": owner_email})

    if filters:
        for project in db.projects.find({"$or": filters}).sort("created_at", -1):
            project_map[str(project.get("_id") or project.get("id"))] = project

    return _sort_projects(project_map)


def create_project(payload: ProjectCreate) -> dict[str, Any]:
    db = get_database()
    data = payload.model_dump()

    now = _now()
    data["created_at"] = now
    data["updated_at"] = now
    data["project_name"] = data["name"]
    data["package_code"] = normalize_package_code(data["package_code"])
    data["project_lane"] = normalize_package_type(data["project_lane"], default="portrait")
    data["package_slug"] = data["package_code"]
    data["package_type"] = data["package_code"]

    if db is None:
        data["_id"] = "local-project-preview"
        return data

    result = db.projects.insert_one(data)
    data["_id"] = result.inserted_id
    ensure_project_owner_membership(data)
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

    package_code = normalize_package_code(package_code)
    package = get_package(package_code)
    if not package:
        return None

    package_lane = normalize_package_type(package.get("package_lane"))
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
    ensure_project_owner_membership(project_doc)

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


def apply_package_purchase_to_project(
    *,
    user: dict[str, Any],
    project_id: str,
    package_code: str,
    package_name: str,
    stripe_session_id: str | None = None,
    stripe_payment_link_id: str | None = None,
) -> dict[str, Any] | None:
    db = get_database()
    if db is None:
        return None

    if not ObjectId.is_valid(project_id):
        return None

    package_code = normalize_package_code(package_code)
    package = get_package(package_code)
    if not package:
        return None

    project = db.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        return None

    user_id = str(user.get("_id") or user.get("id") or user.get("user_id") or "").strip()
    owner_user_id = str(project.get("owner_user_id") or "").strip()
    owner_email = str(project.get("owner_email") or "").strip().lower()
    user_email = str(user.get("email") or "").strip().lower()
    access_snapshot = get_project_access_snapshot(
        project,
        user_id=user_id,
        email=user_email,
    )

    if not access_snapshot.get("accessible"):
        return None

    current_entitlement = get_project_entitlement(project_id) or {}
    current_package_code = str(
        current_entitlement.get("package_code")
        or project.get("package_code")
        or project.get("package_slug")
        or project.get("package_type")
        or ""
    ).strip()
    if (
        current_package_code
        and current_package_code != package_code
        and not can_upgrade(current_package_code, package_code)
    ):
        return None

    now = _now()
    updated_fields: dict[str, Any] = {
        "project_lane": normalize_package_type(
            package.get("package_lane") or project.get("project_lane"),
            default=_normalize(project.get("project_lane")) or "portrait",
        ),
        "package_code": package_code,
        "package_slug": package_code,
        "package_type": package_code,
        "package_name": package_name,
        "item_type": "package",
        "billing_plan": "one_time",
        "status": project.get("status") or "purchased",
        "phase": project.get("phase") or "checkout_completed",
        "source": project.get("source") or "stripe_webhook",
        "updated_at": now,
    }

    if stripe_session_id:
        updated_fields["stripe_session_id"] = stripe_session_id
    if stripe_payment_link_id:
        updated_fields["stripe_payment_link_id"] = stripe_payment_link_id

    db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": updated_fields},
    )

    refreshed = db.projects.find_one({"_id": ObjectId(project_id)}) or project
    ensure_project_owner_membership(refreshed)

    existing_addons = list(current_entitlement.get("active_addons") or [])
    maintenance_plan = str(current_entitlement.get("maintenance_plan") or "not_started")
    delivered_at = current_entitlement.get("delivered_at")

    try:
        upsert_project_entitlement(
            project_id=project_id,
            user_id=owner_user_id or user_id,
            package_code=package_code,
            active_addons=existing_addons,
            maintenance_plan=maintenance_plan,
            delivered_at=delivered_at,
            status="active",
        )
    except Exception:
        pass

    return refreshed
