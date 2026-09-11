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
    const node = document.querySelector("[data-verification-review-status]");
    if (node) node.textContent = message;
  }

  const BLOCKER_LABELS = {
    security_scan_not_clean: "secure malware scan has not returned a clean verdict",
    durable_private_storage_missing: "private R2 storage preparation is incomplete",
    orphaned_project_reference: "the project reference must be reconciled",
    orphaned_family_reference: "the family reference must be reconciled",
  };

  function previewBlockers(item) {
    if (Array.isArray(item.preview_blockers)) return item.preview_blockers;
    const blockers = [];
    if (String(item.scan_status || "").toLowerCase() !== "clean" || item.quarantined) blockers.push("security_scan_not_clean");
    if (!item.durable_private_storage) blockers.push("durable_private_storage_missing");
    return blockers;
  }

  function blockerText(blockers) {
    return blockers.map(function (code) {
      return BLOCKER_LABELS[code] || String(code).replaceAll("_", " ");
    }).join("; ");
  }

  function isOrphaned(item) {
    return Boolean(item.orphaned_project_reference || item.orphaned_family_reference);
  }

  function canApprove(item) {
    return (
      String(item.scan_status || "").toLowerCase() === "clean" &&
      !item.quarantined &&
      item.durable_private_storage === true &&
      !isOrphaned(item)
    );
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
    const list = document.querySelector("[data-verification-review-list]");
    const empty = document.querySelector("[data-verification-review-empty]");
    if (!list || !empty) return;
    if (!items.length) {
      list.innerHTML = "";
      empty.style.display = "";
      return;
    }
    empty.style.display = "none";
    list.innerHTML = items.map(function (item) {
      const orphaned = isOrphaned(item);
      const approvalReady = canApprove(item);
      const previewReady = canPreview(item);
      const scanClean = String(item.scan_status || "").toLowerCase() === "clean" && !item.quarantined;
      const privateReady = item.durable_private_storage === true;
      const blockers = [];
      if (!scanClean) blockers.push("security_scan_not_clean");
      if (!privateReady) blockers.push("durable_private_storage_missing");
      if (item.orphaned_project_reference) blockers.push("orphaned_project_reference");
      if (item.orphaned_family_reference) blockers.push("orphaned_family_reference");
      const previewReason = item.preview_blocker_message || blockerText(previewBlockers(item));

      return `
        <article class="family-record-card" data-evidence-card="${escapeHtml(item.id)}" style="display:grid;gap:.85rem">
          <div>
            <span class="eyebrow">Evidence Review</span>
            <h3>${escapeHtml(item.member_name || "Unnamed family member")}</h3>
            <p class="card-copy"><strong>Family:</strong> ${escapeHtml(item.family_name || item.family_id || "—")} · <strong>Evidence:</strong> ${escapeHtml(item.verification_type || item.evidence_kind || "Family record")}</p>
            <p class="card-copy"><strong>File:</strong> ${escapeHtml(item.original_filename || "—")} · <strong>Current decision:</strong> ${escapeHtml(item.verification_status || "pending")}</p>
          </div>

          <div class="grid-3" style="gap:.55rem">
            ${statusChip("Security scan", scanClean, item.quarantined ? "Blocked / quarantined" : String(item.scan_status || "Pending"))}
            ${statusChip("Private storage", privateReady, "Not prepared")}
            ${statusChip("Record reference", !orphaned, "Reconciliation required")}
          </div>

          ${orphaned ? '<div class="notice"><strong>Orphaned record:</strong> reconcile the removed project/family reference in Control Center before approval.</div>' : ""}
          ${item.possible_duplicate ? `<div class="notice"><strong>Possible duplicate:</strong> ${escapeHtml(item.possible_duplicate_count)} distinct upload records share this customer, file, and review identity. Review each record before reconciliation.</div>` : ""}
          ${blockers.length ? `<div class="notice" data-evidence-blockers><strong>Approval blocked:</strong> ${escapeHtml(blockerText(blockers))}.</div>` : '<div class="notice"><strong>Approval ready:</strong> scan, private storage, and record references are complete.</div>'}
          ${previewReady ? "" : `<div class="notice" data-evidence-preview-blockers><strong>Secure preview preparation required:</strong> ${escapeHtml(previewReason || "scan and private storage must complete")}</div>`}

          <div data-evidence-preview-frame style="min-height:0"></div>

          <div class="form-grid" data-evidence-decision-panel>
            <label>
              Review Notes
              <textarea rows="3" data-evidence-notes placeholder="Record verification findings, correction details, or approval notes."></textarea>
            </label>
            <label>
              Operational Reason
              <input type="text" data-evidence-reason value="Authorized evidence master review" maxlength="300" />
            </label>
          </div>

          <div class="inline-actions">
            <button class="btn btn-secondary" type="button" data-evidence-preview="${escapeHtml(item.id)}" ${previewReady ? "" : "disabled"}>${previewReady ? "View Secure Evidence" : "Preview Not Ready"}</button>
            ${(!previewReady && !orphaned) ? `<button class="btn btn-primary" type="button" data-evidence-rescan="${escapeHtml(item.id)}">Prepare Secure Preview</button>` : ""}
            <button class="btn btn-primary" type="button" data-evidence-decision="approved" data-upload-id="${escapeHtml(item.id)}" ${approvalReady ? "" : "disabled"}>Approve</button>
            <button class="btn btn-secondary" type="button" data-evidence-decision="needs_correction" data-upload-id="${escapeHtml(item.id)}" ${orphaned ? "disabled" : ""}>Needs Correction</button>
            <button class="btn btn-secondary" type="button" data-evidence-decision="rejected" data-upload-id="${escapeHtml(item.id)}" ${orphaned ? "disabled" : ""}>Reject</button>
          </div>
        </article>`;
    }).join("");
  }

  async function loadQueue() {
    setStatus("Loading evidence review queue…");
    const payload = await app.apiRequest("/uploads/admin/review?category=verification_evidence&limit=500", { method: "GET" });
    const duplicatesSuppressed = Number((payload && payload.duplicates_suppressed) || 0);
    const items = (Array.isArray(payload.items) ? payload.items : []).filter(function (item) {
      return !["approved", "rejected"].includes(String(item.verification_status || "pending").toLowerCase());
    });
    render(items);
    setStatus(`${items.length} verification submission(s) need a decision.${duplicatesSuppressed ? ` ${duplicatesSuppressed} duplicate storage record(s) safely suppressed.` : ""}`);
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
      let detail = "Unable to load this evidence record.";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_error) {}
      throw new Error(detail);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    previewUrls.add(url);
    const card = button.closest("[data-evidence-card]");
    const node = card && card.querySelector("[data-evidence-preview-frame]");
    if (!card || !node) throw new Error("Evidence review card is unavailable.");
    releaseCardPreview(card);
    card.dataset.previewObjectUrl = url;
    node.innerHTML = "";

    const frame = document.createElement("div");
    frame.style.cssText = "background:#f7fafc;border:1px solid #c9d9e8;border-radius:12px;padding:12px";
    const type = String(blob.type || "").toLowerCase();
    if (type.startsWith("image/")) {
      const image = document.createElement("img");
      image.src = url;
      image.alt = "Verification evidence submitted for master review";
      image.style.cssText = "display:block;width:100%;height:auto;max-height:620px;object-fit:contain;border-radius:8px;margin:auto";
      frame.appendChild(image);
    } else if (type === "application/pdf") {
      const iframe = document.createElement("iframe");
      iframe.src = url;
      iframe.title = "Private verification document preview";
      iframe.style.cssText = "display:block;width:100%;height:620px;border:0;border-radius:8px;background:white";
      frame.appendChild(iframe);
    } else {
      const message = document.createElement("p");
      message.className = "card-copy";
      message.textContent = "This protected file type cannot be rendered inline in this browser.";
      frame.appendChild(message);
    }
    node.appendChild(frame);
    button.textContent = "Evidence Visible";
    setStatus("Secure evidence loaded inside the review workbench.");
  }

  function reviewInputs(button) {
    const card = button.closest("[data-evidence-card]");
    const notes = card && card.querySelector("[data-evidence-notes]");
    const reason = card && card.querySelector("[data-evidence-reason]");
    return {
      notes: String((notes && notes.value) || "").trim(),
      reason: String((reason && reason.value) || "").trim(),
    };
  }

  async function decide(uploadId, decision, button) {
    const inputs = reviewInputs(button);
    if (inputs.reason.length < 3) {
      throw new Error("Enter an operational reason of at least 3 characters.");
    }
    if (!window.confirm(`Record the ${decision.replaceAll("_", " ")} evidence decision through the governed review workflow?`)) return;
    setStatus("Recording evidence decision…");
    const operation = await executeGoverned(
      "evidence_review",
      uploadId,
      { decision, review_notes: inputs.notes },
      inputs.reason,
    );
    setStatus(operation && operation.state === "audit_closed"
      ? "Evidence review completed through the Continuity Kernel."
      : "Evidence review operation submitted for governed approval.");
    await loadQueue();
  }

  async function prepareSecurePreview(uploadId) {
    if (!window.confirm("Prepare this evidence for review by running the private malware scan and promoting a clean file to private R2 storage?")) return;
    setStatus("Preparing secure evidence preview: scanning file and verifying private storage…");
    const operation = await executeGoverned(
      "upload_rescan",
      uploadId,
      {},
      "Prepare evidence for secure master review",
    );
    if (!(operation && operation.state === "audit_closed")) {
      setStatus("Secure preview preparation was submitted for governed approval.");
      await loadQueue();
      return;
    }
    const items = await loadQueue();
    const refreshed = items.find(function (item) { return String(item.id) === String(uploadId); });
    if (refreshed && canPreview(refreshed)) {
      const button = document.querySelector(`[data-evidence-card="${CSS.escape(String(uploadId))}"] [data-evidence-preview]`);
      if (button) await preview(uploadId, button);
    } else {
      setStatus("Review preparation completed, but the evidence is still blocked. Check scanner, R2, or reconciliation state shown on the card.");
    }
  }

  async function setup() {
    if (!document.querySelector("[data-admin-verification-review]")) return;
    try {
      await app.apiRequest("/auth/me", { method: "GET" });
      await loadQueue();
      const refresh = document.querySelector("[data-refresh-verification-review]");
      if (refresh) refresh.addEventListener("click", loadQueue);
      document.addEventListener("click", async function (event) {
        const previewButton = event.target.closest("[data-evidence-preview]");
        const rescanButton = event.target.closest("[data-evidence-rescan]");
        const decisionButton = event.target.closest("[data-evidence-decision]");
        try {
          if (previewButton) {
            await preview(previewButton.getAttribute("data-evidence-preview"), previewButton);
          } else if (rescanButton) {
            await prepareSecurePreview(rescanButton.getAttribute("data-evidence-rescan"));
          } else if (decisionButton) {
            await decide(
              decisionButton.getAttribute("data-upload-id"),
              decisionButton.getAttribute("data-evidence-decision"),
              decisionButton,
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

  window.addEventListener("beforeunload", function () {
    previewUrls.forEach(function (url) { URL.revokeObjectURL(url); });
    previewUrls.clear();
  });
  document.addEventListener("DOMContentLoaded", setup);
})();