(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};
  if (!app || typeof app.apiRequest !== "function") {
    console.error("portrait-upload.js requires app.js/auth.js first.");
    return;
  }

  const ALLOWED_PHOTO_TYPES = new Set([
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

  function getPackageCodeFromContext(context) {
    return normalizeValue(
      context?.packageCode ||
        context?.activeProject?.package_code ||
        context?.activeProject?.packageCode ||
        context?.resolvedEntitlements?.package_code ||
        "",
    );
  }

  function isLegacySnapshotContext(context) {
    return getPackageCodeFromContext(context) === "legacy_snapshot";
  }

  function resolveMembersFromManifest(manifest) {
    const seen = new Set();
    const members = [];
    const states = Array.isArray(manifest?.states) ? manifest.states : [];

    states.forEach(function (state) {
      const memberId = String(state?.member_id || "").trim();
      if (!memberId || seen.has(memberId)) return;
      seen.add(memberId);
      members.push({
        id: memberId,
        display_name: String(state?.title || "Portrait Subject").trim() || "Portrait Subject",
        generation: 1,
      });
    });

    const primaryMemberId = String(manifest?.primary_member_id || "").trim();
    if (primaryMemberId && !seen.has(primaryMemberId)) {
      members.unshift({
        id: primaryMemberId,
        display_name: "Portrait Subject",
        generation: 1,
      });
    }

    return members;
  }

  async function loadLegacySnapshotMembersFromManifest(familyId) {
    const projectId = getProjectIdFromContext(currentContext);
    if (!projectId) {
      return [];
    }

    const query = new URLSearchParams();
    query.set("project_id", projectId);
    if (familyId) {
      query.set("family_id", familyId);
    }

    const manifest = await app.apiRequest(`/viewer/manifest?${query.toString()}`, {
      method: "GET",
    });
    return resolveMembersFromManifest(manifest);
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
      "dashboard.html",
      "portrait-upload.html",
      "verification-upload.html",
      "link-keys.html",
      "tree-view.html",
      "lineage-certificate.html",
    ].forEach(function (href) {
      document
        .querySelectorAll(`.site-nav a[href^="${href}"]`)
        .forEach(function (node) {
          node.setAttribute("href", withWorkspaceHref(href, context, familyIdOverride));
        });
    });

    document.querySelectorAll("[data-portrait-dashboard-link]").forEach(function (node) {
      node.setAttribute("href", withWorkspaceHref("dashboard.html", context, familyIdOverride));
    });

    document
      .querySelectorAll("[data-portrait-verification-link]")
      .forEach(function (node) {
        node.setAttribute(
          "href",
          withWorkspaceHref("verification-upload.html", context, familyIdOverride),
        );
      });
  }

  function setNavVisible(href, isVisible) {
    document
      .querySelectorAll(`.site-nav a[href^="${href}"]`)
      .forEach(function (node) {
        node.style.display = isVisible ? "" : "none";
      });
  }

  function applyEntitlementNav(context) {
    const resolved = context?.resolvedEntitlements || {};
    if (!Object.keys(resolved).length) return;

    setNavVisible(
      "verification-upload.html",
      Boolean(resolved.can_upload_verification_docs || resolved.can_upload_portraits),
    );
    setNavVisible("link-keys.html", Boolean(resolved.can_use_link_keys));
    setNavVisible("tree-view.html", Boolean(resolved.can_build_family_tree));
    setNavVisible(
      "lineage-certificate.html",
      Boolean(resolved.can_use_lineage_certificate),
    );
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
    return joined || "Portrait Subject";
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
        return `<option value="${escapeHtml(member.id)}">${escapeHtml(getDisplayName(member))}</option>`;
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
      return;
    }

    if ((members || []).length === 1) {
      selectNode.value = String(members[0].id || "").trim();
    }
  }

  function populateMemberSelects() {
    const members = Array.isArray(currentGraph.members)
      ? currentGraph.members
      : [];

    setSelectOptions(
      document.querySelector("[data-portrait-member-select]"),
      members,
      "Select subject",
    );
    setSelectOptions(
      document.querySelector("[data-portrait-list-member]"),
      members,
      "Select subject",
    );
  }

  function renderFamilies(preferredFamilyId) {
    const selectNode = document.querySelector("[data-portrait-family-select]");
    if (!selectNode) return;

    if (!families.length) {
      if (preferredFamilyId) {
        selectNode.innerHTML = `<option value="">Select portrait record</option>`;
        const option = document.createElement("option");
        option.value = preferredFamilyId;
        option.textContent = "Current Portrait Workspace";
        selectNode.appendChild(option);
        selectNode.value = preferredFamilyId;
        currentFamilyId = preferredFamilyId;
        updateNav(currentContext, currentFamilyId);
        return;
      }

      selectNode.innerHTML = `<option value="">No portrait records found</option>`;
      currentFamilyId = "";
      updateNav(currentContext, "");
      return;
    }

    selectNode.innerHTML = `<option value="">Select portrait record</option>`;

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
        option.textContent = "Current Portrait Workspace";
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
        "Please complete the required fields and confirmations before uploading.",
        "error",
      );
      return false;
    }

    return true;
  }

  function validateFileType(file) {
    if (!file) return false;

    const type = String(file.type || "").toLowerCase();
    if (type && ALLOWED_PHOTO_TYPES.has(type)) {
      return true;
    }

    const name = String(file.name || "").toLowerCase();
    return [".jpg", ".jpeg", ".png", ".webp"].some(function (ext) {
      return name.endsWith(ext);
    });
  }

  async function loadFamilies(preferredFamilyId) {
    const pageStatus = document.querySelector("[data-portrait-page-status]");
    const actionStatus = document.querySelector("[data-portrait-action-status]");

    try {
      clearStatus(actionStatus);

      families = await app.apiRequest("/families", { method: "GET" });
      if (!Array.isArray(families)) {
        families = [];
      }

      renderFamilies(preferredFamilyId);

      pageStatus.textContent = families.length
        ? `Loaded ${families.length} portrait record(s).`
        : preferredFamilyId
          ? "Loaded your current portrait workspace."
          : "No portrait records are available yet.";
    } catch (error) {
      console.error("Failed to load portrait records:", error);
      pageStatus.textContent = "Unable to load portrait records.";
      setStatus(
        actionStatus,
        error.message || "Unable to load portrait records.",
        "error",
      );
    }
  }

  async function loadFamilyGraph() {
    const familySelect = document.querySelector("[data-portrait-family-select]");
    const pageStatus = document.querySelector("[data-portrait-page-status]");
    const actionStatus = document.querySelector("[data-portrait-action-status]");

    const familyId = String(familySelect ? familySelect.value : "").trim();
    if (!familyId) {
      setStatus(actionStatus, "Please select a portrait record first.", "error");
      return;
    }

    try {
      clearStatus(actionStatus);
      currentFamilyId = familyId;
      setFamilyIdInUrl(familyId);
      updateNav(currentContext, familyId);

      let members = [];
      if (isLegacySnapshotContext(currentContext)) {
        members = await loadLegacySnapshotMembersFromManifest(familyId);
      } else {
        const projectId = getProjectIdFromContext(currentContext);
        if (projectId) {
          try {
            const manifest = await app.apiRequest(
              `/viewer/manifest?project_id=${encodeURIComponent(projectId)}&family_id=${encodeURIComponent(familyId)}`,
              { method: "GET" },
            );
            const canBuildFamilyTree = Boolean(
              currentContext?.resolvedEntitlements?.can_build_family_tree,
            );
            if (
              normalizeValue(manifest?.mode) === "secure_share" ||
              !canBuildFamilyTree
            ) {
              members = resolveMembersFromManifest(manifest);
            }
          } catch (manifestError) {
            console.warn("Portrait manifest member resolution failed:", manifestError);
          }
        }

        if (!members.length) {
          let graph = await app.apiRequest(
            `/families/${encodeURIComponent(familyId)}/graph`,
            { method: "GET" },
          );

          members = Array.isArray(graph.members) ? graph.members : [];

          if (!members.length) {
            if (projectId) {
              try {
                await app.apiRequest(
                  `/viewer/manifest?project_id=${encodeURIComponent(projectId)}&family_id=${encodeURIComponent(familyId)}`,
                  { method: "GET" },
                );
                graph = await app.apiRequest(
                  `/families/${encodeURIComponent(familyId)}/graph`,
                  { method: "GET" },
                );
                members = Array.isArray(graph.members) ? graph.members : [];
              } catch (retryError) {
                console.warn("Portrait member backfill retry failed:", retryError);
              }
            }
          }
        }
      }

      currentGraph = { members };
      populateMemberSelects();

      if (members.length) {
        const firstMember = String(members[0]?.id || "").trim();
        const listMember = document.querySelector("[data-portrait-list-member]");
        if (members.length === 1 && listMember && firstMember) {
          listMember.value = firstMember;
          await loadUploads();
        }

        pageStatus.textContent = "Portrait record loaded successfully.";
        setStatus(actionStatus, "Portrait record loaded successfully.", "success");
      } else {
        pageStatus.textContent =
          "Portrait record loaded, but no subject record was found yet.";
        setStatus(
          actionStatus,
          "Portrait record loaded, but no subject is available yet for uploads. Please refresh or contact Tomb of Light support if this workspace was just provisioned.",
          "error",
        );
      }
    } catch (error) {
      console.error("Failed to load portrait record:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to load portrait record.",
        "error",
      );
    }
  }

  async function handlePortraitUploadSubmit(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionStatus = document.querySelector("[data-portrait-action-status]");

    if (!validateRequiredForm(form, actionStatus)) {
      return;
    }

    if (!currentFamilyId) {
      setStatus(
        actionStatus,
        "Load the portrait record before uploading a portrait.",
        "error",
      );
      return;
    }

    const memberId = String(form.member_id.value || "").trim();
    const fileInput = form.querySelector('input[name="photo_file"]');
    const file = fileInput && fileInput.files ? fileInput.files[0] : null;

    if (!memberId || !file) {
      setStatus(actionStatus, "Portrait subject and file are required.", "error");
      return;
    }

    if (!validateFileType(file)) {
      setStatus(
        actionStatus,
        "Invalid file type. Allowed portrait formats are JPG, PNG, and WEBP.",
        "error",
      );
      return;
    }

    const body = new FormData();
    body.append("family_id", currentFamilyId);
    body.append("member_id", memberId);
    body.append("file", file);

    try {
      setStatus(actionStatus, "Uploading portrait...", "info");

      await app.apiRequest("/uploads/member-photo", {
        method: "POST",
        body,
      });

      form.reset();

      const memberSelect = document.querySelector("[data-portrait-member-select]");
      const listMember = document.querySelector("[data-portrait-list-member]");
      if (memberSelect) memberSelect.value = memberId;
      if (listMember) listMember.value = memberId;

      setStatus(
        actionStatus,
        "Portrait uploaded successfully. You can return to the dashboard or add another portrait.",
        "success",
      );
      await loadUploads();
    } catch (error) {
      console.error("Portrait upload failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to upload portrait.",
        "error",
      );
    }
  }

  function renderUploads(uploads) {
    const listNode = document.querySelector("[data-portrait-uploads-list]");
    const emptyNode = document.querySelector("[data-portrait-uploads-empty]");
    if (!listNode) return;

    if (!Array.isArray(uploads) || !uploads.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    listNode.innerHTML = uploads
      .map(function (upload, index) {
        const downloadUrl =
          (typeof app.getApiBaseUrl === "function"
            ? app.getApiBaseUrl()
            : "") +
          "/uploads/" +
          encodeURIComponent(upload.id || "") +
          "/download";
        const preview = String(upload.content_type || "").startsWith("image/")
          ? `<div style="margin: 0 0 1rem;">
                 <img
                   src="${escapeHtml(downloadUrl)}"
                   alt="${escapeHtml(upload.original_filename || "Uploaded portrait")}"
                   style="width: 100%; max-height: 260px; object-fit: cover; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);"
                 />
               </div>`
          : "";

        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            ${preview}
            <h3>${escapeHtml(upload.original_filename || "Uploaded Portrait")}</h3>
            <p class="card-copy"><strong>Category:</strong> ${escapeHtml(upload.category || "member_photo")}</p>
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
    const memberSelect = document.querySelector("[data-portrait-list-member]");
    const actionStatus = document.querySelector("[data-portrait-action-status]");

    const memberId = String(memberSelect ? memberSelect.value : "").trim();
    if (!memberId) {
      setStatus(
        actionStatus,
        "Select a portrait subject before loading uploads.",
        "error",
      );
      return;
    }

    try {
      setStatus(actionStatus, "Loading portrait uploads...", "info");

      const payload = await app.apiRequest(
        `/uploads/member/${encodeURIComponent(memberId)}?category=member_photo`,
        { method: "GET" },
      );

      renderUploads(Array.isArray(payload.uploads) ? payload.uploads : []);
      setStatus(actionStatus, "Portrait uploads loaded successfully.", "success");
    } catch (error) {
      console.error("Load portrait uploads failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to load portrait uploads.",
        "error",
      );
    }
  }

  async function downloadUpload(uploadId, originalFilename) {
    const actionStatus = document.querySelector("[data-portrait-action-status]");

    if (!uploadId) {
      setStatus(actionStatus, "Missing upload id.", "error");
      return;
    }

    try {
      setStatus(actionStatus, "Downloading portrait...", "info");

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
        throw new Error(text || "Unable to download portrait.");
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = originalFilename || "portrait-download";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(objectUrl);

      setStatus(actionStatus, "Download started.", "success");
    } catch (error) {
      console.error("Portrait download failed:", error);
      setStatus(
        actionStatus,
        error.message || "Unable to download portrait.",
        "error",
      );
    }
  }

  async function setupPortraitUploadPage() {
    const page = document.querySelector("[data-portrait-upload-page]");
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
      applyEntitlementNav(currentContext);
      await loadFamilies(preferredFamilyId);

      const loadFamilyButton = document.querySelector("[data-portrait-load-family]");
      const uploadForm = document.querySelector("[data-portrait-upload-form]");
      const loadUploadsButton = document.querySelector("[data-portrait-load-uploads]");
      const familySelect = document.querySelector("[data-portrait-family-select]");

      if (loadFamilyButton) {
        loadFamilyButton.addEventListener("click", function () {
          loadFamilyGraph();
        });
      }

      if (uploadForm) {
        uploadForm.addEventListener("submit", handlePortraitUploadSubmit);
      }

      if (loadUploadsButton) {
        loadUploadsButton.addEventListener("click", function () {
          loadUploads();
        });
      }

      document.addEventListener("click", function (event) {
        const downloadButton = event.target.closest("[data-download-upload-id]");
        if (!downloadButton) return;

        downloadUpload(
          downloadButton.getAttribute("data-download-upload-id"),
          downloadButton.getAttribute("data-download-upload-name"),
        );
      });

      if (familySelect) {
        familySelect.addEventListener("change", function () {
          updateNav(currentContext, familySelect.value);
        });
      }

      if (familySelect && familySelect.value) {
        await loadFamilyGraph();
      }
    } catch (error) {
      console.error("Portrait upload page setup failed:", error);
      const pageStatus = document.querySelector("[data-portrait-page-status]");
      const actionStatus = document.querySelector("[data-portrait-action-status]");

      if (pageStatus) {
        pageStatus.textContent = "Portrait workspace could not be loaded.";
      }

      setStatus(
        actionStatus,
        error.message || "Unable to load portrait workspace.",
        "error",
      );
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupPortraitUploadPage();
  });
})();
