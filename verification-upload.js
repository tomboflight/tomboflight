(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};
  if (!app || typeof app.apiRequest !== "function") {
    console.error("verification-upload.js requires app.js/auth.js first.");
    return;
  }

  const ALLOWED_PHOTO_TYPES = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
  ]);

  const ALLOWED_EVIDENCE_TYPES = new Set([
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
  ]);

  let currentFamilyId = "";
  let currentContext = null;
  let currentGraph = { members: [] };
  let families = [];

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

    node.style.display = "block";
    node.textContent = message;

    if (type === "error") {
      node.style.color = "#ffb3b3";
    } else if (type === "success") {
      node.style.color = "#cfe8cf";
    } else {
      node.style.color = "#d6e6ff";
    }
  }

  function clearStatus(node) {
    if (!node) return;
    node.style.display = "none";
    node.textContent = "";
  }

  function getFamilyIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("family_id") || "";
  }

  function setFamilyIdInUrl(familyId) {
    if (!familyId) return;
    const url = new URL(window.location.href);
    url.searchParams.set("family_id", familyId);
    window.history.replaceState({}, "", url.toString());
  }

  function getFamilyIdFromContext(context) {
    return String(
      context?.activeProject?.family_id || context?.activeProject?.familyId || "",
    ).trim();
  }

  function getProjectIdFromContext(context) {
    return String(
      context?.activeProject?.project_id ||
        context?.activeProject?.projectId ||
        context?.activeProject?.id ||
        context?.activeProject?._id ||
        context?.currentWorkspace?.projectId ||
        "",
    ).trim();
  }

  function withWorkspaceHref(href, context, familyIdOverride) {
    if (!href) return href;

    const familyId = String(
      familyIdOverride || getFamilyIdFromUrl() || getFamilyIdFromContext(context) || "",
    ).trim();
    const projectId = getProjectIdFromContext(context);

    if (!familyId && !projectId) {
      return href;
    }

    try {
      const url = new URL(href, window.location.href);
      if (familyId) {
        url.searchParams.set("family_id", familyId);
      }
      if (projectId) {
        url.searchParams.set("project_id", projectId);
      }
      return `${url.pathname.split("/").pop() || href}${url.search}`;
    } catch (error) {
      return href;
    }
  }

  function updateNav(context, familyIdOverride) {
    [
      "intake-review.html",
      "verification-upload.html",
      "link-keys.html",
      "tree-view.html",
      "lineage-certificate.html",
    ].forEach(function (href) {
      document.querySelectorAll(`.site-nav a[href^="${href}"]`).forEach(function (node) {
        node.setAttribute("href", withWorkspaceHref(href, context, familyIdOverride));
      });
    });
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

  function getPreferredFamilyId(context) {
    return String(getFamilyIdFromUrl() || getFamilyIdFromContext(context) || "").trim();
  }

  async function ensureWorkspaceFamilyId(context) {
    const existingFamilyId = getPreferredFamilyId(context);
    if (existingFamilyId) {
      return existingFamilyId;
    }

    const projectId = getProjectIdFromContext(context);
    const lane = normalizeValue(
      context?.packageLane || context?.activeProject?.project_lane,
    );

    if (!projectId || !lane) {
      return existingFamilyId;
    }

    try {
      const manifest = await app.apiRequest(
        `/viewer/manifest?project_id=${encodeURIComponent(projectId)}`,
        { method: "GET" },
      );

      const resolvedFamilyId = String(
        manifest?.family?.id || manifest?.project?.family_id || "",
      ).trim();

      if (!resolvedFamilyId) {
        return existingFamilyId;
      }

      if (context?.activeProject) {
        context.activeProject.family_id = resolvedFamilyId;
      }

      if (context?.currentWorkspace?.activeProject) {
        context.currentWorkspace.activeProject.family_id = resolvedFamilyId;
      }

      setFamilyIdInUrl(resolvedFamilyId);
      return resolvedFamilyId;
    } catch (error) {
      console.warn("Unable to resolve workspace family via viewer manifest:", error);
      return existingFamilyId;
    }
  }

  function getDisplayName(member) {
    const full = String(member.display_name || "").trim();
    if (full) return full;

    const joined =
      `${member.first_name || ""} ${member.last_name || ""}`.trim();
    return joined || "Unknown Member";
  }

  function sortMembers(members) {
    return [...members].sort(function (a, b) {
      const genA = Number.isFinite(Number(a.generation))
        ? Number(a.generation)
        : 999;
      const genB = Number.isFinite(Number(b.generation))
        ? Number(b.generation)
        : 999;
      if (genA !== genB) return genA - genB;
      return getDisplayName(a).localeCompare(getDisplayName(b));
    });
  }

  function setSelectOptions(selectNode, members, placeholder) {
    if (!selectNode) return;

    const currentValue = String(selectNode.value || "").trim();
    const options = sortMembers(members || [])
      .map(function (member) {
        return `<option value="${escapeHtml(member.id)}">${escapeHtml(getDisplayName(member))} — Gen ${escapeHtml(member.generation ?? "—")}</option>`;
      })
      .join("");

    selectNode.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${options}`;

    if (
      currentValue &&
      (members || []).some(function (member) {
        return String(member.id) === currentValue;
      })
    ) {
      selectNode.value = currentValue;
    }
  }

  function populateMemberSelects() {
    const members = Array.isArray(currentGraph.members)
      ? currentGraph.members
      : [];

    setSelectOptions(
      document.querySelector("[data-verification-member-select]"),
      members,
      "Select member",
    );
    setSelectOptions(
      document.querySelector("[data-verification-photo-member]"),
      members,
      "Select member",
    );
    setSelectOptions(
      document.querySelector("[data-verification-list-member]"),
      members,
      "Select member",
    );
  }

  function renderFamilies(preferredFamilyId) {
    const selectNode = document.querySelector(
      "[data-verification-family-select]",
    );
    if (!selectNode) return;

    if (!families.length) {
      if (preferredFamilyId) {
        selectNode.innerHTML = `<option value="">Select family</option>`;
        const option = document.createElement("option");
        option.value = preferredFamilyId;
        option.textContent = "Current Workspace Family";
        selectNode.appendChild(option);
        selectNode.value = preferredFamilyId;
        currentFamilyId = preferredFamilyId;
        updateNav(currentContext, currentFamilyId);
        return;
      }

      selectNode.innerHTML = `<option value="">No family records found</option>`;
      currentFamilyId = "";
      updateNav(currentContext, "");
      return;
    }

    selectNode.innerHTML = `<option value="">Select family</option>`;

    families.forEach(function (family) {
      const option = document.createElement("option");
      option.value = family.id;
      option.textContent =
        family.family_name ||
        family.description ||
        family.created_by ||
        family.id;
      selectNode.appendChild(option);
    });

    if (preferredFamilyId) {
      const matched = families.some(function (family) {
        return String(family?.id || "") === preferredFamilyId;
      });

      if (!matched) {
        const option = document.createElement("option");
        option.value = preferredFamilyId;
        option.textContent = "Current Workspace Family";
        selectNode.appendChild(option);
      }

      selectNode.value = preferredFamilyId;
      currentFamilyId = selectNode.value || preferredFamilyId;
    } else if (families.length === 1) {
      selectNode.value = families[0].id;
      currentFamilyId = families[0].id;
    } else {
      currentFamilyId = "";
    }

    updateNav(currentContext, currentFamilyId);
  }

  function validateRequiredForm(form, statusNode) {
    if (!form) return false;

    if (typeof form.reportValidity === "function" && !form.reportValidity()) {
      setStatus(
        statusNode,
        "Please complete all required fields and confirmations before continuing.",
        "error",
      );
      return false;
    }

    return true;
  }

  function validateFileType(file, allowedTypes, fallbackExtensions) {
    if (!file) return false;

    const type = String(file.type || "").toLowerCase();
    if (type && allowedTypes.has(type)) {
      return true;
    }

    const name = String(file.name || "").toLowerCase();
    return fallbackExtensions.some(function (ext) {
      return name.endsWith(ext);
    });
  }

  async function loadFamilies(preferredFamilyId) {
    const pageStatus = document.querySelector(
      "[data-verification-page-status]",
    );
    const actionStatus = document.querySelector(
      "[data-verification-action-status]",
    );

    try {
      clearStatus(actionStatus);

      families = await app.apiRequest("/families", { method: "GET" });
      if (!Array.isArray(families)) {
        families = [];
      }

      renderFamilies(preferredFamilyId);

      pageStatus.textContent = families.length
        ? `Loaded ${families.length} family record(s).`
        : preferredFamilyId
          ? "Loaded your current workspace family."
          : "No family records are available yet.";
    } catch (error) {
      console.error("Failed to load families:", error);
      pageStatus.textContent = "Unable to load family records.";
      setStatus(
        actionStatus,
        error.message || "Unable to load family records.",
        "error",
      );
    }
  }

  async function loadFamilyGraph() {
    const familySelect = document.querySelector(
      "[data-verification-family-select]",
    );
    const pageStatus = document.querySelector(
      "[data-verification-page-status]",
    );
    const actionStatus = document.querySelector(
      "[data-verification-action-status]",
    );

    const familyId = String(familySelect ? familySelect.value : "").trim();
    if (!familyId) {
      setStatus(actionStatus, "Please select a family first.", "error");
      return;
    }

    try {
      clearStatus(actionStatus);
      currentFamilyId = familyId;
      setFamilyIdInUrl(familyId);
      updateNav(currentContext, familyId);

      const graph = await app.apiRequest(
        `/families/${encodeURIComponent(familyId)}/graph`,
        { method: "GET" },
      );

      currentGraph = {
        members: Array.isArray(graph.members) ? graph.members : [],
      };

      populateMemberSelects();
      pageStatus.textContent = `Family ${familyId} loaded successfully.`;
      setStatus(actionStatus, "Family loaded successfully.", "success");
    } catch (error) {
      console.error("Failed to load family graph:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to load family graph.",
        "error",
      );
    }
  }

  async function handlePhotoUploadSubmit(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionStatus = document.querySelector(
      "[data-verification-action-status]",
    );

    if (!validateRequiredForm(form, actionStatus)) {
      return;
    }

    if (!currentFamilyId) {
      setStatus(
        actionStatus,
        "Load a family before uploading a member photo.",
        "error",
      );
      return;
    }

    const memberId = String(form.member_id.value || "").trim();
    const fileInput = form.querySelector('input[name="photo_file"]');
    const file = fileInput && fileInput.files ? fileInput.files[0] : null;

    if (!memberId || !file) {
      setStatus(actionStatus, "Member and photo file are required.", "error");
      return;
    }

    if (
      !validateFileType(file, ALLOWED_PHOTO_TYPES, [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
      ])
    ) {
      setStatus(
        actionStatus,
        "Invalid file type. Allowed member photo formats are JPG, PNG, and WEBP.",
        "error",
      );
      return;
    }

    const body = new FormData();
    body.append("family_id", currentFamilyId);
    body.append("member_id", memberId);
    body.append("file", file);

    try {
      setStatus(actionStatus, "Uploading member photo...", "info");

      await app.apiRequest("/uploads/member-photo", {
        method: "POST",
        body,
      });

      form.reset();

      const listMember = document.querySelector(
        "[data-verification-list-member]",
      );
      const categoryFilter = document.querySelector(
        "[data-verification-category-filter]",
      );
      if (listMember) listMember.value = memberId;
      if (categoryFilter) categoryFilter.value = "member_photo";

      setStatus(actionStatus, "Member photo uploaded successfully.", "success");
      await loadUploads();
    } catch (error) {
      console.error("Photo upload failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to upload member photo.",
        "error",
      );
    }
  }

  async function handleUploadSubmit(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionStatus = document.querySelector(
      "[data-verification-action-status]",
    );

    if (!validateRequiredForm(form, actionStatus)) {
      return;
    }

    if (!currentFamilyId) {
      setStatus(
        actionStatus,
        "Load a family before uploading evidence.",
        "error",
      );
      return;
    }

    const memberId = String(form.member_id.value || "").trim();
    const verificationType = String(form.verification_type.value || "").trim();
    const evidenceKind = String(form.evidence_kind.value || "").trim();
    const fileInput = form.querySelector('input[name="evidence_file"]');
    const file = fileInput && fileInput.files ? fileInput.files[0] : null;

    if (!memberId || !verificationType || !evidenceKind || !file) {
      setStatus(
        actionStatus,
        "Member, verification type, evidence kind, and file are required.",
        "error",
      );
      return;
    }

    if (
      !validateFileType(file, ALLOWED_EVIDENCE_TYPES, [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
      ])
    ) {
      setStatus(
        actionStatus,
        "Invalid file type. Allowed evidence formats are PDF, JPG, PNG, and WEBP.",
        "error",
      );
      return;
    }

    const body = new FormData();
    body.append("family_id", currentFamilyId);
    body.append("member_id", memberId);
    body.append("verification_type", verificationType);
    body.append("evidence_kind", evidenceKind);
    body.append("file", file);

    try {
      setStatus(actionStatus, "Uploading verification evidence...", "info");

      await app.apiRequest("/uploads/verification-evidence", {
        method: "POST",
        body,
      });

      form.reset();

      const listMember = document.querySelector(
        "[data-verification-list-member]",
      );
      const categoryFilter = document.querySelector(
        "[data-verification-category-filter]",
      );
      if (listMember) listMember.value = memberId;
      if (categoryFilter) categoryFilter.value = "verification_evidence";

      setStatus(
        actionStatus,
        "Verification evidence uploaded successfully.",
        "success",
      );
      await loadUploads();
    } catch (error) {
      console.error("Upload failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to upload verification evidence.",
        "error",
      );
    }
  }

  function renderUploads(uploads) {
    const listNode = document.querySelector("[data-verification-uploads-list]");
    const emptyNode = document.querySelector(
      "[data-verification-uploads-empty]",
    );
    if (!listNode) return;

    if (!Array.isArray(uploads) || !uploads.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    listNode.innerHTML = uploads
      .map(function (upload, index) {
        const preview = String(upload.content_type || "").startsWith("image/")
          ? `<div style="margin: 0 0 1rem;">
                 <img
                   src="${escapeHtml(
                     (typeof app.getApiBaseUrl === "function"
                       ? app.getApiBaseUrl()
                       : "") +
                       "/uploads/" +
                       encodeURIComponent(upload.id || "") +
                       "/download",
                   )}"
                   alt="${escapeHtml(upload.original_filename || "Uploaded image")}"
                   style="width: 100%; max-height: 220px; object-fit: cover; border-radius: 18px; border: 1px solid rgba(255,255,255,0.08);"
                 />
               </div>`
          : "";

        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            ${preview}
            <h3>${escapeHtml(upload.original_filename || "Uploaded File")}</h3>
            <p class="card-copy"><strong>Category:</strong> ${escapeHtml(upload.category || "—")}</p>
            <p class="card-copy"><strong>Verification Type:</strong> ${escapeHtml(upload.verification_type || "—")}</p>
            <p class="card-copy"><strong>Evidence Kind:</strong> ${escapeHtml(upload.evidence_kind || "—")}</p>
            <p class="card-copy"><strong>Content Type:</strong> ${escapeHtml(upload.content_type || "—")}</p>
            <p class="card-copy"><strong>Size:</strong> ${escapeHtml(upload.size_bytes ?? "—")}</p>
            <p class="card-copy"><strong>Uploaded By:</strong> ${escapeHtml(upload.uploaded_by || "—")}</p>
            <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(upload.created_at))}</p>

            <div class="inline-actions" style="margin-top: 1rem">
              <button
                class="btn btn-secondary"
                type="button"
                data-download-upload-id="${escapeHtml(upload.id || "")}"
                data-download-upload-name="${escapeHtml(upload.original_filename || "download")}"
              >
                Download
              </button>
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function loadUploads() {
    const memberSelect = document.querySelector(
      "[data-verification-list-member]",
    );
    const categorySelect = document.querySelector(
      "[data-verification-category-filter]",
    );
    const actionStatus = document.querySelector(
      "[data-verification-action-status]",
    );

    const memberId = String(memberSelect ? memberSelect.value : "").trim();
    const category = String(categorySelect ? categorySelect.value : "").trim();

    if (!memberId) {
      setStatus(
        actionStatus,
        "Select a member before loading uploads.",
        "error",
      );
      return;
    }

    try {
      setStatus(actionStatus, "Loading uploaded records...", "info");

      const query = category ? `?category=${encodeURIComponent(category)}` : "";
      const payload = await app.apiRequest(
        `/uploads/member/${encodeURIComponent(memberId)}${query}`,
        { method: "GET" },
      );

      renderUploads(Array.isArray(payload.uploads) ? payload.uploads : []);
      setStatus(
        actionStatus,
        "Uploaded records loaded successfully.",
        "success",
      );
    } catch (error) {
      console.error("Load uploads failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to load uploaded records.",
        "error",
      );
    }
  }

  async function downloadUpload(uploadId, originalFilename) {
    const actionStatus = document.querySelector(
      "[data-verification-action-status]",
    );

    if (!uploadId) {
      setStatus(actionStatus, "Missing upload id.", "error");
      return;
    }

    try {
      setStatus(actionStatus, "Downloading file...", "info");

      const token = app.getToken ? app.getToken() : "";
      const apiBaseUrl =
        typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";

      const response = await fetch(
        `${apiBaseUrl}/uploads/${encodeURIComponent(uploadId)}/download`,
        {
          method: "GET",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: "include",
        },
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Unable to download file.");
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = originalFilename || "download";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(objectUrl);

      setStatus(actionStatus, "Download started.", "success");
    } catch (error) {
      console.error("Download failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to download uploaded file.",
        "error",
      );
    }
  }

  async function setupVerificationUploadPage() {
    const page = document.querySelector("[data-verification-upload-page]");
    if (!page) return;

    try {
      const token = app.getToken ? app.getToken() : null;
      if (!token) {
        window.location.href = "signin.html";
        return;
      }

      await app.apiRequest("/auth/me", { method: "GET" });
      try {
        currentContext = await getCurrentContext();
      } catch (error) {
        currentContext = null;
      }

      const preferredFamilyId = await ensureWorkspaceFamilyId(currentContext);
      updateNav(currentContext, preferredFamilyId);
      await loadFamilies(preferredFamilyId);

      const loadFamilyButton = document.querySelector(
        "[data-verification-load-family]",
      );
      const photoForm = document.querySelector(
        "[data-verification-photo-form]",
      );
      const uploadForm = document.querySelector(
        "[data-verification-upload-form]",
      );
      const loadUploadsButton = document.querySelector(
        "[data-verification-load-uploads]",
      );

      if (loadFamilyButton) {
        loadFamilyButton.addEventListener("click", function () {
          loadFamilyGraph();
        });
      }

      if (photoForm) {
        photoForm.addEventListener("submit", handlePhotoUploadSubmit);
      }

      if (uploadForm) {
        uploadForm.addEventListener("submit", handleUploadSubmit);
      }

      if (loadUploadsButton) {
        loadUploadsButton.addEventListener("click", function () {
          loadUploads();
        });
      }

      document.addEventListener("click", function (event) {
        const downloadButton = event.target.closest(
          "[data-download-upload-id]",
        );
        if (!downloadButton) return;

        downloadUpload(
          downloadButton.getAttribute("data-download-upload-id"),
          downloadButton.getAttribute("data-download-upload-name"),
        );
      });

      const familySelect = document.querySelector(
        "[data-verification-family-select]",
      );
      if (familySelect) {
        familySelect.addEventListener("change", function () {
          updateNav(currentContext, familySelect.value);
        });
      }
      if (familySelect && familySelect.value) {
        await loadFamilyGraph();
      }
    } catch (error) {
      console.error("Verification upload page setup failed:", error);
      const pageStatus = document.querySelector(
        "[data-verification-page-status]",
      );
      const actionStatus = document.querySelector(
        "[data-verification-action-status]",
      );

      if (pageStatus) {
        pageStatus.textContent = "Verification workspace could not be loaded.";
      }

      setStatus(
        actionStatus,
        error.message || "Unable to load verification workspace.",
        "error",
      );
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupVerificationUploadPage();
  });
})();
