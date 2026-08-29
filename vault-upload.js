(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};
  if (!app || typeof app.apiRequest !== "function") {
    console.error("vault-upload.js requires app.js/auth.js first.");
    return;
  }

  const ALLOWED_VAULT_TYPES = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/ogg",
  ]);

  const ALLOWED_ASSET_TYPES = new Set([
    "vault_photo",
    "vault_document",
    "private_voice_message",
    "private_video_message",
  ]);
  const MAX_VAULT_FILE_BYTES = 25 * 1024 * 1024;

  let currentFamilyId = "";
  let currentProjectId = "";
  let currentVaultScope = "household";
  let availableVaultScopes = [];
  let currentContext = null;
  let currentGraph = { members: [] };
  let families = [];
  let pendingVaultUploadIdempotencyKey = "";
  const previewObjectUrls = new Map();

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
    } catch (error) {
      return String(value);
    }
  }

  function setStatus(node, message, type) {
    if (!node) return;
    if (typeof app.setStatus === "function") {
      app.setStatus(node, message, type || "info");
      return;
    }
    node.style.display = "block";
    node.textContent = message;
    node.dataset.state = type || "info";
  }

  function clearStatus(node) {
    if (!node) return;
    node.style.display = "none";
    node.textContent = "";
  }

  function syncReleaseTimingFields() {
    const select = document.querySelector("[data-vault-release-state]");
    const field = document.querySelector("[data-vault-reveal-date-field]");
    const input = field?.querySelector('input[name="reveal_at"]');
    const isScheduled = select?.value === "scheduled";
    if (field) field.hidden = !isScheduled;
    if (input) input.required = isScheduled;
  }

  function applyScheduledRevealEntitlement(canSchedule) {
    const option = document.querySelector("[data-vault-scheduled-option]");
    const select = document.querySelector("[data-vault-release-state]");
    if (option) option.disabled = !canSchedule;
    if (!canSchedule && select?.value === "scheduled") select.value = "released";
    syncReleaseTimingFields();
  }

  function isEntitlementError(msg) {
    return (
      msg.includes("can_use_household_vault") ||
      msg.includes("vault") ||
      msg.includes("entitlement") ||
      msg.includes("package") ||
      msg.includes("permission")
    );
  }

  function uploadStatusLabel(upload) {
    if (upload.quarantined) return "quarantined — under security review";
    const scanStatus = String(upload.scan_status || "").toLowerCase();
    if (scanStatus === "infected") return "blocked — unsafe file detected";
    if (scanStatus === "error" || scanStatus === "skipped") {
      return "blocked — security scan incomplete";
    }
    if (upload.deletion_status === "pending") return "deletion pending";
    if (upload.superseded || upload.is_current_version === false) {
      return "previous version";
    }
    const vs = String(upload.verification_status || "").toLowerCase();
    if (vs === "rejected") return "rejected";
    if (vs === "needs_correction") return "needs correction";
    if (vs === "approved" || scanStatus === "clean") return "stored securely";
    if (vs === "pending" || scanStatus === "pending") return "security review pending";
    if (upload.id || upload._id) return "stored securely";
    return "pending review";
  }

  function uploadResponseState(payload) {
    const statusPayload = payload?.upload_status;
    return normalizeValue(
      (statusPayload && typeof statusPayload === "object" ? statusPayload.state : statusPayload) ||
        payload?.upload?.upload_status ||
        payload?.upload?.availability_status ||
        payload?.upload?.scan_status ||
        "processing",
    );
  }

  function getFamilyIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("family_id") || "";
  }

  function setFamilyIdInUrl(familyId) {
    const url = new URL(window.location.href);
    if (familyId) url.searchParams.set("family_id", familyId);
    else url.searchParams.delete("family_id");
    window.history.replaceState({}, "", url.toString());
  }

  function scopeRequiresFamily(scope) {
    return scope === "household" || scope === "linked_family";
  }

  function vaultScopeLabel(scope) {
    return {
      personal: "Personal Vault",
      household: "Household Vault",
      linked_family: "Linked Family Vault",
      organization: "Organization Records Vault",
    }[scope] || "Vault";
  }

  function syncPrivacyOptions() {
    const select = document.querySelector('select[name="privacy_scope"]');
    if (!select) return;
    const household = select.querySelector("[data-vault-household-privacy]");
    const linked = select.querySelector("[data-vault-linked-privacy]");
    if (household) household.hidden = currentVaultScope !== "household";
    if (linked) linked.hidden = currentVaultScope !== "linked_family";
    const selected = select.selectedOptions[0];
    if (selected?.hidden) select.value = "private_to_owner";
  }

  async function configureVaultScope(scope) {
    if (!availableVaultScopes.includes(scope)) return;
    const requestedFamilyId = scopeRequiresFamily(scope) ? getFamilyIdFromUrl() : "";
    currentVaultScope = scope;
    currentFamilyId = "";
    currentGraph = { members: [] };
    syncPrivacyOptions();

    const pageStatus = document.querySelector("[data-vault-page-status]");
    const familySelect = document.querySelector("[data-vault-family-select]");
    const loadFamilyButton = document.querySelector("[data-vault-load-family]");
    const requiresFamily = scopeRequiresFamily(currentVaultScope);

    if (requiresFamily) {
      if (familySelect) familySelect.disabled = false;
      if (loadFamilyButton) loadFamilyButton.disabled = false;
      await loadFamilies();
      if (
        requestedFamilyId &&
        families.some(function (family) {
          return String(family._id || family.id || "") === requestedFamilyId;
        })
      ) {
        currentFamilyId = requestedFamilyId;
        if (familySelect) familySelect.value = requestedFamilyId;
        await loadFamilyGraph(requestedFamilyId);
      }
      if (pageStatus) {
        pageStatus.textContent = currentFamilyId
          ? `${vaultScopeLabel(currentVaultScope)} ready.`
          : `Select a family record for the ${vaultScopeLabel(currentVaultScope)}.`;
      }
      return;
    }

    setFamilyIdInUrl("");
    if (familySelect) {
      familySelect.innerHTML = `<option value="">${escapeHtml(vaultScopeLabel(currentVaultScope))}</option>`;
      familySelect.disabled = true;
    }
    if (loadFamilyButton) loadFamilyButton.disabled = true;
    populateMemberSelects([]);
    if (pageStatus) {
      pageStatus.textContent = `${vaultScopeLabel(currentVaultScope)} ready. Upload a protected file.`;
    }
  }

  function getFamilyIdFromContext(context) {
    return String(
      context?.activeProject?.family_id || context?.activeProject?.familyId || "",
    ).trim();
  }

  function getProjectIdFromContext(context) {
    return String(
      context?.activeProject?._id || context?.activeProject?.id || "",
    ).trim();
  }

  function populateMemberSelects(members) {
    const selects = document.querySelectorAll(
      "[data-vault-member-select], [data-vault-list-member]",
    );
    selects.forEach(function (select) {
      const current = select.value;
      select.innerHTML =
        currentVaultScope === "organization"
          ? '<option value="">Organization-level record</option>'
          : currentVaultScope === "personal"
            ? '<option value="">Personal Vault — no member required</option>'
            : currentVaultScope === "linked_family"
              ? '<option value="">Linked-family level file — member optional</option>'
              : '<option value="">Household-level file — member optional</option>';
      members.forEach(function (member) {
        const id = String(member._id || member.id || "").trim();
        const firstName = String(member.first_name || "").trim();
        const lastName = String(member.last_name || "").trim();
        const display = [firstName, lastName].filter(Boolean).join(" ") || id;
        const option = document.createElement("option");
        option.value = id;
        option.textContent = display;
        select.appendChild(option);
      });
      if (current) select.value = current;
    });
  }

  async function loadFamilyGraph(familyId) {
    const familyStatus = document.querySelector("[data-vault-family-status]");
    const pageStatus = document.querySelector("[data-vault-page-status]");

    if (!familyId) {
      setStatus(familyStatus, "Select a family record first.", "error");
      return;
    }

    try {
      setStatus(familyStatus, "Loading family record...", "info");

      const graph = await app.apiRequest(
        `/families/${encodeURIComponent(familyId)}/graph`,
        { method: "GET" },
      );

      currentGraph = graph || { members: [] };
      const members = Array.isArray(currentGraph.members)
        ? currentGraph.members
        : [];
      populateMemberSelects(members);

      setStatus(
        familyStatus,
        `Family loaded. ${members.length} member(s) available.`,
        "success",
      );

      if (pageStatus) {
        pageStatus.textContent =
          "Vault workspace ready. Select a member and upload a vault file.";
      }
    } catch (error) {
      const msg = error.message || "Unable to load family record.";
      if (isEntitlementError(msg)) {
        setStatus(
          familyStatus,
          "Your active package does not include private household vault access. Contact support if you believe this is an error.",
          "error",
        );
      } else {
        setStatus(familyStatus, msg, "error");
      }
    }
  }

  async function loadFamilies() {
    const familySelect = document.querySelector("[data-vault-family-select]");
    const pageStatus = document.querySelector("[data-vault-page-status]");

    try {
      const payload = await app.apiRequest("/families/", { method: "GET" });
      families = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.families)
          ? payload.families
          : [];

      if (familySelect) {
        familySelect.innerHTML = '<option value="">Select a family record</option>';
        families.forEach(function (family) {
          const id = String(family._id || family.id || "").trim();
          const name = String(family.family_name || family.name || id).trim();
          const option = document.createElement("option");
          option.value = id;
          option.textContent = name;
          familySelect.appendChild(option);
        });
      }

      const urlFamilyId = getFamilyIdFromUrl();
      if (urlFamilyId && familySelect) {
        familySelect.value = urlFamilyId;
      }

      if (pageStatus) {
        pageStatus.textContent =
          "Select a family record and load it to begin uploading vault files.";
      }
    } catch (error) {
      if (pageStatus) {
        pageStatus.textContent =
          "Unable to load family records. Please try refreshing.";
      }
    }
  }

  async function getCurrentContext() {
    if (
      !authPages ||
      typeof authPages.fetchOrders !== "function" ||
      (typeof authPages.getDashboardContextForCurrentPage !== "function" &&
        typeof authPages.getDashboardContext !== "function")
    ) {
      return null;
    }

    const me = await app.apiRequest("/auth/me", { method: "GET" });
    const orders = await authPages.fetchOrders();

    if (typeof authPages.getDashboardContextForCurrentPage === "function") {
      return await authPages.getDashboardContextForCurrentPage(me, orders);
    }

    const hints =
      typeof authPages.getWorkspaceSelectionHints === "function"
        ? authPages.getWorkspaceSelectionHints()
        : undefined;

    return await authPages.getDashboardContext(me, orders, hints);
  }

  async function initPage() {
    const pageStatus = document.querySelector("[data-vault-page-status]");

    try {
      const context = await getCurrentContext();
      currentContext = context;

      const entitlements = context?.resolvedEntitlements || {};
      const vaultCapabilityKeys = [
        "can_use_personal_vault",
        "can_use_household_vault",
        "can_use_linked_household_vault",
        "can_use_organization_records_vault",
      ];
      const hasResolvedVaultAccess = vaultCapabilityKeys.some(function (key) {
        return Object.prototype.hasOwnProperty.call(entitlements, key);
      });
      const canUpload = vaultCapabilityKeys.some(function (key) {
        return Boolean(entitlements[key]);
      });
      currentProjectId = getProjectIdFromContext(context);
      availableVaultScopes = [
        entitlements.can_use_organization_records_vault ? "organization" : "",
        entitlements.can_use_household_vault ? "household" : "",
        entitlements.can_use_linked_household_vault ? "linked_family" : "",
        entitlements.can_use_personal_vault ? "personal" : "",
      ].filter(Boolean);
      currentVaultScope = availableVaultScopes[0] || "personal";
      applyScheduledRevealEntitlement(
        Boolean(
          entitlements.can_use_scheduled_reveal ||
            entitlements.can_use_future_message_vault,
        ),
      );

      if (!canUpload) {
        if (pageStatus) {
          setStatus(
            pageStatus,
            hasResolvedVaultAccess
              ? "Your active package does not include a private Vault scope."
              : "Unable to verify private Vault access. Please return to Dashboard or try again shortly.",
            hasResolvedVaultAccess ? "warning" : "info",
          );
        }
        const form = document.querySelector("[data-vault-upload-form]");
        if (form) {
          form.querySelectorAll("input, select, button[type=submit]").forEach(
            function (el) { el.disabled = true; },
          );
        }
        const loadBtn = document.querySelector("[data-vault-load-family]");
        if (loadBtn) loadBtn.disabled = true;
        return;
      }

      const scopeSelect = document.querySelector("[data-vault-scope-select]");
      if (scopeSelect) {
        scopeSelect.innerHTML = availableVaultScopes
          .map(function (scope) {
            return `<option value="${escapeHtml(scope)}">${escapeHtml(vaultScopeLabel(scope))}</option>`;
          })
          .join("");
        scopeSelect.value = currentVaultScope;
      }
      await configureVaultScope(currentVaultScope);
    } catch (error) {
      if (pageStatus) {
        setStatus(
          pageStatus,
          "Unable to load your workspace. Please return to Dashboard or try again shortly.",
          "error",
        );
      }
    }
  }

  function validateVaultFile(file) {
    if (!file) return "Please select a file to upload.";
    const contentType = normalizeValue(file.type);
    if (!ALLOWED_VAULT_TYPES.has(contentType)) {
      return "Unsupported file type. Allowed: MP3, M4A, WAV, WebM, OGG, MP4, MOV.";
    }
    if (Number(file.size || 0) > MAX_VAULT_FILE_BYTES) {
      return "Vault files must be 25MB or smaller.";
    }
    return null;
  }

  function validateVaultAssetFile(assetType, file) {
    const generalError = validateVaultFile(file);
    if (generalError) return generalError;
    const contentType = normalizeValue(file.type);
    if (assetType === "vault_photo" && !contentType.startsWith("image/")) {
      return "Protected photos must be JPG, PNG, or WEBP images.";
    }
    if (
      assetType === "vault_document" &&
      contentType !== "application/pdf" &&
      !contentType.startsWith("image/")
    ) {
      return "Protected documents must be PDF, JPG, PNG, or WEBP files.";
    }
    if (assetType === "private_voice_message" && !contentType.startsWith("audio/")) {
      return "Voice messages must use one of the supported audio formats.";
    }
    if (assetType === "private_video_message" && !contentType.startsWith("video/")) {
      return "Video messages must use one of the supported video formats.";
    }
    return null;
  }

  function uploadDownloadUrl(uploadId) {
    const base =
      typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const url = new URL(
      `${base}/uploads/${encodeURIComponent(uploadId || "")}/download`,
      window.location.origin,
    );
    if (currentVaultScope === "linked_family" && currentProjectId) {
      url.searchParams.set("viewer_project_id", currentProjectId);
    }
    return url.toString();
  }

  function uploadPreviewUrl(uploadId) {
    const base =
      typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const url = new URL(
      `${base}/uploads/${encodeURIComponent(uploadId || "")}/preview`,
      window.location.origin,
    );
    if (currentVaultScope === "linked_family" && currentProjectId) {
      url.searchParams.set("viewer_project_id", currentProjectId);
    }
    return url.toString();
  }

  async function fetchProtectedUpload(uploadId, preview) {
    const token = app.getToken ? app.getToken() : "";
    const response = await fetch(
      preview ? uploadPreviewUrl(uploadId) : uploadDownloadUrl(uploadId),
      {
      method: "GET",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
      cache: "no-store",
      },
    );
    if (!response.ok) {
      let message = "Unable to open this protected Vault file.";
      try {
        const payload = await response.json();
        message = payload.detail || payload.message || message;
      } catch (error) {
        // Keep the safe customer-facing fallback for non-JSON storage errors.
      }
      throw new Error(message);
    }
    return response.blob();
  }

  function releasePreviewUrl(key) {
    const existing = previewObjectUrls.get(key);
    if (existing) {
      window.URL.revokeObjectURL(existing);
      previewObjectUrls.delete(key);
    }
  }

  function clearPreviewUrls() {
    previewObjectUrls.forEach(function (url) {
      window.URL.revokeObjectURL(url);
    });
    previewObjectUrls.clear();
  }

  async function loadProtectedImagePreviews() {
    const nodes = document.querySelectorAll("[data-vault-secure-image-id]");
    await Promise.all(
      Array.from(nodes).map(async function (node) {
        const uploadId = node.getAttribute("data-vault-secure-image-id") || "";
        if (!uploadId) return;
        try {
          const blob = await fetchProtectedUpload(uploadId, true);
          releasePreviewUrl(`inline:${uploadId}`);
          const objectUrl = window.URL.createObjectURL(blob);
          previewObjectUrls.set(`inline:${uploadId}`, objectUrl);
          node.src = objectUrl;
          node.hidden = false;
          const loading = node.parentElement?.querySelector(
            "[data-vault-preview-loading]",
          );
          if (loading) loading.remove();
        } catch (error) {
          const container = node.parentElement;
          node.remove();
          if (container) {
            container.textContent = "Preview unavailable. Use Download or try again.";
            container.dataset.state = "error";
          }
        }
      }),
    );
  }

  function ensurePreviewDialog() {
    let dialog = document.querySelector("[data-vault-preview-dialog]");
    if (dialog) return dialog;

    dialog = document.createElement("dialog");
    dialog.setAttribute("data-vault-preview-dialog", "");
    dialog.setAttribute("aria-labelledby", "vault-preview-title");
    dialog.style.width = "min(920px, calc(100vw - 2rem))";
    dialog.style.maxHeight = "90vh";
    dialog.style.padding = "1.25rem";
    dialog.style.borderRadius = "18px";
    dialog.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:1rem;">
        <h2 id="vault-preview-title" style="margin:0" data-vault-preview-title>Protected file</h2>
        <button class="btn btn-secondary" type="button" data-vault-preview-close>Close</button>
      </div>
      <div data-vault-preview-content style="min-height:180px"></div>
    `;
    dialog.addEventListener("close", function () {
      releasePreviewUrl("dialog");
      const content = dialog.querySelector("[data-vault-preview-content]");
      if (content) content.innerHTML = "";
    });
    dialog.addEventListener("click", function (event) {
      if (event.target.closest("[data-vault-preview-close]")) dialog.close();
    });
    document.body.appendChild(dialog);
    return dialog;
  }

  async function previewUpload(uploadId, filename, contentType) {
    const statusNode = document.querySelector("[data-vault-family-status]");
    try {
      setStatus(statusNode, "Opening protected preview...", "info");
      const blob = await fetchProtectedUpload(uploadId, true);
      releasePreviewUrl("dialog");
      const objectUrl = window.URL.createObjectURL(blob);
      previewObjectUrls.set("dialog", objectUrl);
      const dialog = ensurePreviewDialog();
      const title = dialog.querySelector("[data-vault-preview-title]");
      const content = dialog.querySelector("[data-vault-preview-content]");
      if (title) title.textContent = filename || "Protected Vault file";
      if (!content) return;
      content.innerHTML = "";

      const normalizedType = String(contentType || blob.type || "").toLowerCase();
      let media;
      if (normalizedType.startsWith("image/")) {
        media = document.createElement("img");
        media.alt = filename || "Protected Vault image";
        media.style.cssText = "display:block;max-width:100%;max-height:70vh;margin:auto;border-radius:12px;object-fit:contain;";
      } else if (normalizedType === "application/pdf") {
        media = document.createElement("iframe");
        media.title = filename || "Protected PDF document";
        media.setAttribute("sandbox", "");
        media.style.cssText = "display:block;width:100%;height:70vh;border:0;border-radius:12px;";
      } else if (normalizedType.startsWith("audio/")) {
        media = document.createElement("audio");
        media.controls = true;
        media.style.width = "100%";
      } else if (normalizedType.startsWith("video/")) {
        media = document.createElement("video");
        media.controls = true;
        media.playsInline = true;
        media.style.cssText = "display:block;max-width:100%;max-height:70vh;margin:auto;border-radius:12px;";
      } else {
        throw new Error("This file type can be downloaded but cannot be previewed safely.");
      }
      media.src = objectUrl;
      content.appendChild(media);
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      setStatus(statusNode, "Protected preview opened.", "success");
    } catch (error) {
      releasePreviewUrl("dialog");
      setStatus(statusNode, error.message || "Preview failed.", "error");
    }
  }

  function canPreviewUpload(upload) {
    const contentType = String(upload.content_type || "").toLowerCase();
    return (
      contentType.startsWith("image/") ||
      contentType.startsWith("audio/") ||
      contentType.startsWith("video/") ||
      contentType === "application/pdf"
    );
  }

  function privacyOptionsMarkup(privacy, vaultScope) {
    const options = [
      ["private_to_owner", "Private to me only"],
      ["private_to_owner_and_co_owner", "Me and co-owner"],
    ];
    if (vaultScope === "household") {
      options.push(["household_private", "Household members"]);
    }
    if (vaultScope === "linked_family") {
      options.push(["linked_family_shared", "Approved linked family"]);
    }
    return options
      .map(function (option) {
        return `<option value="${option[0]}" ${privacy === option[0] ? "selected" : ""}>${option[1]}</option>`;
      })
      .join("");
  }

  function renderUploads(uploads) {
    const listNode = document.querySelector("[data-vault-uploads-list]");
    const emptyNode = document.querySelector("[data-vault-uploads-empty]");
    if (!listNode) return;

    if (!Array.isArray(uploads) || !uploads.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    clearPreviewUrls();

    listNode.innerHTML = uploads
      .map(function (upload, index) {
        const uploadId = String(upload.id || upload._id || "");
        const permissions = upload.permissions || {};
        const canPreview = permissions.can_preview === true && canPreviewUpload(upload);
        const canDownload = permissions.can_download === true;
        const canReplace = permissions.can_replace === true && upload.is_current_version !== false;
        const canDelete = permissions.can_delete === true;
        const canChangePrivacy = permissions.can_change_privacy === true;
        const contentType = String(upload.content_type || "");
        const isImage = contentType.toLowerCase().startsWith("image/");
        const version = Number(upload.version || 1);
        const preview = isImage && permissions.can_preview === true
          ? `<div class="helper" style="display:block;margin:0 0 1rem;min-height:120px;" data-vault-preview-container>
               <span data-vault-preview-loading>Loading protected photo preview...</span>
               <img
                 hidden
                 data-vault-secure-image-id="${escapeHtml(uploadId)}"
                 alt="${escapeHtml(upload.original_filename || "Protected Vault photo")}"
                 style="display:block;width:100%;max-height:260px;object-fit:contain;border-radius:12px;"
               />
             </div>`
          : "";
        const privacy = String(
          upload.privacy_scope || upload.visibility_scope || "private_to_owner",
        );
        const uploadVaultScope = String(upload.vault_scope || currentVaultScope);

        return `
          <div class="family-record-card" data-vault-upload-card="${escapeHtml(uploadId)}">
            <div class="card-number">${index + 1}</div>
            ${preview}
            <h3>${escapeHtml(upload.original_filename || "Vault File")}</h3>
            <p class="card-copy"><strong>Status:</strong> ${escapeHtml(uploadStatusLabel(upload))}</p>
            <p class="card-copy"><strong>File Type:</strong> ${escapeHtml(upload.asset_type || upload.category || "—")}</p>
            <p class="card-copy"><strong>Privacy:</strong> ${escapeHtml(privacy)}</p>
            <p class="card-copy"><strong>Version:</strong> ${escapeHtml(version)}${upload.is_current_version === false ? " — previous" : " — current"}</p>
            <p class="card-copy"><strong>Release:</strong> ${escapeHtml(upload.release_state || "available to permitted viewers")}</p>
            <p class="card-copy"><strong>Content Type:</strong> ${escapeHtml(upload.content_type || "—")}</p>
            <p class="card-copy"><strong>Size:</strong> ${escapeHtml(upload.size_bytes ?? "—")}</p>
            <p class="card-copy"><strong>Uploaded By:</strong> ${escapeHtml(upload.uploaded_by || "—")}</p>
            <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(upload.created_at))}</p>

            ${canChangePrivacy ? `
              <label style="display:block;margin-top:0.85rem;">
                File privacy
                <select data-vault-privacy-upload-id="${escapeHtml(uploadId)}">
                  ${privacyOptionsMarkup(privacy, uploadVaultScope)}
                </select>
              </label>
            ` : ""}

            <div class="inline-actions" style="margin-top: 1rem">
              ${canPreview ? `<button
                class="btn btn-secondary"
                type="button"
                data-preview-upload-id="${escapeHtml(uploadId)}"
                data-preview-upload-name="${escapeHtml(upload.original_filename || "Protected Vault file")}"
                data-preview-upload-type="${escapeHtml(contentType)}"
              >
                Preview
              </button>` : ""}
              ${canDownload ? `<button
                class="btn btn-secondary"
                type="button"
                data-download-upload-id="${escapeHtml(uploadId)}"
                data-download-upload-name="${escapeHtml(upload.original_filename || "download")}"
              >
                Download
              </button>` : ""}
              ${canReplace ? `<button
                class="btn btn-primary"
                type="button"
                data-replace-upload-id="${escapeHtml(uploadId)}"
                data-replace-upload-type="${escapeHtml(contentType)}"
              >
                Replace with New Version
              </button>` : ""}
              ${version > 1 || upload.root_upload_id ? `<button
                class="btn btn-secondary"
                type="button"
                data-version-history-upload-id="${escapeHtml(uploadId)}"
              >
                Version History
              </button>` : ""}
              ${canChangePrivacy ? `<button
                class="btn btn-secondary"
                type="button"
                data-save-vault-privacy-id="${escapeHtml(uploadId)}"
              >
                Save Privacy
              </button>` : ""}
              ${canDelete ? `<button
                class="btn btn-secondary"
                type="button"
                data-delete-upload-id="${escapeHtml(uploadId)}"
                data-delete-upload-name="${escapeHtml(upload.original_filename || "this Vault file")}"
              >
                Delete
              </button>` : ""}
            </div>
            <input
              hidden
              type="file"
              data-replacement-file-for="${escapeHtml(uploadId)}"
              accept=".jpg,.jpeg,.png,.webp,.pdf,.mp3,.m4a,.wav,.webm,.ogg,.mp4,.mov,.ogv,image/jpeg,image/png,image/webp,application/pdf,audio/mpeg,audio/mp4,audio/wav,audio/webm,audio/ogg,audio/x-wav,video/mp4,video/webm,video/quicktime,video/ogg"
            />
          </div>
        `;
      })
      .join("");

    loadProtectedImagePreviews();
  }

  async function loadUploads() {
    const memberSelect = document.querySelector("[data-vault-list-member]");
    const familyStatus = document.querySelector("[data-vault-family-status]");

    const memberId = String(memberSelect ? memberSelect.value : "").trim();
    if (!currentFamilyId && !currentProjectId) {
      setStatus(
        familyStatus,
        "Load an active Vault workspace before loading files.",
        "error",
      );
      return;
    }

    try {
      setStatus(familyStatus, "Loading vault files...", "info");

      const endpoint = currentFamilyId
        ? `/uploads/vault/family/${encodeURIComponent(currentFamilyId)}`
        : `/uploads/vault/project/${encodeURIComponent(currentProjectId)}`;
      const query = new URLSearchParams({ vault_scope: currentVaultScope });
      if (currentVaultScope === "linked_family" && currentFamilyId) {
        query.set("include_linked_families", "true");
      }
      const payload = await app.apiRequest(`${endpoint}?${query.toString()}`, { method: "GET" });
      const records = Array.isArray(payload.items)
        ? payload.items
        : Array.isArray(payload.uploads)
          ? payload.uploads
          : [];
      renderUploads(
        memberId
          ? records.filter(function (upload) {
              return String(upload.member_id || "") === memberId;
            })
          : records,
      );
      setStatus(familyStatus, "Vault files loaded successfully.", "success");
    } catch (error) {
      setStatus(
        familyStatus,
        error.message || "Unable to load vault files.",
        "error",
      );
    }
  }

  function createIdempotencyKey(prefix) {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return `${prefix}-${window.crypto.randomUUID()}`;
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function replaceUpload(uploadId, fileInput) {
    const statusNode = document.querySelector("[data-vault-family-status]");
    const file = fileInput?.files?.[0];
    if (!file) return;
    const fileError = validateVaultFile(file);
    if (fileError) {
      setStatus(statusNode, fileError, "error");
      fileInput.value = "";
      return;
    }
    const card = fileInput.closest("[data-vault-upload-card]");
    const privacySelect = card?.querySelector("[data-vault-privacy-upload-id]");
    const body = new FormData();
    body.append("file", file, file.name);
    body.append("consent_attested", "true");
    body.append("authority_attested", "true");
    if (privacySelect?.value) body.append("privacy_scope", privacySelect.value);
    const fileSignature = [
      file.name,
      file.size,
      file.type,
      file.lastModified,
      privacySelect?.value || "",
    ].join(":");
    if (fileInput.dataset.idempotencyFileSignature !== fileSignature) {
      fileInput.dataset.idempotencyFileSignature = fileSignature;
      fileInput.dataset.idempotencyKey = createIdempotencyKey("vault-replace");
    }

    try {
      setStatus(statusNode, "Uploading the replacement as a new protected version...", "info");
      const payload = await app.apiRequest(
        `/uploads/${encodeURIComponent(uploadId)}/replace`,
        {
          method: "POST",
          headers: { "Idempotency-Key": fileInput.dataset.idempotencyKey },
          body,
        },
      );
      const version = payload?.replacement?.version || payload?.upload?.version;
      setStatus(
        statusNode,
        version
          ? `Replacement uploaded successfully as version ${version}.`
          : "Replacement uploaded successfully as a new version.",
        "success",
      );
      delete fileInput.dataset.idempotencyKey;
      delete fileInput.dataset.idempotencyFileSignature;
      fileInput.value = "";
      await loadUploads();
    } catch (error) {
      setStatus(statusNode, error.message || "Unable to replace this Vault file.", "error");
    }
  }

  async function deleteUpload(uploadId, filename) {
    const statusNode = document.querySelector("[data-vault-family-status]");
    const confirmed = window.confirm(
      `Permanently delete ${filename || "this Vault file"}? This removes the selected version from private storage and cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      setStatus(statusNode, "Deleting the protected Vault file...", "info");
      await app.apiRequest(`/uploads/${encodeURIComponent(uploadId)}`, {
        method: "DELETE",
      });
      setStatus(statusNode, "Vault file deleted and removed from the list.", "success");
      await loadUploads();
    } catch (error) {
      setStatus(statusNode, error.message || "Unable to delete this Vault file.", "error");
    }
  }

  async function saveUploadPrivacy(uploadId, card) {
    const statusNode = document.querySelector("[data-vault-family-status]");
    const select = card?.querySelector("[data-vault-privacy-upload-id]");
    if (!select?.value) return;
    const privacy = select.value;
    try {
      setStatus(statusNode, "Saving file privacy...", "info");
      await app.apiRequest(`/uploads/${encodeURIComponent(uploadId)}/privacy`, {
        method: "PATCH",
        body: JSON.stringify({
          privacy_scope: privacy,
          visibility_scope: privacy,
          privacy_classification: privacy,
          share_with_linked_families: privacy === "linked_family_shared",
        }),
      });
      setStatus(statusNode, "File privacy updated.", "success");
      await loadUploads();
    } catch (error) {
      setStatus(statusNode, error.message || "Unable to update file privacy.", "error");
    }
  }

  async function showVersionHistory(uploadId) {
    const statusNode = document.querySelector("[data-vault-family-status]");
    try {
      setStatus(statusNode, "Loading version history...", "info");
      const query = new URLSearchParams();
      if (currentVaultScope === "linked_family" && currentProjectId) {
        query.set("viewer_project_id", currentProjectId);
      }
      const payload = await app.apiRequest(
        `/uploads/${encodeURIComponent(uploadId)}/versions${query.size ? `?${query.toString()}` : ""}`,
        { method: "GET" },
      );
      const versions = Array.isArray(payload.versions) ? payload.versions : [];
      const dialog = ensurePreviewDialog();
      const title = dialog.querySelector("[data-vault-preview-title]");
      const content = dialog.querySelector("[data-vault-preview-content]");
      if (title) title.textContent = "Vault File Version History";
      if (content) {
        content.innerHTML = versions.length
          ? versions
              .map(function (version) {
                return `<article class="family-record-card" style="margin-bottom:0.75rem;">
                  <strong>Version ${escapeHtml(version.version || 1)}${version.is_current_version ? " — current" : ""}</strong>
                  <p class="card-copy">${escapeHtml(version.original_filename || "Protected Vault file")}</p>
                  <p class="card-copy">Status: ${escapeHtml(uploadStatusLabel(version))}</p>
                  <p class="card-copy">Created: ${escapeHtml(formatDate(version.created_at))}</p>
                </article>`;
              })
              .join("")
          : '<p class="card-copy">No version history is available for this file.</p>';
      }
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      setStatus(statusNode, "Version history loaded.", "success");
    } catch (error) {
      setStatus(statusNode, error.message || "Unable to load version history.", "error");
    }
  }

  function setupVaultFileHandlers() {
    document.addEventListener("click", async function (event) {
      const previewButton = event.target.closest("[data-preview-upload-id]");
      if (previewButton) {
        await previewUpload(
          previewButton.getAttribute("data-preview-upload-id") || "",
          previewButton.getAttribute("data-preview-upload-name") || "",
          previewButton.getAttribute("data-preview-upload-type") || "",
        );
        return;
      }

      const replaceButton = event.target.closest("[data-replace-upload-id]");
      if (replaceButton) {
        const card = replaceButton.closest("[data-vault-upload-card]");
        card?.querySelector("[data-replacement-file-for]")?.click();
        return;
      }

      const deleteButton = event.target.closest("[data-delete-upload-id]");
      if (deleteButton) {
        await deleteUpload(
          deleteButton.getAttribute("data-delete-upload-id") || "",
          deleteButton.getAttribute("data-delete-upload-name") || "",
        );
        return;
      }

      const privacyButton = event.target.closest("[data-save-vault-privacy-id]");
      if (privacyButton) {
        await saveUploadPrivacy(
          privacyButton.getAttribute("data-save-vault-privacy-id") || "",
          privacyButton.closest("[data-vault-upload-card]"),
        );
        return;
      }

      const versionsButton = event.target.closest("[data-version-history-upload-id]");
      if (versionsButton) {
        await showVersionHistory(
          versionsButton.getAttribute("data-version-history-upload-id") || "",
        );
        return;
      }

      const btn = event.target.closest("[data-download-upload-id]");
      if (!btn) return;

      const uploadId = btn.getAttribute("data-download-upload-id");
      const filename = btn.getAttribute("data-download-upload-name") || "download";
      if (!uploadId) return;

      try {
        const blob = await fetchProtectedUpload(uploadId);
        const objectUrl = window.URL.createObjectURL(blob);
        const downloadLink = document.createElement("a");
        downloadLink.href = objectUrl;
        downloadLink.download = filename;
        downloadLink.rel = "noopener noreferrer";
        document.body.appendChild(downloadLink);
        downloadLink.click();
        downloadLink.remove();
        window.setTimeout(function () {
          window.URL.revokeObjectURL(objectUrl);
        }, 1000);
      } catch (error) {
        const statusNode = document.querySelector("[data-vault-family-status]");
        if (statusNode) {
          setStatus(
            statusNode,
            error.message || "Vault file download failed.",
            "error",
          );
        }
      }
    });

    document.addEventListener("change", async function (event) {
      const input = event.target.closest("[data-replacement-file-for]");
      if (!input) return;
      await replaceUpload(
        input.getAttribute("data-replacement-file-for") || "",
        input,
      );
    });

    window.addEventListener("pagehide", clearPreviewUrls);
  }

  function setupPage() {
    const page = document.querySelector("[data-vault-upload-page]");
    if (!page) return;

    const familySelect = document.querySelector("[data-vault-family-select]");
    const scopeSelect = document.querySelector("[data-vault-scope-select]");
    const loadFamilyBtn = document.querySelector("[data-vault-load-family]");
    const uploadForm = document.querySelector("[data-vault-upload-form]");
    const uploadStatus = document.querySelector("[data-vault-upload-status]");
    const loadUploadsBtn = document.querySelector("[data-vault-load-uploads]");
    const releaseStateSelect = document.querySelector("[data-vault-release-state]");

    if (releaseStateSelect) {
      releaseStateSelect.addEventListener("change", syncReleaseTimingFields);
      syncReleaseTimingFields();
    }

    if (scopeSelect) {
      scopeSelect.addEventListener("change", async function () {
        await configureVaultScope(String(scopeSelect.value || ""));
        renderUploads([]);
      });
    }

    if (loadFamilyBtn) {
      loadFamilyBtn.addEventListener("click", async function () {
        const familyId = String(
          familySelect ? familySelect.value : "",
        ).trim();
        if (!familyId) {
          const familyStatus = document.querySelector(
            "[data-vault-family-status]",
          );
          setStatus(familyStatus, "Select a family record first.", "error");
          return;
        }
        currentFamilyId = familyId;
        setFamilyIdInUrl(familyId);
        await loadFamilyGraph(familyId);
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener("change", function () {
        pendingVaultUploadIdempotencyKey = "";
      });
      uploadForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        clearStatus(uploadStatus);

        const memberSelect = uploadForm.querySelector(
          "[data-vault-member-select]",
        );
        const memberId = String(
          memberSelect ? memberSelect.value : "",
        ).trim();
        const assetTypeSelect = uploadForm.querySelector(
          "select[name=asset_type]",
        );
        const assetType = String(
          assetTypeSelect ? assetTypeSelect.value : "",
        ).trim();
        const privacyScopeSelect = uploadForm.querySelector(
          "select[name=privacy_scope]",
        );
        const privacyScope = String(
          privacyScopeSelect ? privacyScopeSelect.value : "private_to_owner",
        ).trim();
        const fileInput = uploadForm.querySelector("input[name=vault_file]");
        const file = fileInput ? fileInput.files[0] : null;
        const releaseState = String(
          uploadForm.elements.release_state?.value || "released",
        ).trim();
        const revealAtValue = String(
          uploadForm.elements.reveal_at?.value || "",
        ).trim();

        const checkboxes = uploadForm.querySelectorAll(
          "input[type=checkbox][required]",
        );
        const allChecked = Array.from(checkboxes).every(
          function (cb) { return cb.checked; },
        );

        if (scopeRequiresFamily(currentVaultScope) && !currentFamilyId) {
          setStatus(uploadStatus, "Select and load a family record first.", "error");
          return;
        }
        if (!assetType) {
          setStatus(uploadStatus, "Select a file type.", "error");
          return;
        }
        if (!ALLOWED_ASSET_TYPES.has(assetType)) {
          setStatus(uploadStatus, "Invalid file type selected.", "error");
          return;
        }
        if (!file) {
          setStatus(uploadStatus, "Select a file to upload.", "error");
          return;
        }
        const fileError = validateVaultAssetFile(assetType, file);
        if (fileError) {
          setStatus(uploadStatus, fileError, "error");
          return;
        }
        if (releaseState === "scheduled") {
          const revealDate = revealAtValue ? new Date(revealAtValue) : null;
          if (!revealDate || Number.isNaN(revealDate.getTime())) {
            setStatus(uploadStatus, "Choose a valid reveal date and time.", "error");
            return;
          }
          if (revealDate.getTime() <= Date.now()) {
            setStatus(uploadStatus, "The reveal date must be in the future.", "error");
            return;
          }
        }
        if (!allChecked) {
          setStatus(
            uploadStatus,
            "Please confirm both acknowledgements before uploading.",
            "error",
          );
          return;
        }

        const submitBtn = uploadForm.querySelector("[data-vault-upload-submit]");
        if (submitBtn) submitBtn.disabled = true;

        try {
          setStatus(uploadStatus, "Uploading vault file...", "info");

          const formData = new FormData();
          formData.append("project_id", currentProjectId);
          formData.append("vault_scope", currentVaultScope);
          if (currentFamilyId) formData.append("family_id", currentFamilyId);
          if (memberId) formData.append("member_id", memberId);
          formData.append("asset_type", assetType);
          formData.append("privacy_scope", privacyScope);
          formData.append("release_state", releaseState);
          if (releaseState === "scheduled") {
            formData.append("reveal_at", new Date(revealAtValue).toISOString());
          }
          formData.append("authority_attested", "true");
          formData.append("consent_attested", "true");
          formData.append("file", file, file.name);

          pendingVaultUploadIdempotencyKey =
            pendingVaultUploadIdempotencyKey || createIdempotencyKey("vault-upload");
          const payload = await app.apiRequest("/uploads/private-media", {
            method: "POST",
            headers: { "Idempotency-Key": pendingVaultUploadIdempotencyKey },
            body: formData,
          });
          const responseState = uploadResponseState(payload);
          if (["blocked", "quarantined", "unavailable", "infected", "error"].includes(responseState)) {
            setStatus(
              uploadStatus,
              "The file was received but is unavailable because its security or storage checks did not pass. No one can open it.",
              "error",
            );
          } else {
            setStatus(
              uploadStatus,
              ["available", "ready", "clean"].includes(responseState)
                ? "Vault file stored securely and is now available to permitted viewers."
                : "Vault file received securely and is processing through security review.",
              "success",
            );
          }
          pendingVaultUploadIdempotencyKey = "";
          uploadForm.reset();
          populateMemberSelects(
            Array.isArray(currentGraph.members) ? currentGraph.members : [],
          );
          const listMember = document.querySelector("[data-vault-list-member]");
          if (listMember) listMember.value = memberId;
          await loadUploads();
        } catch (error) {
          const msg = error.message || "Upload failed. Please try again.";
          if (isEntitlementError(msg)) {
            setStatus(
              uploadStatus,
              "Your active package does not allow vault file uploads. Contact support or upgrade your package.",
              "error",
            );
          } else if (msg.includes("asset type")) {
            setStatus(
              uploadStatus,
              "Your package does not permit this vault file type. Check your entitlements.",
              "error",
            );
          } else {
            setStatus(uploadStatus, msg, "error");
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    if (loadUploadsBtn) {
      loadUploadsBtn.addEventListener("click", loadUploads);
    }

    setupVaultFileHandlers();
    initPage();

    if (authPages && typeof authPages.setupLogout === "function") {
      authPages.setupLogout();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupPage);
  } else {
    setupPage();
  }
})();
