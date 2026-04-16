(function () {
  const app = window.TOLApp || window.TOLAuth;
  if (!app) return;

  const statusNode = document.querySelector("[data-household-status]");
  const inviteForm = document.querySelector("[data-household-invite-form]");
  const inviteStatus = document.querySelector("[data-household-invite-status]");
  const acceptForm = document.querySelector("[data-household-accept-form]");
  const acceptStatus = document.querySelector("[data-household-accept-status]");
  const membersList = document.querySelector("[data-household-members-list]");
  const invitesList = document.querySelector("[data-household-invites-list]");
  const membersEmpty = document.querySelector("[data-household-members-empty]");
  const invitesEmpty = document.querySelector("[data-household-invites-empty]");
  const pendingCount = document.querySelector("[data-household-pending-count]");
  const inviteCoOwnerButton = document.querySelector("[data-household-invite-co-owner]");
  const inviteFamilyButton = document.querySelector("[data-household-invite-family]");

  const ROLE_OPTIONS = [
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
    "viewer",
    "minor_viewer",
    "linked_relative",
  ];

  const ROLE_LABELS = {
    billing_owner: "Billing Owner",
    co_owner: "Co-Owner",
    family_manager: "Family Manager",
    contributor: "Contributor",
    viewer: "Viewer",
    minor_viewer: "Minor Viewer",
    linked_relative: "Linked Relative",
  };

  const RELATIONSHIP_LABELS = {
    spouse: "Spouse",
    parent: "Parent",
    child: "Child",
    sibling: "Sibling",
    household_member: "Household Member",
    guardian: "Guardian",
    relative: "Relative",
    other: "Other",
  };

  const PRIVACY_LABELS = {
    household_private: "Household Private",
    household_shared: "Shared Household Access",
    read_only: "Read Only",
    link_only: "Link-Only Access",
    private_to_owner: "Owner Private",
    private_to_owner_and_co_owner: "Owner + Co-Owner Private",
    branch_shared: "Shared Household Access",
    linked_family_shared: "Link-Only Access",
    public_memorial: "Read Only",
    minor_protected: "Household Private",
  };

  const DEFAULT_NOTE_BY_ROLE_RELATIONSHIP = {
    co_owner: {
      spouse: "Spouse invited as co-owner for household management and family tree collaboration.",
    },
    family_manager: {
      parent: "Parent invited to help manage household records and family information.",
    },
    viewer: {
      relative: "Relative invited with read-only household access.",
    },
    contributor: {
      child: "Child invited to contribute approved family content.",
    },
  };

  let currentProjectId = "";
  let currentUser = null;

  function normalizeBaseUrl(value) {
    return String(value || "")
      .trim()
      .replace(/\/+$/, "");
  }

  function isFrontendOriginBaseUrl(value) {
    const normalized = normalizeBaseUrl(value);
    if (!normalized) return false;
    try {
      return new URL(normalized).origin === window.location.origin;
    } catch (_error) {
      return false;
    }
  }

  function ensureApiConfigForHouseholdAccess() {
    if (typeof app.isLocalApp === "function" && app.isLocalApp()) return;
    const currentConfig = window.TOL_CONFIG || {};
    const configuredBase = normalizeBaseUrl(currentConfig.API_BASE_URL);
    const configuredList = Array.isArray(currentConfig.API_BASE_URLS)
      ? currentConfig.API_BASE_URLS.map(normalizeBaseUrl).filter(Boolean)
      : [];
    const configuredCandidates = [configuredBase, ...configuredList].filter(Boolean);
    const isInvalid = !configuredCandidates.length || configuredCandidates.some(isFrontendOriginBaseUrl);
    if (!isInvalid) return;
    const runtimeBase =
      typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "";
    if (!runtimeBase || isFrontendOriginBaseUrl(runtimeBase)) {
      console.warn("[HouseholdAccess] API base config is invalid for live mode.", {
        API_BASE_URL: currentConfig.API_BASE_URL,
        API_BASE_URLS: currentConfig.API_BASE_URLS,
      });
      return;
    }
    const mergedCandidates = Array.from(
      new Set([runtimeBase, ...configuredList].filter((value) => value && !isFrontendOriginBaseUrl(value))),
    );
    window.TOL_CONFIG = Object.assign({}, currentConfig, {
      API_BASE_URL: mergedCandidates[0],
      API_BASE_URLS: mergedCandidates,
    });
    console.warn("[HouseholdAccess] Applied live API base fallback config.", {
      API_BASE_URL: window.TOL_CONFIG.API_BASE_URL,
      API_BASE_URLS: window.TOL_CONFIG.API_BASE_URLS,
    });
  }

  function buildInviteRequestUrl(path, error) {
    const explicitUrl = String(error?.requestUrl || "").trim();
    if (explicitUrl) return explicitUrl;
    if (/^https?:\/\//i.test(String(path || ""))) return String(path);
    const baseFromApp =
      typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "";
    const baseFromConfig = normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL);
    const base = baseFromApp || baseFromConfig;
    return base ? `${base}${path}` : String(path || "");
  }

  function inviteDebugMeta(path, payload, error) {
    const resolvedApiBaseUrl =
      typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "";
    const configuredApiBaseUrl = normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL);
    const tokenPresent =
      typeof app.getToken === "function" ? Boolean(String(app.getToken() || "").trim()) : false;
    return {
      resolvedApiBaseUrl,
      configuredApiBaseUrl,
      requestUrl: buildInviteRequestUrl(path, error),
      method: "POST",
      authTokenPresent: tokenPresent,
      payload: payload || null,
    };
  }

  function userInviteErrorMessage(error, fallback) {
    const detail = String(error?.detail || error?.message || "").trim();
    const statusCode = Number(error?.status || 0);
    if (statusCode === 404) {
      return "The invite feature is currently unavailable. Please contact support.";
    }
    if (statusCode === 403) {
      return "Your current role cannot send this invite. Please use a billing owner account.";
    }
    if (statusCode === 400) {
      return detail || "The invite details are invalid. Please check the form and try again.";
    }
    return detail || fallback;
  }

  function logInviteFailure(action, path, error, payload) {
    console.error("[HouseholdAccess] Invite request failed.", {
      action,
      ...inviteDebugMeta(path, payload, error),
      status: error?.status ?? null,
      statusText: error?.statusText || "",
      responseBody: error?.data ?? error?.responseBody ?? error?.detail ?? error?.message ?? null,
    });
  }

  function logInviteRequest(action, path, payload) {
    console.info("[HouseholdAccess] Invite request.", {
      action,
      ...inviteDebugMeta(path, payload),
    });
  }

  function logInviteSuccess(action, path, responseBody, payload) {
    console.info("[HouseholdAccess] Invite request succeeded.", {
      action,
      ...inviteDebugMeta(path, payload),
      status: 201,
      responseBody,
    });
  }

  function setText(node, message, type = "info") {
    if (!node) return;
    app.setStatus(node, message, type);
  }

  function clear(node) {
    if (!node) return;
    app.clearStatus(node);
  }

  function roleLabel(role) {
    return ROLE_LABELS[String(role || "").trim()] || "Viewer";
  }

  function relationshipLabel(value) {
    return RELATIONSHIP_LABELS[String(value || "").trim()] || "Household Member";
  }

  function privacyLabel(value) {
    return PRIVACY_LABELS[String(value || "").trim()] || "Household Private";
  }

  function titleLabel(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, function (char) {
        return char.toUpperCase();
      });
  }

  function roleNode() {
    return inviteForm ? inviteForm.querySelector('select[name="member_role"]') : null;
  }

  function relationshipNode() {
    return inviteForm ? inviteForm.querySelector('select[name="relationship_scope"]') : null;
  }

  function privacyNode() {
    return inviteForm ? inviteForm.querySelector('select[name="privacy_scope"]') : null;
  }

  function noteNode() {
    return inviteForm ? inviteForm.querySelector('input[name="notes"]') : null;
  }

  function isNoteCustomized() {
    const node = noteNode();
    return Boolean(node && node.dataset.customized === "true");
  }

  function buildAutoNote(memberRole, relationshipScope, privacyScope) {
    const roleValue = String(memberRole || "viewer").trim();
    const relationshipValue = String(relationshipScope || "household_member").trim();
    const preset = DEFAULT_NOTE_BY_ROLE_RELATIONSHIP[roleValue]?.[relationshipValue];
    if (preset) return preset;
    if (roleValue === "linked_relative") {
      return `${relationshipLabel(relationshipValue)} invited for link-only household access.`;
    }
    if (roleValue === "viewer" || String(privacyScope || "").trim() === "read_only") {
      return `${relationshipLabel(relationshipValue)} invited with read-only household access.`;
    }
    return `${relationshipLabel(relationshipValue)} invited as ${titleLabel(roleValue).toLowerCase()} for household collaboration.`;
  }

  function updateAutoInviteDefaults(force = false) {
    if (!inviteForm) return;
    const roleValue = String(roleNode()?.value || "viewer").trim();
    const relationshipValue = String(relationshipNode()?.value || "household_member").trim();
    const privacy = privacyNode();
    if (roleValue === "co_owner" && relationshipValue === "spouse" && privacy) {
      privacy.value = "household_private";
    }
    const privacyValue = String(privacy?.value || "household_private").trim();
    const notes = noteNode();
    if (!notes) return;
    const generated = buildAutoNote(roleValue, relationshipValue, privacyValue);
    if (force || !isNoteCustomized() || !String(notes.value || "").trim()) {
      notes.value = generated;
      notes.dataset.customized = "false";
    }
  }

  function projectIdFromContext(user) {
    const params = new URLSearchParams(window.location.search);
    const directProjectId = String(params.get("project_id") || "").trim();
    if (directProjectId) return directProjectId;

    const context = window.TOLDashboardContext || null;
    const activeProject = context?.activeProject || null;
    if (activeProject && activeProject.id) return String(activeProject.id).trim();
    return String(user?.active_project_id || "").trim();
  }

  function inviteKeyFromQuery() {
    const params = new URLSearchParams(window.location.search);
    return String(params.get("invite_key") || "").trim();
  }

  function isPending(invite) {
    return String(invite?.status || "").toLowerCase() === "pending";
  }

  function isExpired(invite) {
    return String(invite?.status || "").toLowerCase() === "expired";
  }

  function renderPendingCount(items) {
    if (!pendingCount) return;
    const pendingTotal = (items || []).filter(isPending).length;
    pendingCount.textContent = `${pendingTotal} pending invite${pendingTotal === 1 ? "" : "s"}.`;
  }

  async function changeMemberRole(membershipId, memberRole) {
    await app.apiRequest(
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/members/${encodeURIComponent(membershipId)}/role`,
      {
        method: "POST",
        body: JSON.stringify({ member_role: memberRole }),
      },
    );
  }

  async function removeMember(membershipId) {
    await app.apiRequest(
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/members/${encodeURIComponent(membershipId)}/revoke`,
      {
        method: "POST",
      },
    );
  }

  async function resendInvite(inviteId) {
    await app.apiRequest(`/workspace-access/invites/${encodeURIComponent(inviteId)}/resend`, {
      method: "POST",
    });
  }

  async function revokeInvite(inviteId) {
    await app.apiRequest(`/workspace-access/invites/${encodeURIComponent(inviteId)}/revoke`, {
      method: "POST",
    });
  }

  function renderMembers(items) {
    if (!membersList) return;
    membersList.innerHTML = "";
    if (!Array.isArray(items) || !items.length) {
      if (membersEmpty) membersEmpty.style.display = "block";
      return;
    }
    if (membersEmpty) membersEmpty.style.display = "none";
    items.forEach((member) => {
      const card = document.createElement("article");
      card.className = "form-panel";

      const emailLabel = member.email || member.user_id || "Unassigned member";
      const role = String(member.member_role || "viewer").trim();
      const isBillingOwner = role === "billing_owner";
      const options = ROLE_OPTIONS.map(
        (roleCode) =>
          `<option value="${roleCode}" ${roleCode === role ? "selected" : ""}>${roleLabel(roleCode)}</option>`,
      ).join("");
      card.innerHTML = `
        <strong>${emailLabel}</strong>
        <p class="card-copy">Role: ${roleLabel(role)}</p>
        <p class="card-copy">Relationship: ${relationshipLabel(member.relationship_scope || "household_member")}</p>
        <p class="card-copy">Privacy: ${privacyLabel(member.privacy_scope || "household_private")}</p>
        <p class="card-copy">Status: ${member.status || "active"}</p>
        <label>Change Role
          <select ${isBillingOwner ? "disabled" : ""} data-member-role-select>${options}</select>
        </label>
        <div class="inline-actions" style="margin-top:0.75rem;">
          <button class="btn btn-secondary" type="button" data-member-role-save ${isBillingOwner ? "disabled" : ""}>Change Role</button>
          <button class="btn btn-secondary" type="button" data-member-remove ${isBillingOwner ? "disabled" : ""}>Remove Member</button>
        </div>
      `;

      const roleSave = card.querySelector("[data-member-role-save]");
      const roleSelect = card.querySelector("[data-member-role-select]");
      const removeButton = card.querySelector("[data-member-remove]");
      if (roleSave && roleSelect && !isBillingOwner) {
        roleSave.addEventListener("click", async function () {
          try {
            await changeMemberRole(member.id, roleSelect.value);
            await refreshData();
            setText(inviteStatus, "Member role updated.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to change role.", "error");
          }
        });
      }
      if (removeButton && !isBillingOwner) {
        removeButton.addEventListener("click", async function () {
          try {
            await removeMember(member.id);
            await refreshData();
            setText(inviteStatus, "Member removed.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to remove member.", "error");
          }
        });
      }
      membersList.appendChild(card);
    });
  }

  function renderInvites(items) {
    if (!invitesList) return;
    invitesList.innerHTML = "";
    if (!Array.isArray(items) || !items.length) {
      if (invitesEmpty) invitesEmpty.style.display = "block";
      renderPendingCount([]);
      return;
    }
    if (invitesEmpty) invitesEmpty.style.display = "none";
    renderPendingCount(items);
    items.forEach((invite) => {
      const card = document.createElement("article");
      card.className = "form-panel";
      const canResend = isPending(invite) || isExpired(invite);
      const canRevoke = isPending(invite) || isExpired(invite);
      card.innerHTML = `
        <strong>${invite.email || "Invite"}</strong>
        <p class="card-copy">Role: ${roleLabel(invite.member_role || "viewer")}</p>
        <p class="card-copy">Relationship: ${relationshipLabel(invite.relationship_scope || "household_member")}</p>
        <p class="card-copy">Privacy: ${privacyLabel(invite.privacy_scope || "household_private")}</p>
        <p class="card-copy">Status: ${invite.status || "pending"}</p>
        <p class="card-copy">Expires: ${invite.expires_at || "—"}</p>
        <div class="inline-actions" style="margin-top:0.75rem;">
          <button class="btn btn-secondary" type="button" data-invite-resend ${canResend ? "" : "disabled"}>Resend Invite</button>
          <button class="btn btn-secondary" type="button" data-invite-revoke ${canRevoke ? "" : "disabled"}>Revoke Invite</button>
        </div>
      `;

      const resendButton = card.querySelector("[data-invite-resend]");
      const revokeButton = card.querySelector("[data-invite-revoke]");
      if (resendButton && canResend) {
        resendButton.addEventListener("click", async function () {
          try {
            await resendInvite(invite.id);
            await refreshData();
            setText(inviteStatus, "Invite resent.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to resend invite.", "error");
          }
        });
      }
      if (revokeButton && canRevoke) {
        revokeButton.addEventListener("click", async function () {
          try {
            await revokeInvite(invite.id);
            await refreshData();
            setText(inviteStatus, "Invite revoked.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to revoke invite.", "error");
          }
        });
      }

      invitesList.appendChild(card);
    });
  }

  async function refreshData() {
    if (!currentProjectId) return;
    const [membersPayload, invitesPayload] = await Promise.all([
      app.apiRequest(`/workspace-access/project/${encodeURIComponent(currentProjectId)}/members`),
      app.apiRequest(`/workspace-access/project/${encodeURIComponent(currentProjectId)}/invites`),
    ]);
    renderMembers(membersPayload?.items || []);
    renderInvites(invitesPayload?.items || []);
  }

  function selectedInviteRole() {
    if (!inviteForm) return "viewer";
    const node = roleNode();
    return String(node?.value || "viewer").trim();
  }

  async function handleInviteSubmit(event) {
    event.preventDefault();
    clear(inviteStatus);
    if (!currentProjectId) {
      setText(inviteStatus, "Select a workspace project first.", "error");
      return;
    }
    updateAutoInviteDefaults();
    const formData = new FormData(inviteForm);
    const payload = {
      email: String(formData.get("email") || "").trim(),
      member_role: selectedInviteRole(),
      relationship_scope: String(formData.get("relationship_scope") || "household_member").trim(),
      privacy_scope: String(formData.get("privacy_scope") || "household_private").trim(),
      notes: String(formData.get("notes") || "").trim(),
    };
    const invitePaths = [
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/invites`,
      // Backward-compatible singular route retained by backend legacy wiring.
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/invite`,
      `/workspace_access/project/${encodeURIComponent(currentProjectId)}/invites`,
      `/household-access/project/${encodeURIComponent(currentProjectId)}/invites`,
    ];
    try {
      let invite = null;
      let lastError = null;
      for (const invitePath of invitePaths) {
        logInviteRequest(`invite_${payload.member_role}`, invitePath, payload);
        try {
          invite = await app.apiRequest(invitePath, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          logInviteSuccess(`invite_${payload.member_role}`, invitePath, invite, payload);
          break;
        } catch (error) {
          lastError = error;
          logInviteFailure(`invite_${payload.member_role}`, invitePath, error, payload);
          if (Number(error?.status || 0) !== 404) throw error;
        }
      }
      if (!invite) {
        throw lastError || new Error("Invite endpoint is unavailable.");
      }
      const inviteStatusValue = String(invite?.status || "").trim().toLowerCase();
      if (inviteStatusValue !== "pending") {
        throw new Error(
          `Unable to create invite (unexpected status: ${inviteStatusValue || "unknown"}). Please try again or contact support if this persists.`,
        );
      }
      const emailDeliveryFailed =
        String(invite?.email_delivery_status || "").trim().toLowerCase() === "failed";
      const successMessage = emailDeliveryFailed
        ? String(invite?.message || "Invite created, but email delivery failed.").trim()
        : "Invite created successfully and added to pending invites.";
      setText(inviteStatus, successMessage, emailDeliveryFailed ? "warning" : "success");
      inviteForm.reset();
      updateAutoInviteDefaults(true);
      await refreshData();
    } catch (error) {
      setText(
        inviteStatus,
        userInviteErrorMessage(
          error,
          "We couldn’t create that invite right now. Please verify the email and try again.",
        ),
        "error",
      );
    }
  }

  async function handleAcceptSubmit(event) {
    event.preventDefault();
    clear(acceptStatus);
    const formData = new FormData(acceptForm);
    const inviteKey = String(formData.get("invite_key") || "").trim();
    if (!inviteKey) {
      setText(acceptStatus, "Invite key is required.", "error");
      return;
    }
    try {
      await app.apiRequest("/workspace-access/invites/accept", {
        method: "POST",
        body: JSON.stringify({ invite_key: inviteKey }),
      });
      setText(acceptStatus, "Invite accepted. Workspace access granted.", "success");
      await refreshData();
    } catch (error) {
      setText(acceptStatus, error.message || "Failed to accept invite.", "error");
    }
  }

  function bindQuickInviteButtons() {
    if (!inviteForm) return;
    const roleSelect = roleNode();
    const relationshipSelect = relationshipNode();
    const privacySelect = privacyNode();
    const notesInput = noteNode();

    if (roleSelect) {
      roleSelect.addEventListener("change", function () {
        updateAutoInviteDefaults();
      });
    }
    if (relationshipSelect) {
      relationshipSelect.addEventListener("change", function () {
        updateAutoInviteDefaults();
      });
    }
    if (privacySelect) {
      privacySelect.addEventListener("change", function () {
        updateAutoInviteDefaults();
      });
    }
    if (notesInput) {
      notesInput.addEventListener("input", function () {
        notesInput.dataset.customized = String(Boolean(String(notesInput.value || "").trim()));
      });
    }
    if (inviteCoOwnerButton) {
      inviteCoOwnerButton.addEventListener("click", function () {
        if (roleSelect) roleSelect.value = "co_owner";
        if (relationshipSelect) relationshipSelect.value = "spouse";
        updateAutoInviteDefaults(true);
        inviteForm.requestSubmit();
      });
    }
    if (inviteFamilyButton) {
      inviteFamilyButton.addEventListener("click", function () {
        if (roleSelect) roleSelect.value = "contributor";
        updateAutoInviteDefaults(true);
        inviteForm.requestSubmit();
      });
    }
  }

  async function initialize() {
    ensureApiConfigForHouseholdAccess();
    currentUser = await app.requireSession("signin.html");
    if (!currentUser) return;
    currentProjectId = projectIdFromContext(currentUser);
    if (!currentProjectId) {
      if (statusNode) {
        statusNode.textContent =
          "No active workspace project was detected. Open this page from your dashboard workspace.";
      }
      return;
    }
    if (statusNode) {
      statusNode.textContent = `Managing workspace access for project ${currentProjectId}.`;
    }

    const inviteKey = inviteKeyFromQuery();
    if (acceptForm && inviteKey) {
      const keyInput = acceptForm.querySelector('input[name="invite_key"]');
      if (keyInput) keyInput.value = inviteKey;
    }

    bindQuickInviteButtons();
    updateAutoInviteDefaults(true);
    console.info("[HouseholdAccess] Invite runtime API context.", {
      resolvedApiBaseUrl:
        typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "",
      configuredApiBaseUrl: normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL),
      configuredApiBaseUrls: Array.isArray(window.TOL_CONFIG?.API_BASE_URLS)
        ? window.TOL_CONFIG.API_BASE_URLS.map(normalizeBaseUrl).filter(Boolean)
        : [],
      projectId: currentProjectId,
    });
    if (inviteForm) inviteForm.addEventListener("submit", handleInviteSubmit);
    if (acceptForm) acceptForm.addEventListener("submit", handleAcceptSubmit);
    await refreshData();
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
