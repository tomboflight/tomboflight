(function () {
  "use strict";

  const DASHBOARD_SELECTOR = "[data-dashboard]";
  const LAPSED_MAINTENANCE_STATUSES = new Set([
    "canceled",
    "cancelled",
    "churned",
    "overdue",
    "past_due",
    "refunded",
    "unpaid",
  ]);

  function normalizeValue(value) {
    return String(value || "").trim().toLowerCase();
  }

  function getSnapshot(context) {
    return context && context.workspaceContextSnapshot && typeof context.workspaceContextSnapshot === "object"
      ? context.workspaceContextSnapshot
      : {};
  }

  function normalizeWorkspaceTruth(context) {
    if (!context || typeof context !== "object") return null;

    const snapshot = getSnapshot(context);
    const packageInfo = snapshot.package && typeof snapshot.package === "object" ? snapshot.package : {};
    const acquisition = snapshot.acquisition && typeof snapshot.acquisition === "object" ? snapshot.acquisition : {};
    const packageStatus = normalizeValue(packageInfo.status || context.packageStatus);
    const acquisitionSource = normalizeValue(
      acquisition.source ||
        context.acquisitionSource ||
        (packageStatus === "granted"
          ? "governed_grant"
          : packageStatus === "paid"
            ? "paid_order"
            : ""),
    );
    const paymentRequired =
      typeof acquisition.payment_required === "boolean"
        ? acquisition.payment_required
        : typeof packageInfo.payment_required === "boolean"
          ? packageInfo.payment_required
          : context.paymentRequired;

    context.packageStatus = packageStatus || null;
    context.acquisitionSource = acquisitionSource || null;
    context.paymentRequired =
      typeof paymentRequired === "boolean" ? paymentRequired : null;

    const hasVerifiedPaidPackage = Boolean(
      context.hasPackageAccess &&
        acquisitionSource === "paid_order" &&
        packageStatus === "paid" &&
        paymentRequired !== false,
    );
    context.hasPaidPackage = hasVerifiedPaidPackage;

    if (!hasVerifiedPaidPackage) {
      context.paidOrder = null;
      if (context.currentWorkspace && typeof context.currentWorkspace === "object") {
        context.currentWorkspace.paidOrder = null;
      }
    }

    if (context.currentWorkspace && typeof context.currentWorkspace === "object") {
      context.currentWorkspace.acquisitionSource = acquisitionSource || null;
      context.currentWorkspace.paymentRequired =
        typeof paymentRequired === "boolean" ? paymentRequired : null;
      context.currentWorkspace.packageStatus = packageStatus || null;
    }

    context.maintenance =
      snapshot.maintenance && typeof snapshot.maintenance === "object"
        ? snapshot.maintenance
        : context.maintenance && typeof context.maintenance === "object"
          ? context.maintenance
          : {};

    return context;
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node && typeof value === "string" && value) {
      node.textContent = value;
    }
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString();
  }

  function getMaintenancePresentation(maintenance) {
    const state = maintenance && typeof maintenance === "object" ? maintenance : {};
    const status = normalizeValue(state.status || "not_started");

    if (state.read_only === true || state.write_allowed === false) {
      return {
        key: "read_only",
        label: "Read-only — update billing to resume Vault changes",
      };
    }

    if (state.in_grace === true) {
      const graceEnd = formatDate(state.grace_ends_at);
      return {
        key: "grace",
        label: graceEnd
          ? `Grace period — billing should be restored by ${graceEnd}`
          : "Grace period — billing action recommended",
      };
    }

    if (["active", "paid", "current", "trialing"].includes(status)) {
      return { key: "active", label: "Active" };
    }

    if (["not_started", "scheduled", "pending"].includes(status)) {
      return { key: "scheduled", label: "Scheduled / not started" };
    }

    if (LAPSED_MAINTENANCE_STATUSES.has(status)) {
      return { key: "billing_attention", label: "Billing attention required" };
    }

    return {
      key: status || "unknown",
      label: status
        ? status
            .split("_")
            .map(function (part) {
              return part.charAt(0).toUpperCase() + part.slice(1);
            })
            .join(" ")
        : "Status unavailable",
    };
  }

  function ensureMaintenanceRow() {
    let node = document.querySelector("[data-health-maintenance]");
    if (node) return node;

    const list = document.querySelector(
      ".portal-workspace-health-panel .portal-status-list",
    );
    if (!list) return null;

    const row = document.createElement("p");
    row.className = "card-copy";
    row.innerHTML = "<strong>Maintenance:</strong> <span data-health-maintenance>Checking status</span>";
    list.appendChild(row);
    return row.querySelector("[data-health-maintenance]");
  }

  function applyBranchLinkPresentation(context) {
    const resolved = context && context.resolvedEntitlements ? context.resolvedEntitlements : {};
    const canLinkHouseholds = Boolean(resolved.can_link_households);

    document
      .querySelectorAll('.site-nav a[href^="link-keys.html"]')
      .forEach(function (node) {
        node.style.display = canLinkHouseholds ? "" : "none";
      });

    document
      .querySelectorAll('[data-dashboard-tool="link_keys"]')
      .forEach(function (node) {
        node.style.display = canLinkHouseholds ? "" : "none";
        node.setAttribute("aria-hidden", canLinkHouseholds ? "false" : "true");
        if (canLinkHouseholds) {
          node.removeAttribute("aria-disabled");
          node.style.pointerEvents = "";
          const status = node.querySelector(".portal-action-status");
          if (status) {
            status.textContent = "Open";
            status.dataset.state = "success";
          }
        }
      });

    const unlock = document.querySelector("[data-unlock-link-keys]");
    if (unlock) {
      unlock.textContent = canLinkHouseholds ? "Included" : "Not included";
      const label = unlock.parentElement && unlock.parentElement.querySelector("span:first-child");
      if (label) label.textContent = "Household Link Keys";
    }
  }

  function applyGrantPresentation(context) {
    const isGranted =
      context &&
      (context.acquisitionSource === "governed_grant" ||
        context.packageStatus === "granted");
    if (!isGranted) return;

    const packageName = String(context.packageName || "Granted package").trim();
    setText("[data-dashboard-package-display]", `${packageName} — Granted access`);
    setText("[data-dashboard-scope-chip]", "Granted Access");
    setText(
      "[data-command-center-package]",
      `${packageName} · Tomb of Light authorized grant · no package payment required`,
    );
    setText(
      "[data-access-status]",
      "Access granted by Tomb of Light. No package payment is required for this workspace.",
    );
  }

  function applyMaintenancePresentation(context) {
    const presentation = getMaintenancePresentation(context && context.maintenance);
    const node = ensureMaintenanceRow();
    if (node) {
      node.textContent = presentation.label;
      node.dataset.state = presentation.key;
    }

    const vaultCard = document.querySelector('[data-dashboard-tool="vault"]');
    if (vaultCard && presentation.key === "read_only") {
      const status = vaultCard.querySelector(".portal-action-status");
      const cta = vaultCard.querySelector(".portal-action-cta");
      if (status) {
        status.textContent = "Read-only";
        status.dataset.state = "warning";
      }
      if (cta) cta.textContent = "Open Read-only Vault";
    }

    if (presentation.key !== "read_only") return;

    setText("[data-dashboard-next-focus]", "Restore maintenance billing");
    setText(
      "[data-command-center-next-action]",
      "Update maintenance billing to resume Vault changes. Existing Vault files remain available to view and download.",
    );

    const primaryAction = document.querySelector("[data-dashboard-hero-primary-action]");
    if (primaryAction) {
      primaryAction.style.display = "";
      primaryAction.setAttribute("href", "billing.html");
      primaryAction.textContent = "Restore Maintenance Billing";
      primaryAction.dataset.originalHref = "billing.html";
    }
  }

  function clarifyMaterialsWorkflow() {
    const panel = document.querySelector(".portal-materials-panel");
    if (!panel) return;

    const heading = panel.querySelector("summary .portal-disclosure-heading strong");
    if (heading) {
      heading.textContent = "Portrait, record, Vault, and review workflow status";
    }

    const replacements = [
      ["[data-received-portraits]", "Planned", "Planned from intake"],
      ["[data-received-portraits]", "In workflow", "Production workflow active"],
      ["[data-received-portraits]", "Not yet submitted", "No workflow activity confirmed here"],
      ["[data-received-verification]", "Planned", "Planned from intake"],
      ["[data-received-verification]", "In workflow", "Production workflow active"],
      ["[data-received-verification]", "Not yet submitted", "No workflow activity confirmed here"],
      ["[data-received-vault]", "Check workspace", "Check Vault for actual files"],
      ["[data-received-vault]", "Not yet submitted", "No workflow activity confirmed here"],
    ];

    replacements.forEach(function (item) {
      const node = document.querySelector(item[0]);
      if (node && node.textContent.trim() === item[1]) {
        node.textContent = item[2];
      }
    });

    const content = panel.querySelector(".portal-disclosure-content");
    if (content && !content.querySelector("[data-step8-materials-truth-note]")) {
      const note = document.createElement("p");
      note.className = "card-copy";
      note.setAttribute("data-step8-materials-truth-note", "true");
      note.textContent =
        "These indicators describe workflow status, not a file inventory. Open Upload Hub or Vault to view actual uploaded files.";
      content.appendChild(note);
    }
  }

  function applyPresentation(context) {
    if (!document.querySelector(DASHBOARD_SELECTOR) || !context) return;
    applyBranchLinkPresentation(context);
    applyGrantPresentation(context);
    applyMaintenancePresentation(context);
    clarifyMaterialsWorkflow();
  }

  function schedulePresentation(context) {
    const apply = function () {
      applyPresentation(context);
    };
    if (typeof queueMicrotask === "function") queueMicrotask(apply);
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(apply);
    window.setTimeout(apply, 100);
    window.setTimeout(apply, 500);
  }

  function handleContext(context) {
    const normalized = normalizeWorkspaceTruth(context);
    if (!normalized) return;
    window.TOLDashboardContext = normalized;
    schedulePresentation(normalized);
  }

  window.addEventListener("tol:dashboard-context-ready", function (event) {
    handleContext(event && event.detail ? event.detail : window.TOLDashboardContext);
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (window.TOLDashboardContext) {
      handleContext(window.TOLDashboardContext);
    }
  });
})();
