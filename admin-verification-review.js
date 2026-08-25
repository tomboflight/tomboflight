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

  function reviewIdempotencyKey(action, uploadId) {
    const suffix = window.crypto && typeof window.crypto.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `kernel-${action}-${uploadId}-${suffix}`;
  }

  async function executeGoverned(action, uploadId, parameters, reason) {
    const runtime = await app.apiRequest(
      "/admin/control-center/kernel/status",
      { method: "GET" },
    );
    if (!runtime || !runtime.execution_enabled) {
      throw new Error("Continuity Kernel execution is unavailable.");
    }
    const idempotencyKey = reviewIdempotencyKey(action, uploadId);
    const payload = {
      action,
      target: { upload_id: uploadId },
      parameters: {
        ...(parameters || {}),
        continuity_idempotency_key: idempotencyKey,
      },
      reason,
      idempotency_key: idempotencyKey,
    };
    if (runtime.one_step_execution_allowed) {
      return app.apiRequest("/admin/control-center/kernel/execute", {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          confirmed: true,
          solo_founder_override_acknowledged: true,
        }),
      });
    }
    return app.apiRequest("/admin/control-center/kernel/operations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  function canApprove(item) {
    return (
      String(item.scan_status || "").toLowerCase() === "clean" &&
      !item.quarantined &&
      item.durable_private_storage &&
      !item.orphaned_project_reference &&
      !item.orphaned_family_reference
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
      const orphaned = Boolean(
        item.orphaned_project_reference || item.orphaned_family_reference
      );
      const securityReady = (
        String(item.scan_status || "").toLowerCase() === "clean" &&
        !item.quarantined &&
        item.durable_private_storage
      );
      const approvalReady = canApprove(item);
      return `
        <article class="family-record-card" data-evidence-card="${escapeHtml(item.id)}">
          <span class="eyebrow">${escapeHtml(item.scan_status || "pending scan")}</span>
          <h3>${escapeHtml(item.member_name || "Unnamed family member")}</h3>
          <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")}</p>
          <p class="card-copy"><strong>Evidence:</strong> ${escapeHtml(item.verification_type || item.evidence_kind || "Family record")}</p>
          <p class="card-copy"><strong>File:</strong> ${escapeHtml(item.original_filename || "—")}</p>
          <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.verification_status || "pending")}</p>
          ${
            orphaned
              ? '<div class="notice"><strong>Orphaned record:</strong> use Reconcile Manual Removal in the Control Center before approval.</div>'
              : ""
          }
          ${
            approvalReady
              ? '<div class="notice"><strong>Ready:</strong> clean scan and durable private storage are required for approval.</div>'
              : `<div class="notice" data-evidence-blockers><strong>Approval blocked:</strong> ${escapeHtml(orphaned ? "orphaned project or family reference requires reconciliation" : (!item.durable_private_storage ? "durable private storage is incomplete" : "security scan has not returned clean"))}.</div>`
          }
          <div class="inline-actions">
            <button class="btn btn-secondary" type="button" data-evidence-preview="${escapeHtml(item.id)}">Open Secure Preview</button>
            ${
              securityReady || orphaned
                ? ""
                : `<button class="btn btn-secondary" type="button" data-evidence-rescan="${escapeHtml(item.id)}">Run Security Scan</button>`
            }
            <button class="btn btn-primary" type="button" data-evidence-decision="approved" data-upload-id="${escapeHtml(item.id)}" ${approvalReady ? "" : "disabled"}>Approve</button>
            <button class="btn btn-secondary" type="button" data-evidence-decision="needs_correction" data-upload-id="${escapeHtml(item.id)}" ${orphaned ? "disabled" : ""}>Needs Correction</button>
            <button class="btn btn-secondary" type="button" data-evidence-decision="rejected" data-upload-id="${escapeHtml(item.id)}" ${orphaned ? "disabled" : ""}>Reject</button>
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
    const duplicatesSuppressed = Number(
      (payload && payload.duplicates_suppressed) || 0,
    );
    const items = (Array.isArray(payload.items) ? payload.items : []).filter(
      function (item) {
        return !["approved", "rejected"].includes(
          String(item.verification_status || "pending").toLowerCase(),
        );
      },
    );
    render(items);
    setStatus(
      `${items.length} verification submission(s) need a decision.${
        duplicatesSuppressed
          ? ` ${duplicatesSuppressed} duplicate storage record(s) safely suppressed.`
          : ""
      }`,
    );
  }

  async function preview(uploadId) {
    const previewWindow = window.open("about:blank", "_blank");
    const token = app.getToken ? app.getToken() : "";
    const base = typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const response = await fetch(
      `${base}/uploads/${encodeURIComponent(uploadId)}/admin-preview`,
      {
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    if (!response.ok) {
      if (previewWindow) previewWindow.close();
      let detail = "Unable to open this evidence record.";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_error) {
        // Keep the safe fallback message.
      }
      throw new Error(detail);
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
    const reason = window.prompt(
      "Operational reason for the Continuity Kernel evidence packet:",
      `Evidence marked ${decision.replaceAll("_", " ")}`,
    );
    if (reason === null) return;
    if (reason.trim().length < 3) {
      throw new Error("A reason of at least 3 characters is required.");
    }
    if (!window.confirm(`Record the ${decision.replaceAll("_", " ")} evidence decision through the Continuity Kernel?`)) {
      return;
    }
    const operation = await executeGoverned(
      "evidence_review",
      uploadId,
      { decision, review_notes: notes },
      reason.trim(),
    );
    setStatus(
      operation && operation.state === "audit_closed"
        ? "Evidence review completed through the Continuity Kernel."
        : "Evidence review operation submitted for governed approval.",
    );
    await loadQueue();
  }

  async function rescan(uploadId) {
    const reason = window.prompt(
      "Reason for the governed security re-scan:",
      "Resolve pending evidence security scan",
    );
    if (reason === null) return;
    if (reason.trim().length < 3) {
      throw new Error("A reason of at least 3 characters is required.");
    }
    if (!window.confirm("Run this private evidence file through the configured security scanner?")) return;
    setStatus("Running the private security scan…");
    const operation = await executeGoverned(
      "upload_rescan",
      uploadId,
      {},
      reason.trim(),
    );
    setStatus(
      operation && operation.state === "audit_closed"
        ? "Security scan completed. Refreshing the review queue…"
        : "Security scan operation submitted for governed approval.",
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
        const rescanButton = event.target.closest("[data-evidence-rescan]");
        const decisionButton = event.target.closest("[data-evidence-decision]");
        try {
          if (previewButton) {
            await preview(previewButton.getAttribute("data-evidence-preview"));
          } else if (rescanButton) {
            await rescan(rescanButton.getAttribute("data-evidence-rescan"));
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
