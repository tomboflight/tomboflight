(function () {
  "use strict";
  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  const previewUrls = new Set();

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
    security_scan_not_clean: "secure malware scan has not returned a clean verdict",
    customer_consent_attestation_missing: "customer consent attestation is missing",
    upload_authority_attestation_missing: "upload-authority attestation is missing",
    durable_private_storage_missing: "private R2 storage preparation is incomplete",
    orphaned_project_reference: "the project record was removed and must be reconciled",
    orphaned_family_reference: "the family record was removed and must be reconciled",
    orphaned_member_reference: "the family-member record was removed and must be reconciled",
  };

  function approvalBlockers(item) {
    const blockers = [];
    if (String(item.scan_status || "").toLowerCase() !== "clean" || item.quarantined) blockers.push("security_scan_not_clean");
    if (!item.consent_attested) blockers.push("customer_consent_attestation_missing");
    if (!item.authority_attested) blockers.push("upload_authority_attestation_missing");
    if (!item.durable_private_storage) blockers.push("durable_private_storage_missing");
    if (item.orphaned_project_reference) blockers.push("orphaned_project_reference");
    if (item.orphaned_family_reference) blockers.push("orphaned_family_reference");
    if (item.orphaned_member_reference) blockers.push("orphaned_member_reference");
    return blockers;
  }

  function previewBlockers(item) {
    if (Array.isArray(item.preview_blockers)) return item.preview_blockers;
    return approvalBlockers(item).filter(function (code) {
      return ["security_scan_not_clean", "durable_private_storage_missing"].includes(code);
    });
  }

  function blockerText(blockers) {
    return blockers.map(function (code) {
      return BLOCKER_LABELS[code] || String(code).replaceAll("_", " ");
    }).join("; ");
  }

  function isOrphaned(item) {
    return Boolean(
      item.orphaned_project_reference ||
      item.orphaned_family_reference ||
      item.orphaned_member_reference
    );
  }

  function canApprove(item) {
    return approvalBlockers(item).length === 0;
  }

  function canPreview(item) {
    return item.preview_available === true || (
      item.preview_available == null && previewBlockers(item).length === 0
    );
  }

  function reviewIdempotencyKey(action, uploadId) {
    const suffix = window.crypto && typeof window.crypto.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `kernel-${action}-${uploadId}-${suffix}`;
  }

  async function executeGoverned(action, uploadId, parameters, reason) {
    const runtime = await app.apiRequest("/admin/control-center/kernel/status", { method: "GET" });
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

  function statusChip(label, ready, detail) {
    return `<div class="notice" style="margin:0"><strong>${escapeHtml(label)}:</strong> ${ready ? "Ready" : escapeHtml(detail)}</div>`;
  }

  function render(items) {
    const list = document.querySelector("[data-review-list]");
    const empty = document.querySelector("[data-review-empty]");
    if (!list || !empty) return;
    if (!items.length) {
      list.innerHTML = "";
      empty.style.display = "";
      return;
    }
    empty.style.display = "none";
    list.innerHTML = items.map(function (item) {
      const ready = canApprove(item);
      const blockers = approvalBlockers(item);
      const orphaned = isOrphaned(item);
      const previewReady = canPreview(item);
      const scanClean = String(item.scan_status || "").toLowerCase() === "clean" && !item.quarantined;
      const privateReady = item.durable_private_storage === true;
      const customerRecoveryUrl = item.family_id
        ? `portrait-upload.html?family_id=${encodeURIComponent(item.family_id)}`
        : "portrait-upload.html";
      const previewReason = item.preview_blocker_message || blockerText(previewBlockers(item));

      return `
        <article class="family-record-card" data-review-card="${escapeHtml(item.id)}" style="display:grid;gap:.85rem">
          <div>
            <span class="eyebrow">Portrait Review</span>
            <h3>${escapeHtml(item.member_name || "Unnamed family member")}</h3>
            <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")} · <strong>File:</strong> ${escapeHtml(item.original_filename || "—")}</p>
            <p class="card-copy"><strong>Current decision:</strong> ${escapeHtml(item.master_review_status || item.verification_status || "pending")}</p>
          </div>

          <div class="grid-3" style="gap:.55rem">
            ${statusChip("Security scan", scanClean, item.quarantined ? "Blocked / quarantined" : String(item.scan_status || "Pending"))}
            ${statusChip("Private storage", privateReady, "Not prepared")}
            ${statusChip("Consent", item.consent_attested === true, "Missing")}
            ${statusChip("Upload authority", item.authority_attested === true, "Missing")}
          </div>

          ${orphaned ? '<div class="notice"><strong>Orphaned record:</strong> reconcile the removed project/family/member reference in Control Center before any placement decision.</div>' : ""}
          ${item.possible_duplicate ? `<div class="notice"><strong>Possible duplicate:</strong> ${escapeHtml(item.possible_duplicate_count)} distinct upload records share this customer, file, and review identity. Review each record before reconciliation.</div>` : ""}
          ${blockers.length ? `<div class="notice" data-review-blockers><strong>Approval blocked:</strong> ${escapeHtml(blockerText(blockers))}.</div>` : '<div class="notice"><strong>Approval ready:</strong> scan, private storage, consent, authority, and record references are complete.</div>'}
          ${previewReady ? "" : `<div class="notice" data-preview-blockers><strong>Secure preview preparation required:</strong> ${escapeHtml(previewReason || "scan and private storage must complete")}</div>`}

          <div data-review-preview style="min-height:0"></div>

          <div class="form-grid" data-review-decision-panel>
            <label>
              Review Notes
              <textarea rows="3" data-review-notes placeholder="Record the visual review result, corrections needed, or placement note."></textarea>
            </label>
            <label>
              Operational Reason
              <input type="text" data-review-reason value="Authorized portrait master review" maxlength="300" />
            </label>
          </div>

          <div class="inline-actions">
            <button class="btn btn-secondary" type="button" data-preview-id="${escapeHtml(item.id)}" ${previewReady ? "" : "disabled"}>${previewReady ? "View Secure Portrait" : "Preview Not Ready"}</button>
            ${(!previewReady && !orphaned) ? `<button class="btn btn-primary" type="button" data-review-rescan="${escapeHtml(item.id)}">Prepare Secure Preview</button>` : ""}
            <button class="btn btn-primary" type="button" data-review-decision="approve" data-upload-id="${escapeHtml(item.id)}" ${ready ? "" : "disabled"}>Approve &amp; Place</button>
            <button class="btn btn-secondary" type="button" data-review-decision="reject" data-upload-id="${escapeHtml(item.id)}" ${orphaned ? "disabled" : ""}>Reject</button>
            ${(!item.consent_attested || !item.authority_attested) ? `<a class="btn btn-secondary" href="${escapeHtml(customerRecoveryUrl)}">Resolve Customer Attestations</a>` : ""}
          </div>
        </article>`;
    }).join("");
  }

  async function loadQueue() {
    setStatus("Loading portrait review queue…");
    const payload = await app.apiRequest("/uploads/admin/review?category=member_photo&limit=500", { method: "GET" });
    const duplicatesSuppressed = Number((payload && payload.duplicates_suppressed) || 0);
    const items = (Array.isArray(payload.items) ? payload.items : []).filter(function (item) {
      const status = String(item.master_review_status || "pending").toLowerCase();
      return !item.approved_for_cinematic && status !== "rejected";
    });
    render(items);
    setStatus(`${items.length} portrait submission(s) in the review queue.${duplicatesSuppressed ? ` ${duplicatesSuppressed} duplicate storage record(s) safely suppressed.` : ""}`);
    return items;
  }

  function releaseCardPreview(card) {
    const oldUrl = card && card.dataset ? card.dataset.previewObjectUrl : "";
    if (oldUrl) {
      URL.revokeObjectURL(oldUrl);
      previewUrls.delete(oldUrl);
      delete card.dataset.previewObjectUrl;
    }
  }

  async function preview(uploadId, button) {
    const token = app.getToken ? app.getToken() : "";
    const base = typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const response = await fetch(`${base}/uploads/${encodeURIComponent(uploadId)}/admin-preview`, {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      let detail = "Unable to load the portrait preview.";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_error) {}
      throw new Error(detail);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    previewUrls.add(url);
    const card = button.closest("[data-review-card]");
    const node = card && card.querySelector("[data-review-preview]");
    if (!card || !node) throw new Error("Portrait review card is unavailable.");
    releaseCardPreview(card);
    card.dataset.previewObjectUrl = url;
    node.innerHTML = "";
    const frame = document.createElement("div");
    frame.style.cssText = "background:#f7fafc;border:1px solid #c9d9e8;border-radius:12px;padding:12px;text-align:center";
    const image = document.createElement("img");
    image.src = url;
    image.alt = "Portrait submitted for master review";
    image.style.cssText = "display:block;width:100%;height:auto;max-height:560px;object-fit:contain;border-radius:8px;margin:auto";
    frame.appendChild(image);
    node.appendChild(frame);
    button.textContent = "Portrait Visible";
    setStatus("Secure portrait loaded inside the review workbench.");
  }

  function reviewInputs(button) {
    const card = button.closest("[data-review-card]");
    const notes = card && card.querySelector("[data-review-notes]");
    const reason = card && card.querySelector("[data-review-reason]");
    return {
      notes: String((notes && notes.value) || "").trim(),
      reason: String((reason && reason.value) || "").trim(),
    };
  }

  async function decide(uploadId, decision, button) {
    const approving = decision === "approve";
    const inputs = reviewInputs(button);
    if (inputs.reason.length < 3) {
      throw new Error("Enter an operational reason of at least 3 characters.");
    }
    if (!window.confirm(`${approving ? "Approve and place" : "Reject"} this portrait through the governed review workflow?`)) return;
    setStatus(`${approving ? "Approving" : "Rejecting"} portrait…`);
    const operation = await executeGoverned(
      "portrait_review",
      uploadId,
      { decision: approving ? "approved" : "rejected", review_notes: inputs.notes },
      inputs.reason,
    );
    setStatus(operation && operation.state === "audit_closed"
      ? "Portrait review completed through the Continuity Kernel."
      : "Portrait review operation submitted for governed approval.");
    await loadQueue();
  }

  async function prepareSecurePreview(uploadId) {
    if (!window.confirm("Prepare this upload for review by running the private malware scan and promoting a clean file to private R2 storage?")) return;
    setStatus("Preparing secure preview: scanning file and verifying private storage…");
    const operation = await executeGoverned(
      "upload_rescan",
      uploadId,
      {},
      "Prepare upload for secure master review",
    );
    if (!(operation && operation.state === "audit_closed")) {
      setStatus("Secure preview preparation was submitted for governed approval.");
      await loadQueue();
      return;
    }
    const items = await loadQueue();
    const refreshed = items.find(function (item) { return String(item.id) === String(uploadId); });
    if (refreshed && canPreview(refreshed)) {
      const button = document.querySelector(`[data-review-card="${CSS.escape(String(uploadId))}"] [data-preview-id]`);
      if (button) await preview(uploadId, button);
    } else {
      setStatus("Review preparation completed, but the file is still blocked. Check scanner, R2, or record prerequisites shown on the card.");
    }
  }

  async function setup() {
    const page = document.querySelector("[data-admin-portrait-review]");
    if (!page) return;
    try {
      await app.apiRequest("/auth/me", { method: "GET" });
      await loadQueue();
      const refresh = document.querySelector("[data-refresh-review]");
      if (refresh) refresh.addEventListener("click", loadQueue);
      document.addEventListener("click", async function (event) {
        const previewButton = event.target.closest("[data-preview-id]");
        const rescanButton = event.target.closest("[data-review-rescan]");
        const decisionButton = event.target.closest("[data-review-decision]");
        try {
          if (previewButton) {
            await preview(previewButton.getAttribute("data-preview-id"), previewButton);
          } else if (rescanButton) {
            await prepareSecurePreview(rescanButton.getAttribute("data-review-rescan"));
          } else if (decisionButton) {
            await decide(
              decisionButton.getAttribute("data-upload-id"),
              decisionButton.getAttribute("data-review-decision"),
              decisionButton,
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

  window.addEventListener("beforeunload", function () {
    previewUrls.forEach(function (url) { URL.revokeObjectURL(url); });
    previewUrls.clear();
  });
  document.addEventListener("DOMContentLoaded", setup);
})();