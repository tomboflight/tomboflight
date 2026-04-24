import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.dependencies import auth as auth_dependencies
from app.routes import auth as auth_routes


def _request_with_headers(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/auth/logout",
        "raw_path": b"/auth/logout",
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    return Request(scope)


class LogoutRevocationTests(unittest.TestCase):
    def test_logout_revokes_token_sessions(self):
        request = _request_with_headers(
            [(b"authorization", b"Bearer sample-token")]
        )
        response = Response()

        with (
            patch.object(auth_routes, "decode_access_token", return_value={"sub": "user@example.com"}),
            patch.object(auth_routes, "_extract_user_id_from_token", return_value="user-1"),
            patch.object(auth_routes, "revoke_user_sessions") as revoke_mock,
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertTrue(payload["success"])
        revoke_mock.assert_called_once_with(
            user_id="user-1",
            actor_user_id="user-1",
            reason="logout",
        )

    def test_old_token_version_rejected_after_revocation(self):
        request = _request_with_headers()
        with (
            patch.object(auth_dependencies, "_get_token_from_request", return_value=("token", "bearer")),
            patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value={
                    "sub": "user@example.com",
                    "user_id": "user-1",
                    "tv": 0,
                },
            ),
            patch.object(
                auth_dependencies,
                "get_user_by_email",
                return_value={
                    "_id": "user-1",
                    "id": "user-1",
                    "email": "user@example.com",
                    "status": "active",
                    "session_token_version": 1,
                },
            ),
            patch.object(auth_dependencies, "_normalize_user", side_effect=lambda user, _payload: user),
        ):
            with self.assertRaises(HTTPException) as ctx:
                auth_dependencies.get_current_user(request=request, credentials=None)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("revoked", str(ctx.exception.detail).lower())


if __name__ == "__main__":
    unittest.main()
