(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    console.error("admin-intake.js requires app.js/auth.js first.");
    return;
  }

  let allSubmissions = [];
  let currentSubmission = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function normalizeStatus(status) {
    return String(status || "")
      .trim()
      .toLowerCase();
  }

  function humanizeStatus(status) {
    const normalized = normalizeStatus(status);
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
    node.dataset.state = type || "info";

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
    node.dataset.state = "";
  }

  function valueLine(label, value) {
    return `<p class="card-copy"><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value || "—")}</p>`;
  }

  function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function ensureAdminAccess(me) {
    const role = normalizeStatus(me && me.role);
    if (
      !["admin", "super_admin", "platform_admin", "operations_admin"].includes(
        role,
      )
    ) {
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

  function renderSummaryCards(submissions) {
    const node = document.querySelector("[data-admin-queue-summary]");
    if (!node) return;

    const counts = {
      all: submissions.length,
      submitted: 0,
      in_review: 0,
      approved: 0,
      rejected: 0,
      build_ready: 0,
      in_production: 0,
    };

    submissions.forEach(function (item) {
      const status = normalizeStatus(item.status);
      if (Object.prototype.hasOwnProperty.call(counts, status)) {
        counts[status] += 1;
      }
    });

    node.innerHTML = `
      <div><div class="card-number">A</div><h3>All</h3><p class="card-copy">${counts.all} submission(s)</p></div>
      <div><div class="card-number">B</div><h3>Submitted</h3><p class="card-copy">${counts.submitted} waiting</p></div>
      <div><div class="card-number">C</div><h3>In Review</h3><p class="card-copy">${counts.in_review} active</p></div>
      <div><div class="card-number">D</div><h3>Approved</h3><p class="card-copy">${counts.approved} approved</p></div>
      <div><div class="card-number">E</div><h3>Build Ready</h3><p class="card-copy">${counts.build_ready} provisioned</p></div>
      <div><div class="card-number">F</div><h3>Rejected</h3><p class="card-copy">${counts.rejected} rejected</p></div>
    `;
  }

  function renderQueueList() {
    const filterNode = document.querySelector("[data-admin-queue-filter]");
    const listNode = document.querySelector("[data-admin-queue-list]");
    const emptyNode = document.querySelector("[data-admin-queue-empty]");
    if (!listNode) return;

    const filterValue = normalizeStatus(filterNode ? filterNode.value : "all");
    const filtered = allSubmissions.filter(function (item) {
      if (filterValue === "all") return true;
      return normalizeStatus(item.status) === filterValue;
    });

    if (!filtered.length) {
      listNode.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";

    listNode.innerHTML = filtered
      .map(function (item, index) {
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(item.package_name || item.package_slug || "Submission")}</h3>
            ${valueLine("Status", humanizeStatus(item.status))}
            ${valueLine("Email", item.email)}
            ${valueLine("Submission ID", item.id)}
            ${valueLine("Created", formatDate(item.created_at))}
            ${valueLine("Submitted", formatDate(item.submitted_at))}
            ${valueLine("Reviewed By", item.reviewed_by || "—")}
            ${valueLine("Family Root", item.family_root_id || "—")}
            ${valueLine("Project ID", item.project_id || "—")}
            <div class="inline-actions" style="margin-top: 1rem;">
              <a class="btn btn-primary" href="admin-intake-review.html?submission_id=${encodeURIComponent(item.id)}">
                Open Review
              </a>
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function loadQueue() {
    const statusNode = document.querySelector("[data-admin-queue-status]");
    try {
      clearStatus(document.querySelector("[data-admin-queue-action-status]"));
      allSubmissions = await app.apiRequest(
        "/admin/intake-submissions?limit=100",
        {
          method: "GET",
        },
      );

      if (!Array.isArray(allSubmissions)) {
        allSubmissions = [];
      }

      renderSummaryCards(allSubmissions);
      renderQueueList();

      if (statusNode) {
        statusNode.textContent = `Loaded ${allSubmissions.length} intake submission(s) for admin review.`;
      }
    } catch (error) {
      if (statusNode) {
        statusNode.textContent = "Intake queue could not be loaded.";
      }
      setStatus(
        document.querySelector("[data-admin-queue-action-status]"),
        error.message || "Unable to load intake submissions.",
        "error",
      );
    }
  }

  function renderReviewBlock(node, title, number, lines) {
    if (!node) return;
    node.innerHTML = `
      <div>
        <div class="card-number">${escapeHtml(number)}</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${lines.map(escapeHtml).join("<br />")}</p>
      </div>
    `;
  }

  function ensureProvisionButton() {
    const form = document.querySelector("[data-admin-review-form]");
    if (!form) return;

    const actionsRow = form.querySelector(".inline-actions");
    if (!actionsRow) return;

    if (actionsRow.querySelector("[data-admin-provision-build]")) return;

    const button = document.createElement("button");
    button.className = "btn btn-primary";
    button.type = "button";
    button.setAttribute("data-admin-provision-build", "true");
    button.textContent = "Provision Build";

    actionsRow.insertBefore(button, actionsRow.lastElementChild);
  }

  function renderDetail(submission) {
    currentSubmission = submission;

    ensureProvisionButton();

    const pageStatus = document.querySelector(
      "[data-admin-review-page-status]",
    );
    const metaNode = document.querySelector("[data-admin-review-meta]");
    const timelineNode = document.querySelector("[data-admin-review-timeline]");
    const householdNode = document.querySelector(
      "[data-admin-review-household]",
    );
    const familyMapNode = document.querySelector(
      "[data-admin-review-family-map]",
    );
    const uploadsNode = document.querySelector("[data-admin-review-uploads]");
    const consentNode = document.querySelector("[data-admin-review-consent]");

    if (pageStatus) {
      pageStatus.textContent = `Submission ${submission.id} is currently ${humanizeStatus(submission.status)}.`;
    }

    renderReviewBlock(
      metaNode,
      submission.package_name ||
        submission.package_slug ||
        "Submission Overview",
      "1",
      [
        `Status: ${humanizeStatus(submission.status)}`,
        `Email: ${submission.email || "—"}`,
        `Package: ${submission.package_name || submission.package_slug || "—"}`,
        `Review Locked: ${submission.review_locked ? "Yes" : "No"}`,
        `Family Root ID: ${submission.family_root_id || "—"}`,
        `Household ID: ${submission.household_id || "—"}`,
        `Project ID: ${submission.project_id || "—"}`,
      ],
    );

    renderReviewBlock(timelineNode, "Review Timeline and Pipeline", "2", [
      `Created: ${formatDate(submission.created_at)}`,
      `Submitted: ${formatDate(submission.submitted_at)}`,
      `Review Started: ${formatDate(submission.review_started_at)}`,
      `Reviewed: ${formatDate(submission.reviewed_at)}`,
      `Reviewed By: ${submission.reviewed_by || "—"}`,
      `Provisioned: ${formatDate(submission.provisioned_at)}`,
      `Provisioned By: ${submission.provisioned_by || "—"}`,
      `Production Notes: ${submission.production_notes || "—"}`,
    ]);

    const household = submission.household || {};
    renderReviewBlock(
      householdNode,
      household.household_name || "Household",
      "3",
      [
        `Primary Contact: ${household.primary_contact_name || "—"}`,
        `Email: ${household.primary_contact_email || "—"}`,
        `Phone: ${household.primary_contact_phone || "—"}`,
        `Co-Owner: ${household.co_owner_name || "—"}`,
        `Role: ${household.household_role || "—"}`,
        `Scope: ${household.project_scope || "—"}`,
        `Notes: ${household.special_notes || "—"}`,
      ],
    );

    const familyMap = submission.family_map || {};
    renderReviewBlock(
      familyMapNode,
      familyMap.family_branch_name || "Family Map",
      "4",
      [
        `People in Scope: ${familyMap.people_in_scope || "—"}`,
        `Parent One: ${familyMap.parent_one || "—"}`,
        `Parent Two: ${familyMap.parent_two || "—"}`,
        `Spouse / Partner: ${familyMap.spouse_partner || "—"}`,
        `Children: ${familyMap.children_names || "—"}`,
        `Summary: ${familyMap.family_structure_summary || "—"}`,
        `Branch Notes: ${familyMap.branch_notes || "—"}`,
      ],
    );

    const uploads = submission.uploads || {};
    renderReviewBlock(uploadsNode, "Uploads", "5", [
      `Approx. Upload Count: ${uploads.approx_upload_count || "—"}`,
      `Primary Asset Type: ${uploads.primary_asset_type || "—"}`,
      `Key Portraits: ${uploads.key_portraits || "—"}`,
      `Supporting Records: ${uploads.supporting_records || "—"}`,
      `Quality Notes: ${uploads.quality_notes || "—"}`,
    ]);

    const consent = submission.consent || {};
    const review = submission.review || {};
    renderReviewBlock(consentNode, "Consent and Review Notes", "6", [
      `Process Consent: ${consent.consent_process ? "Yes" : "No"}`,
      `Store Consent: ${consent.consent_store ? "Yes" : "No"}`,
      `Visibility: ${consent.visibility_preference || "—"}`,
      `Consent Notes: ${consent.consent_notes || "—"}`,
      `Final Intake Notes: ${review.final_intake_notes || "—"}`,
      `Confirm Accuracy: ${review.confirm_accuracy ? "Yes" : "No"}`,
      `Reviewer Notes: ${submission.review_notes || "—"}`,
      `Approval Notes: ${submission.approval_notes || "—"}`,
      `Rejection Reason: ${submission.rejection_reason || "—"}`,
    ]);

    const form = document.querySelector("[data-admin-review-form]");
    if (form) {
      form.querySelector('[name="review_notes"]').value =
        submission.review_notes || "";
      form.querySelector('[name="approval_notes"]').value =
        submission.approval_notes || "";
      form.querySelector('[name="rejection_reason"]').value =
        submission.rejection_reason || "";
    }
  }

  async function loadReviewDetail() {
    const submissionId = getQueryParam("submission_id");
    const statusNode = document.querySelector(
      "[data-admin-review-action-status]",
    );

    if (!submissionId) {
      setStatus(statusNode, "Missing submission_id in page URL.", "error");
      return;
    }

    try {
      clearStatus(statusNode);
      const submission = await app.apiRequest(
        `/admin/intake-submissions/${encodeURIComponent(submissionId)}`,
        { method: "GET" },
      );
      renderDetail(submission);
    } catch (error) {
      setStatus(
        statusNode,
        error.message || "Unable to load the intake submission.",
        "error",
      );
    }
  }

  function getActionPayload() {
    const form = document.querySelector("[data-admin-review-form]");
    if (!form) {
      return {
        review_notes: "",
        approval_notes: "",
        rejection_reason: "",
        family_name_override: "",
        project_name_override: "",
        production_notes: "",
      };
    }

    const approvalNotes =
      form.querySelector('[name="approval_notes"]').value || "";

    return {
      review_notes: form.querySelector('[name="review_notes"]').value || "",
      approval_notes: approvalNotes,
      rejection_reason:
        form.querySelector('[name="rejection_reason"]').value || "",
      family_name_override: "",
      project_name_override: "",
      production_notes: approvalNotes,
    };
  }

  async function runAdminAction(action) {
    const statusNode = document.querySelector(
      "[data-admin-review-action-status]",
    );
    const submissionId = getQueryParam("submission_id");
    if (!submissionId) {
      setStatus(statusNode, "Missing submission_id in page URL.", "error");
      return;
    }

    const payload = getActionPayload();

    if (action === "reject" && !String(payload.rejection_reason || "").trim()) {
      setStatus(
        statusNode,
        "Rejection reason is required before rejecting.",
        "error",
      );
      return;
    }

    const pathMap = {
      in_review: `/admin/intake-submissions/${encodeURIComponent(submissionId)}/in-review`,
      approve: `/admin/intake-submissions/${encodeURIComponent(submissionId)}/approve`,
      reject: `/admin/intake-submissions/${encodeURIComponent(submissionId)}/reject`,
      provision: `/admin/intake-submissions/${encodeURIComponent(submissionId)}/provision-build`,
    };

    const requestBody =
      action === "provision"
        ? {
            family_name_override: payload.family_name_override,
            project_name_override: payload.project_name_override,
            production_notes: payload.production_notes,
          }
        : {
            review_notes: payload.review_notes,
            approval_notes: payload.approval_notes,
            rejection_reason: payload.rejection_reason,
          };

    try {
      setStatus(statusNode, "Submitting admin action...", "info");
      const result = await app.apiRequest(pathMap[action], {
        method: "POST",
        body: JSON.stringify(requestBody),
      });

      renderDetail(result);

      const label =
        action === "provision"
          ? "Build provisioned successfully."
          : `Submission updated to ${humanizeStatus(result.status)}.`;

      setStatus(statusNode, label, "success");
    } catch (error) {
      setStatus(statusNode, error.message || "Admin action failed.", "error");
    }
  }

  async function setupQueuePage() {
    const page = document.querySelector("[data-admin-queue-page]");
    if (!page) return;

    try {
      await requireAdmin();
      await loadQueue();

      const filterNode = document.querySelector("[data-admin-queue-filter]");
      const refreshNode = document.querySelector("[data-admin-queue-refresh]");

      if (filterNode) {
        filterNode.addEventListener("change", function () {
          renderQueueList();
        });
      }

      if (refreshNode) {
        refreshNode.addEventListener("click", function () {
          loadQueue();
        });
      }
    } catch (error) {
      const node = document.querySelector("[data-admin-queue-action-status]");
      setStatus(node, error.message || "Admin access is required.", "error");
      const hero = document.querySelector("[data-admin-queue-status]");
      if (hero) {
        hero.textContent = "Admin access could not be confirmed.";
      }
    }
  }

  async function setupReviewPage() {
    const page = document.querySelector("[data-admin-review-page]");
    if (!page) return;

    try {
      await requireAdmin();
      await loadReviewDetail();

      const reviewBtn = document.querySelector("[data-admin-mark-review]");
      const approveBtn = document.querySelector("[data-admin-approve]");
      const rejectBtn = document.querySelector("[data-admin-reject]");
      const refreshBtn = document.querySelector("[data-admin-refresh-detail]");

      if (reviewBtn) {
        reviewBtn.addEventListener("click", function () {
          runAdminAction("in_review");
        });
      }

      if (approveBtn) {
        approveBtn.addEventListener("click", function () {
          runAdminAction("approve");
        });
      }

      if (rejectBtn) {
        rejectBtn.addEventListener("click", function () {
          runAdminAction("reject");
        });
      }

      if (refreshBtn) {
        refreshBtn.addEventListener("click", function () {
          loadReviewDetail();
        });
      }

      document.addEventListener("click", function (event) {
        const button = event.target.closest("[data-admin-provision-build]");
        if (!button) return;
        runAdminAction("provision");
      });
    } catch (error) {
      const node = document.querySelector("[data-admin-review-action-status]");
      setStatus(node, error.message || "Admin access is required.", "error");
      const hero = document.querySelector("[data-admin-review-page-status]");
      if (hero) {
        hero.textContent = "Admin access could not be confirmed.";
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupQueuePage();
    setupReviewPage();
  });
})();
