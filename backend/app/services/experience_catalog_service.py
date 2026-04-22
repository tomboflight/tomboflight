from __future__ import annotations

from typing import Any

LANE_CHAMBERS: dict[str, list[str]] = {
    "portrait": [
        "entry_chamber",
        "portrait_chamber",
        "archive_chamber",
        "verification_chamber",
        "narrative_chamber",
    ],
    "household": [
        "entry_chamber",
        "household_chamber",
        "lineage_chamber",
        "archive_chamber",
        "verification_chamber",
        "narrative_chamber",
        "certificate_chamber",
    ],
    "network": [
        "entry_chamber",
        "network_chamber",
        "lineage_chamber",
        "archive_chamber",
        "verification_chamber",
        "narrative_chamber",
        "certificate_chamber",
    ],
    "organization": [
        "entry_chamber",
        "admin_workspace",
        "lineage_chamber",
        "archive_chamber",
        "verification_chamber",
        "narrative_chamber",
        "certificate_chamber",
    ],
}

CHAMBER_LABELS: dict[str, str] = {
    "entry_chamber": "Entry Chamber",
    "portrait_chamber": "Portrait Chamber",
    "household_chamber": "Household Chamber",
    "lineage_chamber": "Lineage Chamber",
    "archive_chamber": "Archive Chamber",
    "verification_chamber": "Verification Chamber",
    "narrative_chamber": "Narrative Chamber",
    "certificate_chamber": "Certificate Chamber",
    "network_chamber": "Network Chamber",
    "admin_workspace": "Admin Workspace",
}

MODULE_LABELS: dict[str, str] = {
    "portrait_chamber": "Portrait memory presence",
    "household_chamber": "Household structure view",
    "lineage_chamber": "Lineage graph intelligence",
    "archive_chamber": "Archive and vault access",
    "verification_chamber": "Verification trust state",
    "narrative_chamber": "Narrative sequencing",
    "certificate_chamber": "Certificate readiness",
    "network_chamber": "Network branch navigation",
    "admin_workspace": "Internal operations workspace",
}


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_lane(value: Any) -> str:
    lane = _normalize(value)
    return lane if lane in LANE_CHAMBERS else "portrait"


def chamber_label(chamber: str) -> str:
    return CHAMBER_LABELS.get(chamber, chamber.replace("_", " ").title())


def derive_experience_mode(package_lane: str) -> str:
    lane = normalize_lane(package_lane)
    return {
        "portrait": "portrait",
        "household": "household",
        "network": "network",
        "organization": "organization",
    }.get(lane, "portrait")


def get_lane_chambers(package_lane: str) -> list[str]:
    return list(LANE_CHAMBERS.get(normalize_lane(package_lane), LANE_CHAMBERS["portrait"]))


def derive_allowed_modules(package_lane: str, resolved_entitlements: dict[str, Any]) -> list[str]:
    lane = normalize_lane(package_lane)
    entitlements = resolved_entitlements or {}
    has_org_lineage = lane == "organization" and bool(
        entitlements.get("structured_organization_lineage")
        or entitlements.get("can_build_org_chart")
    )

    modules = ["entry_chamber"]
    if lane == "portrait" or bool(entitlements.get("can_upload_portraits")):
        modules.append("portrait_chamber")
    if lane == "household" or bool(entitlements.get("can_build_household")):
        modules.append("household_chamber")
    if lane == "network" or bool(entitlements.get("can_link_households")):
        modules.append("network_chamber")
    if lane == "organization":
        modules.append("admin_workspace")
    if bool(entitlements.get("can_build_family_tree")) or has_org_lineage:
        modules.append("lineage_chamber")
    if bool(
        entitlements.get("can_upload_portraits")
        or entitlements.get("can_upload_verification_docs")
    ):
        modules.append("archive_chamber")
    if bool(entitlements.get("can_upload_verification_docs")):
        modules.append("verification_chamber")
    if bool(entitlements.get("can_use_narration")):
        modules.append("narrative_chamber")
    if bool(entitlements.get("can_use_lineage_certificate")):
        modules.append("certificate_chamber")

    return list(dict.fromkeys(modules))


def build_module_unlocks(
    package_lane: str,
    resolved_entitlements: dict[str, Any],
    *,
    is_admin: bool = False,
) -> list[dict[str, Any]]:
    lane = normalize_lane(package_lane)
    entitlements = resolved_entitlements or {}
    allowed_modules = set(derive_allowed_modules(lane, entitlements))

    unlocks: list[dict[str, Any]] = []
    for chamber in get_lane_chambers(lane):
        unlocked = is_admin or chamber in allowed_modules
        if chamber == "entry_chamber":
            unlocked = True

        reason = MODULE_LABELS.get(chamber, chamber_label(chamber))
        if not unlocked:
            reason = f"Locked until {MODULE_LABELS.get(chamber, chamber_label(chamber)).lower()} is included in the active lane."

        unlocks.append(
            {
                "module_key": chamber,
                "unlocked": unlocked,
                "reason": reason,
            }
        )

    return unlocks
