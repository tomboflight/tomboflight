(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    console.error("upload-hub.js requires app.js/auth.js first.");
    return;
  }

  const VAULT_FLAGS = [
    "can_use_personal_vault",
    "can_use_household_vault",
    "can_use_linked_household_vault",
    "can_use_organization_records_vault",
  ];

  function normalize(value) {
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

  function workspaceFrom(context) {
    return context && context.workspace && typeof context.workspace === "object"
      ? context.workspace
      : {};
  }

  function entitlementsFrom(context) {
    return context && context.entitlements && typeof context.entitlements === "object"
      ? context.entitlements
      : {};
  }

  function packageFrom(context) {
    return context && context.package && typeof context.package === "object"
      ? context.package
      : {};
  }

  function familyIdFrom(context) {
    const workspace = workspaceFrom(context);
    return String(workspace.family_id || workspace.familyId || "").trim();
  }

  function projectIdFrom(context) {
    const workspace = workspaceFrom(context);
    return String(workspace.project_id || workspace.projectId || "").trim();
  }

  function packageNameFrom(context) {
    const packageInfo = packageFrom(context);
    return String(
      packageInfo.display_name || packageInfo.name || packageInfo.code || "Active package",
    ).trim();
  }

  function withWorkspace(href, context) {
    try {
      const url = new URL(href, window.location.href);
      const familyId = familyIdFrom(context);
      const projectId = projectIdFrom(context);
      if (familyId) url.searchParams.set("family_id", familyId);
      if (projectId) url.searchParams.set("project_id", projectId);
      return `${url.pathname.split("/").pop() || href}${url.search}${url.hash}`;
    } catch (_error) {
      return href;
    }
  }

  function securityState(record) {
    const scanStatus = normalize(record && record.scan_status);
    if (record && record.quarantined) return "blocked";
    if (["infected", "error", "skipped"].includes(scanStatus)) return "blocked";
    if (!scanStatus || scanStatus === "pending") return "processing";
    if (scanStatus !== "clean") return "unavailable";

    const reviewStatus = normalize(record && record.verification_status);
    if (reviewStatus === "needs_correction") return "needs_correction";
    if (reviewStatus === "rejected") return "rejected";
    if (reviewStatus === "approved") return "approved";
    if (normalize(record && record.category) === "private_media") return "ready";
    return "pending_review";
  }

  function stateLabel(state) {
    const labels = {
      blocked: "Security blocked",
      processing: "Security processing",
      unavailable: "Status unavailable",
      needs_correction: "Needs correction",
      rejected: "Rejected",
      approved: "Approved",
      ready: "Ready",
      pending_review: "Pending review",
      empty: "No files yet",
      not_included: "Not included",
    };
    return labels[state] || "Status unavailable";
  }

  function currentLogicalRecords(records) {
    return (Array.isArray(records) ? records : []).filter(function (record) {
      return record && record.is_current_version !== false;
    });
  }

  function summarize(records) {
    const allRecords = Array.isArray(records) ? records : [];
    const current = currentLogicalRecords(allRecords);
    if (!allRecords.length) {
      return { count: 0, state: "empty", latest: null };
    }

    const states = allRecords.map(securityState);
    let state = "pending_review";
    if (states.includes("blocked")) state = "blocked";
    else if (states.includes("unavailable")) state = "unavailable";
    else if (states.includes("processing")) state = "processing";
    else if (states.includes("needs_correction")) state = "needs_correction";
    else if (states.includes("rejected")) state = "rejected";
    else if (states.includes("pending_review")) state = "pending_review";
    else if (states.includes("approved")) state = "approved";
    else if (states.includes("ready")) state = "ready";

    return {
      count: current.length,
      state,
      latest: allRecords[0] || null,
    };
  }

  function laneCard(lane) {
    const unavailable = lane.unavailable === true;
    const notIncluded = lane.included === false;
    const summary = lane.summary || { count: 0, state: "empty", latest: null };
    const state = unavailable ? "unavailable" : notIncluded ? "not_included" : summary.state;
    const countText = notIncluded
      ? "This upload lane is not part of the active package."
      : unavailable
        ? "Tomb of Light could not confirm the live file inventory for this lane."
        : `${summary.count} current ${summary.count === 1 ? "file" : "files"}`;
    const latestName = summary.latest && summary.latest.original_filename
      ? String(summary.latest.original_filename)
      : "";
    const latestState = summary.latest ? stateLabel(securityState(summary.latest)) : "";
    const latestCopy = latestName
      ? `<p class="card-copy"><strong>Latest:</strong> ${escapeHtml(latestName)} · ${escapeHtml(latestState)}</p>`
      : "";
    const action = !notIncluded
      ? `<a class="btn btn-secondary" href="${escapeHtml(lane.href)}">${escapeHtml(lane.action)}</a>`
      : "";

    return `
      <article class="family-record-card" data-upload-overview-lane="${escapeHtml(lane.key)}">
        <span class="eyebrow">${escapeHtml(lane.eyebrow)}</span>
        <h3>${escapeHtml(lane.title)}</h3>
        <p class="card-copy"><strong data-upload-overview-state>${escapeHtml(stateLabel(state))}</strong></p>
        <p class="card-copy" data-upload-overview-count>${escapeHtml(countText)}</p>
        ${latestCopy}
        <div class="inline-actions" style="margin-top: 1rem">${action}</div>
      </article>
    `;
  }

  function ensureOverviewShell() {
    let section = document.querySelector("[data-upload-overview]");
    if (section) return section;

    const hero = document.querySelector(".portal-upload-hub-hero");
    if (!hero) return null;

    section = document.createElement("section");
    section.className = "page-sections tol-upload-overview-section";
    section.setAttribute("data-upload-overview", "");
    section.innerHTML = `
      <div class="container form-shell">
        <div class="form-panel">
          <span class="eyebrow">Your Uploads</span>
          <h2>Current private file status</h2>
          <p class="card-copy" data-upload-overview-message>
            Loading the authorized upload inventory for this workspace...
          </p>
          <div class="grid-3" data-upload-overview-grid style="margin-top: 1.25rem"></div>
        </div>
      </div>
    `;
    hero.insertAdjacentElement("afterend", section);
    return section;
  }

  function renderUnavailable(message) {
    const section = ensureOverviewShell();
    if (!section) return;
    const messageNode = section.querySelector("[data-upload-overview-message]");
    const grid = section.querySelector("[data-upload-overview-grid]");
    if (messageNode) messageNode.textContent = message;
    if (grid) grid.innerHTML = "";
  }

  async function fetchRecords(endpoint) {
    const payload = await app.apiRequest(endpoint, { method: "GET" });
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload && payload.uploads)) return payload.uploads;
    if (Array.isArray(payload && payload.items)) return payload.items;
    return [];
  }

  async function loadLane(options) {
    if (!options.included) {
      return { ...options, summary: { count: 0, state: "not_included", latest: null } };
    }
    if (!options.endpoint) {
      return { ...options, unavailable: true };
    }
    try {
      const records = await fetchRecords(options.endpoint);
      return { ...options, summary: summarize(records) };
    } catch (_error) {
      return { ...options, unavailable: true };
    }
  }

  async function boot() {
    const section = ensureOverviewShell();
    if (!section) return;

    const token = typeof app.getToken === "function" ? app.getToken() : "";
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    try {
      const user = await app.apiRequest("/auth/me", { method: "GET" });
      if (!user || typeof user !== "object") throw new Error("authenticated_user_unavailable");
      if (typeof app.isInternalRole === "function" && app.isInternalRole(user)) {
        window.location.href = "dashboard.html";
        return;
      }

      const context = await app.apiRequest("/users/me/workspace-context", { method: "GET" });
      if (!context || typeof context !== "object" || normalize(context.status) !== "active") {
        throw new Error("workspace_context_unavailable");
      }

      const entitlements = entitlementsFrom(context);
      const familyId = familyIdFrom(context);
      const projectId = projectIdFrom(context);
      const portraitIncluded = Boolean(entitlements.can_upload_portraits);
      const verificationIncluded = Boolean(entitlements.can_upload_verification_docs);
      const vaultIncluded = VAULT_FLAGS.some(function (flag) {
        return Boolean(entitlements[flag]);
      });

      const portraitEndpoint = portraitIncluded && familyId
        ? `/uploads/family/${encodeURIComponent(familyId)}?category=member_photo`
        : "";
      const verificationEndpoint = verificationIncluded && familyId
        ? `/uploads/family/${encodeURIComponent(familyId)}?category=verification_evidence`
        : "";
      const vaultEndpoint = vaultIncluded && projectId
        ? `/uploads/vault/project/${encodeURIComponent(projectId)}?category=private_media`
        : "";

      const lanes = await Promise.all([
        loadLane({
          key: "portraits",
          eyebrow: "Portraits",
          title: "Portraits & Family Photos",
          included: portraitIncluded,
          endpoint: portraitEndpoint,
          href: withWorkspace("portrait-upload.html", context),
          action: "Manage Portraits",
        }),
        loadLane({
          key: "verification",
          eyebrow: "Verification",
          title: "Verification Records",
          included: verificationIncluded,
          endpoint: verificationEndpoint,
          href: withWorkspace("verification-upload.html", context),
          action: "Manage Records",
        }),
        loadLane({
          key: "vault",
          eyebrow: "Vault",
          title: "Private Vault Files",
          included: vaultIncluded,
          endpoint: vaultEndpoint,
          href: withWorkspace("vault-upload.html", context),
          action: "Open Vault Files",
        }),
      ]);

      const messageNode = section.querySelector("[data-upload-overview-message]");
      const grid = section.querySelector("[data-upload-overview-grid]");
      const hasUnavailable = lanes.some(function (lane) { return lane.unavailable === true; });
      if (messageNode) {
        messageNode.textContent = hasUnavailable
          ? `Live upload status for ${packageNameFrom(context)} loaded with one or more unavailable lanes. No unavailable lane is reported as empty.`
          : `Live upload status for ${packageNameFrom(context)} is shown below. Counts come from your authorized private workspace.`;
      }
      if (grid) grid.innerHTML = lanes.map(laneCard).join("");
    } catch (_error) {
      renderUnavailable(
        "Unable to confirm the live upload inventory for this workspace. No file count or review state has been assumed.",
      );
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
