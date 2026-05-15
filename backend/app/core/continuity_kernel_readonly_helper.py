"""
Continuity Kernel isolated read-only preview helper.

This module is isolated.
This module is read-only.
This module does not expose routes.
This module does not execute repairs.
This module does not approve apply.
This module does not schedule apply.
This module does not write to the database.
This module does not queue mint work.
This module does not mutate certificates.
This module does not alter customer records.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from backend.app.core.continuity_kernel_admin_preview import PROHIBITED_ACTIONS, build_admin_preview
from backend.app.core.continuity_kernel_dry_run_adapter import build_staging_dry_run_payload
from backend.app.core.continuity_kernel_feature_flags import is_readonly_admin_preview_enabled
from backend.app.core.continuity_kernel_validator import validate_apply_request

_DEFAULT_DISABLED_RESPONSE = {
    "enabled": False,
    "status": "disabled",
    "preview": None,
    "validator_result": None,
    "allowed_actions": [],
    "reason_codes": ["FEATURE_FLAG_DISABLED"],
}


def _fixture_context_required_response(*, enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "status": "blocked",
        "preview": None,
        "validator_result": None,
        "allowed_actions": [],
        "reason_codes": ["TEST_CONTEXT_REQUIRED"],
    }


def _invalid_fixture_payload_response(*, enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "status": "invalid_payload",
        "preview": None,
        "validator_result": {"passed": False, "reason_codes": ["FIXTURE_PAYLOAD_INVALID"]},
        "allowed_actions": [],
        "reason_codes": ["FIXTURE_PAYLOAD_INVALID"],
    }


def _safe_dict(value: Any) -> dict:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    return {}


def _safe_list(value: Any) -> list:
    return deepcopy(value) if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _safe_allowed_actions(preview: dict) -> list[str]:
    raw_actions = preview.get("allowed_actions")
    if not isinstance(raw_actions, list):
        return []
    prohibited = set(PROHIBITED_ACTIONS)
    safe_actions = [str(action) for action in raw_actions if isinstance(action, str) and action not in prohibited]
    return _dedupe(safe_actions)


def _safe_reason_codes(validator_result: dict) -> list[str]:
    reason_codes = validator_result.get("reason_codes") if isinstance(validator_result, dict) else []
    if not isinstance(reason_codes, list):
        return []
    return _dedupe([str(value) for value in reason_codes if isinstance(value, str)])


def build_readonly_preview_response(
    *,
    env: dict | None = None,
    dry_run_source: dict | None = None,
    target_selector: dict | None = None,
    actor_context: dict | None = None,
    repair_category: str = "",
    before_snapshot: dict | None = None,
    proposed_after_snapshot: dict | None = None,
    diff_summary: str = "",
    blocked_reasons: list | None = None,
    rollback_plan: dict | None = None,
    structured_override: dict | None = None,
    structured_justification: dict | None = None,
    approval_fixture_payload: dict | None = None,
    test_context: bool = False,
) -> dict:
    """Build a read-only preview response from in-memory Continuity Kernel payload inputs."""
    safe_env = _safe_dict(env)
    if not is_readonly_admin_preview_enabled(env=safe_env):
        return deepcopy(_DEFAULT_DISABLED_RESPONSE)

    if approval_fixture_payload is not None:
        if test_context is not True:
            return _fixture_context_required_response(enabled=True)
        if not isinstance(approval_fixture_payload, dict):
            return _invalid_fixture_payload_response(enabled=True)
        payload = _safe_dict(approval_fixture_payload)
    else:
        payload = build_staging_dry_run_payload(
            dry_run_source=_safe_dict(dry_run_source),
            target_selector=_safe_dict(target_selector),
            actor_context=_safe_dict(actor_context),
            repair_category=_safe_text(repair_category),
            before_snapshot=_safe_dict(before_snapshot),
            proposed_after_snapshot=_safe_dict(proposed_after_snapshot),
            diff_summary=deepcopy(diff_summary),
            blocked_reasons=_safe_list(blocked_reasons),
            rollback_plan=_safe_dict(rollback_plan),
            structured_override=_safe_dict(structured_override) if isinstance(structured_override, dict) else None,
            structured_justification=_safe_dict(structured_justification) if isinstance(structured_justification, dict) else None,
        )

    validator_result = validate_apply_request(
        packet=_safe_dict(payload.get("evidence_packet")),
        authorization=_safe_dict(payload.get("authorization_decision")),
        transition=_safe_dict(payload.get("apply_transition")),
        rollback=_safe_dict(payload.get("rollback_verification")),
    )
    safe_validator_result = _safe_dict(validator_result)
    payload["validator_result"] = deepcopy(safe_validator_result)

    preview = build_admin_preview(_safe_dict(payload))
    safe_preview = _safe_dict(preview)
    safe_preview["allowed_actions"] = _safe_allowed_actions(safe_preview)

    allowed_actions = _safe_allowed_actions(safe_preview)
    reason_codes = _safe_reason_codes(safe_validator_result)
    status = safe_preview.get("status") if isinstance(safe_preview.get("status"), str) else "validation_failed"

    if safe_validator_result.get("passed") is not True:
        status = "validation_failed"
        allowed_actions = []
        safe_preview["allowed_actions"] = []
        reason_codes = _dedupe(reason_codes + ["VALIDATOR_FAILED_CLOSED"])

    return {
        "enabled": True,
        "status": status,
        "preview": safe_preview,
        "validator_result": safe_validator_result,
        "allowed_actions": allowed_actions,
        "reason_codes": reason_codes,
    }


__all__ = ["build_readonly_preview_response"]
