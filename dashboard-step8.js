(function () {
  "use strict";

  const DASHBOARD_SELECTOR = "[data-dashboard]";
  const STEP81_STYLE_ID = "tol-step8-1-styles";
  const STEP81_STYLE_HREF = "dashboard-step8-1.css?v=20260907-step8-1";
  const LAPSED_MAINTENANCE_STATUSES = new Set([
    "canceled",
    "cancelled",
    "churned",
    "overdue",
    "past_due",
    "refunded",
    "unpaid",
  ]);
  const VAULT_FLAGS = [
    "can_use_personal_vault",
    "can_use_household_vault",
    "can_use_linked_household_vault",
    "can_use_organization_records_vault",
  ];

  let lastHomeSignature = "";
  let refreshQueued = false;
  let homeObserver = null;

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

  function ensureStep81Styles() {
    if (document.getElementById(STEP81_STYLE_ID)) return;
    const link = document.createElement("link");
    link.id = STEP81_STYLE_ID;
    link.rel = "stylesheet";
    link.href = STEP81_STYLE_HREF;
    document.head.appendChild(link);
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node && typeof value === "string" && value && node.textContent !== value) {
      node.textContent = value;
    }
  }

  function readText(selector) {
    const node = document.querySelector(selector);
    return String(node && node.textContent ? node.textContent : "").trim();
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString();
  }

  function isInternalContext(context) {
    const user =
      (context && context.user) ||
      window.TOLResolvedUser ||
      (window.TOLApp && typeof window.TOLApp.getSavedUser === "function"
        ? window.TOLApp.getSavedUser()
        : null);
    if (window.TOLApp && typeof window.TOLApp.isInternalRole === "function") {
      return window.TOLApp.isInternalRole(user || {});
    }
    const role = normalizeValue(user && user.role);
    const tier = normalizeValue(user && user.access_tier);
    return ["admin", "super_admin", "operations_admin", "finance_admin", "marketing_admin"].includes(role) ||
      tier.includes("admin");
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

  function getResolvedEntitlements(context) {
    return context && context.resolvedEntitlements && typeof context.resolvedEntitlements === "object"
      ? context.resolvedEntitlements
      : {};
  }

  function getProjectId(context) {
    return String(
      context?.activeProject?.project_id ||
        context?.activeProject?.projectId ||
        context?.activeProject?.id ||
        context?.activeProject?._id ||
        context?.currentWorkspace?.projectId ||
        context?.currentWorkspace?.project_id ||
        "",
    ).trim();
  }

  function getFamilyId(context) {
    return String(
      context?.activeProject?.family_id ||
        context?.activeProject?.familyId ||
        context?.currentWorkspace?.familyId ||
        context?.currentWorkspace?.family_id ||
        "",
    ).trim();
  }

  function withContextParams(href, context) {
    if (!href) return href;
    const familyId = getFamilyId(context);
    const projectId = getProjectId(context);
    try {
      const url = new URL(href, window.location.href);
      if (familyId) url.searchParams.set("family_id", familyId);
      if (projectId) url.searchParams.set("project_id", projectId);
      return `${url.pathname.split("/").pop() || href}${url.search}${url.hash}`;
    } catch (_error) {
      return href;
    }
  }

  function getProjectName(context) {
    const candidates = [
      context?.activeProject?.project_name,
      context?.activeProject?.family_name,
      context?.activeProject?.household_name,
      context?.activeProject?.name,
      context?.currentWorkspace?.projectName,
      readText("[data-command-center-project]"),
    ];
    return String(candidates.find(function (value) {
      return String(value || "").trim();
    }) || "Your Tomb of Light Project").trim();
  }

  function getPackageName(context) {
    return String(
      context?.packageName ||
        context?.currentWorkspace?.packageName ||
        readText("[data-dashboard-package-display]") ||
        "Active Package",
    ).trim();
  }

  function getLaneName(context) {
    const lane = normalizeValue(
      context?.packageLane || getResolvedEntitlements(context).package_lane,
    );
    if (lane === "portrait") return "Portrait";
    if (lane === "network") return "Network";
    if (lane === "organization") return "Organization";
    return "Household";
  }

  function getIntakeStatus(context) {
    const direct = normalizeValue(
      context?.latestSubmission?.status || context?.latestSubmission?.submission_status,
    );
    if (direct) return direct;
    const domStatus = normalizeValue(readText("[data-intake-status-badge]"));
    if (!domStatus || domStatus === "not submitted" || domStatus === "unavailable") {
      return domStatus === "not submitted" ? "not_started" : "";
    }
    return domStatus.replace(/\s+/g, "_");
  }

  function getStageLabel(status) {
    const normalized = normalizeValue(status);
    if (normalized === "approved") return "Intake approved — preparing production materials";
    if (normalized === "build_ready") return "Production setup in progress";
    if (normalized === "in_production") return "Production build in progress";
    if (normalized === "qa_review") return "Verification and quality review";
    if (normalized === "client_review") return "Customer review";
    if (normalized === "delivered") return "Delivered";
    if (normalized === "archived") return "Continuity and maintenance";
    if (normalized === "submitted") return "Intake submitted — review pending";
    if (normalized === "in_review") return "Intake under review";
    if (normalized === "rejected") return "Intake needs attention";
    return "Workspace active";
  }

  function resolvePrimaryAction(context, status) {
    const maintenance = getMaintenancePresentation(context && context.maintenance);
    if (maintenance.key === "read_only" || maintenance.key === "billing_attention") {
      return {
        title: "Restore maintenance billing",
        copy: "Update billing to restore write access. Existing protected files remain available according to your maintenance policy.",
        label: "Open Billing",
        href: "billing.html",
      };
    }

    const normalized = normalizeValue(status);
    if (!normalized || normalized === "not_started") {
      return {
        title: "Start your project intake",
        copy: "Complete the private intake so Tomb of Light can establish the production plan for your workspace.",
        label: "Start Intake",
        href: "intake-welcome.html",
      };
    }
    if (normalized === "rejected") {
      return {
        title: "Resolve your intake items",
        copy: "Review the items requiring attention and resubmit the intake before production continues.",
        label: "Resume Intake",
        href: "intake-household.html",
      };
    }
    if (normalized === "submitted" || normalized === "in_review") {
      return {
        title: "Your intake is under review",
        copy: "No new submission is required right now. You can review the record while Tomb of Light completes the intake review.",
        label: "View Intake Status",
        href: "intake-review.html",
      };
    }
    if (normalized === "approved") {
      return {
        title: "Upload your production materials",
        copy: "Your intake is approved. Add the photographs and supporting records Tomb of Light needs to continue production.",
        label: "Upload Materials",
        href: "upload-hub.html",
      };
    }
    if (normalized === "build_ready") {
      return {
        title: "Continue your production setup",
        copy: "Your project has moved beyond intake. Review your family workspace and add any remaining production materials.",
        label: "Open Family Workspace",
        href: "tree-view.html",
      };
    }
    if (normalized === "in_production") {
      return {
        title: "Production is underway",
        copy: "Your materials are in the production workflow. Review the project record for the latest status and upcoming customer actions.",
        label: "View Project Status",
        href: "intake-review.html",
      };
    }
    if (normalized === "qa_review" || normalized === "client_review") {
      return {
        title: normalized === "client_review" ? "Review your project" : "Quality review is underway",
        copy: normalized === "client_review"
          ? "Your project has reached customer review. Open the project record to review the current delivery state."
          : "Tomb of Light is completing verification and quality review before customer delivery.",
        label: "Open Project",
        href: "intake-review.html",
      };
    }
    if (normalized === "delivered" || normalized === "archived") {
      return {
        title: "Your legacy workspace is ready",
        copy: "Open your protected deliverables and continuity tools from the customer application.",
        label: "View Deliverables",
        href: "lineage-certificate.html",
      };
    }
    return {
      title: "Continue your legacy project",
      copy: "Open your project record to review the current status and next required action.",
      label: "Open Project",
      href: "intake-review.html",
    };
  }

  function resolveProgress(status) {
    const normalized = normalizeValue(status);
    const steps = [
      { key: "intake", label: "Intake", state: "pending" },
      { key: "materials", label: "Materials", state: "pending" },
      { key: "verification", label: "Verification", state: "pending" },
      { key: "production", label: "Production", state: "pending" },
      { key: "delivery", label: "Delivery", state: "pending" },
    ];

    function markComplete(index) {
      if (steps[index]) steps[index].state = "complete";
    }
    function markCurrent(index) {
      if (steps[index]) steps[index].state = "current";
    }

    if (!normalized || normalized === "not_started" || normalized === "rejected") {
      markCurrent(0);
      return steps;
    }
    if (normalized === "submitted" || normalized === "in_review") {
      markCurrent(0);
      return steps;
    }

    markComplete(0);
    if (normalized === "approved" || normalized === "build_ready") {
      markCurrent(1);
      return steps;
    }
    if (normalized === "in_production") {
      markComplete(1);
      markComplete(2);
      markCurrent(3);
      return steps;
    }
    if (normalized === "qa_review") {
      markComplete(1);
      markCurrent(2);
      markCurrent(3);
      return steps;
    }
    if (normalized === "client_review") {
      markComplete(1);
      markComplete(2);
      markComplete(3);
      markCurrent(4);
      return steps;
    }
    if (normalized === "delivered" || normalized === "archived") {
      steps.forEach(function (step) {
        step.state = "complete";
      });
      return steps;
    }

    markCurrent(1);
    return steps;
  }

  function getDomainLinks(context) {
    const resolved = getResolvedEntitlements(context);
    const hasFamily = Boolean(resolved.can_build_family_tree || resolved.can_build_household);
    const hasVault = VAULT_FLAGS.some(function (key) {
      return Boolean(resolved[key]);
    });
    const hasDeliverables = Boolean(
      resolved.can_use_viewer ||
        resolved.can_use_secure_share_viewer ||
        resolved.can_use_lineage_certificate ||
        context?.hasPackageAccess,
    );

    return [
      { key: "home", label: "Home", href: "dashboard.html", show: true },
      { key: "project", label: "My Project", href: "intake-review.html", show: true },
      { key: "family", label: "Family", href: hasFamily ? "tree-view.html" : "household-access.html", show: hasFamily },
      { key: "uploads", label: "Uploads", href: "upload-hub.html", show: Boolean(context?.hasPackageAccess) },
      { key: "vault", label: "Vault", href: "vault-upload.html", show: hasVault },
      { key: "deliverables", label: "Deliverables", href: "lineage-certificate.html", show: hasDeliverables },
      { key: "account", label: "Account", href: "account-security.html", show: true },
      { key: "support", label: "Support", href: "portal-help.html", show: true },
    ].filter(function (item) {
      return item.show;
    }).map(function (item) {
      return Object.assign({}, item, { href: withContextParams(item.href, context) });
    });
  }

  function ensureRail(context) {
    const pageWrap = document.querySelector(".page-wrap");
    if (!pageWrap) return;

    let rail = pageWrap.querySelector(".tol-app-rail");
    if (!rail) {
      rail = document.createElement("aside");
      rail.className = "tol-app-rail";
      rail.setAttribute("aria-label", "Customer workspace navigation");
      pageWrap.insertBefore(rail, pageWrap.firstChild);
    }

    const projectName = getProjectName(context);
    const packageName = getPackageName(context);
    const links = getDomainLinks(context);
    const railSignature = JSON.stringify({ projectName, packageName, links });
    if (rail.dataset.signature === railSignature) return;
    rail.dataset.signature = railSignature;

    rail.innerHTML = `
      <div class="tol-app-rail-brand">
        <img src="site-logo-header.png" alt="" aria-hidden="true" />
        <span>Tomb of Light™</span>
      </div>
      <div class="tol-app-rail-project">
        <small>Current workspace</small>
        <strong>${escapeHtml(projectName)}</strong>
        <span>${escapeHtml(packageName)} · ${escapeHtml(getLaneName(context))}</span>
      </div>
      <nav class="tol-app-rail-nav" aria-label="Workspace sections">
        ${links.map(function (item) {
          return `<a class="tol-app-rail-link" data-tol-domain="${item.key}" href="${escapeHtml(item.href)}"${item.key === "home" ? ' aria-current="page"' : ""}>${escapeHtml(item.label)}</a>`;
        }).join("")}
      </nav>
      <div class="tol-app-rail-foot">
        Private customer workspace<br />
        Protected by Tomb of Light
      </div>
    `;
  }

  function replaceMobileNavigation(context) {
    const nav = document.querySelector("#site-nav");
    if (!nav) return;
    const links = getDomainLinks(context);
    const signature = JSON.stringify(links);
    if (nav.dataset.step81Signature === signature) return;
    nav.dataset.step81Signature = signature;
    nav.innerHTML = links.map(function (item) {
      return `<a href="${escapeHtml(item.href)}"${item.key === "home" ? ' aria-current="page"' : ""}>${escapeHtml(item.label)}</a>`;
    }).join("");
  }

  function getQuickActions(context) {
    const resolved = getResolvedEntitlements(context);
    const actions = [];
    if (resolved.can_build_family_tree) {
      actions.push({
        title: "Family Tree",
        copy: "Open your working lineage structure.",
        href: withContextParams("tree-view.html", context),
      });
    }
    if (context?.hasPackageAccess) {
      actions.push({
        title: "Upload Hub",
        copy: "Add photographs and supporting records.",
        href: "upload-hub.html",
      });
    }
    if (VAULT_FLAGS.some(function (key) { return Boolean(resolved[key]); })) {
      actions.push({
        title: "Vault",
        copy: "Open your private protected legacy files.",
        href: "vault-upload.html",
      });
    }
    if (resolved.can_build_household || resolved.family_household_scope) {
      actions.push({
        title: "Members & Access",
        copy: "Manage trusted household access and roles.",
        href: withContextParams("household-access.html", context),
      });
    }
    if (actions.length < 4) {
      actions.push({
        title: "Account",
        copy: "Manage security and account settings.",
        href: "account-security.html",
      });
    }
    return actions.slice(0, 4);
  }

  function getHomeAlert(context, status) {
    const maintenance = getMaintenancePresentation(context && context.maintenance);
    if (maintenance.key === "read_only" || maintenance.key === "billing_attention") {
      return {
        kind: "warning",
        title: "Maintenance billing needs attention",
        copy: maintenance.label,
      };
    }
    if (maintenance.key === "grace") {
      return {
        kind: "warning",
        title: "Maintenance grace period",
        copy: maintenance.label,
      };
    }
    if (normalizeValue(status) === "approved") {
      return {
        kind: "info",
        title: "Intake approved",
        copy: "Your intake is complete. The next customer action is production materials—not another intake submission.",
      };
    }
    return {
      kind: "info",
      title: "Workspace protected",
      copy: "No urgent account issue is shown on your Home screen.",
    };
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderHome(context) {
    const dashboard = document.querySelector(DASHBOARD_SELECTOR);
    if (!dashboard) return;

    let shell = dashboard.querySelector(".tol-home-shell");
    if (!shell) {
      shell = document.createElement("section");
      shell.className = "tol-home-shell";
      shell.setAttribute("aria-label", "Customer Home");
      const pageSections = dashboard.querySelector(".page-sections");
      if (pageSections) dashboard.insertBefore(shell, pageSections);
      else dashboard.appendChild(shell);
    }

    const status = getIntakeStatus(context);
    const action = resolvePrimaryAction(context, status);
    const progress = resolveProgress(status);
    const quickActions = getQuickActions(context);
    const alert = getHomeAlert(context, status);
    const projectName = getProjectName(context);
    const packageName = getPackageName(context);
    const stageLabel = getStageLabel(status);
    const maintenance = getMaintenancePresentation(context && context.maintenance);

    const signature = JSON.stringify({
      projectName,
      packageName,
      status,
      action,
      progress,
      quickActions,
      alert,
      maintenance,
    });
    if (signature === lastHomeSignature && shell.dataset.rendered === "true") return;
    lastHomeSignature = signature;
    shell.dataset.rendered = "true";

    shell.innerHTML = `
      <div class="tol-home-grid">
        <article class="tol-home-card tol-home-next">
          <span class="tol-home-kicker">Your next step</span>
          <h2>${escapeHtml(action.title)}</h2>
          <p class="tol-home-copy">${escapeHtml(action.copy)}</p>
          <a class="tol-home-primary" href="${escapeHtml(withContextParams(action.href, context))}">${escapeHtml(action.label)}</a>
        </article>
        <article class="tol-home-card">
          <div class="tol-home-status-head">
            <div>
              <span class="tol-home-kicker">Project status</span>
              <h3>${escapeHtml(stageLabel)}</h3>
            </div>
            <span class="tol-home-status-badge">${escapeHtml(packageName)}</span>
          </div>
          <div class="tol-home-progress" aria-label="Project progress">
            ${progress.map(function (step) {
              return `<div class="tol-home-progress-step is-${step.state}">${escapeHtml(step.label)}</div>`;
            }).join("")}
          </div>
        </article>
      </div>
      <article class="tol-home-card tol-home-quick-card">
        <div class="tol-home-quick-head">
          <div>
            <span class="tol-home-kicker">Quick access</span>
            <h3>Open your most-used workspace tools</h3>
          </div>
          <p>Everything else lives in the navigation.</p>
        </div>
        <div class="tol-home-quick-grid">
          ${quickActions.map(function (item) {
            return `<a class="tol-home-quick-action" href="${escapeHtml(item.href)}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.copy)}</span></a>`;
          }).join("")}
        </div>
      </article>
      <div class="tol-home-alert${alert.kind === "warning" ? " is-warning" : ""}">
        <div>
          <strong>${escapeHtml(alert.title)}</strong>
          <span>${escapeHtml(alert.copy)}</span>
        </div>
      </div>
    `;

    setText("[data-dashboard-hero-title]", projectName);
    setText("[data-dashboard-hero-eyebrow]", `${packageName} · ${getLaneName(context)} workspace`);
    setText("[data-dashboard-status]", stageLabel);
  }

  function applyBranchLinkPresentation(context) {
    const resolved = getResolvedEntitlements(context);
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

  function applyLayeredApplication(context) {
    if (!context || isInternalContext(context)) return;
    ensureStep81Styles();
    document.body.classList.add("tol-layered-app");
    ensureRail(context);
    replaceMobileNavigation(context);
    renderHome(context);
  }

  function applyPresentation(context) {
    if (!document.querySelector(DASHBOARD_SELECTOR) || !context) return;
    applyBranchLinkPresentation(context);
    applyGrantPresentation(context);
    applyMaintenancePresentation(context);
    clarifyMaterialsWorkflow();
    applyLayeredApplication(context);
  }

  function schedulePresentation(context) {
    const apply = function () {
      applyPresentation(context);
    };
    if (typeof queueMicrotask === "function") queueMicrotask(apply);
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(apply);
    window.setTimeout(apply, 100);
    window.setTimeout(apply, 500);
    window.setTimeout(apply, 1200);
  }

  function scheduleDomDrivenRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    window.setTimeout(function () {
      refreshQueued = false;
      const context = window.TOLDashboardContext;
      if (context && !isInternalContext(context)) {
        applyLayeredApplication(context);
        applyBranchLinkPresentation(context);
      }
    }, 60);
  }

  function bindHomeObserver() {
    if (homeObserver || !document.body) return;
    homeObserver = new MutationObserver(function (mutations) {
      const relevant = mutations.some(function (mutation) {
        const target = mutation.target instanceof Element ? mutation.target : mutation.target.parentElement;
        if (!target) return false;
        return Boolean(
          target.closest("[data-intake-status-badge]") ||
          target.closest("[data-command-center-stage]") ||
          target.closest("[data-dashboard-status]") ||
          target.closest("[data-health-maintenance]") ||
          target.closest("[data-dashboard-tool=\"link_keys\"]") ||
          target.closest("#site-nav"),
        );
      });
      if (relevant) scheduleDomDrivenRefresh();
    });
    homeObserver.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["style", "data-state"],
    });
  }

  function handleContext(context) {
    const normalized = normalizeWorkspaceTruth(context);
    if (!normalized) return;
    window.TOLDashboardContext = normalized;
    schedulePresentation(normalized);
  }

  ensureStep81Styles();

  window.addEventListener("tol:dashboard-context-ready", function (event) {
    handleContext(event && event.detail ? event.detail : window.TOLDashboardContext);
  });

  document.addEventListener("DOMContentLoaded", function () {
    bindHomeObserver();
    if (window.TOLDashboardContext) {
      handleContext(window.TOLDashboardContext);
    }
  });
})();
