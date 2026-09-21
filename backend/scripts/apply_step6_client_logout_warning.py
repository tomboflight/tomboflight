from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one replacement target in {path}; found {count}.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


APP_JS = ROOT / "app.js"
AUTH_JS = ROOT / "auth.js"
LINK_KEYS_JS = ROOT / "link-keys.js"
MOBILE_SETTINGS = ROOT / "mobile" / "app" / "(app)" / "settings.tsx"
BROWSER_TEST = ROOT / "browser-tests" / "customer-account-phase21.spec.mjs"
CONTRACT_TEST = ROOT / "backend" / "tests" / "contracts" / "test_logout_revocation_client_contract.py"


OLD_APP_LOGOUT = r'''  async function logoutUser(options = {}) {
    const capturedToken = String(options.token || getToken() || "").trim();
    const maxWaitMs =
      Number.isFinite(options.maxWaitMs) && options.maxWaitMs > 0
        ? options.maxWaitMs
        : LOGOUT_REQUEST_MAX_WAIT_MS;
    // Clear the local session immediately so the caller is not blocked on the
    // network round-trip.  The backend call is best-effort: we still attempt it
    // so the server-side httpOnly auth cookie is revoked, but a slow or failing
    // backend cannot prevent the user from being logged out locally.
    clearSession();
    try {
      await apiRequest("/auth/logout", {
        method: "POST",
        headers: capturedToken
          ? {
              Authorization: `Bearer ${capturedToken}`,
            }
          : {},
        totalTimeoutMs: maxWaitMs,
      });
    } catch (_error) {
      // Ignore – local session already cleared above.
    }
  }
'''

NEW_APP_LOGOUT = r'''  async function logoutUser(options = {}) {
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

    if (
      result &&
      typeof result === "object" &&
      result.server_revocation_confirmed === false
    ) {
      throw new Error(
        String(result.message || "").trim() ||
          "This device was signed out locally, but server-side session revocation could not be confirmed.",
      );
    }

    return result;
  }
'''

OLD_SIGNIN_STATUS = r'''    const statusNode = document.querySelector("[data-signin-status]");
    const submitBtn = form.querySelector("[data-submit-btn]");
'''

NEW_SIGNIN_STATUS = r'''    const statusNode = document.querySelector("[data-signin-status]");
    const logoutWarning =
      new URLSearchParams(window.location.search).get("logout_warning") === "1";
    if (logoutWarning) {
      app.setStatus(
        statusNode,
        "This device was signed out, but server-side session revocation could not be confirmed. Reset your password if another device may still have access.",
        "error",
      );
      try {
        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete("logout_warning");
        window.history.replaceState(
          {},
          document.title,
          `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`,
        );
      } catch (_error) {
        // The warning remains visible even when URL cleanup is unavailable.
      }
    }
    const submitBtn = form.querySelector("[data-submit-btn]");
'''

OLD_AUTH_LOGOUT = r'''      const logoutTask =
        app && typeof app.logoutUser === "function"
          ? app.logoutUser({ maxWaitMs: LOGOUT_REDIRECT_MAX_WAIT_MS })
          : Promise.resolve().then(function () {
              if (app && typeof app.clearSession === "function") {
                app.clearSession();
              }
            });

      await Promise.race([
        logoutTask.catch(function () {
          if (app && typeof app.clearSession === "function") {
            app.clearSession();
          }
        }),
        new Promise(function (resolve) {
          window.setTimeout(resolve, LOGOUT_REDIRECT_MAX_WAIT_MS);
        }),
      ]);

      window.location.href = "signin.html";
'''

NEW_AUTH_LOGOUT = r'''      const logoutTask =
        app && typeof app.logoutUser === "function"
          ? app
              .logoutUser({ maxWaitMs: LOGOUT_REDIRECT_MAX_WAIT_MS })
              .then(function () {
                return "confirmed";
              })
          : Promise.resolve().then(function () {
              if (app && typeof app.clearSession === "function") {
                app.clearSession();
              }
              return "unconfirmed";
            });

      const logoutOutcome = await Promise.race([
        logoutTask.catch(function () {
          if (app && typeof app.clearSession === "function") {
            app.clearSession();
          }
          return "failed";
        }),
        new Promise(function (resolve) {
          window.setTimeout(function () {
            resolve("timeout");
          }, LOGOUT_REDIRECT_MAX_WAIT_MS);
        }),
      ]);

      window.location.href =
        logoutOutcome === "confirmed"
          ? "signin.html"
          : "signin.html?logout_warning=1";
'''

OLD_LINK_KEYS_LOGOUT = r'''    document.querySelectorAll("[data-logout-btn]").forEach(function (button) {
      button.addEventListener("click", async function () {
        try {
          if (app.logoutUser) {
            await app.logoutUser();
          } else {
            app.clearSession();
          }
        } catch (error) {
          app.clearSession();
        }

        window.location.href = "signin.html";
      });
    });
'''

NEW_LINK_KEYS_LOGOUT = r'''    document.querySelectorAll("[data-logout-btn]").forEach(function (button) {
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

OLD_MOBILE_LOGOUT = r'''          void (async () => {
            try {
              await signOut();
            } finally {
              if (mountedRef.current) {
                setIsSigningOut(false);
              }
              router.replace('/(auth)/sign-in');
            }
          })();
'''

NEW_MOBILE_LOGOUT = r'''          void (async () => {
            let serverRevocationConfirmed = true;
            try {
              await signOut();
            } catch {
              serverRevocationConfirmed = false;
            } finally {
              if (mountedRef.current) {
                setIsSigningOut(false);
              }
            }

            if (!serverRevocationConfirmed) {
              Alert.alert(
                'Signed Out Locally',
                'This device was signed out, but server-side session revocation could not be confirmed. Reset your password if another device may still have access.',
                [
                  {
                    text: 'Continue',
                    onPress: () => router.replace('/(auth)/sign-in')
                  }
                ],
                { cancelable: false }
              );
              return;
            }

            router.replace('/(auth)/sign-in');
          })();
'''

OLD_BROWSER_ASSERTION = r'''    expect(elapsedMs).toBeGreaterThanOrEqual(8_500);
    expect(elapsedMs).toBeLessThan(10_500);
  });
});
'''

NEW_BROWSER_ASSERTION = r'''    expect(elapsedMs).toBeGreaterThanOrEqual(8_500);
    expect(elapsedMs).toBeLessThan(10_500);
    await expect(page.locator("[data-signin-status]")).toContainText(
      "server-side session revocation could not be confirmed",
    );
  });
});
'''

CONTRACT_CONTENT = '''from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_web_logout_does_not_suppress_revocation_failures() -> None:
    app_source = _read("app.js")
    assert "Ignore – local session already cleared above" not in app_source
    assert "result.server_revocation_confirmed === false" in app_source


def test_web_logout_surfaces_unconfirmed_revocation_after_redirect() -> None:
    auth_source = _read("auth.js")
    assert 'signin.html?logout_warning=1' in auth_source
    assert "server-side session revocation could not be confirmed" in auth_source
    assert 'resolve("timeout")' in auth_source


def test_link_keys_logout_preserves_revocation_warning() -> None:
    link_keys_source = _read("link-keys.js")
    assert 'signin.html?logout_warning=1' in link_keys_source
    assert "serverRevocationConfirmed" in link_keys_source


def test_mobile_logout_warns_before_returning_to_sign_in() -> None:
    settings_source = _read("mobile/app/(app)/settings.tsx")
    assert "Signed Out Locally" in settings_source
    assert "server-side session revocation could not be confirmed" in settings_source
    assert "serverRevocationConfirmed" in settings_source
'''


def main() -> None:
    replace_once(APP_JS, OLD_APP_LOGOUT, NEW_APP_LOGOUT)
    replace_once(AUTH_JS, OLD_SIGNIN_STATUS, NEW_SIGNIN_STATUS)
    replace_once(AUTH_JS, OLD_AUTH_LOGOUT, NEW_AUTH_LOGOUT)
    replace_once(LINK_KEYS_JS, OLD_LINK_KEYS_LOGOUT, NEW_LINK_KEYS_LOGOUT)
    replace_once(MOBILE_SETTINGS, OLD_MOBILE_LOGOUT, NEW_MOBILE_LOGOUT)
    replace_once(BROWSER_TEST, OLD_BROWSER_ASSERTION, NEW_BROWSER_ASSERTION)
    CONTRACT_TEST.write_text(CONTRACT_CONTENT, encoding="utf-8")
    print("Applied client logout revocation warning remediation.")


if __name__ == "__main__":
    main()
