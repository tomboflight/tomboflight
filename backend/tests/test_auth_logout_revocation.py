import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.dependencies import auth as auth_dependencies
from app.routes import auth as auth_routes


def _request_with_headers(
    headers: list[tuple[bytes, bytes]] | None = None,
    *,
    path: str = "/auth/logout",
    client_host: str = "127.0.0.1",
) -> Request:
    scope = {
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

    def test_password_reset_request_uses_request_scoped_rate_key(self):
        request = _request_with_headers(
            path="/auth/password-reset/request",
            client_host="198.51.100.42",
            headers=[(b"x-forwarded-for", b"203.0.113.20")],
        )
        response = Response()
        payload = auth_routes.PasswordResetRequest(email="MixedCase@example.com")

        with (
            patch.object(auth_routes, "_enforce_rate_limit_with_audit") as rate_limit_mock,
            patch.object(
                auth_routes,
                "request_password_reset",
                return_value={"success": True, "message": "If the account exists, a reset link has been sent."},
            ),
        ):
            result = auth_routes.password_reset_request_route(
                payload=payload,
                request=request,
                response=response,
            )

        self.assertTrue(result["success"])
        rate_limit_mock.assert_called_once_with(
            scope="auth_password_reset_request",
            key="198.51.100.42:mixedcase@example.com",
            limit=unittest.mock.ANY,
            window_seconds=unittest.mock.ANY,
            audit_action="password_reset_request_throttled",
        )

    def test_logout_accepts_cookie_authenticated_request_from_allowed_origin(self):
        request = _request_with_headers(
            headers=[
                (b"origin", b"https://tomboflight.com"),
                (b"cookie", b"tol_access_token=cookie-token"),
            ]
        )
        response = Response()

        with (
            patch.object(
                auth_routes,
                "decode_access_token",
                side_effect=lambda token: {"sub": "user@example.com"} if token == "cookie-token" else None,
            ),
            patch.object(
                auth_routes,
                "_extract_user_id_from_token",
                side_effect=lambda token: "cookie-user" if token == "cookie-token" else "",
            ),
            patch.object(auth_routes, "revoke_user_sessions") as revoke_mock,
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertTrue(payload["success"])
        revoke_mock.assert_called_once_with(
            user_id="cookie-user",
            actor_user_id="cookie-user",
            reason="logout",
        )

    def test_logout_rejects_cookie_authenticated_request_from_foreign_origin(self):
        request = _request_with_headers(
            headers=[
                (b"origin", b"https://evil.example"),
                (b"cookie", b"tol_access_token=cookie-token"),
            ]
        )
        response = Response()

        with patch.object(auth_routes, "revoke_user_sessions") as revoke_mock:
            with self.assertRaises(HTTPException) as ctx:
                auth_routes.logout(request=request, response=response)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("origin is not allowed", str(ctx.exception.detail).lower())
        revoke_mock.assert_not_called()

    def test_logout_accepts_bearer_authenticated_request_without_origin(self):
        request = _request_with_headers(
            [(b"authorization", b"Bearer bearer-token")]
        )
        response = Response()

        with (
            patch.object(
                auth_routes,
                "decode_access_token",
                side_effect=lambda token: {"sub": "user@example.com"} if token == "bearer-token" else None,
            ),
            patch.object(
                auth_routes,
                "_extract_user_id_from_token",
                side_effect=lambda token: "bearer-user" if token == "bearer-token" else "",
            ),
            patch.object(auth_routes, "revoke_user_sessions") as revoke_mock,
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertTrue(payload["success"])
        revoke_mock.assert_called_once_with(
            user_id="bearer-user",
            actor_user_id="bearer-user",
            reason="logout",
        )

    def test_logout_prefers_valid_bearer_over_stale_cookie(self):
        request = _request_with_headers(
            headers=[
                (b"authorization", b"Bearer bearer-token"),
                (b"cookie", b"tol_access_token=stale-cookie-token"),
            ]
        )
        response = Response()

        with (
            patch.object(
                auth_routes,
                "decode_access_token",
                side_effect=lambda token: (
                    {"sub": "user@example.com"} if token == "bearer-token" else None
                ),
            ),
            patch.object(
                auth_routes,
                "_extract_user_id_from_token",
                side_effect=lambda token: "bearer-user" if token == "bearer-token" else "",
            ),
            patch.object(auth_routes, "revoke_user_sessions") as revoke_mock,
        ):
            payload = auth_routes.logout(request=request, response=response)

        self.assertTrue(payload["success"])
        revoke_mock.assert_called_once_with(
            user_id="bearer-user",
            actor_user_id="bearer-user",
            reason="logout",
        )


if __name__ == "__main__":
    unittest.main()
