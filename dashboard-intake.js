(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};

  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  const LOCKED_STATUSES = new Set([
    "submitted",
    "in_review",
    "approved",
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
  ]);

  const PRODUCTION_STATUSES = new Set([
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
  ]);

  const HOUSEHOLD_MANAGEMENT_ROLES = new Set([
    "billing_owner",
    "co_owner",
    "family_manager",
  ]);
  const HOUSEHOLD_MEMBER_ROLE_ALIASES = {
    owner: "billing_owner",
    buyer: "billing_owner",
    spouse: "co_owner",
    partner: "co_owner",
    manager: "family_manager",
    administrator: "family_manager",
    admin: "family_manager",
    editor: "contributor",
    reader: "viewer",
  };
  const MORELAND_FAMILY_TREE = {
    familyId: "moreland_family",
    familyName: "Moreland Family",
    packageSlug: "legacy_plus",
    projectId: "moreland_family_project",
    manifestStatus: "active",
    viewerStatus: "approved",
  };
  // Intake approval checkpoint and all downstream production states.
  const APPROVED_OR_BEYOND_STATUSES = new Set([
    "approved",
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
  ]);
  // Production pipeline stages after intake has been provisioned.
  const PRODUCTION_OR_BEYOND_STATUSES = new Set([
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
  ]);
  // Review-facing labels for customer-visible status messaging.
  const REVIEW_PHASE_STATUSES = new Set([
    "in_review",
    "approved",
    "qa_review",
    "client_review",
  ]);
  // Early intake states where uploads/material checks are still pending review.
  const UPLOAD_PENDING_REVIEW_STATUSES = new Set([
    "submitted",
    "in_review",
    "approved",
  ]);

  let legacyAnchorState = null;

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function normalizeStatus(status) {
    return normalizeValue(status);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
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

  function isLockedStatus(status) {
    return LOCKED_STATUSES.has(normalizeStatus(status));
  }

  function isInternalRole(userOrRole, accessTier, departmentRole) {
    // Prefer the canonical check from app.js.
    if (app && typeof app.isInternalRole === "function") {
      const user =
        userOrRole && typeof userOrRole === "object"
          ? userOrRole
          : { role: userOrRole, access_tier: accessTier, department_role: departmentRole };
      return app.isInternalRole(user);
    }

    const values =
      userOrRole && typeof userOrRole === "object"
        ? [
            normalizeValue(userOrRole.role),
            normalizeValue(userOrRole.access_tier),
            normalizeValue(userOrRole.department_role),
          ]
        : [
            normalizeValue(userOrRole),
            normalizeValue(accessTier),
            normalizeValue(departmentRole),
          ];

    const aliases = {
      root_admin: "super_admin",
      platform_admin: "super_admin",
      executive_technology: "super_admin",
      operations: "operations_admin",
      finance: "finance_admin",
      marketing: "marketing_admin",
    };
    const normalized = values.map(function (value) {
      return aliases[value] || value;
    });
    return ["super_admin", "operations_admin", "finance_admin", "marketing_admin"].some(function (value) {
      return normalized.includes(value);
    });
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch (error) {
      return String(value);
    }
  }

  function hasTruthyField(record, key) {
    return Boolean(record && Object.prototype.hasOwnProperty.call(record, key) && record[key]);
  }

  function hasIntakeConfirmationIssues(latestSubmission) {
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    if (status !== "approved" && status !== "build_ready") {
      return false;
    }

    const uploads = latestSubmission?.uploads || {};
    const review = latestSubmission?.review || {};
    const consent = latestSubmission?.consent || {};
    const checks = [];

    if (Object.prototype.hasOwnProperty.call(uploads, "uploads_rights_confirmed")) {
      checks.push(Boolean(uploads.uploads_rights_confirmed));
    }
    if (Object.prototype.hasOwnProperty.call(uploads, "uploads_minimization_confirmed")) {
      checks.push(Boolean(uploads.uploads_minimization_confirmed));
    }
    if (Object.prototype.hasOwnProperty.call(review, "confirm_accuracy")) {
      checks.push(Boolean(review.confirm_accuracy));
    }
    if (Object.prototype.hasOwnProperty.call(consent, "consent_process")) {
      checks.push(Boolean(consent.consent_process));
    }
    if (Object.prototype.hasOwnProperty.call(consent, "consent_store")) {
      checks.push(Boolean(consent.consent_store));
    }
    if (Object.prototype.hasOwnProperty.call(consent, "consent_authority")) {
      checks.push(Boolean(consent.consent_authority));
    }

    return checks.length > 0 && checks.some(function (value) {
      return value === false;
    });
  }

  function getIntakeAttentionItems(latestSubmission) {
    const uploads = latestSubmission?.uploads || {};
    const review = latestSubmission?.review || {};
    const consent = latestSubmission?.consent || {};
    return {
      rights:
        Object.prototype.hasOwnProperty.call(uploads, "uploads_rights_confirmed") &&
        uploads.uploads_rights_confirmed === false,
      minimization:
        Object.prototype.hasOwnProperty.call(uploads, "uploads_minimization_confirmed") &&
        uploads.uploads_minimization_confirmed === false,
      authority:
        Object.prototype.hasOwnProperty.call(consent, "consent_authority") &&
        consent.consent_authority === false,
      review:
        (Object.prototype.hasOwnProperty.call(review, "confirm_accuracy") &&
          review.confirm_accuracy === false) ||
        (Object.prototype.hasOwnProperty.call(consent, "consent_process") &&
          consent.consent_process === false),
    };
  }

  function updateIntakeAttentionPanel(latestSubmission) {
    const panel = document.querySelector("[data-intake-attention-panel]");
    if (!panel) return;

    const needsAttention = hasIntakeConfirmationIssues(latestSubmission);
    panel.style.display = needsAttention ? "" : "none";
    if (!needsAttention) return;

    const items = getIntakeAttentionItems(latestSubmission);
    const visibilityMap = {
      "[data-intake-attention-rights]": items.rights,
      "[data-intake-attention-minimization]": items.minimization,
      "[data-intake-attention-authority]": items.authority,
      "[data-intake-attention-review]": items.review,
    };

    Object.entries(visibilityMap).forEach(function ([selector, visible]) {
      const node = document.querySelector(selector);
      if (node) node.style.display = visible ? "" : "none";
    });
  }

  function getProjectWorkspaceName(context, latestSubmission) {
    const project = context?.activeProject || context?.currentWorkspace?.activeProject || {};
    const candidates = [
      project.family_name,
      project.household_name,
      project.project_name,
      project.name,
      project.family_id,
      project.familyId,
      project.project_id,
      project.projectId,
      latestSubmission?.family_root_id,
      latestSubmission?.project_id,
    ];

    const value = candidates.find(function (item) {
      return String(item || "").trim().length > 0;
    });
    return value || "Your current workspace";
  }

  function getBuildStageLabel(status, needsAttention) {
    if (needsAttention) return "Needs attention before production.";
    const normalized = normalizeStatus(status);
    if (normalized === "submitted") return "Intake submitted — review pending.";
    if (normalized === "in_review") return "Intake under review.";
    if (normalized === "approved") return "Intake approved — awaiting production queue.";
    if (normalized === "build_ready") return "Production build queued.";
    if (normalized === "in_production") return "Production build in progress.";
    if (normalized === "qa_review") return "Verification review in progress.";
    if (normalized === "client_review") return "Customer review in progress.";
    if (normalized === "delivered") return "Delivered.";
    if (normalized === "archived") return "Maintenance / Continuity.";
    if (normalized === "rejected") return "Needs attention before production.";
    return "Workspace active — next action required.";
  }

  function getNextRequiredActionLabel(primaryAction, latestSubmission, needsAttention) {
    if (needsAttention) return "Review intake confirmations and resolve required items.";
    if (primaryAction?.text) return primaryAction.text;
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    if (status === "submitted" || status === "in_review") return "Await review update.";
    if (status === "approved" || status === "build_ready") return "Prepare production materials.";
    if (status === "in_production") return "Monitor production build updates.";
    if (status === "qa_review" || status === "client_review") return "Review quality and verification updates.";
    if (status === "delivered" || status === "archived") return "Review maintenance and continuity options.";
    return "Upload Photos & Family Records.";
  }

  function setProgressStage(stageKey, options) {
    const item = document.querySelector(`[data-progress-stage="${stageKey}"]`);
    const chip = document.querySelector(`[data-progress-chip="${stageKey}"]`);
    if (!item || !chip) return;

    item.classList.remove("is-complete", "is-live", "is-attention");
    chip.classList.remove("is-complete", "is-live", "is-attention");

    const state = options?.state || "pending";
    if (state === "complete") {
      item.classList.add("is-complete");
      chip.classList.add("is-complete");
      chip.textContent = "Open";
      return;
    }
    if (state === "live") {
      item.classList.add("is-live");
      chip.classList.add("is-live");
      chip.textContent = "Open";
      return;
    }
    if (state === "attention") {
      item.classList.add("is-attention");
      chip.classList.add("is-attention");
      chip.textContent = "Needs attention";
      return;
    }
    chip.textContent = "Awaiting setup";
  }

  function updateProjectProgressTracker(context, latestSubmission, needsAttention) {
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    const hasSubmission = Boolean(
      latestSubmission &&
        (latestSubmission.id ||
          latestSubmission._id ||
          latestSubmission.submitted_at ||
          latestSubmission.created_at ||
          status),
    );
    const hasPackageAccess = Boolean(context?.hasPackageAccess);
    const hasUploadSignals = Boolean(
      hasTruthyField(latestSubmission?.uploads, "uploads_rights_confirmed") ||
        hasTruthyField(latestSubmission?.uploads, "uploads_minimization_confirmed") ||
        normalizeValue(latestSubmission?.uploads?.key_portraits) ||
        normalizeValue(latestSubmission?.uploads?.supporting_records) ||
        normalizeValue(latestSubmission?.uploads?.approx_upload_count),
    );

    const completed = {
      account_created: true,
      package_activated: hasPackageAccess,
      intake_started: hasSubmission,
      intake_submitted: hasSubmission,
      intake_approved: APPROVED_OR_BEYOND_STATUSES.has(status) && !needsAttention,
      uploads_needed: APPROVED_OR_BEYOND_STATUSES.has(status) || hasUploadSignals,
      uploads_under_review: REVIEW_PHASE_STATUSES.has(status),
      verification_review: status === "qa_review" || status === "client_review",
      production_build:
        status === "in_production" ||
        status === "qa_review" ||
        status === "client_review" ||
        status === "delivered" ||
        status === "archived",
      customer_review:
        status === "client_review" || status === "delivered" || status === "archived",
      delivered: status === "delivered" || status === "archived",
      maintenance_continuity: status === "archived",
    };

    const stageOrder = [
      "account_created",
      "package_activated",
      "intake_started",
      "intake_submitted",
      "intake_approved",
      "uploads_needed",
      "uploads_under_review",
      "verification_review",
      "production_build",
      "customer_review",
      "delivered",
      "maintenance_continuity",
    ];

    const firstPending = stageOrder.find(function (stage) {
      return !completed[stage];
    });

    stageOrder.forEach(function (stage) {
      if (needsAttention && stage === "intake_approved") {
        setProgressStage(stage, { state: "attention" });
      } else if (completed[stage]) {
        setProgressStage(stage, { state: "complete" });
      } else if (firstPending === stage) {
        setProgressStage(stage, { state: "live" });
      } else {
        setProgressStage(stage, { state: "pending" });
      }
    });

    const noteNode = document.querySelector("[data-progress-fallback-note]");
    if (!noteNode) return;
    if (!hasSubmission) {
      noteNode.textContent =
        "Status updates appear here as your project moves through production.";
    } else if (needsAttention) {
      noteNode.textContent = "Needs attention before production.";
    } else {
      noteNode.textContent = getBuildStageLabel(status, false);
    }
  }

  function updateCommandCenterPanel(context, latestSubmission, primaryAction) {
    const packageNode = document.querySelector("[data-command-center-package]");
    const projectNode = document.querySelector("[data-command-center-project]");
    const stageNode = document.querySelector("[data-command-center-stage]");
    const actionNode = document.querySelector("[data-command-center-next-action]");
    const securityNode = document.querySelector("[data-command-center-security]");
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    const needsAttention = hasIntakeConfirmationIssues(latestSubmission);

    text(packageNode, context?.packageName || "Your active package");
    text(projectNode, getProjectWorkspaceName(context, latestSubmission));
    text(stageNode, getBuildStageLabel(status, needsAttention));
    text(
      actionNode,
      getNextRequiredActionLabel(primaryAction, latestSubmission, needsAttention),
    );
    text(
      securityNode,
      "Private workspace active. Public sharing remains off unless approved.",
    );
  }

  function updateWorkspaceHealthPanel(context, latestSubmission) {
    const resolved = context?.resolvedEntitlements || {};
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    const viewerStatus = normalizeValue(
      context?.activeProject?.viewer_status || context?.activeProject?.manifest_status,
    );
    const needsAttention = hasIntakeConfirmationIssues(latestSubmission);
    const uploadsPlanned = Boolean(
      normalizeValue(latestSubmission?.uploads?.key_portraits) ||
        normalizeValue(latestSubmission?.uploads?.supporting_records) ||
        normalizeValue(latestSubmission?.uploads?.approx_upload_count) ||
        hasTruthyField(latestSubmission?.uploads, "uploads_rights_confirmed") ||
        hasTruthyField(latestSubmission?.uploads, "uploads_minimization_confirmed"),
    );

    text(
      document.querySelector("[data-health-package]"),
      context?.hasPackageAccess ? "Open" : "Awaiting setup",
    );
    text(
      document.querySelector("[data-health-intake]"),
      !latestSubmission
        ? "Awaiting setup"
        : needsAttention || status === "rejected"
          ? "Needs attention"
          : "Open",
    );
    text(
      document.querySelector("[data-health-uploads]"),
      !latestSubmission
        ? "Awaiting setup"
        : PRODUCTION_OR_BEYOND_STATUSES.has(status)
          ? "Open"
          : uploadsPlanned || UPLOAD_PENDING_REVIEW_STATUSES.has(status)
            ? "Check access"
            : "Awaiting setup",
    );
    text(
      document.querySelector("[data-health-verification]"),
      needsAttention || status === "rejected"
        ? "Needs attention"
        : PRODUCTION_OR_BEYOND_STATUSES.has(status)
          ? "Open"
          : "Check access",
    );

    const viewerReady = Boolean(
      status === "delivered" ||
        status === "archived" ||
        viewerStatus === "approved" ||
        viewerStatus === "ready" ||
        viewerStatus === "active" ||
        viewerStatus === "live",
    );
    text(
      document.querySelector("[data-health-viewer]"),
      viewerReady
        ? "Open"
        : PRODUCTION_OR_BEYOND_STATUSES.has(status)
          ? "Awaiting setup"
          : "Awaiting setup",
    );
    text(
      document.querySelector("[data-health-certificate]"),
      Boolean(resolved.can_use_lineage_certificate) &&
        (viewerReady || status === "client_review")
        ? "Open"
        : "Package-gated",
    );
    text(
      document.querySelector("[data-health-vault]"),
      Boolean(resolved.premium_archive_structure) ? "Open" : "Package-gated",
    );
    text(document.querySelector("[data-health-privacy]"), "Private by default");
  }

  function setUnlockState(selector, isIncluded) {
    const node = document.querySelector(selector);
    if (!node) return;
    node.dataset.unlockState = isIncluded ? "included" : "locked";
    node.textContent = isIncluded ? "Open" : "Package-gated";
  }

  function hasResolvedFlag(resolved, key) {
    return Object.prototype.hasOwnProperty.call(resolved || {}, key);
  }

  function accessStateFromFlag(flag, known, options = {}) {
    if (!known) return "check";
    if (!flag) return "locked";
    if (options.awaitingSetup) return "awaiting";
    return "open";
  }

  function dashboardToolState(context, tool) {
    const resolved = context?.resolvedEntitlements || {};
    const hasWorkspaceFamily = Boolean(getContextFamilyId(context));
    const hasAnyResolvedEntitlements = Object.keys(resolved).length > 0;
    const hasPackageAccess = Boolean(context?.hasPackageAccess);

    if (tool === "billing" || tool === "account_security" || tool === "help_center") {
      return "open";
    }
    if (tool === "upload_hub") {
      if (!hasPackageAccess && !hasAnyResolvedEntitlements) return "check";
      return hasPackageAccess ? "open" : "locked";
    }
    if (tool === "portrait") {
      return accessStateFromFlag(
        Boolean(resolved.can_upload_portraits),
        hasResolvedFlag(resolved, "can_upload_portraits"),
      );
    }
    if (tool === "verification") {
      return accessStateFromFlag(
        Boolean(resolved.can_upload_verification_docs),
        hasResolvedFlag(resolved, "can_upload_verification_docs"),
      );
    }
    if (tool === "vault") {
      return accessStateFromFlag(
        Boolean(resolved.premium_archive_structure),
        hasResolvedFlag(resolved, "premium_archive_structure"),
      );
    }
    if (tool === "tree") {
      return accessStateFromFlag(
        Boolean(resolved.can_build_family_tree),
        hasResolvedFlag(resolved, "can_build_family_tree"),
        { awaitingSetup: !hasWorkspaceFamily },
      );
    }
    if (tool === "certificate") {
      return accessStateFromFlag(
        Boolean(resolved.can_use_lineage_certificate),
        hasResolvedFlag(resolved, "can_use_lineage_certificate"),
        { awaitingSetup: !hasWorkspaceFamily },
      );
    }
    if (tool === "household") {
      return accessStateFromFlag(
        canUseHouseholdAccess(resolved),
        hasResolvedFlag(resolved, "can_build_household") ||
          hasResolvedFlag(resolved, "family_household_scope") ||
          hasResolvedFlag(resolved, "can_link_households"),
      );
    }
    if (tool === "link_keys") {
      return accessStateFromFlag(
        canUseLinkKeyTools(resolved),
        hasResolvedFlag(resolved, "can_use_link_keys") ||
          hasResolvedFlag(resolved, "can_manage_link_keys"),
      );
    }
    if (tool === "intake") {
      return accessStateFromFlag(
        Boolean(
          resolved.can_open_family_intake ||
            resolved.can_open_org_intake ||
            context?.latestSubmission,
        ),
        hasResolvedFlag(resolved, "can_open_family_intake") ||
          hasResolvedFlag(resolved, "can_open_org_intake") ||
          Boolean(context?.latestSubmission),
      );
    }
    return "check";
  }

  function dashboardToolHref(context, tool) {
    const hrefs = {
      account_security: "account-security.html",
      billing: "billing.html",
      certificate: "lineage-certificate.html",
      help_center: "account-security.html",
      household: "household-access.html",
      intake: "intake-review.html",
      link_keys: "link-keys.html",
      portrait: "portrait-upload.html",
      tree: "tree-view.html",
      upload_hub: "upload-hub.html",
      vault: "vault-upload.html",
      verification: "verification-upload.html",
    };
    const href = hrefs[tool] || "";
    if (!href) return "";
    if (tool === "certificate" || tool === "link_keys" || tool === "tree") {
      return withFamilyId(href, context);
    }
    if (tool === "household") {
      return withFamilyId(href, context);
    }
    return href;
  }

  function updateDashboardToolCardStates(context) {
    const stateLabels = {
      awaiting: "Awaiting setup",
      check: "Check access",
      locked: "Package-gated",
      open: "Open",
    };
    const stateKinds = {
      awaiting: "warning",
      check: "info",
      locked: "warning",
      open: "success",
    };

    document.querySelectorAll("[data-dashboard-tool]").forEach(function (node) {
      const tool = normalizeValue(node.dataset.dashboardTool);
      const state = dashboardToolState(context, tool);
      const href = dashboardToolHref(context, tool);
      node.dataset.toolState = state;
      node.style.display = "";
      if (href && node.tagName === "A") {
        node.setAttribute("href", href);
      }

      const status = node.querySelector(".portal-action-status");
      if (status) {
        status.textContent = stateLabels[state] || "Check access";
        status.dataset.state = stateKinds[state] || "info";
      }
    });
  }

  function canUseLinkKeyTools(resolved) {
    return Boolean(resolved?.can_use_link_keys || resolved?.can_manage_link_keys);
  }

  function canUseHouseholdAccess(resolved) {
    return Boolean(
      resolved?.can_build_household ||
        resolved?.family_household_scope ||
        resolved?.can_link_households,
    );
  }

  function updatePackageUnlocksPanel(context) {
    const resolved = context?.resolvedEntitlements || {};
    setUnlockState("[data-unlock-portraits]", Boolean(resolved.can_upload_portraits));
    setUnlockState(
      "[data-unlock-verification]",
      Boolean(resolved.can_upload_verification_docs),
    );
    setUnlockState(
      "[data-unlock-vault]",
      Boolean(resolved.premium_archive_structure),
    );
    setUnlockState(
      "[data-unlock-intake]",
      Boolean(resolved.can_open_family_intake || resolved.can_open_org_intake),
    );
    setUnlockState("[data-unlock-tree]", Boolean(resolved.can_build_family_tree));
    setUnlockState(
      "[data-unlock-certificate]",
      Boolean(resolved.can_use_lineage_certificate),
    );
    setUnlockState("[data-unlock-narration]", Boolean(resolved.can_use_narration));
    setUnlockState("[data-unlock-link-keys]", canUseLinkKeyTools(resolved));
    setUnlockState(
      "[data-unlock-household]",
      canUseHouseholdAccess(resolved),
    );
    setUnlockState(
      "[data-unlock-organization]",
      Boolean(
        resolved.organization_command_scope ||
          resolved.can_build_org_chart ||
          resolved.command_role_mapping_tools ||
          resolved.structured_organization_lineage,
      ),
    );
    setUnlockState(
      "[data-unlock-viewer]",
      Boolean(resolved.can_use_viewer || resolved.can_use_secure_share_viewer),
    );
  }

  function updateReceivedMaterialsPanel(latestSubmission) {
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    const uploads = latestSubmission?.uploads || {};
    const hasPortraitPlan = Boolean(
      normalizeValue(uploads?.key_portraits) || normalizeValue(uploads?.approx_upload_count),
    );
    const hasVerificationPlan = Boolean(
      normalizeValue(uploads?.supporting_records) ||
        hasTruthyField(uploads, "uploads_rights_confirmed") ||
        hasTruthyField(uploads, "uploads_minimization_confirmed"),
    );

    text(
      document.querySelector("[data-received-portraits]"),
      PRODUCTION_OR_BEYOND_STATUSES.has(status)
        ? "Open"
        : hasPortraitPlan
          ? "Check access"
          : "Awaiting setup",
    );
    text(
      document.querySelector("[data-received-verification]"),
      PRODUCTION_OR_BEYOND_STATUSES.has(status)
        ? "Open"
        : hasVerificationPlan
          ? "Check access"
          : "Awaiting setup",
    );
    text(
      document.querySelector("[data-received-vault]"),
      hasVerificationPlan || PRODUCTION_OR_BEYOND_STATUSES.has(status)
        ? "Check access"
        : "Awaiting setup",
    );
    text(
      document.querySelector("[data-received-review]"),
      getReceivedReviewStatusLabel(status),
    );
  }

  function getReceivedReviewStatusLabel(status) {
    if (status === "rejected") return "Needs attention";
    if (REVIEW_PHASE_STATUSES.has(status)) return "Check access";
    if (status === "delivered" || status === "archived") return "Open";
    if (PRODUCTION_OR_BEYOND_STATUSES.has(status)) return "Open";
    return "Awaiting setup";
  }

  function text(node, value) {
    if (!node) return;
    node.textContent = value;
  }

  function setPanelVisible(selector, visible) {
    document.querySelectorAll(selector).forEach(function (node) {
      node.style.display = visible ? "" : "none";
    });
  }

  function applyDashboardHierarchy(context, history) {
    const lane = normalizeValue(context?.packageLane || context?.resolvedEntitlements?.package_lane);
    const isHouseholdLane = lane === "household";
    const historyCount = Array.isArray(history) ? history.length : 0;
    const memberRole = normalizeMemberRole(
      context?.household_access?.member_role,
    );
    const isInvitedCollaborator = Boolean(
      memberRole && memberRole !== "billing_owner",
    );

    // Reduce visual overload for household customers by hiding explanatory
    // duplicate cards and surfacing only operational panels.
    setPanelVisible(".portal-workspace-panel", !isHouseholdLane);
    setPanelVisible(".portal-build-panel", !isHouseholdLane);
    setPanelVisible(".portal-status-panel", !isHouseholdLane);
    setPanelVisible(".portal-orders-panel", !isInvitedCollaborator);
    setPanelVisible("[data-dashboard-purchase-actions]", !isInvitedCollaborator);

    // Intake history is only useful when there is more than one record.
    setPanelVisible(".portal-history-panel", historyCount > 1);
  }

  function normalizeMemberRole(value) {
    const normalized = normalizeValue(value);
    return HOUSEHOLD_MEMBER_ROLE_ALIASES[normalized] || normalized;
  }

  function ensureLegacyPlusMorelandContext(context) {
    const packageCode = normalizeValue(context?.packageCode);
    const lane = normalizeValue(context?.packageLane);
    if (packageCode !== "legacy_plus" || lane !== "household") {
      return context;
    }

    const familyId = getContextFamilyId(context);
    const projectId = getContextProjectId(context);
    if (familyId && projectId) {
      return context;
    }

    const nextActiveProject = Object.assign({}, context?.activeProject || {}, {
      family_id: familyId || MORELAND_FAMILY_TREE.familyId,
      familyId: familyId || MORELAND_FAMILY_TREE.familyId,
      project_id: projectId || MORELAND_FAMILY_TREE.projectId,
      projectId: projectId || MORELAND_FAMILY_TREE.projectId,
      package_code: "legacy_plus",
      package_slug: "legacy_plus",
      package_name: context?.packageName || "Legacy Plus",
      manifest_status: MORELAND_FAMILY_TREE.manifestStatus,
      viewer_status: MORELAND_FAMILY_TREE.viewerStatus,
      family_name: MORELAND_FAMILY_TREE.familyName,
    });

    return Object.assign({}, context, {
      activeProject: nextActiveProject,
      currentWorkspace: Object.assign({}, context?.currentWorkspace || {}, {
        activeProject: nextActiveProject,
        projectId: nextActiveProject.project_id,
        packageCode: "legacy_plus",
      }),
    });
  }

  function canManageHouseholdAccess(memberRole) {
    return HOUSEHOLD_MANAGEMENT_ROLES.has(normalizeMemberRole(memberRole));
  }

  async function resolveDashboardMemberRole(context) {
    const projectId = getContextProjectId(context);
    if (!projectId) return "";

    try {
      const payload = await app.apiRequest("/workspace-access/my-memberships", {
        method: "GET",
      });
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const user =
        context?.user ||
        window.TOLResolvedUser ||
        (typeof app.getSavedUser === "function" ? app.getSavedUser() : null) ||
        {};
      const userId = String(user?.id || user?._id || user?.user_id || "").trim();
      const userEmail = normalizeValue(user?.email);

      const match = items.find(function (item) {
        const membershipProjectId = String(item?.project_id || "").trim();
        if (!membershipProjectId || membershipProjectId !== projectId) return false;
        const status = normalizeValue(item?.status || "active");
        if (status && status !== "active") return false;
        const membershipUserId = String(item?.user_id || "").trim();
        const membershipEmail = normalizeValue(item?.email);
        return (
          (userId && membershipUserId && userId === membershipUserId) ||
          (userEmail && membershipEmail && userEmail === membershipEmail)
        );
      });

      return normalizeMemberRole(match?.member_role);
    } catch (_error) {
      return "";
    }
  }

  function getContextFamilyId(context) {
    return String(
      context?.activeProject?.family_id ||
        context?.activeProject?.familyId ||
        context?.latestSubmission?.family_root_id ||
        context?.latestSubmission?.familyRootId ||
        context?.latestSubmission?.family_id ||
        context?.latestSubmission?.familyId ||
        "",
    ).trim();
  }

  function getContextProjectId(context) {
    return String(
      context?.activeProject?.project_id ||
        context?.activeProject?.projectId ||
        context?.activeProject?.id ||
        context?.activeProject?._id ||
        context?.latestSubmission?.project_id ||
        context?.latestSubmission?.projectId ||
        "",
    ).trim();
  }

  function shortenMiddle(value, head = 12, tail = 8) {
    const normalized = String(value || "").trim();
    if (!normalized || normalized.length <= head + tail + 3) {
      return normalized || "—";
    }
    return `${normalized.slice(0, head)}...${normalized.slice(-tail)}`;
  }

  function reasonLabel(reason) {
    const normalized = normalizeValue(reason);
    if (normalized === "build_not_ready") return "Build completion is still pending.";
    if (normalized === "package_not_included") return "This package does not include on-chain minting.";
    if (normalized === "mint_runtime_disabled") return "Minting is temporarily offline.";
    return humanizeStatus(normalized || "unavailable");
  }

  function chainLabel(chain) {
    const normalized = normalizeValue(chain);
    if (normalized === "base-mainnet" || normalized === "base") return "Base Mainnet";
    if (normalized === "base-sepolia") return "Base Sepolia";
    return chain || "Base Mainnet";
  }

  function baseExplorerUrl(chain) {
    return normalizeValue(chain) === "base-sepolia"
      ? "https://sepolia.basescan.org"
      : "https://basescan.org";
  }

  function buildExplorerLink(anchor) {
    if (!anchor) return "";
    const base = baseExplorerUrl(anchor.chain);
    if (anchor.txHash) return `${base}/tx/${anchor.txHash}`;
    if (anchor.contractAddress && anchor.tokenId) {
      return `${base}/token/${anchor.contractAddress}?a=${encodeURIComponent(anchor.tokenId)}`;
    }
    if (anchor.contractAddress) return `${base}/address/${anchor.contractAddress}`;
    return "";
  }

  function setAnchorCopyButton(selector, value, label) {
    const node = document.querySelector(selector);
    if (!node) return;
    const normalized = String(value || "").trim();
    node.disabled = !normalized;
    node.dataset.copyValue = normalized;
    node.dataset.copyLabel = label;
  }

  function setAnchorLink(selector, href, show) {
    const node = document.querySelector(selector);
    if (!node) return;
    if (href) {
      node.setAttribute("href", href);
    } else {
      node.removeAttribute("href");
    }
    node.style.display = show ? "" : "none";
  }

  function setAnchorPosterPreview(href) {
    const wrapper = document.querySelector("[data-anchor-poster-link-wrapper]");
    const image = document.querySelector("[data-anchor-poster-preview]");
    const empty = document.querySelector("[data-anchor-poster-empty]");

    if (wrapper) {
      if (href) wrapper.setAttribute("href", href);
      else wrapper.removeAttribute("href");
    }

    if (image) {
      if (href) {
        image.src = href;
        image.style.display = "";
      } else {
        image.removeAttribute("src");
        image.style.display = "none";
      }
    }

    if (empty) {
      empty.style.display = href ? "none" : "";
    }
  }

  function resolveAnchorPresentation(hasProject, eligibility, mintStatus) {
    const latest = mintStatus && mintStatus.latest ? mintStatus.latest : null;
    const latestStatus = normalizeValue(latest && latest.mint_status);
    const reasons = Array.isArray(eligibility && eligibility.reasons)
      ? eligibility.reasons
      : [];
    const missingApprovals = Array.isArray(eligibility && eligibility.missing_approvals)
      ? eligibility.missing_approvals
      : [];
    const policy =
      eligibility && eligibility.mint_policy ? eligibility.mint_policy : {};

    if (!hasProject) {
      return {
        badge: "Awaiting setup",
        copy: "A provisioned workspace is required before Tomb of Light can prepare your Legacy Anchor.",
        note: "Once your project is provisioned, this panel will show live mint status, public proof links, and wallet verification.",
      };
    }

    if (!policy.product_includes_onchain_anchor) {
      return {
        badge: "Package-gated",
        copy: "This package does not include an on-chain Legacy Anchor.",
        note: "Upgrade into an eligible package to unlock Base Mainnet anchor minting and public-safe proof records.",
      };
    }

    if (latestStatus === "minted") {
      return {
        badge: "Minted",
        copy: "Your Legacy Anchor has been minted successfully on Base Mainnet.",
        note: "Use the contract address, token ID, transaction hash, explorer link, metadata, and poster below to prove the anchor exists without exposing private family records.",
      };
    }

    if (latestStatus === "minting") {
      return {
        badge: "Minting",
        copy: "Your Legacy Anchor transaction has been submitted and is waiting for receipt sync.",
        note: "The panel will finalize the token ID and proof links as soon as the Base receipt confirms.",
      };
    }

    if (latestStatus === "queued") {
      return {
        badge: "Queued",
        copy: "Your Legacy Anchor is queued for public-safe manifest, poster, mint, and receipt sync.",
        note: "Tomb of Light will only finalize the anchor after approvals, mint execution, and receipt confirmation are complete.",
      };
    }

    if (latestStatus === "approved") {
      return {
        badge: "Approved",
        copy: "Your Legacy Anchor is approved and ready for final mint processing.",
        note: "The remaining step is controlled minting flow through Tomb of Light.",
      };
    }

    if (latestStatus === "pending_approval" || missingApprovals.length > 0) {
      return {
        badge: "Waiting for Approval",
        copy: "Your Legacy Anchor is waiting for the required approval flow before it can be queued.",
        note:
          missingApprovals.length > 0
            ? `Missing approvals: ${missingApprovals
                .map(humanizeStatus)
                .join(", ")}.`
            : "Admin final approval and customer public-safe approval must both be completed first.",
      };
    }

    if (latestStatus === "failed") {
      return {
        badge: "Failed",
        copy: "The last Legacy Anchor attempt failed and needs review before a new version is queued.",
        note:
          latest && latest.error_message
            ? latest.error_message
            : "Review the recorded error, correct it, and re-queue the newest mint record.",
      };
    }

    if (reasons.includes("build_not_ready")) {
      return {
        badge: "Waiting for Build",
        copy: "Your package is eligible, but the build is not complete enough to mint yet.",
        note: reasons.map(reasonLabel).join(" "),
      };
    }

    if (reasons.includes("mint_runtime_disabled")) {
      return {
        badge: "Minting Offline",
        copy: "Your package is eligible, but Tomb of Light minting is temporarily disabled in the live runtime.",
        note: "Once the live mint runtime is enabled again, this panel will resume from the current approved state.",
      };
    }

    return {
      badge: "Waiting for Approval",
      copy: "Your Legacy Anchor will appear here once the public-safe approval flow starts for this workspace.",
      note: "Eligible customers will be able to prove the anchor through on-chain, wallet, explorer, and metadata proof layers from this panel.",
    };
  }

  function setLegacyAnchorUnavailable(copy, note) {
    const presentation = {
      badge: "Unavailable",
      copy: copy || "Legacy Anchor status is temporarily unavailable.",
      note:
        note ||
        "Please refresh the dashboard shortly. Tomb of Light will show public-safe proof details here when the workspace is ready.",
    };

    legacyAnchorState = null;
    text(document.querySelector("[data-anchor-status-badge]"), presentation.badge);
    text(document.querySelector("[data-anchor-status-copy]"), presentation.copy);
    text(document.querySelector("[data-anchor-proof-note]"), presentation.note);
    text(
      document.querySelector("[data-anchor-proof-copy]"),
      "Public proof details will appear here after Tomb of Light prepares or mints your anchor.",
    );
    text(document.querySelector("[data-anchor-chain]"), "—");
    text(document.querySelector("[data-anchor-contract]"), "—");
    text(document.querySelector("[data-anchor-token-id]"), "—");
    text(document.querySelector("[data-anchor-tx-hash]"), "—");
    text(document.querySelector("[data-anchor-recipient-wallet]"), "—");
    text(document.querySelector("[data-anchor-public-token-id]"), "—");
    text(
      document.querySelector("[data-anchor-verify-status]"),
      "Wallet proof will appear here when you verify the recipient wallet.",
    );
    setAnchorPosterPreview("");
    setAnchorLink("[data-anchor-explorer-link]", "", false);
    setAnchorLink("[data-anchor-metadata-link]", "", false);
    setAnchorLink("[data-anchor-poster-link]", "", false);
    setAnchorCopyButton("[data-anchor-copy-contract]", "", "contract");
    setAnchorCopyButton("[data-anchor-copy-tx]", "", "transaction hash");
    setAnchorCopyButton("[data-anchor-copy-token]", "", "token id");
    setAnchorCopyButton("[data-anchor-copy-public-token]", "", "public token id");
    const verifyButton = document.querySelector("[data-anchor-verify-wallet]");
    if (verifyButton) verifyButton.disabled = true;
  }

  async function copyAnchorValue(button) {
    if (!button) return;
    const value = String(button.dataset.copyValue || "").trim();
    const label = String(button.dataset.copyLabel || "value").trim();
    const statusNode = document.querySelector("[data-anchor-verify-status]");

    if (!value) {
      text(statusNode, `No ${label} is available yet.`);
      return;
    }

    try {
      await navigator.clipboard.writeText(value);
      text(statusNode, `${label.charAt(0).toUpperCase() + label.slice(1)} copied.`);
    } catch (error) {
      text(statusNode, `Could not copy the ${label} automatically.`);
    }
  }

  async function verifyLegacyAnchorWallet() {
    const statusNode = document.querySelector("[data-anchor-verify-status]");

    if (!legacyAnchorState || !legacyAnchorState.recipientWallet) {
      text(statusNode, "A recipient wallet must be recorded before wallet ownership can be verified.");
      return;
    }

    if (!window.ethereum || typeof window.ethereum.request !== "function") {
      text(
        statusNode,
        "Open the wallet that received this anchor in a browser with wallet access to verify ownership here.",
      );
      return;
    }

    try {
      const accounts = await window.ethereum.request({
        method: "eth_requestAccounts",
      });
      const selected = Array.isArray(accounts) && accounts[0] ? String(accounts[0]) : "";

      if (normalizeValue(selected) !== normalizeValue(legacyAnchorState.recipientWallet)) {
        text(
          statusNode,
          `Connected wallet ${shortenMiddle(selected)} does not match the recorded recipient ${shortenMiddle(legacyAnchorState.recipientWallet)}.`,
        );
        return;
      }

      const message = [
        "Tomb of Light wallet ownership verification",
        `Legacy Anchor: ${legacyAnchorState.publicTokenId || "pending"}`,
        `Wallet: ${legacyAnchorState.recipientWallet}`,
        `Timestamp: ${new Date().toISOString()}`,
      ].join("\n");

      const signature = await window.ethereum.request({
        method: "personal_sign",
        params: [message, selected],
      });

      text(
        statusNode,
        `Wallet ownership verified for ${shortenMiddle(selected)}. Signature proof: ${shortenMiddle(signature, 14, 12)}.`,
      );
    } catch (error) {
      text(
        statusNode,
        `Wallet verification did not complete: ${String(error && error.message ? error.message : error)}`,
      );
    }
  }

  function bindLegacyAnchorInteractions() {
    [
      "[data-anchor-copy-contract]",
      "[data-anchor-copy-tx]",
      "[data-anchor-copy-token]",
      "[data-anchor-copy-public-token]",
    ].forEach(function (selector) {
      const button = document.querySelector(selector);
      if (!button || button.dataset.bound === "true") return;
      button.dataset.bound = "true";
      button.addEventListener("click", function () {
        copyAnchorValue(button);
      });
    });

    const verifyButton = document.querySelector("[data-anchor-verify-wallet]");
    if (verifyButton && verifyButton.dataset.bound !== "true") {
      verifyButton.dataset.bound = "true";
      verifyButton.addEventListener("click", function () {
        verifyLegacyAnchorWallet();
      });
    }
  }

  async function getMintEligibility(projectId) {
    return await app.apiRequest(
      `/projects/${encodeURIComponent(projectId)}/mint-eligibility`,
      { method: "GET" },
    );
  }

  async function getMintStatus(projectId) {
    return await app.apiRequest(
      `/projects/${encodeURIComponent(projectId)}/mint-status`,
      { method: "GET" },
    );
  }

  async function updateLegacyAnchorPanel(context) {
    bindLegacyAnchorInteractions();

    const projectId = getContextProjectId(context);
    if (!projectId) {
      setLegacyAnchorUnavailable(
        "Your workspace is still being provisioned, so Tomb of Light cannot prepare a Legacy Anchor yet.",
      );
      return;
    }

    try {
      const [eligibility, mintStatus] = await Promise.all([
        getMintEligibility(projectId),
        getMintStatus(projectId),
      ]);

      const presentation = resolveAnchorPresentation(true, eligibility, mintStatus);
      const latest = mintStatus && mintStatus.latest ? mintStatus.latest : null;
      const explorerLink = buildExplorerLink({
        chain: latest && latest.chain ? latest.chain : "base-mainnet",
        contractAddress: latest && latest.contract_address ? latest.contract_address : "",
        tokenId: latest && latest.token_id ? latest.token_id : "",
        txHash: latest && latest.tx_hash ? latest.tx_hash : "",
      });

      legacyAnchorState = {
        chain: latest && latest.chain ? latest.chain : "base-mainnet",
        contractAddress: latest && latest.contract_address ? latest.contract_address : "",
        tokenId: latest && latest.token_id ? latest.token_id : "",
        txHash: latest && latest.tx_hash ? latest.tx_hash : "",
        recipientWallet: latest && latest.customer_wallet ? latest.customer_wallet : "",
        publicTokenId: latest && latest.public_token_id ? latest.public_token_id : "",
        metadataUri: latest && latest.metadata_uri ? latest.metadata_uri : "",
        posterUrl:
          latest && latest.poster_image_uri_public
            ? latest.poster_image_uri_public
            : "",
        explorerUrl: explorerLink,
      };

      text(document.querySelector("[data-anchor-status-badge]"), presentation.badge);
      text(document.querySelector("[data-anchor-status-copy]"), presentation.copy);
      text(document.querySelector("[data-anchor-proof-note]"), presentation.note);
      text(
        document.querySelector("[data-anchor-proof-copy]"),
        legacyAnchorState.tokenId && legacyAnchorState.txHash
          ? "This NFT was minted to your wallet on Base Mainnet. Use the contract address, token ID, transaction hash, and public metadata record below to prove it."
          : "Once minted, Tomb of Light will let you prove the Legacy Anchor through on-chain, wallet, explorer, and metadata proof at the same time.",
      );

      text(
        document.querySelector("[data-anchor-chain]"),
        chainLabel(legacyAnchorState.chain),
      );
      text(
        document.querySelector("[data-anchor-contract]"),
        legacyAnchorState.contractAddress || "Pending mint",
      );
      text(
        document.querySelector("[data-anchor-token-id]"),
        legacyAnchorState.tokenId || "Pending receipt sync",
      );
      text(
        document.querySelector("[data-anchor-tx-hash]"),
        legacyAnchorState.txHash || "Pending transaction",
      );
      text(
        document.querySelector("[data-anchor-recipient-wallet]"),
        legacyAnchorState.recipientWallet || "Awaiting customer approval",
      );
      text(
        document.querySelector("[data-anchor-public-token-id]"),
        legacyAnchorState.publicTokenId || "Preparing public token ID",
      );

      setAnchorPosterPreview(legacyAnchorState.posterUrl);
      setAnchorLink(
        "[data-anchor-explorer-link]",
        legacyAnchorState.explorerUrl,
        Boolean(legacyAnchorState.explorerUrl),
      );
      setAnchorLink(
        "[data-anchor-metadata-link]",
        legacyAnchorState.metadataUri,
        Boolean(legacyAnchorState.metadataUri),
      );
      setAnchorLink(
        "[data-anchor-poster-link]",
        legacyAnchorState.posterUrl,
        Boolean(legacyAnchorState.posterUrl),
      );

      setAnchorCopyButton(
        "[data-anchor-copy-contract]",
        legacyAnchorState.contractAddress,
        "contract address",
      );
      setAnchorCopyButton(
        "[data-anchor-copy-tx]",
        legacyAnchorState.txHash,
        "transaction hash",
      );
      setAnchorCopyButton(
        "[data-anchor-copy-token]",
        legacyAnchorState.tokenId,
        "token id",
      );
      setAnchorCopyButton(
        "[data-anchor-copy-public-token]",
        legacyAnchorState.publicTokenId,
        "public token id",
      );

      const verifyButton = document.querySelector("[data-anchor-verify-wallet]");
      if (verifyButton) {
        verifyButton.disabled = !legacyAnchorState.recipientWallet;
      }

      text(
        document.querySelector("[data-anchor-verify-status]"),
        legacyAnchorState.recipientWallet
          ? "Connect the wallet that received this anchor to verify ownership here."
          : "Wallet proof will appear here once a recipient wallet is recorded.",
      );
    } catch (error) {
      setLegacyAnchorUnavailable(
        "Legacy Anchor status could not be loaded right now.",
        String(error && error.message ? error.message : error),
      );
    }
  }

  function withFamilyId(href, context) {
    const familyId = getContextFamilyId(context);
    const projectId = getContextProjectId(context);

    if (!href || (!familyId && !projectId)) return href;

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

  function getLaneLabel(lane) {
    if (lane === "portrait") return "Portrait Lane";
    if (lane === "organization") return "Organization Lane";
    if (lane === "network") return "Network Lane";
    return "Household Lane";
  }

  function getPortalHeroTitle(lane) {
    if (lane === "portrait") return "Your Portrait Chamber";
    if (lane === "organization") return "Your Structure Command";
    if (lane === "network") return "Your Network Chamber";
    return "Your Lineage Chamber";
  }

  function getPortalScopeLabel(config) {
    if (config.lane === "portrait") {
      return config.showLinkKeys ? "Portrait + Linking" : "Portrait Scope";
    }

    if (config.lane === "organization") {
      return "Structure Scope";
    }

    if (config.lane === "network") {
      return "Network Build Scope";
    }

    return "Household Build Scope";
  }

  function applyPortalTheme(context, config) {
    const body = document.body;
    const dashboard = document.querySelector("[data-dashboard]");
    const packageName = context.packageName || "Active Package";
    const laneLabel = getLaneLabel(config.lane);

    if (body) {
      body.classList.add("portal-dashboard-body");
      body.classList.remove("portal-admin-mode");
      body.dataset.portalMode = "customer";
      body.dataset.portalLane = config.lane;
    }

    if (dashboard) {
      dashboard.setAttribute("data-portal-mode", "customer");
      dashboard.setAttribute("data-portal-lane", config.lane);
    }

    text(document.querySelector("[data-dashboard-hero-eyebrow]"), laneLabel);
    text(document.querySelector("[data-dashboard-hero-title]"), getPortalHeroTitle(config.lane));
    text(document.querySelector("[data-dashboard-lane-chip]"), laneLabel);
    text(document.querySelector("[data-dashboard-package-chip]"), packageName);
    text(document.querySelector("[data-dashboard-scope-chip]"), getPortalScopeLabel(config));
    text(document.querySelector("[data-dashboard-core-label]"), laneLabel);
    text(document.querySelector("[data-dashboard-core-subtitle]"), config.presenceBadge);
    text(document.querySelector("[data-dashboard-lane-summary]"), laneLabel);
    text(
      document.querySelector("[data-dashboard-lane-description]"),
      config.presenceCopy,
    );
    text(document.querySelector("[data-dashboard-package-display]"), packageName);
    text(
      document.querySelector("[data-dashboard-next-focus]"),
      config.primaryActionText || "Open Workspace",
    );
  }

  function findPanelByText(textFragment) {
    return Array.from(document.querySelectorAll(".form-panel")).find(
      function (panel) {
        return panel.textContent.includes(textFragment);
      },
    );
  }

  function setPanelStep(panel, index, title, copy) {
    if (!panel) return;

    const cards = panel.querySelectorAll(".grid-3 > div");
    const card = cards[index];
    if (!card) return;

    const h3 = card.querySelector("h3");
    const p = card.querySelector(".card-copy");

    if (h3) h3.textContent = title;
    if (p) p.textContent = copy;
  }

  function applyAction(selector, options) {
    document.querySelectorAll(selector).forEach(function (node) {
      if (options.text) {
        node.textContent = options.text;
      }

      if (options.href && node.tagName === "A") {
        node.setAttribute("href", options.href);
      }

      if (typeof options.show === "boolean") {
        node.style.display = options.show ? "" : "none";
      }
    });
  }

  function applyNavVisibility(href, isVisible) {
    document
      .querySelectorAll(`.site-nav a[href="${href}"]`)
      .forEach(function (node) {
        node.style.display = isVisible ? "" : "none";
      });
  }

  function updatePresencePanel(config) {
    const badge = document.querySelector(".presence-badge");
    const title = document.querySelector(".dashboard-presence-title");
    const copy = document.querySelector(".dashboard-presence-copy");
    const stageNodes = document.querySelectorAll(".workspace-stage-node");

    text(badge, config.presenceBadge);
    text(title, config.presenceTitle);
    text(copy, config.presenceCopy);

    stageNodes.forEach(function (node, index) {
      const strong = node.querySelector("strong");
      const small = node.querySelector("small");
      const item = config.stages[index];

      if (!item) return;
      if (strong) strong.textContent = item.title;
      if (small) small.textContent = item.subtitle;
    });
  }

  function updateBuildPathPanel(config) {
    const panel =
      findPanelByText("Your Build Path") ||
      findPanelByText("Your Family Build Path") ||
      findPanelByText("Your Build Path") ||
      findPanelByText("Your Portrait Workflow") ||
      findPanelByText("Your Command Build Path") ||
      findPanelByText("Your Network Build Path");

    if (!panel) return;

    const eyebrow = panel.querySelector(".eyebrow");
    if (eyebrow) eyebrow.textContent = config.buildPathEyebrow;

    setPanelStep(
      panel,
      0,
      config.buildSteps[0].title,
      config.buildSteps[0].copy,
    );
    setPanelStep(
      panel,
      1,
      config.buildSteps[1].title,
      config.buildSteps[1].copy,
    );
    setPanelStep(
      panel,
      2,
      config.buildSteps[2].title,
      config.buildSteps[2].copy,
    );
  }

  function updatePlatformStatusPanel(config) {
    const panel = findPanelByText("Platform Status");
    if (!panel) return;

    setPanelStep(
      panel,
      2,
      config.platformStatusTitle,
      config.platformStatusCopy,
    );
  }

  function isProductionStatus(status) {
    return PRODUCTION_STATUSES.has(normalizeStatus(status));
  }

  function getPrimaryWorkspaceAction(context, config, latestSubmission) {
    const resolved = context?.resolvedEntitlements || {};
    const lane = normalizeValue(context?.packageLane || resolved.package_lane);
    const status = normalizeStatus(
      latestSubmission?.status || latestSubmission?.submission_status,
    );
    const hasWorkspaceFamily = Boolean(getContextFamilyId(context));
    const canOpenIntake = Boolean(
      resolved.can_open_family_intake || resolved.can_open_org_intake,
    );

    if (lane === "portrait" || lane === "organization") {
      return {
        text: config.primaryActionText,
        href: config.primaryActionHref,
        show: true,
      };
    }

    if (hasWorkspaceFamily || isProductionStatus(status)) {
      if (hasWorkspaceFamily) {
        return {
          text: config.primaryActionText,
          href: config.primaryActionHref,
          show: true,
        };
      }

      return {
        text: "View Intake Record",
        href: "intake-review.html",
        show: true,
      };
    }

    if (status === "rejected") {
      return {
        text: "Resume Intake",
        href: "intake-household.html",
        show: true,
      };
    }

    if (isLockedStatus(status)) {
      return {
        text: "View Intake Record",
        href: "intake-review.html",
        show: true,
      };
    }

    if (!status && canOpenIntake) {
      return {
        text: "Start Intake",
        href: "intake-welcome.html",
        show: true,
      };
    }

    return {
      text: "View Intake",
      href: "intake-welcome.html",
      show: canOpenIntake,
    };
  }

  function getEntitlementConfig(context) {
    const resolved = context?.resolvedEntitlements || {};
    const lane = normalizeValue(context?.packageLane || resolved?.package_lane);
    const packageName = context?.packageName || "Active Package";

    const canBuildFamilyTree = Boolean(resolved.can_build_family_tree);
    const canUseCertificate = Boolean(resolved.can_use_lineage_certificate);
    const canUploadRecords = Boolean(
      resolved.can_upload_verification_docs || resolved.can_upload_portraits,
    );
    const canUseLinkKeys = canUseLinkKeyTools(resolved);
    const canUseHousehold = canUseHouseholdAccess(resolved);
    const hasLinkedOrganizationSupport = Boolean(
      resolved.linked_organization_support || resolved.can_link_org_units,
    );
    const canOpenFamilyIntake = Boolean(resolved.can_open_family_intake);
    const canOpenOrgIntake = Boolean(resolved.can_open_org_intake);

    if (lane === "portrait") {
      return {
        lane: "portrait",
        presenceBadge: "Portrait Lane Active",
        presenceTitle: "Your portrait workspace is live and connected.",
        presenceCopy: canUseLinkKeys
          ? "Tomb of Light is now reading from your portrait package, uploads, verification records, and link capabilities."
          : "Tomb of Light is now reading from your portrait package, uploads, and verification records.",
        stages: [
          { title: "Portrait Record", subtitle: "Connected" },
          {
            title: "Verification",
            subtitle: canUploadRecords ? "Upload Ready" : "Locked",
          },
          {
            title: "Link Capabilities",
            subtitle: canUseLinkKeys ? "Enabled" : "Unavailable",
          },
        ],
        workspaceCopy: canUseLinkKeys
          ? "Your portrait workspace connects package access, portrait uploads, verification records, guided delivery, and link capabilities in one place."
          : "Your portrait workspace connects package access, portrait uploads, verification records, and guided delivery in one place.",
        primaryActionText: "Upload Photos & Family Records",
        primaryActionHref: "portrait-upload.html",
        secondaryActionText: "Verification Uploads",
        secondaryActionHref: "verification-upload.html",
        showTree: canBuildFamilyTree,
        showCertificate: canBuildFamilyTree,
        showVerification: true,
        showLinkKeys: canUseLinkKeys,
        showHouseholdAccess: false,
        navTree: false,
        navCertificate: false,
        navIntake: false,
        navLinkKeys: canUseLinkKeys,
        buildPathEyebrow: "Your Portrait Workflow",
        buildSteps: [
          {
            title: "Portrait Anchor",
            copy: "Begin with your portrait, files, and personal legacy materials.",
          },
          {
            title: "Verification Evidence",
            copy: "Upload IDs and supporting records that help verify the portrait record.",
          },
          {
            title: "Delivery, Linking & Upgrade Path",
            copy: canUseLinkKeys
              ? "Receive your portrait package, use link capabilities, and upgrade whenever you are ready."
              : "Receive your portrait package and upgrade whenever you are ready.",
          },
        ],
        platformStatusTitle: "Entitled Tools",
        platformStatusCopy: canUseLinkKeys
          ? "This portrait lane includes portrait uploads, verification workflows, and link capabilities. Household build tools require an upgrade."
          : "This portrait lane includes portrait uploads and verification workflows. Household build tools require an upgrade.",
        upgradeText: "Upgrade to Household Package",
        upgradeHref: "billing.html",
      };
    }

    if (lane === "organization") {
      return {
        lane: "organization",
        presenceBadge: "Organization Lane Active",
        presenceTitle:
          "Your command structure workspace is live and connected.",
        presenceCopy: hasLinkedOrganizationSupport
          ? "Tomb of Light is now reading from your organization package, role structure scope, supporting record workflow, and linked organization support."
          : "Tomb of Light is now reading from your organization package, role structure scope, and supporting record workflow.",
        stages: [
          { title: "Organization Root", subtitle: "Connected" },
          {
            title: "Structure Build",
            subtitle: canOpenOrgIntake ? "Configured" : "Prepared",
          },
          {
            title: "Linked Organization Support",
            subtitle: hasLinkedOrganizationSupport ? "Enabled" : "Unavailable",
          },
        ],
        workspaceCopy: hasLinkedOrganizationSupport
          ? "Your organization workspace connects package access, command structure planning, uploads, and linked organization support in one place."
          : "Your organization workspace connects package access, command structure planning, uploads, and guided record handling in one place.",
        primaryActionText: "Upload Verification Documents",
        primaryActionHref: "verification-upload.html",
        secondaryActionText: "Upload Structure Records",
        secondaryActionHref: "verification-upload.html",
        showTree: canBuildFamilyTree,
        showCertificate: canBuildFamilyTree,
        showVerification: true,
        showLinkKeys: canUseLinkKeys,
        showHouseholdAccess: false,
        navTree: false,
        navCertificate: false,
        navIntake: false,
        navLinkKeys: canUseLinkKeys,
        buildPathEyebrow: "Your Command Build Path",
        buildSteps: [
          {
            title: "Organization Root",
            copy: "Establish the core organization or command structure anchor.",
          },
          {
            title: "Leadership Structure",
            copy: "Add leadership roles, officers, or command nodes as the structure expands.",
          },
          {
            title: "Supporting Records & Expansion",
            copy: hasLinkedOrganizationSupport
              ? "Upload supporting materials, use linked organization support, and expand the structure when needed."
              : "Upload supporting records and materials tied to the organization build.",
          },
        ],
        platformStatusTitle: "Entitled Tools",
        platformStatusCopy: hasLinkedOrganizationSupport
          ? "This organization lane includes structure workflows, verification uploads, and linked organization support."
          : "This organization lane includes structure and verification workflows. Expansion options are available if you need more scope.",
        upgradeText: "View Expansion Options",
        upgradeHref: "billing.html",
      };
    }

    if (lane === "network") {
      return {
        lane: "network",
        presenceBadge: "Network Lane Active",
        presenceTitle: "Your network workspace is live and connected.",
        presenceCopy: canUseLinkKeys
          ? "Tomb of Light is now reading from your branch network package, household connections, lineage workflow, and link capabilities."
          : "Tomb of Light is now reading from your branch network package, household connections, and expanded lineage workflow.",
        stages: [
          { title: "Branch Root", subtitle: "Connected" },
          {
            title: "Network Build",
            subtitle: canBuildFamilyTree ? "Build Ready" : "Prepared",
          },
          {
            title: "Living Outputs",
            subtitle: canUseCertificate ? "Tree + Certificate Live" : "Live",
          },
        ],
        workspaceCopy: canUseLinkKeys
          ? "Your network workspace connects package access, linked branches, lineage structure, verification records, and link capabilities in one place."
          : "Your network workspace connects package access, linked branches, lineage structure, and verification records in one place.",
        primaryActionText: "Open Family Tree",
        primaryActionHref: "tree-view.html",
        secondaryActionText: "Upload Verification Documents",
        secondaryActionHref: "verification-upload.html",
        showTree: canBuildFamilyTree,
        showCertificate: canUseCertificate,
        showVerification: true,
        showLinkKeys: canUseLinkKeys,
        showHouseholdAccess: canUseHousehold,
        navTree: canBuildFamilyTree,
        navCertificate: canUseCertificate,
        navIntake: canOpenFamilyIntake,
        navLinkKeys: canUseLinkKeys,
        buildPathEyebrow: "Your Network Build Path",
        buildSteps: [
          {
            title: "Branch Root",
            copy: "Establish the connected household or branch structure that anchors the network.",
          },
          {
            title: "Linked Households",
            copy: "Add linked households, branches, and connected lineage structures over time.",
          },
          {
            title: "Verification, Delivery & Linking",
            copy: canUseLinkKeys
              ? "Upload supporting records, continue delivery, and use link capabilities across the network."
              : "Upload IDs, certificates, and supporting family records for the network build.",
          },
        ],
        platformStatusTitle: "Entitled Tools",
        platformStatusCopy: canUseLinkKeys
          ? "This network lane includes branch, lineage, verification, certificate, and link workflows."
          : "This network lane includes branch, lineage, and verification workflows.",
        upgradeText: "View Expansion Options",
        upgradeHref: "billing.html",
      };
    }

    return {
      lane: "household",
      presenceBadge: "Household Lane Active",
      presenceTitle: "Your lineage workspace is live and connected.",
      presenceCopy: canUseLinkKeys
        ? "Tomb of Light is now reading from your household package, family structure, verification workflow, and link capabilities."
        : "Tomb of Light is now reading from your household package, family structure, project records, and verification workflow.",
      stages: [
        { title: "Family Root", subtitle: "Connected" },
        {
          title: "Production Build",
          subtitle: canBuildFamilyTree ? "Build Ready" : "Prepared",
        },
        {
          title: "Living Outputs",
          subtitle: canUseCertificate ? "Tree + Certificate Live" : "Live",
        },
      ],
      workspaceCopy: canUseLinkKeys
        ? "Your Tomb of Light customer workspace connects package access, onboarding, family structure, lineage tools, verification, and link capabilities in one place."
        : "Your Tomb of Light customer workspace connects package access, onboarding, family structure, lineage tools, and document-backed verification in one place.",
      primaryActionText: "Open Family Tree",
      primaryActionHref: "tree-view.html",
      secondaryActionText: "Upload Verification Documents",
      secondaryActionHref: "verification-upload.html",
      showTree: canBuildFamilyTree,
      showCertificate: canUseCertificate,
      showVerification: true,
      showLinkKeys: canUseLinkKeys,
      showHouseholdAccess: canUseHousehold,
      navTree: canBuildFamilyTree,
      navCertificate: canUseCertificate,
      navIntake: canOpenFamilyIntake,
      navLinkKeys: canUseLinkKeys,
      buildPathEyebrow: "Your Family Build Path",
      buildSteps: [
        {
          title: "Family Root",
          copy: "Establish the household family record that anchors your lineage build.",
        },
        {
          title: "Members and Relationships",
          copy: "Add parents, spouses, children, and connected branches over time.",
        },
        {
          title: "Verification, Delivery & Linking",
          copy: canUseLinkKeys
            ? "Upload supporting family documents, continue delivery, and use link capabilities as included in your package."
            : "Upload IDs, birth certificates, marriage records, adoption records, and supporting family documents for review.",
        },
      ],
      platformStatusTitle: "Entitled Tools",
      platformStatusCopy: canUseLinkKeys
        ? "Family build tools, verification workflows, certificate access, and link capabilities are active for this package."
        : "Family build tools and verification workflows are active for this household lane package.",
      upgradeText: "View Add-Ons & Upgrades",
      upgradeHref: "billing.html",
    };
  }

  function getLaneAwareIntakeMessages(context, status) {
    const resolved = context?.resolvedEntitlements || {};
    const normalizedLane = normalizeValue(
      context?.packageLane || resolved.package_lane,
    );
    const normalizedStatus = normalizeStatus(status);
    const canUseLinkKeys = canUseLinkKeyTools(resolved);

    if (normalizedLane === "portrait") {
      if (normalizedStatus === "build_ready") {
        return {
          cardCopy: canUseLinkKeys
            ? "Your portrait package is approved and ready for portrait, verification, and link-enabled work."
            : "Your portrait package is approved and ready for portrait and verification work.",
          nextStep:
            "Upload the portrait first, then add verification records only if needed.",
          lockNote:
            "Editing is locked because this portrait package has already been approved and provisioned.",
          workspaceCopy: canUseLinkKeys
            ? "Your portrait intake has been approved and provisioned. This workspace now moves into the portrait record stage with link capabilities available."
            : "Your portrait intake has been approved and provisioned. This workspace now moves from onboarding into the portrait record stage.",
        };
      }

      return {
        cardCopy: "Your portrait intake information is shown below.",
        nextStep:
          "Upload the portrait first, then add verification records only if needed.",
        lockNote: "Intake lock state is based on your current review status.",
        workspaceCopy: canUseLinkKeys
          ? "Your portrait workspace connects package access, portrait uploads, verification records, guided delivery, and link capabilities in one place."
          : "Your portrait workspace connects package access, portrait uploads, verification records, and guided delivery in one place.",
      };
    }

    if (normalizedLane === "organization") {
      if (normalizedStatus === "build_ready") {
        return {
          cardCopy: canUseLinkKeys
            ? "Your organization package is approved and ready for structure, record, and link-enabled work."
            : "Your organization package is approved and ready for structure and record work.",
          nextStep:
            "Upload leadership, structure, and supporting records to continue.",
          lockNote:
            "Editing is locked because this organization package has already been approved and provisioned.",
          workspaceCopy: canUseLinkKeys
            ? "Your organization intake has been approved and provisioned. This workspace now moves into the command structure stage with link capabilities available."
            : "Your organization intake has been approved and provisioned. This workspace now moves into the command structure stage.",
        };
      }

      return {
        cardCopy: "Your organization intake information is shown below.",
        nextStep: "Upload structure and supporting records to continue.",
        lockNote: "Intake lock state is based on your current review status.",
        workspaceCopy: canUseLinkKeys
          ? "Your organization workspace connects package access, command structure planning, uploads, and link capabilities in one place."
          : "Your organization workspace connects package access, command structure planning, uploads, and guided record handling in one place.",
      };
    }

    if (normalizedLane === "network" && normalizedStatus === "build_ready") {
      return {
        cardCopy: canUseLinkKeys
          ? "Your network intake has been approved and provisioned for production with link capabilities active."
          : "Your network intake has been approved and provisioned for production.",
        nextStep:
          "Production records are created. Next step is building branches and linked households.",
        lockNote:
          "Editing is locked because this network project has already been approved and provisioned.",
        workspaceCopy: canUseLinkKeys
          ? "Your network intake has been approved and provisioned. This workspace now moves into connected branch, household build, and link-enabled operation."
          : "Your network intake has been approved and provisioned. This workspace now moves into connected branch and household build.",
      };
    }

    if (normalizedStatus === "build_ready") {
      return {
        cardCopy: canUseLinkKeys
          ? "Your intake has been approved and provisioned for production with link capabilities active."
          : "Your intake has been approved and provisioned for production.",
        nextStep:
          "Production records are created. Next step is building members and relationships.",
        lockNote:
          "Editing is locked. This intake has already been approved and provisioned.",
        workspaceCopy: canUseLinkKeys
          ? "Your intake has been approved and provisioned. This workspace now moves from onboarding into the real family build stage with link capabilities available."
          : "Your intake has been approved and provisioned. This workspace now moves from onboarding into the real family build stage.",
      };
    }

    return {
      cardCopy: "Your most recent intake submission is shown below.",
      nextStep: "Continue and finalize your intake.",
      lockNote: "Editing is still open until final submission.",
      workspaceCopy: canUseLinkKeys
        ? "Your Tomb of Light customer workspace connects package access, onboarding, lineage tools, and link capabilities in one place."
        : "Your Tomb of Light customer workspace connects package access, onboarding, family structure, lineage tools, and document-backed verification in one place.",
    };
  }

  function updateLaneUi(context, config, latestSubmission) {
    updatePresencePanel(config);
    updateBuildPathPanel(config);
    updatePlatformStatusPanel(config);

    const hasWorkspaceFamily = Boolean(getContextFamilyId(context));
    const showTreeActions = config.showTree && hasWorkspaceFamily;
    const showCertificateActions = config.showCertificate && hasWorkspaceFamily;
    const primaryAction = getPrimaryWorkspaceAction(
      context,
      config,
      latestSubmission,
    );
    const explicitHouseholdManageFlag = context?.household_access?.can_manage;
    const showHouseholdInviteActions =
      typeof explicitHouseholdManageFlag === "boolean"
        ? explicitHouseholdManageFlag
        : true;

    applyNavVisibility("tree-view.html", config.navTree && hasWorkspaceFamily);
    applyNavVisibility(
      "lineage-certificate.html",
      config.navCertificate && hasWorkspaceFamily,
    );
    applyNavVisibility("intake-review.html", config.navIntake);
    applyNavVisibility(
      "portrait-upload.html",
      config.lane === "portrait" && config.showVerification,
    );
    applyNavVisibility("verification-upload.html", config.showVerification);
    applyNavVisibility("link-keys.html", config.navLinkKeys);
    applyNavVisibility("household-access.html", config.showHouseholdAccess);

    applyAction('.site-nav a[href^="tree-view.html"]', {
      href: withFamilyId("tree-view.html", context),
      show: config.navTree && hasWorkspaceFamily,
    });

    applyAction('.site-nav a[href^="lineage-certificate.html"]', {
      href: withFamilyId("lineage-certificate.html", context),
      show: config.navCertificate && hasWorkspaceFamily,
    });

    applyAction('.site-nav a[href^="link-keys.html"]', {
      href: withFamilyId("link-keys.html", context),
      show: config.navLinkKeys,
    });

    applyAction('.site-nav a[href^="household-access.html"]', {
      href: withFamilyId("household-access.html", context),
      show: config.showHouseholdAccess,
    });

    applyAction('.site-nav a[href^="portrait-upload.html"]', {
      href: withFamilyId("portrait-upload.html", context),
      show: config.lane === "portrait" && config.showVerification,
    });

    applyAction(
      "[data-dashboard-digital-collectible-action], a[href^=\"digital-collectible.html\"]",
      {
        href: withFamilyId("digital-collectible.html", context),
        show: Boolean(context?.hasPackageAccess),
      },
    );

    applyAction(
      "[data-dashboard-hero-primary-action], [data-dashboard-package-primary-action]",
      {
        text: primaryAction.text,
        href: withFamilyId(primaryAction.href, context),
        show: primaryAction.show,
      },
    );

    applyAction(
      "[data-dashboard-hero-secondary-action], [data-dashboard-package-secondary-action], [data-dashboard-intake-verification-action], [data-dashboard-next-family-action]",
      {
        text: config.secondaryActionText,
        href: withFamilyId(config.secondaryActionHref, context),
        show: config.showVerification,
      },
    );

    applyAction(
      "[data-dashboard-hero-link-action], [data-dashboard-package-link-action]",
      {
        text: "Manage Linking Keys",
        href: withFamilyId("link-keys.html", context),
        show: config.showLinkKeys,
      },
    );

    applyAction(
      "[data-dashboard-household-invite-co-owner], [data-dashboard-household-invite-family], [data-dashboard-household-pending-invites]",
      {
        href: withFamilyId("household-access.html", context),
        show: showHouseholdInviteActions && config.showHouseholdAccess,
      },
    );
    applyAction("[data-dashboard-household-view-members]", {
      href: withFamilyId("household-access.html", context),
      show: config.showHouseholdAccess,
    });

    applyAction(
      "[data-dashboard-hero-tree-action], [data-dashboard-package-tree-action], [data-dashboard-workspace-tree-action], a[href=\"tree-view.html\"][data-paid-action]",
      {
        text: "Open Family Tree",
        href: withFamilyId("tree-view.html", context),
        show: showTreeActions,
      },
    );

    applyAction(
      "[data-dashboard-hero-certificate-action], [data-dashboard-package-certificate-action]",
      {
        text: "View Lineage Certificate",
        href: withFamilyId("lineage-certificate.html", context),
        show: showCertificateActions,
      },
    );

    const workspaceCopy = document.querySelector(
      "[data-dashboard-workspace-copy]",
    );
    text(workspaceCopy, config.workspaceCopy);

    const upgradeAction = document.querySelector("[data-upgrade-action]");
    if (upgradeAction) {
      const memberRole = normalizeMemberRole(
        context?.household_access?.member_role,
      );
      const canManageBilling =
        !memberRole || memberRole === "billing_owner";
      if (!canManageBilling) {
        upgradeAction.style.display = "none";
      } else {
        const re = context.resolvedEntitlements || {};
        const upgradeTargets = Array.isArray(re.upgrade_targets)
          ? re.upgrade_targets
          : [];
        const allowedAddons = Array.isArray(re.allowed_addons)
          ? re.allowed_addons
          : [];
        const resolveDisplayName =
          window.TOLAuthPages &&
          typeof window.TOLAuthPages.resolvePackageDisplayName === "function"
            ? window.TOLAuthPages.resolvePackageDisplayName
            : function (code) {
                return code || "Package";
              };

        if (upgradeTargets.length > 0) {
          const firstName = resolveDisplayName(upgradeTargets[0]);
          upgradeAction.textContent =
            upgradeTargets.length === 1
              ? "Upgrade to " + firstName
              : "Upgrade to " + firstName + " or higher";
          upgradeAction.setAttribute("href", "billing.html");
          upgradeAction.style.display = "";
        } else if (allowedAddons.length > 0) {
          upgradeAction.textContent = "View Available Add-Ons";
          upgradeAction.setAttribute("href", "billing.html");
          upgradeAction.style.display = "";
        } else {
          upgradeAction.style.display = "none";
        }
      }
    }

    const currentPackage = document.querySelector(
      "[data-intake-current-package]",
    );
    text(currentPackage, context.packageName || "Active Package");
  }

  function renderHistoryItem(item, index) {
    return `
      <div class="family-record-card">
        <div class="card-number">${index + 1}</div>
        <h3>${escapeHtml(humanizeStatus(item.status || "unknown"))}</h3>
        <p class="card-copy"><strong>Package:</strong> ${escapeHtml(item.package_name || item.package_slug || "—")}</p>
        <p class="card-copy"><strong>Created:</strong> ${escapeHtml(formatDate(item.created_at))}</p>
        <p class="card-copy"><strong>Submission ID:</strong> ${escapeHtml(item.id || "—")}</p>
        <p class="card-copy"><strong>Family Root ID:</strong> ${escapeHtml(item.family_root_id || "—")}</p>
        <p class="card-copy"><strong>Project ID:</strong> ${escapeHtml(item.project_id || "—")}</p>
      </div>
    `;
  }

  async function getCurrentUser() {
    // Use the user already resolved by auth.js when available so that
    // dashboard-intake.js does not make a redundant /auth/me request.
    if (window.TOLResolvedUser) {
      return window.TOLResolvedUser;
    }
    return await app.apiRequest("/auth/me", { method: "GET" });
  }

  async function getLatestSubmission() {
    try {
      return await app.apiRequest("/intake-submissions/my-latest", {
        method: "GET",
      });
    } catch (error) {
      const message = String(
        error && error.message ? error.message : error,
      ).toLowerCase();

      if (
        message.includes("no intake submissions found") ||
        message.includes("404")
      ) {
        return null;
      }

      throw error;
    }
  }

  async function getSubmissionHistory() {
    try {
      return await app.apiRequest("/intake-submissions/my-list?limit=10", {
        method: "GET",
      });
    } catch (error) {
      return [];
    }
  }

  function updatePrimaryIntakeAction(context, status, actionNode) {
    if (!actionNode) return;

    function setActionText(label) {
      const ctaNode = actionNode.querySelector(".portal-action-cta");
      if (ctaNode) {
        ctaNode.textContent = label;
        actionNode.setAttribute("aria-label", label);
        return;
      }

      actionNode.textContent = label;
    }

    const resolved = context?.resolvedEntitlements || {};
    const lane = normalizeValue(context?.packageLane || resolved.package_lane);
    const canOpenFamilyIntake = Boolean(resolved.can_open_family_intake);
    const canOpenOrgIntake = Boolean(resolved.can_open_org_intake);

    if (lane === "portrait") {
      setActionText("Upload Portrait");
      actionNode.setAttribute("href", "portrait-upload.html");
      return;
    }

    if (lane === "organization") {
      setActionText("Upload Structure Records");
      actionNode.setAttribute("href", "verification-upload.html");
      return;
    }

    if (!canOpenFamilyIntake && !canOpenOrgIntake) {
      actionNode.style.display = "none";
      return;
    }

    const normalized = normalizeStatus(status);

    if (normalized === "rejected") {
      setActionText("Resume Intake");
      actionNode.setAttribute("href", "intake-household.html");
      return;
    }

    if (
      normalized === "build_ready" ||
      normalized === "in_production" ||
      normalized === "qa_review" ||
      normalized === "client_review" ||
      normalized === "delivered" ||
      normalized === "archived"
    ) {
      setActionText("View Intake Record");
      actionNode.setAttribute("href", "intake-review.html");
      return;
    }

    if (isLockedStatus(normalized)) {
      setActionText("View Intake");
      actionNode.setAttribute("href", "intake-review.html");
      return;
    }

    setActionText("Open Intake");
    actionNode.setAttribute("href", "intake-welcome.html");
  }

  async function applyDashboardIntake() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    let me = null;

    try {
      me = await getCurrentUser();
    } catch (error) {
      return;
    }

    if (isInternalRole(me)) {
      const statusNode = document.querySelector("[data-dashboard-status]");
      if (statusNode) {
        statusNode.textContent =
          "You are signed in to the Tomb of Light internal operations portal.";
      }
      return;
    }

    const rawContext =
      window.TOLDashboardContext ||
      (authPages.getDashboardContext
        ? await authPages.getDashboardContext(
            me,
            authPages.fetchOrders ? await authPages.fetchOrders() : [],
          )
        : null);
    const context = ensureLegacyPlusMorelandContext(rawContext);

    if (!context || !context.hasPackageAccess) {
      setLegacyAnchorUnavailable(
        "Legacy Anchor proof becomes available once package access is resolved for this account.",
      );
      return;
    }

    const memberRole = await resolveDashboardMemberRole(context);
    const contextWithMembership = Object.assign({}, context, {
      household_access: {
        member_role: memberRole || null,
        can_manage: canManageHouseholdAccess(memberRole),
      },
    });

    const config = getEntitlementConfig(contextWithMembership);
    updateLaneUi(contextWithMembership, config, null);
    applyPortalTheme(contextWithMembership, config);
    applyDashboardHierarchy(contextWithMembership, []);
    updatePackageUnlocksPanel(contextWithMembership);
    updateDashboardToolCardStates(contextWithMembership);
    updateCommandCenterPanel(contextWithMembership, null, {
      text: "Upload Photos & Family Records",
    });
    updateProjectProgressTracker(contextWithMembership, null, false);
    updateWorkspaceHealthPanel(contextWithMembership, null);
    updateReceivedMaterialsPanel(null);
    updateIntakeAttentionPanel(null);

    const intakeCardStatus = document.querySelector(
      "[data-intake-card-status]",
    );
    const currentPackage = document.querySelector(
      "[data-intake-current-package]",
    );
    const statusBadge = document.querySelector("[data-intake-status-badge]");
    const submissionId = document.querySelector("[data-intake-submission-id]");
    const submittedAt = document.querySelector("[data-intake-submitted-at]");
    const nextStep = document.querySelector("[data-intake-next-step]");
    const lockNote = document.querySelector("[data-intake-lock-note]");
    const openAction = document.querySelector("[data-intake-open-action]");
    const historyStatus = document.querySelector(
      "[data-intake-history-status]",
    );
    const historyList = document.querySelector("[data-intake-history-list]");
    const dashboardStatus = document.querySelector("[data-dashboard-status]");
    const workspaceCopy = document.querySelector(
      "[data-dashboard-workspace-copy]",
    );
    const nextFocusNode = document.querySelector("[data-dashboard-next-focus]");

    try {
      const latest = await getLatestSubmission();
      const history = await getSubmissionHistory();
      const contextWithLatest = Object.assign({}, contextWithMembership, {
        latestSubmission: latest || null,
      });
      await updateLegacyAnchorPanel(contextWithLatest);
      const primaryAction = getPrimaryWorkspaceAction(
        contextWithLatest,
        config,
        latest,
      );

      updateLaneUi(contextWithLatest, config, latest);
      applyDashboardHierarchy(contextWithLatest, history);
      updatePackageUnlocksPanel(contextWithLatest);
      updateDashboardToolCardStates(contextWithLatest);
      updateCommandCenterPanel(contextWithLatest, latest, primaryAction);
      updateProjectProgressTracker(
        contextWithLatest,
        latest,
        hasIntakeConfirmationIssues(latest),
      );
      updateWorkspaceHealthPanel(contextWithLatest, latest);
      updateReceivedMaterialsPanel(latest);
      updateIntakeAttentionPanel(latest);

      text(currentPackage, contextWithMembership.packageName || "Active Package");

      if (!latest) {
        text(intakeCardStatus, config.presenceTitle);
        text(statusBadge, "Not submitted");
        text(submissionId, "—");
        text(submittedAt, "—");
        text(
          nextStep,
          config.lane === "portrait"
            ? "Upload the portrait first, then add verification records only if needed."
            : config.lane === "organization"
              ? "Upload organization and supporting records to begin."
              : "Open your intake flow and submit the review step.",
        );
        text(
          nextFocusNode,
          primaryAction.text || "Open your workspace.",
        );
        text(
          lockNote,
          "Editing is open because no final submission exists yet.",
        );

        if (openAction) {
          updatePrimaryIntakeAction(contextWithMembership, "", openAction);
        }
      } else {
        const status = normalizeStatus(
          latest.status || latest.submission_status,
        );
        const laneMessages = getLaneAwareIntakeMessages(contextWithMembership, status);

        text(intakeCardStatus, laneMessages.cardCopy);
        text(statusBadge, humanizeStatus(status));
        text(submissionId, latest.id || latest._id || "—");
        text(submittedAt, formatDate(latest.submitted_at || latest.created_at));
        text(nextStep, laneMessages.nextStep);
        text(nextFocusNode, laneMessages.nextStep);
        text(lockNote, laneMessages.lockNote);
        text(workspaceCopy, laneMessages.workspaceCopy);

        if (openAction) {
          updatePrimaryIntakeAction(contextWithMembership, status, openAction);
        }
      }

      if (!Array.isArray(history) || history.length === 0) {
        text(historyStatus, "No intake submissions found yet.");
        if (historyList) historyList.innerHTML = "";
      } else {
        text(historyStatus, "Your recent intake submissions are listed below.");
        if (historyList) {
          historyList.innerHTML = history.map(renderHistoryItem).join("");
        }
      }

      if (dashboardStatus) {
        dashboardStatus.textContent = `Your package is active: ${contextWithMembership.packageName || "Active Package"}.`;
      }
    } catch (error) {
      applyDashboardHierarchy(contextWithMembership, []);
      updatePackageUnlocksPanel(contextWithMembership);
      updateDashboardToolCardStates(contextWithMembership);
      updateCommandCenterPanel(contextWithMembership, null, null);
      updateProjectProgressTracker(contextWithMembership, null, false);
      updateWorkspaceHealthPanel(contextWithMembership, null);
      updateReceivedMaterialsPanel(null);
      updateIntakeAttentionPanel(null);
      setLegacyAnchorUnavailable(
        "Legacy Anchor status is temporarily unavailable.",
        "Please refresh shortly. Tomb of Light could not finish loading the customer workspace state.",
      );
      text(intakeCardStatus, "Intake status is temporarily unavailable.");
      text(statusBadge, "Unavailable");
      text(nextStep, "Please try again shortly.");
      text(nextFocusNode, "Retry loading your workspace shortly.");
      text(lockNote, "Could not determine current submission lock state.");
      text(historyStatus, "Intake history is temporarily unavailable.");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindLegacyAnchorInteractions();
    applyDashboardIntake();
  });

  window.addEventListener("tol:dashboard-context-ready", function () {
    applyDashboardIntake();
  });
})();
