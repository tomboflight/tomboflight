from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from app.routes import users as users_routes


class _Cursor(list):
    def sort(self, key, direction):
        reverse = int(direction) < 0
        return _Cursor(sorted(self, key=lambda row: str(row.get(key) or ""), reverse=reverse))

    def limit(self, amount):
        return _Cursor(self[: int(amount)])


class _AuditCollection:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self.last_query = None

    @staticmethod
    def _matches(row, query):
        action_filter = query.get("action") or {}
        if "$in" in action_filter and row.get("action") not in action_filter["$in"]:
            return False

        alternatives = query.get("$or") or []
        if alternatives:
            matched = False
            for alternative in alternatives:
                if all(row.get(key) == value for key, value in alternative.items()):
                    matched = True
                    break
            if not matched:
                return False
        return True

    def find(self, query):
        self.last_query = query
        return _Cursor([row for row in self.rows if self._matches(row, query)])


class _Database(dict):
    def __init__(self, rows):
        super().__init__({"audit_logs": _AuditCollection(rows)})


def test_customer_security_activity_is_user_scoped_allowlisted_and_redacted():
    rows = [
        {
            "action": "customer_profile_updated",
            "actor_user_id": "user-1",
            "target_type": "user",
            "target_id": "user-1",
            "result": "success",
            "timestamp": "2026-09-07T01:00:00+00:00",
            "before": {"email": "old@example.com"},
            "after": {"email": "new@example.com"},
            "details": {"token": "must-not-leak"},
            "context": {"ip": "203.0.113.10"},
            "actor_email": "customer@example.com",
        },
        {
            "action": "password_reset_completed",
            "actor_user_id": "user-2",
            "target_type": "user",
            "target_id": "user-2",
            "result": "success",
            "timestamp": "2026-09-07T00:59:00+00:00",
        },
        {
            "action": "vault_item_created",
            "actor_user_id": "user-1",
            "target_type": "vault_item",
            "target_id": "vault-1",
            "result": "success",
            "timestamp": "2026-09-07T00:58:00+00:00",
        },
    ]
    database = _Database(rows)
    response = Response()

    with (
        patch.object(users_routes, "get_database", return_value=database),
        patch.object(users_routes, "is_customer_account", return_value=True),
    ):
        result = users_routes.get_my_security_activity(
            response=response,
            current_user={"id": "user-1", "email": "customer@example.com", "role": "user"},
        )

    assert result["count"] == 1
    assert result["items"] == [
        {
            "action": "customer_profile_updated",
            "label": "Personal details updated",
            "result": "success",
            "timestamp": "2026-09-07T01:00:00+00:00",
        }
    ]
    assert set(result["items"][0]) == {"action", "label", "result", "timestamp"}
    assert response.headers["Cache-Control"] == "no-store"


def test_customer_security_activity_empty_state_is_clean():
    response = Response()
    with (
        patch.object(users_routes, "get_database", return_value=_Database([])),
        patch.object(users_routes, "is_customer_account", return_value=True),
    ):
        result = users_routes.get_my_security_activity(
            response=response,
            current_user={"id": "user-empty", "email": "empty@example.com", "role": "user"},
        )

    assert result == {"items": [], "count": 0}


def test_internal_identity_cannot_use_customer_security_activity_endpoint():
    with patch.object(users_routes, "is_customer_account", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            users_routes.get_my_security_activity(
                response=Response(),
                current_user={"id": "admin-1", "email": "admin@example.com", "role": "super_admin"},
            )

    assert exc_info.value.status_code == 403


def test_step5_frontend_uses_authoritative_account_endpoints_and_safe_request_path():
    root = Path(__file__).resolve().parents[2]
    script = (root / "customer-account-step5.js").read_text(encoding="utf-8")
    html = (root / "account-security.html").read_text(encoding="utf-8")

    assert '"/users/me/profile"' in script
    assert '"/users/me/workspace-context"' in script
    assert '"/users/me/security-activity"' in script
    assert "PACKAGE_PROFILES" not in script
    assert "data-customer-account-summary" in html
    assert "data-security-activity-panel" in html
    assert 'href="data-request.html"' in html
    assert "data-account-data-requests-link" in html


def test_security_activity_result_normalization_does_not_echo_arbitrary_backend_text():
    assert users_routes._security_activity_result("success") == "success"
    assert users_routes._security_activity_result("denied") == "failed"
    assert users_routes._security_activity_result("internal-detail-that-should-not-leak") == "recorded"
