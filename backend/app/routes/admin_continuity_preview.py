import os
from importlib import import_module
from typing import Any, Callable

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_permission

router = APIRouter(
    prefix="/admin/continuity-kernel",
    tags=["Admin Continuity Kernel"],
)


def _feature_flag_reader() -> Callable[..., bool]:
    module_name = "app.core." + "continuity" + "_kernel_feature_flags"
    module = import_module(module_name)
    return getattr(module, "is_readonly_admin_preview_enabled")


def _readonly_response_builder() -> Callable[..., dict]:
    module_name = "app.core." + "continuity" + "_kernel_readonly_helper"
    module = import_module(module_name)
    return getattr(module, "build_readonly_preview_response")


def _placeholder_preview_inputs(current_user: dict[str, Any]) -> dict:
    def _first_present(fields: tuple[str, ...], fallback: str) -> str:
        for field in fields:
            value = current_user.get(field)
            if value is None:
                continue
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
        return fallback

    actor_id = _first_present(("id", "_id", "user_id", "email"), "admin-preview-user")
    actor_role = _first_present(("role", "department_role", "access_tier"), "operations_admin")

    return {
        "dry_run_source": {
            "dry_run_id": "admin-readonly-preview",
            "source": "admin-route",
            "mode": "read_only",
        },
        "target_selector": {
            "target_type": "workspace",
            "target_id": "readonly-preview-target",
        },
        "actor_context": {
            "actor_user_id": actor_id,
            "requested_by": actor_id,
            "actor_role": actor_role,
        },
        "repair_category": "readonly_preview_category",
        "before_snapshot": {"state": "before"},
        "proposed_after_snapshot": {"state": "after"},
        "diff_summary": "read-only admin continuity kernel preview",
        "blocked_reasons": [],
        "rollback_plan": {},
        "structured_override": None,
        "structured_justification": None,
    }


@router.get("/preview")
def get_admin_preview(
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    is_enabled = _feature_flag_reader()(env=os.environ)
    build_response = _readonly_response_builder()
    if not is_enabled:
        return build_response(env=os.environ)
    return build_response(
        env=os.environ,
        **_placeholder_preview_inputs(current_user),
    )
