(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") return;

  const SUPPORTED_SECTIONS = new Set([
    "project",
    "family",
    "deliverables",
    "account",
    "support",
  ]);

  let booted = false;

  function normalize(value) {
    return String(value || "").trim().toLowerCase();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function getSection() {
    const requested = normalize(new URLSearchParams(window.location.search).get("section"));
    return SUPPORTED_SECTIONS.has(requested) ? requested : "project";
  }

  function isInternalUser(user) {
    if (typeof app.isInternalRole === "function") return app.isInternalRole(user || {});
    return ["admin", "super_admin", "operations_admin", "finance_admin", "marketing_admin"].includes(
      normalize(user && user.role),
    );
  }

  function getEntitlements(context) {
    return context && context.entitlements && typeof context.entitlements === "object"
      ? context.entitlements
      : context && context.resolved_entitlements && typeof context.resolved_entitlements === "object"
        ? context.resolved_entitlements
        : context && context.resolvedEntitlements && typeof context.resolvedEntitlements === "object"
          ? context.resolvedEntitlements
          : {};
  }

  function getWorkspace(context) {
    return context && context.workspace && typeof context.workspace === "object"
      ? context.workspace
      : {};
  }

  function getPackage(context) {
    return context && context.package && typeof context.package === "object"
      ? context.package
      : {};
  }

  function getProjectId(context) {
    const workspace = getWorkspace(context);
    return String(
      workspace.project_id ||
        workspace.projectId ||
        context?.project_id ||
        context?.projectId ||
        "",
    ).trim();
  }

  function getFamilyId(context) {
    const workspace = getWorkspace(context);
    return String(
      workspace.family_id ||
        workspace.familyId ||
        context?.family_id ||
        context?.familyId ||
        "",
    ).trim();
  }

  function getProjectName(context) {
    const workspace = getWorkspace(context);
    return String(
      workspace.project_name ||
        workspace.projectName ||
        workspace.family_name ||
        workspace.name ||
        "Your Tomb of Light Project",
    ).trim();
  }

  function getPackageName(context) {
    const packageInfo = getPackage(context);
    return String(packageInfo.display_name || packageInfo.name || packageInfo.code || "Active Package").trim();
  }

  function withContext(href, context) {
    if (!href) return href;
    const familyId = getFamilyId(context);
    const projectId = getProjectId(context);
    try {
      const url = new URL(href, window.location.href);
      if (familyId) url.searchParams.set("family_id", familyId);
      if (projectId) url.searchParams.set("project_id", projectId);
      const file = url.pathname.startsWith("/viewer/")
        ? "/viewer/"
        : url.pathname.split("/").pop() || href;
      return `${file}${url.search}${url.hash}`;
    } catch (_error) {
      return href;
    }
  }

  function domainLinks(context, current) {
    const entitlements = getEntitlements(context);
    const hasFamily = Boolean(entitlements.can_build_family_tree || entitlements.can_build_household);
    const hasVault = Boolean(
      entitlements.can_use_personal_vault ||
        entitlements.can_use_household_vault ||
        entitlements.can_use_linked_household_vault ||
        entitlements.can_use_organization_records_vault,
    );
    const items = [
      ["home", "Home", "dashboard.html", true],
      ["project", "My Project", "portal-section.html?section=project", true],
      ["family", "Family", "portal-section.html?section=family", hasFamily],
      ["uploads", "Uploads", "upload-hub.html", true],
      ["vault", "Vault", "vault-upload.html", hasVault],
      ["deliverables", "Deliverables", "portal-section.html?section=deliverables", true],
      ["account", "Account", "portal-section.html?section=account", true],
      ["support", "Support", "portal-section.html?section=support", true],
    ];
    return items
      .filter(function (item) { return item[3]; })
      .map(function (item) {
        return {
          key: item[0],
          label: item[1],
          href: withContext(item[2], context),
          current: item[0] === current,
        };
      });
  }

  function renderNavigation(context, current) {
    const links = domainLinks(context, current);
    const projectName = getProjectName(context);
    const packageName = getPackageName(context);
    const rail = document.querySelector("[data-portal-section-rail]");
    const mobile = document.querySelector("#site-nav");

    if (rail) {
      rail.innerHTML = `
        <div class="portal-section-rail-brand">
          <img src="site-logo-header.png" alt="" aria-hidden="true" />
          <span>Tomb of Light™</span>
        </div>
        <div class="portal-section-rail-project">
          <small>Current workspace</small>
          <strong>${escapeHtml(projectName)}</strong>
          <span>${escapeHtml(packageName)}</span>
        </div>
        <nav class="portal-section-rail-nav" aria-label="Workspace sections">
          ${links.map(function (item) {
            return `<a class="portal-section-rail-link" href="${escapeHtml(item.href)}"${item.current ? ' aria-current="page"' : ""}>${escapeHtml(item.label)}</a>`;
          }).join("")}
        </nav>
        <div class="portal-section-rail-foot">Private customer workspace<br />Protected by Tomb of Light</div>
      `;
    }

    if (mobile) {
      mobile.innerHTML = links.map(function (item) {
        return `<a href="${escapeHtml(item.href)}"${item.current ? ' aria-current="page"' : ""}>${escapeHtml(item.label)}</a>`;
      }).join("");
    }
  }

  function humanize(value) {
    const normalized = normalize(value);
    if (!normalized) return "Not started";
    return normalized
      .split("_")
      .map(function (part) { return part.charAt(0).toUpperCase() + part.slice(1); })
      .join(" ");
  }

  function stageLabel(status) {
    const value = normalize(status);
    if (value === "approved") return "Intake approved";
    if (value === "build_ready") return "Production setup";
    if (value === "in_production") return "Production in progress";
    if (value === "qa_review") return "Verification and quality review";
    if (value === "client_review") return "Customer review";
    if (value === "delivered") return "Delivered";
    if (value === "archived") return "Continuity and maintenance";
    if (value === "submitted") return "Intake submitted";
    if (value === "in_review") return "Intake under review";
    if (value === "rejected") return "Needs attention";
    return value ? humanize(value) : "Not started";
  }

  function isProductionReadyStatus(status) {
    return ["client_review", "delivered", "archived"].includes(normalize(status));
  }

  function card(title, copy, state, href, label, enabled = true) {
    const stateClass = state === "Not included" ? " is-locked" : state.includes("Pending") || state.includes("Awaiting") ? " is-pending" : "";
    const disabled = !enabled;
    return `
      <article class="portal-section-card${disabled ? " is-unavailable" : ""}">
        <div class="portal-section-card-top">
          <h2>${escapeHtml(title)}</h2>
          <span class="portal-section-state${stateClass}">${escapeHtml(state)}</span>
        </div>
        <p>${escapeHtml(copy)}</p>
        <a class="portal-section-action" href="${escapeHtml(enabled ? href : "#")}"${disabled ? ' aria-disabled="true" tabindex="-1"' : ""}>${escapeHtml(label)}</a>
      </article>
    `;
  }

  function renderStatus(context, intake) {
    const container = document.querySelector("[data-portal-section-status]");
    if (!container) return;
    const packageInfo = getPackage(context);
    const acquisition = context && context.acquisition && typeof context.acquisition === "object" ? context.acquisition : {};
    const packageState = normalize(packageInfo.status) === "granted" ? "Granted access" : "Active";
    const intakeState = intake ? stageLabel(intake.status || intake.submission_status) : "Not started";
    const accessState = acquisition.payment_required === false ? "Authorized grant" : "Private customer";
    container.innerHTML = `
      <div class="portal-section-status-card"><small>Package</small><strong>${escapeHtml(packageState)}</strong></div>
      <div class="portal-section-status-card"><small>Project stage</small><strong>${escapeHtml(intakeState)}</strong></div>
      <div class="portal-section-status-card"><small>Access</small><strong>${escapeHtml(accessState)}</strong></div>
    `;
  }

  function renderSection(context, intake, mintStatus) {
    const section = getSection();
    const entitlements = getEntitlements(context);
    const projectId = getProjectId(context);
    const familyId = getFamilyId(context);
    const status = normalize(intake && (intake.status || intake.submission_status));
    const readyForDelivery = isProductionReadyStatus(status);

    const definitions = {
      project: {
        eyebrow: "My Project",
        title: "Project & Intake",
        description: "Review your project stage, intake record, and the production actions that move your legacy build forward.",
        cards: function () {
          return [
            card(
              "Intake record",
              status === "approved"
                ? "Your intake is approved. Review the locked record and production status without resubmitting it."
                : "Open the current intake record and see what still requires customer action.",
              status === "approved" ? "Approved" : stageLabel(status),
              withContext("intake-review.html", context),
              "Open Intake",
            ),
            card(
              "Production materials",
              "Add photographs, family records, and supporting source material through the protected upload workflow.",
              status === "approved" ? "Current step" : "Open",
              withContext("upload-hub.html", context),
              "Open Uploads",
            ),
          ].join("");
        },
      },
      family: {
        eyebrow: "Family",
        title: "Family Workspace",
        description: "Manage the lineage structure and trusted household access without mixing those controls into Home.",
        cards: function () {
          const items = [];
          if (entitlements.can_build_family_tree) {
            items.push(card("Family Tree", "Open the working lineage graph and review placed family relationships.", "Included", withContext("tree-view.html", context), "Open Tree"));
          }
          if (entitlements.can_build_household || entitlements.family_household_scope) {
            items.push(card("Members & Access", "Manage trusted household roles, invitations, and collaboration permissions.", "Included", withContext("household-access.html", context), "Manage Access"));
          }
          if (familyId) {
            items.push(card("Family Reunion Readiness", "Review which visible family members are placed and ready for the customer experience.", "Private view", withContext("family-reunion.html", context), "View Readiness"));
          }
          if (entitlements.can_link_households) {
            items.push(card("Household Link Keys", "Create governed branch-link keys for eligible linked-household workflows.", "Included", withContext("link-keys.html", context), "Manage Link Keys"));
          }
          return items.join("");
        },
      },
      deliverables: {
        eyebrow: "Deliverables",
        title: "Legacy Deliverables",
        description: "See what your package includes separately from what is ready to open today.",
        cards: function () {
          const items = [];
          const viewerIncluded = Boolean(entitlements.can_use_viewer || entitlements.can_use_secure_share_viewer);
          const viewerStatus = normalize(getWorkspace(context).viewer_status || getWorkspace(context).manifest_status);
          const viewerReady = viewerIncluded && (readyForDelivery || ["ready", "approved", "active", "live"].includes(viewerStatus));
          items.push(card(
            "Lineage Cinema / Viewer",
            viewerIncluded
              ? viewerReady
                ? "Your package includes the viewer and the project is ready to open it."
                : "Included with your package. The viewer will open when production readiness is complete."
              : "This deliverable is not included with the active package.",
            viewerIncluded ? (viewerReady ? "Ready" : "Pending production") : "Not included",
            projectId ? `/viewer/?project_id=${encodeURIComponent(projectId)}` : "/viewer/",
            viewerReady ? "Open Viewer" : "Awaiting Production",
            viewerReady,
          ));

          const certificateIncluded = Boolean(entitlements.can_use_lineage_certificate);
          const certificateReady = certificateIncluded && readyForDelivery;
          items.push(card(
            "Lineage Certificate",
            certificateIncluded
              ? certificateReady
                ? "Your verified lineage certificate is ready to review."
                : "Included with your package and awaiting the required production/verification state."
              : "This deliverable is not included with the active package.",
            certificateIncluded ? (certificateReady ? "Ready" : "Pending production") : "Not included",
            withContext("lineage-certificate.html", context),
            certificateReady ? "View Certificate" : "Awaiting Production",
            certificateReady,
          ));

          const latestMint = mintStatus && mintStatus.latest ? mintStatus.latest : null;
          const mintState = normalize(latestMint && latestMint.status);
          const minted = ["minted", "completed", "delivered"].includes(mintState) || Boolean(latestMint && latestMint.tx_hash);
          items.push(card(
            "Legacy Anchor",
            minted
              ? "Your public-safe Legacy Anchor proof is minted and can be reviewed separately from private Vault records."
              : "NFT services are governed separately from the base package and only proceed after the required customer and Tomb of Light approvals.",
            minted ? "Minted" : "Governed service",
            withContext(minted ? "digital-collectible.html" : "dashboard.html#legacy-anchor", context),
            minted ? "View Legacy Anchor" : "View Anchor Status",
          ));
          return items.join("");
        },
      },
      account: {
        eyebrow: "Account",
        title: "Account & Billing",
        description: "Keep identity, security, personal details, billing, and maintenance controls in one account layer.",
        cards: function () {
          return [
            card("Account Security", "Manage password, authenticator protection, recovery, and recent security activity.", "Open", "account-security.html", "Open Security"),
            card("Personal Details", "Update the customer contact profile attached to this Tomb of Light account.", "Open", "billing.html#personal-details", "Manage Details"),
            card("Billing & Cards", "Review saved cards, subscription or maintenance billing, and Stripe customer controls.", "Open", "billing.html", "Open Billing"),
          ].join("");
        },
      },
      support: {
        eyebrow: "Support",
        title: "Support & Privacy",
        description: "Get help without mixing support contacts into the project Home screen.",
        cards: function () {
          return [
            card("Help Center", "Review customer guidance and continuity questions inside the protected portal.", "Open", "portal-help.html", "Open Help Center"),
            card("Customer Support", "Contact the Tomb of Light support team for project or account assistance.", "Available", "mailto:support@tomboflight.com", "Email Support"),
            card("Billing Support", "Contact billing support for payment or maintenance questions.", "Available", "mailto:billing@tomboflight.com", "Email Billing"),
            card("Privacy", "Contact the privacy team for data and privacy requests.", "Available", "mailto:privacy@tomboflight.com", "Email Privacy"),
          ].join("");
        },
      },
    };

    const definition = definitions[section] || definitions.project;
    document.title = `${definition.title} | Tomb of Light`;
    const eyebrow = document.querySelector("[data-portal-section-eyebrow]");
    const title = document.querySelector("[data-portal-section-title]");
    const description = document.querySelector("[data-portal-section-description]");
    const packageNode = document.querySelector("[data-portal-section-package]");
    const grid = document.querySelector("[data-portal-section-grid]");
    if (eyebrow) eyebrow.textContent = definition.eyebrow;
    if (title) title.textContent = definition.title;
    if (description) description.textContent = definition.description;
    if (packageNode) packageNode.textContent = getPackageName(context);
    if (grid) grid.innerHTML = definition.cards();
    renderStatus(context, intake);
    renderNavigation(context, section);
  }

  async function loadLatestIntake() {
    try {
      return await app.apiRequest("/intake-submissions/my-latest", { method: "GET" });
    } catch (error) {
      if (Number(error && error.status) === 404) return null;
      return null;
    }
  }

  async function loadMintStatus(context) {
    const projectId = getProjectId(context);
    if (!projectId) return null;
    try {
      return await app.apiRequest(`/projects/${encodeURIComponent(projectId)}/mint-status`, { method: "GET" });
    } catch (_error) {
      return null;
    }
  }

  async function boot(user) {
    if (booted) return;
    if (!user || isInternalUser(user)) {
      if (user && isInternalUser(user)) window.location.replace("dashboard.html");
      return;
    }
    booted = true;

    const message = document.querySelector("[data-portal-section-message]");
    try {
      const context = await app.apiRequest("/users/me/workspace-context", { method: "GET" });
      const [intake, mintStatus] = await Promise.all([
        loadLatestIntake(),
        getSection() === "deliverables" ? loadMintStatus(context) : Promise.resolve(null),
      ]);
      renderSection(context || {}, intake, mintStatus);
      if (message) message.textContent = "";
    } catch (error) {
      if (message) {
        message.textContent = "Unable to load this workspace section right now. Return to Home or contact support if the problem continues.";
      }
    }
  }

  window.addEventListener("tol:user-resolved", function (event) {
    boot(event && event.detail ? event.detail.user : window.TOLResolvedUser);
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (window.TOLResolvedUser) boot(window.TOLResolvedUser);
    window.setTimeout(function () {
      if (!booted && window.TOLResolvedUser) boot(window.TOLResolvedUser);
    }, 250);
  });
})();
