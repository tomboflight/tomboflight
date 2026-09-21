from __future__ import annotations

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
