(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  const packageNames = {
    legacy_snapshot: "Legacy Snapshot",
    legacy_portrait_intro: "Legacy Portrait Intro",
    digital_legacy_portrait: "Digital Legacy Portrait",
    household_foundation: "Household Foundation",
    heirloom_legacy_tree: "Heirloom Legacy Tree",
    legacy_plus: "Legacy Plus",
    family_estate_concierge: "Family Estate Concierge",
    command_structure_network: "Command Structure Network",
  };

  let configurationReady = false;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatDate(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString();
  }

  function setStatus(node, message, state) {
    if (!node) return;
    app.setStatus(node, message, state || "info");
  }

  function userFacingError(error, fallback) {
    const message = String((error && error.message) || "").trim();
    if (message && message.length <= 240) return message;
    return fallback;
  }

  function renderConfiguration(configuration) {
    const node = document.querySelector("[data-admin-event-configuration]");
    const sendButton = document.querySelector("[data-admin-event-send]");
    const required = Array.isArray(configuration && configuration.required_packages)
      ? configuration.required_packages
      : Object.keys(packageNames);
    const configured = new Set(
      Array.isArray(configuration && configuration.configured_packages)
        ? configuration.configured_packages
        : [],
    );
    configurationReady = Boolean(configuration && configuration.configured);

    const labels = required.map(function (code) {
      const label = packageNames[code] || code;
      return `${label}: ${configured.has(code) ? "ready" : "not configured"}`;
    });
    const error = String((configuration && configuration.configuration_error) || "").trim();
    const expiration = formatDate(configuration && configuration.expires_at);
    const summary = configurationReady
      ? `Ready. All ${required.length} package values are protected in the backend. Offer expiration: ${expiration}.`
      : `Sending is blocked until protected deployment configuration is complete. ${error || labels.join(" · ")}`;

    setStatus(node, summary, configurationReady ? "success" : "error");
    if (sendButton) sendButton.disabled = !configurationReady;
  }

  function renderInvitations(items) {
    const list = document.querySelector("[data-admin-event-invitation-list]");
    const empty = document.querySelector("[data-admin-event-empty]");
    if (!list || !empty) return;
    const records = Array.isArray(items) ? items : [];
    empty.hidden = records.length > 0;
    list.innerHTML = records
      .map(function (item) {
        const status = String(item.status || "unknown");
        const revocable = [
          "pending",
          "delivered",
          "delivery_failed",
          "fulfillment_in_progress",
        ].includes(status);
        const revokeControls = revocable
          ? `<label>
              Revocation reason
              <input type="text" maxlength="500" data-admin-event-revoke-reason="${escapeHtml(item.id)}" />
            </label>
            <button class="btn btn-secondary" type="button" data-admin-event-revoke="${escapeHtml(item.id)}">
              Revoke Invitation
            </button>`
          : "";
        return `<article class="card">
          <span class="eyebrow">${escapeHtml(status.replaceAll("_", " "))}</span>
          <h3>${escapeHtml(item.email)}</h3>
          <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package_name || packageNames[item.package_code] || item.package_code)}</p>
          <p class="card-copy"><strong>Invitation email:</strong> ${escapeHtml(item.invitation_delivery_status || "—")}</p>
          <p class="card-copy"><strong>Offer email:</strong> ${escapeHtml(item.promotion_delivery_status || "—")}</p>
          <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
          <p class="card-copy"><strong>Expires:</strong> ${escapeHtml(formatDate(item.expires_at))}</p>
          <div class="form-grid">${revokeControls}</div>
        </article>`;
      })
      .join("");
  }

  async function loadInvitations() {
    const statusNode = document.querySelector("[data-admin-event-page-status]");
    const payload = await app.apiRequest("/bridge-events/paint/invitations", {
      method: "GET",
    });
    renderConfiguration(payload && payload.configuration);
    renderInvitations(payload && payload.items);
    if (statusNode) {
      statusNode.textContent = configurationReady
        ? "Protected invitation delivery is operational."
        : "Protected invitation delivery is blocked pending deployment configuration.";
    }
  }

  async function handleSend(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const statusNode = document.querySelector("[data-admin-event-action-status]");
    const submitButton = document.querySelector("[data-admin-event-send]");
    const data = new FormData(form);
    const payload = {
      email: String(data.get("email") || "").trim().toLowerCase(),
      package_code: String(data.get("package_code") || "").trim(),
      reason: String(data.get("reason") || "").trim(),
      confirmed: data.get("confirmed") === "on",
    };

    if (!configurationReady) {
      setStatus(statusNode, "Protected deployment configuration is incomplete. Sending remains blocked.", "error");
      return;
    }
    if (!form.reportValidity() || !payload.confirmed) return;

    submitButton.disabled = true;
    try {
      setStatus(statusNode, "Sending one protected invitation…", "info");
      const result = await app.apiRequest("/bridge-events/paint/invitations", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      form.reset();
      setStatus(
        statusNode,
        result && result.invitation_created === false
          ? "An active invitation already exists. It was reused and no duplicate email was sent."
          : "Secure invitation sent and audit evidence recorded.",
        "success",
      );
      await loadInvitations();
    } catch (error) {
      setStatus(statusNode, userFacingError(error, "The invitation could not be sent."), "error");
    } finally {
      submitButton.disabled = !configurationReady;
    }
  }

  async function handleRevoke(button) {
    const invitationId = String(button.getAttribute("data-admin-event-revoke") || "");
    const reasonNode = document.querySelector(
      `[data-admin-event-revoke-reason="${CSS.escape(invitationId)}"]`,
    );
    const reason = String((reasonNode && reasonNode.value) || "").trim();
    const statusNode = document.querySelector("[data-admin-event-action-status]");
    if (reason.length < 3) {
      setStatus(statusNode, "Enter a revocation reason of at least 3 characters.", "error");
      if (reasonNode) reasonNode.focus();
      return;
    }
    if (!window.confirm("Revoke this unused private-event invitation? This cannot be undone.")) return;

    button.disabled = true;
    try {
      await app.apiRequest(
        `/bridge-events/paint/invitations/${encodeURIComponent(invitationId)}/revoke`,
        {
          method: "POST",
          body: JSON.stringify({ reason, confirmed: true }),
        },
      );
      setStatus(statusNode, "Invitation revoked and audit evidence recorded.", "success");
      await loadInvitations();
    } catch (error) {
      button.disabled = false;
      setStatus(statusNode, userFacingError(error, "The invitation could not be revoked."), "error");
    }
  }

  async function setupPage() {
    const page = document.querySelector("[data-admin-event-access-page]");
    if (!page) return;
    const token = app.getToken ? app.getToken() : null;
    if (!token) {
      window.location.replace("signin.html");
      return;
    }

    const form = document.querySelector("[data-admin-event-invitation-form]");
    const refresh = document.querySelector("[data-admin-event-refresh]");
    if (form) form.addEventListener("submit", handleSend);
    if (refresh) refresh.addEventListener("click", loadInvitations);
    document.addEventListener("click", function (event) {
      const button = event.target.closest("[data-admin-event-revoke]");
      if (button) handleRevoke(button);
    });

    try {
      await app.apiRequest("/auth/me", { method: "GET" });
      await loadInvitations();
    } catch (error) {
      const pageStatus = document.querySelector("[data-admin-event-page-status]");
      const configNode = document.querySelector("[data-admin-event-configuration]");
      if (pageStatus) pageStatus.textContent = "CEO authorization could not be confirmed.";
      setStatus(configNode, "This surface requires canonical CEO authorization.", "error");
    }
  }

  document.addEventListener("DOMContentLoaded", setupPage);
})();
