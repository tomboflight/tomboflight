(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

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

  const state = {
    currentUser: null,
    roleKey: "",
    queue: "overview",
    selectedCaseId: "",
    selectedTab: "identity",
    cases: [],
    workspace: null,
  };

  function normalizeValue(value) {
    return String(value || "").trim();
  }

  function normalizeLower(value) {
    return normalizeValue(value).toLowerCase();
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
    const values = [
      normalizeLower(me && me.role),
      normalizeLower(me && me.access_tier),
      normalizeLower(me && me.department_role),
    ].filter(Boolean);
    const direct = values.find(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });
    if (direct) return direct;
    if (typeof app.isInternalRole === "function" && app.isInternalRole(me)) return "admin";
    return "";
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

  async function fetchJson(path) {
    return app.apiRequest(path, { method: "GET" });
  }

  async function postJson(path, body) {
    return app.apiRequest(path, {
      method: "POST",
      body: JSON.stringify(body || {}),
    });
  }

  function renderTopSummary(summary) {
    const node = document.querySelector("[data-admin-top-summary]");
    if (!node) return;
    const cards = [
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
          <div class="family-record-card admin-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(item[0])}</h3>
            <p class="card-copy">${escapeHtml(String(item[1] ?? 0))}</p>
          </div>
        `;
      })
      .join("");
  }

  function renderPriorityRepairs(priority) {
    const node = document.querySelector("[data-admin-priority-repairs]");
    if (!node) return;
    const cards = [
      ["Paid order without project link", (priority.paid_order_without_project_link || []).length],
      ["Project without entitlement", (priority.project_without_entitlement || []).length],
      ["Package without lane", (priority.package_without_lane || []).length],
      ["Mint-eligible blocked", (priority.mint_eligible_blocked || []).length],
    ];
    node.innerHTML = cards
      .map(function (item) {
        return `
          <div class="family-record-card admin-card">
            <div class="card-number">!</div>
            <h3>${escapeHtml(item[0])}</h3>
            <p class="card-copy">${escapeHtml(String(item[1]))}</p>
          </div>
        `;
      })
      .join("");
  }

  async function loadOverview() {
    try {
      const payload = await fetchJson("/admin/control-center/overview?limit=24");
      renderTopSummary(payload.summary || {});
      renderPriorityRepairs(payload.priority_repairs || {});
    } catch (error) {
      console.error("Overview load failed:", error);
      renderTopSummary({});
      renderPriorityRepairs({});
    }
  }

  function renderCaseList() {
    const node = document.querySelector("[data-admin-case-list]");
    if (!node) return;
    const cases = Array.isArray(state.cases) ? state.cases : [];
    if (!cases.length) {
      node.innerHTML = `
        <div class="family-record-card admin-card">
          <div class="card-number">•</div>
          <h3>No case results</h3>
          <p class="card-copy">No customer cases matched this queue/search.</p>
        </div>
      `;
      return;
    }

    node.innerHTML = cases
      .map(function (item) {
        const alerts = Array.isArray(item.alerts) ? item.alerts : [];
        const isSelected = state.selectedCaseId === item.case_id;
        return `
          <article class="family-record-card admin-card admin-case-row ${isSelected ? "is-selected" : ""}" data-case-row="${escapeHtml(item.case_id || "")}">
            <div class="admin-card-header">
              <span class="admin-card-badge">C</span>
              <h3 class="admin-card-title">${escapeHtml(item.name || "Customer Case")}</h3>
            </div>
            <div class="admin-card-meta">
              <p class="card-copy"><strong>Email:</strong> ${escapeHtml(item.email || "—")}</p>
              <p class="card-copy"><strong>Role:</strong> ${escapeHtml(item.role || "customer")}</p>
              <p class="card-copy"><strong>Project:</strong> ${escapeHtml(item.project || "—")}</p>
              <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package || "—")}</p>
              <p class="card-copy"><strong>Lane:</strong> ${laneChip(item.lane)}</p>
              <p class="card-copy"><strong>Status:</strong> ${statusChip(item.status || "unknown", item.status === "paid" || item.status === "delivered" ? "success" : "default")}</p>
              <p class="card-copy"><strong>Alerts:</strong> ${alerts.length ? alerts.map(function (alert) { return statusChip(alert.replaceAll("_", " "), "error"); }).join(" ") : statusChip("none", "success")}</p>
              <p class="card-copy"><strong>Updated:</strong> ${escapeHtml(formatDate(item.updated_at))}</p>
            </div>
            <div class="inline-actions" style="margin-top: 0.8rem; flex-wrap: wrap">
              <label class="card-copy" style="display:inline-flex;align-items:center;gap:0.4rem;margin:0;">
                <input type="checkbox" data-case-select="${escapeHtml(item.case_id || "")}" />
                Select for bulk repair
              </label>
              <button class="btn btn-secondary" type="button" data-open-case="${escapeHtml(item.case_id || "")}">Open Case</button>
            </div>
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
        <div class="family-record-card admin-card">
          <div class="card-number">⚙</div>
          <h3>No case selected</h3>
          <p class="card-copy">Select a customer case to open the workspace.</p>
        </div>
      `;
      return;
    }

    const tab = state.selectedTab;
    const tabData = workspace.tabs[tab];

    if (tab === "audit_timeline") {
      const timeline = Array.isArray(tabData) ? tabData : Array.isArray(workspace.audit_timeline) ? workspace.audit_timeline : [];
      node.innerHTML = timeline.length
        ? timeline
            .map(function (item) {
              return `
                <article class="family-record-card admin-card">
                  <div class="admin-card-header">
                    <span class="admin-card-badge">A</span>
                    <h3 class="admin-card-title">${escapeHtml(item.action || "Audit Event")}</h3>
                  </div>
                  <div class="admin-card-meta">
                    <p class="card-copy"><strong>Target:</strong> ${escapeHtml(item.target_type || "—")} / <span class="admin-id-ref">${escapeHtml(shortId(item.target_id))}</span></p>
                    <p class="card-copy"><strong>Actor:</strong> ${escapeHtml(item.actor_email || item.actor_name || "—")}</p>
                    <p class="card-copy"><strong>Result:</strong> ${statusChip(item.result || "success", item.result === "success" ? "success" : "error")}</p>
                    <p class="card-copy"><strong>When:</strong> ${escapeHtml(formatDate(item.timestamp))}</p>
                  </div>
                </article>
              `;
            })
            .join("")
        : `<div class="family-record-card admin-card"><h3>No audit timeline</h3><p class="card-copy">No audit events were found for this case context.</p></div>`;
      return;
    }

    if (tab === "orders_billing") {
      const primaryOrder = tabData && tabData.primary_order ? tabData.primary_order : {};
      const related = Array.isArray(tabData && tabData.related_orders) ? tabData.related_orders : [];
      node.innerHTML = `
        <article class="family-record-card admin-card">
          <div class="admin-card-header"><span class="admin-card-badge">O</span><h3 class="admin-card-title">Primary Order</h3></div>
          <div class="admin-card-meta">${renderObjectRows(primaryOrder)}</div>
        </article>
        <article class="family-record-card admin-card">
          <div class="admin-card-header"><span class="admin-card-badge">R</span><h3 class="admin-card-title">Related Orders (${related.length})</h3></div>
          <div class="admin-card-meta">
            ${related.length ? related.map(function (order) { return `<p class="card-copy"><strong>${escapeHtml(shortId(order.id))}</strong> · ${escapeHtml(order.status || "unknown")} · ${escapeHtml(order.package_name || order.package_code || "—")} · ${escapeHtml(formatDate(order.created_at))}</p>`; }).join("") : '<p class="card-copy">No related orders.</p>'}
          </div>
        </article>
      `;
      return;
    }

    if (tab === "uploads_verification") {
      const uploads = tabData && Array.isArray(tabData.items) ? tabData.items : [];
      node.innerHTML = `
        <article class="family-record-card admin-card">
          <div class="admin-card-header"><span class="admin-card-badge">U</span><h3 class="admin-card-title">Upload & Verification Records (${uploads.length})</h3></div>
          <div class="admin-card-meta">
            ${uploads.length ? uploads.map(function (upload) { return `<p class="card-copy"><strong>${escapeHtml(upload.filename || shortId(upload.id))}</strong> · ${escapeHtml(upload.category || "upload")} · ${escapeHtml(formatDate(upload.created_at))}</p>`; }).join("") : '<p class="card-copy">No uploads found for this case.</p>'}
          </div>
        </article>
      `;
      return;
    }

    node.innerHTML = `
      <article class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">${escapeHtml(tab.charAt(0).toUpperCase())}</span>
          <h3 class="admin-card-title">${escapeHtml(tab.replaceAll("_", " "))}</h3>
        </div>
        <div class="admin-card-meta">${renderObjectRows(tabData || {})}</div>
      </article>
    `;
  }

  function renderCaseContext() {
    const node = document.querySelector("[data-admin-case-context]");
    if (!node) return;
    const selected = (state.cases || []).find(function (item) {
      return item.case_id === state.selectedCaseId;
    });

    if (!selected) {
      node.innerHTML = `
        <div class="family-record-card admin-card">
          <h3>Context panel</h3>
          <p class="card-copy">Select a case to see alerts, blocking reasons, and contextual status.</p>
        </div>
      `;
      return;
    }

    const blocking = Array.isArray(selected.mint_blocking_reasons) ? selected.mint_blocking_reasons : [];
    node.innerHTML = `
      <div class="family-record-card admin-card">
        <h3>${escapeHtml(selected.name || "Selected Case")}</h3>
        <p class="card-copy"><strong>Case:</strong> <span class="admin-id-ref">${escapeHtml(shortId(selected.case_id))}</span></p>
        <p class="card-copy"><strong>Alerts:</strong> ${selected.alerts && selected.alerts.length ? selected.alerts.map(function (alert) { return statusChip(alert.replaceAll("_", " "), "error"); }).join(" ") : statusChip("none", "success")}</p>
        <p class="card-copy"><strong>Mint Blocking Reasons:</strong> ${blocking.length ? escapeHtml(blocking.join(", ")) : "none"}</p>
      </div>
    `;
  }

  function applyRailSelection() {
    document.querySelectorAll("[data-case-queue]").forEach(function (button) {
      const queue = button.getAttribute("data-case-queue") || "";
      button.classList.toggle("is-active", queue === state.queue);
    });
  }

  function applyTabSelection() {
    document.querySelectorAll("[data-admin-case-tab]").forEach(function (button) {
      const tab = button.getAttribute("data-admin-case-tab") || "";
      button.classList.toggle("is-active", tab === state.selectedTab);
    });
  }

  async function loadCaseWorkspace(caseId) {
    if (!caseId) return;
    state.selectedCaseId = caseId;
    applyTabSelection();
    renderWorkspaceTab();
    try {
      const payload = await fetchJson(`/admin/control-center/cases/${encodeURIComponent(caseId)}`);
      state.workspace = payload || null;
      renderWorkspaceTab();
      renderCaseContext();
    } catch (error) {
      setPageStatus(error.message || "Unable to load case workspace.", "error");
    }
  }

  async function loadCases() {
    setPageStatus("Loading customer cases...", "info");
    try {
      const payload = await fetchJson(
        `/admin/control-center/cases?queue=${encodeURIComponent(state.queue)}&limit=80&search=${encodeURIComponent(getSearchValue())}`,
      );
      state.cases = Array.isArray(payload.items) ? payload.items : [];
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
    if (!state.selectedCaseId) {
      setPageStatus("Select a case first.", "error");
      return;
    }
    setPageStatus("Running case action...", "info");
    try {
      await postJson(
        `/admin/control-center/cases/${encodeURIComponent(state.selectedCaseId)}/actions/${encodeURIComponent(action)}`,
        {},
      );
      await Promise.allSettled([loadOverview(), loadCases(), loadCaseWorkspace(state.selectedCaseId)]);
      setPageStatus("Case action completed.", "success");
    } catch (error) {
      setPageStatus(error.message || "Case action failed.", "error");
    }
  }

  function bindEvents() {
    document.addEventListener("click", function (event) {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const queueButton = target.closest("[data-case-queue]");
      if (queueButton) {
        state.queue = queueButton.getAttribute("data-case-queue") || "overview";
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
      if (caseRow && !target.closest("[data-case-select]")) {
        const caseId = caseRow.getAttribute("data-case-row");
        if (caseId) loadCaseWorkspace(caseId);
        return;
      }

      const caseActionButton = target.closest("[data-admin-case-action]");
      if (caseActionButton) {
        const action = caseActionButton.getAttribute("data-admin-case-action");
        if (action) runCaseAction(action);
        return;
      }

      const bulkActionButton = target.closest("[data-admin-bulk-action]");
      if (bulkActionButton) {
        const action = bulkActionButton.getAttribute("data-admin-bulk-action");
        if (action) runBulkAction(action);
        return;
      }

      const tabButton = target.closest("[data-admin-case-tab]");
      if (tabButton) {
        state.selectedTab = tabButton.getAttribute("data-admin-case-tab") || "identity";
        applyTabSelection();
        renderWorkspaceTab();
      }
    });

    const searchInput = document.querySelector("[data-admin-case-search]");
    if (searchInput) {
      searchInput.addEventListener("change", loadCases);
      searchInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
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
      titleNode.textContent = "Customer Case Command Console";
    }
    if (statusNode) {
      statusNode.textContent = `Internal premium operations controls are active for role: ${state.roleKey || "admin"}.`;
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

    updateRoleSummary();
    bindEvents();
    applyRailSelection();
    applyTabSelection();
    await Promise.allSettled([loadOverview(), loadCases()]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupPage().catch(function (error) {
      console.error("Failed to initialize admin control center:", error);
      setPageStatus(error.message || "Unable to initialize admin console.", "error");
    });
  });
})();
