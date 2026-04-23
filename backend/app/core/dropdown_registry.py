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



INTAKE_DROPDOWN_REGISTRY: dict[str, list[dict[str, str]]] = {
    "who_are_you_adding": [
        {"key": "myself", "label": "Myself"},
        {"key": "parent", "label": "Parent"},
        {"key": "child", "label": "Child"},
        {"key": "spouse_or_partner", "label": "Spouse or Partner"},
        {"key": "sibling", "label": "Sibling"},
        {"key": "grandparent", "label": "Grandparent"},
        {"key": "grandchild", "label": "Grandchild"},
        {"key": "other_relative", "label": "Other Relative"},
        {"key": "household_member", "label": "Household Member"},
        {"key": "linked_household_member", "label": "Linked Household Member"},
        {"key": "organization_member", "label": "Organization Member"},
    ],
    "exact_relationship_type": [
        {"key": "biological_parent", "label": "Biological Parent"},
        {"key": "adoptive_parent", "label": "Adoptive Parent"},
        {"key": "step_parent", "label": "Step Parent"},
        {"key": "guardian", "label": "Guardian"},
        {"key": "spouse", "label": "Spouse"},
        {"key": "former_spouse", "label": "Former Spouse"},
        {"key": "sibling", "label": "Sibling"},
        {"key": "household_member", "label": "Household Member"},
        {"key": "linked_household", "label": "Linked Household"},
    ],
    "where_should_this_belong": [
        {"key": "auto", "label": "Let Tomb of Light place this automatically"},
        {"key": "main_household_line", "label": "Main Household Line"},
        {"key": "linked_household_branch", "label": "Linked Household Branch"},
        {"key": "organization_structure", "label": "Organization Structure"},
    ],
    "what_are_you_uploading": [
        {"key": "portrait_photo", "label": "Portrait Photo"},
        {"key": "group_photo", "label": "Group Photo"},
        {"key": "document", "label": "Document"},
        {"key": "certificate", "label": "Certificate"},
        {"key": "private_voice_message", "label": "Private Voice Message"},
        {"key": "private_video_message", "label": "Private Video Message"},
        {"key": "narration_audio", "label": "Narration Audio"},
        {"key": "memorial_media", "label": "Memorial Media"},
        {"key": "verification_evidence", "label": "Verification Evidence"},
    ],
    "who_does_this_item_belong_to": [
        {"key": "project", "label": "Project"},
        {"key": "household", "label": "Household"},
        {"key": "specific_person", "label": "Specific Person"},
        {"key": "relationship_record", "label": "Relationship Record"},
        {"key": "organization_unit", "label": "Organization Unit"},
    ],
    "privacy_scope": [
        {"key": "only_me", "label": "Only Me"},
        {"key": "me_and_co_owner", "label": "Me and Co-Owner"},
        {"key": "household_private", "label": "Household Private"},
        {"key": "branch_shared", "label": "Branch Shared"},
        {"key": "linked_household_shared", "label": "Linked Household Shared"},
        {"key": "public_memorial", "label": "Public Memorial"},
        {"key": "minor_protected", "label": "Minor Protected"},
    ],
    "release_mode": [
        {"key": "immediate", "label": "Immediate"},
        {"key": "scheduled", "label": "Scheduled (planned)"},
        {"key": "manual", "label": "Manual"},
    ],
    "verification_choice": [
        {"key": "no_verification_needed", "label": "No Verification Needed"},
        {"key": "attach_supporting_evidence", "label": "Attach Supporting Evidence"},
        {
            "key": "this_is_evidence_for_existing_person_or_relationship",
            "label": "Evidence for Existing Person or Relationship",
        },
    ],
}


PRIVACY_SCOPE_CANONICAL_MAP: dict[str, str] = {
    "only_me": "private_to_owner",
    "me_and_co_owner": "private_to_owner_and_co_owner",
    "household_private": "household_private",
    "branch_shared": "branch_shared",
    "linked_household_shared": "linked_family_shared",
    "public_memorial": "public_memorial",
    "minor_protected": "minor_protected",
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


def get_intake_dropdowns() -> dict[str, list[dict[str, str]]]:
    return deepcopy(INTAKE_DROPDOWN_REGISTRY)


def get_privacy_scope_canonical_map() -> dict[str, str]:
    return deepcopy(PRIVACY_SCOPE_CANONICAL_MAP)
