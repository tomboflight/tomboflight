(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  const INTERNAL_ROLE_KEYS = new Set([
    "super_admin",
    "ceo_master_admin",
    "executive_tech_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
  ]);

  const ROLE_ALIASES = {
    superadmin: "super_admin",
    root_admin: "super_admin",
    platform_admin: "super_admin",
    ceo_super_admin: "ceo_master_admin",
    "ceo-super-admin": "ceo_master_admin",
    ceo_master_admin: "ceo_master_admin",
    "ceo-master-admin": "ceo_master_admin",
    executive_technology: "executive_tech_admin",
    executive_tech_admin: "executive_tech_admin",
    "executive-tech-admin": "executive_tech_admin",
    cto_admin: "executive_tech_admin",
    cfo_admin: "finance_admin",
    cmo_admin: "marketing_admin",
    coo_admin: "operations_admin",
    operations: "operations_admin",
    finance: "finance_admin",
    marketing: "marketing_admin",
  };
  const ROLE_PERMISSION_FALLBACK = {
    ceo_master_admin: [
      "*",
    ],
    super_admin: [
      "*",
    ],
    executive_tech_admin: [
      "admin.access",
      "admin.control.view",
      "admin.intake.review",
      "admin.intake.write",
    ],
    operations_admin: [
      "admin.access",
      "admin.control.view",
      "admin.intake.review",
      "admin.intake.write",
    ],
    finance_admin: [
      "admin.access",
      "admin.control.view",
    ],
    marketing_admin: [
      "admin.access",
      "admin.control.view",
    ],
  };

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function normalizeRole(value) {
    const normalized = normalizeValue(value);
    return ROLE_ALIASES[normalized] || normalized;
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
    const roleCodes = Array.isArray(me && me.role_codes) ? me.role_codes : [];
    return [
      normalizeRole(me && me.access_tier),
      normalizeRole(me && me.department_role),
      normalizeRole(me && me.role),
      ...roleCodes.map(normalizeRole),
    ].filter(Boolean);
  }

  function getInternalRoleKey(me) {
    const signals = getRoleSignals(me);
    const matched = signals.find(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });
    if (matched) return matched;
    if (app && typeof app.isInternalRole === "function" && app.isInternalRole(me)) {
      return "admin";
    }
    return "";
  }

  // Use the canonical check from app.js when available, falling back to the
  // local role-key lookup (which is also needed for role-specific card sets).
  function isInternalRole(me) {
    if (app && typeof app.isInternalRole === "function") {
      return app.isInternalRole(me);
    }
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
    const explicitTitle = String(me?.business_title || "").trim();
    if (explicitTitle) return explicitTitle;

    const roleKey = getInternalRoleKey(me);

    if (roleKey === "ceo_master_admin") return "CEO Master Administrator";
    if (roleKey === "super_admin") return "CEO / Super Admin";
    if (roleKey === "executive_tech_admin") return "Executive Technical Admin";
    if (roleKey === "operations_admin") {
      return "COO";
    }
    if (roleKey === "finance_admin") {
      return "CFO";
    }
    if (roleKey === "marketing_admin") {
      return "CMO";
    }
    return "Internal Control";
  }

  function getPermissionSet(me) {
    const values = Array.isArray(me && me.permissions) ? me.permissions : [];
    const roleSignals = getRoleSignals(me);
    const inferred = roleSignals.flatMap(function (roleCode) {
      return ROLE_PERMISSION_FALLBACK[roleCode] || [];
    });
    return new Set(
      [...values, ...inferred].map(function (value) {
        return normalizeValue(value);
      }),
    );
  }

  function hasPermission(me, requiredCodes) {
    const permissions = getPermissionSet(me);
    if (permissions.has("*")) return true;
    return requiredCodes.some(function (permission) {
      return permissions.has(normalizeValue(permission));
    });
  }

  function getRoleCards(me) {
    const cards = [];
    if (hasPermission(me, ["admin.control.view"])) {
      cards.push(
        card(
          "A",
          "Control Center",
          "Review uploads, mint readiness, orders, entitlements, user records, and audit-visible data based on your assigned permissions.",
          "admin-control-center.html",
          "Open Control Center",
        ),
      );
    }
    if (hasPermission(me, ["admin.intake.review", "admin.intake.write"])) {
      cards.push(
        card(
          "B",
          "Intake Queue",
          "Review submitted intake records, move them through approval, and provision workspaces by lane.",
          "admin-intake-queue.html",
          "Open Intake Queue",
        ),
      );
    }
    if (hasPermission(me, ["admin.access"])) {
      cards.push(
        card(
          "C",
          "Family Manager",
          "Load household and network family builds, add members, and manage lineage relationships.",
          "admin-family-manager.html",
          "Open Family Manager",
        ),
      );
    }
    return cards;
  }

  function applyAdminPortalTheme(me) {
    const body = document.body;
    const dashboard = document.querySelector("[data-dashboard]");
    const roleTitle = getRoleTitle(me);
    const cards = getRoleCards(me);
    const canUseControlCenter = hasPermission(me, ["admin.control.view"]);
    const nextFocus = canUseControlCenter
      ? "Control Center"
      : cards.length
        ? "Intake Queue"
        : "Awaiting published tools";

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
      ["[data-dashboard-identity-node]", "Identity Ready"],
      ["[data-dashboard-package-node]", "Package Scope Ready"],
      ["[data-dashboard-records-node]", "Records Ready"],
    ];

    updates.forEach(function (item) {
      const node = document.querySelector(item[0]);
      if (node) node.textContent = item[1];
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
    const adminToolsButton = document.querySelector("[data-dashboard-admin-tools]");

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

    if (adminToolsButton && adminToolsButton.dataset.workspaceLinkBound !== "true") {
      adminToolsButton.dataset.workspaceLinkBound = "true";
      adminToolsButton.addEventListener("click", function () {
        navigateToWorkspaceArea("#dashboard-admin-tools");
      });
    }
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

  function applyAdminDashboardLayer(me) {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard || !isInternalRole(me)) return;

    applyAdminPortalTheme(me);
    // Customer-only panels are hidden declaratively by CSS using
    // body[data-portal-mode="admin"] — no DOM iteration needed here.
    hideCustomerNavItems();
    hideCustomerBillingLinks();
    showAdminOnlyPanels();
    updateHeroForInternal();
    injectAdminPanel(me);
    enableAdminWorkspaceLinks(me);
  }

  function renderAdminWorkspaceError(operation, message) {
    const statusNode = document.querySelector("[data-dashboard-status]");
    if (statusNode) {
      statusNode.textContent = `${operation} failed. ${message}`;
    }
    const anchor = document.querySelector("[data-admin-portal-anchor]");
    if (!anchor) return;
    const existing = document.querySelector("[data-admin-tools-panel]");
    if (existing) existing.remove();
    const panel = document.createElement("div");
    panel.className = "form-panel portal-admin-panel";
    panel.setAttribute("data-admin-tools-panel", "true");
    panel.innerHTML = `
      <span class="eyebrow">Admin Workspace Error</span>
      <p class="card-copy" style="margin-bottom: 0.85rem;"><strong>Operation:</strong> ${escapeHtml(operation)}</p>
      <p class="card-copy" style="margin-bottom: 1rem;">${escapeHtml(message)}</p>
      <div class="inline-actions"><button class="btn btn-primary" type="button" data-admin-bootstrap-retry>Retry</button></div>
    `;
    anchor.prepend(panel);
    const retryButton = panel.querySelector("[data-admin-bootstrap-retry]");
    if (retryButton instanceof HTMLButtonElement) {
      retryButton.addEventListener("click", async function () {
        retryButton.disabled = true;
        retryButton.textContent = "Retrying...";
        try {
          const me = await app.fetchCurrentUser();
          window.TOLResolvedUser = me;
          applyAdminDashboardLayer(me);
        } catch (error) {
          const safeMessage = String((error && error.message) || "Unable to refresh workspace context.");
          renderAdminWorkspaceError("workspace bootstrap", safeMessage);
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // auth.js fetches /auth/me in setupDashboard() and publishes
    // tol:user-resolved with the result.  We subscribe here instead of
    // making a duplicate network request.
    if (window.TOLResolvedUser) {
      // auth.js resolved before this DOMContentLoaded handler ran.
      try {
        applyAdminDashboardLayer(window.TOLResolvedUser);
      } catch (error) {
        renderAdminWorkspaceError(
          "workspace bootstrap",
          String((error && error.message) || "Unable to initialize internal workspace."),
        );
      }
      return;
    }

    const bootstrapTimeout = window.setTimeout(function () {
      if (!window.TOLResolvedUser) {
        renderAdminWorkspaceError(
          "session resolution",
          "No resolved internal session was detected. Use Retry to reload authorized tools.",
        );
      }
    }, 7000);

    window.addEventListener(
      "tol:user-resolved",
      function (event) {
        window.clearTimeout(bootstrapTimeout);
        try {
          const user = event && event.detail ? event.detail.user : null;
          if (!user) {
            renderAdminWorkspaceError(
              "session resolution",
              "Resolved session payload is missing required user context.",
            );
            return;
          }
          applyAdminDashboardLayer(user);
        } catch (error) {
          renderAdminWorkspaceError(
            "workspace bootstrap",
            String((error && error.message) || "Unable to initialize internal workspace."),
          );
        }
      },
      { once: true },
    );
  });
})();
