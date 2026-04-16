from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.package_catalog import get_package
from app.database import get_database
from app.schemas.project import ProjectCreate
from app.services.entitlement_service import can_upgrade
from app.services.project_entitlement_service import (
    get_project_entitlement,
    upsert_project_entitlement,
)


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

    identity_filters: list[dict[str, Any]] = []
    if owner_user_id:
        identity_filters.append({"owner_user_id": owner_user_id})
    if owner_email:
        identity_filters.append({"owner_email": owner_email})

    if not identity_filters:
        return []

    projects_by_id: dict[str, dict[str, Any]] = {}

    for project in db.projects.find({"$or": identity_filters}).sort("created_at", -1):
        projects_by_id[str(project.get("_id"))] = project

    family_filters: list[dict[str, Any]] = []
    if owner_user_id:
        family_filters.append({"shared_with_user_ids": owner_user_id})
    if owner_email:
        family_filters.append({"shared_with_emails": owner_email})

    if family_filters:
        shared_family_ids: set[str] = set()
        shared_project_ids: set[str] = set()

        for family in db.families.find({"$or": family_filters}, {"_id": 1, "project_id": 1}):
            family_id = _normalize(family.get("_id"))
            if family_id:
                shared_family_ids.add(family_id)

            project_id = _normalize(family.get("project_id"))
            if project_id:
                shared_project_ids.add(project_id)

        if shared_project_ids:
            project_id_values: list[Any] = []
            for project_id in shared_project_ids:
                project_id_values.append(project_id)
                if ObjectId.is_valid(project_id):
                    project_id_values.append(ObjectId(project_id))

            for project in db.projects.find({"_id": {"$in": project_id_values}}):
                projects_by_id[str(project.get("_id"))] = project

        if shared_family_ids:
            for project in db.projects.find({"family_id": {"$in": list(shared_family_ids)}}):
                projects_by_id[str(project.get("_id"))] = project

    return sorted(
        list(projects_by_id.values()),
        key=lambda item: _normalize(
            item.get("updated_at") or item.get("created_at"),
        ),
        reverse=True,
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

    if user_id and owner_user_id and owner_user_id != user_id:
        return None
    if user_email and owner_email and owner_email != user_email:
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
        "project_lane": str(package.get("package_lane") or project.get("project_lane") or "").strip().lower() or project.get("project_lane"),
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
