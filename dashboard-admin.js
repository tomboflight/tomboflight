(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  function normalizeRole(role) {
    return String(role || "")
      .trim()
      .toLowerCase();
  }

  function injectAdminPanel() {
    const dashboard = document.querySelector("[data-dashboard]");
    const authRequired = document.querySelector("[data-auth-required]");
    if (!dashboard || !authRequired) return;
    if (document.querySelector("[data-admin-tools-panel]")) return;

    const panel = document.createElement("div");
    panel.className = "form-panel";
    panel.setAttribute("data-admin-tools-panel", "true");

    panel.innerHTML = `
      <span class="eyebrow">Admin Tools</span>
      <div class="grid-3">
        <div>
          <div class="card-number">A</div>
          <h3>Intake Queue</h3>
          <p class="card-copy">Review submitted intake records, mark them in review, approve, or reject.</p>
        </div>
        <div>
          <div class="card-number">B</div>
          <h3>Operational Review</h3>
          <p class="card-copy">Use the admin account to control the intake workflow and internal checkpoints.</p>
        </div>
        <div>
          <div class="card-number">C</div>
          <h3>Admin Access</h3>
          <p class="card-copy">This panel only appears when the logged-in account is an admin.</p>
        </div>
      </div>

      <div class="inline-actions" style="margin-top: 1.5rem;">
        <a class="btn btn-primary" href="admin-intake-queue.html">Open Intake Queue</a>
      </div>
    `;

    authRequired.prepend(panel);
  }

  async function setupAdminDashboardTools() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    try {
      const me = await app.apiRequest("/auth/me", { method: "GET" });
      if (normalizeRole(me && me.role) === "admin") {
        injectAdminPanel();
      }
    } catch (error) {
      // ignore for non-admin or session issues already handled elsewhere
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupAdminDashboardTools();
  });
})();
