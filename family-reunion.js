(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};
  if (!app || typeof app.apiRequest !== "function") return;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function humanize(value) {
    return String(value || "unknown")
      .split("_")
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function projectIdFromContext(context) {
    return String(
      context?.activeProject?.project_id ||
      context?.activeProject?.projectId ||
      context?.activeProject?.id ||
      context?.activeProject?._id ||
      context?.currentWorkspace?.projectId ||
      "",
    ).trim();
  }

  function statusPill(value, readyValue) {
    const ready = value === readyValue;
    return `<span class="eyebrow" data-state="${ready ? "success" : "pending"}">${escapeHtml(humanize(value))}</span>`;
  }

  function render(payload) {
    const summaryNode = document.querySelector("[data-reunion-summary]");
    const householdsNode = document.querySelector("[data-reunion-households]");
    const emptyNode = document.querySelector("[data-reunion-empty]");
    const statusNode = document.querySelector("[data-reunion-status]");
    const summary = payload.summary || {};

    statusNode.textContent = payload.ready
      ? "Every visible family member is ready for the family reunion."
      : `${summary.incomplete_member_count || 0} visible family member(s) still need attention.`;

    summaryNode.innerHTML = [
      ["Households", summary.household_count || 0],
      ["Members Ready", `${summary.complete_member_count || 0} / ${summary.member_count || 0}`],
      ["Cinematic Slides Ready", summary.slide_ready_count || 0],
    ].map(function (item, index) {
      return `<div class="family-record-card"><div class="card-number">${index + 1}</div><h3>${escapeHtml(item[0])}</h3><p class="card-copy">${escapeHtml(item[1])}</p></div>`;
    }).join("");

    const households = Array.isArray(payload.households) ? payload.households : [];
    if (!households.length) {
      householdsNode.innerHTML = "";
      emptyNode.style.display = "";
      return;
    }
    emptyNode.style.display = "none";

    householdsNode.innerHTML = households.map(function (household) {
      const completion = household.completion || {};
      const members = Array.isArray(household.members) ? household.members : [];
      const memberCards = members.map(function (member) {
        const reasons = Array.isArray(member.incomplete_reasons)
          ? member.incomplete_reasons
          : [];
        return `
          <div class="family-record-card">
            <span class="eyebrow">Generation ${escapeHtml(member.generation ?? "unplaced")}</span>
            <h3>${escapeHtml(member.display_name)}</h3>
            <p class="card-copy"><strong>Portrait:</strong> ${statusPill(member.portrait_status, "approved")}</p>
            <p class="card-copy"><strong>Tree placement:</strong> ${statusPill(member.placement_status === "root" ? "placed" : member.placement_status, "placed")}</p>
            <p class="card-copy"><strong>Account:</strong> ${escapeHtml(humanize(member.account_status))}</p>
            <p class="card-copy"><strong>Verification:</strong> ${escapeHtml(humanize(member.verification_status))}</p>
            <p class="card-copy"><strong>Automatic slide:</strong> ${member.slide_ready ? "Ready" : "Not ready"}</p>
            ${reasons.length ? `<p class="card-copy"><strong>Needs:</strong> ${escapeHtml(reasons.map(humanize).join(", "))}</p>` : '<p class="card-copy"><strong>Status:</strong> Complete</p>'}
          </div>
        `;
      }).join("");
      return `
        <section class="form-panel" style="margin-top: 1.5rem">
          <span class="eyebrow">${escapeHtml(household.alignment_status || "unplaced")}</span>
          <h2>${escapeHtml(household.household_name || "Linked Household")}</h2>
          <p class="card-copy">${escapeHtml(completion.complete_members || 0)} of ${escapeHtml(completion.total_members || 0)} visible members complete (${escapeHtml(completion.percent || 0)}%).</p>
          <div class="grid-3" style="margin-top: 1rem">${memberCards}</div>
        </section>
      `;
    }).join("");
  }

  async function setup() {
    const page = document.querySelector("[data-family-reunion-page]");
    if (!page) return;
    const statusNode = document.querySelector("[data-reunion-status]");
    try {
      const me = await app.apiRequest("/auth/me", { method: "GET" });
      const orders = authPages.fetchOrders ? await authPages.fetchOrders() : [];
      const context =
        typeof authPages.getDashboardContextForCurrentPage === "function"
          ? await authPages.getDashboardContextForCurrentPage(me, orders)
          : await authPages.getDashboardContext(me, orders);
      const queryProjectId = new URLSearchParams(window.location.search).get("project_id");
      const projectId = queryProjectId || projectIdFromContext(context);
      if (!projectId) throw new Error("No active project is attached to this account.");
      const payload = await app.apiRequest(
        `/projects/${encodeURIComponent(projectId)}/family-reunion-readiness`,
        { method: "GET" },
      );
      render(payload);
    } catch (error) {
      statusNode.textContent = error.message || "Unable to load family reunion readiness.";
    }
  }

  document.addEventListener("DOMContentLoaded", setup);
})();
