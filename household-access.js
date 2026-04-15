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

  let currentProjectId = "";

  function setText(node, message, type = "info") {
    if (!node) return;
    app.setStatus(node, message, type);
  }

  function clear(node) {
    if (!node) return;
    app.clearStatus(node);
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
      card.innerHTML = `
        <strong>${member.email || member.user_id || "Unassigned member"}</strong>
        <p class="card-copy">Role: ${member.member_role || "viewer"}</p>
        <p class="card-copy">Relationship: ${member.relationship_scope || "household_member"}</p>
        <p class="card-copy">Privacy: ${member.privacy_scope || "household_private"}</p>
        <p class="card-copy">Status: ${member.status || "active"}</p>
      `;
      membersList.appendChild(card);
    });
  }

  function renderInvites(items) {
    if (!invitesList) return;
    invitesList.innerHTML = "";
    if (!Array.isArray(items) || !items.length) {
      if (invitesEmpty) invitesEmpty.style.display = "block";
      return;
    }
    if (invitesEmpty) invitesEmpty.style.display = "none";
    items.forEach((invite) => {
      const card = document.createElement("article");
      card.className = "form-panel";
      card.innerHTML = `
        <strong>${invite.email || "Invite"}</strong>
        <p class="card-copy">Role: ${invite.member_role || "viewer"}</p>
        <p class="card-copy">Status: ${invite.status || "pending"}</p>
        <p class="card-copy">Expires: ${invite.expires_at || "—"}</p>
        <p class="card-copy">Invite Key: ${invite.invite_key || "hidden"}</p>
      `;
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

  async function handleInviteSubmit(event) {
    event.preventDefault();
    clear(inviteStatus);
    if (!currentProjectId) {
      setText(inviteStatus, "Select a workspace project first.", "error");
      return;
    }
    const formData = new FormData(inviteForm);
    const payload = {
      email: String(formData.get("email") || "").trim(),
      member_role: String(formData.get("member_role") || "viewer").trim(),
      relationship_scope: String(formData.get("relationship_scope") || "household_member").trim(),
      privacy_scope: String(formData.get("privacy_scope") || "household_private").trim(),
    };
    try {
      await app.apiRequest(`/workspace-access/project/${encodeURIComponent(currentProjectId)}/invites`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setText(inviteStatus, "Invite created. Share the key with the invited person.", "success");
      inviteForm.reset();
      await refreshData();
    } catch (error) {
      setText(inviteStatus, error.message || "Failed to create invite.", "error");
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

  async function initialize() {
    const user = await app.requireSession("signin.html");
    if (!user) return;
    currentProjectId = projectIdFromContext(user);
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

    if (inviteForm) inviteForm.addEventListener("submit", handleInviteSubmit);
    if (acceptForm) acceptForm.addEventListener("submit", handleAcceptSubmit);
    await refreshData();
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
