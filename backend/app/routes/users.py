from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.database import get_database
from app.dependencies.auth import (
    get_current_user,
    is_customer_account,
    require_capability,
    require_permission,
)
from app.schemas.experience import (
    UserEmailChangeConfirm,
    UserEmailChangeRequest,
    UserEmailChangeResponse,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.schemas.user import UserCreate, UserResponse, build_user_response
from app.services.auth_service import get_user_by_id
from app.services.user_service import (
    confirm_email_change,
    list_users,
    request_email_change,
    update_user_profile,
)
from app.services.rate_limit_service import enforce_rate_limit
from app.services.workspace_access_service import build_workspace_context_snapshot

router = APIRouter(prefix="/users", tags=["Users"])

SECURITY_ACTIVITY_LABELS: dict[str, str] = {
    "account_activation_requested": "Account activation requested",
    "customer_profile_updated": "Personal details updated",
    "customer_email_change_requested": "Email change requested",
    "customer_email_changed": "Login email changed",
    "password_reset_requested": "Password reset requested",
    "password_reset_completed": "Password reset completed",
    "password_changed": "Password changed",
    "mfa_enrollment_verified": "Authenticator MFA enabled",
    "mfa_disabled": "Authenticator MFA disabled",
    "mfa_login_challenge_failed": "MFA verification failed",
    "mfa_login_challenge_succeeded": "MFA verification succeeded",
    "session_revoked": "Session signed out or revoked",
    "admin_security_reset": "Account security reset",
}
SECURITY_ACTIVITY_LIMIT = 20


def _apply_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _request_key(request: Request, principal: str) -> str:
    client_host = str((request.client.host if request.client else "") or "").strip()
    return f"{client_host or 'unknown'}:{principal}"


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _require_customer_self_service(user: dict[str, Any]) -> None:
    if not is_customer_account(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account self-service is not available to internal accounts.",
        )


def _profile_response(user: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
    user_id = (
        _current_user_id(user)
        if user.get("_id") or user.get("id") or user.get("user_id")
        else _current_user_id(current_user)
    )
    address = user.get("mailing_address_structured")
    if not isinstance(address, dict):
        address = None
    return {
        "id": str(user.get("_id") or user.get("id") or user_id),
        "email": str(user.get("email") or current_user.get("email") or "").strip().lower(),
        "full_name": str(
            user.get("full_name")
            or current_user.get("full_name")
            or current_user.get("name")
            or ""
        ).strip(),
        "role": str(user.get("role") or current_user.get("role") or "user").strip(),
        "status": str(user.get("status") or current_user.get("status") or "active").strip(),
        "created_at": str(user.get("created_at") or current_user.get("created_at") or ""),
        "last_login_at": user.get("last_login_at") or current_user.get("last_login_at"),
        "policy_version": user.get("policy_version") or current_user.get("policy_version"),
        "phone_number": user.get("phone_number") or None,
        "mailing_address": address,
        "pending_email": user.get("pending_email") or None,
        "billing_sync_status": user.get("billing_profile_sync_status") or None,
        "legal_acceptance": {
            "policy_version": user.get("policy_version") or current_user.get("policy_version"),
            "terms_accepted_at": user.get("terms_accepted_at") or current_user.get("terms_accepted_at"),
            "privacy_accepted_at": user.get("privacy_accepted_at") or current_user.get("privacy_accepted_at"),
            "eligibility_attested_at": (
                user.get("eligibility_attested_at")
                or current_user.get("eligibility_attested_at")
            ),
        },
    }


def _security_activity_result(value: Any) -> str:
    normalized = str(value or "success").strip().lower()
    if normalized in {"success", "succeeded", "complete", "completed", "ok"}:
        return "success"
    if normalized in {"failure", "failed", "error", "denied", "blocked"}:
        return "failed"
    return "recorded"


def _list_customer_security_activity(user_id: str) -> list[dict[str, str]]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    query = {
        "action": {"$in": sorted(SECURITY_ACTIVITY_LABELS)},
        "$or": [
            {"target_type": "user", "target_id": user_id},
            {"actor_user_id": user_id},
        ],
    }
    cursor = (
        db["audit_logs"]
        .find(query)
        .sort("timestamp", -1)
        .limit(SECURITY_ACTIVITY_LIMIT)
    )

    items: list[dict[str, str]] = []
    for row in cursor:
        action = str(row.get("action") or "").strip().lower()
        label = SECURITY_ACTIVITY_LABELS.get(action)
        if not label:
            continue
        items.append(
            {
                "action": action,
                "label": label,
                "result": _security_activity_result(row.get("result")),
                "timestamp": str(row.get("timestamp") or "").strip(),
            }
        )
    return items


@router.get("/", response_model=list[UserResponse])
def get_users(current_user: dict[str, Any] = Depends(require_permission("admin.users.read"))):
    users = list_users()
    return [build_user_response(user) for user in users]


@router.post("/", response_model=UserResponse)
def create_user_route(
    payload: UserCreate,
    current_user: dict[str, Any] = Depends(require_capability("manage_users_full")),
):
    del payload, current_user
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Direct account creation is retired. Use the Continuity Kernel "
            "customer_account_create action so approval, activation, and evidence are recorded."
        ),
    )


@router.get("/me/profile", response_model=UserProfileResponse)
def get_my_profile(response: Response, current_user: dict[str, Any] = Depends(get_current_user)):
    _apply_no_store(response)
    _require_customer_self_service(current_user)
    user_id = _current_user_id(current_user)
    user = get_user_by_id(user_id) or current_user
    return _profile_response(user, current_user)


@router.patch("/me/profile", response_model=UserProfileResponse)
def patch_my_profile(
    payload: UserProfileUpdate,
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _apply_no_store(response)
    _require_customer_self_service(current_user)
    user_id = _current_user_id(current_user)
    try:
        profile_updates: dict[str, Any] = {"full_name": payload.full_name}
        if "phone_number" in payload.model_fields_set:
            profile_updates["phone_number"] = payload.phone_number
        if "mailing_address" in payload.model_fields_set:
            profile_updates["mailing_address"] = (
                payload.mailing_address.model_dump() if payload.mailing_address else None
            )
        updated_user = update_user_profile(user_id, **profile_updates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return _profile_response(updated_user, current_user)


@router.get("/me/security-activity")
def get_my_security_activity(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _apply_no_store(response)
    _require_customer_self_service(current_user)
    try:
        items = _list_customer_security_activity(_current_user_id(current_user))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security activity is temporarily unavailable.",
        ) from exc
    return {"items": items, "count": len(items)}


@router.post("/me/email-change/request", response_model=UserEmailChangeResponse)
def request_my_email_change(
    payload: UserEmailChangeRequest,
    request: Request,
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _apply_no_store(response)
    _require_customer_self_service(current_user)
    enforce_rate_limit(
        scope="customer_email_change_request",
        key=_request_key(request, _current_user_id(current_user)),
        limit=max(1, int(settings.auth_password_reset_request_rate_limit or 5)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
    )
    try:
        return request_email_change(
            _current_user_id(current_user),
            new_email=str(payload.new_email),
            current_password=payload.current_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/me/email-change/confirm", response_model=UserEmailChangeResponse)
def confirm_my_email_change(
    payload: UserEmailChangeConfirm,
    request: Request,
    response: Response,
):
    _apply_no_store(response)
    enforce_rate_limit(
        scope="customer_email_change_confirm",
        key=_request_key(request, "token"),
        limit=max(1, int(settings.auth_password_reset_request_rate_limit or 5)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
    )
    try:
        return confirm_email_change(payload.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/me/workspace-context")
def get_my_workspace_context(
    project_id: str = "",
    family_id: str = "",
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return build_workspace_context_snapshot(
        current_user,
        project_id=project_id,
        family_id=family_id,
    )


@router.get("/me/access-context")
def get_my_access_context(
    project_id: str = "",
    family_id: str = "",
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return get_my_workspace_context(
        project_id=project_id,
        family_id=family_id,
        current_user=current_user,
    )
