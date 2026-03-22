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

  function isInternalRole(role) {
    return [
      "admin",
      "super_admin",
      "platform_admin",
      "operations_admin",
      "finance_admin",
      "marketing_admin",
    ].includes(normalizeRole(role));
  }

  function getRoleTitle(role) {
    const normalized = normalizeRole(role);

    if (normalized === "super_admin") return "Super Admin Control";
    if (normalized === "platform_admin") return "Platform Admin Control";
    if (normalized === "operations_admin") return "Operations Admin Control";
    if (normalized === "finance_admin") return "Finance Admin Control";
    if (normalized === "marketing_admin") return "Marketing Admin Control";
    if (normalized === "admin") return "Admin Control";
    return "Internal Control";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function card(number, title, copy, href, buttonText) {
    const action =
      href && buttonText
        ? `<div class="inline-actions" style="margin-top: 1rem;">
           <a class="btn btn-primary" href="${escapeHtml(href)}">${escapeHtml(buttonText)}</a>
         </div>`
        : `<div class="inline-actions" style="margin-top: 1rem;">
           <span class="btn btn-secondary" aria-disabled="true">Coming Next</span>
         </div>`;

    return `
      <div class="family-record-card">
        <div class="card-number">${escapeHtml(number)}</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${escapeHtml(copy)}</p>
        ${action}
      </div>
    `;
  }

  function getRoleCards(role) {
    const normalized = normalizeRole(role);

    if (normalized === "super_admin" || normalized === "admin") {
      return [
        card(
          "A",
          "Intake Queue",
          "Review submitted intake records, mark them in review, approve, reject, and control onboarding flow.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
        card(
          "B",
          "Operations Pipeline",
          "Track approved submissions, production readiness, verification flow, and delivery progression.",
          "",
          "",
        ),
        card(
          "C",
          "Finance Oversight",
          "View package status, customer payment truth, operational finance checkpoints, and reporting visibility.",
          "",
          "",
        ),
        card(
          "D",
          "Platform Control",
          "Use system-level oversight for workflow governance, audit review, and high-trust administrative control.",
          "",
          "",
        ),
        card(
          "E",
          "Marketing Intelligence",
          "Review top-level demand, conversion, and funnel activity without exposing protected family records.",
          "",
          "",
        ),
      ];
    }

    if (normalized === "platform_admin") {
      return [
        card(
          "A",
          "Intake Queue",
          "Access internal onboarding review workflow and troubleshoot intake state transitions.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
        card(
          "B",
          "Platform Tools",
          "Platform health, operational debugging, and system-level workflow support.",
          "",
          "",
        ),
      ];
    }

    if (normalized === "operations_admin") {
      return [
        card(
          "A",
          "Intake Queue",
          "Review submitted onboarding records and move customer submissions through the review process.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
        card(
          "B",
          "Operations Review",
          "Prepare verified submissions for the family build, relationship setup, and delivery workflow.",
          "",
          "",
        ),
      ];
    }

    if (normalized === "finance_admin") {
      return [
        card(
          "A",
          "Finance Oversight",
          "Track orders, package activation, payment truth, and customer billing checkpoints.",
          "",
          "",
        ),
        card(
          "B",
          "Revenue View",
          "Use finance-specific reporting without exposing protected family lineage content.",
          "",
          "",
        ),
      ];
    }

    if (normalized === "marketing_admin") {
      return [
        card(
          "A",
          "Marketing Intelligence",
          "View conversion-level business insights and campaign-facing reporting without exposing private customer lineage records.",
          "",
          "",
        ),
        card(
          "B",
          "Growth Oversight",
          "Prepare future campaign, funnel, and acquisition visibility inside a controlled admin environment.",
          "",
          "",
        ),
      ];
    }

    return [];
  }

  function injectAdminPanel(me) {
    const authRequired = document.querySelector("[data-auth-required]");
    if (!authRequired) return;
    if (document.querySelector("[data-admin-tools-panel]")) return;

    const role = normalizeRole(me && me.role);
    if (!isInternalRole(role)) return;

    const panel = document.createElement("div");
    panel.className = "form-panel";
    panel.setAttribute("data-admin-tools-panel", "true");

    const cards = getRoleCards(role).join("");

    panel.innerHTML = `
      <span class="eyebrow">${escapeHtml(getRoleTitle(role))}</span>
      <p class="card-copy" style="margin-bottom: 1.25rem;">
        This internal control layer is visible only to authorized Tomb of Light operational roles.
      </p>
      <div class="grid-3">
        ${cards}
      </div>
    `;

    authRequired.prepend(panel);
  }

  async function setupAdminDashboardTools() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    try {
      const me = await app.apiRequest("/auth/me", { method: "GET" });
      injectAdminPanel(me);
    } catch (error) {
      // session handling already exists elsewhere
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupAdminDashboardTools();
  });
})();
