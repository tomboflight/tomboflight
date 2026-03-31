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
    return (
      signals.find(function (value) {
        return INTERNAL_ROLE_KEYS.has(value);
      }) || ""
    );
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

  function emptyCard(title, copy) {
    return `
      <div class="family-record-card">
        <div class="card-number">•</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${escapeHtml(copy)}</p>
      </div>
    `;
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

  async function fetchJson(path) {
    return app.apiRequest(path, { method: "GET" });
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

  function buildOrderCard(item) {
    return `
      <div class="family-record-card">
        <div class="card-number">O</div>
        <h3>${escapeHtml(item.package_name || item.package_code || "Order")}</h3>
        <p class="card-copy"><strong>Email:</strong> ${escapeHtml(item.email || "—")}</p>
        <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.status || "—")}</p>
        <p class="card-copy"><strong>Billing:</strong> ${escapeHtml(item.billing_plan || "—")}</p>
        <p class="card-copy"><strong>Project:</strong> ${escapeHtml(item.project_id || "—")}</p>
        <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
      </div>
    `;
  }

  function buildEntitlementCard(item) {
    return `
      <div class="family-record-card">
        <div class="card-number">E</div>
        <h3>${escapeHtml(item.package_name || item.package_code || "Entitlement")}</h3>
        <p class="card-copy"><strong>Project:</strong> ${escapeHtml(item.project_id || "—")}</p>
        <p class="card-copy"><strong>User:</strong> ${escapeHtml(item.user_id || "—")}</p>
        <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.status || "—")}</p>
        <p class="card-copy"><strong>Maintenance:</strong> ${escapeHtml(item.maintenance_status || "—")}</p>
        <p class="card-copy"><strong>Updated:</strong> ${escapeHtml(formatDate(item.updated_at))}</p>
      </div>
    `;
  }

  function buildProjectCard(item) {
    const familyHref = item.family_id
      ? `admin-family-manager.html?family_id=${encodeURIComponent(item.family_id)}`
      : "";

    return `
      <div class="family-record-card">
        <div class="card-number">P</div>
        <h3>${escapeHtml(item.name || "Project")}</h3>
        <p class="card-copy"><strong>Owner:</strong> ${escapeHtml(item.owner_email || "—")}</p>
        <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package_name || item.package_code || "—")}</p>
        <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.status || "—")}</p>
        <p class="card-copy"><strong>Phase:</strong> ${escapeHtml(item.phase || "—")}</p>
        <p class="card-copy"><strong>Lane:</strong> ${escapeHtml(item.project_lane || "—")}</p>
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
      <div class="family-record-card">
        <div class="card-number">U</div>
        <h3>${escapeHtml(item.full_name || `${item.first_name || ""} ${item.last_name || ""}`.trim() || item.email || "User")}</h3>
        <p class="card-copy"><strong>Email:</strong> ${escapeHtml(item.email || "—")}</p>
        <p class="card-copy"><strong>Role:</strong> ${escapeHtml(item.role || "—")}</p>
        <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.status || "—")}</p>
        <p class="card-copy"><strong>Last Login:</strong> ${escapeHtml(formatDate(item.last_login_at))}</p>
        <p class="card-copy"><strong>Reset Requested:</strong> ${escapeHtml(formatDate(item.password_reset_requested_at))}</p>
        <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
        <div class="inline-actions" style="margin-top: 1rem;">
          <button class="btn btn-secondary" type="button" data-admin-password-reset="${escapeHtml(item.id || "")}">
            Issue Reset Link
          </button>
        </div>
      </div>
    `;
  }

  function buildAuditCard(item) {
    return `
      <div class="family-record-card">
        <div class="card-number">A</div>
        <h3>${escapeHtml(item.action || "Audit Event")}</h3>
        <p class="card-copy"><strong>Entity:</strong> ${escapeHtml(item.entity_type || "—")} / ${escapeHtml(item.entity_id || "—")}</p>
        <p class="card-copy"><strong>Actor:</strong> ${escapeHtml(item.actor_email || item.actor_name || item.actor_user_id || "—")}</p>
        <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
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
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildUploadCard).join("")
          : emptyCard("No uploads found", "No customer uploads matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Upload review unavailable", error.message || "Unable to load uploads."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load uploads.", "error");
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
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildMintCard).join("")
          : emptyCard("No mint records found", "No mint-eligible projects matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Mint controls unavailable", error.message || "Unable to load mint controls."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load mint controls.", "error");
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
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildOrderCard).join("")
          : emptyCard("No orders found", "No orders matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Orders unavailable", error.message || "Unable to load orders."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load orders.", "error");
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
      renderSectionCards(
        sectionKey,
        items.length
          ? items.map(buildEntitlementCard).join("")
          : emptyCard("No entitlements found", "No project entitlements matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Entitlements unavailable", error.message || "Unable to load entitlements."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load entitlements.", "error");
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
      renderSectionCards(
        sectionKey,
        filtered.length
          ? filtered.slice(0, 24).map(buildProjectCard).join("")
          : emptyCard("No projects found", "No projects matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Projects unavailable", error.message || "Unable to load projects."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load projects.", "error");
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
      renderSectionCards(
        sectionKey,
        filtered.length
          ? filtered.slice(0, 24).map(buildUserCard).join("")
          : emptyCard("No users found", "No users matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Users unavailable", error.message || "Unable to load users."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load users.", "error");
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
      renderSectionCards(
        sectionKey,
        filtered.length
          ? filtered.slice(0, 24).map(buildAuditCard).join("")
          : emptyCard("No audit logs found", "No audit logs matched the current filters."),
      );
      clearSectionStatus(sectionKey);
    } catch (error) {
      renderSectionCards(
        sectionKey,
        emptyCard("Audit logs unavailable", error.message || "Unable to load audit logs."),
      );
      setSectionStatus(sectionKey, error.message || "Unable to load audit logs.", "error");
    }
  }

  async function loadVisibleSections() {
    const sectionKeys = Object.keys(SECTION_LOADERS).filter(canAccessSection);
    for (const sectionKey of sectionKeys) {
      await SECTION_LOADERS[sectionKey]();
    }
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
        await loadVisibleSections();
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
    bindRefreshButtons();
    document.addEventListener("click", function (event) {
      handleClick(event).catch(function (error) {
        setPageStatus(error.message || "Unable to complete that action.", "error");
      });
    });

    await loadVisibleSections();
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupPage().catch(function (error) {
      console.error("Failed to load admin control center:", error);
      setPageStatus(error.message || "Unable to load internal control center.", "error");
    });
  });
})();
