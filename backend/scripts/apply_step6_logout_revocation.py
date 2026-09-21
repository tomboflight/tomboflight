from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    occurrences = source.count(old)
    if occurrences != 1:
        raise RuntimeError(
            f"Expected exactly one replacement target in {path}; found {occurrences}."
        )
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


AUTH_ROUTE = REPOSITORY_ROOT / "backend" / "app" / "routes" / "auth.py"
AUTH_SERVICE = REPOSITORY_ROOT / "backend" / "app" / "services" / "auth_service.py"
TEST_FILE = REPOSITORY_ROOT / "backend" / "tests" / "test_logout_revocation_integrity.py"


OLD_LOGOUT = '''@router.post("/logout")
def logout(request: Request, response: Response):
    bearer_token = (
        request.headers.get("authorization", "").split(" ", 1)[1]
        if request.headers.get("authorization", "").lower().startswith("bearer ")
        else ""
    )
    cookie_token = str(request.cookies.get(COOKIE_NAME) or "")

    payload = None
    token = ""
    source = None

    if bearer_token:
        bearer_payload = decode_access_token(str(bearer_token or ""))
        if bearer_payload:
            token = bearer_token
            payload = bearer_payload
            source = "bearer"

    if not token and cookie_token:
        token = cookie_token
        payload = decode_access_token(cookie_token)
        source = "cookie"

    if not token and bearer_token:
        token = bearer_token
        source = "bearer"

    if source == "cookie":
        _enforce_cookie_auth_origin(request)

    user_id = _extract_user_id_from_token(str(token or ""))
    if not user_id and payload:
        user = get_user_by_email(str(payload.get("sub") or "").strip().lower())
        user_id = _current_user_id(user or {})
    if user_id:
        try:
            revoke_user_sessions(user_id=user_id, actor_user_id=user_id, reason="logout")
        except Exception:
            pass
    _clear_auth_cookie(response, request)
    _apply_no_store(response)
    return {"success": True, "message": "Logged out successfully."}
'''


NEW_LOGOUT = '''LOGOUT_REVOCATION_FAILURE_MESSAGE = (
    "This device was signed out locally, but server-side session revocation "
    "could not be confirmed. Use Account Security or reset your password to "
    "invalidate any remaining sessions."
)


def _resolve_logout_user_id(token: str, payload: dict | None) -> str:
    if not payload:
        return ""

    direct_user_id = str(payload.get("user_id") or payload.get("id") or "").strip()
    if direct_user_id:
        return direct_user_id

    email = str(payload.get("sub") or payload.get("email") or "").strip().lower()
    if email:
        user = get_user_by_email(email)
        resolved_user_id = _current_user_id(user or {})
        if resolved_user_id:
            return resolved_user_id

    # Preserve compatibility with older signed tokens that carried a stable id
    # outside the current user_id claim. Never treat the email subject itself as
    # an id when the identity store could not resolve it.
    extracted_identity = _extract_user_id_from_token(str(token or ""))
    if extracted_identity and extracted_identity.strip().lower() != email:
        return extracted_identity.strip()
    return ""


@router.post("/logout")
def logout(request: Request, response: Response):
    bearer_token = (
        request.headers.get("authorization", "").split(" ", 1)[1]
        if request.headers.get("authorization", "").lower().startswith("bearer ")
        else ""
    )
    cookie_token = str(request.cookies.get(COOKIE_NAME) or "")

    payload = None
    token = ""
    source = None

    if bearer_token:
        bearer_payload = decode_access_token(str(bearer_token or ""))
        if bearer_payload:
            token = bearer_token
            payload = bearer_payload
            source = "bearer"

    if not token and cookie_token:
        token = cookie_token
        payload = decode_access_token(cookie_token)
        source = "cookie"

    if not token and bearer_token:
        token = bearer_token
        source = "bearer"

    if source == "cookie":
        _enforce_cookie_auth_origin(request)

    revocation_required = bool(payload)
    revocation_confirmed = not revocation_required
    revocation_failure_reason = ""
    user_id = ""

    if revocation_required:
        try:
            user_id = _resolve_logout_user_id(token, payload)
            if not user_id:
                revocation_failure_reason = "logout_identity_unresolved"
            elif revoke_user_sessions(
                user_id=user_id,
                actor_user_id=user_id,
                reason="logout",
            ):
                revocation_confirmed = True
            else:
                revocation_failure_reason = "session_revocation_not_persisted"
        except Exception:
            revocation_failure_reason = "session_revocation_error"
            logger.exception(
                "Logout session revocation failed.",
                extra={"logout_user_id": user_id or None},
            )

    _clear_auth_cookie(response, request)
    _apply_no_store(response)

    if not revocation_confirmed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            create_audit_log(
                "session_revocation_failed",
                user_id or None,
                "user",
                user_id or "unresolved",
                {"reason": revocation_failure_reason or "revocation_unconfirmed"},
            )
        except Exception:
            logger.warning(
                "Unable to persist logout revocation-failure audit evidence.",
                exc_info=True,
            )
        return {
            "success": False,
            "local_logout": True,
            "server_revocation_required": True,
            "server_revocation_confirmed": False,
            "message": LOGOUT_REVOCATION_FAILURE_MESSAGE,
        }

    return {
        "success": True,
        "local_logout": True,
        "server_revocation_required": revocation_required,
        "server_revocation_confirmed": True,
        "message": "Logged out successfully.",
    }
'''


OLD_REVOKE_IMPORT = "from pymongo import ASCENDING\n"
NEW_REVOKE_IMPORT = "from pymongo import ASCENDING, ReturnDocument\n"


OLD_REVOKE = '''def revoke_user_sessions(
    *,
    user_id: str,
    actor_user_id: str | None = None,
    reason: str = "logout",
) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False
    next_version = _session_version(user) + 1
    db = get_database()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "session_token_version": next_version,
                "last_logout_at": _now_iso(),
            }
        },
    )
    try:
        create_audit_log(
            "session_revoked",
            actor_user_id or user_id,
            "user",
            str(user["_id"]),
            {
                "reason": _normalize_text(reason) or "logout",
                "email": _normalize_text(user.get("email")).lower(),
                "session_token_version": next_version,
            },
        )
    except Exception:
        pass
    return True
'''


NEW_REVOKE = '''def revoke_user_sessions(
    *,
    user_id: str,
    actor_user_id: str | None = None,
    reason: str = "logout",
) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False

    db = get_database()
    revoked_user = db.users.find_one_and_update(
        {"_id": user["_id"]},
        {
            "$inc": {"session_token_version": 1},
            "$set": {"last_logout_at": _now_iso()},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not revoked_user:
        return False

    next_version = _session_version(revoked_user)
    try:
        create_audit_log(
            "session_revoked",
            actor_user_id or user_id,
            "user",
            str(revoked_user.get("_id") or user["_id"]),
            {
                "reason": _normalize_text(reason) or "logout",
                "email": _normalize_text(
                    revoked_user.get("email") or user.get("email")
                ).lower(),
                "session_token_version": next_version,
            },
        )
    except Exception:
        pass
    return True
'''


TEST_CONTENT = '''from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from pymongo import ReturnDocument
from starlette.requests import Request
from starlette.responses import Response

from app.routes import auth as auth_routes
from app.services import auth_service


def _request_with_headers(
    headers: list[tuple[bytes, bytes]] | None = None,
    *,
    client_host: str = "127.0.0.1",
) -> Request:
    path = "/auth/logout"
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers or [],
            "client": (client_host, 12345),
            "server": ("testserver", 443),
        }
    )


def _deleted_cookie_headers(response: Response) -> str:
    return "\n".join(
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    )


class _UsersCollection:
    def __init__(self, result: dict[str, Any] | None) -> None:
        self.result = result
        self.calls: list[tuple[dict[str, Any], dict[str, Any], Any]] = []

    def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        return_document: Any,
    ) -> dict[str, Any] | None:
        self.calls.append((query, update, return_document))
        return self.result


class LogoutRevocationIntegrityTests(unittest.TestCase):
    def test_logout_does_not_claim_success_when_revocation_raises(self) -> None:
        request = _request_with_headers(
            [(b"authorization", b"Bearer valid-token")]
        )
        response = Response()

        with (
            patch.object(
                auth_routes,
                "decode_access_token",
                return_value={
                    "sub": "user@example.com",
                    "user_id": "user-1",
                },
            ),
            patch.object(
                auth_routes,
                "revoke_user_sessions",
                side_effect=RuntimeError("database unavailable"),
            ),
            patch.object(auth_routes, "create_audit_log"),
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertEqual(response.status_code, 503)
        self.assertFalse(payload["success"])
        self.assertTrue(payload["local_logout"])
        self.assertTrue(payload["server_revocation_required"])
        self.assertFalse(payload["server_revocation_confirmed"])
        cookie_headers = _deleted_cookie_headers(response)
        self.assertIn(auth_routes.COOKIE_NAME, cookie_headers)
        self.assertIn(auth_routes.CSRF_COOKIE_NAME, cookie_headers)
        self.assertIn("Max-Age=0", cookie_headers)

    def test_logout_does_not_claim_success_when_revocation_returns_false(self) -> None:
        request = _request_with_headers(
            [(b"authorization", b"Bearer valid-token")]
        )
        response = Response()

        with (
            patch.object(
                auth_routes,
                "decode_access_token",
                return_value={"user_id": "user-1"},
            ),
            patch.object(auth_routes, "revoke_user_sessions", return_value=False),
            patch.object(auth_routes, "create_audit_log"),
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertEqual(response.status_code, 503)
        self.assertFalse(payload["success"])
        self.assertFalse(payload["server_revocation_confirmed"])

    def test_logout_resolves_legacy_email_identity_before_revocation(self) -> None:
        request = _request_with_headers(
            [(b"authorization", b"Bearer legacy-token")]
        )
        response = Response()

        with (
            patch.object(
                auth_routes,
                "decode_access_token",
                return_value={"sub": "legacy@example.com"},
            ),
            patch.object(
                auth_routes,
                "get_user_by_email",
                return_value={"_id": "legacy-user"},
            ),
            patch.object(
                auth_routes,
                "revoke_user_sessions",
                return_value=True,
            ) as revoke_mock,
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["server_revocation_confirmed"])
        revoke_mock.assert_called_once_with(
            user_id="legacy-user",
            actor_user_id="legacy-user",
            reason="logout",
        )

    def test_invalid_or_expired_token_requires_only_local_logout(self) -> None:
        request = _request_with_headers(
            [(b"authorization", b"Bearer expired-token")]
        )
        response = Response()

        with (
            patch.object(auth_routes, "decode_access_token", return_value=None),
            patch.object(auth_routes, "revoke_user_sessions") as revoke_mock,
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["local_logout"])
        self.assertFalse(payload["server_revocation_required"])
        self.assertTrue(payload["server_revocation_confirmed"])
        revoke_mock.assert_not_called()

    def test_session_revocation_uses_atomic_monotonic_increment(self) -> None:
        users = _UsersCollection(
            {
                "_id": "user-1",
                "email": "user@example.com",
                "session_token_version": 4,
            }
        )
        database = SimpleNamespace(users=users)

        with (
            patch.object(
                auth_service,
                "get_user_by_id",
                return_value={
                    "_id": "user-1",
                    "email": "user@example.com",
                    "session_token_version": 3,
                },
            ),
            patch.object(auth_service, "get_database", return_value=database),
            patch.object(auth_service, "create_audit_log") as audit_mock,
        ):
            revoked = auth_service.revoke_user_sessions(
                user_id="user-1",
                actor_user_id="user-1",
                reason="logout",
            )

        self.assertTrue(revoked)
        self.assertEqual(len(users.calls), 1)
        query, update, return_document = users.calls[0]
        self.assertEqual(query, {"_id": "user-1"})
        self.assertEqual(update["$inc"], {"session_token_version": 1})
        self.assertIn("last_logout_at", update["$set"])
        self.assertEqual(return_document, ReturnDocument.AFTER)
        audit_payload = audit_mock.call_args.args[4]
        self.assertEqual(audit_payload["session_token_version"], 4)

    def test_session_revocation_returns_false_when_update_is_not_persisted(self) -> None:
        users = _UsersCollection(None)
        database = SimpleNamespace(users=users)

        with (
            patch.object(
                auth_service,
                "get_user_by_id",
                return_value={"_id": "user-1", "session_token_version": 3},
            ),
            patch.object(auth_service, "get_database", return_value=database),
            patch.object(auth_service, "create_audit_log") as audit_mock,
        ):
            revoked = auth_service.revoke_user_sessions(user_id="user-1")

        self.assertFalse(revoked)
        audit_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
'''


def main() -> None:
    replace_once(AUTH_ROUTE, OLD_LOGOUT, NEW_LOGOUT)
    replace_once(AUTH_SERVICE, OLD_REVOKE_IMPORT, NEW_REVOKE_IMPORT)
    replace_once(AUTH_SERVICE, OLD_REVOKE, NEW_REVOKE)
    TEST_FILE.write_text(TEST_CONTENT, encoding="utf-8")
    print("Applied Step 6 logout revocation integrity remediation.")


if __name__ == "__main__":
    main()
