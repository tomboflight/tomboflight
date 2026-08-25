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

  const BLOCKER_LABELS = {
    security_scan_not_clean: "Run the security scan and obtain a clean verdict before previewing this file.",
    customer_consent_attestation_missing: "customer consent attestation is missing",
    upload_authority_attestation_missing: "upload-authority attestation is missing",
    durable_private_storage_missing: "Private storage migration must complete before preview.",
    orphaned_project_reference: "the project record was removed and must be reconciled",
    orphaned_family_reference: "the family record was removed and must be reconciled",
    orphaned_member_reference: "the family-member record was removed and must be reconciled",
  };

  function approvalBlockers(item) {
    const blockers = [];
    if (String(item.scan_status || "").toLowerCase() !== "clean" || item.quarantined) {
      blockers.push("security_scan_not_clean");
    }
    if (!item.consent_attested) blockers.push("customer_consent_attestation_missing");
    if (!item.authority_attested) blockers.push("upload_authority_attestation_missing");
    if (!item.durable_private_storage) blockers.push("durable_private_storage_missing");
    if (item.orphaned_project_reference) blockers.push("orphaned_project_reference");
    if (item.orphaned_family_reference) blockers.push("orphaned_family_reference");
    if (item.orphaned_member_reference) blockers.push("orphaned_member_reference");
    return blockers;
  }

  function blockerText(blockers) {
    return blockers.map(function (code) {
      return BLOCKER_LABELS[code] || String(code).replaceAll("_", " ");
    }).join("; ");
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
      item.consent_attested &&
      item.authority_attested &&
      item.durable_private_storage &&
      !item.orphaned_project_reference &&
      !item.orphaned_family_reference &&
      !item.orphaned_member_reference
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
      const blockers = approvalBlockers(item);
      const orphaned = Boolean(
        item.orphaned_project_reference ||
        item.orphaned_family_reference ||
        item.orphaned_member_reference
      );
      const scanReady = (
        String(item.scan_status || "").toLowerCase() === "clean" &&
        !item.quarantined &&
        item.durable_private_storage
      );
      const previewBlockers = Array.isArray(item.preview_blockers)
        ? item.preview_blockers
        : approvalBlockers(item).filter(function (code) {
            return ["security_scan_not_clean", "durable_private_storage_missing"].includes(code);
          });
      const previewAvailable = item.preview_available === true || (
        item.preview_available == null && previewBlockers.length === 0
      );
      const customerRecoveryUrl = item.family_id
        ? `portrait-upload.html?family_id=${encodeURIComponent(item.family_id)}`
        : "portrait-upload.html";
      return `
        <article class="family-record-card" data-review-card="${escapeHtml(item.id)}">
          <span class="eyebrow">${escapeHtml(item.scan_status || "pending scan")}</span>
          <h3>${escapeHtml(item.member_name || "Unnamed family member")}</h3>
          <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")}</p>
          <p class="card-copy"><strong>File:</strong> ${escapeHtml(item.original_filename || "—")}</p>
          <p class="card-copy"><strong>Consent:</strong> ${item.consent_attested ? "Attested" : "Missing"}</p>
          <p class="card-copy"><strong>Authority:</strong> ${item.authority_attested ? "Attested" : "Missing"}</p>
          <p class="card-copy"><strong>Current status:</strong> ${escapeHtml(item.master_review_status || item.verification_status || "pending")}</p>
          ${
            orphaned
              ? '<div class="notice"><strong>Orphaned record:</strong> use Reconcile Manual Removal in the Control Center before any placement decision.</div>'
              : ""
          }
          ${
            blockers.length
              ? `<div class="notice" data-review-blockers><strong>Approval blocked:</strong> ${escapeHtml(blockerText(blockers))}.</div>`
              : '<div class="notice"><strong>Ready:</strong> clean scan and required attestations are recorded.</div>'
          }
          ${
            item.possible_duplicate
              ? `<div class="notice"><strong>Possible duplicate:</strong> ${escapeHtml(item.possible_duplicate_count)} distinct upload records share the same customer, file, and review identity. Review each record before reconciliation.</div>`
              : ""
          }
          ${
            previewAvailable
              ? ""
              : `<div class="notice" data-preview-blockers><strong>Preview blocked:</strong> ${escapeHtml(item.preview_blocker_message || blockerText(previewBlockers))}</div>`
          }
          <div data-review-preview style="margin: 0.75rem 0"></div>
          <div class="inline-actions">
            <button class="btn btn-secondary" type="button" data-preview-id="${escapeHtml(item.id)}" ${previewAvailable ? "" : "disabled"}>${previewAvailable ? "Preview" : "Preview Blocked"}</button>
            ${
              scanReady || orphaned
                ? ""
                : `<button class="btn btn-secondary" type="button" data-review-rescan="${escapeHtml(item.id)}">Run Security Scan</button>`
            }
            <button class="btn btn-primary" type="button" data-review-decision="approve" data-upload-id="${escapeHtml(item.id)}" ${ready ? "" : "disabled"}>Approve &amp; Place</button>
            <button class="btn btn-secondary" type="button" data-review-decision="reject" data-upload-id="${escapeHtml(item.id)}" ${orphaned ? "disabled" : ""}>Reject</button>
            ${
              !item.consent_attested || !item.authority_attested
                ? `<a class="btn btn-secondary" href="${escapeHtml(customerRecoveryUrl)}">Customer Attestation Path</a>`
                : ""
            }
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
    const duplicatesSuppressed = Number(
      (payload && payload.duplicates_suppressed) || 0,
    );
    const items = (Array.isArray(payload.items) ? payload.items : []).filter(
      function (item) {
        const status = String(item.master_review_status || "pending").toLowerCase();
        return !item.approved_for_cinematic && status !== "rejected";
      },
    );
    render(items);
    setStatus(
      `${items.length} portrait submission(s) in the review queue.${
        duplicatesSuppressed
          ? ` ${duplicatesSuppressed} duplicate storage record(s) safely suppressed.`
          : ""
      }`,
    );
  }

  async function preview(uploadId, button) {
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
      let detail = "Unable to load the portrait preview.";
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
    const reason = window.prompt(
      "Operational reason for the Continuity Kernel evidence packet:",
      approving ? "Portrait approved after master review" : "Portrait rejected after master review",
    );
    if (reason === null) return;
    if (reason.trim().length < 3) {
      throw new Error("A reason of at least 3 characters is required.");
    }
    if (!window.confirm(`${approving ? "Approve and place" : "Reject"} this portrait through the Continuity Kernel?`)) {
      return;
    }
    const operation = await executeGoverned(
      "portrait_review",
      uploadId,
      {
        decision: approving ? "approved" : "rejected",
        review_notes: reviewNotes,
      },
      reason.trim(),
    );
    setStatus(
      operation && operation.state === "audit_closed"
        ? "Portrait review completed through the Continuity Kernel."
        : "Portrait review operation submitted for governed approval.",
    );
    await loadQueue();
  }

  async function rescan(uploadId) {
    const reason = window.prompt(
      "Reason for the governed security re-scan:",
      "Resolve pending upload security scan",
    );
    if (reason === null) return;
    if (reason.trim().length < 3) {
      throw new Error("A reason of at least 3 characters is required.");
    }
    if (!window.confirm("Run this file through the configured private security scanner?")) return;
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
    const page = document.querySelector("[data-admin-portrait-review]");
    if (!page) return;
    try {
      await app.apiRequest("/auth/me", { method: "GET" });
      await loadQueue();
      document.querySelector("[data-refresh-review]").addEventListener("click", loadQueue);
      document.addEventListener("click", async function (event) {
        const previewButton = event.target.closest("[data-preview-id]");
        const rescanButton = event.target.closest("[data-review-rescan]");
        const decisionButton = event.target.closest("[data-review-decision]");
        try {
          if (previewButton) {
            await preview(previewButton.getAttribute("data-preview-id"), previewButton);
          } else if (rescanButton) {
            await rescan(rescanButton.getAttribute("data-review-rescan"));
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
