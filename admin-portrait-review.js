(function () {
  "use strict";
  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setStatus(message) {
    const node = document.querySelector("[data-review-status]");
    if (node) node.textContent = message;
  }

  function canApprove(item) {
    return (
      String(item.scan_status || "").toLowerCase() === "clean" &&
      !item.quarantined &&
      item.consent_attested &&
      item.authority_attested
    );
  }

  function render(items) {
    const list = document.querySelector("[data-review-list]");
    const empty = document.querySelector("[data-review-empty]");
    if (!items.length) {
      list.innerHTML = "";
      empty.style.display = "";
      return;
    }
    empty.style.display = "none";
    list.innerHTML = items.map(function (item) {
      const ready = canApprove(item);
      return `
        <article class="family-record-card" data-review-card="${escapeHtml(item.id)}">
          <span class="eyebrow">${escapeHtml(item.scan_status || "pending scan")}</span>
          <h3>${escapeHtml(item.member_name || "Unnamed family member")}</h3>
          <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")}</p>
          <p class="card-copy"><strong>File:</strong> ${escapeHtml(item.original_filename || "—")}</p>
          <p class="card-copy"><strong>Consent:</strong> ${item.consent_attested ? "Attested" : "Missing"}</p>
          <p class="card-copy"><strong>Authority:</strong> ${item.authority_attested ? "Attested" : "Missing"}</p>
          <p class="card-copy"><strong>Current status:</strong> ${escapeHtml(item.master_review_status || item.verification_status || "pending")}</p>
          <div data-review-preview style="margin: 0.75rem 0"></div>
          <div class="inline-actions">
            <button class="btn btn-secondary" type="button" data-preview-id="${escapeHtml(item.id)}">Preview</button>
            <button class="btn btn-primary" type="button" data-review-decision="approve" data-upload-id="${escapeHtml(item.id)}" ${ready ? "" : "disabled"}>Approve &amp; Place</button>
            <button class="btn btn-secondary" type="button" data-review-decision="reject" data-upload-id="${escapeHtml(item.id)}">Reject</button>
          </div>
        </article>
      `;
    }).join("");
  }

  async function loadQueue() {
    setStatus("Loading portrait review queue…");
    const payload = await app.apiRequest(
      "/uploads/admin/review?category=member_photo&limit=500",
      { method: "GET" },
    );
    const items = (Array.isArray(payload.items) ? payload.items : []).filter(
      function (item) {
        const status = String(item.master_review_status || "pending").toLowerCase();
        return !item.approved_for_cinematic && status !== "rejected";
      },
    );
    render(items);
    setStatus(`${items.length} portrait submission(s) in the review queue.`);
  }

  async function preview(uploadId, button) {
    const token = app.getToken ? app.getToken() : "";
    const base = typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const response = await fetch(
      `${base}/uploads/${encodeURIComponent(uploadId)}/download`,
      {
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    if (!response.ok) throw new Error("Unable to load the portrait preview.");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const card = button.closest("[data-review-card]");
    const node = card.querySelector("[data-review-preview]");
    node.innerHTML = "";
    const image = document.createElement("img");
    image.src = url;
    image.alt = "Portrait submitted for master review";
    image.style.cssText = "width:100%;max-height:320px;object-fit:cover;border-radius:8px";
    image.addEventListener("load", function () { URL.revokeObjectURL(url); }, { once: true });
    node.appendChild(image);
  }

  async function decide(uploadId, decision) {
    const approving = decision === "approve";
    const reviewNotes = window.prompt(
      approving ? "Optional approval note:" : "Reason for rejection:",
      "",
    ) || "";
    await app.apiRequest(
      `/uploads/${encodeURIComponent(uploadId)}/cinematic-approval`,
      {
        method: "POST",
        body: JSON.stringify({
          approved_for_cinematic: approving,
          verification_status: approving ? "approved" : "rejected",
          consent_status: approving ? "approved" : "rejected",
          review_notes: reviewNotes,
        }),
      },
    );
    await loadQueue();
  }

  async function setup() {
    const page = document.querySelector("[data-admin-portrait-review]");
    if (!page) return;
    try {
      await app.apiRequest("/auth/me", { method: "GET" });
      await loadQueue();
      document.querySelector("[data-refresh-review]").addEventListener("click", loadQueue);
      document.addEventListener("click", async function (event) {
        const previewButton = event.target.closest("[data-preview-id]");
        const decisionButton = event.target.closest("[data-review-decision]");
        try {
          if (previewButton) {
            await preview(previewButton.getAttribute("data-preview-id"), previewButton);
          } else if (decisionButton) {
            await decide(
              decisionButton.getAttribute("data-upload-id"),
              decisionButton.getAttribute("data-review-decision"),
            );
          }
        } catch (error) {
          setStatus(error.message || "Portrait review action failed.");
        }
      });
    } catch (error) {
      setStatus(error.message || "You do not have master portrait-review access.");
    }
  }

  document.addEventListener("DOMContentLoaded", setup);
})();
