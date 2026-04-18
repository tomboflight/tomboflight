(function () {
  const app = window.TOLApp || window.TOLAuth;
  if (!app) return;

  const statusNode = document.querySelector("[data-household-status]");
  const inviteForm = document.querySelector("[data-household-invite-form]");
  const inviteStatus = document.querySelector("[data-household-invite-status]");
  const acceptForm = document.querySelector("[data-household-accept-form]");
  const acceptStatus = document.querySelector("[data-household-accept-status]");
  const acceptLinkStatus = document.querySelector("[data-household-accept-link-status]");
  const membersList = document.querySelector("[data-household-members-list]");
  const invitesList = document.querySelector("[data-household-invites-list]");
  const membersEmpty = document.querySelector("[data-household-members-empty]");
  const invitesEmpty = document.querySelector("[data-household-invites-empty]");
  const membersLoading = document.querySelector("[data-household-members-loading]");
  const invitesLoading = document.querySelector("[data-household-invites-loading]");
  const membersError = document.querySelector("[data-household-members-error]");
  const invitesError = document.querySelector("[data-household-invites-error]");
  const pendingCount = document.querySelector("[data-household-pending-count]");
  const inviteCoOwnerButton = document.querySelector("[data-household-invite-co-owner]");
  const inviteFamilyButton = document.querySelector("[data-household-invite-family]");

  const ROLE_OPTIONS = [
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
    "viewer",
    "minor_viewer",
    "linked_relative",
  ];

  const ROLE_LABELS = {
    billing_owner: "Billing Owner",
    co_owner: "Co-Owner",
    family_manager: "Family Manager",
    contributor: "Contributor",
    viewer: "Viewer",
    minor_viewer: "Minor Viewer",
    linked_relative: "Linked Relative",
  };

  const ROLE_ALIASES = {
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

  const RELATIONSHIP_LABELS = {
    spouse: "Spouse",
    parent: "Parent",
    child: "Child",
    sibling: "Sibling",
    household_member: "Household Member",
    guardian: "Guardian",
    relative: "Relative",
    other: "Other",
  };

  const PRIVACY_LABELS = {
    household_private: "Household Private",
    household_shared: "Shared Household Access",
    read_only: "Read Only",
    link_only: "Link-Only Access",
    private_to_owner: "Owner Private",
    private_to_owner_and_co_owner: "Owner + Co-Owner Private",
    branch_shared: "Shared Household Access",
    linked_family_shared: "Link-Only Access",
    public_memorial: "Read Only",
    minor_protected: "Household Private",
  };

  const DEFAULT_NOTE_BY_ROLE_RELATIONSHIP = {
    co_owner: {
      spouse: "Spouse invited as co-owner for household management and family tree collaboration.",
    },
    family_manager: {
      spouse: "Spouse invited as family manager to help manage household records and family tree collaboration.",
      parent: "Parent invited to help manage household records and family information.",
    },
    viewer: {
      relative: "Relative invited with read-only household access.",
    },
    contributor: {
      child: "Child invited to contribute approved family content.",
    },
  };

  const ROLE_PRIORITY = {
    billing_owner: 100,
    co_owner: 80,
    family_manager: 60,
    contributor: 40,
    viewer: 20,
    minor_viewer: 10,
    linked_relative: 10,
    legacy_executor: 5,
  };

  const ROLE_ASSIGNMENTS = {
    billing_owner: new Set(ROLE_OPTIONS),
    co_owner: new Set(["family_manager", "contributor", "viewer", "minor_viewer", "linked_relative"]),
    family_manager: new Set(["contributor", "viewer", "minor_viewer"]),
  };

  const ROLE_CAN_MANAGE_ACCESS = new Set(["billing_owner", "co_owner", "family_manager"]);

  let currentProjectId = "";
  let currentUser = null;
  let currentMemberRole = "viewer";
  let hasResolvedMemberRole = false;

  function inviteApiFallbackBaseUrls() {
    const configuredFallbacks = Array.isArray(window.TOL_CONFIG?.INVITE_API_BASE_URL_FALLBACKS)
      ? window.TOL_CONFIG.INVITE_API_BASE_URL_FALLBACKS
      : [];
    return configuredFallbacks.map(normalizeBaseUrl).filter(Boolean);
  }

  function normalizeBaseUrl(value) {
    return String(value || "")
      .trim()
      .replace(/\/+$/, "");
  }

  function readableMessage(value, fallback = "") {
    if (typeof app.getReadableErrorMessage === "function") {
      const parsed = app.getReadableErrorMessage(value, "");
      if (parsed) return parsed;
    }
    const normalized = String(value || "").trim();
    if (normalized && normalized !== "[object Object]") return normalized;
    return String(fallback || "").trim();
  }

  function isFrontendOriginBaseUrl(value) {
    const normalized = normalizeBaseUrl(value);
    if (!normalized) return false;
    try {
      return new URL(normalized).origin === window.location.origin;
    } catch (_error) {
      return false;
    }
  }

  function ensureApiConfigForHouseholdAccess() {
    if (typeof app.isLocalApp === "function" && app.isLocalApp()) return;
    const currentConfig = window.TOL_CONFIG || {};
    const configuredBase = normalizeBaseUrl(currentConfig.API_BASE_URL);
    const configuredList = Array.isArray(currentConfig.API_BASE_URLS)
      ? currentConfig.API_BASE_URLS.map(normalizeBaseUrl).filter(Boolean)
      : [];
    const configuredCandidates = [configuredBase, ...configuredList]
      .filter(Boolean)
      .filter((value) => !isFrontendOriginBaseUrl(value));
    const runtimeBase =
      typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "";
    const mergedCandidates = Array.from(
      new Set([
        runtimeBase,
        ...configuredCandidates,
        ...inviteApiFallbackBaseUrls(),
      ].filter((value) => value && !isFrontendOriginBaseUrl(value))),
    );
    if (!mergedCandidates.length) {
      console.warn("[HouseholdAccess] API base config is invalid for live mode.", {
        API_BASE_URL: currentConfig.API_BASE_URL,
        API_BASE_URLS: currentConfig.API_BASE_URLS,
      });
      return;
    }
    window.TOL_CONFIG = Object.assign({}, currentConfig, {
      API_BASE_URL: mergedCandidates[0],
      API_BASE_URLS: mergedCandidates,
    });
    console.warn("[HouseholdAccess] Applied live API base fallback config.", {
      API_BASE_URL: window.TOL_CONFIG.API_BASE_URL,
      API_BASE_URLS: window.TOL_CONFIG.API_BASE_URLS,
    });
  }

  function buildInviteRequestUrl(path, error) {
    const explicitUrl = String(error?.requestUrl || "").trim();
    if (explicitUrl) return explicitUrl;
    if (/^https?:\/\//i.test(String(path || ""))) return String(path);
    const baseFromApp =
      typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "";
    const baseFromConfig = normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL);
    const base = baseFromApp || baseFromConfig;
    return base ? `${base}${path}` : String(path || "");
  }

  function inviteDebugMeta(path, payload, error) {
    const resolvedApiBaseUrl = normalizeBaseUrl(error?.resolvedApiBaseUrl || app.getApiBaseUrl?.());
    const resolvedApiBaseUrls = resolveInviteApiBaseUrls();
    const configuredApiBaseUrl = normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL);
    const tokenPresent =
      typeof app.getToken === "function" ? Boolean(String(app.getToken() || "").trim()) : false;
    return {
      resolvedApiBaseUrl,
      resolvedApiBaseUrls,
      configuredApiBaseUrl,
      requestUrl: buildInviteRequestUrl(path, error),
      method: "POST",
      authTokenPresent: tokenPresent,
      payload: payload || null,
    };
  }

  function userInviteErrorMessage(error, fallback) {
    const detail = readableMessage(
      error?.detail || error?.message || error?.data || error?.responseBody,
      "",
    );
    const statusCode = Number(error?.status || 0);
    if (statusCode === 404) {
      return "The invite feature is currently unavailable. Please contact support.";
    }
    if (statusCode === 403) {
      return "Your current role cannot send this invite. Please use a billing owner account.";
    }
    if (statusCode === 400) {
      return detail || "The invite details are invalid. Please check the form and try again.";
    }
    return detail || fallback;
  }

  function logInviteFailure(action, path, error, payload) {
    console.error("[HouseholdAccess] Invite request failed.", {
      action,
      ...inviteDebugMeta(path, payload, error),
      status: error?.status ?? null,
      statusText: error?.statusText || "",
      responseBody: error?.data ?? error?.responseBody ?? error?.detail ?? error?.message ?? null,
    });
  }

  function logInviteRequest(action, path, payload) {
    console.info("[HouseholdAccess] Invite request.", {
      action,
      ...inviteDebugMeta(path, payload),
    });
  }

  function logInviteSuccess(action, path, responseBody, payload, responseMeta) {
    console.info("[HouseholdAccess] Invite request succeeded.", {
      action,
      ...inviteDebugMeta(path, payload),
      status: Number(responseMeta?.status || 201),
      requestUrl: String(responseMeta?.requestUrl || buildInviteRequestUrl(path, responseMeta)),
      responseBody,
    });
  }

  function resolveInviteApiBaseUrls() {
    const configuredBase = normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL);
    const configuredList = Array.isArray(window.TOL_CONFIG?.API_BASE_URLS)
      ? window.TOL_CONFIG.API_BASE_URLS.map(normalizeBaseUrl).filter(Boolean)
      : [];
    const runtimeBase =
      typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "";
    return Array.from(
      new Set(
        [runtimeBase, configuredBase, ...configuredList]
          .concat(inviteApiFallbackBaseUrls())
          .map(normalizeBaseUrl)
          .filter((value) => value && !isFrontendOriginBaseUrl(value)),
      ),
    );
  }

  function loadRequestPaths(pathOrPaths) {
    return Array.from(
      new Set(
        (Array.isArray(pathOrPaths) ? pathOrPaths : [pathOrPaths])
          .map((value) => String(value || "").trim())
          .filter(Boolean),
      ),
    );
  }

  function loadDebugMeta(path, method, projectId, error) {
    const resolvedApiBaseUrl = normalizeBaseUrl(error?.resolvedApiBaseUrl || app.getApiBaseUrl?.());
    const resolvedApiBaseUrls = resolveInviteApiBaseUrls();
    const configuredApiBaseUrl = normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL);
    const tokenPresent =
      typeof app.getToken === "function" ? Boolean(String(app.getToken() || "").trim()) : false;
    return {
      resolvedApiBaseUrl,
      resolvedApiBaseUrls,
      configuredApiBaseUrl,
      requestUrl: buildInviteRequestUrl(path, error),
      method: String(method || "GET").toUpperCase(),
      authTokenPresent: tokenPresent,
      projectId: String(projectId || "").trim() || null,
    };
  }

  function logLoadRequest(action, path, method, projectId, requestMeta) {
    console.info("[HouseholdAccess] Load request.", {
      action,
      ...loadDebugMeta(path, method, projectId, requestMeta),
      requestUrl: String(requestMeta?.requestUrl || buildInviteRequestUrl(path, requestMeta)),
    });
  }

  function logLoadResponse(action, path, method, projectId, responseMeta, responseBody) {
    console.info("[HouseholdAccess] Load request response.", {
      action,
      ...loadDebugMeta(path, method, projectId, responseMeta),
      status: Number(responseMeta?.status || 0),
      requestUrl: String(responseMeta?.requestUrl || buildInviteRequestUrl(path, responseMeta)),
      responseBody,
    });
  }

  function logLoadFailure(action, path, method, projectId, error) {
    console.error("[HouseholdAccess] Load request failed.", {
      action,
      ...loadDebugMeta(path, method, projectId, error),
      status: error?.status ?? null,
      statusText: error?.statusText || "",
      responseBody: error?.data ?? error?.responseBody ?? error?.detail ?? error?.message ?? null,
    });
  }

  async function sendLoadRequest(pathOrPaths, action, projectId, options = {}) {
    const paths = loadRequestPaths(pathOrPaths);
    const apiBaseUrls = resolveInviteApiBaseUrls();
    const authToken = typeof app.getToken === "function" ? String(app.getToken() || "").trim() : "";
    const fallbackStatusCodes = new Set(
      (Array.isArray(options.fallbackStatusCodes) && options.fallbackStatusCodes.length
        ? options.fallbackStatusCodes
        : [404, 500, 502, 503, 504]
      )
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0),
    );
    let lastError = null;

    for (const path of paths) {
      for (const apiBaseUrl of apiBaseUrls) {
        const requestUrl = `${apiBaseUrl}${path}`;
        logLoadRequest(action, path, "GET", projectId, {
          requestUrl,
          resolvedApiBaseUrl: apiBaseUrl,
        });
        try {
          const headers = { Accept: "application/json" };
          if (authToken) headers.Authorization = `Bearer ${authToken}`;
          const response = await fetch(requestUrl, {
            method: "GET",
            credentials: "include",
            headers,
          });
          const contentType = String(response.headers.get("content-type") || "").toLowerCase();
          let responseBody = null;
          if (contentType.includes("application/json")) {
            responseBody = await response.json();
          } else {
            const text = await response.text();
            responseBody = text ? { detail: text } : null;
          }
          const responseMeta = {
            requestUrl,
            resolvedApiBaseUrl: apiBaseUrl,
            status: response.status,
          };
          logLoadResponse(action, path, "GET", projectId, responseMeta, responseBody);
          if (!response.ok) {
            const detail = readableMessage(
              responseBody?.detail || responseBody?.message || responseBody?.error || responseBody,
              response.statusText || `Request failed with status ${response.status}`,
            );
            const error = new Error(detail || `Request failed with status ${response.status}`);
            error.status = response.status;
            error.statusText = response.statusText;
            error.detail = detail;
            error.data = responseBody;
            error.responseBody = responseBody;
            error.requestUrl = requestUrl;
            error.resolvedApiBaseUrl = apiBaseUrl;
            lastError = error;
            logLoadFailure(action, path, "GET", projectId, error);
            if (fallbackStatusCodes.has(response.status)) {
              continue;
            }
            throw error;
          }
          return responseBody;
        } catch (error) {
          if (fallbackStatusCodes.has(Number(error?.status || 0))) {
            lastError = error;
            continue;
          }
          if (Number(error?.status || 0) > 0) {
            throw error;
          }
          const networkError = new Error(error?.message || "Network request failed.");
          networkError.status = 0;
          networkError.detail = error?.message || "Network request failed.";
          networkError.requestUrl = requestUrl;
          networkError.resolvedApiBaseUrl = apiBaseUrl;
          lastError = networkError;
          logLoadFailure(action, path, "GET", projectId, networkError);
        }
      }
    }

    throw (
      lastError ||
      new Error(
        `Load endpoint unavailable for paths [${paths.join(", ") || "none"}] across all configured hosts: ${apiBaseUrls.join(", ") || "none"}`,
      )
    );
  }

  function workspaceMembersLoadPaths(projectId) {
    const encoded = encodeURIComponent(String(projectId || "").trim());
    return [
      `/workspace-access/project/${encoded}/members`,
      `/workspace_access/project/${encoded}/members`,
      `/household-access/project/${encoded}/members`,
    ];
  }

  function workspaceInvitesLoadPaths(projectId) {
    const encoded = encodeURIComponent(String(projectId || "").trim());
    return [
      `/workspace-access/project/${encoded}/invites`,
      `/workspace_access/project/${encoded}/invites`,
      `/household-access/project/${encoded}/invites`,
    ];
  }

  async function sendInviteRequest(path, payload, action) {
    const apiBaseUrls = resolveInviteApiBaseUrls();
    const authToken = typeof app.getToken === "function" ? String(app.getToken() || "").trim() : "";
    let lastError = null;
    for (const apiBaseUrl of apiBaseUrls) {
      const requestUrl = `${apiBaseUrl}${path}`;
      logInviteRequest(action, path, payload);
      console.info("[HouseholdAccess] Invite request attempt.", {
        action,
        resolvedApiBaseUrl: apiBaseUrl,
        requestUrl,
        method: "POST",
        payload,
      });
      try {
        const headers = {
          Accept: "application/json",
          "Content-Type": "application/json",
        };
        if (authToken) headers.Authorization = `Bearer ${authToken}`;
        const response = await fetch(requestUrl, {
          method: "POST",
          credentials: "include",
          headers,
          body: JSON.stringify(payload),
        });
        const contentType = String(response.headers.get("content-type") || "").toLowerCase();
        let responseBody = null;
        if (contentType.includes("application/json")) {
          responseBody = await response.json();
        } else {
          const text = await response.text();
          responseBody = text ? { detail: text } : null;
        }
        console.info("[HouseholdAccess] Invite request response.", {
          action,
          resolvedApiBaseUrl: apiBaseUrl,
          requestUrl,
          method: "POST",
          payload,
          status: response.status,
          responseBody,
        });
        if (!response.ok) {
          const detail = readableMessage(
            responseBody?.detail || responseBody?.message || responseBody?.error || responseBody,
            response.statusText || `Request failed with status ${response.status}`,
          );
          const error = new Error(detail || `Request failed with status ${response.status}`);
          error.status = response.status;
          error.statusText = response.statusText;
          error.detail = detail;
          error.data = responseBody;
          error.responseBody = responseBody;
          error.requestUrl = requestUrl;
          error.resolvedApiBaseUrl = apiBaseUrl;
          lastError = error;
          if (response.status === 404) {
            // Some live environments run mixed backend versions per host; keep
            // trying remaining API hosts so invite creation is not blocked.
            continue;
          }
          throw error;
        }
        return {
          responseBody,
          meta: {
            requestUrl,
            resolvedApiBaseUrl: apiBaseUrl,
            status: response.status,
          },
        };
      } catch (error) {
        if (Number(error?.status || 0) === 404) {
          lastError = error;
          continue;
        }
        if (Number(error?.status || 0) > 0) {
          throw error;
        }
        const networkError = new Error(error?.message || "Network request failed.");
        networkError.status = 0;
        networkError.detail = error?.message || "Network request failed.";
        networkError.requestUrl = requestUrl;
        networkError.resolvedApiBaseUrl = apiBaseUrl;
        lastError = networkError;
      }
    }
    throw (
      lastError ||
      new Error(
        `Invite endpoint unavailable across all configured hosts: ${apiBaseUrls.join(", ") || "none"}`,
      )
    );
  }

  function setText(node, message, type = "info") {
    if (!node) return;
    app.setStatus(node, message, type);
  }

  function clear(node) {
    if (!node) return;
    app.clearStatus(node);
  }

  function roleLabel(role) {
    return ROLE_LABELS[normalizeRole(role)] || "Viewer";
  }

  function relationshipLabel(value) {
    const normalized = normalizeLower(value).replace(/-/g, "_");
    if (!normalized) return "Household Member";
    if (RELATIONSHIP_LABELS[normalized]) return RELATIONSHIP_LABELS[normalized];
    return titleLabel(normalized);
  }

  function privacyLabel(value) {
    return PRIVACY_LABELS[String(value || "").trim()] || "Household Private";
  }

  function titleLabel(value) {
    return String(value || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, function (char) {
        return char.toUpperCase();
      });
  }

  function formatDateTime(value) {
    const normalized = normalizeValue(value);
    if (!normalized) return "—";
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return normalized;
    try {
      return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(parsed);
    } catch (_error) {
      return parsed.toISOString().split("T")[0];
    }
  }

  function normalizeInviteStatus(value) {
    const normalized = normalizeLower(value);
    if (normalized === "accepted") return "Accepted";
    if (normalized === "expired") return "Expired";
    if (normalized === "revoked") return "Revoked";
    if (normalized === "pending") return "Pending";
    return titleLabel(normalized || "pending");
  }

  function memberDisplayName(member) {
    const directName = normalizeValue(
      member?.full_name || member?.display_name || member?.name || member?.user_name,
    );
    if (directName) return directName;
    const first = normalizeValue(member?.first_name || member?.given_name);
    const last = normalizeValue(member?.last_name || member?.family_name);
    const joined = `${first} ${last}`.trim();
    if (joined) return joined;
    return "Name not provided";
  }

  function setLoadingState(loading) {
    const show = Boolean(loading);
    if (membersLoading) membersLoading.style.display = show ? "block" : "none";
    if (invitesLoading) invitesLoading.style.display = show ? "block" : "none";
  }

  function setLoadErrorState(message = "") {
    const errorText = normalizeValue(message);
    if (membersError) {
      membersError.style.display = errorText ? "block" : "none";
      membersError.textContent = errorText;
    }
    if (invitesError) {
      invitesError.style.display = errorText ? "block" : "none";
      invitesError.textContent = errorText;
    }
  }

  function normalizeValue(value) {
    return String(value || "").trim();
  }

  function normalizeLower(value) {
    return normalizeValue(value).toLowerCase();
  }

  function normalizeRole(value) {
    const normalized = normalizeLower(value);
    const aliased = ROLE_ALIASES[normalized] || normalized;
    return ROLE_OPTIONS.includes(aliased) ? aliased : "viewer";
  }

  function roleRank(role) {
    return Number(ROLE_PRIORITY[normalizeRole(role)] || 0);
  }

  function roleCanAssign(actorRole, targetRole) {
    const actor = normalizeRole(actorRole);
    const target = normalizeRole(targetRole);
    return Boolean(ROLE_ASSIGNMENTS[actor] && ROLE_ASSIGNMENTS[actor].has(target));
  }

  function roleCanManageAccess(role) {
    return ROLE_CAN_MANAGE_ACCESS.has(normalizeRole(role));
  }

  function currentUserIdentity() {
    if (!currentUser) return { userId: "", email: "" };
    return {
      userId: normalizeValue(currentUser?.id || currentUser?._id || currentUser?.user_id),
      email: normalizeLower(currentUser?.email),
    };
  }

  function roleNode() {
    return inviteForm ? inviteForm.querySelector('select[name="member_role"]') : null;
  }

  function relationshipNode() {
    return inviteForm ? inviteForm.querySelector('select[name="relationship_scope"]') : null;
  }

  function privacyNode() {
    return inviteForm ? inviteForm.querySelector('select[name="privacy_scope"]') : null;
  }

  function noteNode() {
    return inviteForm ? inviteForm.querySelector('input[name="notes"]') : null;
  }

  function isNoteCustomized() {
    const node = noteNode();
    return Boolean(node && node.dataset.customized === "true");
  }

  function buildAutoNote(memberRole, relationshipScope, privacyScope) {
    const roleValue = String(memberRole || "viewer").trim();
    const relationshipValue = String(relationshipScope || "household_member").trim();
    const privacyValue = String(privacyScope || "").trim();
    const preset = DEFAULT_NOTE_BY_ROLE_RELATIONSHIP[roleValue]?.[relationshipValue];
    if (preset) return preset;
    if (roleValue === "linked_relative") {
      return `${relationshipLabel(relationshipValue)} invited for link-only household access.`;
    }
    const isViewerRole = roleValue === "viewer" || roleValue === "minor_viewer";
    if (isViewerRole || privacyValue === "read_only") {
      return `${relationshipLabel(relationshipValue)} invited with read-only household access.`;
    }
    return `${relationshipLabel(relationshipValue)} invited as ${titleLabel(roleValue).toLowerCase()} for household collaboration.`;
  }

  function updateAutoInviteDefaults(force = false) {
    if (!inviteForm) return;
    const roleValue = String(roleNode()?.value || "viewer").trim();
    const relationshipValue = String(relationshipNode()?.value || "household_member").trim();
    const privacy = privacyNode();
    if (roleValue === "co_owner" && relationshipValue === "spouse" && privacy) {
      privacy.value = "household_private";
    }
    const privacyValue = String(privacy?.value || "household_private").trim();
    const notes = noteNode();
    if (!notes) return;
    const generated = buildAutoNote(roleValue, relationshipValue, privacyValue);
    if (force || !isNoteCustomized() || !String(notes.value || "").trim()) {
      notes.value = generated;
      notes.dataset.customized = "false";
    }
  }

  function projectIdFromContext(user) {
    const params = new URLSearchParams(window.location.search);
    const directProjectId = String(params.get("project_id") || "").trim();
    if (directProjectId) return directProjectId;

    const context = window.TOLDashboardContext || null;
    const activeProject = context?.activeProject || null;
    if (activeProject && (activeProject.id || activeProject._id || activeProject.project_id)) {
      return String(activeProject.id || activeProject._id || activeProject.project_id).trim();
    }
    return String(user?.active_project_id || "").trim();
  }

  async function resolveProjectIdFromAccessContext() {
    try {
      const payload = await sendLoadRequest(
        "/users/me/access-context",
        "load_access_context",
        "",
        { fallbackStatusCodes: [404, 500, 502, 503, 504] },
      );
      return normalizeValue(payload?.active_project_id);
    } catch (error) {
      return "";
    }
  }

  async function resolveProjectIdFromMemberships() {
    try {
      const payload = await sendLoadRequest(
        "/workspace-access/my-memberships",
        "load_my_memberships",
        "",
        { fallbackStatusCodes: [404, 500, 502, 503, 504] },
      );
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const active = items.find(function (item) {
        return normalizeLower(item?.status || "active") === "active" && normalizeValue(item?.project_id);
      });
      return normalizeValue(active?.project_id);
    } catch (error) {
      return "";
    }
  }

  async function resolveProjectId(user) {
    const direct = projectIdFromContext(user);
    if (direct) return direct;

    const fromAccessContext = await resolveProjectIdFromAccessContext();
    if (fromAccessContext) return fromAccessContext;

    const fromMemberships = await resolveProjectIdFromMemberships();
    if (fromMemberships) return fromMemberships;

    return "";
  }

  function resolveCurrentMemberRole(items) {
    const members = Array.isArray(items) ? items : [];
    const identity = currentUserIdentity();
    const found = members.find(function (member) {
      const memberUserId = normalizeValue(member?.user_id);
      const memberEmail = normalizeLower(member?.email);
      return (
        (identity.userId && memberUserId && identity.userId === memberUserId) ||
        (identity.email && memberEmail && identity.email === memberEmail)
      );
    });
    if (!found) return "";
    return normalizeRole(found?.member_role || "viewer");
  }

  async function resolveCurrentMemberRoleFromMemberships(projectId) {
    const normalizedProjectId = normalizeValue(projectId);
    if (!normalizedProjectId) return "";
    try {
      const payload = await sendLoadRequest(
        "/workspace-access/my-memberships",
        "load_my_memberships_role",
        normalizedProjectId,
        { fallbackStatusCodes: [404, 500, 502, 503, 504] },
      );
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const identity = currentUserIdentity();
      const found = items.find(function (item) {
        const status = normalizeLower(item?.status || "active");
        const itemProjectId = normalizeValue(item?.project_id);
        const itemUserId = normalizeValue(item?.user_id);
        const itemEmail = normalizeLower(item?.email);
        if (status !== "active") return false;
        if (!itemProjectId || itemProjectId !== normalizedProjectId) return false;
        return (
          (identity.userId && itemUserId && identity.userId === itemUserId) ||
          (identity.email && itemEmail && identity.email === itemEmail)
        );
      });
      if (!found) return "";
      return normalizeRole(found?.member_role || "viewer");
    } catch (_error) {
      return "";
    }
  }

  function applyInviteFormRoleAccess() {
    if (!inviteForm) return;
    const canManage = hasResolvedMemberRole && roleCanManageAccess(currentMemberRole);
    const roleSelect = roleNode();
    const relationshipSelect = relationshipNode();
    const privacySelect = privacyNode();
    const notesInput = noteNode();
    const emailInput = inviteForm.querySelector('input[name="email"]');
    const submitButtons = inviteForm.querySelectorAll('button[type="submit"], button[type="button"]');

    [roleSelect, relationshipSelect, privacySelect, notesInput, emailInput].forEach(function (node) {
      if (!node) return;
      node.disabled = !canManage;
    });
    submitButtons.forEach(function (button) {
      button.disabled = !canManage;
    });

    if (roleSelect) {
      Array.from(roleSelect.options || []).forEach(function (option) {
        option.disabled = !canManage || !roleCanAssign(currentMemberRole, option.value);
      });
      if (canManage && roleSelect.selectedOptions.length) {
        const selected = roleSelect.selectedOptions[0];
        if (selected && selected.disabled) {
          const firstEnabled = Array.from(roleSelect.options).find(function (option) {
            return !option.disabled;
          });
          if (firstEnabled) roleSelect.value = firstEnabled.value;
        }
      }
    }

    if (!hasResolvedMemberRole) {
      setText(
        inviteStatus,
        "Accept your invite to activate workspace access controls.",
        "info",
      );
    } else if (!canManage) {
      setText(
        inviteStatus,
        "Your role is read-only for invites and member access changes.",
        "warning",
      );
    } else if (inviteStatus && inviteStatus.dataset.state === "warning") {
      clear(inviteStatus);
    }
  }

  function inviteKeyFromQuery() {
    const params = new URLSearchParams(window.location.search);
    return String(params.get("invite_key") || "").trim();
  }

  function projectIdFromQuery() {
    const params = new URLSearchParams(window.location.search);
    return String(params.get("project_id") || "").trim();
  }

  function signinRedirectUrlWithInviteContext() {
    const inviteKey = inviteKeyFromQuery();
    const projectId = projectIdFromQuery();
    if (!inviteKey) return "signin.html";
    const params = new URLSearchParams();
    params.set("invite_key", inviteKey);
    if (projectId) params.set("project_id", projectId);
    return `signin.html?${params.toString()}`;
  }

  function isPending(invite) {
    return String(invite?.status || "").toLowerCase() === "pending";
  }

  function isExpired(invite) {
    return String(invite?.status || "").toLowerCase() === "expired";
  }

  function renderPendingCount(items) {
    if (!pendingCount) return;
    const pendingTotal = (items || []).filter(isPending).length;
    pendingCount.textContent = `${pendingTotal} pending invite${pendingTotal === 1 ? "" : "s"}.`;
  }

  function householdLoadFailureMessage(error) {
    const statusCode = Number(error?.status || 0);
    const raw = readableMessage(
      error?.detail || error?.message || error?.data || error?.responseBody,
      "",
    ).toLowerCase();
    if (!statusCode && raw.includes("network")) {
      return "We couldn’t reach the workspace access service. Please refresh and try again.";
    }
    if (statusCode === 404) {
      return "Workspace access endpoints are not available on the active API host yet.";
    }
    if (statusCode >= 500 || raw === "load failed") {
      return "Workspace access is temporarily unavailable. Please refresh and try again.";
    }
    return readableMessage(
      error?.detail || error?.message || error?.data || error?.responseBody,
      "Unable to load workspace access settings.",
    );
  }

  async function changeMemberRole(membershipId, memberRole) {
    await app.apiRequest(
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/members/${encodeURIComponent(membershipId)}/role`,
      {
        method: "POST",
        body: JSON.stringify({ member_role: memberRole }),
      },
    );
  }

  async function removeMember(membershipId) {
    await app.apiRequest(
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/members/${encodeURIComponent(membershipId)}/revoke`,
      {
        method: "POST",
      },
    );
  }

  async function resendInvite(inviteId) {
    await app.apiRequest(`/workspace-access/invites/${encodeURIComponent(inviteId)}/resend`, {
      method: "POST",
    });
  }

  async function revokeInvite(inviteId) {
    await app.apiRequest(`/workspace-access/invites/${encodeURIComponent(inviteId)}/revoke`, {
      method: "POST",
    });
  }

  function renderMembers(items) {
    if (!membersList) return;
    membersList.innerHTML = "";
    if (!Array.isArray(items) || !items.length) {
      if (membersEmpty) membersEmpty.style.display = "block";
      return;
    }
    if (membersEmpty) membersEmpty.style.display = "none";
    const canManage = roleCanManageAccess(currentMemberRole);
    const actorRank = roleRank(currentMemberRole);
    items.forEach((member) => {
      const card = document.createElement("article");
      card.className = "form-panel";

      const emailLabel = member.email || member.user_id || "Unassigned member";
      const fullName = memberDisplayName(member);
      const role = normalizeRole(member.member_role || "viewer");
      const isBillingOwner = role === "billing_owner";
      const isCoOwnerSpouse =
        role === "co_owner" && normalizeLower(member.relationship_scope) === "spouse";
      const parityNote = isBillingOwner
        ? "Primary household owner and billing authority."
        : isCoOwnerSpouse
          ? "Co-Owner (Spouse) with parity for household access management."
          : "";
      const targetRank = roleRank(role);
      const canTouchTarget = canManage && !isBillingOwner && targetRank < actorRank;
      const options = ROLE_OPTIONS.map(
        (roleCode) => {
          const disabled = !canManage || !roleCanAssign(currentMemberRole, roleCode);
          return `<option value="${roleCode}" ${roleCode === role ? "selected" : ""} ${disabled ? "disabled" : ""}>${roleLabel(roleCode)}</option>`;
        },
      ).join("");
      card.innerHTML = `
        <strong>${fullName}</strong>
        <p class="card-copy">Email: ${emailLabel}</p>
        <p class="card-copy">Role: ${roleLabel(role)}</p>
        ${parityNote ? `<p class="card-copy">${parityNote}</p>` : ""}
        <p class="card-copy">Relationship: ${relationshipLabel(member.relationship_scope || "household_member")}</p>
        <p class="card-copy">Privacy: ${privacyLabel(member.privacy_scope || "household_private")}</p>
        <p class="card-copy">Status: ${member.status || "active"}</p>
        <label>Change Role
          <select ${canTouchTarget ? "" : "disabled"} data-member-role-select>${options}</select>
        </label>
        <div class="inline-actions" style="margin-top:0.75rem;">
          <button class="btn btn-secondary" type="button" data-member-role-save ${canTouchTarget ? "" : "disabled"}>Change Role</button>
          <button class="btn btn-secondary" type="button" data-member-remove ${canTouchTarget ? "" : "disabled"}>Remove Member</button>
        </div>
      `;

      const roleSave = card.querySelector("[data-member-role-save]");
      const roleSelect = card.querySelector("[data-member-role-select]");
      const removeButton = card.querySelector("[data-member-remove]");
      if (roleSave && roleSelect && canTouchTarget) {
        roleSave.addEventListener("click", async function () {
          try {
            await changeMemberRole(member.id, roleSelect.value);
            await refreshData();
            setText(inviteStatus, "Member role updated.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to change role.", "error");
          }
        });
      }
      if (removeButton && canTouchTarget) {
        removeButton.addEventListener("click", async function () {
          try {
            await removeMember(member.id);
            await refreshData();
            setText(inviteStatus, "Member removed.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to remove member.", "error");
          }
        });
      }
      membersList.appendChild(card);
    });
  }

  function renderInvites(items) {
    if (!invitesList) return;
    invitesList.innerHTML = "";
    if (!Array.isArray(items) || !items.length) {
      if (invitesEmpty) invitesEmpty.style.display = "block";
      renderPendingCount([]);
      return;
    }
    if (invitesEmpty) invitesEmpty.style.display = "none";
    renderPendingCount(items);
    const canManageInvites = roleCanManageAccess(currentMemberRole);
    items.forEach((invite) => {
      const card = document.createElement("article");
      card.className = "form-panel";
      const canResend = canManageInvites && (isPending(invite) || isExpired(invite));
      const canRevoke = canManageInvites && (isPending(invite) || isExpired(invite));
      card.innerHTML = `
        <strong>${invite.email || "Invite"}</strong>
        <p class="card-copy">Role: ${roleLabel(invite.member_role || "viewer")}</p>
        <p class="card-copy">Relationship: ${relationshipLabel(invite.relationship_scope || "household_member")}</p>
        <p class="card-copy">Privacy: ${privacyLabel(invite.privacy_scope || "household_private")}</p>
        <p class="card-copy">Status: ${normalizeInviteStatus(invite.status || "pending")}</p>
        <p class="card-copy">Created: ${formatDateTime(invite.created_at)}</p>
        <p class="card-copy">Accepted: ${formatDateTime(invite.accepted_at)}</p>
        <p class="card-copy">Expires: ${formatDateTime(invite.expires_at)}</p>
        <div class="inline-actions" style="margin-top:0.75rem;">
          <button class="btn btn-secondary" type="button" data-invite-resend ${canResend ? "" : "disabled"}>Resend Invite</button>
          <button class="btn btn-secondary" type="button" data-invite-revoke ${canRevoke ? "" : "disabled"}>Revoke Invite</button>
        </div>
      `;

      const resendButton = card.querySelector("[data-invite-resend]");
      const revokeButton = card.querySelector("[data-invite-revoke]");
      if (resendButton && canResend) {
        resendButton.addEventListener("click", async function () {
          try {
            await resendInvite(invite.id);
            await refreshData();
            setText(inviteStatus, "Invite resent.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to resend invite.", "error");
          }
        });
      }
      if (revokeButton && canRevoke) {
        revokeButton.addEventListener("click", async function () {
          try {
            await revokeInvite(invite.id);
            await refreshData();
            setText(inviteStatus, "Invite revoked.", "success");
          } catch (error) {
            setText(inviteStatus, error.message || "Failed to revoke invite.", "error");
          }
        });
      }

      invitesList.appendChild(card);
    });
  }

  async function refreshData() {
    if (!currentProjectId) return;
    setLoadingState(true);
    setLoadErrorState("");
    try {
      const [membersPayload, invitesPayload] = await Promise.all([
        sendLoadRequest(workspaceMembersLoadPaths(currentProjectId), "load_members", currentProjectId),
        sendLoadRequest(workspaceInvitesLoadPaths(currentProjectId), "load_invites", currentProjectId),
      ]);
      const memberItems = membersPayload?.items || [];
      let resolvedRole = resolveCurrentMemberRole(memberItems);
      if (!resolvedRole) {
        resolvedRole = await resolveCurrentMemberRoleFromMemberships(currentProjectId);
      }
      currentMemberRole = resolvedRole || "viewer";
      hasResolvedMemberRole = Boolean(resolvedRole);
      applyInviteFormRoleAccess();
      renderMembers(memberItems);
      renderInvites(invitesPayload?.items || []);
      if (statusNode) {
        statusNode.textContent = `Household access is up to date for project ${currentProjectId}.`;
      }
    } catch (error) {
      const detail = householdLoadFailureMessage(error);
      setLoadErrorState(detail);
      throw error;
    } finally {
      setLoadingState(false);
    }
  }

  function selectedInviteRole() {
    if (!inviteForm) return "viewer";
    const node = roleNode();
    return String(node?.value || "viewer").trim();
  }

  async function handleInviteSubmit(event) {
    event.preventDefault();
    clear(inviteStatus);
    if (!roleCanManageAccess(currentMemberRole)) {
      setText(inviteStatus, "Your role cannot send invites from this workspace.", "error");
      return;
    }
    if (!currentProjectId) {
      setText(inviteStatus, "Select a workspace project first.", "error");
      return;
    }
    updateAutoInviteDefaults();
    const formData = new FormData(inviteForm);
    const payload = {
      email: String(formData.get("email") || "").trim(),
      member_role: selectedInviteRole(),
      relationship_scope: String(formData.get("relationship_scope") || "household_member").trim(),
      privacy_scope: String(formData.get("privacy_scope") || "household_private").trim(),
      notes: String(formData.get("notes") || "").trim(),
    };
    const invitePaths = [
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/invites`,
      // Backward-compatible singular route retained by backend legacy wiring.
      `/workspace-access/project/${encodeURIComponent(currentProjectId)}/invite`,
      `/workspace_access/project/${encodeURIComponent(currentProjectId)}/invites`,
      `/household-access/project/${encodeURIComponent(currentProjectId)}/invites`,
    ];
    try {
      let invite = null;
      let inviteMeta = null;
      let lastError = null;
      for (const invitePath of invitePaths) {
        try {
          const inviteResult = await sendInviteRequest(invitePath, payload, `invite_${payload.member_role}`);
          invite = inviteResult?.responseBody || null;
          inviteMeta = inviteResult?.meta || null;
          logInviteSuccess(`invite_${payload.member_role}`, invitePath, invite, payload, inviteMeta);
          break;
        } catch (error) {
          lastError = error;
          logInviteFailure(`invite_${payload.member_role}`, invitePath, error, payload);
          if (Number(error?.status || 0) !== 404) throw error;
        }
      }
      if (!invite) {
        throw lastError || new Error("Invite endpoint is unavailable.");
      }
      const inviteStatusValue = String(invite?.status || "").trim().toLowerCase();
      if (inviteStatusValue !== "pending") {
        throw new Error(
          `Unable to create invite (unexpected status: ${inviteStatusValue || "unknown"}). Please try again or contact support if this persists.`,
        );
      }
      const emailDeliveryFailed =
        String(invite?.email_delivery_status || "").trim().toLowerCase() === "failed";
      const successMessage = emailDeliveryFailed
        ? String(invite?.message || "Invite created, but email delivery failed.").trim()
        : "Invite created successfully and added to pending invites.";
      setText(inviteStatus, successMessage, emailDeliveryFailed ? "warning" : "success");
      inviteForm.reset();
      updateAutoInviteDefaults(true);
      await refreshData();
    } catch (error) {
      setText(
        inviteStatus,
        userInviteErrorMessage(
          error,
          "We couldn’t create that invite right now. Please verify the email and try again.",
        ),
        "error",
      );
    }
  }

  async function handleAcceptSubmit(event) {
    event.preventDefault();
    clear(acceptStatus);
    const formData = new FormData(acceptForm);
    const inviteKey = String(formData.get("invite_key") || "").trim();
    if (!inviteKey) {
      setText(acceptStatus, "Invite key is required.", "error");
      return;
    }
    try {
      const membership = await acceptInviteByKey(inviteKey);
      hydrateProjectContextFromMembership(membership);
      setText(acceptStatus, "Invite accepted. Workspace access granted.", "success");
      if (currentProjectId) {
        await refreshData();
      }
    } catch (error) {
      setText(acceptStatus, error.message || "Failed to accept invite.", "error");
    }
  }

  function projectIdFromMembership(membership) {
    const rawProjectId = membership?.project_id;
    if (rawProjectId === null || rawProjectId === undefined) return null;
    const normalized = String(rawProjectId).trim();
    return normalized === "" ? null : normalized;
  }

  async function acceptInviteByKey(inviteKey) {
    return await app.apiRequest("/workspace-access/invites/accept", {
      method: "POST",
      body: JSON.stringify({ invite_key: inviteKey }),
    });
  }

  function hydrateProjectContextFromMembership(membership) {
    const acceptedProjectId = projectIdFromMembership(membership);
    if (!currentProjectId && acceptedProjectId) {
      currentProjectId = acceptedProjectId;
    }
    if (currentProjectId && statusNode) {
      statusNode.textContent = `Managing workspace access for project ${currentProjectId}.`;
    }
  }

  function bindQuickInviteButtons() {
    if (!inviteForm) return;
    const roleSelect = roleNode();
    const relationshipSelect = relationshipNode();
    const privacySelect = privacyNode();
    const notesInput = noteNode();

    if (roleSelect) {
      roleSelect.addEventListener("change", function () {
        updateAutoInviteDefaults();
      });
    }
    if (relationshipSelect) {
      relationshipSelect.addEventListener("change", function () {
        updateAutoInviteDefaults();
      });
    }
    if (privacySelect) {
      privacySelect.addEventListener("change", function () {
        updateAutoInviteDefaults();
      });
    }
    if (notesInput) {
      notesInput.addEventListener("input", function () {
        notesInput.dataset.customized = String(Boolean(String(notesInput.value || "").trim()));
      });
    }
    if (inviteCoOwnerButton) {
      inviteCoOwnerButton.addEventListener("click", function () {
        if (roleSelect) roleSelect.value = "co_owner";
        if (relationshipSelect) relationshipSelect.value = "spouse";
        updateAutoInviteDefaults(true);
        inviteForm.requestSubmit();
      });
    }
    if (inviteFamilyButton) {
      inviteFamilyButton.addEventListener("click", function () {
        if (roleSelect) roleSelect.value = "contributor";
        updateAutoInviteDefaults(true);
        inviteForm.requestSubmit();
      });
    }
  }

  async function initialize() {
    try {
      ensureApiConfigForHouseholdAccess();
      const token = typeof app.getToken === "function" ? String(app.getToken() || "").trim() : "";
      if (!token) {
        window.location.href = signinRedirectUrlWithInviteContext();
        return;
      }

      currentUser = await sendLoadRequest("/auth/me", "load_current_user", "", {
        fallbackStatusCodes: [404, 500, 502, 503, 504],
      });
      if (typeof app.saveUser === "function") {
        app.saveUser(currentUser);
      }

      const inviteKey = inviteKeyFromQuery();
      currentProjectId = await resolveProjectId(currentUser);
      if (inviteKey) {
        setText(
          acceptLinkStatus,
          "Invite link detected. Continue below to confirm access for this signed-in account.",
          "info",
        );
      } else {
        clear(acceptLinkStatus);
      }
      if (acceptForm && inviteKey) {
        const keyInput = acceptForm.querySelector('input[name="invite_key"]');
        if (keyInput) keyInput.value = inviteKey;
      }

      bindQuickInviteButtons();
      updateAutoInviteDefaults(true);
      applyInviteFormRoleAccess();
      if (inviteForm) inviteForm.addEventListener("submit", handleInviteSubmit);
      if (acceptForm) acceptForm.addEventListener("submit", handleAcceptSubmit);

      if (!currentProjectId && inviteKey && acceptForm) {
        try {
          const membership = await acceptInviteByKey(inviteKey);
          hydrateProjectContextFromMembership(membership);
        } catch (error) {
          const statusCode = Number(error?.status);
          console.warn("[HouseholdAccess] Auto-accept invite skipped.", {
            detail: readableMessage(error?.detail || error?.message, "invite auto-accept failed"),
            status: Number.isFinite(statusCode) && statusCode > 0 ? statusCode : null,
          });
          // Keep the page interactive so invite acceptance can still be attempted manually.
        }
      }

      if (!currentProjectId) {
        if (statusNode) {
          statusNode.textContent = inviteKey
            ? "No active workspace project was detected yet. Accept the invite key below to activate workspace access."
            : "No active workspace project was detected. Open this page from your dashboard workspace.";
        }
        return;
      }

      if (statusNode && currentProjectId) {
        statusNode.textContent = `Loading household members and invite history for project ${currentProjectId}…`;
      } else if (statusNode) {
        statusNode.textContent =
          "Invite context detected. Open your invite email link or use the advanced invite code option.";
      }

      console.info("[HouseholdAccess] Invite runtime API context.", {
        resolvedApiBaseUrl:
          typeof app.getApiBaseUrl === "function" ? normalizeBaseUrl(app.getApiBaseUrl()) : "",
        resolvedApiBaseUrls: resolveInviteApiBaseUrls(),
        configuredApiBaseUrl: normalizeBaseUrl(window.TOL_CONFIG?.API_BASE_URL),
        configuredApiBaseUrls: Array.isArray(window.TOL_CONFIG?.API_BASE_URLS)
          ? window.TOL_CONFIG.API_BASE_URLS.map(normalizeBaseUrl).filter(Boolean)
          : [],
        projectId: currentProjectId,
      });

      try {
        await refreshData();
      } catch (error) {
        const statusCode = Number(error?.status || 0);
        if (statusCode === 403 && inviteKey) {
          hasResolvedMemberRole = false;
          applyInviteFormRoleAccess();
          setText(
            acceptStatus,
            "Accept this invite to activate workspace access for this project.",
            "info",
          );
          return;
        }
        throw error;
      }
    } catch (error) {
      const statusCode = Number(error?.status || 0);
      if (statusCode === 401 || (statusCode === 403 && !inviteKeyFromQuery())) {
        if (typeof app.clearSession === "function") app.clearSession();
        window.location.href = signinRedirectUrlWithInviteContext();
        return;
      }
      const detail = householdLoadFailureMessage(error);
      if (statusNode) {
        statusNode.textContent = detail;
      }
      console.error("[HouseholdAccess] Bootstrap load failed.", {
        status: statusCode || null,
        detail,
        requestUrl: String(error?.requestUrl || "").trim() || null,
        resolvedApiBaseUrl: String(error?.resolvedApiBaseUrl || "").trim() || null,
        responseBody: error?.data ?? error?.responseBody ?? null,
        projectId: currentProjectId || null,
      });
    }
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
