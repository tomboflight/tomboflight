(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  const INVITE_TOKEN_KEY = "tol_bridge_paint_invite_token";

  function tokenFromHash() {
    const rawHash = String(window.location.hash || "").replace(/^#/, "");
    if (!rawHash) return "";
    const params = new URLSearchParams(rawHash);
    return String(params.get("invite") || "").trim();
  }

  function saveInviteToken(token) {
    try {
      if (token) window.sessionStorage.setItem(INVITE_TOKEN_KEY, token);
    } catch (_error) {
      // The in-memory value still supports this page session.
    }
  }

  function storedInviteToken() {
    try {
      return String(window.sessionStorage.getItem(INVITE_TOKEN_KEY) || "").trim();
    } catch (_error) {
      return "";
    }
  }

  function clearInviteToken() {
    try {
      window.sessionStorage.removeItem(INVITE_TOKEN_KEY);
    } catch (_error) {
      // Nothing else is required when browser storage is unavailable.
    }
  }

  function removeTokenFromAddressBar() {
    if (!window.location.hash) return;
    window.history.replaceState(
      {},
      document.title,
      `${window.location.pathname}${window.location.search}`,
    );
  }

  function setupSecureEventAccess() {
    const form = document.querySelector("[data-bridge-paint-access-form]");
    const statusNode = document.querySelector("[data-bridge-paint-access-status]");
    const submitButton = document.querySelector("[data-bridge-paint-access-submit]");
    if (!form || !statusNode || !submitButton) return;

    const hashToken = tokenFromHash();
    if (hashToken) saveInviteToken(hashToken);
    removeTokenFromAddressBar();
    let accessToken = hashToken || storedInviteToken();

    if (!accessToken) {
      submitButton.disabled = true;
      app.setStatus(
        statusNode,
        "Open the one-time link from your invitation email. Contact the event organizer if you need a new invitation.",
        "info",
      );
    } else {
      app.setStatus(
        statusNode,
        "Secure invitation detected. Enter the exact email address that received it.",
        "success",
      );
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const formData = new FormData(form);
      const email = String(formData.get("email") || "").trim().toLowerCase();
      if (!email || !accessToken) {
        app.setStatus(
          statusNode,
          "A valid invitation link and invited email address are required.",
          "error",
        );
        return;
      }

      submitButton.disabled = true;
      try {
        app.setStatus(statusNode, "Verifying private event access…", "info");
        const payload = await app.apiRequest("/bridge-events/paint/access/request", {
          method: "POST",
          body: JSON.stringify({ email, access_token: accessToken }),
        });
        clearInviteToken();
        accessToken = "";
        form.reset();
        app.setStatus(
          statusNode,
          String(
            (payload && payload.message) ||
              "If the invitation is valid, the private offer will be sent to the invited mailbox.",
          ),
          "success",
        );
      } catch (_error) {
        submitButton.disabled = false;
        app.setStatus(
          statusNode,
          "Secure event access is temporarily unavailable. No invitation was consumed. Try again.",
          "error",
        );
      }
    });
  }

  document.addEventListener("DOMContentLoaded", setupSecureEventAccess);
})();
