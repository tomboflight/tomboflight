(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};
  if (!app || typeof app.apiRequest !== "function") {
    console.error("vault-upload.js requires app.js/auth.js first.");
    return;
  }

  const ALLOWED_VAULT_TYPES = new Set([
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
    "private_voice_message",
    "private_video_message",
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

  function uploadStatusLabel(upload) {
    if (upload.quarantined) return "quarantined — under security review";
    const vs = String(upload.verification_status || "").toLowerCase();
    if (vs === "rejected") return "rejected";
    if (vs === "needs_correction") return "needs correction";
    if (vs === "approved") return "saved to vault";
    if (vs === "pending") return "pending review";
    if (upload.id || upload._id) return "saved to vault";
    return "pending review";
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
      context?.activeProject?._id || context?.activeProject?.id || "",
    ).trim();
  }

  function populateMemberSelects(members) {
    const selects = document.querySelectorAll(
      "[data-vault-member-select], [data-vault-list-member]",
    );
    selects.forEach(function (select) {
      const current = select.value;
      select.innerHTML = '<option value="">Select member</option>';
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
      if (msg.includes("can_upload") || msg.includes("entitlement") ||
          msg.includes("package") || msg.includes("permission")) {
        setStatus(
          familyStatus,
          "Your active package does not include vault file access. Contact support if you believe this is an error.",
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
      const payload = await app.apiRequest("/families/list", { method: "GET" });
      families = Array.isArray(payload?.families) ? payload.families : [];

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

  async function initPage() {
    const pageStatus = document.querySelector("[data-vault-page-status]");

    try {
      const context = await app.apiRequest("/auth/context", { method: "GET" });
      currentContext = context;

      const entitlements = context?.resolved_entitlements || {};
      const canUpload =
        entitlements.can_upload_portraits ||
        entitlements.can_upload_verification_docs;

      if (!canUpload) {
        if (pageStatus) {
          pageStatus.textContent =
            "Your active package does not include vault file access. Upgrade your package to enable vault uploads.";
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

      await loadFamilies();

      const urlFamilyId = getFamilyIdFromUrl();
      if (urlFamilyId) {
        currentFamilyId = urlFamilyId;
        await loadFamilyGraph(urlFamilyId);
      }
    } catch (error) {
      if (pageStatus) {
        pageStatus.textContent =
          "Unable to load your workspace. Please sign in and try again.";
      }
    }
  }

  function validateVaultFile(file) {
    if (!file) return "Please select a file to upload.";
    const contentType = normalizeValue(file.type);
    if (!ALLOWED_VAULT_TYPES.has(contentType)) {
      return "Unsupported file type. Allowed: MP3, M4A, WAV, WebM, OGG, MP4, MOV.";
    }
    return null;
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

    const base =
      typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";

    listNode.innerHTML = uploads
      .map(function (upload, index) {
        const downloadUrl =
          base + "/uploads/" + encodeURIComponent(upload.id || "") + "/download";

        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(upload.original_filename || "Vault File")}</h3>
            <p class="card-copy"><strong>Status:</strong> ${escapeHtml(uploadStatusLabel(upload))}</p>
            <p class="card-copy"><strong>File Type:</strong> ${escapeHtml(upload.asset_type || upload.category || "—")}</p>
            <p class="card-copy"><strong>Privacy:</strong> ${escapeHtml(upload.privacy_scope || upload.visibility_scope || "—")}</p>
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
    const memberSelect = document.querySelector("[data-vault-list-member]");
    const familyStatus = document.querySelector("[data-vault-family-status]");

    const memberId = String(memberSelect ? memberSelect.value : "").trim();
    if (!memberId && !currentFamilyId) {
      setStatus(
        familyStatus,
        "Load a family before loading vault files.",
        "error",
      );
      return;
    }

    try {
      setStatus(familyStatus, "Loading vault files...", "info");

      const endpoint = memberId
        ? `/uploads/member/${encodeURIComponent(memberId)}?category=private_media`
        : `/uploads/family/${encodeURIComponent(currentFamilyId)}?category=private_media`;

      const payload = await app.apiRequest(endpoint, { method: "GET" });
      renderUploads(Array.isArray(payload.uploads) ? payload.uploads : []);
      setStatus(familyStatus, "Vault files loaded successfully.", "success");
    } catch (error) {
      setStatus(
        familyStatus,
        error.message || "Unable to load vault files.",
        "error",
      );
    }
  }

  function setupDownloadHandlers() {
    document.addEventListener("click", async function (event) {
      const btn = event.target.closest("[data-download-upload-id]");
      if (!btn) return;

      const uploadId = btn.getAttribute("data-download-upload-id");
      const filename = btn.getAttribute("data-download-upload-name") || "download";
      if (!uploadId) return;

      try {
        const base =
          typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
        const url =
          base + "/uploads/" + encodeURIComponent(uploadId) + "/download";
        const response = await app.apiRequest(url, {
          method: "GET",
          raw: true,
        });
        if (response && response.url) {
          window.open(response.url, "_blank", "noopener,noreferrer");
        }
      } catch (error) {
        console.error("Vault file download failed:", error);
      }
    });
  }

  function setupPage() {
    const page = document.querySelector("[data-vault-upload-page]");
    if (!page) return;

    const familySelect = document.querySelector("[data-vault-family-select]");
    const loadFamilyBtn = document.querySelector("[data-vault-load-family]");
    const uploadForm = document.querySelector("[data-vault-upload-form]");
    const uploadStatus = document.querySelector("[data-vault-upload-status]");
    const loadUploadsBtn = document.querySelector("[data-vault-load-uploads]");

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

        const checkboxes = uploadForm.querySelectorAll(
          "input[type=checkbox][required]",
        );
        const allChecked = Array.from(checkboxes).every(
          function (cb) { return cb.checked; },
        );

        if (!memberId) {
          setStatus(uploadStatus, "Select a family member first.", "error");
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
        const fileError = validateVaultFile(file);
        if (fileError) {
          setStatus(uploadStatus, fileError, "error");
          return;
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
          formData.append("family_id", currentFamilyId);
          formData.append("member_id", memberId);
          formData.append("asset_type", assetType);
          formData.append("privacy_scope", privacyScope);
          formData.append("file", file, file.name);

          await app.apiRequest("/uploads/private-media", {
            method: "POST",
            body: formData,
          });

          setStatus(
            uploadStatus,
            "Vault file uploaded successfully. Status: saved to vault — pending security review.",
            "success",
          );
          uploadForm.reset();
          populateMemberSelects(
            Array.isArray(currentGraph.members) ? currentGraph.members : [],
          );
        } catch (error) {
          const msg = error.message || "Upload failed. Please try again.";
          if (msg.includes("can_upload") || msg.includes("entitlement") ||
              msg.includes("package") || msg.includes("permission")) {
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

    setupDownloadHandlers();
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
