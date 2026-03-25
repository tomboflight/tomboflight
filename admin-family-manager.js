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
            <p class="card-copy"><strong>Member ID:</strong> ${escapeHtml(member.id || "—")}</p>
            <p class="card-copy"><strong>Bio:</strong> ${escapeHtml(member.bio || "—")}</p>
            <div class="inline-actions" style="margin-top: 1rem;">
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

  function populateRelationshipMemberSelects(graph) {
    const sourceSelect = document.querySelector("[data-admin-source-member]");
    const targetSelect = document.querySelector("[data-admin-target-member]");
    if (!sourceSelect || !targetSelect) return;

    const members = sortMembers(
      Array.isArray(graph.members) ? graph.members : [],
    );

    const options = members
      .map(function (member) {
        return `<option value="${escapeHtml(member.id)}">${escapeHtml(getDisplayName(member))} — Gen ${escapeHtml(member.generation ?? "—")}</option>`;
      })
      .join("");

    sourceSelect.innerHTML = `<option value="">Select source member</option>${options}`;
    targetSelect.innerHTML = `<option value="">Select target member</option>${options}`;
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
