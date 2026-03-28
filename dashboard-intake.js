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

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
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

  function isLockedStatus(status) {
    return LOCKED_STATUSES.has(normalizeStatus(status));
  }

  function isInternalRole(role) {
    return [
      "admin",
      "super_admin",
      "platform_admin",
      "operations_admin",
      "finance_admin",
      "marketing_admin",
      "root_admin",
    ].includes(normalizeValue(role));
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch (error) {
      return String(value);
    }
  }

  function text(node, value) {
    if (!node) return;
    node.textContent = value;
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

  function getEntitlementConfig(context) {
    const resolved = context?.resolvedEntitlements || {};
    const lane = normalizeValue(context?.packageLane || resolved?.package_lane);
    const packageName = context?.packageName || "Active Package";

    const canBuildFamilyTree = Boolean(resolved.can_build_family_tree);
    const canUseCertificate = Boolean(resolved.can_use_lineage_certificate);
    const canUploadRecords = Boolean(
      resolved.can_upload_verification_docs || resolved.can_upload_portraits,
    );
    const canUseLinkKeys = Boolean(resolved.can_use_link_keys);
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
        primaryActionText: "Upload Portrait & Records",
        primaryActionHref: "verification-upload.html",
        secondaryActionText: "Verification Uploads",
        secondaryActionHref: "verification-upload.html",
        showTree: canBuildFamilyTree,
        showCertificate: canBuildFamilyTree,
        showVerification: true,
        showLinkKeys: canUseLinkKeys,
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
        upgradeHref: "index.html#pricing",
      };
    }

    if (lane === "organization") {
      return {
        lane: "organization",
        presenceBadge: "Organization Lane Active",
        presenceTitle:
          "Your command structure workspace is live and connected.",
        presenceCopy: canUseLinkKeys
          ? "Tomb of Light is now reading from your organization package, role structure scope, supporting record workflow, and link capabilities."
          : "Tomb of Light is now reading from your organization package, role structure scope, and supporting record workflow.",
        stages: [
          { title: "Organization Root", subtitle: "Connected" },
          {
            title: "Structure Build",
            subtitle: canOpenOrgIntake ? "Configured" : "Prepared",
          },
          {
            title: "Link Capabilities",
            subtitle: canUseLinkKeys ? "Enabled" : "Unavailable",
          },
        ],
        workspaceCopy: canUseLinkKeys
          ? "Your organization workspace connects package access, command structure planning, uploads, and link capabilities in one place."
          : "Your organization workspace connects package access, command structure planning, uploads, and guided record handling in one place.",
        primaryActionText: "Upload Structure Records",
        primaryActionHref: "verification-upload.html",
        secondaryActionText: "Upload Structure Records",
        secondaryActionHref: "verification-upload.html",
        showTree: canBuildFamilyTree,
        showCertificate: canBuildFamilyTree,
        showVerification: true,
        showLinkKeys: canUseLinkKeys,
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
            copy: canUseLinkKeys
              ? "Upload supporting materials, use link capabilities, and expand the structure when needed."
              : "Upload supporting records and materials tied to the organization build.",
          },
        ],
        platformStatusTitle: "Entitled Tools",
        platformStatusCopy: canUseLinkKeys
          ? "This organization lane includes structure workflows, verification uploads, and link capabilities."
          : "This organization lane includes structure and verification workflows. Expansion options are available if you need more scope.",
        upgradeText: "View Expansion Options",
        upgradeHref: "index.html#pricing",
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
        primaryActionText: "Continue Network Build",
        primaryActionHref: "tree-view.html",
        secondaryActionText: "Upload Verification Docs",
        secondaryActionHref: "verification-upload.html",
        showTree: canBuildFamilyTree,
        showCertificate: canUseCertificate,
        showVerification: true,
        showLinkKeys: canUseLinkKeys,
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
        upgradeHref: "index.html#pricing",
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
      primaryActionText: "Continue Family Build",
      primaryActionHref: "tree-view.html",
      secondaryActionText: "Upload Verification Docs",
      secondaryActionHref: "verification-upload.html",
      showTree: canBuildFamilyTree,
      showCertificate: canUseCertificate,
      showVerification: true,
      showLinkKeys: canUseLinkKeys,
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
      upgradeHref: "index.html#pricing",
    };
  }

  function getLaneAwareIntakeMessages(context, status) {
    const resolved = context?.resolvedEntitlements || {};
    const normalizedLane = normalizeValue(
      context?.packageLane || resolved.package_lane,
    );
    const normalizedStatus = normalizeStatus(status);
    const canUseLinkKeys = Boolean(resolved.can_use_link_keys);

    if (normalizedLane === "portrait") {
      if (normalizedStatus === "build_ready") {
        return {
          cardCopy: canUseLinkKeys
            ? "Your portrait package is approved and ready for portrait, verification, and link-enabled work."
            : "Your portrait package is approved and ready for portrait and verification work.",
          nextStep: "Upload portrait and supporting verification records.",
          lockNote:
            "Editing is locked because this portrait package has already been approved and provisioned.",
          workspaceCopy: canUseLinkKeys
            ? "Your portrait intake has been approved and provisioned. This workspace now moves into the portrait record stage with link capabilities available."
            : "Your portrait intake has been approved and provisioned. This workspace now moves from onboarding into the portrait record stage.",
        };
      }

      return {
        cardCopy: "Your portrait intake information is shown below.",
        nextStep: "Upload portrait and supporting verification records.",
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

  function updateLaneUi(context, config) {
    updatePresencePanel(config);
    updateBuildPathPanel(config);
    updatePlatformStatusPanel(config);

    applyNavVisibility("tree-view.html", config.navTree);
    applyNavVisibility("lineage-certificate.html", config.navCertificate);
    applyNavVisibility("intake-review.html", config.navIntake);
    applyNavVisibility("verification-upload.html", config.showVerification);
    applyNavVisibility("link-keys.html", config.navLinkKeys);

    applyAction(
      "[data-dashboard-workspace-primary-action], [data-dashboard-package-primary-action]",
      {
        text: config.primaryActionText,
        href: config.primaryActionHref,
        show: true,
      },
    );

    applyAction(
      '[href="verification-upload.html"][data-paid-action], [data-dashboard-next-family-action]',
      {
        text: config.secondaryActionText,
        href: config.secondaryActionHref,
        show: config.showVerification,
      },
    );

    applyAction("[data-dashboard-link-keys-action]", {
      text: "Open Link Keys",
      href: "link-keys.html",
      show: config.showLinkKeys,
    });

    applyAction(
      '[data-dashboard-workspace-tree-action], a[href="tree-view.html"][data-paid-action]',
      {
        text: "Open Family Tree",
        href: "tree-view.html",
        show: config.showTree,
      },
    );

    applyAction(
      '[data-dashboard-workspace-certificate-action], a[href="lineage-certificate.html"][data-paid-action]',
      {
        text: "View Lineage Certificate",
        href: "lineage-certificate.html",
        show: config.showCertificate,
      },
    );

    const workspaceCopy = document.querySelector(
      "[data-dashboard-workspace-copy]",
    );
    text(workspaceCopy, config.workspaceCopy);

    const upgradeAction = document.querySelector("[data-upgrade-action]");
    if (upgradeAction) {
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
        upgradeAction.setAttribute("href", "index.html#pricing");
        upgradeAction.style.display = "";
      } else if (allowedAddons.length > 0) {
        upgradeAction.textContent = "View Available Add-Ons";
        upgradeAction.setAttribute("href", "index.html#pricing");
        upgradeAction.style.display = "";
      } else {
        upgradeAction.style.display = "none";
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
        <h3>${humanizeStatus(item.status || "unknown")}</h3>
        <p class="card-copy"><strong>Package:</strong> ${item.package_name || item.package_slug || "—"}</p>
        <p class="card-copy"><strong>Created:</strong> ${formatDate(item.created_at)}</p>
        <p class="card-copy"><strong>Submission ID:</strong> ${item.id || "—"}</p>
        <p class="card-copy"><strong>Family Root ID:</strong> ${item.family_root_id || "—"}</p>
        <p class="card-copy"><strong>Project ID:</strong> ${item.project_id || "—"}</p>
      </div>
    `;
  }

  async function getCurrentUser() {
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

    const resolved = context?.resolvedEntitlements || {};
    const lane = normalizeValue(context?.packageLane || resolved.package_lane);
    const canOpenFamilyIntake = Boolean(resolved.can_open_family_intake);
    const canOpenOrgIntake = Boolean(resolved.can_open_org_intake);

    if (lane === "portrait") {
      actionNode.textContent = "Upload Portrait & Records";
      actionNode.setAttribute("href", "verification-upload.html");
      return;
    }

    if (lane === "organization") {
      actionNode.textContent = "Upload Structure Records";
      actionNode.setAttribute("href", "verification-upload.html");
      return;
    }

    if (!canOpenFamilyIntake && !canOpenOrgIntake) {
      actionNode.style.display = "none";
      return;
    }

    const normalized = normalizeStatus(status);

    if (normalized === "rejected") {
      actionNode.textContent = "Resume Intake";
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
      actionNode.textContent = "View Intake Record";
      actionNode.setAttribute("href", "intake-review.html");
      return;
    }

    if (isLockedStatus(normalized)) {
      actionNode.textContent = "View Intake";
      actionNode.setAttribute("href", "intake-review.html");
      return;
    }

    actionNode.textContent = "Open Intake";
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

    if (isInternalRole(me && me.role)) {
      const statusNode = document.querySelector("[data-dashboard-status]");
      if (statusNode) {
        statusNode.textContent =
          "You are signed in to the Tomb of Light internal operations portal.";
      }
      return;
    }

    const context =
      window.TOLDashboardContext ||
      (authPages.getDashboardContext
        ? await authPages.getDashboardContext(
            me,
            authPages.fetchOrders ? await authPages.fetchOrders() : [],
          )
        : null);

    if (!context || !context.hasPackageAccess) {
      return;
    }

    const config = getEntitlementConfig(context);
    updateLaneUi(context, config);

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

    try {
      const latest = await getLatestSubmission();
      const history = await getSubmissionHistory();

      text(currentPackage, context.packageName || "Active Package");

      if (!latest) {
        text(intakeCardStatus, config.presenceTitle);
        text(statusBadge, "Not submitted");
        text(submissionId, "—");
        text(submittedAt, "—");
        text(
          nextStep,
          config.lane === "portrait"
            ? "Upload portrait and supporting records to begin."
            : config.lane === "organization"
              ? "Upload organization and supporting records to begin."
              : "Open your intake flow and submit the review step.",
        );
        text(
          lockNote,
          "Editing is open because no final submission exists yet.",
        );

        if (openAction) {
          updatePrimaryIntakeAction(context, "", openAction);
        }
      } else {
        const status = normalizeStatus(
          latest.status || latest.submission_status,
        );
        const laneMessages = getLaneAwareIntakeMessages(context, status);

        text(intakeCardStatus, laneMessages.cardCopy);
        text(statusBadge, humanizeStatus(status));
        text(submissionId, latest.id || latest._id || "—");
        text(submittedAt, formatDate(latest.submitted_at || latest.created_at));
        text(nextStep, laneMessages.nextStep);
        text(lockNote, laneMessages.lockNote);
        text(workspaceCopy, laneMessages.workspaceCopy);

        if (openAction) {
          updatePrimaryIntakeAction(context, status, openAction);
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
        dashboardStatus.textContent = `Your package is active: ${context.packageName || "Active Package"}.`;
      }
    } catch (error) {
      text(intakeCardStatus, "Intake status is temporarily unavailable.");
      text(statusBadge, "Unavailable");
      text(nextStep, "Please try again shortly.");
      text(lockNote, "Could not determine current submission lock state.");
      text(historyStatus, "Intake history is temporarily unavailable.");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyDashboardIntake();
  });

  window.addEventListener("tol:dashboard-context-ready", function () {
    applyDashboardIntake();
  });
})();
