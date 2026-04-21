(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  const INTERNAL_ROLE_KEYS = new Set([
    "super_admin",
    "executive_tech_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
  ]);

  const ROLE_ALIASES = {
    superadmin: "super_admin",
    root_admin: "super_admin",
    platform_admin: "super_admin",
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
    selectedTab: "identity",
    cases: [],
    workspace: null,
    packageOptions: [],
  };
  const DEFAULT_ROLE_KEY = "user";

  const QUEUE_META = {
    overview: ["Overview", "Executive repair posture across active customer operations."],
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
    identity: "Identity",
    package_lane: "Package & Lane",
    orders_billing: "Orders & Billing",
    project: "Project",
    entitlements: "Entitlements",
    uploads_verification: "Uploads / Verification",
    mint_readiness: "Mint Readiness",
    audit_timeline: "Audit Timeline",
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

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch (_error) {
      return String(value);
    }
  }

  function setPageStatus(message, type) {
    app.setStatus(document.querySelector("[data-admin-control-action-status]"), message, type);
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
    return state.allowedTabs.includes(normalized);
  }

  function isAllowedCaseAction(action) {
    const normalized = normalizeLower(action);
    return state.allowedActions.includes(normalized);
  }

  function isAllowedBulkAction(action) {
    const normalized = normalizeLower(action);
    return state.allowedBulkActions.includes(normalized);
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

    if (!isAllowedQueue(state.queue)) {
      state.queue = state.allowedQueues[0] || "overview";
    }
    if (!isAllowedTab(state.selectedTab)) {
      state.selectedTab = state.allowedTabs[0] || "identity";
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

  function renderTopSummary(summary, financeSections) {
    const node = document.querySelector("[data-admin-top-summary]");
    if (!node) return;
    const isFinanceRole = state.roleKey === "finance_admin";
    const moneyNow = (financeSections && financeSections.money_now) || {};
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

  function renderPriorityRepairs(priority, financeSections) {
    const node = document.querySelector("[data-admin-priority-repairs]");
    if (!node) return;
    const isFinanceRole = state.roleKey === "finance_admin";
    const financeIntegrity = (financeSections && financeSections.finance_integrity) || {};
    const payroll = (financeSections && financeSections.payroll) || {};
    const cards = isFinanceRole
      ? [
          ["Unlinked Payments", financeIntegrity.unlinked_payments || 0],
          ["Order/Project Mismatch", financeIntegrity.order_project_mismatch || 0],
          ["Entitlement Mismatch", financeIntegrity.entitlement_mismatch || 0],
          ["Refunded but Access Active", financeIntegrity.refunded_but_still_active_access || 0],
          ["Manual Override Log", financeIntegrity.manual_override_log || 0],
          ["Pending Payroll Review", payroll.pending_payroll_review || 0],
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
      renderTopSummary(payload.summary || {}, payload.finance_sections || {});
      renderPriorityRepairs(payload.priority_repairs || {}, payload.finance_sections || {});
    } catch (error) {
      console.error("Overview load failed:", error);
      renderTopSummary({}, {});
      renderPriorityRepairs({}, {});
    }
  }

  function renderCaseList() {
    const node = document.querySelector("[data-admin-case-list]");
    if (!node) return;
    const cases = Array.isArray(state.cases) ? state.cases : [];
    const canRepairSelected = isAllowedBulkAction("repair-selected-records");
    if (!cases.length) {
      node.innerHTML = `
        <div class="admin-empty-state">
          <div class="card-number">C</div>
          <h3>No case results</h3>
          <p class="card-copy">No customer cases matched this queue/search.</p>
        </div>
      `;
      return;
    }

    node.innerHTML = cases
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
      .join("");
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
    const tabData = workspace.tabs[tab];
    const warningMarkup = renderWarningStrip((tabData && tabData.warnings) || workspace.warnings || []);

    if (tab === "audit_timeline") {
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

    if (tab === "orders_billing") {
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
      `;
      return;
    }

    if (tab === "uploads_verification") {
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

    if (tab === "identity") {
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
                <div class="admin-card-header"><span class="admin-card-badge">S</span><h3 class="admin-card-title">Super Admin Controls</h3></div>
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
                <div class="inline-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                  <button class="btn btn-primary" type="button" data-super-admin-user-save="${escapeHtml(userId)}">Save User Updates</button>
                  <button class="btn btn-secondary" type="button" data-super-admin-user-action="activate" data-super-admin-user-id="${escapeHtml(userId)}">Activate</button>
                  <button class="btn btn-secondary" type="button" data-super-admin-user-action="suspend" data-super-admin-user-id="${escapeHtml(userId)}">Suspend</button>
                  <button class="btn btn-secondary" type="button" data-super-admin-user-action="disable" data-super-admin-user-id="${escapeHtml(userId)}">Disable</button>
                  <button class="btn btn-secondary" type="button" data-super-admin-user-action="restore" data-super-admin-user-id="${escapeHtml(userId)}">Restore</button>
                  <button class="btn btn-secondary" type="button" data-super-admin-user-password-reset="${escapeHtml(userId)}">Trigger Password Reset</button>
                </div>
              </article>
            `
            : ""
        }
      `;
      return;
    }

    if (tab === "mint_readiness") {
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

    if (tab === "package_lane") {
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
              <div class="admin-card-header"><span class="admin-card-badge">S</span><h3 class="admin-card-title">Super Admin Package Change</h3></div>
              <div class="admin-field-grid">
                <label class="admin-field">
                  <span>Target Package</span>
                  <select data-super-admin-package-field="package_code">
                    ${packageOptions || packageFallbackOption}
                  </select>
                </label>
                <label class="admin-field"><span>Target Lane</span><input type="text" data-super-admin-package-field="project_lane" value="${escapeHtml(tabData.project_lane || tabData.lane || "")}" /></label>
                <label class="admin-field"><span>Order Status</span><input type="text" data-super-admin-package-field="order_status" value="${escapeHtml((workspace.tabs.orders_billing || {}).order_status || "")}" /></label>
              </div>
              <div class="inline-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="btn btn-secondary" type="button" data-super-admin-package-preview="${escapeHtml(projectId)}">Preview Change</button>
                <button class="btn btn-primary" type="button" data-super-admin-package-apply="${escapeHtml(projectId)}">Apply Package Change</button>
              </div>
              <div data-super-admin-package-preview-output class="helper" style="margin-top: 0.75rem;"></div>
            </article>
            `
            : ""
        }
      `;
      return;
    }

    if (tab === "project") {
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
                <div class="admin-card-header"><span class="admin-card-badge">S</span><h3 class="admin-card-title">Super Admin Repair Toolkit</h3></div>
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
                </div>
                <label class="admin-field" style="margin-top: 0.6rem; display: inline-flex; align-items: center; gap: 0.45rem;">
                  <input type="checkbox" data-super-admin-repair-field="confirm_destructive" />
                  <span>I confirm destructive edits if required</span>
                </label>
                <div class="inline-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                  <button class="btn btn-primary" type="button" data-super-admin-repair-run="${escapeHtml(caseId)}">Apply Repair Tool</button>
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
    node.innerHTML = `
      <div class="admin-context-card">
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
      </div>
    `;
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
    if (title) title.textContent = meta[0];
    if (subtitle) subtitle.textContent = meta[1];
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
      const available = Boolean(selected && allowedByRole && allowedByCase && hasRequirements);
      button.hidden = !allowedByRole;
      button.disabled = !available;
      button.classList.toggle("is-disabled", !available);
      button.setAttribute("data-action-tier", tier);
      button.classList.toggle("admin-action-tier--primary", tier === "primary");
      button.classList.toggle("admin-action-tier--secondary", tier === "secondary");
      button.classList.toggle("admin-action-tier--utility", tier === "utility");
      button.setAttribute("aria-disabled", available ? "false" : "true");
    });
  }

  function updateBulkActionAvailability() {
    document.querySelectorAll("[data-admin-bulk-action]").forEach(function (button) {
      const action = button.getAttribute("data-admin-bulk-action") || "";
      const allowed = isAllowedBulkAction(action);
      button.hidden = !allowed;
      button.disabled = !allowed;
      button.classList.toggle("is-disabled", !allowed);
      button.setAttribute("aria-disabled", allowed ? "false" : "true");
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
      renderWorkspaceTab();
      renderCaseHeader();
      renderCaseContext();
      updateActionAvailability();
      updateBulkActionAvailability();
    } catch (error) {
      setPageStatus(error.message || "Unable to load case workspace.", "error");
    }
  }

  async function loadCases() {
    const meta = QUEUE_META[state.queue] || QUEUE_META.customer_cases;
    setPageStatus(`Loading ${meta[0].toLowerCase()}...`, "info");
    try {
      const payload = await fetchJson(
        `/admin/control-center/cases?queue=${encodeURIComponent(state.queue)}&limit=80&search=${encodeURIComponent(getSearchValue())}`,
      );
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
      setPageStatus(error.message || "Unable to load customer cases.", "error");
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
    const endpointMap = {
      "repair-missing-entitlements": "/admin/control-center/bulk/repair-missing-entitlements",
      "assign-missing-lanes": "/admin/control-center/bulk/assign-missing-lanes",
      "link-unlinked-paid-orders": "/admin/control-center/bulk/link-unlinked-paid-orders",
      "normalize-broken-package-records": "/admin/control-center/bulk/normalize-broken-package-records",
      "refresh-mint-readiness": "/admin/control-center/bulk/refresh-mint-readiness",
      "repair-selected-records": "/admin/control-center/bulk/repair-selected-records",
      "repair-all-safe-records": "/admin/control-center/bulk/repair-all-safe-records",
    };
    const endpoint = endpointMap[action];
    if (!endpoint) return;

    const body = action === "repair-selected-records" ? selectedRepairIds() : { limit: 500 };
    if (
      action === "repair-selected-records" &&
      (!body.project_ids.length && !body.order_ids.length)
    ) {
      setPageStatus("Select one or more cases before running Repair Selected Records.", "error");
      return;
    }

    setPageStatus("Running bulk action...", "info");
    try {
      await postJson(endpoint, body);
      await Promise.allSettled([loadOverview(), loadCases()]);
      setPageStatus("Bulk action completed.", "success");
    } catch (error) {
      setPageStatus(error.message || "Bulk action failed.", "error");
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
    setPageStatus("Running case action...", "info");
    try {
      await postJson(
        `/admin/control-center/cases/${encodeURIComponent(caseId)}/actions/${encodeURIComponent(action)}`,
        {},
      );
      await loadOverview();
      await loadCases();
      if (state.selectedCaseId === caseId) {
        await loadCaseWorkspace(caseId);
      }
      setPageStatus("Case action completed.", "success");
    } catch (error) {
      setPageStatus(error.message || "Case action failed.", "error");
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

  async function runSuperAdminUserUpdate(userId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    if (!window.confirm("Apply user profile and account updates?")) return;
    setPageStatus("Saving user updates...", "info");
    try {
      await app.apiRequest(`/admin/control-center/super-admin/users/${encodeURIComponent(userId)}`, {
        method: "PATCH",
        body: JSON.stringify(collectSuperAdminUserPayload()),
      });
      await loadCases();
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus("User updates saved.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to update user.", "error");
    }
  }

  async function runSuperAdminUserStateAction(userId, action) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    if (!window.confirm(`Confirm ${action} for this account?`)) return;
    setPageStatus("Updating account status...", "info");
    try {
      await postJson(
        `/admin/control-center/super-admin/users/${encodeURIComponent(userId)}/status-action`,
        { action },
      );
      await loadCases();
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus("Account status updated.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to update account status.", "error");
    }
  }

  async function runSuperAdminPasswordReset(userId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    if (!window.confirm("Trigger password reset for this account?")) return;
    setPageStatus("Issuing password reset...", "info");
    try {
      await postJson(
        `/admin/control-center/super-admin/users/${encodeURIComponent(userId)}/password-reset`,
        {},
      );
      setPageStatus("Password reset issued.", "success");
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

  async function runSuperAdminPackageApply(projectId) {
    if (!state.isSuperAdmin) {
      setPageStatus("Super Admin access is required.", "error");
      return;
    }
    if (!window.confirm("Apply package change and repair consistency across project/order/entitlements?")) return;
    setPageStatus("Applying package change...", "info");
    try {
      const payload = await postJson(
        `/admin/control-center/super-admin/projects/${encodeURIComponent(projectId)}/package-change/apply`,
        collectSuperAdminPackagePayload(),
      );
      renderSuperAdminPackagePreview(payload || {});
      await loadOverview();
      await loadCases();
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus("Package change applied and synchronized.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to apply package change.", "error");
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
      await postJson(
        `/admin/control-center/super-admin/cases/${encodeURIComponent(caseId)}/repair`,
        payload,
      );
      await loadOverview();
      await loadCases();
      if (state.selectedCaseId) await loadCaseWorkspace(state.selectedCaseId);
      setPageStatus("Super admin repair completed and logged.", "success");
    } catch (error) {
      setPageStatus(error.message || "Unable to complete super admin repair.", "error");
    }
  }

  function bindEvents() {
    document.addEventListener("click", function (event) {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const queueButton = target.closest("[data-case-queue]");
      if (queueButton) {
        const queue = queueButton.getAttribute("data-case-queue") || "overview";
        if (!isAllowedQueue(queue)) return;
        state.queue = queue;
        applyRailSelection();
        loadCases();
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
        if (action && userId) runSuperAdminUserStateAction(userId, action);
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

      const superAdminRepair = target.closest("[data-super-admin-repair-run]");
      if (superAdminRepair) {
        const caseId = superAdminRepair.getAttribute("data-super-admin-repair-run");
        if (caseId) runSuperAdminCaseRepair(caseId);
        return;
      }

      const tabButton = target.closest("[data-admin-case-tab]");
      if (tabButton) {
        const tab = tabButton.getAttribute("data-admin-case-tab") || "identity";
        if (!isAllowedTab(tab)) return;
        state.selectedTab = tab;
        applyTabSelection();
        renderWorkspaceTab();
      }
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
        await Promise.allSettled([loadOverview(), loadCases()]);
        setPageStatus("Customer case console refreshed.", "success");
      });
    }
  }

  function updateRoleSummary() {
    const titleNode = document.querySelector("[data-admin-control-title]");
    const statusNode = document.querySelector("[data-admin-control-status]");
    if (titleNode) {
      titleNode.textContent = "Customer Operations Workspace";
    }
    if (statusNode) {
      const queueCount = Array.isArray(state.allowedQueues) ? state.allowedQueues.length : 0;
      statusNode.textContent = `Search-first case operations are active for role: ${state.roleKey || DEFAULT_ROLE_KEY} across ${queueCount} permitted queue${queueCount === 1 ? "" : "s"}.`;
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

    try {
      await loadAccessProfile();
      if (state.isSuperAdmin) {
        await loadPackageOptions();
      }
    } catch (error) {
      setPageStatus(error.message || "Unable to load access profile.", "error");
    }

    updateRoleSummary();
    applyRailSelection();
    applyTabSelection();
    renderCaseHeader();
    updateActionAvailability();
    updateBulkActionAvailability();
    await Promise.allSettled([loadOverview(), loadCases()]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupPage().catch(function (error) {
      console.error("Failed to initialize admin control center:", error);
      setPageStatus(error.message || "Unable to initialize admin console.", "error");
    });
  });
})();
