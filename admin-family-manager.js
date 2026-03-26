(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    console.error("admin-family-manager.js requires app.js/auth.js first.");
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

  let familyBuilds = [];
  let currentFamilyId = "";
  let currentGraph = { members: [], relationships: [] };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function humanizeValue(value) {
    const normalized = normalizeValue(value);
    if (!normalized) return "Unknown";
    return normalized
      .split("_")
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
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

  function ensureAdminAccess(me) {
    const values = [
      normalizeValue(me && me.role),
      normalizeValue(me && me.access_tier),
      normalizeValue(me && me.department_role),
    ];

    const hasAccess = values.some(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });

    if (!hasAccess) {
      throw new Error("Admin access is required to use this page.");
    }
  }

  async function requireAdmin() {
    const token = app.getToken ? app.getToken() : null;
    if (!token) {
      window.location.href = "signin.html";
      return null;
    }

    const me = await app.apiRequest("/auth/me", { method: "GET" });
    ensureAdminAccess(me);
    return me;
  }

  async function apiRequestWithFallback(paths, options) {
    let lastError = null;

    for (const path of paths) {
      try {
        return await app.apiRequest(path, options);
      } catch (error) {
        lastError = error;
        console.error(`API request failed for ${path}`, error);
      }
    }

    throw lastError || new Error("All API request attempts failed.");
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

  function parseEvidenceFiles(value) {
    return String(value || "")
      .split(/[\n,]+/)
      .map(function (item) {
        return item.trim();
      })
      .filter(Boolean);
  }

  function getVerificationPayload(member, actionType) {
    const displayName = getDisplayName(member);

    const defaultType =
      actionType === "verify"
        ? member.verification_method || "birth_certificate"
        : member.verification_method || "admin_review";

    const verificationType = window.prompt(
      `Verification type for ${displayName}?`,
      defaultType,
    );
    if (verificationType === null) return null;

    const verificationMethod = window.prompt(
      `Verification method for ${displayName}?`,
      member.verification_method || "admin_review",
    );
    if (verificationMethod === null) return null;

    const reviewNotes = window.prompt(
      `Internal review notes for ${displayName}?`,
      member.verification_notes || "",
    );
    if (reviewNotes === null) return null;

    const evidenceSummary = window.prompt(
      `Evidence summary for ${displayName}?`,
      "",
    );
    if (evidenceSummary === null) return null;

    const evidenceFilesRaw = window.prompt(
      `Evidence file references for ${displayName}? (comma separated or line separated)`,
      "",
    );
    if (evidenceFilesRaw === null) return null;

    return {
      verification_type: String(verificationType || "").trim(),
      verification_method: String(verificationMethod || "").trim(),
      review_notes: String(reviewNotes || "").trim(),
      evidence_summary: String(evidenceSummary || "").trim(),
      evidence_files: parseEvidenceFiles(evidenceFilesRaw),
    };
  }

  function getClearVerificationPayload(member) {
    const displayName = getDisplayName(member);
    const reviewNotes = window.prompt(
      `Reason for clearing verification on ${displayName}?`,
      member.verification_notes || "",
    );
    if (reviewNotes === null) return null;

    return {
      review_notes: String(reviewNotes || "").trim(),
    };
  }

  function renderFamilyBuildOptions() {
    const selectNode = document.querySelector("[data-admin-family-select]");
    if (!selectNode) return;

    if (!familyBuilds.length) {
      selectNode.innerHTML = `<option value="">No provisioned family builds found</option>`;
      return;
    }

    selectNode.innerHTML = `<option value="">Select a family build</option>`;

    familyBuilds.forEach(function (item) {
      const option = document.createElement("option");
      option.value = item.family_root_id;
      option.textContent = `${item.email || "Unknown Email"} — ${item.family_root_id}`;
      selectNode.appendChild(option);
    });

    const fromQuery = new URLSearchParams(window.location.search).get(
      "family_id",
    );
    if (fromQuery) {
      selectNode.value = fromQuery;
      currentFamilyId = fromQuery;
    }
  }

  function renderSummary(graph) {
    const node = document.querySelector("[data-admin-family-summary]");
    if (!node) return;

    const members = Array.isArray(graph.members) ? graph.members : [];
    const relationships = Array.isArray(graph.relationships)
      ? graph.relationships
      : [];

    const generations = members
      .map(function (member) {
        return Number(member.generation);
      })
      .filter(function (value) {
        return Number.isFinite(value);
      });

    const generationCount = generations.length
      ? Math.max(...generations) - Math.min(...generations) + 1
      : 0;

    const verifiedCount = members.filter(function (member) {
      return (
        member.is_verified === true ||
        normalizeValue(member.verification_status) === "verified"
      );
    }).length;

    node.innerHTML = `
      <div><div class="card-number">A</div><h3>Members</h3><p class="card-copy">${members.length} total member(s)</p></div>
      <div><div class="card-number">B</div><h3>Relationships</h3><p class="card-copy">${relationships.length} total relationship(s)</p></div>
      <div><div class="card-number">C</div><h3>Generations</h3><p class="card-copy">${generationCount} generation level(s)</p></div>
      <div><div class="card-number">D</div><h3>Verified Members</h3><p class="card-copy">${verifiedCount} verified</p></div>
      <div><div class="card-number">E</div><h3>Family Root</h3><p class="card-copy">${escapeHtml(currentFamilyId || "—")}</p></div>
      <div><div class="card-number">F</div><h3>Status</h3><p class="card-copy">Family build loaded</p></div>
    `;
  }

  function renderMembers(graph) {
    const listNode = document.querySelector("[data-admin-family-members-list]");
    const emptyNode = document.querySelector(
      "[data-admin-family-members-empty]",
    );
    if (!listNode) return;

    const members = sortMembers(
      Array.isArray(graph.members) ? graph.members : [],
    );

    if (!members.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    listNode.innerHTML = members
      .map(function (member, index) {
        const verified =
          member.is_verified === true ||
          normalizeValue(member.verification_status) === "verified";

        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(getDisplayName(member))}</h3>
            <p class="card-copy"><strong>Generation:</strong> ${escapeHtml(member.generation ?? "—")}</p>
            <p class="card-copy"><strong>Birth Year:</strong> ${escapeHtml(member.birth_year ?? "—")}</p>
            <p class="card-copy"><strong>Verified:</strong> ${verified ? "Yes" : "No"}</p>
            <p class="card-copy"><strong>Verification Status:</strong> ${escapeHtml(member.verification_status || "unverified")}</p>
            <p class="card-copy"><strong>Verification Method:</strong> ${escapeHtml(member.verification_method || "—")}</p>
            <p class="card-copy"><strong>Verified By:</strong> ${escapeHtml(member.verified_by || "—")}</p>
            <p class="card-copy"><strong>Verified At:</strong> ${escapeHtml(formatDate(member.verified_at))}</p>
            <p class="card-copy"><strong>Member ID:</strong> ${escapeHtml(member.id || "—")}</p>
            <p class="card-copy"><strong>Bio:</strong> ${escapeHtml(member.bio || "—")}</p>

            <div class="inline-actions" style="margin-top: 1rem">
              <button
                class="btn btn-primary"
                type="button"
                data-verify-member-id="${escapeHtml(member.id || "")}"
              >
                Verify
              </button>

              <button
                class="btn btn-secondary"
                type="button"
                data-pending-member-id="${escapeHtml(member.id || "")}"
              >
                Mark Pending
              </button>

              <button
                class="btn btn-secondary"
                type="button"
                data-reject-member-id="${escapeHtml(member.id || "")}"
              >
                Reject
              </button>

              <button
                class="btn btn-secondary"
                type="button"
                data-clear-verification-member-id="${escapeHtml(member.id || "")}"
              >
                Clear Verification
              </button>
            </div>

            <div class="inline-actions" style="margin-top: 1rem">
              <button
                class="btn btn-secondary"
                type="button"
                data-delete-member-id="${escapeHtml(member.id || "")}"
                data-delete-member-name="${escapeHtml(getDisplayName(member))}"
              >
                Delete Member
              </button>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderRelationships(graph) {
    const listNode = document.querySelector(
      "[data-admin-family-relationships-list]",
    );
    const emptyNode = document.querySelector(
      "[data-admin-family-relationships-empty]",
    );
    if (!listNode) return;

    const members = Array.isArray(graph.members) ? graph.members : [];
    const relationships = Array.isArray(graph.relationships)
      ? graph.relationships
      : [];
    const memberMap = new Map();

    members.forEach(function (member) {
      memberMap.set(member.id, member);
    });

    if (!relationships.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    listNode.innerHTML = relationships
      .map(function (relationship, index) {
        const source = memberMap.get(relationship.source_member_id);
        const target = memberMap.get(relationship.target_member_id);

        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(humanizeValue(relationship.relationship_type || "unknown"))}</h3>
            <p class="card-copy"><strong>Source:</strong> ${escapeHtml(source ? getDisplayName(source) : relationship.source_member_id || "—")}</p>
            <p class="card-copy"><strong>Target:</strong> ${escapeHtml(target ? getDisplayName(target) : relationship.target_member_id || "—")}</p>
            <p class="card-copy"><strong>Relationship ID:</strong> ${escapeHtml(relationship.id || relationship._id || "—")}</p>
            <p class="card-copy"><strong>Notes:</strong> ${escapeHtml(relationship.notes || "—")}</p>
            <div class="inline-actions" style="margin-top: 1rem;">
              <button
                class="btn btn-secondary"
                type="button"
                data-delete-relationship-id="${escapeHtml(relationship.id || relationship._id || "")}"
              >
                Delete Relationship
              </button>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderMemberUploads(records) {
    const listNode = document.querySelector("[data-admin-member-uploads-list]");
    const emptyNode = document.querySelector(
      "[data-admin-member-uploads-empty]",
    );
    if (!listNode) return;

    if (!Array.isArray(records) || !records.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    listNode.innerHTML = records
      .map(function (upload, index) {
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(upload.original_filename || "Uploaded File")}</h3>
            <p class="card-copy"><strong>Category:</strong> ${escapeHtml(upload.category || "—")}</p>
            <p class="card-copy"><strong>Verification Type:</strong> ${escapeHtml(upload.verification_type || "—")}</p>
            <p class="card-copy"><strong>Evidence Kind:</strong> ${escapeHtml(upload.evidence_kind || "—")}</p>
            <p class="card-copy"><strong>Content Type:</strong> ${escapeHtml(upload.content_type || "—")}</p>
            <p class="card-copy"><strong>Size:</strong> ${escapeHtml(upload.size_bytes ?? "—")}</p>
            <p class="card-copy"><strong>Uploaded By:</strong> ${escapeHtml(upload.uploaded_by || "—")}</p>
            <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(upload.created_at))}</p>
            <p class="card-copy"><strong>Upload ID:</strong> ${escapeHtml(upload.id || "—")}</p>

            <div class="inline-actions" style="margin-top: 1rem">
              <button
                class="btn btn-secondary"
                type="button"
                data-download-upload-id="${escapeHtml(upload.id || "")}"
                data-download-upload-name="${escapeHtml(upload.original_filename || "download")}"
              >
                Download
              </button>

              <button
                class="btn btn-secondary"
                type="button"
                data-delete-upload-id="${escapeHtml(upload.id || "")}"
              >
                Delete Upload
              </button>
            </div>
          </div>
        `;
      })
      .join("");
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

  function populateRelationshipMemberSelects(graph) {
    const members = Array.isArray(graph.members) ? graph.members : [];

    setSelectOptions(
      document.querySelector("[data-admin-source-member]"),
      members,
      "Select source member",
    );
    setSelectOptions(
      document.querySelector("[data-admin-target-member]"),
      members,
      "Select target member",
    );
  }

  function populateUploadMemberSelects(graph) {
    const members = Array.isArray(graph.members) ? graph.members : [];

    setSelectOptions(
      document.querySelector("[data-admin-photo-member]"),
      members,
      "Select member",
    );
    setSelectOptions(
      document.querySelector("[data-admin-evidence-member]"),
      members,
      "Select member",
    );
    setSelectOptions(
      document.querySelector("[data-admin-uploads-member]"),
      members,
      "Select member",
    );
  }

  async function loadFamilyBuildOptions() {
    const statusNode = document.querySelector("[data-admin-family-status]");
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    try {
      clearStatus(actionNode);

      const submissions = await apiRequestWithFallback(
        [
          "/admin/intake-submissions?limit=100",
          "/admin/intake-submissions/?limit=100",
        ],
        { method: "GET" },
      );

      const seen = new Set();
      familyBuilds = (Array.isArray(submissions) ? submissions : []).filter(
        function (item) {
          const familyRootId = String(item.family_root_id || "").trim();
          if (!familyRootId) return false;
          if (seen.has(familyRootId)) return false;
          seen.add(familyRootId);
          return true;
        },
      );

      renderFamilyBuildOptions();

      if (statusNode) {
        statusNode.textContent = familyBuilds.length
          ? `Loaded ${familyBuilds.length} provisioned family build(s).`
          : "No provisioned family builds were found yet.";
      }
    } catch (error) {
      console.error("Family build options load failed:", error);
      if (statusNode) {
        statusNode.textContent = "Family build options could not be loaded.";
      }
      setStatus(
        actionNode,
        error.message || "Unable to load provisioned family builds.",
        "error",
      );
    }
  }

  async function loadFamilyGraph() {
    const selectNode = document.querySelector("[data-admin-family-select]");
    const statusNode = document.querySelector("[data-admin-family-status]");
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    const familyId = String(selectNode ? selectNode.value : "").trim();
    if (!familyId) {
      setStatus(actionNode, "Please select a family build first.", "error");
      return;
    }

    try {
      clearStatus(actionNode);
      currentFamilyId = familyId;

      const graph = await app.apiRequest(
        `/families/${encodeURIComponent(familyId)}/graph`,
        { method: "GET" },
      );

      currentGraph = {
        members: Array.isArray(graph.members) ? graph.members : [],
        relationships: Array.isArray(graph.relationships)
          ? graph.relationships
          : [],
      };

      renderSummary(currentGraph);
      renderMembers(currentGraph);
      renderRelationships(currentGraph);
      populateRelationshipMemberSelects(currentGraph);
      populateUploadMemberSelects(currentGraph);

      if (statusNode) {
        statusNode.textContent = `Family build ${familyId} loaded successfully.`;
      }

      setStatus(actionNode, "Family build loaded successfully.", "success");
    } catch (error) {
      console.error("Family graph load failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to load family graph.",
        "error",
      );
    }
  }

  async function loadMemberUploads() {
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );
    const memberSelect = document.querySelector("[data-admin-uploads-member]");
    const categorySelect = document.querySelector(
      "[data-admin-upload-category-filter]",
    );

    const memberId = String(memberSelect ? memberSelect.value : "").trim();
    const category = String(categorySelect ? categorySelect.value : "").trim();

    if (!memberId) {
      setStatus(actionNode, "Select a member before loading uploads.", "error");
      return;
    }

    try {
      setStatus(actionNode, "Loading member uploads...", "info");

      const query = category ? `?category=${encodeURIComponent(category)}` : "";

      const payload = await app.apiRequest(
        `/uploads/member/${encodeURIComponent(memberId)}${query}`,
        { method: "GET" },
      );

      renderMemberUploads(
        Array.isArray(payload.uploads) ? payload.uploads : [],
      );
      setStatus(actionNode, "Member uploads loaded successfully.", "success");
    } catch (error) {
      console.error("Load member uploads failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to load member uploads.",
        "error",
      );
    }
  }

  async function handleCreateMember(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!currentFamilyId) {
      setStatus(actionNode, "Load a family before adding a member.", "error");
      return;
    }

    const firstName = String(form.first_name.value || "").trim();
    const lastName = String(form.last_name.value || "").trim();
    const generation = String(form.generation.value || "").trim();
    const birthYear = String(form.birth_year.value || "").trim();
    const bio = String(form.bio.value || "").trim();

    if (!firstName || !lastName || !generation) {
      setStatus(
        actionNode,
        "First name, last name, and generation are required.",
        "error",
      );
      return;
    }

    const payload = {
      family_id: currentFamilyId,
      first_name: firstName,
      last_name: lastName,
      generation: Number(generation),
      bio: bio || "",
    };

    if (birthYear) {
      payload.birth_year = Number(birthYear);
    }

    try {
      setStatus(actionNode, "Creating family member...", "info");

      await app.apiRequest("/family-members", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      form.reset();
      await loadFamilyGraph();
      setStatus(actionNode, "Family member created successfully.", "success");
    } catch (error) {
      console.error("Create member failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to create family member.",
        "error",
      );
    }
  }

  async function handleCreateRelationship(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!currentFamilyId) {
      setStatus(
        actionNode,
        "Load a family before adding a relationship.",
        "error",
      );
      return;
    }

    const sourceMemberId = String(form.source_member_id.value || "").trim();
    const targetMemberId = String(form.target_member_id.value || "").trim();
    const relationshipType = String(form.relationship_type.value || "").trim();
    const notes = String(form.notes.value || "").trim();

    if (!sourceMemberId || !targetMemberId || !relationshipType) {
      setStatus(
        actionNode,
        "Source member, target member, and relationship type are required.",
        "error",
      );
      return;
    }

    const payload = {
      family_id: currentFamilyId,
      source_member_id: sourceMemberId,
      target_member_id: targetMemberId,
      relationship_type: relationshipType,
      notes: notes || "",
    };

    try {
      setStatus(actionNode, "Creating relationship...", "info");

      await app.apiRequest("/relationships", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      form.reset();
      populateRelationshipMemberSelects(currentGraph);
      await loadFamilyGraph();
      setStatus(actionNode, "Relationship created successfully.", "success");
    } catch (error) {
      console.error("Create relationship failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to create relationship.",
        "error",
      );
    }
  }

  async function handleUploadMemberPhoto(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!currentFamilyId) {
      setStatus(actionNode, "Load a family before uploading a photo.", "error");
      return;
    }

    const memberId = String(form.member_id.value || "").trim();
    const fileInput = form.querySelector('input[name="photo_file"]');
    const file = fileInput && fileInput.files ? fileInput.files[0] : null;

    if (!memberId || !file) {
      setStatus(actionNode, "Member and photo file are required.", "error");
      return;
    }

    const body = new FormData();
    body.append("family_id", currentFamilyId);
    body.append("member_id", memberId);
    body.append("file", file);

    try {
      setStatus(actionNode, "Uploading member photo...", "info");

      await app.apiRequest("/uploads/member-photo", {
        method: "POST",
        body,
      });

      form.reset();
      await loadFamilyGraph();
      setStatus(actionNode, "Member photo uploaded successfully.", "success");
    } catch (error) {
      console.error("Member photo upload failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to upload member photo.",
        "error",
      );
    }
  }

  async function handleUploadVerificationEvidence(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!currentFamilyId) {
      setStatus(
        actionNode,
        "Load a family before uploading verification evidence.",
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
        actionNode,
        "Member, verification type, evidence kind, and file are required.",
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
      setStatus(actionNode, "Uploading verification evidence...", "info");

      await app.apiRequest("/uploads/verification-evidence", {
        method: "POST",
        body,
      });

      form.reset();
      setStatus(
        actionNode,
        "Verification evidence uploaded successfully.",
        "success",
      );
    } catch (error) {
      console.error("Verification evidence upload failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to upload verification evidence.",
        "error",
      );
    }
  }

  async function deleteRelationship(relationshipId) {
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!relationshipId) {
      setStatus(actionNode, "Missing relationship id.", "error");
      return;
    }

    const confirmed = window.confirm(
      "Delete this relationship? This action cannot be undone.",
    );
    if (!confirmed) return;

    try {
      setStatus(actionNode, "Deleting relationship...", "info");

      await app.apiRequest(
        `/relationships/${encodeURIComponent(relationshipId)}`,
        {
          method: "DELETE",
        },
      );

      await loadFamilyGraph();
      setStatus(actionNode, "Relationship deleted successfully.", "success");
    } catch (error) {
      console.error("Delete relationship failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to delete relationship.",
        "error",
      );
    }
  }

  async function deleteMember(memberId, memberName) {
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!memberId) {
      setStatus(actionNode, "Missing member id.", "error");
      return;
    }

    const confirmed = window.confirm(
      `Delete ${memberName || "this member"}?\n\nIf relationships still point to this member, delete those relationships first.`,
    );
    if (!confirmed) return;

    try {
      setStatus(actionNode, "Deleting family member...", "info");

      await app.apiRequest(`/family-members/${encodeURIComponent(memberId)}`, {
        method: "DELETE",
      });

      await loadFamilyGraph();
      setStatus(actionNode, "Family member deleted successfully.", "success");
    } catch (error) {
      console.error("Delete member failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to delete family member.",
        "error",
      );
    }
  }

  async function downloadUpload(uploadId, originalFilename) {
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!uploadId) {
      setStatus(actionNode, "Missing upload id.", "error");
      return;
    }

    try {
      setStatus(actionNode, "Downloading file...", "info");

      const token = app.getToken ? app.getToken() : "";
      const apiBaseUrl =
        typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";

      const response = await fetch(
        `${apiBaseUrl}/uploads/${encodeURIComponent(uploadId)}/download`,
        {
          method: "GET",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        },
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Unable to download upload.");
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

      setStatus(actionNode, "Download started.", "success");
    } catch (error) {
      console.error("Download upload failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to download upload.",
        "error",
      );
    }
  }

  async function deleteUpload(uploadId) {
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    if (!uploadId) {
      setStatus(actionNode, "Missing upload id.", "error");
      return;
    }

    const confirmed = window.confirm(
      "Delete this uploaded file? This action cannot be undone.",
    );
    if (!confirmed) return;

    try {
      setStatus(actionNode, "Deleting upload...", "info");

      await app.apiRequest(`/uploads/${encodeURIComponent(uploadId)}`, {
        method: "DELETE",
      });

      await loadMemberUploads();
      await loadFamilyGraph();
      setStatus(actionNode, "Upload deleted successfully.", "success");
    } catch (error) {
      console.error("Delete upload failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to delete upload.",
        "error",
      );
    }
  }

  async function runVerificationAction(memberId, actionType) {
    const actionNode = document.querySelector(
      "[data-admin-family-action-status]",
    );

    const member = (currentGraph.members || []).find(function (item) {
      return String(item.id) === String(memberId);
    });

    if (!member) {
      setStatus(actionNode, "Unable to locate selected member.", "error");
      return;
    }

    const displayName = getDisplayName(member);

    let path = "";
    let payload = null;

    if (actionType === "verify") {
      payload = getVerificationPayload(member, actionType);
      if (!payload) return;
      path = `/verification-records/member/${encodeURIComponent(memberId)}/verify`;
    } else if (actionType === "pending") {
      payload = getVerificationPayload(member, actionType);
      if (!payload) return;
      path = `/verification-records/member/${encodeURIComponent(memberId)}/pending`;
    } else if (actionType === "reject") {
      payload = getVerificationPayload(member, actionType);
      if (!payload) return;
      path = `/verification-records/member/${encodeURIComponent(memberId)}/reject`;
    } else if (actionType === "clear") {
      payload = getClearVerificationPayload(member);
      if (!payload) return;
      path = `/verification-records/member/${encodeURIComponent(memberId)}/clear`;
    } else {
      setStatus(actionNode, "Unsupported verification action.", "error");
      return;
    }

    try {
      const actionLabel =
        actionType === "verify"
          ? "Verifying member..."
          : actionType === "pending"
            ? "Marking member pending..."
            : actionType === "reject"
              ? "Rejecting verification..."
              : "Clearing verification...";

      setStatus(actionNode, actionLabel, "info");

      await app.apiRequest(path, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      await loadFamilyGraph();

      const doneLabel =
        actionType === "verify"
          ? `${displayName} verified successfully.`
          : actionType === "pending"
            ? `${displayName} marked pending verification.`
            : actionType === "reject"
              ? `${displayName} verification rejected.`
              : `${displayName} verification cleared.`;

      setStatus(actionNode, doneLabel, "success");
    } catch (error) {
      console.error("Verification action failed:", error);
      setStatus(
        actionNode,
        error.message || "Unable to update verification state.",
        "error",
      );
    }
  }

  async function setupAdminFamilyManagerPage() {
    const page = document.querySelector("[data-admin-family-manager-page]");
    if (!page) return;

    try {
      await requireAdmin();
      await loadFamilyBuildOptions();

      const loadButton = document.querySelector("[data-admin-family-load]");
      const memberForm = document.querySelector("[data-admin-member-form]");
      const relationshipForm = document.querySelector(
        "[data-admin-relationship-form]",
      );
      const photoForm = document.querySelector("[data-admin-photo-form]");
      const evidenceForm = document.querySelector("[data-admin-evidence-form]");
      const loadUploadsButton = document.querySelector(
        "[data-admin-load-member-uploads]",
      );

      if (loadButton) {
        loadButton.addEventListener("click", function () {
          loadFamilyGraph();
        });
      }

      if (memberForm) {
        memberForm.addEventListener("submit", handleCreateMember);
      }

      if (relationshipForm) {
        relationshipForm.addEventListener("submit", handleCreateRelationship);
      }

      if (photoForm) {
        photoForm.addEventListener("submit", handleUploadMemberPhoto);
      }

      if (evidenceForm) {
        evidenceForm.addEventListener(
          "submit",
          handleUploadVerificationEvidence,
        );
      }

      if (loadUploadsButton) {
        loadUploadsButton.addEventListener("click", function () {
          loadMemberUploads();
        });
      }

      document.addEventListener("click", function (event) {
        const relationshipButton = event.target.closest(
          "[data-delete-relationship-id]",
        );
        if (relationshipButton) {
          deleteRelationship(
            relationshipButton.getAttribute("data-delete-relationship-id"),
          );
          return;
        }

        const memberButton = event.target.closest("[data-delete-member-id]");
        if (memberButton) {
          deleteMember(
            memberButton.getAttribute("data-delete-member-id"),
            memberButton.getAttribute("data-delete-member-name"),
          );
          return;
        }

        const verifyButton = event.target.closest("[data-verify-member-id]");
        if (verifyButton) {
          runVerificationAction(
            verifyButton.getAttribute("data-verify-member-id"),
            "verify",
          );
          return;
        }

        const pendingButton = event.target.closest("[data-pending-member-id]");
        if (pendingButton) {
          runVerificationAction(
            pendingButton.getAttribute("data-pending-member-id"),
            "pending",
          );
          return;
        }

        const rejectButton = event.target.closest("[data-reject-member-id]");
        if (rejectButton) {
          runVerificationAction(
            rejectButton.getAttribute("data-reject-member-id"),
            "reject",
          );
          return;
        }

        const clearButton = event.target.closest(
          "[data-clear-verification-member-id]",
        );
        if (clearButton) {
          runVerificationAction(
            clearButton.getAttribute("data-clear-verification-member-id"),
            "clear",
          );
          return;
        }

        const downloadButton = event.target.closest(
          "[data-download-upload-id]",
        );
        if (downloadButton) {
          downloadUpload(
            downloadButton.getAttribute("data-download-upload-id"),
            downloadButton.getAttribute("data-download-upload-name"),
          );
          return;
        }

        const deleteUploadButton = event.target.closest(
          "[data-delete-upload-id]",
        );
        if (deleteUploadButton) {
          deleteUpload(
            deleteUploadButton.getAttribute("data-delete-upload-id"),
          );
        }
      });

      const selectNode = document.querySelector("[data-admin-family-select]");
      if (selectNode && selectNode.value) {
        await loadFamilyGraph();
      }
    } catch (error) {
      console.error("Admin family manager setup failed:", error);

      const statusNode = document.querySelector("[data-admin-family-status]");
      const actionNode = document.querySelector(
        "[data-admin-family-action-status]",
      );

      if (statusNode) {
        statusNode.textContent = "Admin access could not be confirmed.";
      }

      setStatus(
        actionNode,
        error.message || "Admin access is required.",
        "error",
      );
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupAdminFamilyManagerPage();
  });
})();
