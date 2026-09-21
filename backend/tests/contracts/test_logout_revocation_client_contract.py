from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_web_logout_does_not_suppress_revocation_failures() -> None:
    app_source = _read("app.js")
    assert "Ignore – local session already cleared above" not in app_source
    assert "result.server_revocation_confirmed === false" in app_source


def test_cookie_only_logout_preserves_csrf_before_local_clear() -> None:
    app_source = _read("app.js")
    capture_index = app_source.index("const capturedCsrfToken")
    clear_index = app_source.index("clearSession();", capture_index)
    request_index = app_source.index('apiRequest("/auth/logout"', clear_index)
    assert capture_index < clear_index < request_index
    assert '"X-CSRF-Token": capturedCsrfToken' in app_source


def test_web_logout_surfaces_unconfirmed_revocation_after_redirect() -> None:
    auth_source = _read("auth.js")
    assert 'signin.html?logout_warning=1' in auth_source
    assert "server-side session revocation could not be confirmed" in auth_source
    assert 'resolve("timeout")' in auth_source


def test_link_keys_does_not_install_a_duplicate_logout_handler() -> None:
    link_keys_source = _read("link-keys.js")
    assert 'document.querySelectorAll("[data-logout-btn]")' not in link_keys_source
    assert "Logout is handled once by auth.js" in link_keys_source


def test_mobile_logout_warns_before_returning_to_sign_in() -> None:
    settings_source = _read("mobile/app/(app)/settings.tsx")
    assert "Signed Out Locally" in settings_source
    assert "server-side session revocation could not be confirmed" in settings_source
    assert "serverRevocationConfirmed" in settings_source
