(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    console.error("admin-intake.js requires app.js/auth.js first.");
    return;
  }

  const INTERNAL_ROLE_KEYS = new Set([
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
  ]);

  const LINK_KEY_ENABLED_PACKAGES = new Set([
    "digital_legacy_portrait",
    "household_foundation",
    "heirloom_legacy_tree",
    "legacy_plus",
    "family_estate_concierge",
  ]);

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

  function normalizeValue(value) {
    return String(value || "").trim().toLowerCase();
  }

  function normalizeStatus(status) {
    return normalizeValue(status);
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

  function normalizePackageCode(value) {
    const normalized = normalizeValue(value);
    const mapping = {
      "legacy-snapshot": "legacy_snapshot",
      legacy_snapshot: "legacy_snapshot",
      "legacy-portrait-intro": "legacy_portrait_intro",
      legacy_portrait_intro: "legacy_portrait_intro",
      "digital-legacy-portrait": "digital_legacy_portrait",
      digital_legacy_portrait: "digital_legacy_portrait",
      "starter-family-tree": "household_foundation",
      starter_family_tree: "household_foundation",
      "household-foundation": "household_foundation",
      household_foundation: "household_foundation",
      "heirloom-legacy-tree": "heirloom_legacy_tree",
      heirloom_legacy_tree: "heirloom_legacy_tree",
      "legacy-plus": "legacy_plus",
      legacy_plus: "legacy_plus",
      "family-estate-concierge": "family_estate_concierge",
      family_estate_concierge: "family_estate_concierge",
      "command-structure-network": "command_structure_network",
      command_structure_network: "command_structure_network",
    };

    return mapping[normalized] || normalized;
  }

  function resolvePackageLane(packageCode) {
    const normalized = normalizePackageCode(packageCode);

    if (
      normalized === "legacy_snapshot" ||
      normalized === "legacy_portrait_intro" ||
      normalized === "digital_legacy_portrait"
    ) {
      return "portrait";
    }

    if (
      normalized === "household_foundation" ||
      normalized === "heirloom_legacy_tree" ||
      normalized === "legacy_plus"
    ) {
      return "household";
    }

    if (normalized === "family_estate_concierge") {
      return "network";
    }

    if (normalized === "command_structure_network") {
      return "organization";
    }

    return "unknown";
  }

  function getSubmissionPackageCode(submission) {
    return normalizePackageCode(
      submission &&
        (submission.package_code || submission.package_slug || submission.package_name)
    );
  }

  function isFamilyBuildLane(lane) {
    return lane === "household" || lane === "network";
  }

  function packageSupportsLinkKeys(packageCode) {
    return LINK_KEY_ENABLED_PACKAGES.has(normalizePackageCode(packageCode));
  }

  function isFamilyBuildSubmission(submission) {
    const lane = resolvePackageLane(getSubmissionPackageCode(submission));
    return isFamilyBuildLane(lane) && !!String(submission?.family_root_id || "").trim();
  }

  function isProvisionedSubmission(submission) {
    if (!submission) return false;

    const statusValue = normalizeStatus(submission.status);
    return (
      !!submission.provisioned_at ||
      !!submission.project_id ||
      [
        "build_ready",
        "in_production",
        "qa_review",
        "client_review",
        "delivered",
        "archived",
      ].includes(statusValue)
    );
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

  function withWorkspaceHref(href, submission) {
    if (!href) return href;

    const familyId = String(
      submission?.family_root_id || submission?.family_id || "",
    ).trim();
    const projectId = String(
      submission?.project_id || submission?.projectId || "",
    ).trim();

    if (!familyId && !projectId) {
      return href;
    }

    try {
      const url = new URL(href, window.location.href);
      if (familyId) {
        url.searchParams.set("family_id", familyId);
      }
      if (projectId) {
        url.searchParams.set("project_id", projectId);
      }
      return `${url.pathname.split("/").pop() || href}${url.search}`;
    } catch (error) {
      return href;
    }
  }

  function ensureAdminAccess(me) {
    const values = [
      normalizeValue(me && me.role),
      normalizeValue(me && me.access_tier),
      normalizeValue(me && me.department_role),
    ];

    const hasAccess = values.some(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });

    if (!hasAccess) {
      const error = new Error("Admin access is required to use this page.");
      error.code = "admin_access_required";
      throw error;
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

  async function apiRequestWithFallback(paths, options) {
    let lastError = null;

    for (const path of paths) {
      try {
        return await app.apiRequest(path, options);
      } catch (error) {
        lastError = error;
        console.error(`API request failed for ${path}`, error);
      }
    }

    throw lastError || new Error("All API request attempts failed.");
  }

  function configureActionLink(node, { text, href, show = true }) {
    if (!node) return;
    node.textContent = text;
    node.setAttribute("href", href);
    node.style.display = show ? "" : "none";
  }

  function redirectCustomerToDashboard(error) {
    if (error?.code !== "admin_access_required") {
      return false;
    }

    window.location.replace("dashboard.html");
    return true;
  }

  function getProvisionedWorkspaceLabel(submission) {
    const lane = resolvePackageLane(getSubmissionPackageCode(submission));

    if (lane === "portrait") return "live portrait workspace";
    if (lane === "organization") return "live organization workspace";
    return "live family build";
  }

  function getProvisionedActionMessage(submission) {
    const lane = resolvePackageLane(getSubmissionPackageCode(submission));

    if (lane === "portrait") {
      return "This submission is already provisioned. Use the customer dashboard or Verification Uploads instead.";
    }

    if (lane === "organization") {
      return "This submission is already provisioned. Use the customer dashboard or structure upload tools instead.";
    }

    return "This submission is already provisioned. Use Family Manager, Family Tree, or Lineage Certificate instead.";
  }

  function updateReviewActionState(submission) {
    const postBuildNotice = document.querySelector("[data-admin-post-build-notice]");
    const postBuildActions = document.querySelector("[data-admin-post-build-actions]");

    const familyManagerLink = document.querySelector("[data-admin-open-family-manager]");
    const familyTreeLink = document.querySelector("[data-admin-open-family-tree]");
    const certificateLink = document.querySelector("[data-admin-open-lineage-certificate]");

    const reviewBtn = document.querySelector("[data-admin-mark-review]");
    const approveBtn = document.querySelector("[data-admin-approve]");
    const rejectBtn = document.querySelector("[data-admin-reject]");
    const provisionBtn = document.querySelector("[data-admin-provision-build]");

    const provisioned = isProvisionedSubmission(submission);
    const statusValue = normalizeStatus(submission && submission.status);
    const packageCode = getSubmissionPackageCode(submission);
    const lane = resolvePackageLane(packageCode);
    const hasFamilyBuild = isFamilyBuildSubmission(submission);
    const linkKeysEnabled = packageSupportsLinkKeys(packageCode);

    if (provisioned) {
      if (postBuildNotice) {
        let notice = `This submission has already been provisioned into a ${getProvisionedWorkspaceLabel(submission)}.`;

        if (linkKeysEnabled) {
          notice += " Link capabilities are enabled for this package.";
        }

        postBuildNotice.textContent = notice;
        postBuildNotice.style.display = "block";
      }

      if (postBuildActions) postBuildActions.style.display = "flex";

      if (reviewBtn) reviewBtn.style.display = "none";
      if (approveBtn) approveBtn.style.display = "none";
      if (rejectBtn) rejectBtn.style.display = "none";
      if (provisionBtn) provisionBtn.style.display = "none";

      if (hasFamilyBuild) {
        configureActionLink(familyManagerLink, {
          text: "Open Family Manager",
          href: withWorkspaceHref("admin-family-manager.html", submission),
          show: true,
        });

        configureActionLink(familyTreeLink, {
          text: "Open Family Tree",
          href: withWorkspaceHref("tree-view.html", submission),
          show: true,
        });

        configureActionLink(certificateLink, {
          text: "Open Lineage Certificate",
          href: withWorkspaceHref("lineage-certificate.html", submission),
          show: true,
        });

        return;
      }

      if (lane === "portrait") {
        configureActionLink(familyManagerLink, {
          text: "Open Customer Dashboard",
          href: "dashboard.html",
          show: true,
        });

        configureActionLink(familyTreeLink, {
          text: "Open Verification Uploads",
          href: withWorkspaceHref("verification-upload.html", submission),
          show: true,
        });

        configureActionLink(certificateLink, {
          text: "Open Linking Keys",
          href: withWorkspaceHref("link-keys.html", submission),
          show: linkKeysEnabled,
        });

        return;
      }

      if (lane === "organization") {
        configureActionLink(familyManagerLink, {
          text: "Open Structure Workspace",
          href: withWorkspaceHref("verification-upload.html", submission),
          show: true,
        });

        configureActionLink(familyTreeLink, {
          text: "Open Family Tree",
          href: "tree-view.html",
          show: false,
        });

        configureActionLink(certificateLink, {
          text: "Open Lineage Certificate",
          href: "lineage-certificate.html",
          show: false,
        });

        return;
      }
    }

    if (postBuildNotice) postBuildNotice.style.display = "none";
    if (postBuildActions) postBuildActions.style.display = "none";

    if (reviewBtn) reviewBtn.style.display = "";
    if (approveBtn) approveBtn.style.display = "";
    if (rejectBtn) rejectBtn.style.display = "";

    if (provisionBtn) {
      provisionBtn.style.display = statusValue === "approved" ? "" : "none";
    }
  }

  function renderSummaryCards(submissions) {
    const node = document.querySelector("[data-admin-queue-summary]");
    if (!node) return;

    const counts = {
      all: submissions.length,
      submitted: 0,
      in_review: 0,
      approved: 0,
      build_ready: 0,
      rejected: 0,
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
        const lane = resolvePackageLane(getSubmissionPackageCode(item));
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(item.package_name || item.package_slug || "Submission")}</h3>
            ${valueLine("Status", humanizeStatus(item.status))}
            ${valueLine("Lane", lane)}
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
    const actionNode = document.querySelector("[data-admin-queue-action-status]");

    try {
      clearStatus(actionNode);

      allSubmissions = await apiRequestWithFallback(
        [
          "/admin/intake-submissions?limit=100",
          "/admin/intake-submissions/?limit=100",
        ],
        { method: "GET" },
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
      console.error("Admin queue load failed:", error);

      if (statusNode) {
        statusNode.textContent = "Intake queue could not be loaded.";
      }

      setStatus(
        actionNode,
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
        <p class="card-copy">${(lines || []).map(escapeHtml).join("<br />")}</p>
      </div>
    `;
  }

  function renderDetail(submission) {
    currentSubmission = submission;

    const pageStatus = document.querySelector("[data-admin-review-page-status]");
    const metaNode = document.querySelector("[data-admin-review-meta]");
    const timelineNode = document.querySelector("[data-admin-review-timeline]");
    const householdNode = document.querySelector("[data-admin-review-household]");
    const familyMapNode = document.querySelector("[data-admin-review-family-map]");
    const uploadsNode = document.querySelector("[data-admin-review-uploads]");
    const consentNode = document.querySelector("[data-admin-review-consent]");

    const provisioned = isProvisionedSubmission(submission);
    const packageCode = getSubmissionPackageCode(submission);
    const lane = resolvePackageLane(packageCode);
    const hasFamilyBuild = isFamilyBuildSubmission(submission);

    if (pageStatus) {
      pageStatus.textContent = provisioned
        ? `Submission ${submission.id} is currently ${humanizeStatus(submission.status)} and has already been provisioned into a ${getProvisionedWorkspaceLabel(submission)}.`
        : `Submission ${submission.id} is currently ${humanizeStatus(submission.status)}.`;
    }

    renderReviewBlock(
      metaNode,
      submission.package_name ||
        submission.package_slug ||
        "Submission Overview",
      "1",
      [
        `Status: ${humanizeStatus(submission.status)}`,
        `Lane: ${lane}`,
        `Email: ${submission.email || "—"}`,
        `Package: ${submission.package_name || submission.package_slug || "—"}`,
        `Review Locked: ${submission.review_locked ? "Yes" : "No"}`,
        `Family Root ID: ${hasFamilyBuild ? submission.family_root_id || "—" : "Not applicable"}`,
        `Household ID: ${hasFamilyBuild ? submission.household_id || "—" : "Not applicable"}`,
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
      household.household_name ||
        (lane === "portrait"
          ? "Portrait Intake"
          : lane === "organization"
            ? "Structure Intake"
            : "Household"),
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
      familyMap.family_branch_name ||
        (lane === "organization" ? "Structure Map" : "Family Map"),
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
      const reviewNotes = form.querySelector('[name="review_notes"]');
      const approvalNotes = form.querySelector('[name="approval_notes"]');
      const rejectionReason = form.querySelector('[name="rejection_reason"]');

      if (reviewNotes) reviewNotes.value = submission.review_notes || "";
      if (approvalNotes) approvalNotes.value = submission.approval_notes || "";
      if (rejectionReason) {
        rejectionReason.value = submission.rejection_reason || "";
      }
    }

    updateReviewActionState(submission);
  }

  async function loadReviewDetail() {
    const submissionId = getQueryParam("submission_id");
    const statusNode = document.querySelector("[data-admin-review-action-status]");

    if (!submissionId) {
      setStatus(statusNode, "Missing submission_id in page URL.", "error");
      return;
    }

    try {
      clearStatus(statusNode);

      const submission = await apiRequestWithFallback(
        [
          `/admin/intake-submissions/${encodeURIComponent(submissionId)}`,
          `/admin/intake-submissions/${encodeURIComponent(submissionId)}/`,
        ],
        { method: "GET" },
      );

      renderDetail(submission);
    } catch (error) {
      console.error("Admin intake detail load failed:", error);
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

    const reviewNotes =
      (form.querySelector('[name="review_notes"]') || {}).value || "";
    const approvalNotes =
      (form.querySelector('[name="approval_notes"]') || {}).value || "";
    const rejectionReason =
      (form.querySelector('[name="rejection_reason"]') || {}).value || "";

    return {
      review_notes: reviewNotes,
      approval_notes: approvalNotes,
      rejection_reason: rejectionReason,
      family_name_override: "",
      project_name_override: "",
      production_notes: approvalNotes,
    };
  }

  function setReviewButtonsDisabled(disabled) {
    [
      "[data-admin-mark-review]",
      "[data-admin-approve]",
      "[data-admin-reject]",
      "[data-admin-provision-build]",
      "[data-admin-refresh-detail]",
      "[data-admin-refresh-detail-post]",
    ].forEach(function (selector) {
      const button = document.querySelector(selector);
      if (button) button.disabled = disabled;
    });
  }

  async function runAdminAction(action) {
    const statusNode = document.querySelector("[data-admin-review-action-status]");
    const submissionId = getQueryParam("submission_id");
    if (!submissionId) {
      setStatus(statusNode, "Missing submission_id in page URL.", "error");
      return;
    }

    if (currentSubmission && isProvisionedSubmission(currentSubmission)) {
      setStatus(statusNode, getProvisionedActionMessage(currentSubmission), "error");
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

    if (
      action === "provision" &&
      normalizeStatus(currentSubmission && currentSubmission.status) !== "approved"
    ) {
      setStatus(
        statusNode,
        "Approve the submission before provisioning the build.",
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
      setReviewButtonsDisabled(true);
      setStatus(statusNode, "Submitting admin action...", "info");

      const result = await app.apiRequest(pathMap[action], {
        method: "POST",
        body: JSON.stringify(requestBody),
      });

      renderDetail(result);

      const lane = resolvePackageLane(getSubmissionPackageCode(result));
      const label =
        action === "provision"
          ? lane === "portrait"
            ? "Portrait workspace provisioned successfully."
            : lane === "organization"
              ? "Organization workspace provisioned successfully."
              : "Family build provisioned successfully."
          : `Submission updated to ${humanizeStatus(result.status)}.`;

      setStatus(statusNode, label, "success");
    } catch (error) {
      console.error("Admin action failed:", error);
      setStatus(statusNode, error.message || "Admin action failed.", "error");
    } finally {
      setReviewButtonsDisabled(false);
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
      console.error("Admin queue page setup failed:", error);
      if (redirectCustomerToDashboard(error)) return;

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
      const provisionBtn = document.querySelector("[data-admin-provision-build]");
      const refreshBtn = document.querySelector("[data-admin-refresh-detail]");
      const refreshPostBtn = document.querySelector("[data-admin-refresh-detail-post]");

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

      if (provisionBtn) {
        provisionBtn.addEventListener("click", function () {
          runAdminAction("provision");
        });
      }

      if (refreshBtn) {
        refreshBtn.addEventListener("click", function () {
          loadReviewDetail();
        });
      }

      if (refreshPostBtn) {
        refreshPostBtn.addEventListener("click", function () {
          loadReviewDetail();
        });
      }
    } catch (error) {
      console.error("Admin review page setup failed:", error);
      if (redirectCustomerToDashboard(error)) return;

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
