(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const summaryPanel = document.querySelector("[data-customer-account-summary]");
  const activityPanel = document.querySelector("[data-security-activity-panel]");

  if (!app || (!summaryPanel && !activityPanel)) return;

  const ROLE_LABELS = {
    billing_owner: "Billing Owner",
    co_owner: "Co-Owner",
    family_manager: "Family Manager",
    contributor: "Contributor",
    viewer: "Viewer",
    minor_viewer: "Minor Viewer",
    linked_relative: "Linked Relative",
    legacy_executor: "Legacy Executor",
    super_admin: "Super Administrator",
    ceo: "CEO",
    cto: "CTO",
    coo: "COO",
    cfo: "CFO",
    admin: "Administrator",
  };

  function text(value) {
    return String(value || "").trim();
  }

  function firstText() {
    for (let index = 0; index < arguments.length; index += 1) {
      const value = text(arguments[index]);
      if (value) return value;
    }
    return "";
  }

  function setText(selector, value, fallback) {
    const node = document.querySelector(selector);
    if (!node) return;
    node.textContent = text(value) || fallback || "Not available";
  }

  function setLabel(selector, value) {
    const node = document.querySelector(selector);
    const container = node && node.parentElement;
    const label = container && container.querySelector(".eyebrow");
    if (label) label.textContent = value;
  }

  function friendlyStatus(value) {
    const normalized = text(value).toLowerCase();
    if (!normalized) return "Not available";
    return normalized
      .replaceAll("_", " ")
      .replace(/\b\w/g, function (character) {
        return character.toUpperCase();
      });
  }

  function friendlyRole(value) {
    const normalized = text(value).toLowerCase();
    return ROLE_LABELS[normalized] || friendlyStatus(normalized);
  }

  function isInternalAdmin(user) {
    return Boolean(
      user &&
      (user.is_admin === true ||
        text(user.dashboard_type).toLowerCase() === "admin" ||
        (Array.isArray(user.admin_roles) && user.admin_roles.length > 0))
    );
  }

  function renderCustomerSummary(profile, snapshot) {
    const workspace = snapshot && typeof snapshot.workspace === "object" ? snapshot.workspace : {};
    const packageInfo = snapshot && typeof snapshot.package === "object" ? snapshot.package : {};
    const entitlements = snapshot && typeof snapshot.entitlements === "object" ? snapshot.entitlements : {};
    const membership = snapshot && typeof snapshot.membership === "object" ? snapshot.membership : {};
    const family = snapshot && typeof snapshot.family === "object" ? snapshot.family : {};
    const project = snapshot && typeof snapshot.project === "object" ? snapshot.project : {};

    const packageName = firstText(
      packageInfo.display_name,
      packageInfo.name,
      entitlements.package_name,
      workspace.package_name,
      project.package_name,
    );
    const packageCode = firstText(
      packageInfo.code,
      packageInfo.package_code,
      entitlements.package_code,
      workspace.package_code,
      project.package_code,
    );
    const projectName = firstText(
      workspace.project_name,
      project.project_name,
      project.name,
      workspace.project_id,
      project._id,
      project.id,
    );
    const familyName = firstText(
      workspace.family_name,
      workspace.household_name,
      family.family_name,
      family.household_name,
      family.name,
      workspace.family_id,
      family._id,
      family.id,
    );
    const memberRole = firstText(
      membership.member_role,
      membership.role,
      workspace.member_role,
      snapshot && snapshot.member_role,
    );

    setText("[data-summary-account-status]", friendlyStatus(profile.status), "Unknown");
    setText("[data-summary-email]", profile.email, "Not available");
    setText("[data-summary-package]", packageName || packageCode, "No active package connected");
    setText("[data-summary-project]", projectName, "No active project connected");
    setText("[data-summary-family]", familyName, "No family or household connected");
    setText("[data-summary-member-role]", friendlyRole(memberRole), "Not assigned");
    setText("[data-summary-billing-sync]", friendlyStatus(profile.billing_sync_status), "Not linked");

    const statusNode = document.querySelector("[data-customer-account-summary-status]");
    if (statusNode) {
      statusNode.textContent =
        "Account and workspace details are loaded from your current Tomb of Light records.";
    }
  }

  function renderInternalSummary(user) {
    if (summaryPanel) {
      const title = summaryPanel.querySelector("h2");
      const eyebrow = summaryPanel.querySelector(":scope > .eyebrow");
      if (eyebrow) eyebrow.textContent = "Internal Account Overview";
      if (title) title.textContent = "Your internal operations identity";
    }

    const roles = Array.isArray(user.admin_roles) ? user.admin_roles : [];
    const officerRoles = Array.isArray(user.officer_roles) ? user.officer_roles : [];
    const roleText = [...new Set([...officerRoles, ...roles])]
      .map(friendlyRole)
      .filter(Boolean)
      .join(" · ");

    setLabel("[data-summary-package]", "Operations Scope");
    setLabel("[data-summary-project]", "Portal Type");
    setLabel("[data-summary-family]", "Authority");
    setLabel("[data-summary-member-role]", "Internal Role");
    setLabel("[data-summary-billing-sync]", "Authenticator MFA");

    setText("[data-summary-account-status]", friendlyStatus(user.status || "active"), "Active");
    setText("[data-summary-email]", user.email, "Not available");
    setText("[data-summary-package]", "Internal Operations", "Internal Operations");
    setText("[data-summary-project]", "Administrator Workspace", "Administrator Workspace");
    setText("[data-summary-family]", user.is_admin ? "Authorized" : "Not authorized", "Not authorized");
    setText("[data-summary-member-role]", roleText, friendlyRole(user.role || "admin"));
    setText("[data-summary-billing-sync]", user.mfa_enabled ? "Enabled" : "Optional · Disabled", "Optional · Disabled");

    const statusNode = document.querySelector("[data-customer-account-summary-status]");
    if (statusNode) {
      statusNode.textContent =
        "This is an internal Tomb of Light operations identity. Customer package, household, and billing fields do not apply to this account.";
    }

    if (activityPanel) {
      const eyebrow = activityPanel.querySelector(":scope > .eyebrow");
      const title = activityPanel.querySelector("h2");
      if (eyebrow) eyebrow.textContent = "Internal Security Activity";
      if (title) title.textContent = "Administrative security history";
    }
    const activityStatus = document.querySelector("[data-security-activity-status]");
    const activityList = document.querySelector("[data-security-activity-list]");
    if (activityList) {
      activityList.innerHTML = "";
      const card = document.createElement("div");
      card.className = "portal-account-activity-item";
      const strong = document.createElement("strong");
      strong.textContent = "Administrative audit trail";
      const detail = document.createElement("p");
      detail.className = "card-copy";
      detail.textContent =
        "Internal security and privileged-operation events are retained in the governed audit system and Control Center rather than the customer self-service feed.";
      card.appendChild(strong);
      card.appendChild(detail);
      activityList.appendChild(card);
    }
    if (activityStatus) {
      activityStatus.textContent = "Internal account recognized. Customer-only security history endpoints are not used for this identity.";
    }

    const nav = document.getElementById("site-nav");
    if (nav) {
      nav.innerHTML =
        '<a href="dashboard.html">Admin Workspace</a>' +
        '<a href="admin-control-center.html">Control Center</a>' +
        '<a href="admin-family-manager.html">Family Manager</a>' +
        '<a href="admin-portrait-review.html">Portrait Review</a>' +
        '<a href="admin-verification-review.html">Evidence Review</a>';
    }
    const dataRequestLink = document.querySelector("[data-account-data-requests-link]");
    if (dataRequestLink) dataRequestLink.hidden = true;
    const signInLink = document.querySelector('.header-actions a[href="signin.html"]');
    if (signInLink) signInLink.hidden = true;
  }

  function formatTimestamp(value) {
    const raw = text(value);
    if (!raw) return "Time unavailable";
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    return date.toLocaleString();
  }

  function renderActivity(payload) {
    const listNode = document.querySelector("[data-security-activity-list]");
    const statusNode = document.querySelector("[data-security-activity-status]");
    if (!listNode) return;

    listNode.innerHTML = "";
    const items = Array.isArray(payload && payload.items) ? payload.items : [];
    if (!items.length) {
      if (statusNode) statusNode.textContent = "No recent security activity is available for this account.";
      return;
    }

    items.forEach(function (item) {
      const card = document.createElement("div");
      card.className = "portal-account-activity-item";
      const title = document.createElement("strong");
      title.textContent = text(item.label) || "Account security event";
      const meta = document.createElement("p");
      meta.className = "card-copy";
      meta.textContent = `${formatTimestamp(item.timestamp)} · ${friendlyStatus(item.result || "recorded")}`;
      card.appendChild(title);
      card.appendChild(meta);
      listNode.appendChild(card);
    });

    if (statusNode) {
      statusNode.textContent = `Showing ${items.length} recent account security event${items.length === 1 ? "" : "s"}.`;
    }
  }

  async function resolveSignedInUser() {
    try {
      if (typeof app.fetchCurrentUser === "function") {
        return await app.fetchCurrentUser();
      }
      return await app.apiRequest("/auth/me", { method: "GET" });
    } catch (_error) {
      return null;
    }
  }

  async function loadAccountDetails() {
    const user = await resolveSignedInUser();
    if (!user) {
      const summaryStatus = document.querySelector("[data-customer-account-summary-status]");
      const activityStatus = document.querySelector("[data-security-activity-status]");
      if (summaryStatus) summaryStatus.textContent = "Sign in to view your account and workspace summary.";
      if (activityStatus) activityStatus.textContent = "Sign in to view recent security activity.";
      return;
    }

    if (isInternalAdmin(user)) {
      renderInternalSummary(user);
      return;
    }

    if (summaryPanel) {
      try {
        const results = await Promise.all([
          app.apiRequest("/users/me/profile", { method: "GET" }),
          app.apiRequest("/users/me/workspace-context", { method: "GET" }),
        ]);
        renderCustomerSummary(results[0] || user, results[1] || {});
      } catch (_error) {
        const statusNode = document.querySelector("[data-customer-account-summary-status]");
        if (statusNode) statusNode.textContent = "Your account summary could not be loaded right now.";
      }
    }

    if (activityPanel) {
      try {
        const payload = await app.apiRequest("/users/me/security-activity", { method: "GET" });
        renderActivity(payload || {});
      } catch (_error) {
        const statusNode = document.querySelector("[data-security-activity-status]");
        if (statusNode) statusNode.textContent = "Recent security activity could not be loaded right now.";
      }
    }
  }

  document.addEventListener("DOMContentLoaded", loadAccountDetails);
})();