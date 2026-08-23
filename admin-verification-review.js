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
    const node = document.querySelector("[data-verification-review-status]");
    if (node) node.textContent = message;
  }

  function canApprove(item) {
    return (
      String(item.scan_status || "").toLowerCase() === "clean" &&
      !item.quarantined
    );
  }

  function render(items) {
    const list = document.querySelector("[data-verification-review-list]");
    const empty = document.querySelector("[data-verification-review-empty]");
    if (!items.length) {
      list.innerHTML = "";
      empty.style.display = "";
      return;
    }
    empty.style.display = "none";
    list.innerHTML = items.map(function (item) {
      return `
        <article class="family-record-card" data-evidence-card="${escapeHtml(item.id)}">
          <span class="eyebrow">${escapeHtml(item.scan_status || "pending scan")}</span>
          <h3>${escapeHtml(item.member_name || "Unnamed family member")}</h3>
          <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")}</p>
          <p class="card-copy"><strong>Evidence:</strong> ${escapeHtml(item.verification_type || item.evidence_kind || "Family record")}</p>
          <p class="card-copy"><strong>File:</strong> ${escapeHtml(item.original_filename || "—")}</p>
          <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.verification_status || "pending")}</p>
          <div class="inline-actions">
            <button class="btn btn-secondary" type="button" data-evidence-preview="${escapeHtml(item.id)}">Open Secure Preview</button>
            <button class="btn btn-primary" type="button" data-evidence-decision="approved" data-upload-id="${escapeHtml(item.id)}" ${canApprove(item) ? "" : "disabled"}>Approve</button>
            <button class="btn btn-secondary" type="button" data-evidence-decision="needs_correction" data-upload-id="${escapeHtml(item.id)}">Needs Correction</button>
            <button class="btn btn-secondary" type="button" data-evidence-decision="rejected" data-upload-id="${escapeHtml(item.id)}">Reject</button>
          </div>
        </article>`;
    }).join("");
  }

  async function loadQueue() {
    setStatus("Loading evidence review queue…");
    const payload = await app.apiRequest(
      "/uploads/admin/review?category=verification_evidence&limit=500",
      { method: "GET" },
    );
    const items = (Array.isArray(payload.items) ? payload.items : []).filter(
      function (item) {
        return !["approved", "rejected"].includes(
          String(item.verification_status || "pending").toLowerCase(),
        );
      },
    );
    render(items);
    setStatus(`${items.length} verification submission(s) need a decision.`);
  }

  async function preview(uploadId) {
    const previewWindow = window.open("about:blank", "_blank");
    const token = app.getToken ? app.getToken() : "";
    const base = typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const response = await fetch(
      `${base}/uploads/${encodeURIComponent(uploadId)}/download`,
      {
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    if (!response.ok) {
      if (previewWindow) previewWindow.close();
      throw new Error("Unable to open this evidence record.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    if (previewWindow) {
      previewWindow.opener = null;
      previewWindow.location.replace(url);
    } else {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.click();
    }
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
  }

  async function decide(uploadId, decision) {
    const notes = window.prompt(
      decision === "approved" ? "Optional verification note:" : "Review note:",
      "",
    ) || "";
    await app.apiRequest(
      `/uploads/${encodeURIComponent(uploadId)}/verification-review`,
      {
        method: "POST",
        body: JSON.stringify({ decision, review_notes: notes }),
      },
    );
    await loadQueue();
  }

  async function setup() {
    if (!document.querySelector("[data-admin-verification-review]")) return;
    try {
      await app.apiRequest("/auth/me", { method: "GET" });
      await loadQueue();
      document.querySelector("[data-refresh-verification-review]")
        .addEventListener("click", loadQueue);
      document.addEventListener("click", async function (event) {
        const previewButton = event.target.closest("[data-evidence-preview]");
        const decisionButton = event.target.closest("[data-evidence-decision]");
        try {
          if (previewButton) {
            await preview(previewButton.getAttribute("data-evidence-preview"));
          } else if (decisionButton) {
            await decide(
              decisionButton.getAttribute("data-upload-id"),
              decisionButton.getAttribute("data-evidence-decision"),
            );
          }
        } catch (error) {
          setStatus(error.message || "Evidence review action failed.");
        }
      });
    } catch (error) {
      setStatus(error.message || "You do not have master evidence-review access.");
    }
  }

  document.addEventListener("DOMContentLoaded", setup);
})();
