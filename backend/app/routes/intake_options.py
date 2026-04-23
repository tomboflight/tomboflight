from __future__ import annotations

from fastapi import APIRouter

from app.core.dropdown_registry import (
    get_intake_dropdowns,
    get_privacy_scope_canonical_map,
)

router = APIRouter(tags=["Intake Options"])


@router.get("/intake/options")
def get_intake_options_route():
    return {
        "dropdowns": get_intake_dropdowns(),
        "privacy_scope_mapping": get_privacy_scope_canonical_map(),
        "defaults": {
            "where_should_this_belong": "auto",
            "privacy_scope": "household_private",
            "release_mode": "immediate",
        },
    }
