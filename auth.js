(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const POST_LOGIN_REDIRECT = "dashboard.html";
  const SIGNUP_POLICY_VERSION = "2026-03-26";
  const DASHBOARD_CONTEXT_STORAGE_KEY = "tol_dashboard_context_v1";

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

  const NARRATION_ENABLED_PACKAGES = new Set([
    "heirloom_legacy_tree",
    "legacy_plus",
    "family_estate_concierge",
  ]);

  const HOUSEHOLD_LINK_ENABLED_PACKAGES = new Set([
    "legacy_plus",
    "family_estate_concierge",
  ]);

  if (!app) {
    console.error("auth.js requires app.js to be loaded first.");
    return;
  }

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function isInternalRole(user) {
    const role = normalizeValue(user && user.role);
    const accessTier = normalizeValue(user && user.access_tier);
    const departmentRole = normalizeValue(user && user.department_role);

    return [role, accessTier, departmentRole].some(function (value) {
      return INTERNAL_ROLE_KEYS.has(value);
    });
  }

  function getAccessTokenFromResponse(loginData) {
    return (
      loginData?.access_token ||
      loginData?.token ||
      loginData?.accessToken ||
      null
    );
  }

  function getErrorMessage(error) {
    if (!error) return "Unknown error";
    if (typeof error === "string") return error;
    if (error.message) return String(error.message);
    return String(error);
  }

  function isAuthFailure(error) {
    const message = getErrorMessage(error).toLowerCase();

    return (
      message.includes("invalid or expired token") ||
      message.includes("invalid token") ||
      message.includes("invalid token payload") ||
      message.includes("user not found") ||
      message.includes("inactive") ||
      message.includes("unauthorized") ||
      message.includes("forbidden") ||
      message.includes("401") ||
      message.includes("403") ||
      message.includes("not authenticated")
    );
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  async function withRetry(fn, attempts = 2, delayMs = 300) {
    let lastError;

    for (let i = 0; i < attempts; i += 1) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        if (i < attempts - 1) {
          await sleep(delayMs);
        }
      }
    }

    throw lastError;
  }

  function toArray(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.items)) return payload.items;
    if (Array.isArray(payload?.orders)) return payload.orders;
    if (Array.isArray(payload?.data)) return payload.data;
    if (Array.isArray(payload?.submissions)) return payload.submissions;
    return [];
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

  function stripMaintenanceSuffix(packageCode) {
    return normalizePackageCode(packageCode)
      .replace(/_maintenance_monthly$/, "")
      .replace(/_maintenance_yearly$/, "");
  }

  function resolvePackageLane(packageCode) {
    const normalized = stripMaintenanceSuffix(packageCode);

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

  function resolvePackageDisplayName(packageCode) {
    const normalized = stripMaintenanceSuffix(packageCode);

    const mapping = {
      legacy_snapshot: "Legacy Snapshot",
      legacy_portrait_intro: "Legacy Portrait Intro",
      digital_legacy_portrait: "Digital Legacy Portrait",
      household_foundation: "Household Foundation",
      heirloom_legacy_tree: "Heirloom Legacy Tree",
      legacy_plus: "Legacy Plus",
      family_estate_concierge: "Family Estate Concierge",
      command_structure_network: "Command Structure Network",
    };

    return mapping[normalized] || normalized || "Package";
  }

  function packageSupportsLinkKeys(packageCode) {
    return LINK_KEY_ENABLED_PACKAGES.has(stripMaintenanceSuffix(packageCode));
  }

  function buildFallbackEntitlements(packageCode, packageLane) {
    const normalizedCode = stripMaintenanceSuffix(packageCode);
    const lane =
      normalizeValue(packageLane) || resolvePackageLane(normalizedCode);

    return {
      package_code: normalizedCode,
      package_lane: lane,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_build_household: lane === "household" || lane === "network",
      can_build_family_tree: lane === "household" || lane === "network",
      can_build_org_chart: lane === "organization",
      can_link_households: HOUSEHOLD_LINK_ENABLED_PACKAGES.has(normalizedCode),
      can_link_org_units: lane === "organization",
      can_use_viewer: true,
      can_use_narration: NARRATION_ENABLED_PACKAGES.has(normalizedCode),
      can_use_lineage_certificate: lane === "household" || lane === "network",
      can_open_family_intake: lane === "household" || lane === "network",
      can_open_org_intake: lane === "organization",
      can_use_link_keys: packageSupportsLinkKeys(normalizedCode),
      can_manage_link_keys: packageSupportsLinkKeys(normalizedCode),
      allowed_addons: [],
      upgrade_targets: [],
    };
  }

  function getResolvedEntitlements(
    activeEntitlement,
    packageCode,
    packageLane,
  ) {
    const fallback = buildFallbackEntitlements(packageCode, packageLane);
    const resolved =
      activeEntitlement &&
      activeEntitlement.resolved_entitlements &&
      typeof activeEntitlement.resolved_entitlements === "object"
        ? activeEntitlement.resolved_entitlements
        : {};

    return Object.assign({}, fallback, resolved, {
      package_code: stripMaintenanceSuffix(
        resolved.package_code || activeEntitlement?.package_code || packageCode,
      ),
      package_lane:
        normalizeValue(
          resolved.package_lane ||
            activeEntitlement?.package_lane ||
            packageLane,
        ) || fallback.package_lane,
    });
  }

  function toTimestamp(value) {
    if (!value) return 0;

    const timestamp = new Date(value).getTime();
    return Number.isFinite(timestamp) ? timestamp : 0;
  }

  function getRecordRecency(record) {
    if (!record || typeof record !== "object") return 0;

    return Math.max(
      toTimestamp(record.updated_at),
      toTimestamp(record.created_at),
      toTimestamp(record.delivered_at),
      toTimestamp(record.maintenance_started_at),
    );
  }

  function sortByMostRecent(items) {
    return (Array.isArray(items) ? items.slice() : []).sort(function (a, b) {
      return getRecordRecency(b) - getRecordRecency(a);
    });
  }

  function getPackageCodeFromRecord(record) {
    if (!record || typeof record !== "object") return "";

    return stripMaintenanceSuffix(
      normalizePackageCode(
        record.package_code || record.package_slug || record.package_type,
      ),
    );
  }

  function hasKnownPackage(record) {
    const packageCode = getPackageCodeFromRecord(record);
    return Boolean(packageCode && packageCode !== "unknown");
  }

  function getProjectIdFromRecord(record) {
    if (!record || typeof record !== "object") return "";

    const rawId = record.project_id || record.projectId || record.id || record._id;
    return rawId == null ? "" : String(rawId);
  }

  function getFamilyIdFromRecord(record) {
    if (!record || typeof record !== "object") return "";

    const rawId = record.family_id || record.familyId;
    return rawId == null ? "" : String(rawId).trim();
  }

  function getWorkspaceSelectionHints(search) {
    try {
      const params = new URLSearchParams(
        typeof search === "string" ? search : window.location.search,
      );

      return {
        projectId: String(params.get("project_id") || "").trim(),
        familyId: String(params.get("family_id") || "").trim(),
      };
    } catch (error) {
      return {
        projectId: "",
        familyId: "",
      };
    }
  }

  function hasWorkspaceSelectionHints(hints) {
    return Boolean(hints?.projectId || hints?.familyId);
  }

  function candidateMatchesWorkspaceHints(candidate, hints) {
    if (!candidate || !hasWorkspaceSelectionHints(hints)) {
      return false;
    }

    const candidateProjectId = String(
      candidate.projectId || getProjectIdFromRecord(candidate.activeProject),
    ).trim();
    const candidateFamilyId = getFamilyIdFromRecord(candidate.activeProject);

    if (hints.projectId && candidateProjectId === hints.projectId) {
      return true;
    }

    if (hints.familyId && candidateFamilyId === hints.familyId) {
      return true;
    }

    return false;
  }

  function toSerializableContextRecord(record) {
    if (!record || typeof record !== "object") return null;

    return {
      id: record.id,
      _id: record._id,
      project_id: record.project_id,
      projectId: record.projectId,
      family_id: record.family_id,
      familyId: record.familyId,
      package_code: record.package_code,
      package_slug: record.package_slug,
      package_name: record.package_name,
      package_lane: record.package_lane,
      project_lane: record.project_lane,
      status: record.status,
      created_at: record.created_at,
      updated_at: record.updated_at,
      delivered_at: record.delivered_at,
      item_type: record.item_type,
      resolved_entitlements:
        record.resolved_entitlements &&
        typeof record.resolved_entitlements === "object"
          ? record.resolved_entitlements
          : undefined,
    };
  }

  function toSerializableWorkspaceCandidate(candidate) {
    if (!candidate || typeof candidate !== "object") return null;

    return {
      source: candidate.source,
      sourcePriority: candidate.sourcePriority,
      projectId: candidate.projectId,
      packageCode: candidate.packageCode,
      packageLane: candidate.packageLane,
      packageName: candidate.packageName,
      sortKey: candidate.sortKey,
      resolvedEntitlements:
        candidate.resolvedEntitlements &&
        typeof candidate.resolvedEntitlements === "object"
          ? candidate.resolvedEntitlements
          : {},
      paidOrder: toSerializableContextRecord(candidate.paidOrder),
      activeEntitlement: toSerializableContextRecord(candidate.activeEntitlement),
      activeProject: toSerializableContextRecord(candidate.activeProject),
    };
  }

  function toSerializableDashboardContext(context, user) {
    if (!context || typeof context !== "object") return null;

    return {
      userId: String(
        user?.id ||
          user?._id ||
          user?.user_id ||
          context.user?.id ||
          context.user?._id ||
          "",
      ).trim(),
      userEmail: normalizeValue(user?.email || context.user?.email),
      storedAt: Date.now(),
      context: {
        user: user
          ? {
              id: user.id,
              _id: user._id,
              user_id: user.user_id,
              email: user.email,
              role: user.role,
              access_tier: user.access_tier,
              department_role: user.department_role,
              full_name: user.full_name,
              name: user.name,
            }
          : null,
        packageCode: context.packageCode,
        packageLane: context.packageLane,
        packageName: context.packageName,
        hasPackageAccess: Boolean(context.hasPackageAccess),
        hasPaidPackage: Boolean(context.hasPaidPackage),
        resolvedEntitlements:
          context.resolvedEntitlements &&
          typeof context.resolvedEntitlements === "object"
            ? context.resolvedEntitlements
            : {},
        paidOrder: toSerializableContextRecord(context.paidOrder),
        activeEntitlement: toSerializableContextRecord(context.activeEntitlement),
        activeProject: toSerializableContextRecord(context.activeProject),
        currentWorkspace: toSerializableWorkspaceCandidate(context.currentWorkspace),
      },
    };
  }

  function cacheDashboardContext(context, user) {
    try {
      const payload = toSerializableDashboardContext(context, user);
      if (!payload) return;

      window.sessionStorage.setItem(
        DASHBOARD_CONTEXT_STORAGE_KEY,
        JSON.stringify(payload),
      );
    } catch (error) {
      // no-op
    }
  }

  function clearCachedDashboardContext() {
    try {
      window.sessionStorage.removeItem(DASHBOARD_CONTEXT_STORAGE_KEY);
    } catch (error) {
      // no-op
    }
  }

  function readCachedDashboardContext(user, hints) {
    try {
      const raw = window.sessionStorage.getItem(DASHBOARD_CONTEXT_STORAGE_KEY);
      if (!raw) return null;

      const payload = JSON.parse(raw);
      const cachedContext =
        payload && typeof payload.context === "object" ? payload.context : null;

      if (!cachedContext) return null;

      const cachedUserId = String(payload.userId || "").trim();
      const currentUserId = String(
        user?.id || user?._id || user?.user_id || "",
      ).trim();
      const cachedUserEmail = normalizeValue(payload.userEmail);
      const currentUserEmail = normalizeValue(user?.email);

      if (
        (cachedUserId && currentUserId && cachedUserId !== currentUserId) ||
        (cachedUserEmail &&
          currentUserEmail &&
          cachedUserEmail !== currentUserEmail)
      ) {
        return null;
      }

      if (
        hasWorkspaceSelectionHints(hints) &&
        !candidateMatchesWorkspaceHints(cachedContext.currentWorkspace, hints) &&
        !candidateMatchesWorkspaceHints(
          {
            projectId: getProjectIdFromRecord(cachedContext.activeProject),
            activeProject: cachedContext.activeProject,
          },
          hints,
        )
      ) {
        return null;
      }

      return cachedContext;
    } catch (error) {
      return null;
    }
  }

  function createProjectLookup(items) {
    return (Array.isArray(items) ? items : []).reduce(function (lookup, item) {
      const projectId = getProjectIdFromRecord(item);
      if (projectId && !lookup.has(projectId)) {
        lookup.set(projectId, item);
      }
      return lookup;
    }, new Map());
  }

  function getPaidOrder(orders) {
    return (
      sortByMostRecent(
        (Array.isArray(orders) ? orders : []).filter(function (order) {
          if (!hasKnownPackage(order)) return false;

          const status = normalizeValue(order?.status);
          const itemType = normalizeValue(order?.item_type || "package");
          return (
            itemType === "package" &&
            ["paid", "complete", "completed", "succeeded"].includes(status)
          );
        }),
      )[0] || null
    );
  }

  function formatDate(value) {
    if (!value) return "—";

    try {
      return new Date(value).toLocaleString();
    } catch (error) {
      return String(value);
    }
  }

  function setLinkEnabled(element, enabled) {
    if (!element) return;

    if (!element.dataset.originalHref && element.getAttribute("href")) {
      element.dataset.originalHref = element.getAttribute("href");
    }

    if (enabled) {
      element.style.pointerEvents = "";
      element.style.opacity = "";
      element.removeAttribute("aria-disabled");

      if (element.dataset.originalHref) {
        element.setAttribute("href", element.dataset.originalHref);
      }
    } else {
      element.style.pointerEvents = "none";
      element.style.opacity = "0.45";
      element.setAttribute("aria-disabled", "true");
    }
  }

  function setButtonEnabled(element, enabled) {
    if (!element) return;

    element.disabled = !enabled;
    element.style.opacity = enabled ? "" : "0.45";
    element.style.pointerEvents = enabled ? "" : "none";
    element.setAttribute("aria-disabled", enabled ? "false" : "true");
  }

  function setActionEnabled(element, enabled) {
    if (!element) return;

    if (element.tagName === "A") {
      setLinkEnabled(element, enabled);
    } else {
      setButtonEnabled(element, enabled);
    }
  }

  function setActionHrefAndText(element, href, text) {
    if (!element) return;
    if (href) {
      element.setAttribute("href", href);
      element.dataset.originalHref = href;
    }
    if (text) {
      element.textContent = text;
    }
  }

  function setPaidActionState(enabled) {
    document.querySelectorAll("[data-paid-action]").forEach(function (element) {
      setActionEnabled(element, enabled);
    });
  }

  async function fetchCurrentUserWithToken(token) {
    const user = await app.apiRequest("/auth/me", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    app.saveUser(user);
    return user;
  }

  async function handleLogin(email, password) {
    const loginData = await app.apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    const token = getAccessTokenFromResponse(loginData);

    if (!token) {
      throw new Error("Login succeeded but no access token was returned.");
    }

    clearCachedDashboardContext();
    app.saveToken(token);

    const me = await fetchCurrentUserWithToken(token);
    app.saveUser(me);

    return { loginData, me };
  }

  function redirectAfterLogin() {
    window.location.href = POST_LOGIN_REDIRECT;
  }

  function populateUserFields(user, refs) {
    if (!user || !refs) return;

    if (refs.userName) refs.userName.textContent = user.full_name || "User";
    if (refs.userEmail) refs.userEmail.textContent = user.email || "";
    if (refs.userRole) refs.userRole.textContent = user.role || "user";
  }

  async function fetchOrders() {
    const payload = await app.apiRequest("/orders/my-orders", {
      method: "GET",
    });
    return toArray(payload);
  }

  async function fetchProjectEntitlements() {
    const payload = await app.apiRequest("/project-entitlements/my-active", {
      method: "GET",
    });
    return toArray(payload);
  }

  async function fetchProjects() {
    const payload = await app.apiRequest("/projects/", {
      method: "GET",
    });
    return toArray(payload);
  }

  function renderOrders(orders) {
    const statusNode = document.querySelector("[data-orders-status]");
    const listNode = document.querySelector("[data-orders-list]");
    if (!statusNode || !listNode) return;

    listNode.innerHTML = "";

    if (!orders.length) {
      statusNode.textContent = "No purchases have been recorded yet.";
      return;
    }

    statusNode.textContent = "Your recorded purchases are listed below.";

    orders.forEach(function (order, index) {
      const card = document.createElement("div");
      card.className = "feature-card feature-card-clean";

      const itemType = normalizeValue(order.item_type || "package");
      const billingPlan = normalizeValue(order.billing_plan || "one_time");

      let metaLine = "";
      if (itemType === "maintenance") {
        metaLine = `Billing: ${billingPlan || "maintenance"}`;
      } else if (itemType === "addon") {
        metaLine = "Type: Add-On";
      } else {
        metaLine = "Type: Package";
      }

      card.innerHTML = `
        <div class="card-number">${index + 1}</div>
        <h3>${order.package_name || order.package_code || order.package_slug || "Package"}</h3>
        <p class="card-copy">Status: ${order.status || "unknown"}</p>
        <p class="card-copy">Price: ${order.price_label || "—"}</p>
        <p class="card-copy">${metaLine}</p>
        <p class="card-copy">Created: ${formatDate(order.created_at)}</p>
      `;
      listNode.appendChild(card);
    });
  }

  function getActiveEntitlement(entitlements) {
    const active = sortByMostRecent(
      (Array.isArray(entitlements) ? entitlements : []).filter(function (item) {
        return hasKnownPackage(item) && normalizeValue(item.status) === "active";
      }),
    );

    if (active.length) return active[0];

    return (
      sortByMostRecent(
        (Array.isArray(entitlements) ? entitlements : []).filter(hasKnownPackage),
      )[0] || null
    );
  }

  function getActiveProject(projects, activeEntitlement, paidOrder) {
    const validProjects = sortByMostRecent(
      (Array.isArray(projects) ? projects : []).filter(hasKnownPackage),
    );
    if (!validProjects.length) return null;

    const projectsById = createProjectLookup(validProjects);

    const entitlementProjectId = getProjectIdFromRecord(activeEntitlement);
    if (entitlementProjectId) {
      const found = projectsById.get(entitlementProjectId);
      if (found) return found;
    }

    const paidOrderProjectId = getProjectIdFromRecord(paidOrder);
    if (paidOrderProjectId) {
      const found = projectsById.get(paidOrderProjectId);
      if (found) return found;
    }

    return validProjects[0] || null;
  }

  function buildWorkspaceCandidate(source, record, lookups) {
    if (!record || !hasKnownPackage(record)) return null;

    const recordProjectId = getProjectIdFromRecord(record);
    const activeEntitlement =
      source === "entitlement"
        ? record
        : recordProjectId
          ? lookups.entitlementsByProjectId.get(recordProjectId) || null
          : null;
    const activeProject =
      source === "project"
        ? record
        : recordProjectId
          ? lookups.projectsById.get(recordProjectId) || null
          : null;
    const paidOrder =
      source === "order"
        ? record
        : recordProjectId
          ? lookups.ordersByProjectId.get(recordProjectId) || null
          : null;

    const packageCode =
      getPackageCodeFromRecord(activeEntitlement) ||
      getPackageCodeFromRecord(activeProject) ||
      getPackageCodeFromRecord(paidOrder) ||
      getPackageCodeFromRecord(record);

    if (!packageCode || packageCode === "unknown") {
      return null;
    }

    const packageLane =
      normalizeValue(activeEntitlement?.package_lane) ||
      normalizeValue(activeProject?.project_lane) ||
      resolvePackageLane(packageCode);

    return {
      source,
      sourcePriority:
        source === "entitlement" ? 0 : source === "order" ? 1 : 2,
      paidOrder,
      activeEntitlement,
      activeProject,
      projectId:
        recordProjectId || getProjectIdFromRecord(activeEntitlement) || getProjectIdFromRecord(activeProject),
      packageCode,
      packageLane,
      packageName:
        activeEntitlement?.package_name ||
        activeEntitlement?.resolved_entitlements?.display_name ||
        paidOrder?.package_name ||
        activeProject?.package_name ||
        resolvePackageDisplayName(packageCode),
      resolvedEntitlements: getResolvedEntitlements(
        activeEntitlement,
        packageCode,
        packageLane,
      ),
      sortKey: Math.max(
        getRecordRecency(record),
        getRecordRecency(activeEntitlement),
        getRecordRecency(activeProject),
        getRecordRecency(paidOrder),
      ),
    };
  }

  function resolveCurrentWorkspace(orders, entitlements, projects, options) {
    const hints =
      options && typeof options === "object"
        ? {
            projectId: String(options.projectId || "").trim(),
            familyId: String(options.familyId || "").trim(),
          }
        : { projectId: "", familyId: "" };

    const paidOrders = sortByMostRecent(
      (Array.isArray(orders) ? orders : []).filter(function (order) {
        if (!hasKnownPackage(order)) return false;

        const status = normalizeValue(order?.status);
        const itemType = normalizeValue(order?.item_type || "package");
        return (
          itemType === "package" &&
          ["paid", "complete", "completed", "succeeded"].includes(status)
        );
      }),
    );
    const activeEntitlements = sortByMostRecent(
      (Array.isArray(entitlements) ? entitlements : []).filter(function (item) {
        return hasKnownPackage(item) && normalizeValue(item.status) === "active";
      }),
    );
    const validProjects = sortByMostRecent(
      (Array.isArray(projects) ? projects : []).filter(hasKnownPackage),
    );

    const lookups = {
      ordersByProjectId: createProjectLookup(paidOrders),
      entitlementsByProjectId: createProjectLookup(activeEntitlements),
      projectsById: createProjectLookup(validProjects),
    };

    const candidates = [];
    const seen = new Set();

    function pushCandidate(source, record) {
      const candidate = buildWorkspaceCandidate(source, record, lookups);
      if (!candidate) return;

      const key = [
        candidate.projectId || "no-project",
        candidate.packageCode || "no-package",
        candidate.source,
      ].join("|");

      if (seen.has(key)) return;
      seen.add(key);
      candidates.push(candidate);
    }

    activeEntitlements.forEach(function (item) {
      pushCandidate("entitlement", item);
    });
    paidOrders.forEach(function (item) {
      pushCandidate("order", item);
    });
    validProjects.forEach(function (item) {
      pushCandidate("project", item);
    });

    candidates.sort(function (left, right) {
      if (right.sortKey !== left.sortKey) {
        return right.sortKey - left.sortKey;
      }

      return left.sourcePriority - right.sourcePriority;
    });

    if (hasWorkspaceSelectionHints(hints)) {
      const hintedCandidate = candidates.find(function (candidate) {
        return candidateMatchesWorkspaceHints(candidate, hints);
      });

      if (hintedCandidate) {
        return hintedCandidate;
      }
    }

    return candidates[0] || null;
  }

  async function getDashboardContext(user, orders, options) {
    let entitlements = [];
    let projects = [];
    const hints =
      options && typeof options === "object"
        ? {
            projectId: String(options.projectId || "").trim(),
            familyId: String(options.familyId || "").trim(),
          }
        : { projectId: "", familyId: "" };

    try {
      const results = await Promise.all([
        fetchProjectEntitlements().catch(function () {
          return [];
        }),
        fetchProjects().catch(function () {
          return [];
        }),
      ]);

      entitlements = Array.isArray(results[0]) ? results[0] : [];
      projects = Array.isArray(results[1]) ? results[1] : [];
    } catch (error) {
      entitlements = [];
      projects = [];
    }

    const currentWorkspace = resolveCurrentWorkspace(
      orders,
      entitlements,
      projects,
      hints,
    );
    const paidOrder = currentWorkspace?.paidOrder || getPaidOrder(orders);
    const activeEntitlement =
      currentWorkspace?.activeEntitlement || getActiveEntitlement(entitlements);
    const activeProject =
      currentWorkspace?.activeProject ||
      getActiveProject(projects, activeEntitlement, paidOrder);

    const packageCode =
      currentWorkspace?.packageCode ||
      getPackageCodeFromRecord(activeEntitlement) ||
      getPackageCodeFromRecord(activeProject) ||
      getPackageCodeFromRecord(paidOrder);

    const packageLane =
      currentWorkspace?.packageLane ||
      normalizeValue(activeEntitlement?.package_lane) ||
      normalizeValue(activeProject?.project_lane) ||
      resolvePackageLane(packageCode);

    const packageName =
      currentWorkspace?.packageName ||
      activeEntitlement?.package_name ||
      activeEntitlement?.resolved_entitlements?.display_name ||
      paidOrder?.package_name ||
      activeProject?.package_name ||
      resolvePackageDisplayName(packageCode);

    const hasPackageAccess = Boolean(currentWorkspace && packageCode);
    const resolvedEntitlements =
      currentWorkspace?.resolvedEntitlements ||
      getResolvedEntitlements(activeEntitlement, packageCode, packageLane);

    return {
      user: user || null,
      orders,
      paidOrder,
      entitlements,
      activeEntitlement,
      projects,
      activeProject,
      packageCode,
      packageLane,
      packageName,
      resolvedEntitlements,
      currentWorkspace,
      hasPackageAccess,
      hasPaidPackage: hasPackageAccess,
    };
  }

  async function getDashboardContextForCurrentPage(user, orders) {
    const hints = getWorkspaceSelectionHints();
    const cached = readCachedDashboardContext(user, hints);

    if (cached) {
      return cached;
    }

    return getDashboardContext(user, orders, hints);
  }

  function publishDashboardContext(context) {
    window.TOLDashboardContext = context;
    cacheDashboardContext(context, context?.user);

    try {
      window.dispatchEvent(
        new CustomEvent("tol:dashboard-context-ready", {
          detail: context,
        }),
      );
    } catch (error) {
      // no-op
    }
  }

  function updateAccessState(context) {
    const accessStatus = document.querySelector("[data-access-status]");
    const intakeOpenAction = document.querySelector(
      "[data-intake-open-action]",
    );
    const upgradeAction = document.querySelector("[data-upgrade-action]");

    const hasPackageAccess = !!context?.hasPackageAccess;
    const packageLane = normalizeValue(context?.packageLane);
    const packageName = context?.packageName || "your package";
    const resolved =
      context?.resolvedEntitlements ||
      buildFallbackEntitlements(context?.packageCode, context?.packageLane);

    const canUploadRecords = Boolean(
      resolved.can_upload_verification_docs || resolved.can_upload_portraits,
    );
    const canUseLinkKeys = Boolean(resolved.can_use_link_keys);
    const canOpenFamilyIntake = Boolean(resolved.can_open_family_intake);
    const upgradeTargets = Array.isArray(resolved.upgrade_targets)
      ? resolved.upgrade_targets
      : [];
    const allowedAddons = Array.isArray(resolved.allowed_addons)
      ? resolved.allowed_addons
      : [];

    setPaidActionState(hasPackageAccess);

    if (intakeOpenAction) {
      const showIntakeAction = hasPackageAccess && canOpenFamilyIntake;
      setActionEnabled(intakeOpenAction, showIntakeAction);
      intakeOpenAction.style.display = showIntakeAction ? "" : "none";
    }

    if (upgradeAction) {
      upgradeAction.style.display = "";

      if (!hasPackageAccess) {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "View Packages",
        );
      } else if (packageLane === "portrait") {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "Upgrade to Household Package",
        );
      } else if (upgradeTargets.length && allowedAddons.length) {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "View Add-Ons & Upgrades",
        );
      } else if (allowedAddons.length) {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "View Add-Ons",
        );
      } else if (upgradeTargets.length) {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "View Upgrade Options",
        );
      } else if (packageLane === "organization" || packageLane === "network") {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "View Expansion Options",
        );
      } else {
        setActionHrefAndText(
          upgradeAction,
          "index.html#pricing",
          "View Packages",
        );
      }
    }

    if (!accessStatus) return;

    if (!hasPackageAccess) {
      accessStatus.textContent =
        "Purchase required. Buy a Tomb of Light package to unlock platform tools.";
      return;
    }

    if (packageLane === "portrait") {
      accessStatus.textContent = canUseLinkKeys
        ? `Access unlocked through ${packageName}. This portrait package includes uploads, verification workflows, and link capabilities. Household build tools require an upgrade.`
        : `Access unlocked through ${packageName}. This portrait package includes uploads and verification workflows. Household build tools require an upgrade.`;
      return;
    }

    if (packageLane === "organization") {
      accessStatus.textContent = canUseLinkKeys
        ? `Access unlocked through ${packageName}. This organization package includes structure workflows, verification uploads, and link capabilities.`
        : `Access unlocked through ${packageName}. This organization package includes structure workflows and verification uploads.`;
      return;
    }

    if (packageLane === "network") {
      accessStatus.textContent = canUseLinkKeys
        ? `Access unlocked through ${packageName}. Network, branch, verification, and link capabilities are active for this account.`
        : `Access unlocked through ${packageName}. Network, branch, and verification workflows are active for this account.`;
      return;
    }

    accessStatus.textContent = canUseLinkKeys
      ? `Access unlocked through ${packageName}. Family build tools, verification uploads, and link capabilities are active.`
      : `Access unlocked through ${packageName}. Family build tools and verification uploads are active.`;
  }

  function renderNoIntakeBecauseNoPurchase() {
    const intakeStatus = document.querySelector("[data-intake-card-status]");
    const currentPackage = document.querySelector(
      "[data-intake-current-package]",
    );
    const submissionStatus = document.querySelector(
      "[data-intake-status-badge]",
    );
    const submissionId = document.querySelector("[data-intake-submission-id]");
    const submittedAt = document.querySelector("[data-intake-submitted-at]");
    const nextStep = document.querySelector("[data-intake-next-step]");
    const lockNote = document.querySelector("[data-intake-lock-note]");
    const intakeHistoryStatus = document.querySelector(
      "[data-intake-history-status]",
    );
    const intakeHistoryList = document.querySelector(
      "[data-intake-history-list]",
    );

    if (intakeStatus) {
      intakeStatus.textContent = "Purchase required before intake opens.";
    }
    if (currentPackage) currentPackage.textContent = "No package detected";
    if (submissionStatus) submissionStatus.textContent = "Not submitted";
    if (submissionId) submissionId.textContent = "—";
    if (submittedAt) submittedAt.textContent = "—";
    if (nextStep) {
      nextStep.textContent = "Purchase a package first to unlock intake.";
    }
    if (lockNote) {
      lockNote.textContent =
        "Intake is locked until a package is attached to your account.";
    }
    if (intakeHistoryStatus) {
      intakeHistoryStatus.textContent = "No intake submissions found yet.";
    }
    if (intakeHistoryList) intakeHistoryList.innerHTML = "";
  }

  function setupSignupForm() {
    const form = document.querySelector("[data-signup-form]");
    if (!form) return;

    const statusNode = document.querySelector("[data-signup-status]");
    const submitBtn = form.querySelector("[data-submit-btn]");

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);
      const fullName = String(formData.get("full_name") || "").trim();
      const email = String(formData.get("email") || "")
        .trim()
        .toLowerCase();
      const password = String(formData.get("password") || "").trim();
      const confirmPassword = String(
        formData.get("confirm_password") || "",
      ).trim();

      const termsAccepted = Boolean(formData.get("terms_accepted"));
      const privacyAccepted = Boolean(formData.get("privacy_accepted"));
      const eligibilityAttested = Boolean(formData.get("eligibility_attested"));

      if (!fullName || !email || !password || !confirmPassword) {
        app.setStatus(
          statusNode,
          "Please complete all required fields.",
          "error",
        );
        return;
      }

      if (password.length < 8) {
        app.setStatus(
          statusNode,
          "Password must be at least 8 characters long.",
          "error",
        );
        return;
      }

      if (password !== confirmPassword) {
        app.setStatus(statusNode, "Passwords do not match.", "error");
        return;
      }

      if (!termsAccepted || !privacyAccepted || !eligibilityAttested) {
        app.setStatus(
          statusNode,
          "You must accept the Terms, Privacy Policy, and eligibility confirmation before creating an account.",
          "error",
        );
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Creating Account...";
      }

      try {
        await app.apiRequest("/auth/signup", {
          method: "POST",
          body: JSON.stringify({
            full_name: fullName,
            email,
            password,
            terms_accepted: termsAccepted,
            privacy_accepted: privacyAccepted,
            eligibility_attested: eligibilityAttested,
            policy_version: SIGNUP_POLICY_VERSION,
          }),
        });

        app.setStatus(
          statusNode,
          "Account created successfully. Signing you in...",
          "success",
        );

        await handleLogin(email, password);
        redirectAfterLogin();
      } catch (error) {
        app.setStatus(
          statusNode,
          getErrorMessage(error) || "Signup failed.",
          "error",
        );
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Create Account";
        }
      }
    });
  }

  function setupSigninForm() {
    const form = document.querySelector("[data-signin-form]");
    if (!form) return;

    const statusNode = document.querySelector("[data-signin-status]");
    const submitBtn = form.querySelector("[data-submit-btn]");
    const defaultSubmitLabel =
      (submitBtn && submitBtn.textContent
        ? submitBtn.textContent.trim()
        : "") || "Enter Portal";

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);
      const email = String(formData.get("email") || "")
        .trim()
        .toLowerCase();
      const password = String(formData.get("password") || "").trim();

      if (!email || !password) {
        app.setStatus(
          statusNode,
          "Please enter your email and password.",
          "error",
        );
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Signing In...";
      }

      try {
        await handleLogin(email, password);
        app.setStatus(statusNode, "Portal access granted.", "success");
        redirectAfterLogin();
      } catch (error) {
        app.setStatus(
          statusNode,
          getErrorMessage(error) || "Login failed.",
          "error",
        );
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = defaultSubmitLabel;
        }
      }
    });
  }

  async function setupDashboard() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    const authRequired = document.querySelector("[data-auth-required]");
    const userName = document.querySelector("[data-user-name]");
    const userEmail = document.querySelector("[data-user-email]");
    const userRole = document.querySelector("[data-user-role]");
    const statusNode = document.querySelector("[data-dashboard-status]");

    const refs = { userName, userEmail, userRole };

    const token = app.getToken();
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    const savedUser = app.getSavedUser();
    if (savedUser) {
      populateUserFields(savedUser, refs);
      if (authRequired) authRequired.style.display = "block";
    }

    let me = null;

    try {
      me = await withRetry(
        function () {
          return app.fetchCurrentUser();
        },
        2,
        300,
      );

      populateUserFields(me, refs);

      if (authRequired) authRequired.style.display = "block";

      if (isInternalRole(me)) {
        app.setStatus(
          statusNode,
          "You are signed in to the Tomb of Light internal operations portal.",
          "success",
        );
        return;
      }

      app.setStatus(
        statusNode,
        "You are signed in and connected to the Tomb of Light platform.",
        "success",
      );
    } catch (error) {
      if (isAuthFailure(error)) {
        clearCachedDashboardContext();
        app.clearSession();
        app.setStatus(
          statusNode,
          "Your session is not valid. Please sign in again.",
          "error",
        );
        setTimeout(function () {
          window.location.href = "signin.html";
        }, 1200);
        return;
      }

      console.error("Dashboard auth verification failed:", error);

      if (!savedUser) {
        app.setStatus(
          statusNode,
          "We could not verify your session right now. Please refresh and try again.",
          "error",
        );
        return;
      }

      app.setStatus(
        statusNode,
        "You appear signed in. Live account verification is temporarily unavailable.",
        "error",
      );
      return;
    }

    try {
      const orders = await withRetry(
        function () {
          return fetchOrders();
        },
        2,
        300,
      );

      renderOrders(orders);

      const context = await getDashboardContext(me, orders);
      updateAccessState(context);
      publishDashboardContext(context);

      if (!context.hasPackageAccess) {
        renderNoIntakeBecauseNoPurchase();
        app.setStatus(
          statusNode,
          "Your customer workspace is connected, but no active package is attached yet.",
          "error",
        );
        return;
      }

      app.setStatus(
        statusNode,
        `Your package is active: ${context.packageName || "Active Package"}.`,
        "success",
      );
    } catch (error) {
      console.error("Dashboard load failed:", error);

      if (isAuthFailure(error)) {
        clearCachedDashboardContext();
        app.clearSession();
        app.setStatus(
          statusNode,
          "Your session expired while loading dashboard data. Please sign in again.",
          "error",
        );
        setTimeout(function () {
          window.location.href = "signin.html";
        }, 1200);
        return;
      }

      app.setStatus(
        statusNode,
        "You are signed in, but your dashboard data could not be loaded yet.",
        "error",
      );
    }
  }

  async function gatePurchaseRequiredPages() {
    const page = window.location.pathname.split("/").pop() || "";

    const uploadPages = new Set(["verification-upload.html"]);
    const linkKeyPages = new Set(["link-keys.html"]);
    const familyIntakePages = new Set([
      "intake-welcome.html",
      "intake-household.html",
      "intake-family-map.html",
      "intake-uploads.html",
      "intake-consent.html",
      "intake-review.html",
    ]);
    const familyTreePages = new Set([
      "tree-view.html",
      "create-family.html",
      "add-member.html",
      "create-relationship.html",
      "family-graph.html",
      "lineage-intelligence.html",
    ]);
    const certificatePages = new Set(["lineage-certificate.html"]);

    if (
      !uploadPages.has(page) &&
      !linkKeyPages.has(page) &&
      !familyIntakePages.has(page) &&
      !familyTreePages.has(page) &&
      !certificatePages.has(page)
    ) {
      return;
    }

    const token = app.getToken();
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    try {
      const me = await withRetry(
        function () {
          return app.fetchCurrentUser();
        },
        2,
        300,
      );

      if (isInternalRole(me)) {
        return;
      }

      const orders = await withRetry(
        function () {
          return fetchOrders();
        },
        2,
        300,
      );

      const context = await getDashboardContextForCurrentPage(me, orders);
      publishDashboardContext(context);
      const resolved =
        context?.resolvedEntitlements ||
        buildFallbackEntitlements(context?.packageCode, context?.packageLane);

      if (!context || !context.hasPackageAccess) {
        window.location.href = "dashboard.html?purchase_required=1";
        return;
      }

      if (
        uploadPages.has(page) &&
        !(
          resolved.can_upload_verification_docs || resolved.can_upload_portraits
        )
      ) {
        window.location.href = "dashboard.html?purchase_required=1";
        return;
      }

      if (linkKeyPages.has(page) && !resolved.can_use_link_keys) {
        window.location.href = "dashboard.html?upgrade_required=1";
        return;
      }

      if (familyIntakePages.has(page) && !resolved.can_open_family_intake) {
        window.location.href = "dashboard.html?upgrade_required=1";
        return;
      }

      if (familyTreePages.has(page) && !resolved.can_build_family_tree) {
        window.location.href = "dashboard.html?upgrade_required=1";
        return;
      }

      if (certificatePages.has(page) && !resolved.can_use_lineage_certificate) {
        window.location.href = "dashboard.html?upgrade_required=1";
      }
    } catch (error) {
      if (isAuthFailure(error)) {
        clearCachedDashboardContext();
        app.clearSession();
        window.location.href = "signin.html";
        return;
      }

      console.error("Purchase gate check failed:", error);
    }
  }

  function bindLogoutButtons() {
    document.querySelectorAll("[data-logout-btn]").forEach(function (button) {
      button.addEventListener("click", async function () {
        try {
          if (app.logoutUser) {
            await app.logoutUser();
          } else {
            app.clearSession();
          }
        } catch (error) {
          app.clearSession();
        }

        clearCachedDashboardContext();
        window.location.href = "signin.html";
      });
    });
  }

  function protectAuthPages() {
    const isSigninPage = !!document.querySelector("[data-signin-form]");
    const isSignupPage = !!document.querySelector("[data-signup-form]");
    const token = app.getToken();

    if (!(isSigninPage || isSignupPage) || !token) {
      return;
    }

    withRetry(
      function () {
        return app.fetchCurrentUser();
      },
      2,
      300,
    )
      .then(function () {
        redirectAfterLogin();
      })
      .catch(function (error) {
        if (isAuthFailure(error)) {
          clearCachedDashboardContext();
          app.clearSession();
        } else {
          console.error("Auth page protection check failed:", error);
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    protectAuthPages();
    setupSignupForm();
    setupSigninForm();
    setupDashboard();
    bindLogoutButtons();
    gatePurchaseRequiredPages();
  });

  window.TOLAuthPages = {
    handleLogin,
    redirectAfterLogin,
    fetchOrders,
    fetchProjectEntitlements,
    fetchProjects,
    getDashboardContext,
    getDashboardContextForCurrentPage,
    getResolvedEntitlements,
    buildFallbackEntitlements,
    getWorkspaceSelectionHints,
    normalizePackageCode,
    resolvePackageLane,
    resolvePackageDisplayName,
    packageSupportsLinkKeys,
    isInternalRole,
    getPaidOrder,
  };
})();
