(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  const INTERNAL_ROLE_KEYS = new Set([
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
  ]);

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function getInternalRoleKey(me) {
    const role = normalizeValue(me && me.role);
    const accessTier = normalizeValue(me && me.access_tier);
    const departmentRole = normalizeValue(me && me.department_role);

    return accessTier || departmentRole || role;
  }

  function isInternalRole(me) {
    const role = normalizeValue(me && me.role);
    const accessTier = normalizeValue(me && me.access_tier);
    const departmentRole = normalizeValue(me && me.department_role);

    return [role, accessTier, departmentRole].some(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });
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

  function getRoleTitle(me) {
    const roleKey = getInternalRoleKey(me);

    if (roleKey === "root_admin") return "Company Root Control";
    if (roleKey === "super_admin") return "Executive Control";
    if (roleKey === "operations_admin" || roleKey === "operations") {
      return "Operations Control";
    }
    if (roleKey === "finance_admin" || roleKey === "finance") {
      return "Finance Control";
    }
    if (roleKey === "marketing_admin" || roleKey === "marketing") {
      return "Marketing Control";
    }
    if (roleKey === "platform_admin" || roleKey === "executive_technology") {
      return "Platform Control";
    }
    return "Internal Control";
  }

  function getRoleCards(me) {
    const roleKey = getInternalRoleKey(me);

    if (["root_admin", "super_admin", "admin"].includes(roleKey)) {
      return [
        card(
          "A",
          "Intake Queue",
          "Review submitted intake records, move them through approval, and provision build records.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
        card(
          "B",
          "Operations Pipeline",
          "Track approved submissions, build readiness, verification flow, and delivery progression.",
          "",
          "",
        ),
        card(
          "C",
          "Finance Oversight",
          "View package, payment, and operational finance checkpoints in the internal workspace.",
          "",
          "",
        ),
        card(
          "D",
          "Platform Control",
          "Use system-level oversight for workflow governance, audit review, and environment control.",
          "",
          "",
        ),
        card(
          "E",
          "Marketing Intelligence",
          "Review demand, conversion, and growth metrics without exposing protected customer lineage data.",
          "",
          "",
        ),
      ];
    }

    if (roleKey === "operations_admin" || roleKey === "operations") {
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
          "Prepare approved submissions for family build, relationship setup, and delivery workflow.",
          "",
          "",
        ),
      ];
    }

    if (roleKey === "platform_admin" || roleKey === "executive_technology") {
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

    if (roleKey === "finance_admin" || roleKey === "finance") {
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

    if (roleKey === "marketing_admin" || roleKey === "marketing") {
      return [
        card(
          "A",
          "Marketing Intelligence",
          "View conversion-level business insight and campaign-facing reporting without exposing private customer lineage records.",
          "",
          "",
        ),
        card(
          "B",
          "Growth Oversight",
          "Prepare future campaign, funnel, and acquisition visibility inside a controlled internal environment.",
          "",
          "",
        ),
      ];
    }

    return [];
  }

  function hideCustomerPanels() {
    document
      .querySelectorAll("[data-dashboard-customer-only]")
      .forEach(function (node) {
        node.style.display = "none";
      });
  }

  function updateHeroForInternal() {
    const eyebrow = document.querySelector("[data-dashboard-hero-eyebrow]");
    const title = document.querySelector("[data-dashboard-hero-title]");
    const status = document.querySelector("[data-dashboard-status]");

    if (eyebrow) eyebrow.textContent = "Internal Operations";
    if (title) title.textContent = "Admin Workspace";
    if (status) {
      status.textContent =
        "You are signed in to the Tomb of Light internal operations portal.";
    }
  }

  function injectAdminPanel(me) {
    const anchor = document.querySelector("[data-admin-portal-anchor]");
    if (!anchor) return;
    if (document.querySelector("[data-admin-tools-panel]")) return;

    if (!isInternalRole(me)) return;

    const panel = document.createElement("div");
    panel.className = "form-panel";
    panel.setAttribute("data-admin-tools-panel", "true");

    const cards = getRoleCards(me).join("");

    panel.innerHTML = `
      <span class="eyebrow">${escapeHtml(getRoleTitle(me))}</span>
      <p class="card-copy" style="margin-bottom: 1.25rem;">
        This internal workspace is reserved for authorized Tomb of Light operational roles and is separate from the public customer workspace.
      </p>
      <div class="grid-3">
        ${cards}
      </div>
    `;

    anchor.prepend(panel);
  }

  async function setupAdminDashboardTools() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    try {
      const me = await app.apiRequest("/auth/me", { method: "GET" });

      if (isInternalRole(me)) {
        hideCustomerPanels();
        updateHeroForInternal();
        injectAdminPanel(me);
      }
    } catch (error) {
      console.error("Failed to load internal dashboard layer:", error);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupAdminDashboardTools();
  });
})();
