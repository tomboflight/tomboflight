(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  // Role-key set used to determine which internal role a user holds.
  // app.js exports a canonical isInternalRole() helper for boolean checks;
  // admin-control-center.js also needs the specific role key to drive
  // SECTION_ACCESS and role-title logic, so the set is retained here.
  // Keep this list in sync with INTERNAL_ROLE_KEYS in app.js.
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

  const FULL_CONTROL_KEYS = new Set([
    "root_admin",
    "super_admin",
    "admin",
    "platform_admin",
    "executive_technology",
  ]);

  const SECTION_ACCESS = {
    uploads: new Set([
      "operations_admin",
      "operations",
      "finance_admin",
      "finance",
    ]),
    mints: new Set([
      "operations_admin",
      "operations",
      "finance_admin",
      "finance",
    ]),
    orders: new Set(["finance_admin", "finance"]),
    entitlements: new Set(["finance_admin", "finance"]),
    projects: new Set([
      "operations_admin",
      "operations",
      "marketing_admin",
      "marketing",
    ]),
    users: new Set(["marketing_admin", "marketing"]),
    audit: new Set(["operations_admin", "operations", "finance_admin", "finance", "marketing_admin", "marketing"]),
  };

  const SECTION_LOADERS = {
    uploads: loadUploads,
    mints: loadMints,
    orders: loadOrders,
    entitlements: loadEntitlements,
    projects: loadProjects,
    users: loadUsers,
    audit: loadAuditLogs,
  };

  let currentUser = null;
  let currentRoleKey = "";
  const sectionSnapshots = {};
  let selectedProjectId = "";

  function normalizeValue(value) {
    return String(value || "").trim().toLowerCase();
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

  function getRoleSignals(me) {
    return [
      normalizeValue(me && me.role),
      normalizeValue(me && me.access_tier),
      normalizeValue(me && me.department_role),
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

  function getRoleTitle(roleKey) {
    if (roleKey === "root_admin") return "Company Root Control";
    if (roleKey === "super_admin") return "Executive Control";
    if (roleKey === "admin") return "Administrative Control";
    if (roleKey === "platform_admin" || roleKey === "executive_technology") {
      return "Platform Control";
    }
    if (roleKey === "operations_admin" || roleKey === "operations") {
      return "Operations Control";
    }
    if (roleKey === "finance_admin" || roleKey === "finance") {
      return "Finance Control";
    }
    if (roleKey === "marketing_admin" || roleKey === "marketing") {
      return "Marketing Control";
    }
    return "Internal Control";
  }

  function canAccessSection(sectionKey) {
    if (FULL_CONTROL_KEYS.has(currentRoleKey)) return true;
    const allowed = SECTION_ACCESS[sectionKey];
    return Boolean(allowed && allowed.has(currentRoleKey));
  }

  SECTION_ACCESS.users = new Set([
    "operations_admin",
    "operations",
    "finance_admin",
    "finance",
    "marketing_admin",
    "marketing",
  ]);

  function getSearchValue() {
    const node = document.querySelector("[data-admin-control-search]");
    return String((node && node.value) || "").trim();
  }

  function setPageStatus(message, type) {
    app.setStatus(
      document.querySelector("[data-admin-control-action-status]"),
      message,
      type,
    );
  }

  function setSectionStatus(sectionKey, message, type) {
    const node = document.querySelector(`[data-section-status="${sectionKey}"]`);
    app.setStatus(node, message, type);
  }

  function clearSectionStatus(sectionKey) {
    const node = document.querySelector(`[data-section-status="${sectionKey}"]`);
    app.clearStatus(node);
  }

  function sectionListNode(sectionKey) {
    return document.querySelector(`[data-section-list="${sectionKey}"]`);
  }

  function formatSectionTitle(sectionKey) {
    const normalized = String(sectionKey || "").trim();
    if (!normalized) return "Section";
    return normalized
      .split(/[_-]+/)
      .filter(Boolean)
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function emptyCard(title, copy) {
    return `
      <div class="family-record-card">
        <div class="card-number">•</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${escapeHtml(copy)}</p>
      </div>
    `;
  }

  function safeErrorMessage(error, fallback) {
    const local = typeof app.isLocalApp === "function" && app.isLocalApp();
    if (local && error && error.message) {
      return error.message;
    }
    return fallback || "Unable to load data right now.";
  }

  function updateSectionSnapshot(sectionKey, payload) {
    sectionSnapshots[sectionKey] = Object.assign(
      {
        items: [],
        state: "ok",
        updatedAt: Date.now(),
      },
      payload || {},
      {
        updatedAt: Date.now(),
      },
    );
    renderAdvancedVisibility();
  }

  function buildSectionSnapshotCard(sectionKey) {
    const snapshot = sectionSnapshots[sectionKey] || {};
    const state = snapshot.state || "idle";
    const label =
      state === "error"
        ? "Unavailable"
        : state === "ok"
          ? "Live"
          : "Loading";
    const total = Array.isArray(snapshot.items) ? snapshot.items.length : 0;
    const title = formatSectionTitle(sectionKey);
    const updated = snapshot.updatedAt
      ? new Date(snapshot.updatedAt).toLocaleTimeString()
      : "—";

    return `
      <div class="family-record-card">
        <div class="card-number">${escapeHtml(title.charAt(0))}</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy"><strong>State:</strong> ${escapeHtml(label)}</p>
        <p class="card-copy"><strong>Visible Records:</strong> ${escapeHtml(String(total))}</p>
        <p class="card-copy"><strong>Updated:</strong> ${escapeHtml(updated)}</p>
      </div>
    `;
  }

  function buildPriorityAlerts() {
    const alerts = [];

    const uploads = sectionSnapshots.uploads?.items || [];
    uploads.slice(0, 3).forEach(function (item) {
      alerts.push({
        code: "U",
        title: item.original_filename || "Upload review item",
        copy: `${item.category || "upload"} · ${item.uploaded_by || "unknown user"}`,
      });
    });

    const mints = sectionSnapshots.mints?.items || [];
    mints
      .filter(function (item) {
        const latest = item.latest_mint_record || {};
        return Boolean(latest.error_message || (latest.pending_approvals || []).length);
      })
      .slice(0, 3)
      .forEach(function (item) {
        const latest = item.latest_mint_record || {};
        alerts.push({
          code: "M",
          title: item.project_name || item.project_id || "Mint queue item",
          copy:
            latest.error_message ||
            `Pending approvals: ${(latest.pending_approvals || []).join(", ") || "none"}`,
        });
      });

    const orders = sectionSnapshots.orders?.items || [];
    orders
      .filter(function (item) {
        return ["pending", "failed", "requires_action"].includes(
          normalizeValue(item.status),
        );
      })
      .slice(0, 2)
      .forEach(function (item) {
        alerts.push({
          code: "O",
          title: item.email || item.package_name || "Order needs review",
          copy: `Status: ${item.status || "unknown"}`,
        });
      });

    return alerts.slice(0, 6);
  }

  function renderAdvancedVisibility() {
    const summaryNode = document.querySelector("[data-admin-ops-summary]");
    const feedNode = document.querySelector("[data-admin-priority-feed]");
    const feedStatusNode = document.querySelector("[data-admin-priority-feed-status]");
    if (!summaryNode || !feedNode) return;

    const visibleSections = Object.keys(SECTION_LOADERS).filter(canAccessSection);
    const summaryCards = visibleSections.length
      ? visibleSections.map(buildSectionSnapshotCard).join("")
      : emptyCard("No section access", "No advanced operations sections are available.");
    summaryNode.innerHTML = summaryCards;

    const alerts = buildPriorityAlerts();
    if (!alerts.length) {
      feedNode.innerHTML = emptyCard(
        "Priority queue is clear",
        "No urgent upload, mint, or order items are currently flagged.",
      );
      app.clearStatus(feedStatusNode);
      return;
    }

    feedNode.innerHTML = alerts
      .map(function (alert) {
        return `
          <div class="family-record-card">
            <div class="card-number">${escapeHtml(alert.code)}</div>
            <h3>${escapeHtml(alert.title)}</h3>
            <p class="card-copy">${escapeHtml(alert.copy)}</p>
          </div>
        `;
      })
      .join("");
    app.setStatus(feedStatusNode, `Priority items: ${alerts.length}`, "info");
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
      {
        title: "Paid order without project link",
        value: (priority.paid_order_without_project_link || []).length,
      },
      {
        title: "Project without entitlement",
        value: (priority.project_without_entitlement || []).length,
      },
      {
        title: "Package without lane",
        value: (priority.package_without_lane || []).length,
      },
      {
        title: "Mint-eligible blocked",
        value: (priority.mint_eligible_blocked || []).length,
      },
    ];
    node.innerHTML = cards
      .map(function (item) {
        return `
          <div class="family-record-card admin-card">
            <div class="card-number">!</div>
            <h3>${escapeHtml(item.title)}</h3>
            <p class="card-copy">${escapeHtml(String(item.value))}</p>
          </div>
        `;
      })
      .join("");
  }

  async function loadConsoleOverview() {
    try {
      const payload = await fetchJson("/admin/control-center/overview?limit=24");
      renderTopSummary(payload.summary || {});
      renderPriorityRepairs(payload.priority_repairs || {});
    } catch (_error) {
      renderTopSummary({});
      renderPriorityRepairs({});
    }
  }

  function workspaceStatusBadge(status) {
    const normalized = normalizeValue(status);
    const label = normalized || "unknown";
    const map = {
      healthy: "success",
      warning: "default",
      missing: "error",
      blocked: "error",
      ready: "success",
    };
    return buildStatusChip(label, map[normalized] || "default");
  }

  function buildWorkspaceSection(title, status, body) {
    return `
      <div class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">${escapeHtml(title.charAt(0))}</span>
          <h3 class="admin-card-title">${escapeHtml(title)}</h3>
        </div>
        <p class="card-copy"><strong>Status:</strong> ${workspaceStatusBadge(status)}</p>
        ${body}
      </div>
    `;
  }

  function workspaceHealth(readiness, key) {
    if (!readiness) return "missing";
    if (key === "mint_review_ready") return readiness.mint_review_ready ? "ready" : "blocked";
    if (key === "mint_eligible") return readiness.mint_eligible ? "ready" : "blocked";
    return readiness[key] ? "healthy" : "missing";
  }

  function renderWorkspaceSnapshot(payload) {
    const node = document.querySelector("[data-admin-project-workspace]");
    if (!node) return;
    const project = payload.project || {};
    const order = payload.order || null;
    const entitlement = payload.entitlement || null;
    const readiness = payload.readiness || {};

    node.innerHTML = `
      <div class="inline-actions" style="margin-bottom: 1rem; flex-wrap: wrap">
        <button class="btn btn-secondary" type="button" data-admin-workspace-action="sync-package">Sync Package</button>
        <button class="btn btn-secondary" type="button" data-admin-workspace-action="assign-lane">Assign Lane</button>
        <button class="btn btn-secondary" type="button" data-admin-workspace-action="link-order">Link Order</button>
        <button class="btn btn-secondary" type="button" data-admin-workspace-action="generate-entitlement">Generate Entitlement</button>
        <button class="btn btn-secondary" type="button" data-admin-workspace-action="refresh-readiness">Refresh Readiness</button>
        <button class="btn btn-primary" type="button" data-admin-workspace-action="enable-mint-review">Queue for Mint Review</button>
      </div>
      <div class="grid-3">
        ${buildWorkspaceSection(
          "Identity",
          "healthy",
          `
            <p class="card-copy"><strong>Project:</strong> ${escapeHtml(project.name || "—")}</p>
            <p class="card-copy"><strong>Owner:</strong> ${escapeHtml(project.owner_email || "—")}</p>
            <p class="card-copy"><strong>Project ID:</strong> <span class="admin-id-ref">${escapeHtml(shortId(project.id))}</span></p>
          `,
        )}
        ${buildWorkspaceSection(
          "Package & Lane",
          workspaceHealth(readiness, "lane_assigned"),
          `
            <p class="card-copy"><strong>Package:</strong> ${escapeHtml(project.package_name || project.package_code || "—")}</p>
            <p class="card-copy"><strong>Lane:</strong> ${buildLaneChip(project.project_lane)}</p>
            <p class="card-copy"><strong>Package Synced:</strong> ${yesNoBadge(readiness.package_synced)}</p>
          `,
        )}
        ${buildWorkspaceSection(
          "Order Link",
          workspaceHealth(readiness, "order_linked"),
          `
            <p class="card-copy"><strong>Order:</strong> <span class="admin-id-ref">${escapeHtml(shortId((order || {}).id))}</span></p>
            <p class="card-copy"><strong>Order Status:</strong> ${buildStatusChip((order || {}).status || "none", (order || {}).status === "paid" ? "success" : "default")}</p>
            <p class="card-copy"><strong>Linked:</strong> ${yesNoBadge(readiness.order_linked)}</p>
          `,
        )}
        ${buildWorkspaceSection(
          "Entitlement",
          workspaceHealth(readiness, "entitlement_exists"),
          `
            <p class="card-copy"><strong>Exists:</strong> ${yesNoBadge(readiness.entitlement_exists)}</p>
            <p class="card-copy"><strong>Plan:</strong> ${escapeHtml((entitlement || {}).maintenance_plan || "—")}</p>
            <p class="card-copy"><strong>Status:</strong> ${escapeHtml((entitlement || {}).maintenance_status || "—")}</p>
          `,
        )}
        ${buildWorkspaceSection(
          "Uploads / Intake",
          readiness.uploads_present && readiness.intake_approved ? "healthy" : "warning",
          `
            <p class="card-copy"><strong>Uploads Present:</strong> ${yesNoBadge(readiness.uploads_present)}</p>
            <p class="card-copy"><strong>Build Ready:</strong> ${yesNoBadge(readiness.build_ready)}</p>
            <p class="card-copy"><strong>Intake Approved:</strong> ${yesNoBadge(readiness.intake_approved)}</p>
          `,
        )}
        ${buildWorkspaceSection(
          "Mint Readiness",
          workspaceHealth(readiness, "mint_eligible"),
          `
            <p class="card-copy"><strong>Mint Review Ready:</strong> ${yesNoBadge(readiness.mint_review_ready)}</p>
            <p class="card-copy"><strong>Mint Eligible:</strong> ${yesNoBadge(readiness.mint_eligible)}</p>
            <p class="card-copy"><strong>Policy:</strong> ${escapeHtml(((readiness.mint_policy || {}).token_type) || "—")}</p>
          `,
        )}
      </div>
    `;
  }

  async function loadWorkspace(projectId) {
    if (!projectId) return;
    selectedProjectId = projectId;
    const workspaceNode = document.querySelector("[data-admin-project-workspace]");
    if (workspaceNode) {
      workspaceNode.innerHTML = emptyCard("Loading workspace...", "Pulling project command panel...");
    }
    try {
      const payload = await fetchJson(`/admin/control-center/projects/${encodeURIComponent(projectId)}/workspace`);
      renderWorkspaceSnapshot(payload || {});
    } catch (error) {
      if (workspaceNode) {
        workspaceNode.innerHTML = emptyCard("Workspace unavailable", error.message || "Unable to load project workspace.");
      }
    }
  }

  function updateRoleSummary() {
    const roleTitle = getRoleTitle(currentRoleKey);
    const visibleSections = Object.keys(SECTION_ACCESS).filter(canAccessSection);

    const titleNode = document.querySelector("[data-admin-control-title]");
    const statusNode = document.querySelector("[data-admin-control-status]");
    const roleNode = document.querySelector("[data-admin-control-role]");
    const laneNode = document.querySelector("[data-admin-control-lane]");
    const toolsNode = document.querySelector("[data-admin-control-tools]");

    if (titleNode) titleNode.textContent = roleTitle;
    if (statusNode) {
      statusNode.textContent =
        "Internal controls are live for uploads, records, entitlements, mint review, and troubleshooting based on your role.";
    }
    if (roleNode) roleNode.textContent = roleTitle;
    if (laneNode) laneNode.textContent = currentRoleKey || "internal";
    if (toolsNode) {
      toolsNode.textContent = visibleSections.length
        ? `${visibleSections.length} section(s) published`
        : "No browser tools published for this role yet";
    }
  }

  function applySectionVisibility() {
    document.querySelectorAll("[data-control-section]").forEach(function (node) {
      const sectionKey = node.getAttribute("data-control-section") || "";
      node.style.display = canAccessSection(sectionKey) ? "" : "none";
    });
  }

  function renderSectionCards(sectionKey, cardsMarkup) {
    const node = sectionListNode(sectionKey);
    if (!node) return;
    node.innerHTML = cardsMarkup;
  }

  function markAllSectionsUnavailable(message) {
    Object.keys(SECTION_LOADERS).forEach(function (sectionKey) {
      if (!canAccessSection(sectionKey)) return;
      const title = formatSectionTitle(sectionKey);
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard(`${title} unavailable`, message),
      );
      setSectionStatus(sectionKey, message, "error");
    });
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

  async function downloadUpload(uploadId, originalFilename) {
    const token = typeof app.getToken === "function" ? app.getToken() : "";
    const response = await fetch(
      `${app.getApiBaseUrl()}/uploads/${encodeURIComponent(uploadId)}/download`,
      {
        method: "GET",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      },
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Unable to download upload.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = originalFilename || "download";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function buildUploadCard(item) {
    const familyHref = item.family_id
      ? `admin-family-manager.html?family_id=${encodeURIComponent(item.family_id)}`
      : "";

    return `
      <div class="family-record-card">
        <div class="card-number">U</div>
        <h3>${escapeHtml(item.original_filename || "Uploaded File")}</h3>
        <p class="card-copy"><strong>Category:</strong> ${escapeHtml(item.category || "—")}</p>
        <p class="card-copy"><strong>Project:</strong> ${escapeHtml(item.project_name || item.project_id || "—")}</p>
        <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")}</p>
        <p class="card-copy"><strong>Member:</strong> ${escapeHtml(item.member_name || item.member_id || "—")}</p>
        <p class="card-copy"><strong>Uploaded By:</strong> ${escapeHtml(item.uploaded_by || "—")}</p>
        <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
        <div class="inline-actions" style="margin-top: 1rem;">
          <button class="btn btn-secondary" type="button" data-admin-open-workspace="${escapeHtml(item.id || "")}">
            Open Ops Panel
          </button>
          ${
            familyHref
              ? `<a class="btn btn-secondary" href="${escapeHtml(familyHref)}">Open Family</a>`
              : ""
          }
          <button class="btn btn-secondary" type="button" data-upload-download="${escapeHtml(item.id || "")}" data-upload-name="${escapeHtml(item.original_filename || "download")}">Download</button>
          <button class="btn btn-secondary" type="button" data-upload-delete="${escapeHtml(item.id || "")}">Delete</button>
        </div>
      </div>
    `;
  }

  function buildMintCard(item) {
    const latest = item.latest_mint_record || null;
    const policy = (item.eligibility || {}).mint_policy || {};
    const isEligible = Boolean((item.eligibility || {}).eligible);
    const pendingApprovals = Array.isArray((latest || {}).pending_approvals)
      ? latest.pending_approvals
      : [];
    const canPrepare = Boolean(policy.product_includes_onchain_anchor);
    const prepareLabel = latest ? "Prepare New Version" : "Prepare Mint";

    return `
      <div class="family-record-card">
        <div class="card-number">M</div>
        <h3>${escapeHtml(item.project_name || item.project_id || "Workspace")}</h3>
        <p class="card-copy"><strong>Owner:</strong> ${escapeHtml(item.owner_email || "—")}</p>
        <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package_name || item.package_code || "—")}</p>
        <p class="card-copy"><strong>Build:</strong> ${escapeHtml(item.status || "—")} / ${escapeHtml(item.phase || "—")}</p>
        <p class="card-copy"><strong>Eligibility:</strong> ${escapeHtml((item.eligibility || {}).eligible ? "Ready" : ((item.eligibility || {}).reasons || []).join(", ") || "Not ready")}</p>
        <p class="card-copy"><strong>Latest Mint:</strong> ${escapeHtml((latest || {}).mint_status || "none")}</p>
        <p class="card-copy"><strong>Pending Approvals:</strong> ${escapeHtml(pendingApprovals.join(", ") || "none")}</p>
        <p class="card-copy"><strong>Token:</strong> ${escapeHtml((latest || {}).token_id || "—")}</p>
        <p class="card-copy"><strong>Error:</strong> ${escapeHtml((latest || {}).error_message || "—")}</p>
        <div class="inline-actions" style="margin-top: 1rem;">
          ${
            canPrepare
              ? `<button class="btn btn-secondary" type="button" data-mint-prepare="${escapeHtml(item.project_id || "")}">${escapeHtml(prepareLabel)}</button>`
              : ""
          }
          ${
            latest && pendingApprovals.includes("admin_final")
              ? `<button class="btn btn-secondary" type="button" data-mint-approve-admin="${escapeHtml(item.project_id || "")}" data-mint-record-id="${escapeHtml(latest.id || "")}">Approve Admin</button>`
              : ""
          }
          ${
            latest && pendingApprovals.includes("customer_public_safe")
              ? `<button class="btn btn-secondary" type="button" data-mint-approve-customer="${escapeHtml(item.project_id || "")}" data-mint-record-id="${escapeHtml(latest.id || "")}">Approve Customer Override</button>`
              : ""
          }
          ${
            latest && isEligible && ["approved", "queued"].includes(String(latest.mint_status || ""))
              ? `<button class="btn btn-secondary" type="button" data-mint-queue="${escapeHtml(item.project_id || "")}" data-mint-record-id="${escapeHtml(latest.id || "")}">Queue Mint</button>`
              : ""
          }
          ${
            latest && latest.id
              ? `<button class="btn btn-secondary" type="button" data-mint-sync="${escapeHtml(latest.id || "")}">Sync Receipt</button>`
              : ""
          }
        </div>
      </div>
    `;
  }

  function buildStatusChip(value, chipClass) {
    if (!value) return "";
    return `<span class="admin-status-chip admin-status-chip--${escapeHtml(chipClass || "default")}">${escapeHtml(value)}</span>`;
  }

  function buildLaneChip(lane) {
    const laneMap = {
      portrait: "Portrait",
      household: "Household",
      network: "Network",
      organization: "Organization",
    };
    const label = laneMap[String(lane || "").toLowerCase()] || lane || "—";
    const cls = laneMap[String(lane || "").toLowerCase()] ? lane.toLowerCase() : "default";
    return `<span class="admin-lane-chip admin-lane-chip--${escapeHtml(cls)}">${escapeHtml(label)}</span>`;
  }

  function shortId(id) {
    if (!id) return "—";
    const s = String(id);
    return s.length > 12 ? `…${s.slice(-8)}` : s;
  }

  function yesNoBadge(value) {
    return buildStatusChip(value ? "yes" : "no", value ? "success" : "error");
  }

  function statusFromHealth(health) {
    const normalized = normalizeValue(health);
    if (normalized === "healthy" || normalized === "ready") return "success";
    if (normalized === "blocked") return "error";
    if (normalized === "missing" || normalized === "warning") return "default";
    return "default";
  }

  function buildOrderCard(item) {
    const projectDisplay = item.project_id
      ? shortId(item.project_id)
      : "No project linked";
    return `
      <div class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">O</span>
          <h3 class="admin-card-title">${escapeHtml(item.package_name || item.package_code || "Order")}</h3>
        </div>
        <div class="admin-card-meta">
          <p class="card-copy"><strong>Email:</strong> ${escapeHtml(item.email || "—")}</p>
          <p class="card-copy"><strong>Status:</strong> ${buildStatusChip(item.status, item.status === "paid" ? "success" : "default")}</p>
          <p class="card-copy"><strong>Plan:</strong> ${escapeHtml(item.billing_plan || "—")}</p>
          <p class="card-copy"><strong>Project:</strong> <span class="admin-id-ref">${escapeHtml(projectDisplay)}</span></p>
          <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
        </div>
      </div>
    `;
  }

  function buildEntitlementCard(item) {
    return `
      <div class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">E</span>
          <h3 class="admin-card-title">${escapeHtml(item.package_name || item.package_code || "Entitlement")}</h3>
        </div>
        <div class="admin-card-meta">
          <p class="card-copy"><strong>Project:</strong> <span class="admin-id-ref">${escapeHtml(shortId(item.project_id))}</span></p>
          <p class="card-copy"><strong>User:</strong> <span class="admin-id-ref">${escapeHtml(shortId(item.user_id))}</span></p>
          <p class="card-copy"><strong>Status:</strong> ${buildStatusChip(item.status, item.status === "active" ? "success" : "default")}</p>
          <p class="card-copy"><strong>Maintenance:</strong> ${escapeHtml(item.maintenance_status || "—")}</p>
          <p class="card-copy"><strong>Updated:</strong> ${escapeHtml(formatDate(item.updated_at))}</p>
        </div>
      </div>
    `;
  }

  function buildProjectCard(item) {
    const familyHref = item.family_id
      ? `admin-family-manager.html?family_id=${encodeURIComponent(item.family_id)}`
      : "";

    return `
      <div class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">P</span>
          <h3 class="admin-card-title">${escapeHtml(item.name || "Project")}</h3>
        </div>
        <div class="admin-card-meta">
          <p class="card-copy"><strong>Owner:</strong> ${escapeHtml(item.owner_email || "—")}</p>
          <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package_name || item.package_code || "—")}</p>
          <p class="card-copy"><strong>Status:</strong> ${buildStatusChip(item.status, item.status === "purchased" || item.status === "delivered" ? "success" : "default")}</p>
          <p class="card-copy"><strong>Phase:</strong> ${escapeHtml(item.phase || "—")}</p>
          <p class="card-copy"><strong>Lane:</strong> ${buildLaneChip(item.project_lane)}</p>
        </div>
        <div class="inline-actions" style="margin-top: 1rem;">
          ${
            familyHref
              ? `<a class="btn btn-secondary" href="${escapeHtml(familyHref)}">Open Family</a>`
              : ""
          }
        </div>
      </div>
    `;
  }

  function buildUserCard(item) {
    return `
      <div class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">U</span>
          <h3 class="admin-card-title">${escapeHtml(item.full_name || `${item.first_name || ""} ${item.last_name || ""}`.trim() || item.email || "User")}</h3>
        </div>
        <div class="admin-card-meta">
          <p class="card-copy"><strong>Email:</strong> ${escapeHtml(item.email || "—")}</p>
          <p class="card-copy"><strong>Role:</strong> ${buildStatusChip(item.role, "role")}</p>
          <p class="card-copy"><strong>Status:</strong> ${buildStatusChip(item.status, item.status === "active" ? "success" : "default")}</p>
          <p class="card-copy"><strong>Last Login:</strong> ${escapeHtml(formatDate(item.last_login_at))}</p>
          <p class="card-copy"><strong>Reset Requested:</strong> ${escapeHtml(formatDate(item.password_reset_requested_at))}</p>
          <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
        </div>
        <div class="inline-actions" style="margin-top: 1rem;">
          <button class="btn btn-secondary" type="button" data-admin-password-reset="${escapeHtml(item.id || "")}">
            Issue Reset Link
          </button>
        </div>
      </div>
    `;
  }

  function renderWorkspaceProjectList(items) {
    const node = document.querySelector("[data-admin-project-workspace-list]");
    if (!node) return;
    const list = Array.isArray(items) ? items.slice(0, 12) : [];
    node.innerHTML = list.length
      ? list
          .map(function (item) {
            return `
              <div class="family-record-card admin-card">
                <div class="admin-card-header">
                  <span class="admin-card-badge">P</span>
                  <h3 class="admin-card-title">${escapeHtml(item.name || "Project")}</h3>
                </div>
                <p class="card-copy"><strong>Owner:</strong> ${escapeHtml(item.owner_email || "—")}</p>
                <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package_name || item.package_code || "—")}</p>
                <button class="btn btn-secondary" type="button" data-admin-open-workspace="${escapeHtml(item.id || "")}">
                  Open Workspace
                </button>
              </div>
            `;
          })
          .join("")
      : emptyCard("No projects", "No projects available for workspace view.");
  }

  function buildAuditCard(item) {
    const action = item.action || item.event || item.entity_type || "Audit Event";
    return `
      <div class="family-record-card admin-card">
        <div class="admin-card-header">
          <span class="admin-card-badge">A</span>
          <h3 class="admin-card-title">${escapeHtml(action)}</h3>
        </div>
        <div class="admin-card-meta">
          <p class="card-copy"><strong>Target:</strong> ${escapeHtml(item.target_type || item.entity_type || "—")} / <span class="admin-id-ref">${escapeHtml(shortId(item.target_id || item.entity_id))}</span></p>
          <p class="card-copy"><strong>Actor:</strong> ${escapeHtml(item.actor_email || item.actor_name || shortId(item.actor_user_id))}</p>
          <p class="card-copy"><strong>Result:</strong> ${buildStatusChip(item.result, item.result === "success" ? "success" : item.result === "failure" ? "error" : "default")}</p>
          <p class="card-copy"><strong>When:</strong> ${escapeHtml(formatDate(item.created_at || item.timestamp))}</p>
        </div>
      </div>
    `;
  }

  async function loadUploads() {
    const sectionKey = "uploads";
    try {
      setSectionStatus(sectionKey, "Loading uploaded file review...", "info");
      const payload = await fetchJson(
        `/uploads/admin/review?limit=24&search=${encodeURIComponent(getSearchValue())}`,
      );
      const items = Array.isArray(payload.items) ? payload.items : [];
      updateSectionSnapshot(sectionKey, { items, state: "ok" });
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildUploadCard).join("")
          : emptyCard("No uploads found", "No customer uploads matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      renderWorkspaceProjectList([]);
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Upload review unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadMints() {
    const sectionKey = "mints";
    try {
      setSectionStatus(sectionKey, "Loading mint controls...", "info");
      const payload = await fetchJson(
        `/admin/mint-records/overview?limit=24&search=${encodeURIComponent(getSearchValue())}&mintable_only=true`,
      );
      const items = Array.isArray(payload.items) ? payload.items : [];
      updateSectionSnapshot(sectionKey, { items, state: "ok" });
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildMintCard).join("")
          : emptyCard("No mint records found", "No mint-eligible projects matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Mint controls unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadOrders() {
    const sectionKey = "orders";
    try {
      setSectionStatus(sectionKey, "Loading order records...", "info");
      const payload = await fetchJson(
        `/orders/admin/all?limit=24&search=${encodeURIComponent(getSearchValue())}`,
      );
      const items = Array.isArray(payload.items) ? payload.items : [];
      updateSectionSnapshot(sectionKey, { items, state: "ok" });
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildOrderCard).join("")
          : emptyCard("No orders found", "No orders matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Orders unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadEntitlements() {
    const sectionKey = "entitlements";
    try {
      setSectionStatus(sectionKey, "Loading project entitlements...", "info");
      const payload = await fetchJson(
        `/project-entitlements/admin/list?limit=24&search=${encodeURIComponent(getSearchValue())}`,
      );
      const items = Array.isArray(payload.items) ? payload.items : [];
      updateSectionSnapshot(sectionKey, { items, state: "ok" });
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildEntitlementCard).join("")
          : emptyCard("No entitlements found", "No project entitlements matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Entitlements unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadProjects() {
    const sectionKey = "projects";
    try {
      setSectionStatus(sectionKey, "Loading project records...", "info");
      const items = await fetchJson("/projects");
      const filtered = Array.isArray(items)
        ? items.filter(function (item) {
            const haystack = [
              item.id,
              item.name,
              item.owner_email,
              item.package_code,
              item.package_name,
              item.project_lane,
            ]
              .join(" ")
              .toLowerCase();
            const search = getSearchValue().toLowerCase();
            return !search || haystack.includes(search);
          })
        : [];
      updateSectionSnapshot(sectionKey, { items: filtered.slice(0, 24), state: "ok" });
      renderWorkspaceProjectList(filtered);
      renderSectionCards(
        sectionKey,
        filtered.length
          ? filtered.slice(0, 24).map(buildProjectCard).join("")
          : emptyCard("No projects found", "No projects matched the current filters."),
      );
      if (!selectedProjectId && filtered.length) {
        await loadWorkspace(filtered[0].id);
      }
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Projects unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadUsers() {
    const sectionKey = "users";
    try {
      setSectionStatus(sectionKey, "Loading user directory...", "info");
      const items = await fetchJson("/users/");
      const filtered = Array.isArray(items)
        ? items.filter(function (item) {
          const haystack = [
              item.full_name,
              item.first_name,
              item.last_name,
              item.email,
              item.role,
              item.status,
            ]
              .join(" ")
              .toLowerCase();
            const search = getSearchValue().toLowerCase();
            return !search || haystack.includes(search);
          })
        : [];
      updateSectionSnapshot(sectionKey, { items: filtered.slice(0, 24), state: "ok" });
      renderSectionCards(
        sectionKey,
        filtered.length
          ? filtered.slice(0, 24).map(buildUserCard).join("")
          : emptyCard("No users found", "No users matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Users unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadAuditLogs() {
    const sectionKey = "audit";
    try {
      setSectionStatus(sectionKey, "Loading audit trail...", "info");
      const items = await fetchJson("/audit-logs/");
      const filtered = Array.isArray(items)
        ? items.filter(function (item) {
            const haystack = [
              item.action,
              item.entity_type,
              item.entity_id,
              item.actor_email,
              item.actor_name,
            ]
              .join(" ")
              .toLowerCase();
            const search = getSearchValue().toLowerCase();
            return !search || haystack.includes(search);
          })
        : [];
      updateSectionSnapshot(sectionKey, { items: filtered.slice(0, 24), state: "ok" });
      renderSectionCards(
        sectionKey,
        filtered.length
          ? filtered.slice(0, 24).map(buildAuditCard).join("")
          : emptyCard("No audit logs found", "No audit logs matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      const message = safeErrorMessage(
        error,
        "This section is temporarily unavailable.",
      );
      updateSectionSnapshot(sectionKey, { items: [], state: "error" });
      renderSectionCards(
        sectionKey,
        emptyCard("Audit logs unavailable", message),
      );
      setSectionStatus(sectionKey, message, "error");
    }
  }

  async function loadVisibleSections() {
    const sectionKeys = Object.keys(SECTION_LOADERS).filter(canAccessSection);
    sectionKeys.forEach(function (sectionKey) {
      updateSectionSnapshot(sectionKey, {
        items: (sectionSnapshots[sectionKey] && sectionSnapshots[sectionKey].items) || [],
        state: "loading",
      });
    });
    await Promise.allSettled(
      sectionKeys.map(function (sectionKey) {
        return SECTION_LOADERS[sectionKey]();
      }),
    );
  }

  async function runMintAction(path, body, message) {
    setPageStatus(message, "info");
    await app.apiRequest(path, {
      method: "POST",
      body: JSON.stringify(body || {}),
    });
    setPageStatus("Mint control updated successfully.", "success");
    await loadMints();
  }

  async function handleClick(event) {
    const openWorkspaceButton = event.target.closest("[data-admin-open-workspace]");
    if (openWorkspaceButton) {
      const projectId = openWorkspaceButton.getAttribute("data-admin-open-workspace");
      if (!projectId) return;
      await loadWorkspace(projectId);
      return;
    }

    const workspaceActionButton = event.target.closest("[data-admin-workspace-action]");
    if (workspaceActionButton) {
      if (!selectedProjectId) {
        setPageStatus("Select a project first.", "error");
        return;
      }
      const action = workspaceActionButton.getAttribute("data-admin-workspace-action");
      try {
        if (action === "sync-package") {
          setPageStatus("Syncing package...", "info");
          await postJson(`/admin/control-center/projects/${encodeURIComponent(selectedProjectId)}/sync-package`, {});
        } else if (action === "assign-lane") {
          setPageStatus("Assigning lane...", "info");
          await postJson(`/admin/control-center/projects/${encodeURIComponent(selectedProjectId)}/assign-lane`, {});
        } else if (action === "link-order") {
          const workspace = await fetchJson(`/admin/control-center/projects/${encodeURIComponent(selectedProjectId)}/workspace`);
          const orderId = (workspace.order || {}).id;
          if (!orderId) {
            throw new Error("No order was found to link.");
          }
          setPageStatus("Linking order...", "info");
          await postJson(`/admin/control-center/orders/${encodeURIComponent(orderId)}/link-project`, {
            project_id: selectedProjectId,
          });
        } else if (action === "generate-entitlement") {
          setPageStatus("Generating entitlement...", "info");
          await postJson(`/admin/control-center/projects/${encodeURIComponent(selectedProjectId)}/generate-entitlement`, {
            force: true,
          });
        } else if (action === "refresh-readiness") {
          setPageStatus("Refreshing readiness...", "info");
          await fetchJson(`/admin/control-center/projects/${encodeURIComponent(selectedProjectId)}/readiness-check`);
        } else if (action === "enable-mint-review") {
          setPageStatus("Queueing mint review readiness...", "info");
          await postJson(`/admin/control-center/projects/${encodeURIComponent(selectedProjectId)}/enable-mint-review`, {});
        }
        await Promise.allSettled([loadWorkspace(selectedProjectId), loadConsoleOverview(), loadProjects()]);
        setPageStatus("Admin operation completed.", "success");
      } catch (error) {
        setPageStatus(error.message || "Unable to run admin operation.", "error");
      }
      return;
    }

    const downloadButton = event.target.closest("[data-upload-download]");
    if (downloadButton) {
      try {
        setPageStatus("Downloading upload...", "info");
        await downloadUpload(
          downloadButton.getAttribute("data-upload-download"),
          downloadButton.getAttribute("data-upload-name"),
        );
        setPageStatus("Upload downloaded successfully.", "success");
      } catch (error) {
        setPageStatus(error.message || "Unable to download upload.", "error");
      }
      return;
    }

    const deleteButton = event.target.closest("[data-upload-delete]");
    if (deleteButton) {
      const uploadId = deleteButton.getAttribute("data-upload-delete");
      if (!uploadId) return;
      if (!window.confirm("Delete this upload? This action cannot be undone.")) {
        return;
      }
      try {
        setPageStatus("Deleting upload...", "info");
        await app.apiRequest(`/uploads/${encodeURIComponent(uploadId)}`, {
          method: "DELETE",
        });
        setPageStatus("Upload deleted successfully.", "success");
        await loadUploads();
      } catch (error) {
        setPageStatus(error.message || "Unable to delete upload.", "error");
      }
      return;
    }

    const prepareButton = event.target.closest("[data-mint-prepare]");
    if (prepareButton) {
      const projectId = prepareButton.getAttribute("data-mint-prepare");
      if (!projectId) return;
      await runMintAction(
        `/projects/${encodeURIComponent(projectId)}/mint-records/prepare`,
        {
          version_strategy: "new_version_if_needed",
          poster_style: "abstract_cover",
          public_title_opt_in: false,
          public_title: "",
          public_title_kind: "none",
        },
        "Preparing mint record...",
      );
      return;
    }

    const approveAdminButton = event.target.closest("[data-mint-approve-admin]");
    if (approveAdminButton) {
      const projectId = approveAdminButton.getAttribute("data-mint-approve-admin");
      const mintRecordId = approveAdminButton.getAttribute("data-mint-record-id");
      if (!projectId || !mintRecordId) return;
      await runMintAction(
        `/projects/${encodeURIComponent(projectId)}/mint-records/${encodeURIComponent(mintRecordId)}/approve-admin`,
        { notes: "Approved through the internal control center." },
        "Approving admin mint step...",
      );
      return;
    }

    const approveCustomerButton = event.target.closest("[data-mint-approve-customer]");
    if (approveCustomerButton) {
      const projectId = approveCustomerButton.getAttribute("data-mint-approve-customer");
      const mintRecordId = approveCustomerButton.getAttribute("data-mint-record-id");
      if (!projectId || !mintRecordId) return;
      await runMintAction(
        `/projects/${encodeURIComponent(projectId)}/mint-records/${encodeURIComponent(mintRecordId)}/approve-customer-admin`,
        {
          notes: "Approved by internal admin override for troubleshooting or managed delivery.",
          wallet_address: "",
          approved_poster_opt_in: false,
          public_title_opt_in: false,
          public_title: "",
          public_title_kind: "none",
        },
        "Approving customer public-safe step...",
      );
      return;
    }

    const queueButton = event.target.closest("[data-mint-queue]");
    if (queueButton) {
      const projectId = queueButton.getAttribute("data-mint-queue");
      const mintRecordId = queueButton.getAttribute("data-mint-record-id");
      if (!projectId || !mintRecordId) return;
      await runMintAction(
        `/projects/${encodeURIComponent(projectId)}/mint-records/${encodeURIComponent(mintRecordId)}/queue`,
        {},
        "Queueing mint job...",
      );
      return;
    }

    const syncButton = event.target.closest("[data-mint-sync]");
    if (syncButton) {
      const mintRecordId = syncButton.getAttribute("data-mint-sync");
      if (!mintRecordId) return;
      await runMintAction(
        `/mint-records/${encodeURIComponent(mintRecordId)}/sync`,
        {},
        "Syncing mint receipt...",
      );
      return;
    }

    const passwordResetButton = event.target.closest("[data-admin-password-reset]");
    if (passwordResetButton) {
      const userId = passwordResetButton.getAttribute("data-admin-password-reset");
      if (!userId) return;
      try {
        setPageStatus("Issuing password reset link...", "info");
        const payload = await app.apiRequest(
          `/auth/admin/users/${encodeURIComponent(userId)}/password-reset`,
          {
            method: "POST",
          },
        );
        const resetUrl = String(payload && payload.reset_url ? payload.reset_url : "").trim();
        if (resetUrl && navigator.clipboard && navigator.clipboard.writeText) {
          try {
            await navigator.clipboard.writeText(resetUrl);
            setPageStatus("Password reset link issued and copied to clipboard.", "success");
          } catch (_error) {
            setPageStatus("Password reset link issued. Copy it from the dialog.", "success");
          }
        } else {
          setPageStatus("Password reset link issued successfully.", "success");
        }

        if (resetUrl) {
          window.prompt("Share this secure reset link with the user:", resetUrl);
        }
        await loadUsers();
      } catch (error) {
        setPageStatus(error.message || "Unable to issue password reset link.", "error");
      }
    }
  }

  function bindRefreshButtons() {
    document.querySelectorAll("[data-section-refresh]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const sectionKey = button.getAttribute("data-section-refresh") || "";
        const loader = SECTION_LOADERS[sectionKey];
        if (!loader || !canAccessSection(sectionKey)) return;
        await loader();
      });
    });

    const refreshAllButton = document.querySelector("[data-admin-control-refresh]");
    if (refreshAllButton) {
      refreshAllButton.addEventListener("click", async function () {
        setPageStatus("Refreshing internal console...", "info");
        await Promise.allSettled([loadVisibleSections(), loadConsoleOverview()]);
        setPageStatus("Internal control center refreshed.", "success");
      });
    }

    const searchNode = document.querySelector("[data-admin-control-search]");
    if (searchNode) {
      searchNode.addEventListener("change", loadVisibleSections);
    }
  }

  async function setupPage() {
    currentUser = await app.requireSession("signin.html");
    if (!currentUser) return;

    currentRoleKey = getInternalRoleKey(currentUser);
    if (!currentRoleKey) {
      window.location.href = "dashboard.html";
      return;
    }

    updateRoleSummary();
    applySectionVisibility();
    renderAdvancedVisibility();
    bindRefreshButtons();
    document.addEventListener("click", function (event) {
      handleClick(event).catch(function (error) {
        setPageStatus(error.message || "Unable to complete that action.", "error");
      });
    });

    await Promise.allSettled([loadVisibleSections(), loadConsoleOverview()]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupPage().catch(function (error) {
      console.error("Failed to load admin control center:", error);
      const message = safeErrorMessage(
        error,
        "Unable to load internal control center.",
      );
      markAllSectionsUnavailable(message);
      setPageStatus(message, "error");
    });
  });
})();
