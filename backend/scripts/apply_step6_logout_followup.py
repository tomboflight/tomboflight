from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "app.js"
LINK_KEYS_JS = ROOT / "link-keys.js"
CONTRACT_TEST = ROOT / "backend" / "tests" / "contracts" / "test_logout_revocation_client_contract.py"


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one replacement target in {path}; found {count}.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


OLD_APP_LOGOUT = r'''  async function logoutUser(options = {}) {
    const capturedToken = String(options.token || getToken() || "").trim();
    const maxWaitMs =
      Number.isFinite(options.maxWaitMs) && options.maxWaitMs > 0
        ? options.maxWaitMs
        : LOGOUT_REQUEST_MAX_WAIT_MS;
    // Clear local state immediately, but do not suppress failure to revoke the
    // server session. Callers must distinguish local sign-out from confirmed
    // server-side revocation so users receive accurate security status.
    clearSession();
    const result = await apiRequest("/auth/logout", {
      method: "POST",
      headers: capturedToken
        ? {
            Authorization: `Bearer ${capturedToken}`,
          }
        : {},
      totalTimeoutMs: maxWaitMs,
    });
'''

NEW_APP_LOGOUT = r'''  async function logoutUser(options = {}) {
    const capturedToken = String(options.token || getToken() || "").trim();
    const capturedCsrfToken = String(
      options.csrfToken || getCsrfToken() || "",
    ).trim();
    const maxWaitMs =
      Number.isFinite(options.maxWaitMs) && options.maxWaitMs > 0
        ? options.maxWaitMs
        : LOGOUT_REQUEST_MAX_WAIT_MS;
    // Clear local state immediately, but preserve the current credentials for
    // the logout request. This keeps cookie-only sessions CSRF-valid while the
    // caller still receives immediate local sign-out behavior.
    clearSession();
    const result = await apiRequest("/auth/logout", {
      method: "POST",
      headers: {
        ...(capturedToken
          ? {
              Authorization: `Bearer ${capturedToken}`,
            }
          : {}),
        ...(capturedCsrfToken
          ? {
              "X-CSRF-Token": capturedCsrfToken,
            }
          : {}),
      },
      totalTimeoutMs: maxWaitMs,
    });
'''

OLD_LINK_KEYS_LOGOUT = r'''    document.querySelectorAll("[data-logout-btn]").forEach(function (button) {
      button.addEventListener("click", async function () {
        let serverRevocationConfirmed = false;
        try {
          if (app.logoutUser) {
            await app.logoutUser();
            serverRevocationConfirmed = true;
          } else {
            app.clearSession();
          }
        } catch (_error) {
          app.clearSession();
        }

        window.location.href = serverRevocationConfirmed
          ? "signin.html"
          : "signin.html?logout_warning=1";
      });
    });
'''

NEW_LINK_KEYS_LOGOUT = r'''    // Logout is handled once by auth.js through its delegated
    // [data-logout-btn] listener. A second page-local listener would issue a
    // duplicate revocation request after local credentials have been cleared.
'''

OLD_CONTRACT = '''def test_web_logout_does_not_suppress_revocation_failures() -> None:
    app_source = _read("app.js")
    assert "Ignore – local session already cleared above" not in app_source
    assert "result.server_revocation_confirmed === false" in app_source


def test_web_logout_surfaces_unconfirmed_revocation_after_redirect() -> None:
'''

NEW_CONTRACT = '''def test_web_logout_does_not_suppress_revocation_failures() -> None:
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
'''

OLD_LINK_CONTRACT = '''def test_link_keys_logout_preserves_revocation_warning() -> None:
    link_keys_source = _read("link-keys.js")
    assert 'signin.html?logout_warning=1' in link_keys_source
    assert "serverRevocationConfirmed" in link_keys_source
'''

NEW_LINK_CONTRACT = '''def test_link_keys_does_not_install_a_duplicate_logout_handler() -> None:
    link_keys_source = _read("link-keys.js")
    assert 'document.querySelectorAll("[data-logout-btn]")' not in link_keys_source
    assert "Logout is handled once by auth.js" in link_keys_source
'''


def main() -> None:
    replace_once(APP_JS, OLD_APP_LOGOUT, NEW_APP_LOGOUT)
    replace_once(LINK_KEYS_JS, OLD_LINK_KEYS_LOGOUT, NEW_LINK_KEYS_LOGOUT)
    replace_once(CONTRACT_TEST, OLD_CONTRACT, NEW_CONTRACT)
    replace_once(CONTRACT_TEST, OLD_LINK_CONTRACT, NEW_LINK_CONTRACT)
    print("Applied Step 6 logout CSRF and duplicate-handler follow-up.")


if __name__ == "__main__":
    main()
