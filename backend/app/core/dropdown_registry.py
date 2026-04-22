from __future__ import annotations

from copy import deepcopy
from typing import Any

ORGANIZATION_TYPE_OPTIONS: list[str] = [
    "military_unit",
    "police_department",
    "fire_department",
    "emergency_services",
    "government_agency",
    "elected_office",
    "legislative_body",
    "political_campaign",
    "court_or_judicial_office",
    "masonic_lodge",
    "fraternal_order",
    "church_or_ministry",
    "nonprofit",
    "corporation",
    "small_business",
    "school_or_university",
    "hospital_or_healthcare_system",
    "union_or_labor_organization",
    "tribal_government",
    "civic_association",
    "sports_team_or_league",
    "foundation",
    "custom",
]

ORGANIZATION_TYPE_LABELS: dict[str, str] = {
    "military_unit": "Military Unit",
    "police_department": "Police Department",
    "fire_department": "Fire Department",
    "emergency_services": "Emergency Services",
    "government_agency": "Government Agency",
    "elected_office": "Elected Office",
    "legislative_body": "Legislative Body",
    "political_campaign": "Political Campaign",
    "court_or_judicial_office": "Court or Judicial Office",
    "masonic_lodge": "Masonic Lodge",
    "fraternal_order": "Fraternal Order",
    "church_or_ministry": "Church or Ministry",
    "nonprofit": "Nonprofit",
    "corporation": "Corporation",
    "small_business": "Small Business",
    "school_or_university": "School or University",
    "hospital_or_healthcare_system": "Hospital or Healthcare System",
    "union_or_labor_organization": "Union or Labor Organization",
    "tribal_government": "Tribal Government",
    "civic_association": "Civic Association",
    "sports_team_or_league": "Sports Team or League",
    "foundation": "Foundation",
    "custom": "Custom",
}

ORGANIZATION_SUBTYPE_OPTIONS: dict[str, list[dict[str, str]]] = {
    "police_department": [
        {"key": "municipal_police", "label": "Municipal Police"},
        {"key": "county_sheriff_office", "label": "County Sheriff Office"},
        {"key": "state_police", "label": "State Police"},
        {"key": "campus_police", "label": "Campus Police"},
    ],
    "fire_department": [
        {"key": "municipal_fire_department", "label": "Municipal Fire Department"},
        {"key": "county_fire_service", "label": "County Fire Service"},
        {"key": "wildland_fire_service", "label": "Wildland Fire Service"},
        {"key": "airport_fire_rescue", "label": "Airport Fire Rescue"},
    ],
    "elected_office": [
        {"key": "federal_office", "label": "Federal Office"},
        {"key": "state_office", "label": "State Office"},
        {"key": "county_office", "label": "County Office"},
        {"key": "municipal_office", "label": "Municipal Office"},
    ],
    "political_campaign": [
        {"key": "federal_campaign", "label": "Federal Campaign"},
        {"key": "state_campaign", "label": "State Campaign"},
        {"key": "local_campaign", "label": "Local Campaign"},
    ],
}

SHARED_DROPDOWN_REGISTRY: dict[str, list[dict[str, str]]] = {
    "organization_type": [
        {"key": key, "label": ORGANIZATION_TYPE_LABELS[key]} for key in ORGANIZATION_TYPE_OPTIONS
    ],
    "person_status": [
        {"key": "active", "label": "Active"},
        {"key": "inactive", "label": "Inactive"},
        {"key": "on_leave", "label": "On Leave"},
        {"key": "retired", "label": "Retired"},
        {"key": "deceased", "label": "Deceased"},
    ],
    "assignment_status": [
        {"key": "pending", "label": "Pending"},
        {"key": "active", "label": "Active"},
        {"key": "acting", "label": "Acting"},
        {"key": "completed", "label": "Completed"},
        {"key": "cancelled", "label": "Cancelled"},
    ],
    "transition_event_type": [
        {"key": "appointed", "label": "Appointed"},
        {"key": "elected", "label": "Elected"},
        {"key": "promoted", "label": "Promoted"},
        {"key": "transferred", "label": "Transferred"},
        {"key": "reassigned", "label": "Reassigned"},
        {"key": "retired", "label": "Retired"},
        {"key": "resigned", "label": "Resigned"},
    ],
    "support_record_type": [
        {"key": "appointment_record", "label": "Appointment Record"},
        {"key": "promotion_record", "label": "Promotion Record"},
        {"key": "transfer_record", "label": "Transfer Record"},
        {"key": "official_roster", "label": "Official Roster"},
        {"key": "service_record", "label": "Service Record"},
        {"key": "official_photo", "label": "Official Photo"},
    ],
    "privacy_level": [
        {"key": "public", "label": "Public"},
        {"key": "internal", "label": "Internal"},
        {"key": "restricted", "label": "Restricted"},
        {"key": "confidential", "label": "Confidential"},
    ],
}


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def get_safe_organization_type(organization_type: Any) -> str:
    normalized = _normalize(organization_type)
    if normalized in ORGANIZATION_TYPE_OPTIONS:
        return normalized
    return "custom"


def get_all_organization_types() -> list[dict[str, str]]:
    return deepcopy(SHARED_DROPDOWN_REGISTRY["organization_type"])


def get_organization_subtypes(organization_type: Any) -> list[dict[str, str]]:
    normalized = get_safe_organization_type(organization_type)
    return deepcopy(ORGANIZATION_SUBTYPE_OPTIONS.get(normalized) or [])


def get_shared_dropdowns() -> dict[str, list[dict[str, str]]]:
    return deepcopy(SHARED_DROPDOWN_REGISTRY)


def assert_no_duplicate_dropdown_keys() -> None:
    for group_key, options in SHARED_DROPDOWN_REGISTRY.items():
        seen: set[str] = set()
        for option in options:
            option_key = _normalize(option.get("key"))
            if not option_key:
                raise ValueError(f"Dropdown group '{group_key}' contains an empty key.")
            if option_key in seen:
                raise ValueError(
                    f"Dropdown group '{group_key}' contains duplicate key '{option_key}'."
                )
            seen.add(option_key)
