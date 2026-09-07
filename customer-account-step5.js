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

  function renderSummary(profile, snapshot) {
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
    setText(
      "[data-summary-package]",
      packageName || packageCode,
      "No active package connected",
    );
    setText("[data-summary-project]", projectName, "No active project connected");
    setText("[data-summary-family]", familyName, "No family or household connected");
    setText("[data-summary-member-role]", friendlyRole(memberRole), "Not assigned");
    setText(
      "[data-summary-billing-sync]",
      friendlyStatus(profile.billing_sync_status),
      "Not linked",
    );

    const statusNode = document.querySelector("[data-customer-account-summary-status]");
    if (statusNode) {
      statusNode.textContent =
        "Account and workspace details are loaded from your current Tomb of Light records.";
    }
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

  async function loadCustomerAccountDetails() {
    const token = typeof app.getToken === "function" ? app.getToken() : "";
    if (!token) {
      const summaryStatus = document.querySelector("[data-customer-account-summary-status]");
      const activityStatus = document.querySelector("[data-security-activity-status]");
      if (summaryStatus) summaryStatus.textContent = "Sign in to view your account and workspace summary.";
      if (activityStatus) activityStatus.textContent = "Sign in to view recent security activity.";
      return;
    }

    if (summaryPanel) {
      try {
        const results = await Promise.all([
          app.apiRequest("/users/me/profile", { method: "GET" }),
          app.apiRequest("/users/me/workspace-context", { method: "GET" }),
        ]);
        renderSummary(results[0] || {}, results[1] || {});
      } catch (error) {
        const statusNode = document.querySelector("[data-customer-account-summary-status]");
        if (statusNode) statusNode.textContent = "Your account summary could not be loaded right now.";
      }
    }

    if (activityPanel) {
      try {
        const payload = await app.apiRequest("/users/me/security-activity", { method: "GET" });
        renderActivity(payload || {});
      } catch (error) {
        const statusNode = document.querySelector("[data-security-activity-status]");
        if (statusNode) statusNode.textContent = "Recent security activity could not be loaded right now.";
      }
    }
  }

  document.addEventListener("DOMContentLoaded", loadCustomerAccountDetails);
})();
