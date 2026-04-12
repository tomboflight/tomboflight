from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _as_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_datetime_string(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return datetime.now(UTC).isoformat()


def _as_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


class RoleResponse(BaseModel):
    id: str
    role_code: str
    role_name: str
    status: str
    description: str = ""
    created_at: str
    updated_at: str | None = None


class PermissionResponse(BaseModel):
    id: str
    permission_code: str
    permission_name: str
    status: str
    description: str = ""
    created_at: str
    updated_at: str | None = None


class RolePermissionResponse(BaseModel):
    id: str
    role_code: str
    permission_code: str
    status: str
    created_at: str
    updated_at: str | None = None


class UserRoleAssignmentResponse(BaseModel):
    id: str
    user_id: str
    role_code: str
    status: str
    assigned_by: str | None = None
    assigned_at: str
    created_at: str
    updated_at: str | None = None


class WorkflowEventResponse(BaseModel):
    id: str
    project_id: str
    from_state: str
    to_state: str
    status: str
    actor_user_id: str | None = None
    actor_role_code: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str | None = None


class VaultResponse(BaseModel):
    id: str
    vault_code: str
    vault_type: str
    status: str
    project_id: str | None = None
    family_id: str | None = None
    organization_id: str | None = None
    storage_limit_bytes: int = 0
    storage_used_bytes: int = 0
    created_at: str
    updated_at: str | None = None


class VaultFileResponse(BaseModel):
    id: str
    file_id: str
    vault_id: str
    project_id: str | None = None
    uploader_id: str
    category: str
    evidence_kind: str = ""
    checksum: str
    internal_only: bool = False
    customer_visible: bool = False
    verification_status: str
    size_bytes: int = 0
    uploaded_at: str
    last_accessed_at: str | None = None
    created_at: str
    updated_at: str | None = None


class ToolStatusResponse(BaseModel):
    id: str
    tool_code: str
    status: str
    severity: str
    message: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str | None = None


class FailedWorkflowQueueResponse(BaseModel):
    id: str
    queue_item_id: str
    project_id: str | None = None
    workflow_name: str
    failed_state: str
    failure_reason: str
    status: str
    retry_count: int = 0
    next_retry_at: str | None = None
    created_at: str
    updated_at: str | None = None


def build_role_response(data: dict[str, Any]) -> RoleResponse:
    return RoleResponse(
        id=_as_string(data.get("_id")),
        role_code=_as_string(data.get("role_code")),
        role_name=_as_string(data.get("role_name")),
        status=_as_string(data.get("status"), "active"),
        description=_as_string(data.get("description")),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_permission_response(data: dict[str, Any]) -> PermissionResponse:
    return PermissionResponse(
        id=_as_string(data.get("_id")),
        permission_code=_as_string(data.get("permission_code")),
        permission_name=_as_string(data.get("permission_name")),
        status=_as_string(data.get("status"), "active"),
        description=_as_string(data.get("description")),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_role_permission_response(data: dict[str, Any]) -> RolePermissionResponse:
    return RolePermissionResponse(
        id=_as_string(data.get("_id")),
        role_code=_as_string(data.get("role_code")),
        permission_code=_as_string(data.get("permission_code")),
        status=_as_string(data.get("status"), "active"),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_user_role_assignment_response(data: dict[str, Any]) -> UserRoleAssignmentResponse:
    return UserRoleAssignmentResponse(
        id=_as_string(data.get("_id")),
        user_id=_as_string(data.get("user_id")),
        role_code=_as_string(data.get("role_code")),
        status=_as_string(data.get("status"), "active"),
        assigned_by=_as_string(data.get("assigned_by")) or None,
        assigned_at=_as_datetime_string(data.get("assigned_at") or data.get("created_at")),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_workflow_event_response(data: dict[str, Any]) -> WorkflowEventResponse:
    return WorkflowEventResponse(
        id=_as_string(data.get("_id")),
        project_id=_as_string(data.get("project_id")),
        from_state=_as_string(data.get("from_state")),
        to_state=_as_string(data.get("to_state")),
        status=_as_string(data.get("status"), "recorded"),
        actor_user_id=_as_string(data.get("actor_user_id")) or None,
        actor_role_code=_as_string(data.get("actor_role_code")) or None,
        context=_as_context(data.get("context")),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_vault_response(data: dict[str, Any]) -> VaultResponse:
    return VaultResponse(
        id=_as_string(data.get("_id")),
        vault_code=_as_string(data.get("vault_code")),
        vault_type=_as_string(data.get("vault_type"), "standard"),
        status=_as_string(data.get("status"), "active"),
        project_id=_as_string(data.get("project_id")) or None,
        family_id=_as_string(data.get("family_id")) or None,
        organization_id=_as_string(data.get("organization_id")) or None,
        storage_limit_bytes=int(data.get("storage_limit_bytes") or 0),
        storage_used_bytes=int(data.get("storage_used_bytes") or 0),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_vault_file_response(data: dict[str, Any]) -> VaultFileResponse:
    return VaultFileResponse(
        id=_as_string(data.get("_id")),
        file_id=_as_string(data.get("file_id")),
        vault_id=_as_string(data.get("vault_id")),
        project_id=_as_string(data.get("project_id")) or None,
        uploader_id=_as_string(data.get("uploader_id")),
        category=_as_string(data.get("category")),
        evidence_kind=_as_string(data.get("evidence_kind")),
        checksum=_as_string(data.get("checksum")),
        internal_only=_as_bool(data.get("internal_only"), False),
        customer_visible=_as_bool(data.get("customer_visible"), False),
        verification_status=_as_string(data.get("verification_status"), "pending"),
        size_bytes=int(data.get("size_bytes") or 0),
        uploaded_at=_as_datetime_string(data.get("uploaded_at") or data.get("created_at")),
        last_accessed_at=_as_datetime_string(data.get("last_accessed_at")) if data.get("last_accessed_at") else None,
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_tool_status_response(data: dict[str, Any]) -> ToolStatusResponse:
    return ToolStatusResponse(
        id=_as_string(data.get("_id")),
        tool_code=_as_string(data.get("tool_code")),
        status=_as_string(data.get("status"), "ok"),
        severity=_as_string(data.get("severity"), "info"),
        message=_as_string(data.get("message")),
        context=_as_context(data.get("context")),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )


def build_failed_workflow_queue_response(data: dict[str, Any]) -> FailedWorkflowQueueResponse:
    return FailedWorkflowQueueResponse(
        id=_as_string(data.get("_id")),
        queue_item_id=_as_string(data.get("queue_item_id")),
        project_id=_as_string(data.get("project_id")) or None,
        workflow_name=_as_string(data.get("workflow_name")),
        failed_state=_as_string(data.get("failed_state")),
        failure_reason=_as_string(data.get("failure_reason")),
        status=_as_string(data.get("status"), "queued"),
        retry_count=int(data.get("retry_count") or 0),
        next_retry_at=_as_datetime_string(data.get("next_retry_at")) if data.get("next_retry_at") else None,
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )
