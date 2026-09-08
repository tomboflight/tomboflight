(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  function revealProtectedShell() {
    const protectedNode = document.querySelector("[data-auth-required]");
    if (protectedNode) protectedNode.style.display = "";
  }

  function showVerificationFailure() {
    revealProtectedShell();
    const title = document.querySelector("[data-portal-section-title]");
    const description = document.querySelector("[data-portal-section-description]");
    const message = document.querySelector("[data-portal-section-message]");
    const grid = document.querySelector("[data-portal-section-grid]");
    const status = document.querySelector("[data-portal-section-status]");

    if (title) title.textContent = "Secure session unavailable";
    if (description) {
      description.textContent =
        "Tomb of Light could not verify this protected customer session.";
    }
    if (message) {
      message.textContent =
        "Return to sign in and try again. No private workspace data has been displayed.";
    }
    if (grid) grid.innerHTML = "";
    if (status) status.innerHTML = "";
  }

  async function resolveProtectedUser() {
    if (window.TOLResolvedUser) {
      revealProtectedShell();
      window.dispatchEvent(
        new CustomEvent("tol:user-resolved", {
          detail: { user: window.TOLResolvedUser },
        }),
      );
      return;
    }

    try {
      const user = await app.apiRequest("/auth/me", { method: "GET" });
      if (!user || typeof user !== "object") {
        throw new Error("Authenticated user response was unavailable.");
      }
      window.TOLResolvedUser = user;
      revealProtectedShell();
      window.dispatchEvent(
        new CustomEvent("tol:user-resolved", { detail: { user } }),
      );
    } catch (_error) {
      showVerificationFailure();
    }
  }

  resolveProtectedUser();
})();
