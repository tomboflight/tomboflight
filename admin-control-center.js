(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

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

  const state = {
    currentUser: null,
    accessProfile: null,
    roleKey: "",
    allowedQueues: [],
    allowedTabs: [],
    allowedActions: [],
    allowedBulkActions: [],
    isSuperAdmin: false,
    queue: "overview",
    selectedCaseId: "",
    selectedTab: "overview",
    cases: [],
    workspace: null,
    packageOptions: [],
    marketingSections: {},
    operationsSections: {},
    activeImpersonation: null,
    impersonationTicker: 0,
    bootstrapFailed: false,
    bootstrapErrorCode: "",
    accessProfileLoadFailed: false,
    overviewLoadFailed: false,
    casesLoadFailed: false,
    lastStatusMessage: "",
    diagnostics: null,
    fulfillmentItems: [],
    kernelStatus: null,
    kernelOperations: [],
    kernelPendingIdempotency: {},
    createAccountPreview: null,
    lifecycleWorkflow: null,
    teamAccess: {
      officers: [],
      roleTemplates: {},
      ceoIdentity: null,
      loaded: false,
    },
    teamAccessPreview: null,
  };
  const DEFAULT_ROLE_KEY = "user";

  const ADMIN_ERROR_CODES = {
    accessProfile: "ACC-AUTH-CONTEXT-FAILED",
    bootstrap: "ACC-BOOTSTRAP-FAILED",
    search: "ACC-SEARCH-FAILED",
    scope: "ACC-SCOPE-FAILED",
    parse: "ACC-RESPONSE-PARSE-FAILED",
    network: "NET-API-UNREACHABLE",
  };

  function classifyAdminError(error, fallbackCode) {
    const message = String((error && error.message) || "").toLowerCase();
    if (error instanceof TypeError || message.includes("failed to fetch") || message.includes("network")) {
      return ADMIN_ERROR_CODES.network;
    }
    if (message.includes("json") || message.includes("parse") || message.includes("unexpected token")) {
      return ADMIN_ERROR_CODES.parse;
    }
    return fallbackCode || ADMIN_ERROR_CODES.bootstrap;
  }

  let lastFailedRetry = null;

  function showBootstrapError(code, message, retryFn) {
    state.bootstrapFailed = true;
    state.bootstrapErrorCode = code;
    lastFailedRetry = typeof retryFn === "function" ? retryFn : null;
    const banner = document.querySelector("[data-admin-bootstrap-error]");
    const messageNode = document.querySelector("[data-admin-bootstrap-error-message]");
    if (messageNode) {
      messageNode.textContent = `${code}: ${message || "Service temporarily unavailable."}`;
    }
    if (banner) banner.hidden = false;
    updateActionAvailability();
    updateBulkActionAvailability();
    updateGlobalAdminControls();
  }

  function clearBootstrapError() {
    if (!state.bootstrapFailed) return;
    state.bootstrapFailed = false;
    state.bootstrapErrorCode = "";
    lastFailedRetry = null;
    const banner = document.querySelector("[data-admin-bootstrap-error]");
    if (banner) banner.hidden = true;
    updateActionAvailability();
    updateBulkActionAvailability();
    updateGlobalAdminControls();
  }

  const QUEUE_META = {
    overview: ["Overview", "Executive repair posture across active customer operations."],
    manual_fulfillment: [
      "Paid — Manual Fulfillment Required",
      "Stripe-verified purchases awaiting manual review and provisioning by an authorized operator.",
    ],
    intake_onboarding: ["Intake & Onboarding", "New accounts/projects, intake progression, and stalled intake visibility."],
    verification_upload_review: ["Verification & Upload Review", "Upload review, verification pending states, and aging verification queues."],
    workspace_access_invites: ["Workspace Access & Invites", "Invite delivery health, expiration risk, and member access mismatches."],
    build_fulfillment: ["Build & Fulfillment", "Project/build progression, readiness gates, and fulfillment blocking states."],
    exceptions_escalations: ["Exceptions & Escalations", "Operational exceptions requiring manual review or executive escalation."],
    ops_reports: ["Ops Reports", "Queue totals, aging, throughput, and operations export tooling."],
    traffic_awareness: ["Traffic & Awareness", "Visitors, sessions, landing pages, and source visibility."],
    funnel_conversion: ["Funnel Conversion", "CTA to purchase funnel conversion checkpoints."],
    package_demand: ["Package Demand", "Lane demand and conversion for Tomb of Light packages."],
    campaign_performance: ["Campaign Performance", "Campaign/source visits, signups, purchases, and conversion."],
    content_performance: ["Content Performance", "Homepage, hero CTA, pricing, testimonial, and dropoff telemetry."],
    marketing_reports: ["Marketing Reports", "Funnel, campaign, attribution, page, and package-interest export readiness."],
    money_now: ["Money Now", "Gross/net revenue, collected totals, refunds, failures, and unpaid balances."],
    subscriptions_maintenance: ["Subscriptions & Maintenance", "Active plans, renewals due, past-due subscriptions, and recovery signals."],
    package_revenue: ["Package Revenue", "Lane package sales volume with upgrade and downgrade visibility."],
    finance_integrity: ["Finance Integrity", "Unlinked payments, order/entitlement mismatch, override, and duplicate-risk signals."],
    payroll: ["Payroll", "Read-only payroll snapshot (totals, due dates, history, pending review)."],
    reports_exports: ["Reports & Exports", "Export generation is not yet live; section shows current availability status only."],
    customer_cases: ["Customer Cases", "Search and open the full case workspace."],
    orders: ["Orders", "Paid orders that need project linkage or billing review."],
    projects: ["Projects", "Active project records, lanes, phases, and source state."],
    entitlements: ["Entitlements", "Missing or stale package entitlements."],
    mint_queue: ["Mint Queue", "Mint-ready and mint-blocked project review."],
    upload_review: ["Upload Review", "Files, verification readiness, and pending upload cases."],
    billing_maintenance: ["Billing / Maintenance", "Maintenance defaults, subscriptions, and charge state."],
    users: ["Users", "Customer/admin identity conflicts and account records."],
    audit: ["Audit", "Recent action timeline and accountable repair history."],
    system_health: ["System Health", "Operational mismatches and service repair posture."],
  };

  const TAB_LABELS = {
    overview: "Overview",
    package_services: "Package & Services",
    family_household: "Family / Household",
    production: "Production",
    uploads: "Uploads",
    vault_metadata: "Vault Metadata",
    billing: "Billing",
    maintenance: "Maintenance",
    certificates: "Certificates",
    delivery: "Delivery",
    roles_access: "Roles & Access",
    mint: "Mint",
    audit_history: "Audit History",
  };
  const TAB_BACKEND_KEY = {
    overview: "identity",
    package_services: "package_lane",
    family_household: "project",
    production: "project",
    uploads: "uploads_verification",
    vault_metadata: "entitlements",
    billing: "orders_billing",
    maintenance: "maintenance",
    certificates: "certificates",
    delivery: "delivery",
    roles_access: "roles_access",
    mint: "mint_readiness",
    audit_history: "audit_timeline",
  };

  const ACTION_AVAILABILITY = {
    sync_package: ["project_id"],
    normalize_package: ["project_id"],
    assign_lane: ["project_id"],
    link_order_to_project: ["project_id", "order_id"],
    generate_entitlement: ["project_id"],
    refresh_entitlement: ["project_id"],
    run_readiness_check: ["project_id"],
    queue_for_mint_review: ["project_id"],
    repair_record: ["project_id"],
    refresh_case_data: [],
  };

  const ACTION_TIERS = {
    sync_package: "primary",
    repair_record: "primary",
    queue_for_mint_review: "primary",
    normalize_package: "secondary",
    assign_lane: "secondary",
    link_order_to_project: "secondary",
    generate_entitlement: "secondary",
    refresh_entitlement: "secondary",
    run_readiness_check: "utility",
    refresh_case_data: "utility",
  };

  function normalizeValue(value) {
    return String(value || "").trim();
  }

  function normalizeLower(value) {
    return normalizeValue(value).toLowerCase();
  }

  function normalizeRole(value) {
    const normalized = normalizeLower(value);
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

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function openDialog(node) {
    if (!(node instanceof HTMLDialogElement)) return;
    if (typeof node.showModal === "function") {
      if (!node.open) node.showModal();
      return;
    }
    node.setAttribute("open", "open");
  }

  function closeDialog(node) {
    if (!(node instanceof HTMLDialogElement)) return;
    if (typeof node.close === "function" && node.open) {
      node.close();
      return;
    }
    node.removeAttribute("open");
  }

  function dialogByName(name) {
    const selectors = {
      create: "[data-admin-create-dialog]",
      lifecycle: "[data-admin-lifecycle-dialog]",
      team: "[data-admin-team-dialog]",
    };
    const selector = selectors[name];
    return selector ? document.querySelector(selector) : null;
  }

  function fieldValue(selector) {
    const node = document.querySelector(selector);
    return normalizeValue(node && node.value);
  }

  function renderChipList(values, emptyLabel) {
    const items = asArray(values).filter(Boolean);
    if (!items.length) return `<span class="admin-scope-empty">${escapeHtml(emptyLabel || "None")}</span>`;
    return items
      .map(function (item) {
        return `<span class="admin-scope-chip">${escapeHtml(titleize(item))}</span>`;
      })
      .join("");
  }

  function setButtonEnabled(button, enabled) {
    if (!(button instanceof HTMLButtonElement)) return;
    button.disabled = !enabled;
    button.setAttribute("aria-disabled", enabled ? "false" : "true");
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch (_error) {
      return String(value);
    }
  }

  function setPageStatus(message, type) {
    state.lastStatusMessage = normalizeValue(message);
    document.documentElement.dataset.adminLastStatus = state.lastStatusMessage;
    app.setStatus(document.querySelector("[data-admin-control-action-status]"), message, type);
  }

  function extractErrorMessage(error, fallback) {
    const nested =
      (error && (error.detail || error.message || error.error || error.reason)) ||
      (error && error.responseBody && (error.responseBody.detail || error.responseBody.message)) ||
      fallback;
    return normalizeValue(nested) || fallback;
  }

  function actionableError(code, operation, endpoint, error) {
    const safeOperation = normalizeValue(operation) || "Request";
    const safeEndpoint = normalizeValue(endpoint);
    const message = extractErrorMessage(error, "Unknown service failure.");
    const endpointDetail = safeEndpoint ? ` Endpoint: ${safeEndpoint}.` : "";
    return `${safeOperation} failed (${code}). ${message}.${endpointDetail} Use Refresh to retry.`;
  }

  function clearPageStatus() {
    app.clearStatus(document.querySelector("[data-admin-control-action-status]"));
  }

  function getSearchValue() {
    const node = document.querySelector("[data-admin-case-search]");
    return normalizeValue(node && node.value);
  }

  function getInternalRoleKey(me) {
    const roleCodes = Array.isArray(me && me.role_codes) ? me.role_codes : [];
    const values = [
      normalizeRole(me && me.access_tier),
      normalizeRole(me && me.department_role),
      normalizeRole(me && me.role),
      ...roleCodes.map(normalizeRole),
    ].filter(Boolean);
    const direct = values.find(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });
    if (direct) return direct;
    if (typeof app.isInternalRole === "function" && app.isInternalRole(me)) return "admin";
    return "";
  }

  function normalizeAccessList(values) {
    return Array.isArray(values)
      ? values.map(normalizeLower).filter(Boolean)
      : [];
  }

  function isAllowedQueue(queue) {
    const normalized = normalizeLower(queue);
    return state.allowedQueues.includes(normalized);
  }

  function isAllowedTab(tab) {
    const normalized = normalizeLower(tab);
    const backendKey = normalizeLower(TAB_BACKEND_KEY[normalized] || normalized);
    return state.allowedTabs.includes(backendKey);
  }

  function isAllowedCaseAction(action) {
    const normalized = normalizeLower(action);
    return state.allowedActions.includes(normalized);
  }

  function isAllowedBulkAction(action) {
    const normalized = normalizeLower(action);
    return state.allowedBulkActions.includes(normalized);
  }

  function isMarketingRole() {
    return state.roleKey === "marketing_admin";
  }

  function isOperationsRole() {
    return state.roleKey === "operations_admin";
  }

  async function loadAccessProfile() {
    const profile = await fetchJson("/admin/control-center/access-profile");
    state.accessProfile = profile || {};
    const profileRoleKey = normalizeRole(profile && profile.role_key);
    state.roleKey = profileRoleKey ? profileRoleKey : (state.roleKey || DEFAULT_ROLE_KEY);
    state.allowedQueues = normalizeAccessList(profile && profile.allowed_queues);
    state.allowedTabs = normalizeAccessList(profile && profile.allowed_tabs);
    state.allowedActions = normalizeAccessList(profile && profile.allowed_actions);
    state.allowedBulkActions = normalizeAccessList(profile && profile.allowed_bulk_actions);
    state.isSuperAdmin = Boolean(profile && profile.is_super_admin);
    state.accessProfileLoadFailed = false;
    updateGlobalAdminControls();

    if (!isAllowedQueue(state.queue)) {
      state.queue = state.allowedQueues[0] || "overview";
    }
    if (!isAllowedTab(state.selectedTab)) {
      const preferredTabs = Object.keys(TAB_BACKEND_KEY);
      state.selectedTab =
        preferredTabs.find(function (tab) {
          return isAllowedTab(tab);
        }) || "overview";
    }
  }

  async function loadPackageOptions() {
    if (state.packageOptions.length) return;
    try {
      const payload = await fetchJson("/packages/catalog");
      const packages = payload && payload.packages ? payload.packages : {};
      state.packageOptions = Object.keys(packages)
        .map(function (code) {
          const item = packages[code] || {};
          return {
            code,
            label: item.display_name || code,
          };
        })
        .sort(function (a, b) {
          return a.label.localeCompare(b.label);
        });
    } catch (_error) {
      state.packageOptions = [];
    }
  }

  async function loadTeamAccessBlueprint(force) {
    if (!state.isSuperAdmin) return null;
    if (state.teamAccess.loaded && !force) return state.teamAccess;
    const payload = await fetchJson("/admin/control-center/super-admin/officers");
    state.teamAccess = {
      officers: asArray(payload && payload.items),
      roleTemplates:
        payload && payload.role_templates && typeof payload.role_templates === "object"
          ? payload.role_templates
          : {},
      ceoIdentity: payload && payload.ceo_identity ? payload.ceo_identity : null,
      loaded: true,
    };
    return state.teamAccess;
  }

  function shortId(value) {
    const id = normalizeValue(value);
    if (!id) return "—";
    return id.length > 13 ? `…${id.slice(-10)}` : id;
  }

  function laneChip(lane) {
    const normalized = normalizeLower(lane);
    const cls = ["portrait", "household", "network", "organization"].includes(normalized)
      ? normalized
      : "default";
    return `<span class="admin-lane-chip admin-lane-chip--${escapeHtml(cls)}">${escapeHtml(normalized || "unknown")}</span>`;
  }

  function statusChip(label, cls) {
    return `<span class="admin-status-chip admin-status-chip--${escapeHtml(cls || "default")}">${escapeHtml(label || "unknown")}</span>`;
  }

  function humanize(value) {
    return normalizeValue(value)
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function titleize(value) {
    const text = humanize(value);
    if (!text) return "—";
    return text.replace(/\b\w/g, function (letter) {
      return letter.toUpperCase();
    });
  }

  function chipClassForValue(value) {
    const normalized = normalizeLower(value);
    if (["yes", "ready", "linked", "exists", "eligible", "minted", "mint_ready", "active", "paid", "complete", "completed", "succeeded", "success", "files_present"].includes(normalized)) {
      return "success";
    }
    if (["no", "blocked", "missing", "not_linked", "unknown", "failed", "error", "waiting_for_uploads", "not_ready"].includes(normalized)) {
      return "error";
    }
    return "default";
  }

  function getSelectedCase() {
    return (state.cases || []).find(function (item) {
      return item.case_id === state.selectedCaseId;
    });
  }

  function getWorkspaceContext(selected) {
    const workspace = state.workspace && state.workspace.case_id === state.selectedCaseId ? state.workspace : null;
    const tabs = (workspace && workspace.tabs) || {};
    const identity = tabs.identity || {};
    const packageTab = tabs.package_lane || {};
    const projectTab = tabs.project || {};
    const mintTab = tabs.mint_readiness || {};
    const project = (workspace && workspace.project) || {};
    const packageInfo = (workspace && workspace.package) || {};
    const readiness = (workspace && workspace.readiness) || {};
    const selectedFallback = selected || {};
    const blocking = Array.isArray(mintTab.blocking_reasons)
      ? mintTab.blocking_reasons
      : Array.isArray(readiness.blocking_reasons)
        ? readiness.blocking_reasons
        : Array.isArray(selectedFallback.mint_blocking_reasons)
          ? selectedFallback.mint_blocking_reasons
          : [];

    return {
      workspace,
      caseId: (workspace && workspace.case_id) || selectedFallback.case_id || "",
      name:
        identity.full_name ||
        project.name ||
        project.project_name ||
        selectedFallback.name ||
        selectedFallback.project ||
        "Customer Case",
      email: identity.email || selectedFallback.email || "",
      projectName:
        projectTab.project_name ||
        project.name ||
        project.project_name ||
        "",
      packageName:
        packageTab.package_name ||
        packageInfo.package_name ||
        selectedFallback.package_name ||
        selectedFallback.package ||
        "Unknown Package",
      packageCode:
        packageTab.package_code ||
        packageInfo.package_code ||
        selectedFallback.package_code ||
        "",
      lane:
        packageTab.project_lane ||
        packageTab.lane ||
        projectTab.project_lane ||
        projectTab.lane ||
        selectedFallback.lane ||
        "",
      status:
        projectTab.build_status ||
        project.status ||
        selectedFallback.status ||
        "unknown",
      alerts: workspace ? workspace.alerts || [] : selectedFallback.alerts || [],
      guidance: getGuidanceItems(workspace ? workspace.operator_guidance : selectedFallback.operator_guidance),
      blocking,
    };
  }

  function getActionScope(selected) {
    const workspace = state.workspace && state.workspace.case_id === state.selectedCaseId ? state.workspace : null;
    const selectedFallback = selected || {};
    if (!workspace) {
      return {
        project_id: selectedFallback.project_id || "",
        order_id: selectedFallback.order_id || "",
      };
    }

    const tabs = workspace.tabs || {};
    const projectTab = tabs.project || {};
    const ordersTab = tabs.orders_billing || {};
    const primaryOrder = ordersTab.primary_order || {};
    const project = workspace.project || {};
    const order = workspace.order || {};

    return {
      project_id: projectTab.project_id || project.id || project.project_id || "",
      order_id: order.id || primaryOrder.id || "",
    };
  }

  function renderScalar(value) {
    if (value == null || value === "") return "—";
    if (typeof value === "boolean") return value ? "yes" : "no";
    return String(value);
  }

  function renderFieldGrid(fields) {
    return `
      <div class="admin-field-grid">
        ${fields
          .map(function (field) {
            const value = field.value;
            const isChip = field.chip || typeof value === "boolean";
            return `
              <div class="admin-field">
                <span>${escapeHtml(field.label)}</span>
                <strong class="${field.mono ? "admin-id-ref" : ""}">
                  ${
                    isChip
                      ? statusChip(titleize(renderScalar(value)), chipClassForValue(value))
                      : escapeHtml(renderScalar(value))
                  }
                </strong>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function renderStatusStack(items, emptyLabel) {
    const values = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!values.length) {
      return statusChip(emptyLabel || "none", "success");
    }
    return values
      .map(function (item) {
        return statusChip(titleize(item), "error");
      })
      .join(" ");
  }

  function renderWarningStrip(warnings) {
    const values = Array.isArray(warnings) ? warnings.filter(Boolean) : [];
    if (!values.length) return "";
    return `
      <div class="admin-warning-strip">
        <span>Warnings</span>
        <div>${renderStatusStack(values)}</div>
      </div>
    `;
  }

  function getGuidanceItems(items) {
    return Array.isArray(items) ? items.filter(Boolean) : [];
  }

  function guidanceSeverityClass(value) {
    const severity = normalizeLower(value);
    if (["critical", "warning", "info"].includes(severity)) return severity;
    return "info";
  }

  function renderGuidanceList(items, emptyTitle, emptyCopy) {
    const guidance = getGuidanceItems(items);
    if (!guidance.length) {
      return `
        <div class="admin-guidance-empty">
          <strong>${escapeHtml(emptyTitle || "No active blockers")}</strong>
          <span>${escapeHtml(emptyCopy || "The selected case has no operational guidance at this moment.")}</span>
        </div>
      `;
    }
    return `
      <div class="admin-guidance-list">
        ${guidance
          .map(function (item) {
            const severityClass = guidanceSeverityClass(item.severity);
            return `
              <div class="admin-guidance-item admin-guidance-item--${escapeHtml(severityClass)}">
                <div>
                  <span>${escapeHtml(titleize(item.severity || "guidance"))}</span>
                  <strong>${escapeHtml(item.title || "Operator guidance")}</strong>
                </div>
                <p>${escapeHtml(item.rule || "Review the case state before proceeding.")}</p>
                <small>Next admin move: ${escapeHtml(item.next_action || "Run Readiness Check")}</small>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
  }

  async function fetchJson(path) {
    return app.apiRequest(path, { method: "GET" });
  }

  async function postJson(path, body) {
    return app.apiRequest(path, {
      method: "POST",
      body: JSON.stringify(body || {}),
    });
  }

  function kernelIdempotencyKey(action, target) {
    const suffix =
      window.crypto && typeof window.crypto.randomUUID === "function"
        ? window.crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const targetId = normalizeValue(
      target && (target.project_id || target.case_id || target.user_id || target.officer_email || target.target_id),
    );
    return `kernel-${normalizeLower(action).replaceAll("-", "_")}-${targetId || "bulk"}-${suffix}`;
  }

  function promptExecutionReason(label, defaultReason) {
    const reason = window.prompt(
      `${label}: enter the operational reason that will be attached to the evidence packet.`,
      defaultReason || "",
    );
    if (reason === null) return null;
    const normalized = normalizeValue(reason);
    if (normalized.length < 3) {
      setPageStatus("A reason of at least 3 characters is required for governed execution.", "error");
      return null;
    }
    return normalized;
  }

  async function submitGovernedOperation(action, target, parameters, reason) {
    if (!state.kernelStatus || !state.kernelStatus.execution_enabled) {
      throw new Error("Continuity Kernel execution is unavailable or disabled by the emergency kill switch.");
    }
    const normalizedAction = normalizeLower(action).replaceAll("-", "_");
    const fingerprint = JSON.stringify({
      action: normalizedAction,
      target: target || {},
      parameters: parameters || {},
      reason,
    });
    const idempotencyKey =
      state.kernelPendingIdempotency[fingerprint] || kernelIdempotencyKey(normalizedAction, target || {});
    state.kernelPendingIdempotency[fingerprint] = idempotencyKey;
    const payload = {
      action: normalizedAction,
      target: target || {},
      parameters: {
        ...(parameters || {}),
        continuity_idempotency_key: idempotencyKey,
      },
      reason,
      idempotency_key: idempotencyKey,
    };
    let operation;
    if (state.kernelStatus.one_step_execution_allowed) {
      operation = await postJson("/admin/control-center/kernel/execute", {
        ...payload,
        confirmed: true,
        solo_founder_override_acknowledged: true,
      });
    } else {
      operation = await postJson("/admin/control-center/kernel/operations", payload);
    }
    delete state.kernelPendingIdempotency[fingerprint];
    return operation;
  }

  function kernelOperationMessage(operation, completedLabel) {
    const payload = operation || {};
    if (Array.isArray(payload.blocked_reasons) && payload.blocked_reasons.length) {
      return `Operation ${shortId(payload.operation_id)} was blocked by preflight; no business write executed.`;
    }
    if (payload.state === "review_requested") {
      return `Governed operation ${shortId(payload.operation_id)} submitted for officer approval.`;
    }
    if (payload.execution_outcome === "partial_failure") {
      return `Operation ${shortId(payload.operation_id)} executed with ${payload.execution_failure_count || 0} recorded failure(s).`;
    }
    if (payload.evidence_recording_status === "incomplete") {
      return `Operation ${shortId(payload.operation_id)} executed, but secondary audit evidence is incomplete and requires review.`;
    }
    return `${completedLabel} Kernel operation ${shortId(payload.operation_id)} captured the execution evidence.`;
  }

  function kernelOperationStatusType(operation) {
    return operation &&
      ((Array.isArray(operation.blocked_reasons) && operation.blocked_reasons.length > 0) ||
        operation.execution_outcome === "partial_failure" ||
        operation.evidence_recording_status === "incomplete")
      ? "error"
      : "success";
  }

  function renderKernelStatus() {
    const node = document.querySelector("[data-admin-kernel-status]");
    const label = document.querySelector("[data-admin-kernel-status-label]");
    const meta = document.querySelector("[data-admin-kernel-status-meta]");
    if (!node || !label || !meta) return;
    const payload = state.kernelStatus;
    if (!payload) {
      node.dataset.state = "error";
      label.textContent = "Operational runtime unavailable";
      meta.textContent = " Governed writes are fail-closed.";
      return;
    }
    const enabled = Boolean(payload.execution_enabled);
    node.dataset.state = enabled ? "success" : "error";
    label.textContent = enabled ? "Operational execution enabled" : "Emergency kill switch active";
    const mode = payload.one_step_execution_allowed ? "CEO one-step execution" : "officer request workflow";
    meta.textContent = ` v${payload.runtime_version || "—"} · ${payload.action_count || 0} actions · ${mode}`;
  }

  function renderKernelOperations() {
    const node = document.querySelector("[data-admin-kernel-operations]");
    if (!node) return;
    const items = Array.isArray(state.kernelOperations) ? state.kernelOperations : [];
    if (!items.length) {
      node.innerHTML = '<p class="card-copy">No governed operations have been recorded yet.</p>';
      return;
    }
    node.innerHTML = items
      .map(function (operation) {
        const canApprove = Boolean(
            state.kernelStatus &&
            state.kernelStatus.one_step_execution_allowed &&
            operation.state === "review_requested" &&
            (!Array.isArray(operation.blocked_reasons) || operation.blocked_reasons.length === 0),
        );
        const canClose = Boolean(
          state.kernelStatus &&
            state.kernelStatus.one_step_execution_allowed &&
            operation.state === "apply_executed" &&
            operation.execution_outcome !== "partial_failure" &&
            operation.evidence_recording_status !== "incomplete",
        );
        return `
          <div class="admin-priority-repair-item">
            <span>
              ${escapeHtml(titleize(operation.action))}
              <small class="admin-id-ref">${escapeHtml(shortId(operation.target_id))}</small>
            </span>
            <strong>${escapeHtml(titleize(operation.state))}</strong>
            ${
              canApprove
                ? `<button class="btn btn-primary" type="button" data-admin-kernel-approve-execute="${escapeHtml(operation.operation_id)}">Approve + Execute</button>`
                : ""
            }
            ${
              canClose
                ? `<button class="btn btn-secondary" type="button" data-admin-kernel-close="${escapeHtml(operation.operation_id)}">Close Audit</button>`
                : ""
            }
          </div>
        `;
      })
      .join("");
  }

  async function loadKernelOperations() {
    if (!state.kernelStatus) {
      state.kernelOperations = [];
      renderKernelOperations();
      return;
    }
    try {
      const payload = await fetchJson("/admin/control-center/kernel/operations?limit=12");
      state.kernelOperations = Array.isArray(payload && payload.items) ? payload.items : [];
    } catch (_error) {
      state.kernelOperations = [];
    }
    renderKernelOperations();
  }

  async function loadKernelStatus() {
    try {
      state.kernelStatus = await fetchJson("/admin/control-center/kernel/status");
    } catch (_error) {
      state.kernelStatus = null;
    }
    renderKernelStatus();
    await loadKernelOperations();
  }

  async function approveAndExecuteKernelOperation(operationId) {
    const reason = promptExecutionReason("Approve and execute this governed operation");
    if (reason === null) return;
    if (!window.confirm("Approve and execute this operation against live business records?")) return;
    setPageStatus("Approving and executing governed operation...", "info");
    try {
      await postJson(`/admin/control-center/kernel/operations/${encodeURIComponent(operationId)}/approve`, {
        approval_reason: reason,
        solo_founder_override_acknowledged: true,
      });
      const operation = await postJson(
        `/admin/control-center/kernel/operations/${encodeURIComponent(operationId)}/execute`,
        {},
      );
      await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
      setPageStatus(
        kernelOperationMessage(operation, "Execution completed."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to approve and execute the governed operation.", "error");
    }
  }

  async function closeKernelOperation(operationId) {
    if (!window.confirm("Close the audit record for this completed operation?")) return;
    try {
      await postJson(`/admin/control-center/kernel/operations/${encodeURIComponent(operationId)}/close`, {});
      await loadKernelStatus();
      setPageStatus("Continuity operation audit closed.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to close the Continuity audit record.", "error");
    }
  }

  async function loadActiveImpersonation() {
    if (!state.isSuperAdmin) {
      state.activeImpersonation = null;
      return;
    }
    try {
      const payload = await fetchJson("/admin/control-center/super-admin/impersonation/active");
      state.activeImpersonation = payload && payload.active ? payload : null;
    } catch (_error) {
      state.activeImpersonation = null;
    }
    renderImpersonationBanner();
  }

  function renderDiagnostics(payload) {
    const section = document.querySelector("[data-admin-diagnostics-section]");
    const output = document.querySelector("[data-admin-diagnostics-output]");
    if (!section || !output) return;
    // The diagnostics section becomes available but stays collapsed by
    // default; it sits in normal document flow and never overlays cases.
    section.hidden = false;
    const data = payload || {};
    state.diagnostics = data;
    renderStatusSummary();
    const rows = [
      ["Authenticated user ID", data.user_id],
      ["Normalized role", data.role_key],
      ["CEO Master Admin recognized", data.is_ceo_master_admin ? "yes" : "no"],
      ["Wildcard permission status", data.is_wildcard ? "granted" : "not granted"],
      ["Queue-scope mode", data.queue_scope_mode],
      ["Bootstrap endpoint status", data.bootstrap_endpoint_status],
      ["Search endpoint status", data.search_endpoint_status],
      ["Frontend revision", data.frontend_revision],
      ["Backend revision", data.backend_revision],
    ];
    output.innerHTML = rows
      .map(function (row) {
        return `<div><dt>${escapeHtml(row[0])}</dt><dd>${escapeHtml(String(row[1] ?? "unknown"))}</dd></div>`;
      })
      .join("");
  }

  async function loadDiagnostics() {
    if (!state.isSuperAdmin) return;
    try {
      const payload = await fetchJson("/admin/control-center/diagnostics");
      renderDiagnostics(payload);
    } catch (error) {
      console.error("Diagnostics load failed:", error);
      renderDiagnostics({
        role_key: state.roleKey,
        bootstrap_endpoint_status: "unavailable",
        search_endpoint_status: "unavailable",
      });
    }
  }

  function roleDisplayLabel(roleKey) {
    const labels = {
      ceo_master_admin: "CEO Master Administrator",
      finance_admin: "Finance Administrator (CFO)",
      operations_admin: "Operations Administrator (COO)",
      marketing_admin: "Marketing Administrator (CMO)",
    };
    return labels[roleKey] || "Administrator";
  }

  function renderStatusSummary() {
    const summary = document.querySelector("[data-admin-status-summary]");
    if (!summary) return;
    const data = state.diagnostics || {};
    const bootstrapOk = (data.bootstrap_endpoint_status || "") === "ok";
    const searchOk = (data.search_endpoint_status || "") === "ok";
    const chips = [
      ["System Ready", bootstrapOk],
      ["CEO Role Verified", Boolean(data.is_ceo_master_admin)],
      ["Search Ready", searchOk],
      ["Metrics Ready", !state.overviewLoadFailed],
      [
        state.bootstrapFailed ? "Payments Attention Required" : "Payments Ready",
        !state.bootstrapFailed,
      ],
    ];
    summary.innerHTML = chips
      .map(function (chip) {
        return `<span class="admin-status-chip" data-state="${chip[1] ? "ok" : "attention"}">${escapeHtml(chip[0])}</span>`;
      })
      .join("");
  }

  function toggleDiagnosticsPanel() {
    const panel = document.querySelector("[data-admin-diagnostics-panel]");
    const toggle = document.querySelector("[data-admin-diagnostics-toggle]");
    if (!panel || !toggle) return;
    const expanded = panel.hidden;
    panel.hidden = !expanded;
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    toggle.textContent = expanded ? "Hide System Diagnostics" : "Show System Diagnostics";
  }

  const FULFILLMENT_ACTION_LABELS = {
    verify_payment: "Verify Payment",
    start_fulfillment: "Mark Fulfillment In Progress",
    assign_package: "Assign Purchased Package",
    complete_fulfillment: "Mark Fulfillment Complete",
    escalate_mismatch: "Escalate Payment Mismatch",
  };

  function renderFulfillmentQueue() {
    const list = document.querySelector("[data-admin-case-list]");
    if (!list) return;
    const items = state.fulfillmentItems || [];
    if (!items.length) {
      list.innerHTML = `<div class="family-record-card admin-card"><h3>No paid orders waiting</h3><p class="card-copy">Verified purchases requiring manual fulfillment will appear here.</p></div>`;
      return;
    }
    list.innerHTML = items
      .map(function (item) {
        const actionButtons = Object.keys(FULFILLMENT_ACTION_LABELS)
          .map(function (action) {
            return `<button class="btn btn-secondary" type="button" data-fulfillment-action="${action}" data-fulfillment-order="${escapeHtml(item.order_id)}">${escapeHtml(FULFILLMENT_ACTION_LABELS[action])}</button>`;
          })
          .join("");
        return `
          <div class="family-record-card admin-card admin-fulfillment-card">
            <h3>${escapeHtml(item.customer_name || item.email || "Unknown customer")}</h3>
            <p class="card-copy">${escapeHtml(item.email || "no email")} · ${escapeHtml(item.package_name || item.package_code || "unknown package")} · ${escapeHtml(item.amount_label || "amount unknown")} ${escapeHtml((item.currency || "usd").toUpperCase())}</p>
            <dl class="admin-diagnostics-grid">
              <div><dt>Order</dt><dd>${escapeHtml(item.order_id)}</dd></div>
              <div><dt>Stripe session</dt><dd>${escapeHtml(item.stripe_session_id || "none")}</dd></div>
              <div><dt>Payment intent</dt><dd>${escapeHtml(item.stripe_payment_intent_id || "none")}</dd></div>
              <div><dt>Payment status</dt><dd>${escapeHtml(item.payment_status || "unknown")}${item.payment_verified ? " (verified)" : " (not verified)"}</dd></div>
              <div><dt>Billing plan</dt><dd>${escapeHtml(item.billing_plan || "one_time")}</dd></div>
              <div><dt>Coupon</dt><dd>${escapeHtml(item.coupon || "none")}</dd></div>
              <div><dt>Payment date</dt><dd>${escapeHtml(item.payment_date || "unknown")}</dd></div>
              <div><dt>Fulfillment status</dt><dd>${escapeHtml(item.fulfillment_status || "pending_manual_fulfillment")}</dd></div>
              <div><dt>Linked project</dt><dd>${escapeHtml(item.linked_project_id || "none")}</dd></div>
              <div><dt>Entitlement</dt><dd>${escapeHtml(item.entitlement_status || "unknown")}</dd></div>
              <div><dt>Assigned operator</dt><dd>${escapeHtml(item.assigned_operator || "unassigned")}</dd></div>
              <div><dt>Next required action</dt><dd>${escapeHtml(item.next_required_action || "verify_payment")}</dd></div>
            </dl>
            <div class="admin-bulk-action-grid">${actionButtons}</div>
          </div>`;
      })
      .join("");
  }

  async function loadFulfillmentQueue() {
    setPageStatus("Loading paid manual fulfillment queue...", "info");
    try {
      const payload = await fetchJson("/admin/control-center/fulfillment/queue");
      state.fulfillmentItems = Array.isArray(payload.items) ? payload.items : [];
      renderFulfillmentQueue();
      clearPageStatus();
    } catch (error) {
      setPageStatus(error.message || "Unable to load fulfillment queue.", "error");
    }
  }

  async function runFulfillmentAction(orderId, action) {
    const label = FULFILLMENT_ACTION_LABELS[action] || action;
    const reason = window.prompt(`${label}: enter a reason for the audit record.`);
    if (reason === null) return;
    if (!reason || reason.trim().length < 3) {
      setPageStatus("A reason of at least 3 characters is required.", "error");
      return;
    }
    if (!window.confirm(`Submit ${label.toLowerCase()} to the Continuity Kernel for live execution?`)) return;
    setPageStatus(`Running ${label.toLowerCase()}...`, "info");
    try {
      const operation = await submitGovernedOperation(
        "manual_fulfillment",
        { order_id: orderId },
        { fulfillment_action: action },
        reason.trim(),
      );
      await Promise.allSettled([loadKernelStatus(), loadFulfillmentQueue()]);
      setPageStatus(
        kernelOperationMessage(operation, `${label} completed.`),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || `${label} failed.`, "error");
    }
  }

  function renderStripeOpsCard(workspace, tabData) {
    const identity = (workspace && workspace.tabs && workspace.tabs.identity) || {};
    const email = identity.email || "";
    const subscriptionId = (tabData && (tabData.subscription || (tabData.primary_order || {}).subscription_id)) || "";
    return `
      <article class="admin-dossier-card admin-dossier-card--wide" data-stripe-ops-card>
        <div class="admin-card-header"><span class="admin-card-badge">$</span><h3 class="admin-card-title">Stripe Operations</h3></div>
        <p class="card-copy">Server-side Stripe actions for this customer. Every action requires a reason and is audit logged.</p>
        <div class="admin-field-grid">
          <label class="admin-field"><span>Customer Email</span><input type="email" data-stripe-ops-field="customer_email" value="${escapeHtml(email)}" /></label>
          <label class="admin-field"><span>Reason (required)</span><input type="text" data-stripe-ops-field="reason" placeholder="Why are you doing this?" /></label>
          <label class="admin-field"><span>Stripe Price ID (links / subscriptions)</span><input type="text" data-stripe-ops-field="price_id" placeholder="price_..." /></label>
          <label class="admin-field"><span>Subscription ID</span><input type="text" data-stripe-ops-field="subscription_id" value="${escapeHtml(subscriptionId)}" placeholder="sub_..." /></label>
          <label class="admin-field"><span>Invoice ID (retry)</span><input type="text" data-stripe-ops-field="invoice_id" placeholder="in_..." /></label>
          <label class="admin-field"><span>Invoice Amount (cents)</span><input type="number" min="1" data-stripe-ops-field="amount_cents" placeholder="e.g. 250000" /></label>
          <label class="admin-field"><span>Invoice Description</span><input type="text" data-stripe-ops-field="description" placeholder="What is being invoiced" /></label>
        </div>
        <div class="inline-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="ensure_customer">Ensure Stripe Customer</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="open_customer">Open in Stripe</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="payment_link">Create Payment Link</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="invoice">Create + Send Invoice</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="invoice_retry">Retry Invoice</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="subscription_create">Create Subscription</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="subscription_change">Change Subscription Price</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="subscription_pause">Pause Subscription</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="subscription_resume">Resume Subscription</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="subscription_cancel">Cancel Subscription</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="payment_method_link">Send Payment-Method Update Link</button>
          <button class="btn btn-secondary" type="button" data-stripe-ops-action="history">Payment History</button>
        </div>
        <div class="admin-record-list" data-stripe-ops-result style="margin-top: 0.75rem;"></div>
      </article>
    `;
  }

  function stripeOpsField(card, name) {
    const input = card.querySelector(`[data-stripe-ops-field="${name}"]`);
    return input ? String(input.value || "").trim() : "";
  }

  function renderStripeOpsResult(card, payload) {
    const node = card.querySelector("[data-stripe-ops-result]");
    if (!node) return;
    node.innerHTML = `<pre style="white-space: pre-wrap; word-break: break-word; margin: 0;">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
  }

  async function runStripeOpsAction(card, action) {
    const email = stripeOpsField(card, "customer_email");
    const reason = stripeOpsField(card, "reason");
    const needsReason = action !== "open_customer" && action !== "history";
    if (needsReason && reason.length < 3) {
      setPageStatus("A reason of at least 3 characters is required for Stripe operations.", "error");
      return;
    }
    setPageStatus("Running Stripe operation...", "info");
    try {
      let result;
      if (action === "open_customer") {
        result = await fetchJson(`/admin/stripe-ops/customers/open?customer_email=${encodeURIComponent(email)}`);
        if (result && result.dashboard_url) window.open(result.dashboard_url, "_blank", "noopener");
      } else if (action === "history") {
        result = await fetchJson(`/admin/stripe-ops/customers/history?customer_email=${encodeURIComponent(email)}`);
      } else {
        if (action === "subscription_cancel") {
          if (!window.confirm("Cancel this subscription? This is a destructive action.")) {
            setPageStatus("Subscription cancel aborted.", "info");
            return;
          }
        }
        if (!window.confirm("Submit this Stripe operation to the Continuity Kernel for live execution?")) return;
        const parameters = {
          stripe_action: action,
          customer_email: email,
          price_id: stripeOpsField(card, "price_id"),
          subscription_id: stripeOpsField(card, "subscription_id"),
          invoice_id: stripeOpsField(card, "invoice_id"),
          amount_cents: Number(stripeOpsField(card, "amount_cents")) || 0,
          description: stripeOpsField(card, "description"),
          at_period_end: true,
          confirm: action === "subscription_cancel",
        };
        const targetId =
          parameters.subscription_id ||
          parameters.invoice_id ||
          email ||
          parameters.price_id ||
          action;
        const operation = await submitGovernedOperation(
          "stripe_operation",
          { target_id: targetId },
          parameters,
          reason,
        );
        result = operation.execution_result || operation.proposed_after_snapshot || operation;
        await loadKernelStatus();
        setPageStatus(
          kernelOperationMessage(operation, "Stripe operation completed."),
          kernelOperationStatusType(operation),
        );
      }
      renderStripeOpsResult(card, result);
      if (action === "open_customer" || action === "history") {
        setPageStatus("Stripe read-only operation completed.", "success");
      }
    } catch (error) {
      setPageStatus(error.message || "Stripe operation failed.", "error");
    }
  }

  function formatExpirationCountdown(value) {
    if (!value) return "unknown expiry";
    const expiresAt = new Date(value).getTime();
    if (!Number.isFinite(expiresAt)) return "unknown expiry";
    const diffMs = expiresAt - Date.now();
    if (diffMs <= 0) return "expired";
    const totalMinutes = Math.ceil(diffMs / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours > 0 ? `${hours}h ${minutes}m remaining` : `${minutes}m remaining`;
  }

  function renderImpersonationBanner() {
    const node = document.querySelector("[data-admin-impersonation-banner]");
    if (!node) return;
    const session = state.activeImpersonation;
    if (!session || !session.active) {
      node.innerHTML = "";
      node.hidden = true;
      return;
    }
    node.hidden = false;
    const statusLabel = session.editing_enabled ? "editing enabled" : "read-only";
    const project = session.project_id ? shortId(session.project_id) : "no linked project";
    const expires = formatExpirationCountdown(session.expires_at);
    node.innerHTML = `
      <div class="admin-warning-strip" style="margin-top:0.75rem;">
        <span>Impersonation Active</span>
        <div>
          <strong>${escapeHtml(session.banner || "Read-only customer context")}</strong>
          <span class="admin-id-ref" style="margin-left:0.5rem;">project ${escapeHtml(project)}</span>
          <span style="margin-left:0.5rem;">${escapeHtml(statusLabel)}</span>
          <span style="margin-left:0.5rem;">${escapeHtml(expires)}</span>
        </div>
      </div>
    `;
  }

  function startImpersonationTicker() {
    window.clearInterval(state.impersonationTicker);
    state.impersonationTicker = window.setInterval(function () {
      if (!state.activeImpersonation || !state.activeImpersonation.active) return;
      renderImpersonationBanner();
    }, 30000);
  }

  function renderTopSummary(summary, financeSections, marketingSections) {
    const node = document.querySelector("[data-admin-top-summary]");
    if (!node) return;
    if (state.overviewLoadFailed) {
      node.innerHTML = [
        "Total Users",
        "Active Projects",
        "Paid Orders",
        "Missing Entitlements",
        "Mint-Ready Projects",
        "Data Mismatches",
      ]
        .map(function (label) {
          return `
            <div class="admin-summary-tile">
              <span>${escapeHtml(label)}</span>
              <strong>Unavailable</strong>
            </div>
          `;
        })
        .join("");
      return;
    }
    const isMarketing = isMarketingRole();
    const isOpsRole = isOperationsRole();
    const isFinanceRole = state.roleKey === "finance_admin";
    const moneyNow = (financeSections && financeSections.money_now) || {};
    const traffic = (marketingSections && marketingSections.traffic_awareness) || {};
    const funnel = (marketingSections && marketingSections.funnel_conversion) || {};
    const campaign = (marketingSections && marketingSections.campaign_performance) || {};
    const packageDemand = (marketingSections && marketingSections.package_demand) || {};
    const cards = isFinanceRole
      ? [
          ["Gross Revenue", moneyNow.gross_revenue],
          ["Net Revenue", moneyNow.net_revenue],
          ["Collected Today", moneyNow.collected_today],
          ["Collected Month", moneyNow.collected_month],
          ["Refunds This Month", moneyNow.refunds_this_month],
          ["Failed Payments", moneyNow.failed_payments],
          ["Unpaid Balances", moneyNow.unpaid_balances],
        ]
      : isMarketing
        ? [
            ["Visitors", (traffic.visitors || {}).live ? (traffic.visitors || {}).value : "unavailable"],
            ["Sessions", (traffic.sessions || {}).live ? (traffic.sessions || {}).value : "unavailable"],
            ["CTA Clicks", (funnel.cta_clicks || {}).live ? (funnel.cta_clicks || {}).value : "unavailable"],
            ["Purchases", (funnel.purchases_completed || {}).live ? (funnel.purchases_completed || {}).value : "unavailable"],
            ["Campaign Visits", (campaign.campaign_visits || {}).live ? (campaign.campaign_visits || {}).value : "unavailable"],
            ["Package Conversion %", (packageDemand.package_conversion_rate || {}).live ? (packageDemand.package_conversion_rate || {}).value : "unavailable"],
          ]
        : isOpsRole
          ? [
              ["Intake Started", (((state.operationsSections || {}).intake_onboarding || {}).intake_started || {}).value || 0],
              ["Verification Pending", (((state.operationsSections || {}).verification_upload_review || {}).verification_pending || {}).value || 0],
              ["Pending Invites", (((state.operationsSections || {}).workspace_access_invites || {}).pending_invites || {}).value || 0],
              ["Blocked Projects", (((state.operationsSections || {}).build_fulfillment || {}).blocked_projects || {}).value || 0],
              ["Manual Review Queue", (((state.operationsSections || {}).exceptions_escalations || {}).manual_review_queue || {}).value || 0],
              ["Queue Totals", (((state.operationsSections || {}).ops_reports || {}).queue_totals || {}).value || 0],
            ]
          : [
          ["Total Users", summary.total_users],
          ["Active Projects", summary.total_active_projects],
          ["Paid Orders", summary.paid_orders],
          ["Missing Entitlements", summary.missing_entitlements],
          ["Mint-Ready Projects", summary.mint_ready_projects],
          ["Data Mismatches", summary.projects_with_data_mismatch],
            ];
    node.innerHTML = cards
      .map(function (item, index) {
        return `
          <div class="admin-summary-tile">
            <span>${escapeHtml(item[0])}</span>
            <strong>${escapeHtml(String(item[1] ?? 0))}</strong>
          </div>
        `;
      })
      .join("");
  }

  function renderPriorityRepairs(priority, financeSections, marketingSections) {
    const node = document.querySelector("[data-admin-priority-repairs]");
    if (!node) return;
    if (state.overviewLoadFailed) {
      node.innerHTML = `
        <div class="admin-priority-repair-item">
          <span>Admin metrics status</span>
          <strong>Unavailable</strong>
        </div>
      `;
      return;
    }
    const isMarketing = isMarketingRole();
    const isOpsRole = isOperationsRole();
    const isFinanceRole = state.roleKey === "finance_admin";
    const financeIntegrity = (financeSections && financeSections.finance_integrity) || {};
    const payroll = (financeSections && financeSections.payroll) || {};
    const reports = (marketingSections && marketingSections.marketing_reports) || {};
    const reportEntries = Object.entries(reports);
    const cards = isFinanceRole
      ? [
          ["Unlinked Payments", financeIntegrity.unlinked_payments || 0],
          ["Order/Project Mismatch", financeIntegrity.order_project_mismatch || 0],
          ["Entitlement Mismatch", financeIntegrity.entitlement_mismatch || 0],
          ["Refunded but Access Active", financeIntegrity.refunded_but_still_active_access || 0],
          ["Manual Override Log", financeIntegrity.manual_override_log || 0],
          ["Pending Payroll Review", payroll.pending_payroll_review || 0],
        ]
      : isMarketing
        ? reportEntries.map(function (entry) {
            const key = entry[0];
            const value = entry[1] || {};
            return [titleize(key), value.available ? "live" : "unavailable"];
          })
        : isOpsRole
          ? [
              ["Stuck Intake", (((state.operationsSections || {}).intake_onboarding || {}).stuck_intake || {}).value || 0],
              ["Aging Verification Queue", (((state.operationsSections || {}).verification_upload_review || {}).aging_verification_queue || {}).value || 0],
              ["Failed Invite Deliveries", (((state.operationsSections || {}).workspace_access_invites || {}).failed_invite_deliveries || {}).value || 0],
              ["Waiting on Customer", (((state.operationsSections || {}).build_fulfillment || {}).waiting_on_customer || {}).value || 0],
              ["Stuck Linkage", (((state.operationsSections || {}).exceptions_escalations || {}).stuck_linkage || {}).value || 0],
              ["Exec Escalations", (((state.operationsSections || {}).exceptions_escalations || {}).projects_needing_executive_escalation || {}).value || 0],
            ]
          : [
          ["Paid order without project link", (priority.paid_order_without_project_link || []).length],
          ["Project without entitlement", (priority.project_without_entitlement || []).length],
          ["Package without lane", (priority.package_without_lane || []).length],
          ["Mint-eligible blocked", (priority.mint_eligible_blocked || []).length],
            ];
    node.innerHTML = cards
      .map(function (item) {
        return `
          <div class="admin-priority-repair-item">
            <span>${escapeHtml(item[0])}</span>
            <strong>${escapeHtml(String(item[1]))}</strong>
          </div>
        `;
      })
      .join("");
  }

  async function loadOverview() {
    try {
      const payload = await fetchJson("/admin/control-center/overview?limit=24");
      state.overviewLoadFailed = false;
      state.marketingSections = payload.marketing_sections || {};
      state.operationsSections = payload.operations_sections || {};
      renderTopSummary(payload.summary || {}, payload.finance_sections || {}, payload.marketing_sections || {});
      renderPriorityRepairs(payload.priority_repairs || {}, payload.finance_sections || {}, payload.marketing_sections || {});
      if (isMarketingRole()) renderMarketingQueuePanel();
    } catch (error) {
      console.error("Overview load failed:", error);
      state.overviewLoadFailed = true;
      state.marketingSections = {};
      state.operationsSections = {};
      renderTopSummary({}, {}, {});
      renderPriorityRepairs({}, {}, {});
      if (isMarketingRole()) renderMarketingQueuePanel();
    }
  }

  function renderMarketingMetric(label, metric) {
    const payload = metric || {};
    const isLive = Boolean(payload.live);
    const value = isLive ? payload.value : "Unavailable";
    const note = !isLive && payload.status_note ? `<p class="card-copy">${escapeHtml(payload.status_note)}</p>` : "";
    const displayValue =
      value && typeof value === "object"
        ? `<pre class="card-copy">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`
        : `<strong>${escapeHtml(String(value ?? "—"))}</strong>`;
    return `
      <article class="admin-dossier-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">${isLive ? "L" : "N"}</span>
          <h3 class="admin-card-title">${escapeHtml(label)}</h3>
        </div>
        ${displayValue}
        ${!isLive ? '<p class="card-copy">Status: non-live</p>' : ""}
        ${note}
      </article>
    `;
  }

  function renderMarketingQueuePanel() {
    const node = document.querySelector("[data-admin-case-list]");
    if (!node) return;
    const sections = state.marketingSections || {};
    const queueSection = sections[state.queue] || {};
    const entries = Object.entries(queueSection);
    if (!entries.length) {
      node.innerHTML = `
        <div class="admin-empty-state">
          <h3>No marketing metrics available</h3>
          <p class="card-copy">This section has no live metrics yet for Tomb of Light.</p>
        </div>
      `;
      return;
    }

    node.innerHTML = entries
      .map(function (entry) {
        return renderMarketingMetric(titleize(entry[0]), entry[1]);
      })
      .join("");
  }

  function renderOperationsMetric(label, metric) {
    const payload = metric || {};
    const isLive = Boolean(payload.live);
    const value = Object.prototype.hasOwnProperty.call(payload, "value") ? payload.value : payload;
    const displayValue =
      value && typeof value === "object"
        ? `<pre class="card-copy">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`
        : `<strong>${escapeHtml(String(value ?? "—"))}</strong>`;
    return `
      <article class="admin-dossier-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">${isLive ? "L" : "N"}</span>
          <h3 class="admin-card-title">${escapeHtml(label)}</h3>
        </div>
        ${displayValue}
        ${isLive ? "" : `<p class="card-copy">Status: ${escapeHtml(payload.status || "unavailable")}</p>`}
        ${payload.status_note ? `<p class="card-copy">${escapeHtml(payload.status_note)}</p>` : ""}
      </article>
    `;
  }

  function renderOperationsQueuePanel() {
    const sections = state.operationsSections || {};
    const queueSection = sections[state.queue] || {};
    const entries = Object.entries(queueSection);
    if (!entries.length) {
      return `
        <div class="admin-empty-state">
          <h3>No operations metrics available</h3>
          <p class="card-copy">This Tomb of Light operations section has no live metrics yet.</p>
        </div>
      `;
    }
    const exportAction =
      state.queue === "ops_reports"
        ? `<div class="inline-actions" style="margin-bottom: 0.75rem;"><button class="btn btn-primary" type="button" data-admin-export-ops-report>Export Ops Report</button></div>`
        : "";
    return `
      ${exportAction}
      <div class="admin-ops-metrics-grid">
        ${entries
          .map(function (entry) {
            return renderOperationsMetric(titleize(entry[0]), entry[1]);
          })
          .join("")}
      </div>
    `;
  }

  function renderCaseList() {
    const node = document.querySelector("[data-admin-case-list]");
    if (!node) return;
    const operationsPanel = isOperationsRole() ? renderOperationsQueuePanel() : "";
    if (isMarketingRole()) {
      renderMarketingQueuePanel();
      return;
    }
    if (isOperationsRole() && state.queue === "ops_reports") {
      node.innerHTML = operationsPanel;
      return;
    }
    const cases = Array.isArray(state.cases) ? state.cases : [];
    const canRepairSelected = isAllowedBulkAction("repair-selected-records");
    if (!cases.length) {
      node.innerHTML = `
        ${operationsPanel}
        <div class="admin-empty-state">
          <div class="card-number">C</div>
          <h3>No case results</h3>
          <p class="card-copy">No customer cases matched this queue/search.</p>
        </div>
      `;
      return;
    }

    node.innerHTML = `${operationsPanel}${cases
      .map(function (item) {
        const alerts = Array.isArray(item.alerts) ? item.alerts : [];
        const guidance = getGuidanceItems(item.operator_guidance);
        const primaryGuidance = guidance[0] || null;
        const isSelected = state.selectedCaseId === item.case_id;
        return `
          <article class="admin-case-row ${isSelected ? "is-selected" : ""}" data-case-row="${escapeHtml(item.case_id || "")}">
            ${
              canRepairSelected
                ? `<label class="admin-case-select" aria-label="Select ${escapeHtml(item.name || "case")} for bulk repair">
                    <input type="checkbox" data-case-select="${escapeHtml(item.case_id || "")}" />
                  </label>`
                : '<span class="admin-case-select" aria-hidden="true"></span>'
            }
            <div class="admin-case-primary">
              <h3>${escapeHtml(item.name || "Customer Case")}</h3>
              <p>${escapeHtml(item.email || "No email")} · ${escapeHtml(item.role || "customer")}</p>
              ${item.account_type ? `<p class="card-copy">Account Type: ${escapeHtml(item.account_type)}</p>` : ""}
            </div>
            <div class="admin-case-detail">
              <span>Project</span>
              <strong>${escapeHtml(item.project || "No linked project")}</strong>
            </div>
            <div class="admin-case-detail">
              <span>Package</span>
              <strong>${escapeHtml(item.package_name || item.package || "Unknown Package")}</strong>
            </div>
            <div class="admin-case-detail admin-case-lane">
              <span>Lane</span>
              ${laneChip(item.lane)}
            </div>
            <div class="admin-case-detail">
              <span>Status</span>
              ${statusChip(item.status || "unknown", chipClassForValue(item.status))}
            </div>
            <div class="admin-case-alerts">
              ${alerts.length ? renderStatusStack(alerts) : statusChip("clear", "success")}
            </div>
            ${
              primaryGuidance
                ? `<div class="admin-case-guidance"><span>Next</span><strong>${escapeHtml(primaryGuidance.next_action || primaryGuidance.title || "Review Case")}</strong></div>`
                : ""
            }
            <button class="btn btn-secondary admin-open-case" type="button" data-open-case="${escapeHtml(item.case_id || "")}">Open</button>
          </article>
        `;
      })
      .join("")}`;
  }

  function summarizeTabValue(value) {
    if (value == null) return "—";
    if (Array.isArray(value)) return `${value.length} item(s)`;
    if (typeof value === "object") return `${Object.keys(value).length} fields`;
    return String(value);
  }

  function renderObjectRows(objectValue) {
    const entries = Object.entries(objectValue || {});
    if (!entries.length) {
      return `<p class="card-copy">No data.</p>`;
    }
    return entries
      .map(function (entry) {
        const key = String(entry[0]).replaceAll("_", " ");
        const value = entry[1];
        if (Array.isArray(value)) {
          return `<p class="card-copy"><strong>${escapeHtml(key)}:</strong> ${escapeHtml(value.join(", ") || "—")}</p>`;
        }
        if (value && typeof value === "object") {
          return `<p class="card-copy"><strong>${escapeHtml(key)}:</strong> ${escapeHtml(JSON.stringify(value))}</p>`;
        }
        return `<p class="card-copy"><strong>${escapeHtml(key)}:</strong> ${escapeHtml(summarizeTabValue(value))}</p>`;
      })
      .join("");
  }

  function renderWorkspaceTab() {
    const node = document.querySelector("[data-admin-case-workspace]");
    if (!node) return;
    const workspace = state.workspace;
    if (!workspace || !workspace.tabs) {
      node.innerHTML = `
        <div class="admin-empty-state">
          <div class="card-number">C</div>
          <h3>No case selected</h3>
          <p class="card-copy">Select a customer case to open the workspace.</p>
        </div>
      `;
      return;
    }

    const tab = state.selectedTab;
    const backendTab = TAB_BACKEND_KEY[tab] || tab;
    const tabData = workspace.tabs[backendTab];
    const warningMarkup = renderWarningStrip((tabData && tabData.warnings) || workspace.warnings || []);

    if (backendTab === "audit_timeline") {
      const timeline = Array.isArray(tabData) ? tabData : Array.isArray(workspace.audit_timeline) ? workspace.audit_timeline : [];
      node.innerHTML = timeline.length
        ? timeline
            .map(function (item) {
              return `
                <article class="admin-dossier-card">
                  <div class="admin-card-header">
                    <span class="admin-card-badge">A</span>
                    <h3 class="admin-card-title">${escapeHtml(item.action || "Audit Event")}</h3>
                  </div>
                  ${renderFieldGrid([
                    { label: "Target", value: `${item.target_type || "—"} / ${shortId(item.target_id)}` },
                    { label: "Actor", value: item.actor_email || item.actor_name || "—" },
                    { label: "Result", value: item.result || "success", chip: true },
                    { label: "When", value: formatDate(item.timestamp) },
                  ])}
                </article>
              `;
            })
            .join("")
        : `<div class="admin-empty-state"><h3>No audit timeline</h3><p class="card-copy">No audit events were found for this case context.</p></div>`;
      return;
    }

    if (backendTab === "orders_billing") {
      const primaryOrder = tabData && tabData.primary_order ? tabData.primary_order : {};
      const related = Array.isArray(tabData && tabData.related_orders) ? tabData.related_orders : [];
      node.innerHTML = `
        ${warningMarkup}
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">O</span><h3 class="admin-card-title">Primary Order</h3></div>
          ${renderFieldGrid([
            { label: "Package", value: tabData.package_name || primaryOrder.package_name },
            { label: "Package Code", value: tabData.package_code || primaryOrder.package_code, mono: true },
            { label: "Lane", value: tabData.lane || primaryOrder.lane, chip: true },
            { label: "Order Status", value: tabData.order_status || primaryOrder.status, chip: true },
            { label: "Paid", value: tabData.paid, chip: true },
            { label: "Stripe Session", value: tabData.stripe_session_id || primaryOrder.stripe_session_id, mono: true },
            { label: "Payment Link", value: tabData.payment_link_id || primaryOrder.payment_link_id, mono: true },
            { label: "Project Link", value: tabData.project_link_status, chip: true },
            { label: "Subscription", value: tabData.subscription || primaryOrder.subscription_id, mono: true },
            { label: "Maintenance", value: tabData.maintenance_state, chip: true },
            { label: "Next Charge", value: formatDate(tabData.next_charge_date) },
          ])}
        </article>
        <article class="admin-dossier-card">
          <div class="admin-card-header"><span class="admin-card-badge">R</span><h3 class="admin-card-title">Related Orders (${related.length})</h3></div>
          <div class="admin-record-list">
            ${related.length ? related.map(function (order) { return `<p><strong>${escapeHtml(shortId(order.id))}</strong><span>${escapeHtml(order.status || "unknown")} · ${escapeHtml(order.package_name || order.package_code || "—")} · ${escapeHtml(formatDate(order.created_at))}</span></p>`; }).join("") : '<p>No related orders.</p>'}
          </div>
        </article>
        ${state.isSuperAdmin ? renderStripeOpsCard(workspace, tabData) : ""}
      `;
      return;
    }

    if (backendTab === "uploads_verification") {
      const uploads = tabData && Array.isArray(tabData.items) ? tabData.items : [];
      node.innerHTML = `
        ${warningMarkup}
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">U</span><h3 class="admin-card-title">Upload & Verification Records (${uploads.length})</h3></div>
          ${renderFieldGrid([
            { label: "Uploaded Files", value: tabData.uploaded_files },
            { label: "Categories", value: (tabData.file_categories || []).join(", ") || "—" },
            { label: "Review Status", value: tabData.review_status, chip: true },
            { label: "Verification", value: tabData.verification_readiness, chip: true },
          ])}
          <div class="admin-record-list">
            ${uploads.length ? uploads.map(function (upload) { return `<p><strong>${escapeHtml(upload.filename || shortId(upload.id))}</strong><span>${escapeHtml(upload.category || "upload")} · ${escapeHtml(upload.status || "received")} · ${escapeHtml(formatDate(upload.created_at))}</span></p>`; }).join("") : '<p>No uploads found for this case.</p>'}
          </div>
        </article>
      `;
      return;
    }

    if (backendTab === "identity") {
      const userId =
        (tabData && tabData.user_id) ||
        (workspace.tabs && workspace.tabs.identity && workspace.tabs.identity.user_id) ||
        "";
      const showSuperAdminControls = Boolean(state.isSuperAdmin && userId);
      node.innerHTML = `
        ${warningMarkup}
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">I</span><h3 class="admin-card-title">Identity</h3></div>
          ${renderFieldGrid([
            { label: "User ID", value: userId, mono: true },
            { label: "Full Name", value: tabData.full_name },
            { label: "Email", value: tabData.email },
            { label: "Phone", value: tabData.phone_number },
            { label: "Birthday", value: tabData.birthday },
            { label: "Role", value: tabData.role, chip: true },
            { label: "Status", value: tabData.status, chip: true },
            { label: "Admin/User Relationship", value: tabData.admin_user_relationship, chip: true },
            { label: "Access Tier", value: tabData.access_tier || "—" },
            { label: "Department Role", value: tabData.department_role || "—" },
            { label: "Mailing Address", value: tabData.mailing_address || "—" },
            { label: "Last Login", value: formatDate(tabData.last_login_at) },
          ])}
        </article>
        ${
          showSuperAdminControls
            ? `
              <article class="admin-dossier-card admin-dossier-card--wide">
                <div class="admin-card-header"><span class="admin-card-badge">S</span><div><h3 class="admin-card-title">CEO Account Controls</h3><p class="card-copy">Update identity details, control access, or close the account through one governed workflow.</p></div></div>
                <div class="admin-field-grid">
                  <label class="admin-field"><span>Full Name</span><input type="text" data-super-admin-user-field="full_name" value="${escapeHtml(tabData.full_name || "")}" /></label>
                  <label class="admin-field"><span>Email</span><input type="email" data-super-admin-user-field="email" value="${escapeHtml(tabData.email || "")}" /></label>
                  <label class="admin-field"><span>Phone Number</span><input type="text" data-super-admin-user-field="phone_number" value="${escapeHtml(tabData.phone_number || "")}" /></label>
                  <label class="admin-field"><span>Birthday</span><input type="text" data-super-admin-user-field="birthday" value="${escapeHtml(tabData.birthday || "")}" /></label>
                  <label class="admin-field"><span>Mailing Address</span><input type="text" data-super-admin-user-field="mailing_address" value="${escapeHtml(tabData.mailing_address || "")}" /></label>
                  <label class="admin-field"><span>Role</span><input type="text" data-super-admin-user-field="role" value="${escapeHtml(tabData.role || "")}" /></label>
                  <label class="admin-field"><span>Status</span><input type="text" data-super-admin-user-field="status" value="${escapeHtml(tabData.status || "")}" /></label>
                  <label class="admin-field"><span>Access Tier</span><input type="text" data-super-admin-user-field="access_tier" value="${escapeHtml(tabData.access_tier || "")}" /></label>
                  <label class="admin-field"><span>Department Role</span><input type="text" data-super-admin-user-field="department_role" value="${escapeHtml(tabData.department_role || "")}" /></label>
                </div>
                <div class="admin-account-control-section">
                  <div><h4>Profile &amp; sign-in</h4><p>Contact changes and account access changes are audited separately.</p></div>
                  <div class="inline-actions">
                    <button class="btn btn-primary" type="button" data-super-admin-user-save="${escapeHtml(userId)}">Save Profile</button>
                    <button class="btn btn-secondary" type="button" data-super-admin-user-password-reset="${escapeHtml(userId)}">Send Password Reset</button>
                    <button class="btn btn-secondary" type="button" data-super-admin-user-action="activate" data-super-admin-user-id="${escapeHtml(userId)}">Activate</button>
                    <button class="btn btn-secondary" type="button" data-super-admin-user-action="restore" data-super-admin-user-id="${escapeHtml(userId)}">Restore</button>
                    <button class="btn btn-secondary" type="button" data-super-admin-user-action="suspend" data-super-admin-user-id="${escapeHtml(userId)}">Suspend</button>
                    <button class="btn btn-secondary" type="button" data-super-admin-user-action="disable" data-super-admin-user-id="${escapeHtml(userId)}">Disable</button>
                  </div>
                </div>
                <div class="admin-danger-zone">
                  <div>
                    <h4>Close account</h4>
                    <p>Preview owned projects, family workspaces, memberships, entitlements, and invites before access is archived. Orders, billing evidence, uploads, vault records, certificates, delivery records, and audit history are preserved.</p>
                  </div>
                  <div class="inline-actions">
                    <button class="btn btn-secondary" type="button" data-super-admin-user-action="archive" data-super-admin-user-id="${escapeHtml(userId)}">Archive Account Only</button>
                    <button class="btn btn-danger" type="button" data-super-admin-user-action="archive" data-super-admin-user-id="${escapeHtml(userId)}" data-super-admin-archive-owned="true">Close Account &amp; Workspaces</button>
                  </div>
                </div>
              </article>
            `
            : ""
        }
      `;
      return;
    }

    if (backendTab === "mint_readiness") {
      const guidance = getGuidanceItems(tabData && tabData.guidance);
      const history = Array.isArray(tabData && tabData.historical_attempts) ? tabData.historical_attempts : [];
      const currentState = tabData.current_state || tabData.eligibility || "blocked";
      const decision = tabData.decision || (tabData.eligibility === "eligible" ? "Ready for mint review" : "Readiness gates are still blocking mint review");
      const nextAction = tabData.next_admin_action || (guidance[0] && guidance[0].next_action) || "Run Readiness Check";
      node.innerHTML = `
        ${warningMarkup}
        <article class="admin-dossier-card admin-dossier-card--wide admin-mint-decision-card">
          <div class="admin-card-header"><span class="admin-card-badge">M</span><h3 class="admin-card-title">Mint Decision</h3></div>
          <div class="admin-decision-grid">
            <div>
              <span>Current Mint State</span>
              <strong>${statusChip(titleize(currentState), chipClassForValue(currentState))}</strong>
            </div>
            <div>
              <span>Operational Decision</span>
              <strong>${escapeHtml(decision)}</strong>
            </div>
            <div>
              <span>Next Admin Move</span>
              <strong>${escapeHtml(nextAction)}</strong>
            </div>
          </div>
        </article>
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">R</span><h3 class="admin-card-title">Readiness Gates</h3></div>
          ${renderFieldGrid([
            { label: "Eligibility", value: tabData.eligibility, chip: true },
            { label: "Runtime", value: tabData.runtime, chip: true },
            { label: "Review Ready", value: tabData.approvals && tabData.approvals.mint_review_ready, chip: true },
            { label: "Public Approval Required", value: tabData.approvals && tabData.approvals.customer_public_safe_approval_required, chip: true },
            { label: "Token ID", value: tabData.token_id, mono: true },
            { label: "Transaction", value: tabData.tx_hash, mono: true },
            { label: "Chain", value: tabData.chain, chip: true },
            { label: "Version", value: tabData.version_number },
            { label: "Wallet", value: tabData.wallet, mono: true },
            { label: "Queue Status", value: tabData.mint_queue_status, chip: true },
            { label: "Historical Attempts", value: tabData.historical_attempt_count },
            { label: "Error State", value: tabData.error_state || "none", chip: true },
          ])}
          <div class="admin-blocking-reasons">
            <span>Blocking Reasons</span>
            <div>${renderStatusStack(tabData.blocking_reasons || [], "none")}</div>
          </div>
          <div class="admin-record-list">
            <span>Historical Mint Attempts</span>
            ${
              history.length
                ? history
                    .map(function (attempt) {
                      return `<p><strong>v${escapeHtml(attempt.version_number || "—")} · ${escapeHtml(titleize(attempt.status || "historical"))}</strong><span>${escapeHtml(shortId(attempt.mint_record_id))} · ${escapeHtml(attempt.token_id || "no token")} · ${escapeHtml(attempt.error_message || attempt.error_code || "historical only")}</span></p>`;
                    })
                    .join("")
                : "<p>No historical mint attempts.</p>"
            }
          </div>
        </article>
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">G</span><h3 class="admin-card-title">Operator Guidance</h3></div>
          ${renderGuidanceList(guidance, "Mint path is clear", "No active mint blockers were returned for this case.")}
        </article>
      `;
      return;
    }

    if (backendTab === "package_lane") {
      const projectId =
        (workspace.tabs && workspace.tabs.project && workspace.tabs.project.project_id) ||
        (workspace.project && workspace.project.id) ||
        "";
      const packageCode = tabData.package_code || "";
      const packageOptions = (state.packageOptions || [])
        .map(function (item) {
          const selected = item.code === packageCode ? ' selected="selected"' : "";
          return `<option value="${escapeHtml(item.code)}"${selected}>${escapeHtml(item.label)} (${escapeHtml(item.code)})</option>`;
        })
        .join("");
      const packageFallbackOption = packageCode
        ? `<option value="${escapeHtml(packageCode)}">${escapeHtml(packageCode)}</option>`
        : `<option value="" selected="selected">Select package</option>`;
      const showSuperAdminControls = Boolean(state.isSuperAdmin && projectId);
      node.innerHTML = `
        ${warningMarkup}
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">P</span><h3 class="admin-card-title">Package & Lane</h3></div>
          ${renderFieldGrid([
            { label: "Package Name", value: tabData.package_name },
            { label: "Package Code", value: tabData.package_code, mono: true },
            { label: "Lane", value: tabData.project_lane || tabData.lane, chip: true },
            { label: "Normalization", value: tabData.package_normalization_status, chip: true },
            { label: "Source", value: tabData.source || "—" },
            { label: "Raw Value", value: tabData.raw_value || "—" },
          ])}
        </article>
        ${
          showSuperAdminControls
            ? `
            <article class="admin-dossier-card admin-dossier-card--wide">
              <div class="admin-card-header"><span class="admin-card-badge">S</span><h3 class="admin-card-title">CEO Master Admin Package &amp; Service Controls</h3></div>
              <div class="admin-field-grid">
                <label class="admin-field">
                  <span>Target Package</span>
                  <select data-super-admin-package-field="package_code">
                    ${packageOptions || packageFallbackOption}
                  </select>
                </label>
                <label class="admin-field"><span>Target Lane</span><input type="text" data-super-admin-package-field="project_lane" value="${escapeHtml(tabData.project_lane || tabData.lane || "")}" /></label>
                <label class="admin-field"><span>Verified Order Status (read-only)</span><input type="text" data-super-admin-package-field="order_status" readonly value="${escapeHtml((workspace.tabs.orders_billing || {}).order_status || "")}" /></label>
                <label class="admin-field"><span>Reason</span><input type="text" data-super-admin-package-field="reason" placeholder="Required for apply operations" /></label>
                <label class="admin-field">
                  <span>Service Operation</span>
                  <select data-super-admin-service-field="operation">
                    <option value="">None</option>
                    <option value="assign">assign</option>
                    <option value="upgrade">upgrade</option>
                    <option value="downgrade">downgrade</option>
                    <option value="complimentary_package">complimentary package</option>
                    <option value="promotional_package">promotional package</option>
                    <option value="internal_validation_account">internal validation account</option>
                  </select>
                </label>
                <label class="admin-field"><span>Add Add-ons (comma separated)</span><input type="text" data-super-admin-service-field="add_addons" placeholder="extra_storage, tribute_narration" /></label>
                <label class="admin-field"><span>Remove Add-ons (comma separated)</span><input type="text" data-super-admin-service-field="remove_addons" placeholder="extra_upload_pack" /></label>
                <label class="admin-field"><span>Storage Adjustment (GB)</span><input type="number" step="0.1" data-super-admin-service-field="storage_adjustment_gb" value="0" /></label>
                <label class="admin-field"><span>Upload Adjustment</span><input type="number" step="1" data-super-admin-service-field="upload_adjustment" value="0" /></label>
                <label class="admin-field"><span>Member Allowance Adjustment</span><input type="number" step="1" data-super-admin-service-field="member_allowance_adjustment" value="0" /></label>
                <label class="admin-field"><span>Maintenance State</span><input type="text" data-super-admin-service-field="maintenance_state" value="" placeholder="active, paused, not_started" /></label>
                <label class="admin-field" style="display: inline-flex; align-items: center; gap: 0.45rem;"><input type="checkbox" data-super-admin-service-field="narration_enabled" /><span>Narration</span></label>
                <label class="admin-field" style="display: inline-flex; align-items: center; gap: 0.45rem;"><input type="checkbox" data-super-admin-service-field="vault_enabled" /><span>Vault</span></label>
                <label class="admin-field" style="display: inline-flex; align-items: center; gap: 0.45rem;"><input type="checkbox" data-super-admin-service-field="scheduled_reveal_enabled" /><span>Scheduled Reveal</span></label>
                <label class="admin-field" style="display: inline-flex; align-items: center; gap: 0.45rem;"><input type="checkbox" data-super-admin-service-field="link_keys_enabled" /><span>Link Keys</span></label>
                <label class="admin-field" style="display: inline-flex; align-items: center; gap: 0.45rem;"><input type="checkbox" data-super-admin-service-field="certificate_access_enabled" /><span>Certificate Access</span></label>
                <label class="admin-field" style="display: inline-flex; align-items: center; gap: 0.45rem;"><input type="checkbox" data-super-admin-service-field="viewer_access_enabled" /><span>Viewer Access</span></label>
              </div>
              <div class="inline-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="btn btn-secondary" type="button" data-super-admin-package-preview="${escapeHtml(projectId)}">Preview Package Assignment / Change</button>
                <button class="btn btn-primary" type="button" data-super-admin-package-apply="${escapeHtml(projectId)}">Apply Package Assignment / Change</button>
                <button class="btn btn-secondary" type="button" data-super-admin-service-preview="${escapeHtml(projectId)}">Preview Service Controls</button>
                <button class="btn btn-primary" type="button" data-super-admin-service-apply="${escapeHtml(projectId)}">Apply Service Controls</button>
                <button class="btn btn-secondary" type="button" data-super-admin-package-revoke-preview="${escapeHtml(projectId)}">Preview Package Revocation</button>
                <button class="btn btn-secondary" type="button" data-super-admin-package-revoke="${escapeHtml(projectId)}">Revoke Current Package</button>
                <button class="btn btn-secondary" type="button" data-super-admin-package-restore="${escapeHtml(projectId)}">Restore Package</button>
                <button class="btn btn-secondary" type="button" data-super-admin-preview-cancel>Cancel Preview</button>
              </div>
              <div data-super-admin-package-preview-output class="helper" style="margin-top: 0.75rem;"></div>
            </article>
            `
            : ""
        }
      `;
      return;
    }

    if (backendTab === "project") {
      const caseId = workspace.case_id || state.selectedCaseId || "";
      const linked = (tabData && tabData.linked_family) || {};
      const showSuperAdminControls = Boolean(state.isSuperAdmin && caseId);
      node.innerHTML = `
        ${warningMarkup}
        <article class="admin-dossier-card admin-dossier-card--wide">
          <div class="admin-card-header"><span class="admin-card-badge">P</span><h3 class="admin-card-title">Project Workspace</h3></div>
          ${renderFieldGrid([
            { label: "Project Name", value: tabData.project_name },
            { label: "Project ID", value: tabData.project_id, mono: true },
            { label: "Build Status", value: tabData.build_status, chip: true },
            { label: "Phase", value: tabData.phase, chip: true },
            { label: "Intake Readiness", value: tabData.intake_readiness, chip: true },
            { label: "Family ID", value: linked.family_id, mono: true },
            { label: "Family Name", value: linked.family_name },
            { label: "Household ID", value: linked.household_id, mono: true },
            { label: "Household Name", value: linked.household_name },
          ])}
        </article>
        ${
          showSuperAdminControls
            ? `
              <article class="admin-dossier-card admin-dossier-card--wide">
                <div class="admin-card-header"><span class="admin-card-badge">S</span><h3 class="admin-card-title">Restricted Administrative Actions</h3></div>
                <p class="card-copy">All actions are audit-logged with before/after snapshots and a required repair reason.</p>
                <div class="admin-field-grid">
                  <label class="admin-field"><span>Repair Tool</span><select data-super-admin-repair-field="action">
                    <option value="">Select tool</option>
                    <option value="fix_family_relationship">fix family relationship</option>
                    <option value="relink_person">relink person</option>
                    <option value="add_missing_parent">add missing parent</option>
                    <option value="correct_spouse_connection">correct spouse connection</option>
                    <option value="correct_child_connection">correct child connection</option>
                    <option value="fix_household_member_access">fix household member access</option>
                    <option value="resend_invite">resend invite</option>
                    <option value="cancel_invite">cancel invite</option>
                    <option value="update_invite_email">correct invite email</option>
                    <option value="repair_entitlement">repair entitlement</option>
                    <option value="repair_package_lane">repair package lane</option>
                    <option value="repair_tree_rendering">repair tree rendering</option>
                  </select></label>
                  <label class="admin-field"><span>Reason / Note</span><input type="text" data-super-admin-repair-field="reason" placeholder="Required for audit" /></label>
                  <label class="admin-field"><span>Relationship ID</span><input type="text" data-super-admin-repair-field="relationship_id" /></label>
                  <label class="admin-field"><span>Member ID</span><input type="text" data-super-admin-repair-field="member_id" /></label>
                  <label class="admin-field"><span>Source Member ID</span><input type="text" data-super-admin-repair-field="source_member_id" /></label>
                  <label class="admin-field"><span>Target Member ID</span><input type="text" data-super-admin-repair-field="target_member_id" /></label>
                  <label class="admin-field"><span>Family ID</span><input type="text" data-super-admin-repair-field="family_id" value="${escapeHtml(linked.family_id || "")}" /></label>
                  <label class="admin-field"><span>Child Member ID</span><input type="text" data-super-admin-repair-field="child_member_id" /></label>
                  <label class="admin-field"><span>Parent Member ID</span><input type="text" data-super-admin-repair-field="parent_member_id" /></label>
                  <label class="admin-field"><span>Parent First Name</span><input type="text" data-super-admin-repair-field="parent_first_name" /></label>
                  <label class="admin-field"><span>Parent Last Name</span><input type="text" data-super-admin-repair-field="parent_last_name" /></label>
                  <label class="admin-field"><span>Relationship Type</span><input type="text" data-super-admin-repair-field="relationship_type" /></label>
                  <label class="admin-field"><span>Membership ID</span><input type="text" data-super-admin-repair-field="membership_id" /></label>
                  <label class="admin-field"><span>Member Role</span><input type="text" data-super-admin-repair-field="member_role" /></label>
                  <label class="admin-field"><span>Relationship Scope</span><input type="text" data-super-admin-repair-field="relationship_scope" /></label>
                  <label class="admin-field"><span>Privacy Scope</span><input type="text" data-super-admin-repair-field="privacy_scope" /></label>
                  <label class="admin-field"><span>Invite ID</span><input type="text" data-super-admin-repair-field="invite_id" /></label>
                  <label class="admin-field"><span>Invite Email</span><input type="email" data-super-admin-repair-field="invite_email" /></label>
                  <label class="admin-field"><span>Notes</span><input type="text" data-super-admin-repair-field="notes" /></label>
                  <label class="admin-field"><span>Status</span><input type="text" data-super-admin-repair-field="status" /></label>
                  <label class="admin-field"><span>New Owner User ID</span><input type="text" data-super-admin-new-owner-id /></label>
                </div>
                <label class="admin-field" style="margin-top: 0.6rem; display: inline-flex; align-items: center; gap: 0.45rem;">
                  <input type="checkbox" data-super-admin-repair-field="confirm_destructive" />
                  <span>I confirm destructive edits if required</span>
                </label>
                <div class="inline-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                  <button class="btn btn-primary" type="button" data-super-admin-repair-run="${escapeHtml(caseId)}">Apply Repair Tool</button>
                  <button class="btn btn-secondary" type="button" data-super-admin-transfer-ownership="${escapeHtml(tabData.project_id || "")}">Transfer Ownership</button>
                </div>
              </article>
            `
            : ""
        }
      `;
      return;
    }

    const flatFields = Object.entries(tabData || {}).filter(function (entry) {
      return !entry[1] || typeof entry[1] !== "object" || Array.isArray(entry[1]);
    });
    const objectFields = Object.entries(tabData || {}).filter(function (entry) {
      return entry[1] && typeof entry[1] === "object" && !Array.isArray(entry[1]);
    });
    node.innerHTML = `
      ${warningMarkup}
      <article class="admin-dossier-card admin-dossier-card--wide">
        <div class="admin-card-header">
          <span class="admin-card-badge">${escapeHtml(tab.charAt(0).toUpperCase())}</span>
          <h3 class="admin-card-title">${escapeHtml(TAB_LABELS[tab] || titleize(tab))}</h3>
        </div>
        ${renderFieldGrid(
          flatFields.map(function (entry) {
            return {
              label: titleize(entry[0]),
              value: Array.isArray(entry[1]) ? entry[1].join(", ") : entry[1],
              chip: ["status", "state", "readiness", "paid", "exists"].some(function (key) {
                return entry[0].includes(key);
              }),
            };
          }),
        )}
      </article>
      ${objectFields
        .map(function (entry) {
          return `
            <article class="admin-dossier-card">
              <div class="admin-card-header">
                <span class="admin-card-badge">${escapeHtml(entry[0].charAt(0).toUpperCase())}</span>
                <h3 class="admin-card-title">${escapeHtml(titleize(entry[0]))}</h3>
              </div>
              ${renderObjectRows(entry[1])}
            </article>
          `;
        })
        .join("")}
    `;
  }

  function renderCaseContext() {
    const node = document.querySelector("[data-admin-case-context]");
    if (!node) return;
    const selected = getSelectedCase();

    if (!selected) {
      node.innerHTML = `
        <div class="admin-context-card">
          <h3>Context panel</h3>
          <p class="card-copy">Select a case to see alerts, blocking reasons, and contextual status.</p>
        </div>
      `;
      return;
    }

    if (!state.workspace || state.workspace.case_id !== state.selectedCaseId) {
      node.innerHTML = `
        <div class="admin-context-card">
          <h3>Opening case workspace</h3>
          <p class="card-copy">Loading the case-scoped operations context.</p>
        </div>
      `;
      return;
    }

    const context = getWorkspaceContext(selected);
    const impersonation = state.activeImpersonation;
    const isImpersonating = Boolean(impersonation && impersonation.active);
    const canStartImpersonation = Boolean(state.isSuperAdmin && context.caseId && !isImpersonating);
    const canStopImpersonation = Boolean(state.isSuperAdmin && isImpersonating);
    node.innerHTML = `
      <div class="admin-context-card">
        ${
          isImpersonating
            ? `<div class="admin-warning-strip"><span>Customer Preview Active</span><div><strong>${escapeHtml(impersonation.banner || "Read-only customer context")}</strong></div></div>
               <div class="admin-diagnostics-grid" style="margin-top:0.75rem;">
                 <div><dt>Customer-visible package</dt><dd>${escapeHtml(context.packageName || "No package")}</dd></div>
                 <div><dt>Customer-visible project</dt><dd>${escapeHtml(context.projectName || selected.project || "No linked project")}</dd></div>
                 <div><dt>Current status</dt><dd>${escapeHtml(selected.status || "unknown")}</dd></div>
                 <div><dt>Access lane</dt><dd>${escapeHtml(context.lane || "unknown")}</dd></div>
               </div>
               <p class="card-copy">This is an audited, read-only customer-context preview. It does not replace the administrator identity or authorize hidden customer-session writes.</p>`
            : ""
        }
        <h3>${escapeHtml(context.name || "Selected Case")}</h3>
        <p class="card-copy"><strong>Case:</strong> <span class="admin-id-ref">${escapeHtml(shortId(context.caseId))}</span></p>
        <p class="card-copy"><strong>Package:</strong> ${escapeHtml(context.packageName || "—")} ${context.packageCode ? `<span class="admin-id-ref">${escapeHtml(context.packageCode)}</span>` : ""}</p>
        <p class="card-copy"><strong>Lane:</strong> ${laneChip(context.lane)}</p>
        <div class="admin-context-chip-row">${renderStatusStack(context.alerts || [], "none")}</div>
        <div class="admin-context-guidance">
          <span>Operator Guidance</span>
          ${renderGuidanceList(context.guidance, "No active repair guidance", "This case is not reporting a repair blocker in the selected queue.")}
        </div>
        <div class="admin-blocking-reasons">
          <span>Mint Blocking Reasons</span>
          <div>${renderStatusStack(context.blocking, "none")}</div>
        </div>
        ${
          state.isSuperAdmin
            ? `<div class="inline-actions" style="margin-top: 0.85rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <label class="admin-field" style="min-width: 18rem;"><span>Preview reason</span><input type="text" data-admin-impersonation-start-reason placeholder="Required reason to start customer preview" /></label>
                <button class="btn btn-secondary" type="button" data-admin-impersonation-start="${escapeHtml(context.caseId)}" ${canStartImpersonation ? "" : "disabled"}>Start Read-Only Customer Preview</button>
                <button class="btn btn-primary" type="button" data-admin-impersonation-stop ${canStopImpersonation ? "" : "disabled"}>Exit Customer Preview</button>
              </div>`
            : ""
        }
      </div>
    `;
  }

  function syncRailGroups() {
    document.querySelectorAll("[data-admin-nav-group]").forEach(function (group) {
      const visibleButtons = Array.from(group.querySelectorAll("[data-case-queue]")).filter(function (button) {
        return !button.hidden;
      });
      group.hidden = visibleButtons.length === 0;
      const hasActive = visibleButtons.some(function (button) {
        return button.classList.contains("is-active");
      });
      if (hasActive && group instanceof HTMLDetailsElement) group.open = true;
    });
  }

  function updateGlobalAdminControls() {
    document.querySelectorAll("[data-super-admin-create-account], [data-super-admin-manage-team-access]").forEach(function (button) {
      button.hidden = !state.isSuperAdmin;
      button.disabled = !state.isSuperAdmin || state.bootstrapFailed;
      button.setAttribute("aria-disabled", button.disabled ? "true" : "false");
    });
  }

  function applyRailSelection() {
    document.querySelectorAll("[data-case-queue]").forEach(function (button) {
      const queue = button.getAttribute("data-case-queue") || "";
      const allowed = isAllowedQueue(queue);
      button.hidden = !allowed;
      button.disabled = !allowed;
      button.setAttribute("aria-disabled", allowed ? "false" : "true");
      button.classList.toggle("is-active", queue === state.queue);
    });
    const meta = QUEUE_META[state.queue] || QUEUE_META.customer_cases;
    const title = document.querySelector("[data-admin-list-title]");
    const subtitle = document.querySelector("[data-admin-list-subtitle]");
    const activeQueue = document.querySelector("[data-admin-active-queue]");
    if (title) title.textContent = meta[0];
    if (subtitle) subtitle.textContent = meta[1];
    if (activeQueue) activeQueue.textContent = meta[0];
    syncRailGroups();
  }

  function applyTabSelection() {
    document.querySelectorAll("[data-admin-case-tab]").forEach(function (button) {
      const tab = button.getAttribute("data-admin-case-tab") || "";
      const allowed = isAllowedTab(tab);
      button.hidden = !allowed;
      button.disabled = !allowed;
      button.classList.toggle("is-active", tab === state.selectedTab);
      button.setAttribute("aria-selected", tab === state.selectedTab ? "true" : "false");
      button.setAttribute("aria-disabled", allowed ? "false" : "true");
    });
  }

  function renderCaseHeader() {
    const heading = document.querySelector("[data-admin-case-heading]");
    const meta = document.querySelector("[data-admin-case-meta]");
    const selected = getSelectedCase();
    if (!heading || !meta) return;
    if (!selected) {
      heading.textContent = "No case selected";
      meta.textContent = "Open a customer or project to isolate the record.";
      return;
    }
    if (!state.workspace || state.workspace.case_id !== state.selectedCaseId) {
      heading.textContent = "Opening case workspace";
      meta.textContent = "Loading isolated case details.";
      return;
    }
    const context = getWorkspaceContext(selected);
    heading.textContent = context.name || "Customer Case";
    meta.innerHTML = `${escapeHtml(context.email || "No email")} · ${escapeHtml(context.projectName || "No project")} · ${laneChip(context.lane)} · ${statusChip(context.status || "unknown", chipClassForValue(context.status))}`;
  }

  function updateActionAvailability() {
    const selected = getSelectedCase();
    const scope = getActionScope(selected);
    document.querySelectorAll("[data-admin-case-action]").forEach(function (button) {
      const action = button.getAttribute("data-admin-case-action") || "";
      const tier = ACTION_TIERS[action] || "utility";
      const allowedByRole = isAllowedCaseAction(action);
      const requirements = ACTION_AVAILABILITY[action] || [];
      const allowedByCase =
        selected && (!Array.isArray(selected.quick_actions) || selected.quick_actions.includes(action));
      const hasRequirements =
        action === "link_order_to_project"
          ? Boolean(scope.project_id && scope.order_id)
          : requirements.every(function (key) {
              return scope[key];
            });
      const available = Boolean(
        selected && allowedByRole && allowedByCase && hasRequirements && !state.bootstrapFailed,
      );
      button.hidden = !allowedByRole;
      button.disabled = !available;
      button.classList.toggle("is-disabled", !available);
      button.setAttribute("data-action-tier", tier);
      button.classList.toggle("admin-action-tier--primary", tier === "primary");
      button.classList.toggle("admin-action-tier--secondary", tier === "secondary");
      button.classList.toggle("admin-action-tier--utility", tier === "utility");
      button.setAttribute("aria-disabled", available ? "false" : "true");
      if (!available && state.bootstrapFailed) {
        button.title = `Disabled: admin bootstrap has not succeeded (${state.bootstrapErrorCode}).`;
      } else if (!available && !selected) {
        button.title = "Disabled: select a valid target account first.";
      } else {
        button.removeAttribute("title");
      }
    });
  }

  function updateBulkActionAvailability() {
    document.querySelectorAll("[data-admin-bulk-action]").forEach(function (button) {
      const action = button.getAttribute("data-admin-bulk-action") || "";
      const allowedByRole = isAllowedBulkAction(action);
      const allowed = allowedByRole && !state.bootstrapFailed;
      button.hidden = !allowedByRole;
      button.disabled = !allowed;
      button.classList.toggle("is-disabled", !allowed);
      button.setAttribute("aria-disabled", allowed ? "false" : "true");
      if (!allowed && state.bootstrapFailed) {
        button.title = `Disabled: admin bootstrap has not succeeded (${state.bootstrapErrorCode}).`;
      } else {
        button.removeAttribute("title");
      }
    });
  }

  async function loadCaseWorkspace(caseId) {
    if (!caseId) return;
    state.selectedCaseId = caseId;
    state.workspace = null;
    applyTabSelection();
    renderCaseList();
    renderCaseHeader();
    renderCaseContext();
    updateActionAvailability();
    updateBulkActionAvailability();
    renderWorkspaceTab();
    try {
      const payload = await fetchJson(`/admin/control-center/cases/${encodeURIComponent(caseId)}`);
      state.workspace = payload || null;
      state.casesLoadFailed = false;
      renderWorkspaceTab();
      renderCaseHeader();
      renderCaseContext();
      updateActionAvailability();
      updateBulkActionAvailability();
    } catch (error) {
      setPageStatus(
        actionableError("ACC-CASE-WORKSPACE", "Case workspace load", `/admin/control-center/cases/${caseId}`, error),
        "error",
      );
    }
  }

  async function loadCases() {
    if (state.queue === "manual_fulfillment") {
      state.cases = [];
      state.selectedCaseId = "";
      state.workspace = null;
      renderCaseHeader();
      renderCaseContext();
      updateActionAvailability();
      updateBulkActionAvailability();
      await loadFulfillmentQueue();
      return;
    }
    if (isMarketingRole()) {
      state.cases = [];
      state.selectedCaseId = "";
      state.workspace = null;
      renderCaseList();
      renderCaseHeader();
      renderCaseContext();
      updateActionAvailability();
      updateBulkActionAvailability();
      clearPageStatus();
      return;
    }
    if (isOperationsRole() && state.queue === "ops_reports") {
      state.cases = [];
      state.selectedCaseId = "";
      state.workspace = null;
      renderCaseList();
      renderCaseHeader();
      renderCaseContext();
      updateActionAvailability();
      updateBulkActionAvailability();
      clearPageStatus();
      return;
    }
    const meta = QUEUE_META[state.queue] || QUEUE_META.customer_cases;
    setPageStatus(`Loading ${meta[0].toLowerCase()}...`, "info");
    try {
      const payload = await fetchJson(
        `/admin/control-center/cases?queue=${encodeURIComponent(state.queue)}&limit=80&search=${encodeURIComponent(getSearchValue())}`,
      );
      state.casesLoadFailed = false;
      state.cases = Array.isArray(payload.items) ? payload.items : [];
      if (!state.cases.length) {
        state.selectedCaseId = "";
        state.workspace = null;
      }
      renderCaseList();
      if (!state.selectedCaseId && state.cases.length) {
        await loadCaseWorkspace(state.cases[0].case_id);
      } else if (state.selectedCaseId) {
        const stillExists = state.cases.find(function (item) {
          return item.case_id === state.selectedCaseId;
        });
        if (stillExists) {
          await loadCaseWorkspace(state.selectedCaseId);
        } else if (state.cases.length) {
          await loadCaseWorkspace(state.cases[0].case_id);
        }
      }
      renderCaseContext();
      renderCaseHeader();
      updateActionAvailability();
      updateBulkActionAvailability();
      if (!state.cases.length) renderWorkspaceTab();
      clearPageStatus();
    } catch (error) {
      console.error("Case load failed:", error);
      state.casesLoadFailed = true;
      const code = classifyAdminError(error, ADMIN_ERROR_CODES.search);
      showBootstrapError(code, error && error.message, loadCases);
      setPageStatus(actionableError(code, "Case search", `/admin/control-center/cases?queue=${state.queue}`, error), "error");
    }
  }

  function selectedRepairIds() {
    const projectIds = [];
    const orderIds = [];
    document.querySelectorAll("[data-case-select]").forEach(function (checkbox) {
      if (!checkbox.checked) return;
      const caseId = checkbox.getAttribute("data-case-select") || "";
      const caseRow = state.cases.find(function (item) {
        return item.case_id === caseId;
      });
      if (!caseRow) return;
      if (caseRow.project_id) projectIds.push(caseRow.project_id);
      if (caseRow.order_id) orderIds.push(caseRow.order_id);
    });
    return { project_ids: projectIds, order_ids: orderIds };
  }

  async function runBulkAction(action) {
    if (!isAllowedBulkAction(action)) {
      setPageStatus("Your role cannot run that bulk action.", "error");
      return;
    }
    const body = action === "repair-selected-records" ? selectedRepairIds() : { limit: 500 };
    if (
      action === "repair-selected-records" &&
      (!body.project_ids.length && !body.order_ids.length)
    ) {
      setPageStatus("Select one or more cases before running Repair Selected Records.", "error");
      return;
    }

    const reason = promptExecutionReason(`Run ${titleize(action)}`);
    if (reason === null) return;
    if (!window.confirm("Submit this bulk operation to the Continuity Kernel for live execution?")) return;

    setPageStatus("Submitting governed bulk operation...", "info");
    try {
      const operation = await submitGovernedOperation(action, {}, body, reason);
      await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
      setPageStatus(kernelOperationMessage(operation, "Bulk action completed."), kernelOperationStatusType(operation));
    } catch (error) {
      setPageStatus(error.message || "Governed bulk action failed.", "error");
    }
  }

  async function startImpersonation(caseId, reasonValue) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    const reason = normalizeValue(reasonValue);
    if (!reason) {
      setPageStatus("A reason is required to start customer view.", "error");
      return;
    }
    if (!window.confirm("Start an audited, read-only customer-context preview through the Continuity Kernel?")) return;
    setPageStatus("Starting customer-context preview...", "info");
    try {
      const operation = await submitGovernedOperation(
        "impersonation_start",
        { case_id: caseId },
        {},
        reason,
      );
      await loadKernelStatus();
      await loadActiveImpersonation();
      renderCaseContext();
      setPageStatus(
        kernelOperationMessage(operation, "Read-only customer preview started."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to start customer view.", "error");
    }
  }

  async function stopImpersonation() {
    if (!state.isSuperAdmin || !state.activeImpersonation || !state.activeImpersonation.session_id) {
      setPageStatus("No active customer-view session.", "error");
      return;
    }
    const reason = promptExecutionReason("Exit this customer preview", "Operator exited preview");
    if (reason === null || !window.confirm("Exit this audited customer preview through the Continuity Kernel?")) return;
    setPageStatus("Exiting customer preview...", "info");
    try {
      const operation = await submitGovernedOperation(
        "impersonation_stop",
        { session_id: state.activeImpersonation.session_id },
        {},
        reason,
      );
      await loadKernelStatus();
      await loadActiveImpersonation();
      renderCaseContext();
      setPageStatus(
        kernelOperationMessage(operation, "Exited customer preview."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to exit customer view.", "error");
    }
  }

  async function runCaseAction(action) {
    if (!isAllowedCaseAction(action)) {
      setPageStatus("Your role cannot run that case action.", "error");
      return;
    }
    if (!state.selectedCaseId) {
      setPageStatus("Select a case first.", "error");
      return;
    }
    const caseId = state.selectedCaseId;
    const isReadOnlyAction = action === "run_readiness_check" || action === "refresh_case_data";
    let reason = "";
    if (!isReadOnlyAction) {
      reason = promptExecutionReason(`Run ${titleize(action)} for the selected case`);
      if (reason === null) return;
      if (!window.confirm("Submit this case operation to the Continuity Kernel for live execution?")) return;
    }
    setPageStatus("Running case action...", "info");
    try {
      const operation = isReadOnlyAction
        ? await postJson(
            `/admin/control-center/cases/${encodeURIComponent(caseId)}/actions/${encodeURIComponent(action)}`,
            {},
          )
        : await submitGovernedOperation(action, { case_id: caseId }, {}, reason);
      await loadOverview();
      await loadCases();
      if (!isReadOnlyAction) await loadKernelStatus();
      if (state.selectedCaseId === caseId) {
        await loadCaseWorkspace(caseId);
      }
      setPageStatus(
        isReadOnlyAction
          ? "Case check completed."
          : kernelOperationMessage(operation, "Case action completed."),
        isReadOnlyAction ? "success" : kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Case action failed.", "error");
    }
  }

  async function exportOpsReport() {
    if (!isOperationsRole() || !isAllowedQueue("ops_reports")) {
      setPageStatus("Your role cannot export operations reports.", "error");
      return;
    }
    setPageStatus("Generating operations report export...", "info");
    try {
      const payload = await fetchJson("/admin/control-center/ops-reports/export");
      const blob = new Blob([JSON.stringify(payload || {}, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "tomb-of-light-ops-report.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setPageStatus("Operations report exported.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to export operations report.", "error");
    }
  }

  function collectSuperAdminUserPayload() {
    const payload = {};
    document.querySelectorAll("[data-super-admin-user-field]").forEach(function (node) {
      const key = node.getAttribute("data-super-admin-user-field");
      if (!key) return;
      payload[key] = normalizeValue(node.value);
    });
    return payload;
  }

  function populateCreatePackageOptions() {
    const select = document.querySelector('[data-admin-create-field="package_code"]');
    if (!(select instanceof HTMLSelectElement)) return;
    const current = select.value;
    select.innerHTML = `<option value="">Account only — no package</option>${state.packageOptions
      .map(function (item) {
        return `<option value="${escapeHtml(item.code)}">${escapeHtml(item.label)} · ${escapeHtml(item.code)}</option>`;
      })
      .join("")}`;
    if (Array.from(select.options).some(function (option) { return option.value === current; })) {
      select.value = current;
    }
  }

  function createAccountPayloadFromDialog() {
    const packageCode = fieldValue('[data-admin-create-field="package_code"]');
    return {
      full_name: fieldValue('[data-admin-create-field="full_name"]'),
      email: fieldValue('[data-admin-create-field="email"]').toLowerCase(),
      phone_number: fieldValue('[data-admin-create-field="phone_number"]') || null,
      package_code: packageCode || null,
      project_name: packageCode ? fieldValue('[data-admin-create-field="project_name"]') || null : null,
      package_grant_type: packageCode
        ? fieldValue('[data-admin-create-field="package_grant_type"]') || "complimentary_package"
        : null,
      reason: fieldValue('[data-admin-create-field="reason"]'),
    };
  }

  function createAccountPreviewFingerprint(payload) {
    return JSON.stringify({
      full_name: payload.full_name,
      email: payload.email,
      phone_number: payload.phone_number,
      package_code: payload.package_code,
      project_name: payload.project_name,
      package_grant_type: payload.package_grant_type,
    });
  }

  function syncCreatePackageFields() {
    const payload = createAccountPayloadFromDialog();
    const projectName = document.querySelector('[data-admin-create-field="project_name"]');
    const grantType = document.querySelector('[data-admin-create-field="package_grant_type"]');
    const hasPackage = Boolean(payload.package_code);
    if (projectName instanceof HTMLInputElement) {
      projectName.disabled = !hasPackage;
      projectName.required = hasPackage;
      if (hasPackage && !normalizeValue(projectName.value) && payload.full_name) {
        projectName.value = `${payload.full_name} Legacy Build`;
      }
      if (!hasPackage) projectName.value = "";
    }
    if (grantType instanceof HTMLSelectElement) grantType.disabled = !hasPackage;
  }

  function resetCreatePreview(message) {
    state.createAccountPreview = null;
    const previewNode = document.querySelector("[data-admin-create-preview]");
    if (previewNode) {
      previewNode.innerHTML = `<h3>Execution preview</h3><p>${escapeHtml(message || "Complete the fields and choose Preview. Nothing is written until Execute is confirmed.")}</p>`;
    }
    setButtonEnabled(document.querySelector("[data-admin-create-execute]"), false);
  }

  function validateCreateAccountPayload(payload) {
    if (!payload.full_name) return "Full name is required.";
    if (!payload.email || !payload.email.includes("@")) return "A valid customer email is required.";
    if (payload.package_code && !payload.project_name) return "Project name is required when a package is granted.";
    if (payload.reason.length < 3) return "An operational reason of at least 3 characters is required.";
    return "";
  }

  function renderCreateAccountPreview(preview) {
    const node = document.querySelector("[data-admin-create-preview]");
    if (!node) return;
    const proposed = (preview && preview.proposed_after) || {};
    const warnings = asArray(preview && preview.warnings);
    node.innerHTML = `
      <div class="admin-preview-heading"><h3>Execution preview</h3>${statusChip("Ready for confirmation", "success")}</div>
      <div class="admin-preview-facts">
        <div><span>Account</span><strong>${escapeHtml(proposed.full_name || "—")}</strong><small>${escapeHtml(proposed.email || "—")}</small></div>
        <div><span>Initial status</span><strong>${escapeHtml(titleize(proposed.status || "pending_activation"))}</strong></div>
        <div><span>Package</span><strong>${escapeHtml(proposed.package_name || "No package")}</strong><small>${escapeHtml(proposed.package_code || "Account only")}</small></div>
        <div><span>Project</span><strong>${escapeHtml(proposed.project_name || "No project")}</strong><small>${escapeHtml(proposed.project_lane || "No lane")}</small></div>
      </div>
      <div class="admin-preview-section"><span>Records written</span><div>${renderChipList(preview && preview.records_to_write, "Identity and audit records")}</div></div>
      ${warnings.length ? `<div class="admin-preview-warning">${warnings.map(function (item) { return `<p>${escapeHtml(item)}</p>`; }).join("")}</div>` : ""}
      <p class="admin-preview-assurance">No paid order is fabricated and no Stripe transaction is created or changed.</p>
    `;
  }

  function syncCreateExecuteAvailability() {
    const payload = createAccountPayloadFromDialog();
    const confirmed = Boolean(document.querySelector("[data-admin-create-confirm]")?.checked);
    const previewCurrent = Boolean(
      state.createAccountPreview &&
      state.createAccountPreview.fingerprint === createAccountPreviewFingerprint(payload),
    );
    setButtonEnabled(
      document.querySelector("[data-admin-create-execute]"),
      confirmed && previewCurrent && !validateCreateAccountPayload(payload),
    );
  }

  function openSuperAdminCreateAccount() {
    if (!state.isSuperAdmin) {
      setPageStatus("CEO Master Administrator access is required.", "error");
      return;
    }
    const dialog = dialogByName("create");
    const form = document.querySelector("[data-admin-create-form]");
    if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
    form.reset();
    populateCreatePackageOptions();
    syncCreatePackageFields();
    resetCreatePreview();
    openDialog(dialog);
    const nameInput = document.querySelector('[data-admin-create-field="full_name"]');
    if (nameInput instanceof HTMLInputElement) nameInput.focus();
  }

  async function previewSuperAdminCreateAccount() {
    if (!state.isSuperAdmin) return;
    syncCreatePackageFields();
    const payload = createAccountPayloadFromDialog();
    const validationError = validateCreateAccountPayload(payload);
    if (validationError) {
      resetCreatePreview(validationError);
      setPageStatus(validationError, "error");
      return;
    }
    setPageStatus("Building account creation preview...", "info");
    try {
      const preview = await postJson("/admin/control-center/super-admin/users/preview", {
        ...payload,
        confirmed: false,
      });
      state.createAccountPreview = {
        fingerprint: createAccountPreviewFingerprint(payload),
        payload: preview || {},
      };
      renderCreateAccountPreview(preview || {});
      syncCreateExecuteAvailability();
      setPageStatus("Account creation preview is ready. No records have been written.", "success");
    } catch (error) {
      resetCreatePreview(error.message || "Unable to preview account creation.");
      setPageStatus(error.message || "Unable to preview account creation.", "error");
    }
  }

  async function runSuperAdminCreateAccount(event) {
    if (event) event.preventDefault();
    if (!state.isSuperAdmin) return;
    const payload = createAccountPayloadFromDialog();
    const validationError = validateCreateAccountPayload(payload);
    const previewCurrent = Boolean(
      state.createAccountPreview &&
      state.createAccountPreview.fingerprint === createAccountPreviewFingerprint(payload),
    );
    if (validationError || !previewCurrent || !document.querySelector("[data-admin-create-confirm]")?.checked) {
      setPageStatus(validationError || "Preview and confirm the current account details before execution.", "error");
      syncCreateExecuteAvailability();
      return;
    }
    setButtonEnabled(document.querySelector("[data-admin-create-execute]"), false);
    setPageStatus("Executing governed account creation...", "info");
    try {
      const operation = await submitGovernedOperation(
        "customer_account_create",
        { customer_email: payload.email },
        {
          user_payload: {
            full_name: payload.full_name,
            email: payload.email,
            phone_number: payload.phone_number,
            package_code: payload.package_code,
            project_name: payload.project_name,
            package_grant_type: payload.package_grant_type,
          },
        },
        payload.reason,
      );
      closeDialog(dialogByName("create"));
      await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
      setPageStatus(
        kernelOperationMessage(
          operation,
          payload.package_code
            ? "Customer identity, project, and package entitlement created pending activation."
            : "Customer identity created pending activation.",
        ),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to create account.", "error");
      syncCreateExecuteAvailability();
    }
  }

  async function runSuperAdminTransferOwnership(projectId) {
    const ownerNode = document.querySelector("[data-super-admin-new-owner-id]");
    const newOwnerUserId = normalizeValue(ownerNode && ownerNode.value);
    const reason = normalizeValue(window.prompt("Reason for ownership transfer:") || "");
    if (!newOwnerUserId || !reason || !window.confirm("Confirm project ownership transfer through the Continuity Kernel?")) return;
    try {
      const operation = await submitGovernedOperation(
        "project_ownership_transfer",
        { project_id: projectId },
        { new_owner_user_id: newOwnerUserId },
        reason,
      );
      await loadKernelStatus();
      await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(
        kernelOperationMessage(operation, "Project ownership transferred."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to transfer ownership.", "error");
    }
  }

  async function runSuperAdminUserUpdate(userId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }

    const reason = promptExecutionReason("Apply user profile and account updates");
    if (reason === null || !window.confirm("Apply user updates through the Continuity Kernel?")) return;
    setPageStatus("Saving user updates...", "info");
    try {
      const operation = await submitGovernedOperation(
        "user_profile_update",
        { user_id: userId },
        { user_payload: collectSuperAdminUserPayload() },
        reason,
      );
      await Promise.allSettled([loadKernelStatus(), loadCases()]);
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(
        kernelOperationMessage(operation, "User updates saved."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to update user.", "error");
    }
  }

  function currentIdentityRecord() {
    return (state.workspace && state.workspace.tabs && state.workspace.tabs.identity) || {};
  }

  function lifecycleIsDestructive(workflow) {
    return Boolean(workflow && ["suspend", "disable", "archive"].includes(workflow.action));
  }

  function renderLifecyclePreview(preview) {
    const node = document.querySelector("[data-admin-lifecycle-preview]");
    if (!node) return;
    const before = (preview && preview.before) || {};
    const after = (preview && preview.proposed_after) || {};
    const ownership = (preview && preview.ownership_dependencies) || {};
    const ownershipRows = Object.entries(ownership).filter(function (entry) { return Number(entry[1] || 0) > 0; });
    const warnings = asArray(preview && preview.warnings);
    const blocked = Boolean(preview && preview.blocked);
    node.dataset.state = blocked ? "error" : "success";
    node.innerHTML = `
      <div class="admin-preview-heading">
        <h3>Impact preview</h3>
        ${statusChip(blocked ? "Blocked" : "Ready for confirmation", blocked ? "error" : "success")}
      </div>
      <div class="admin-preview-facts">
        <div><span>Current status</span><strong>${escapeHtml(titleize(before.status || "active"))}</strong></div>
        <div><span>Resulting status</span><strong>${escapeHtml(titleize(after.status || "—"))}</strong></div>
        <div><span>Login access</span><strong>${after.login_enabled ? "Enabled" : "Disabled immediately"}</strong></div>
        <div><span>Owned workspace handling</span><strong>${after.archive_owned_records ? "Archive active access" : "Account only"}</strong></div>
      </div>
      <div class="admin-preview-section"><span>Active dependencies</span><div>${
        ownershipRows.length
          ? ownershipRows.map(function (entry) { return `<span class="admin-scope-chip">${escapeHtml(titleize(entry[0]))}: ${escapeHtml(entry[1])}</span>`; }).join("")
          : '<span class="admin-scope-empty">No active owned dependencies</span>'
      }</div></div>
      ${after.archive_owned_records ? `<div class="admin-preview-section"><span>Access records archived</span><div>${renderChipList(Object.keys((preview && preview.records_to_archive) || {}), "No owned access records")}</div></div>` : ""}
      <div class="admin-preview-section"><span>Business and evidence records preserved</span><div>${renderChipList(preview && preview.records_preserved, "Audit history")}</div></div>
      ${warnings.length ? `<div class="admin-preview-warning">${warnings.map(function (item) { return `<p>${escapeHtml(item)}</p>`; }).join("")}</div>` : ""}
      <p class="admin-preview-assurance">Closure is a recoverable access archive, not an untraceable database deletion.</p>
    `;
  }

  function syncLifecycleExecuteAvailability() {
    const workflow = state.lifecycleWorkflow;
    const execute = document.querySelector("[data-admin-lifecycle-execute]");
    if (!workflow || !workflow.preview) {
      setButtonEnabled(execute, false);
      return;
    }
    const reason = fieldValue("[data-admin-lifecycle-reason]");
    const confirmed = Boolean(document.querySelector("[data-admin-lifecycle-confirm]")?.checked);
    const typed = fieldValue("[data-admin-lifecycle-typed-confirm]").toLowerCase();
    const typedMatches = !workflow.closeOwned || typed === workflow.email.toLowerCase();
    setButtonEnabled(execute, !workflow.preview.blocked && reason.length >= 3 && confirmed && typedMatches);
  }

  async function openSuperAdminLifecycle(userId, action, archiveOwnedRecords) {
    if (!state.isSuperAdmin) {
      setPageStatus("CEO Master Administrator access is required.", "error");
      return;
    }
    const identity = currentIdentityRecord();
    const closeOwned = Boolean(archiveOwnedRecords && action === "archive");
    state.lifecycleWorkflow = {
      userId,
      action,
      closeOwned,
      email: normalizeValue(identity.email),
      name: normalizeValue(identity.full_name) || "Selected account",
      preview: null,
    };
    const dialog = dialogByName("lifecycle");
    const form = document.querySelector("[data-admin-lifecycle-form]");
    if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
    form.reset();
    const title = document.querySelector("[data-admin-lifecycle-title]");
    const target = document.querySelector("[data-admin-lifecycle-target]");
    const typedWrap = document.querySelector("[data-admin-lifecycle-typed-wrap]");
    const confirmLabel = document.querySelector("[data-admin-lifecycle-confirm-label]");
    const execute = document.querySelector("[data-admin-lifecycle-execute]");
    if (title) title.textContent = closeOwned ? "Close account and owned workspaces" : `${titleize(action)} account`;
    if (target) target.textContent = `${state.lifecycleWorkflow.name} · ${state.lifecycleWorkflow.email || userId}`;
    if (typedWrap) typedWrap.hidden = !closeOwned;
    if (confirmLabel) {
      confirmLabel.textContent = closeOwned
        ? "I confirm login, roles, memberships, entitlements, and active owned workspaces should be archived."
        : `I confirm this account should be ${titleize(action).toLowerCase()}.`;
    }
    if (execute instanceof HTMLButtonElement) {
      execute.textContent = closeOwned ? "Close Account & Workspaces" : `${titleize(action)} Account`;
      execute.classList.toggle("btn-danger", lifecycleIsDestructive(state.lifecycleWorkflow));
      execute.classList.toggle("btn-primary", !lifecycleIsDestructive(state.lifecycleWorkflow));
    }
    const previewNode = document.querySelector("[data-admin-lifecycle-preview]");
    if (previewNode) previewNode.innerHTML = "<h3>Impact preview</h3><p>Loading the account’s dependencies and protected records…</p>";
    setButtonEnabled(execute, false);
    openDialog(dialog);
    try {
      const preview = await postJson(
        `/admin/control-center/super-admin/users/${encodeURIComponent(userId)}/status-action/preview`,
        { action, archive_owned_records: closeOwned, confirmed: false, reason: "" },
      );
      if (!state.lifecycleWorkflow || state.lifecycleWorkflow.userId !== userId || state.lifecycleWorkflow.action !== action) return;
      state.lifecycleWorkflow.preview = preview || {};
      renderLifecyclePreview(preview || {});
      syncLifecycleExecuteAvailability();
    } catch (error) {
      if (previewNode) {
        previewNode.dataset.state = "error";
        previewNode.innerHTML = `<h3>Impact preview unavailable</h3><p>${escapeHtml(error.message || "Unable to load account dependencies.")}</p>`;
      }
      setPageStatus(error.message || "Unable to preview the account action.", "error");
    }
  }

  async function runSuperAdminUserStateAction(event) {
    if (event) event.preventDefault();
    const workflow = state.lifecycleWorkflow;
    if (!state.isSuperAdmin || !workflow || !workflow.preview) return;
    const reason = fieldValue("[data-admin-lifecycle-reason]");
    const confirmed = Boolean(document.querySelector("[data-admin-lifecycle-confirm]")?.checked);
    const typed = fieldValue("[data-admin-lifecycle-typed-confirm]").toLowerCase();
    if (
      workflow.preview.blocked ||
      reason.length < 3 ||
      !confirmed ||
      (workflow.closeOwned && typed !== workflow.email.toLowerCase())
    ) {
      setPageStatus("Complete the reason and confirmation shown in the impact preview before execution.", "error");
      syncLifecycleExecuteAvailability();
      return;
    }
    setButtonEnabled(document.querySelector("[data-admin-lifecycle-execute]"), false);
    setPageStatus("Executing governed account lifecycle action...", "info");
    try {
      const operation = await submitGovernedOperation(
        "account_lifecycle",
        { user_id: workflow.userId },
        { lifecycle_action: workflow.action, archive_owned_records: workflow.closeOwned },
        reason,
      );
      closeDialog(dialogByName("lifecycle"));
      state.lifecycleWorkflow = null;
      await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(kernelOperationMessage(operation, "Account lifecycle updated."), kernelOperationStatusType(operation));
    } catch (error) {
      setPageStatus(error.message || "Unable to update account status.", "error");
      syncLifecycleExecuteAvailability();
    }
  }

  function teamOfficerEmail(officer) {
    return normalizeValue(officer && (officer.officer_email || officer.email)).toLowerCase();
  }

  function selectedTeamOfficer() {
    const email = fieldValue('[data-admin-team-field="officer_email"]').toLowerCase();
    return state.teamAccess.officers.find(function (officer) {
      return teamOfficerEmail(officer) === email;
    }) || null;
  }

  function selectedTeamTemplate() {
    const roleCode = fieldValue('[data-admin-team-field="role_template"]');
    return state.teamAccess.roleTemplates[roleCode] || null;
  }

  function populateTeamAccessControls() {
    const officerSelect = document.querySelector('[data-admin-team-field="officer_email"]');
    const templateSelect = document.querySelector('[data-admin-team-field="role_template"]');
    if (officerSelect instanceof HTMLSelectElement) {
      officerSelect.innerHTML = '<option value="">Select officer</option>' + state.teamAccess.officers
        .map(function (officer) {
          const email = teamOfficerEmail(officer);
          const missing = normalizeLower(officer.status) === "missing_user";
          const label = `${officer.full_name || email} · ${officer.business_title || titleize(officer.current_role || "officer")}`;
          return `<option value="${escapeHtml(email)}" ${missing ? "disabled" : ""}>${escapeHtml(label)}${missing ? " · account missing" : ""}</option>`;
        })
        .join("");
    }
    if (templateSelect instanceof HTMLSelectElement) {
      templateSelect.innerHTML = '<option value="">Select job template</option>' + Object.entries(state.teamAccess.roleTemplates)
        .map(function (entry) {
          const template = entry[1] || {};
          return `<option value="${escapeHtml(entry[0])}">${escapeHtml(template.name || titleize(entry[0]))}</option>`;
        })
        .join("");
    }
    const ceoIdentity = document.querySelector("[data-admin-team-ceo-identity]");
    if (ceoIdentity) {
      ceoIdentity.textContent = normalizeValue(state.teamAccess.ceoIdentity && state.teamAccess.ceoIdentity.email) || "l.robinson@tomboflight.com";
    }
  }

  function renderTeamScope() {
    const node = document.querySelector("[data-admin-team-scope]");
    if (!node) return;
    const template = selectedTeamTemplate();
    if (!template) {
      node.innerHTML = "<h3>Job scope</h3><p>Select a job template to see exactly which queues, records, and actions it exposes.</p>";
      return;
    }
    const queues = asArray(template.allowed_queues).map(function (queue) {
      return (QUEUE_META[queue] && QUEUE_META[queue][0]) || titleize(queue);
    });
    const actions = asArray(template.allowed_actions).concat(asArray(template.allowed_bulk_actions));
    node.innerHTML = `
      <div class="admin-preview-heading"><h3>${escapeHtml(template.name || titleize(template.role_code))}</h3>${statusChip("Job-scoped", "success")}</div>
      <p>${escapeHtml(template.description || "Scoped Tomb of Light operational access.")}</p>
      <div class="admin-preview-section"><span>Visible work queues (${queues.length})</span><div>${renderChipList(queues, "No operational queues")}</div></div>
      <div class="admin-preview-section"><span>Executable case actions (${actions.length})</span><div>${renderChipList(actions, "Read-only role")}</div></div>
      <div class="admin-preview-section"><span>Backend permissions (${asArray(template.permissions).length})</span><div>${renderChipList(template.permissions, "No permissions")}</div></div>
    `;
  }

  function teamAccessFingerprint(officer, template) {
    return JSON.stringify({
      officer_email: teamOfficerEmail(officer),
      role_template: template && template.role_code,
      revoke_permissions: asArray(officer && officer.permission_overrides).slice().sort(),
    });
  }

  function resetTeamAccessPreview(message) {
    state.teamAccessPreview = null;
    const node = document.querySelector("[data-admin-team-preview]");
    if (node) {
      node.innerHTML = `<h3>Access-change preview</h3><p>${escapeHtml(message || "Preview compares current access with the selected job template. No access changes have been applied.")}</p>`;
    }
    setButtonEnabled(document.querySelector("[data-admin-team-execute]"), false);
  }

  function renderTeamAccessPreview(preview, officer, template) {
    const node = document.querySelector("[data-admin-team-preview]");
    if (!node) return;
    const before = (preview && preview.before) || {};
    const after = (preview && preview.proposed_after) || {};
    node.innerHTML = `
      <div class="admin-preview-heading"><h3>Access-change preview</h3>${statusChip("Ready for confirmation", "success")}</div>
      <div class="admin-preview-facts">
        <div><span>Officer</span><strong>${escapeHtml((officer && officer.full_name) || teamOfficerEmail(officer))}</strong><small>${escapeHtml(teamOfficerEmail(officer))}</small></div>
        <div><span>Current role</span><strong>${escapeHtml(asArray(before.role_assignments).map(titleize).join(", ") || titleize(officer && officer.current_role))}</strong></div>
        <div><span>New job template</span><strong>${escapeHtml((template && template.name) || titleize(template && template.role_code))}</strong></div>
        <div><span>Custom overrides</span><strong>${asArray(after.permission_overrides).length ? escapeHtml(asArray(after.permission_overrides).join(", ")) : "Removed — exact job scope"}</strong></div>
      </div>
      <p class="admin-preview-assurance">The CEO Master Administrator role is not assignable here. The officer will see and execute only the selected job scope.</p>
    `;
  }

  function syncTeamAccessExecuteAvailability() {
    const officer = selectedTeamOfficer();
    const template = selectedTeamTemplate();
    const reason = fieldValue('[data-admin-team-field="reason"]');
    const confirmed = Boolean(document.querySelector("[data-admin-team-confirm]")?.checked);
    const previewCurrent = Boolean(
      officer && template && state.teamAccessPreview &&
      state.teamAccessPreview.fingerprint === teamAccessFingerprint(officer, template),
    );
    setButtonEnabled(
      document.querySelector("[data-admin-team-execute]"),
      previewCurrent && reason.length >= 3 && confirmed,
    );
  }

  async function openTeamAccessDialog() {
    if (!state.isSuperAdmin) {
      setPageStatus("CEO Master Administrator access is required.", "error");
      return;
    }
    const dialog = dialogByName("team");
    const form = document.querySelector("[data-admin-team-form]");
    if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
    form.reset();
    resetTeamAccessPreview("Loading the CEO-owned role templates and active officers…");
    openDialog(dialog);
    try {
      await loadTeamAccessBlueprint();
      populateTeamAccessControls();
      renderTeamScope();
      resetTeamAccessPreview();
    } catch (error) {
      resetTeamAccessPreview(error.message || "Unable to load team access.");
      setPageStatus(error.message || "Unable to load team access.", "error");
    }
  }

  async function previewTeamAccess() {
    const officer = selectedTeamOfficer();
    const template = selectedTeamTemplate();
    const reason = fieldValue('[data-admin-team-field="reason"]');
    if (!officer || !template) {
      resetTeamAccessPreview("Select an officer and a job template first.");
      setPageStatus("Select an officer and a job template first.", "error");
      return;
    }
    if (reason.length < 3) {
      resetTeamAccessPreview("An operational reason of at least 3 characters is required.");
      setPageStatus("An operational reason of at least 3 characters is required.", "error");
      return;
    }
    const email = teamOfficerEmail(officer);
    const revokePermissions = asArray(officer.permission_overrides);
    setPageStatus("Building officer access preview...", "info");
    try {
      const preview = await postJson("/admin/control-center/super-admin/officers/permissions/preview", {
        officer_email: email,
        role_assignments: [template.role_code],
        grant_permissions: [],
        revoke_permissions: revokePermissions,
        reason,
        confirmed: false,
      });
      state.teamAccessPreview = {
        fingerprint: teamAccessFingerprint(officer, template),
        payload: preview || {},
      };
      renderTeamAccessPreview(preview || {}, officer, template);
      syncTeamAccessExecuteAvailability();
      setPageStatus("Officer access preview is ready. No permissions have changed.", "success");
    } catch (error) {
      resetTeamAccessPreview(error.message || "Unable to preview officer access.");
      setPageStatus(error.message || "Unable to preview officer access.", "error");
    }
  }

  async function applyTeamAccess(event) {
    if (event) event.preventDefault();
    const officer = selectedTeamOfficer();
    const template = selectedTeamTemplate();
    const reason = fieldValue('[data-admin-team-field="reason"]');
    const confirmed = Boolean(document.querySelector("[data-admin-team-confirm]")?.checked);
    const previewCurrent = Boolean(
      officer && template && state.teamAccessPreview &&
      state.teamAccessPreview.fingerprint === teamAccessFingerprint(officer, template),
    );
    if (!previewCurrent || reason.length < 3 || !confirmed) {
      setPageStatus("Preview and confirm the current job assignment before applying access.", "error");
      syncTeamAccessExecuteAvailability();
      return;
    }
    const email = teamOfficerEmail(officer);
    const parameters = {
      role_assignments: [template.role_code],
      grant_permissions: [],
      revoke_permissions: asArray(officer.permission_overrides),
    };
    setButtonEnabled(document.querySelector("[data-admin-team-execute]"), false);
    setPageStatus("Applying job-scoped officer access through the Continuity Kernel...", "info");
    try {
      const operation = await submitGovernedOperation(
        "officer_permissions",
        { officer_email: email },
        parameters,
        reason,
      );
      await Promise.allSettled([loadKernelStatus(), loadTeamAccessBlueprint(true)]);
      closeDialog(dialogByName("team"));
      setPageStatus(
        kernelOperationMessage(operation, `${template.name || titleize(template.role_code)} access applied to ${officer.full_name || email}.`),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to apply officer access.", "error");
      syncTeamAccessExecuteAvailability();
    }
  }

  async function runSuperAdminPasswordReset(userId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    const reason = promptExecutionReason("Send a password reset to this account");
    if (reason === null || !window.confirm("Send a password-reset link through the Continuity Kernel?")) return;
    setPageStatus("Issuing password reset...", "info");
    try {
      const operation = await submitGovernedOperation(
        "user_password_reset",
        { user_id: userId },
        {},
        reason,
      );
      await loadKernelStatus();
      setPageStatus(
        kernelOperationMessage(operation, "Password-reset link sent to the account email."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to issue password reset.", "error");
    }
  }

  function collectSuperAdminPackagePayload() {
    const payload = { package_code: "", project_lane: "", order_status: "" };
    document.querySelectorAll("[data-super-admin-package-field]").forEach(function (node) {
      const key = node.getAttribute("data-super-admin-package-field");
      if (!key) return;
      payload[key] = normalizeValue(node.value);
    });
    return payload;
  }

  function collectSuperAdminServicePayload() {
    const payload = {};
    document.querySelectorAll("[data-super-admin-service-field]").forEach(function (node) {
      const key = node.getAttribute("data-super-admin-service-field");
      if (!key) return;
      if (node instanceof HTMLInputElement && node.type === "checkbox") {
        payload[key] = Boolean(node.checked);
        return;
      }
      const value = normalizeValue(node.value);
      if (key === "add_addons" || key === "remove_addons") {
        payload[key] = value
          ? value
              .split(",")
              .map(function (part) {
                return normalizeValue(part);
              })
              .filter(Boolean)
          : [];
        return;
      }
      if (["storage_adjustment_gb", "upload_adjustment", "member_allowance_adjustment"].includes(key)) {
        payload[key] = value === "" ? 0 : Number(value);
        return;
      }
      payload[key] = value;
    });
    const packagePayload = collectSuperAdminPackagePayload();
    payload.package_code = packagePayload.package_code || "";
    payload.project_lane = packagePayload.project_lane || "";
    payload.reason = packagePayload.reason || "";
    return payload;
  }

  function renderSuperAdminPackagePreview(payload) {
    const node = document.querySelector("[data-super-admin-package-preview-output]");
    if (!node) return;
    const changes = Array.isArray(payload && payload.changes) ? payload.changes : [];
    if (!changes.length) {
      node.textContent = "No field changes detected.";
      return;
    }
    node.innerHTML = changes
      .map(function (change) {
        return `${escapeHtml(titleize(change.scope))} · ${escapeHtml(titleize(change.field))}: ${escapeHtml(renderScalar(change.before))} to ${escapeHtml(renderScalar(change.after))}`;
      })
      .join("<br />");
  }

  async function runSuperAdminPackagePreview(projectId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    setPageStatus("Generating package-change preview...", "info");
    try {
      const payload = await postJson(
        `/admin/control-center/super-admin/projects/${encodeURIComponent(projectId)}/package-change/preview`,
        collectSuperAdminPackagePayload(),
      );
      renderSuperAdminPackagePreview(payload || {});
      setPageStatus("Package-change preview ready.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to preview package change.", "error");
    }
  }

  function clearSuperAdminPreviewOutput() {
    const node = document.querySelector("[data-super-admin-package-preview-output]");
    if (!node) return;
    node.textContent = "";
  }

  async function runSuperAdminServicePreview(projectId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    setPageStatus("Generating service-control preview...", "info");
    try {
      const payload = await postJson(
        `/admin/control-center/super-admin/projects/${encodeURIComponent(projectId)}/service-controls/preview`,
        collectSuperAdminServicePayload(),
      );
      renderSuperAdminPackagePreview(payload || {});
      setPageStatus("Service-control preview ready.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to preview service controls.", "error");
    }
  }

  async function runSuperAdminServiceApply(projectId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    const parameters = collectSuperAdminServicePayload();
    const reason = normalizeValue(parameters.reason);
    if (reason.length < 3) {
      setPageStatus("A reason of at least 3 characters is required for service-control execution.", "error");
      return;
    }
    if (!window.confirm("Apply service controls through the Continuity Kernel while preserving Stripe purchase history?")) return;
    setPageStatus("Applying service controls...", "info");
    try {
      const operation = await submitGovernedOperation(
        "service_controls",
        { project_id: projectId },
        parameters,
        reason,
      );
      renderSuperAdminPackagePreview(
        operation.execution_result || operation.proposed_after_snapshot || operation || {},
      );
      await loadOverview();
      await loadCases();
      await loadKernelStatus();
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(kernelOperationMessage(operation, "Service controls applied."), kernelOperationStatusType(operation));
    } catch (error) {
      setPageStatus(error.message || "Unable to apply service controls.", "error");
    }
  }

  async function runSuperAdminPackageApply(projectId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }

    const parameters = collectSuperAdminPackagePayload();
    const reason = normalizeValue(parameters.reason);
    if (reason.length < 3) {
      setPageStatus("A reason of at least 3 characters is required for package execution.", "error");
      return;
    }
    if (!window.confirm("Apply the package change through the Continuity Kernel and repair consistency across project/order/entitlements?")) return;
    setPageStatus("Applying package change...", "info");
    try {
      const operation = await submitGovernedOperation(
        "package_change",
        { project_id: projectId },
        parameters,
        reason,
      );
      renderSuperAdminPackagePreview(
        operation.execution_result || operation.proposed_after_snapshot || operation || {},
      );
      await loadOverview();
      await loadCases();
      await loadKernelStatus();
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(
        kernelOperationMessage(operation, "Package change applied and synchronized."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to apply package change.", "error");
    }
  }

  async function runSuperAdminPackageLifecycle(projectId, action, previewOnly) {
    if (!state.isSuperAdmin) return;
    if (previewOnly) {
      try {
        const payload = await postJson(
          `/admin/control-center/super-admin/projects/${encodeURIComponent(projectId)}/package-revoke/preview`,
          {},
        );
        renderSuperAdminPackagePreview(payload || {});
        setPageStatus("Package revocation preview ready.", "success");
      } catch (error) {
        setPageStatus(error.message || "Unable to preview package revocation.", "error");
      }
      return;
    }

    const reason = promptExecutionReason(`${titleize(action)} this package`);
    if (reason === null || !window.confirm(`Confirm package ${action} through the Continuity Kernel?`)) return;
    try {
      const operation = await submitGovernedOperation(
        action === "restore" ? "package_restore" : "package_revoke",
        { project_id: projectId },
        {},
        reason,
      );
      renderSuperAdminPackagePreview(
        operation.execution_result || operation.proposed_after_snapshot || operation || {},
      );
      await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(
        kernelOperationMessage(operation, `Package ${action} completed.`),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || `Unable to ${action} package.`, "error");
    }
  }

  function collectSuperAdminRepairPayload() {
    const payload = {};
    document.querySelectorAll("[data-super-admin-repair-field]").forEach(function (node) {
      const key = node.getAttribute("data-super-admin-repair-field");
      if (!key) return;
      if (node instanceof HTMLInputElement && node.type === "checkbox") {
        payload[key] = Boolean(node.checked);
        return;
      }
      const value = normalizeValue(node.value);
      if (value) payload[key] = value;
    });
    return payload;
  }

  async function runSuperAdminCaseRepair(caseId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    const payload = collectSuperAdminRepairPayload();
    if (!payload.action) {
      setPageStatus("Select a repair tool first.", "error");
      return;
    }
    if (!payload.reason) {
      setPageStatus("A repair reason is required for audit logging.", "error");
      return;
    }
    if (
      (payload.action === "cancel_invite" || payload.action === "fix_family_relationship") &&
      !payload.confirm_destructive &&
      !window.confirm("This action can overwrite customer linkage data. Continue?")
    ) {
      return;
    }
    setPageStatus("Applying super admin repair...", "info");
    try {
      const operation = await submitGovernedOperation(
        "case_repair",
        { case_id: caseId },
        { repair_action: payload.action, repair_payload: payload },
        payload.reason,
      );
      await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus(
        kernelOperationMessage(operation, "Super admin repair completed and logged."),
        kernelOperationStatusType(operation),
      );
    } catch (error) {
      setPageStatus(error.message || "Unable to complete super admin repair.", "error");
    }
  }

  function bindEvents() {
    document.addEventListener("click", function (event) {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const dialogClose = target.closest("[data-admin-dialog-close]");
      if (dialogClose) {
        const name = dialogClose.getAttribute("data-admin-dialog-close") || "";
        closeDialog(dialogByName(name));
        if (name === "lifecycle") state.lifecycleWorkflow = null;
        return;
      }

      const bootstrapRetry = target.closest("[data-admin-bootstrap-retry]");
      if (bootstrapRetry) {
        const retryFn = lastFailedRetry;
        clearBootstrapError();
        setPageStatus("Retrying...", "info");
        if (typeof retryFn === "function") {
          retryFn();
        } else {
          bootstrapAccessAndData();
        }

        return;
      }

      const superAdminCreateAccount = target.closest("[data-super-admin-create-account]");
      if (superAdminCreateAccount) {
        openSuperAdminCreateAccount();
        return;
      }

      const superAdminManageTeamAccess = target.closest("[data-super-admin-manage-team-access]");
      if (superAdminManageTeamAccess) {
        openTeamAccessDialog();
        return;
      }

      const createPreviewAction = target.closest("[data-admin-create-preview-action]");
      if (createPreviewAction) {
        previewSuperAdminCreateAccount();
        return;
      }

      const teamPreviewAction = target.closest("[data-admin-team-preview-action]");
      if (teamPreviewAction) {
        previewTeamAccess();
        return;
      }

      const kernelRefresh = target.closest("[data-admin-kernel-refresh]");
      if (kernelRefresh) {
        loadKernelStatus();
        return;
      }

      const kernelApproveExecute = target.closest("[data-admin-kernel-approve-execute]");
      if (kernelApproveExecute) {
        const operationId = kernelApproveExecute.getAttribute("data-admin-kernel-approve-execute");
        if (operationId) approveAndExecuteKernelOperation(operationId);
        return;
      }

      const kernelClose = target.closest("[data-admin-kernel-close]");
      if (kernelClose) {
        const operationId = kernelClose.getAttribute("data-admin-kernel-close");
        if (operationId) closeKernelOperation(operationId);
        return;
      }

      const queueButton = target.closest("[data-case-queue]");
      if (queueButton) {
        const queue = queueButton.getAttribute("data-case-queue") || "overview";
        if (!isAllowedQueue(queue)) return;
        state.queue = queue;
        applyRailSelection();
        loadCases();
        return;
      }

      const diagnosticsToggle = target.closest("[data-admin-diagnostics-toggle]");
      if (diagnosticsToggle) {
        toggleDiagnosticsPanel();
        return;
      }

      const fulfillmentActionButton = target.closest("[data-fulfillment-action]");
      if (fulfillmentActionButton) {
        const action = fulfillmentActionButton.getAttribute("data-fulfillment-action") || "";
        const orderId = fulfillmentActionButton.getAttribute("data-fulfillment-order") || "";
        if (action && orderId) runFulfillmentAction(orderId, action);
        return;
      }

      const stripeOpsButton = target.closest("[data-stripe-ops-action]");
      if (stripeOpsButton) {
        const card = stripeOpsButton.closest("[data-stripe-ops-card]");
        const action = stripeOpsButton.getAttribute("data-stripe-ops-action") || "";
        if (card && action) runStripeOpsAction(card, action);
        return;
      }

      const openCaseButton = target.closest("[data-open-case]");
      if (openCaseButton) {
        const caseId = openCaseButton.getAttribute("data-open-case");
        if (caseId) loadCaseWorkspace(caseId);
        return;
      }

      const caseRow = target.closest("[data-case-row]");
      if (caseRow && !target.closest("[data-case-select]") && !target.closest(".admin-case-select")) {
        const caseId = caseRow.getAttribute("data-case-row");
        if (caseId) loadCaseWorkspace(caseId);
        return;
      }

      const caseActionButton = target.closest("[data-admin-case-action]");
      if (caseActionButton) {
        if (caseActionButton.disabled || caseActionButton.classList.contains("is-disabled")) return;
        const action = caseActionButton.getAttribute("data-admin-case-action");
        if (action) runCaseAction(action);
        return;
      }

      const bulkActionButton = target.closest("[data-admin-bulk-action]");
      if (bulkActionButton) {
        if (bulkActionButton.disabled || bulkActionButton.classList.contains("is-disabled")) return;
        const action = bulkActionButton.getAttribute("data-admin-bulk-action");
        if (action) runBulkAction(action);
        return;
      }

      const exportOpsButton = target.closest("[data-admin-export-ops-report]");
      if (exportOpsButton) {
        exportOpsReport();
        return;
      }

      const superAdminUserSave = target.closest("[data-super-admin-user-save]");
      if (superAdminUserSave) {
        const userId = superAdminUserSave.getAttribute("data-super-admin-user-save");
        if (userId) runSuperAdminUserUpdate(userId);
        return;
      }

      const superAdminUserAction = target.closest("[data-super-admin-user-action]");
      if (superAdminUserAction) {
        const action = superAdminUserAction.getAttribute("data-super-admin-user-action");
        const userId = superAdminUserAction.getAttribute("data-super-admin-user-id");
        const archiveOwnedRecords = superAdminUserAction.getAttribute("data-super-admin-archive-owned") === "true";
        if (action && userId) openSuperAdminLifecycle(userId, action, archiveOwnedRecords);
        return;
      }

      const superAdminPasswordReset = target.closest("[data-super-admin-user-password-reset]");
      if (superAdminPasswordReset) {
        const userId = superAdminPasswordReset.getAttribute("data-super-admin-user-password-reset");
        if (userId) runSuperAdminPasswordReset(userId);
        return;
      }

      const superAdminPackagePreview = target.closest("[data-super-admin-package-preview]");
      if (superAdminPackagePreview) {
        const projectId = superAdminPackagePreview.getAttribute("data-super-admin-package-preview");
        if (projectId) runSuperAdminPackagePreview(projectId);
        return;
      }

      const superAdminPackageApply = target.closest("[data-super-admin-package-apply]");
      if (superAdminPackageApply) {
        const projectId = superAdminPackageApply.getAttribute("data-super-admin-package-apply");
        if (projectId) runSuperAdminPackageApply(projectId);
        return;
      }

      const superAdminServicePreview = target.closest("[data-super-admin-service-preview]");
      if (superAdminServicePreview) {
        const projectId = superAdminServicePreview.getAttribute("data-super-admin-service-preview");
        if (projectId) runSuperAdminServicePreview(projectId);
        return;
      }

      const superAdminServiceApply = target.closest("[data-super-admin-service-apply]");
      if (superAdminServiceApply) {
        const projectId = superAdminServiceApply.getAttribute("data-super-admin-service-apply");
        if (projectId) runSuperAdminServiceApply(projectId);
        return;
      }

      const packageRevokePreview = target.closest("[data-super-admin-package-revoke-preview]");
      if (packageRevokePreview) {
        runSuperAdminPackageLifecycle(packageRevokePreview.getAttribute("data-super-admin-package-revoke-preview"), "revoke", true);
        return;
      }

      const packageRevoke = target.closest("[data-super-admin-package-revoke]");
      if (packageRevoke) {
        runSuperAdminPackageLifecycle(packageRevoke.getAttribute("data-super-admin-package-revoke"), "revoke", false);
        return;
      }

      const packageRestore = target.closest("[data-super-admin-package-restore]");
      if (packageRestore) {
        runSuperAdminPackageLifecycle(packageRestore.getAttribute("data-super-admin-package-restore"), "restore", false);
        return;
      }

      const superAdminPreviewCancel = target.closest("[data-super-admin-preview-cancel]");
      if (superAdminPreviewCancel) {
        clearSuperAdminPreviewOutput();
        setPageStatus("Preview canceled with no write.", "info");
        return;
      }

      const superAdminRepair = target.closest("[data-super-admin-repair-run]");
      if (superAdminRepair) {
        const caseId = superAdminRepair.getAttribute("data-super-admin-repair-run");
        if (caseId) runSuperAdminCaseRepair(caseId);
        return;
      }

      const transferOwnership = target.closest("[data-super-admin-transfer-ownership]");
      if (transferOwnership) {
        runSuperAdminTransferOwnership(transferOwnership.getAttribute("data-super-admin-transfer-ownership"));
        return;
      }

      const tabButton = target.closest("[data-admin-case-tab]");
      if (tabButton) {
        const tab = tabButton.getAttribute("data-admin-case-tab") || "identity";
        if (!isAllowedTab(tab)) return;
        state.selectedTab = tab;
        applyTabSelection();
        renderWorkspaceTab();
        return;
      }

      const impersonationStart = target.closest("[data-admin-impersonation-start]");
      if (impersonationStart) {
        const caseId = impersonationStart.getAttribute("data-admin-impersonation-start");
        const reasonInput = document.querySelector("[data-admin-impersonation-start-reason]");
        const reason = reasonInput instanceof HTMLInputElement ? reasonInput.value : "";
        if (caseId) startImpersonation(caseId, reason);
        return;
      }

      const impersonationStop = target.closest("[data-admin-impersonation-stop]");
      if (impersonationStop) {
        stopImpersonation();
      }
    });

    const createForm = document.querySelector("[data-admin-create-form]");
    if (createForm instanceof HTMLFormElement) {
      createForm.addEventListener("submit", runSuperAdminCreateAccount);
      createForm.addEventListener("input", function (event) {
        const target = event.target;
        if (target instanceof Element && target.matches('[data-admin-create-field="package_code"], [data-admin-create-field="full_name"]')) {
          syncCreatePackageFields();
        }
        if (target instanceof Element && !target.matches('[data-admin-create-field="reason"], [data-admin-create-confirm]')) {
          resetCreatePreview("Account details changed. Preview the current values before execution.");
        }
        syncCreateExecuteAvailability();
      });
      createForm.addEventListener("change", function (event) {
        const target = event.target;
        if (target instanceof Element && target.matches('[data-admin-create-field="package_code"]')) {
          syncCreatePackageFields();
          resetCreatePreview("Package selection changed. Preview the current values before execution.");
        }
        syncCreateExecuteAvailability();
      });
    }

    const lifecycleForm = document.querySelector("[data-admin-lifecycle-form]");
    if (lifecycleForm instanceof HTMLFormElement) {
      lifecycleForm.addEventListener("submit", runSuperAdminUserStateAction);
      lifecycleForm.addEventListener("input", syncLifecycleExecuteAvailability);
      lifecycleForm.addEventListener("change", syncLifecycleExecuteAvailability);
    }

    const teamForm = document.querySelector("[data-admin-team-form]");
    if (teamForm instanceof HTMLFormElement) {
      teamForm.addEventListener("submit", applyTeamAccess);
      teamForm.addEventListener("input", function (event) {
        const target = event.target;
        if (target instanceof Element && target.matches('[data-admin-team-field="officer_email"], [data-admin-team-field="role_template"]')) {
          resetTeamAccessPreview("Officer or job template changed. Preview the current assignment before applying it.");
          renderTeamScope();
        }
        syncTeamAccessExecuteAvailability();
      });
      teamForm.addEventListener("change", function (event) {
        const target = event.target;
        if (target instanceof Element && target.matches('[data-admin-team-field="officer_email"], [data-admin-team-field="role_template"]')) {
          resetTeamAccessPreview("Officer or job template changed. Preview the current assignment before applying it.");
          renderTeamScope();
        }
        syncTeamAccessExecuteAvailability();
      });
    }

    document.querySelectorAll(".admin-workflow-dialog").forEach(function (dialog) {
      dialog.addEventListener("cancel", function () {
        if (dialog.matches("[data-admin-lifecycle-dialog]")) state.lifecycleWorkflow = null;
      });
    });

    const searchInput = document.querySelector("[data-admin-case-search]");
    if (searchInput) {
      let searchTimer = 0;
      searchInput.addEventListener("input", function () {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(function () {
          state.selectedCaseId = "";
          state.workspace = null;
          loadCases();
        }, 280);
      });
      searchInput.addEventListener("change", loadCases);
      searchInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          window.clearTimeout(searchTimer);
          state.selectedCaseId = "";
          state.workspace = null;
          loadCases();
        }
      });
    }

    const refreshButton = document.querySelector("[data-admin-refresh-cases]");
    if (refreshButton) {
      refreshButton.addEventListener("click", async function () {
        setPageStatus("Refreshing customer case console...", "info");
        await Promise.allSettled([loadKernelStatus(), loadOverview(), loadCases()]);
        setPageStatus("Customer case console refreshed.", "success");
      });
    }
  }

  function updateRoleSummary() {
    const titleNode = document.querySelector("[data-admin-control-title]");
    const statusNode = document.querySelector("[data-admin-control-status]");
    if (titleNode) {
      titleNode.textContent = state.roleKey === "ceo_master_admin"
        ? "CEO Master Administrator"
        : isMarketingRole()
          ? "Marketing Command Center"
          : "Customer Operations Workspace";
    }
    if (statusNode) {
      const queueCount = Array.isArray(state.allowedQueues) ? state.allowedQueues.length : 0;
      const isWildcardScope = Boolean(
        state.isSuperAdmin || (state.accessProfile && state.accessProfile.is_wildcard),
      );
      if (state.accessProfileLoadFailed) {
        statusNode.textContent = "Access scope unavailable (ACC-ACCESS-PROFILE). Use Refresh to retry.";
        return;
      }
      const scopeLabel = isWildcardScope
        ? "All permitted operational queues"
        : `${queueCount} permitted ${isMarketingRole() ? "section" : "queue"}${queueCount === 1 ? "" : "s"}`;
      statusNode.textContent = isMarketingRole()
        ? `Marketing command center is active for ${roleDisplayLabel(state.roleKey)} across ${scopeLabel}.`
        : `Search-first case operations are active for ${roleDisplayLabel(state.roleKey)} across ${scopeLabel}.`;
    }
  }

  function configureMarketingLayout() {
    if (!isMarketingRole()) return;
    const searchPanel = document.querySelector(".admin-command-search");
    if (searchPanel) searchPanel.hidden = true;
    const workspacePanel = document.querySelector(".admin-case-workspace-panel");
    if (workspacePanel) workspacePanel.hidden = true;
    const contextPanel = document.querySelector(".admin-case-context-panel");
    if (contextPanel) contextPanel.hidden = true;
    const railHeading = document.querySelector(".admin-case-rail h3");
    if (railHeading) railHeading.textContent = "Marketing Rail";
  }

  async function bootstrapAccessAndData() {
    try {
      await loadAccessProfile();
      if (state.isSuperAdmin) {
        await loadPackageOptions();
      }
      await loadKernelStatus();
      await loadActiveImpersonation();
      startImpersonationTicker();
      clearBootstrapError();
    } catch (error) {
      console.error("Admin bootstrap failed:", error);
      const code = classifyAdminError(error, ADMIN_ERROR_CODES.accessProfile);
      showBootstrapError(code, error && error.message, bootstrapAccessAndData);
      setPageStatus(`${code}: ${error && error.message ? error.message : "Unable to load access profile."}`, "error");
    }

    configureMarketingLayout();
    updateRoleSummary();
    applyRailSelection();
    applyTabSelection();
    renderCaseHeader();
    updateActionAvailability();
    updateBulkActionAvailability();
    await Promise.allSettled([loadOverview(), loadCases()]);
    if (state.isSuperAdmin) {
      await loadDiagnostics();
    }
  }

  async function setupPage() {
    state.currentUser = await app.requireSession("signin.html");
    if (!state.currentUser) return;

    state.roleKey = getInternalRoleKey(state.currentUser);
    if (!state.roleKey) {
      window.location.href = "dashboard.html";
      return;
    }

    // Bind event handlers immediately so button clicks are never silently
    // ignored regardless of whether the async profile/data loads succeed.
    bindEvents();

    await bootstrapAccessAndData();
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupPage().catch(function (error) {
      console.error("Failed to initialize admin control center:", error);
      setPageStatus(error.message || "Unable to initialize admin console.", "error");
    });
  });
})();
