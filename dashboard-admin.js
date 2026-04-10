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

  function getRoleSignals(me) {
    return [
      normalizeValue(me && me.role),
      normalizeValue(me && me.access_tier),
      normalizeValue(me && me.department_role),
    ].filter(Boolean);
  }

  function getInternalRoleKey(me) {
    const signals = getRoleSignals(me);
    return (
      signals.find(function (value) {
        return INTERNAL_ROLE_KEYS.has(value);
      }) || ""
    );
  }

  function isInternalRole(me) {
    return Boolean(getInternalRoleKey(me));
  }

  function card(number, title, copy, href, buttonText) {
    return `
      <div class="family-record-card">
        <div class="card-number">${escapeHtml(number)}</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${escapeHtml(copy)}</p>
        <div class="inline-actions" style="margin-top: 1rem;">
          <a class="btn btn-primary" href="${escapeHtml(href)}">${escapeHtml(buttonText)}</a>
        </div>
      </div>
    `;
  }

  function getRoleTitle(me) {
    const roleKey = getInternalRoleKey(me);

    if (roleKey === "root_admin") return "Company Root Control";
    if (roleKey === "super_admin") return "Executive Control";
    if (roleKey === "admin") return "Administrative Control";
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

    if (
      [
        "root_admin",
        "super_admin",
        "admin",
        "platform_admin",
        "executive_technology",
      ].includes(roleKey)
    ) {
      return [
        card(
          "A",
          "Control Center",
          "Review uploads, oversee mint records, inspect orders, entitlements, user records, and audit history from one internal workspace.",
          "admin-control-center.html",
          "Open Control Center",
        ),
        card(
          "B",
          "Intake Queue",
          "Review submitted intake records, move them through approval, and provision package workspaces correctly by lane.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
        card(
          "C",
          "Family Manager",
          "Load real household and network family builds, add members, and manage lineage relationships in the live platform.",
          "admin-family-manager.html",
          "Open Family Manager",
        ),
      ];
    }

    if (
      [
        "operations_admin",
        "operations",
      ].includes(roleKey)
    ) {
      return [
        card(
          "A",
          "Control Center",
          "Review uploads, monitor onchain anchor readiness, and troubleshoot provisioned workspaces from one operations console.",
          "admin-control-center.html",
          "Open Control Center",
        ),
        card(
          "B",
          "Intake Queue",
          "Review submitted intake records, move them through approval, and provision package workspaces correctly by lane.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
        card(
          "C",
          "Family Manager",
          "Load real household and network family builds, add members, and manage lineage relationships in the live platform.",
          "admin-family-manager.html",
          "Open Family Manager",
        ),
      ];
    }

    if (["finance_admin", "finance"].includes(roleKey)) {
      return [
        card(
          "A",
          "Control Center",
          "Review order records, project entitlements, mint status, and audit events tied to protected package delivery.",
          "admin-control-center.html",
          "Open Control Center",
        ),
      ];
    }

    if (["marketing_admin", "marketing"].includes(roleKey)) {
      return [
        card(
          "A",
          "Control Center",
          "Review users, projects, and audit-visible customer records published to your internal marketing scope.",
          "admin-control-center.html",
          "Open Control Center",
        ),
      ];
    }

    return [];
  }

  function applyAdminPortalTheme(me) {
    const body = document.body;
    const dashboard = document.querySelector("[data-dashboard]");
    const roleTitle = getRoleTitle(me);
    const cards = getRoleCards(me);
    const nextFocus = cards.length ? "Intake Queue" : "Awaiting published tools";

    if (body) {
      body.classList.add("portal-dashboard-body", "portal-admin-mode");
      body.dataset.portalMode = "admin";
      body.dataset.portalLane = "admin";
    }

    if (dashboard) {
      dashboard.setAttribute("data-portal-mode", "admin");
      dashboard.setAttribute("data-portal-lane", "admin");
    }

    const updates = [
      ["[data-dashboard-lane-chip]", "Admin Lane"],
      ["[data-dashboard-package-chip]", roleTitle],
      ["[data-dashboard-scope-chip]", "Authorized Tools"],
      ["[data-dashboard-core-label]", "Operations Core"],
      ["[data-dashboard-core-subtitle]", "Secure Internal Access"],
      ["[data-dashboard-lane-summary]", "Internal Operations"],
      [
        "[data-dashboard-lane-description]",
        "This environment exposes internal Tomb of Light workflow tools without mixing in customer package panels.",
      ],
      ["[data-dashboard-package-display]", roleTitle],
      ["[data-dashboard-next-focus]", nextFocus],
    ];

    updates.forEach(function (item) {
      const node = document.querySelector(item[0]);
      if (node) node.textContent = item[1];
    });
  }

  function hideCustomerPanels() {
    document
      .querySelectorAll("[data-dashboard-customer-only]")
      .forEach(function (node) {
        node.style.display = "none";
      });
  }

  function hideCustomerNavItems() {
    [
      'a[href="intake-review.html"]',
      'a[href="verification-upload.html"]',
      'a[href="link-keys.html"]',
      'a[href="tree-view.html"]',
      'a[href="lineage-certificate.html"]',
    ].forEach(function (selector) {
      document
        .querySelectorAll(`.site-nav ${selector}`)
        .forEach(function (node) {
          node.style.display = "none";
        });
    });
  }

  function hideCustomerBillingLinks() {
    document
      .querySelectorAll('[data-dashboard-billing-link]')
      .forEach(function (node) {
        node.style.display = "none";
      });
  }

  function showAdminOnlyPanels() {
    document
      .querySelectorAll("[data-dashboard-admin-only]")
      .forEach(function (node) {
        node.style.display = "";
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

  function navigateToWorkspaceArea(href) {
    if (!href) return;

    if (href.startsWith("#")) {
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      window.history.replaceState({}, "", href);
      return;
    }

    window.location.href = href;
  }

  function makeWorkspaceLink(selector, href, label) {
    const node = document.querySelector(selector);
    if (!node) return;

    node.setAttribute("data-admin-workspace-link", "true");
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "link");
    node.setAttribute("aria-label", label);
    node.dataset.workspaceHref = href;

    if (node.dataset.workspaceLinkBound === "true") {
      return;
    }

    node.dataset.workspaceLinkBound = "true";
    node.addEventListener("click", function () {
      navigateToWorkspaceArea(node.dataset.workspaceHref || "");
    });
    node.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }

      event.preventDefault();
      navigateToWorkspaceArea(node.dataset.workspaceHref || "");
    });
  }

  function enableAdminWorkspaceLinks(me) {
    const roleTitle = getRoleTitle(me);

    makeWorkspaceLink(
      "[data-dashboard-lane-chip]",
      "#dashboard-admin-workspace",
      "Open admin workspace",
    );
    makeWorkspaceLink(
      "[data-dashboard-package-chip]",
      "#dashboard-active-package",
      `Open ${roleTitle}`,
    );
    makeWorkspaceLink(
      "[data-dashboard-scope-chip]",
      "#dashboard-admin-tools",
      "Open authorized tools",
    );
    makeWorkspaceLink(
      "[data-dashboard-identity-node]",
      "#dashboard-account-profile",
      "Open identity workspace area",
    );
    makeWorkspaceLink(
      "[data-dashboard-package-node]",
      "#dashboard-active-package",
      "Open package workspace area",
    );
    makeWorkspaceLink(
      "[data-dashboard-records-node]",
      "admin-intake-queue.html",
      "Open records workspace area",
    );
  }

  function injectAdminPanel(me) {
    const anchor = document.querySelector("[data-admin-portal-anchor]");
    if (!anchor) return;

    const existing = document.querySelector("[data-admin-tools-panel]");
    if (existing) existing.remove();

    if (!isInternalRole(me)) return;

    const panel = document.createElement("div");
    panel.className = "form-panel portal-admin-panel";
    panel.setAttribute("data-admin-tools-panel", "true");

    const cards = getRoleCards(me);
    const cardsMarkup = cards.length
      ? `<div class="grid-3">${cards.join("")}</div>`
      : `<p class="card-copy">No dedicated browser-based tools are currently published for this internal role.</p>`;

    panel.innerHTML = `
      <span class="eyebrow">${escapeHtml(getRoleTitle(me))}</span>
      <p class="card-copy" style="margin-bottom: 1.25rem;">
        This internal workspace is reserved for authorized Tomb of Light operational roles and is separate from the public customer workspace.
      </p>
      ${cardsMarkup}
    `;

    anchor.prepend(panel);
  }

  async function setupAdminDashboardTools() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    try {
      const me = await app.apiRequest("/auth/me", { method: "GET" });

      if (isInternalRole(me)) {
        applyAdminPortalTheme(me);
        hideCustomerPanels();
        hideCustomerNavItems();
        hideCustomerBillingLinks();
        showAdminOnlyPanels();
        updateHeroForInternal();
        injectAdminPanel(me);
        enableAdminWorkspaceLinks(me);
      }
    } catch (error) {
      console.error("Failed to load internal dashboard layer:", error);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupAdminDashboardTools();
  });
})();
