(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const POST_LOGIN_REDIRECT = "dashboard.html";
  const SIGNUP_POLICY_VERSION = "2026-03-26";
  const DASHBOARD_CONTEXT_STORAGE_KEY = "tol_dashboard_context_v2";
  let hasLogoutBinding = false;
  const HOUSEHOLD_LINK_PACKAGE_CODES = new Set([
    "legacy_plus",
    "family_estate_concierge",
  ]);

  if (!app) {
    console.error("auth.js requires app.js to be loaded first.");
    return;
  }
  const requiredPackageHelpers = [
    "normalizePackageCode",
    "stripMaintenanceSuffix",
    "resolvePackageLane",
    "resolvePackageDisplayName",
    "packageSupportsLinkKeys",
    "getPackageProfile",
  ];
  if (
    requiredPackageHelpers.some(function (helperName) {
      return typeof app[helperName] !== "function";
    })
  ) {
    console.error("auth.js requires package helper exports from app.js.");
    return;
  }

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function isInternalRole(user) {
    return app && typeof app.isInternalRole === "function"
      ? app.isInternalRole(user)
      : false;
  }

  function parseEmbeddedPayload(value) {
    if (typeof value !== "string") return value;

    const trimmed = value.trim();
    if (!trimmed || !["{", "["].includes(trimmed.charAt(0))) {
      return value;
    }

    try {
      return JSON.parse(trimmed);
    } catch (error) {
      return value;
    }
  }

  function collectLoginPayloads(value, seen) {
    const parsedValue = parseEmbeddedPayload(value);
    if (!parsedValue || typeof parsedValue !== "object") return [];

    const visited = seen || new Set();
    if (visited.has(parsedValue)) return [];
    visited.add(parsedValue);

    const payloads = [parsedValue];
    [
      "data",
      "detail",
      "result",
      "payload",
      "response",
      "auth",
      "login",
      "mfa",
      "totp",
      "two_factor",
      "twoFactor",
    ].forEach(function (key) {
      if (Object.prototype.hasOwnProperty.call(parsedValue, key)) {
        payloads.push(
          ...collectLoginPayloads(parsedValue[key], visited),
        );
      }
    });

    return payloads;
  }

  function getFirstResponseValue(loginData, keys) {
    const payloads = collectLoginPayloads(loginData);
    for (const payload of payloads) {
      for (const key of keys) {
        if (!Object.prototype.hasOwnProperty.call(payload, key)) continue;
        const value = parseEmbeddedPayload(payload[key]);
        if (value === null || typeof value === "undefined") continue;
        if (typeof value === "string" && !value.trim()) continue;
        return value;
      }
    }

    return null;
  }

  function getFirstResponseString(loginData, keys) {
    const value = getFirstResponseValue(loginData, keys);
    if (value === null || typeof value === "undefined") return "";
    if (typeof value === "object") return "";
    return String(value).trim();
  }

  function getAccessTokenFromResponse(loginData) {
    return getFirstResponseString(loginData, [
      "access_token",
      "accessToken",
      "token",
      "jwt",
    ]);
  }

  function getMfaChallengeToken(loginData) {
    return getFirstResponseString(loginData, [
      "mfa_challenge_token",
      "mfaChallengeToken",
      "challenge_token",
      "challengeToken",
      "mfa_token",
      "mfaToken",
      "challenge",
    ]);
  }

  function isTruthyFlag(value) {
    if (value === true || value === 1) return true;
    if (typeof value !== "string") return false;

    return ["true", "1", "yes"].includes(value.trim().toLowerCase());
  }

  function getLoginStatus(loginData) {
    return getFirstResponseString(loginData, [
      "status",
      "auth_status",
      "authStatus",
      "state",
    ])
      .trim()
      .toLowerCase();
  }

  function isMfaRequired(loginData) {
    const status = getLoginStatus(loginData);
    return Boolean(
      isTruthyFlag(
        getFirstResponseValue(loginData, [
          "mfa_required",
          "mfaRequired",
          "requires_mfa",
          "requiresMfa",
          "two_factor_required",
          "twoFactorRequired",
          "totp_required",
          "totpRequired",
          "required",
        ]),
      ) ||
        status === "mfa_required" ||
        status === "mfa_login_required" ||
        status === "mfa_enrollment_required" ||
        status === "mfa_setup_required" ||
        status === "two_factor_required" ||
        status === "totp_required",
    );
  }

  function isMfaEnrollmentRequired(loginData) {
    return Boolean(
      isTruthyFlag(
        getFirstResponseValue(loginData, [
          "mfa_enrollment_required",
          "mfaEnrollmentRequired",
          "enrollment_required",
          "enrollmentRequired",
          "requires_mfa_enrollment",
          "requiresMfaEnrollment",
          "setup_required",
          "setupRequired",
          "enroll_required",
          "enrollRequired",
        ]),
      ) ||
        ["mfa_enrollment_required", "mfa_setup_required"].includes(
          getLoginStatus(loginData),
        ),
    );
  }

  function isMfaEnrollmentChallenge(loginData) {
    return Boolean(
      isMfaRequired(loginData) &&
        isMfaEnrollmentRequired(loginData) &&
        getMfaChallengeToken(loginData),
    );
  }

  function isMfaVerificationChallenge(loginData) {
    return Boolean(
      isMfaRequired(loginData) &&
        !isMfaEnrollmentRequired(loginData) &&
        getMfaChallengeToken(loginData),
    );
  }

  function looksLikeMfaResponse(loginData) {
    const status = getLoginStatus(loginData);
    return Boolean(
      isMfaRequired(loginData) ||
        isMfaEnrollmentRequired(loginData) ||
        getMfaChallengeToken(loginData) ||
        status.includes("mfa") ||
        status.includes("totp") ||
        status.includes("two_factor"),
    );
  }

  function getErrorMessage(error) {
    const sharedParser =
      app && typeof app.getReadableErrorMessage === "function"
        ? app.getReadableErrorMessage
        : null;
    if (sharedParser) {
      const parsed = sharedParser(error, "");
      if (parsed) return parsed;
    }
    if (!error) return "Unknown error";
    if (typeof error === "string") return error;
    if (error.message) return String(error.message);
    return "Something went wrong. Please try again.";
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
    return app.normalizePackageCode(value);
  }

  function stripMaintenanceSuffix(packageCode) {
    return app.stripMaintenanceSuffix(packageCode);
  }

  function resolvePackageLane(packageCode) {
    return app.resolvePackageLane(packageCode);
  }

  function resolvePackageDisplayName(packageCode) {
    return app.resolvePackageDisplayName(packageCode);
  }

  function packageSupportsLinkKeys(packageCode) {
    return app.packageSupportsLinkKeys(packageCode);
  }

  function buildFallbackEntitlements(packageCode, packageLane) {
    const normalizedCode = stripMaintenanceSuffix(packageCode);
    const profile = app.getPackageProfile(normalizedCode);
    const lane =
      normalizeValue(packageLane) ||
      normalizeValue(profile?.package_lane) ||
      resolvePackageLane(normalizedCode);

    return {
      package_code: normalizedCode,
      package_lane: lane,
      can_upload_portraits: Boolean(profile?.can_upload_portraits ?? true),
      can_upload_verification_docs: Boolean(
        profile?.can_upload_verification_docs ?? true,
      ),
      can_build_household:
        typeof profile?.can_build_household === "boolean"
          ? profile.can_build_household
          : lane === "household" || lane === "network",
      can_build_family_tree:
        typeof profile?.can_build_family_tree === "boolean"
          ? profile.can_build_family_tree
          : lane === "household" || lane === "network",
      can_build_org_chart:
        typeof profile?.can_build_org_chart === "boolean"
          ? profile.can_build_org_chart
          : lane === "organization",
      can_link_households:
        typeof profile?.can_link_households === "boolean"
          ? profile.can_link_households
          : HOUSEHOLD_LINK_PACKAGE_CODES.has(normalizedCode),
      can_link_org_units:
        typeof profile?.can_link_org_units === "boolean"
          ? profile.can_link_org_units
          : lane === "organization",
      can_use_viewer: Boolean(profile?.can_use_viewer ?? true),
      can_use_narration: Boolean(profile?.can_use_narration ?? false),
      can_use_lineage_certificate:
        typeof profile?.can_use_lineage_certificate === "boolean"
          ? profile.can_use_lineage_certificate
          : lane === "household" || lane === "network",
      can_open_family_intake:
        typeof profile?.can_open_family_intake === "boolean"
          ? profile.can_open_family_intake
          : lane === "household" || lane === "network",
      can_open_org_intake:
        typeof profile?.can_open_org_intake === "boolean"
          ? profile.can_open_org_intake
          : lane === "organization",
      can_use_link_keys: packageSupportsLinkKeys(normalizedCode),
      can_manage_link_keys: Boolean(
        profile?.can_manage_link_keys ?? packageSupportsLinkKeys(normalizedCode),
      ),
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

  function getFamilyIdFromSubmission(record) {
    if (!record || typeof record !== "object") return "";

    const rawId =
      record.family_root_id ||
      record.familyRootId ||
      record.family_id ||
      record.familyId;

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

  function getWorkspaceHintsFromUser(user) {
    return {
      projectId: String(
        user?.active_project_id || user?.activeProjectId || "",
      ).trim(),
      familyId: String(
        user?.active_family_id || user?.activeFamilyId || "",
      ).trim(),
    };
  }

  function mergeWorkspaceSelectionHints(primary, fallback) {
    const primaryHints =
      primary && typeof primary === "object"
        ? {
            projectId: String(
              primary.projectId ||
                primary.project_id ||
                primary.active_project_id ||
                "",
            ).trim(),
            familyId: String(
              primary.familyId ||
                primary.family_id ||
                primary.active_family_id ||
                "",
            ).trim(),
          }
        : { projectId: "", familyId: "" };
    const fallbackHints =
      fallback && typeof fallback === "object"
        ? {
            projectId: String(
              fallback.projectId ||
                fallback.project_id ||
                fallback.active_project_id ||
                "",
            ).trim(),
            familyId: String(
              fallback.familyId ||
                fallback.family_id ||
                fallback.active_family_id ||
                "",
            ).trim(),
          }
        : { projectId: "", familyId: "" };

    return {
      projectId: primaryHints.projectId || fallbackHints.projectId,
      familyId: primaryHints.familyId || fallbackHints.familyId,
    };
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

  async function completeAuthenticatedLogin(loginData) {
    const token = getAccessTokenFromResponse(loginData);

    if (!token) {
      throw new Error("Login succeeded but no access token was returned.");
    }

    clearCachedDashboardContext();
    app.saveToken(token);

    const me = await fetchCurrentUserWithToken(token);
    app.saveUser(me);

    return { status: "authenticated", loginData, me };
  }

  async function handleLogin(email, password) {
    const loginData = await app.apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    if (getAccessTokenFromResponse(loginData)) {
      return await completeAuthenticatedLogin(loginData);
    }

    if (isMfaEnrollmentChallenge(loginData)) {
      clearCachedDashboardContext();
      app.clearSession();
      return {
        status: "mfa_enrollment_required",
        loginData,
        mfaChallengeToken: getMfaChallengeToken(loginData),
      };
    }

    if (isMfaVerificationChallenge(loginData)) {
      clearCachedDashboardContext();
      app.clearSession();
      return {
        status: "mfa_required",
        loginData,
        mfaChallengeToken: getMfaChallengeToken(loginData),
      };
    }

    if (looksLikeMfaResponse(loginData)) {
      throw new Error(
        "Secure verification could not be started. Please try signing in again.",
      );
    }

    throw new Error(
      "Secure sign-in could not be completed. Please refresh and try again.",
    );
  }

  async function beginMfaEnrollment(mfaChallengeToken) {
    return await app.apiRequest("/auth/mfa/enroll/begin", {
      method: "POST",
      body: JSON.stringify({ mfa_challenge_token: mfaChallengeToken }),
    });
  }

  async function verifyMfaEnrollment(setupToken, code) {
    const loginData = await app.apiRequest("/auth/mfa/enroll/verify", {
      method: "POST",
      body: JSON.stringify({ setup_token: setupToken, code }),
    });

    return await completeAuthenticatedLogin(loginData);
  }

  async function verifyMfaLogin(mfaChallengeToken, code, recoveryCode) {
    const payload = { mfa_challenge_token: mfaChallengeToken };
    if (code) {
      payload.code = code;
    }
    if (recoveryCode) {
      payload.recovery_code = recoveryCode;
    }

    const loginData = await app.apiRequest("/auth/mfa/login/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    return await completeAuthenticatedLogin(loginData);
  }

  function getInviteContextFromQuery() {
    try {
      const params = new URLSearchParams(window.location.search);
      return {
        inviteKey: String(params.get("invite_key") || "").trim(),
        projectId: String(params.get("project_id") || "").trim(),
      };
    } catch (_error) {
      return { inviteKey: "", projectId: "" };
    }
  }

  function buildInviteContextQueryString(context) {
    const inviteKey = String(context?.inviteKey || "").trim();
    if (!inviteKey) return "";
    const params = new URLSearchParams();
    params.set("invite_key", inviteKey);
    const projectId = String(context?.projectId || "").trim();
    if (projectId) params.set("project_id", projectId);
    return params.toString();
  }

  function preserveInviteContextOnAuthLinks() {
    const inviteQueryString = buildInviteContextQueryString(
      getInviteContextFromQuery(),
    );
    if (!inviteQueryString) return;

    document.querySelectorAll("a[href]").forEach(function (link) {
      const rawHref = String(link.getAttribute("href") || "").trim();
      if (
        !rawHref ||
        rawHref.startsWith("#") ||
        rawHref.startsWith("mailto:") ||
        rawHref.startsWith("tel:")
      ) {
        return;
      }

      let parsed;
      try {
        parsed = new URL(rawHref, window.location.href);
      } catch (_error) {
        return;
      }

      const filename = String(parsed.pathname.split("/").pop() || "").toLowerCase();
      if (
        filename !== "signin.html" &&
        filename !== "signup.html" &&
        filename !== "household-access.html"
      ) {
        return;
      }

      const rewrittenPath = String(parsed.pathname.split("/").pop() || filename);
      const rewrittenSearch = `?${inviteQueryString}`;
      link.setAttribute("href", `${rewrittenPath}${rewrittenSearch}${parsed.hash}`);
    });
  }

  function getPostLoginRedirect() {
    const inviteQueryString = buildInviteContextQueryString(
      getInviteContextFromQuery(),
    );
    if (!inviteQueryString) {
      return POST_LOGIN_REDIRECT;
    }
    return `household-access.html?${inviteQueryString}`;
  }

  function redirectAfterLogin() {
    window.location.href = getPostLoginRedirect();
  }

  function getRoleSignals(user) {
    const roleAliases = {
      root_admin: "super_admin",
      platform_admin: "super_admin",
      executive_technology: "super_admin",
      operations: "operations_admin",
      finance: "finance_admin",
      marketing: "marketing_admin",
    };
    const normalizeRole = function (value) {
      const normalized = normalizeValue(value);
      return roleAliases[normalized] || normalized;
    };
    return [
      normalizeRole(user?.access_tier),
      normalizeRole(user?.department_role),
      normalizeRole(user?.role),
    ].filter(Boolean);
  }

  function getBusinessTitle(user) {
    const explicitTitle = String(user?.business_title || "").trim();
    if (explicitTitle) return explicitTitle;

    const signals = getRoleSignals(user);
    if (
      signals.includes("super_admin") ||
      signals.includes("root_admin") ||
      signals.includes("platform_admin") ||
      signals.includes("executive_technology")
    ) {
      return "CEO / Super Admin";
    }
    if (signals.includes("finance_admin")) {
      return "CFO";
    }
    if (signals.includes("operations_admin")) {
      return "COO";
    }
    if (signals.includes("marketing_admin")) {
      return "CMO";
    }
    return "Internal Admin";
  }

  function isPrototypeCustomer(user) {
    return (
      normalizeValue(user?.account_type) === "prototype_customer" ||
      normalizeValue(user?.prototype_key) === "genesis_prototype" ||
      normalizeValue(user?.email) === "larry.frontend.test2@tomboflight.com"
    );
  }

  function getCustomerAccountLabel(user, packageName) {
    const packageLabel = String(packageName || "").trim();
    const baseLabel = isPrototypeCustomer(user)
      ? "Genesis Prototype Customer"
      : "Customer Account";
    return packageLabel ? `${baseLabel} - ${packageLabel}` : baseLabel;
  }

  function getAccountDisplayLabel(user) {
    if (isInternalRole(user)) {
      return getBusinessTitle(user);
    }
    return getCustomerAccountLabel(user);
  }

  function populateUserFields(user, refs) {
    if (!user || !refs) return;

    if (refs.userName) refs.userName.textContent = user.full_name || "User";
    if (refs.userEmail) refs.userEmail.textContent = user.email || "";
    if (refs.userRole) refs.userRole.textContent = getAccountDisplayLabel(user);
  }

  function updateCustomerProfileFields(context, refs) {
    if (!context || !refs || !refs.userRole || isInternalRole(context.user)) {
      return;
    }

    refs.userRole.textContent = getCustomerAccountLabel(
      context.user,
      context.packageName,
    );
  }

  async function fetchOrders() {
    const payload = await app.apiRequest("/orders/my-orders", {
      method: "GET",
    });
    return toArray(payload);
  }

  async function fetchLatestIntakeSubmissionSafe() {
    try {
      return await app.apiRequest("/intake-submissions/my-latest", {
        method: "GET",
      });
    } catch (error) {
      const message = getErrorMessage(error).toLowerCase();

      if (
        message.includes("no intake submissions found") ||
        message.includes("404")
      ) {
        return null;
      }

      throw error;
    }
  }

  async function fetchProjectEntitlements() {
    const payload = await app.apiRequest("/project-entitlements/my-active", {
      method: "GET",
    });
    return toArray(payload);
  }

  async function fetchWorkspaceMemberships() {
    const payload = await app.apiRequest("/workspace-access/my-memberships", {
      method: "GET",
    });
    return toArray(payload);
  }

  async function fetchProjectEntitlementByProjectId(projectId) {
    const normalizedProjectId = String(projectId || "").trim();
    if (!normalizedProjectId) return null;

    try {
      return await app.apiRequest(
        `/project-entitlements/project/${encodeURIComponent(normalizedProjectId)}`,
        {
          method: "GET",
        },
      );
    } catch (error) {
      const message = getErrorMessage(error).toLowerCase();
      if (
        message.includes("project entitlement not found") ||
        message.includes("not authorized") ||
        message.includes("404") ||
        message.includes("403")
      ) {
        return null;
      }
      throw error;
    }
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
    let hints = mergeWorkspaceSelectionHints(
      options,
      getWorkspaceHintsFromUser(user),
    );

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

    if (!hints.projectId) {
      try {
        const memberships = await fetchWorkspaceMemberships();
        const activeMemberships = sortByMostRecent(
          (Array.isArray(memberships) ? memberships : []).filter(function (item) {
            return normalizeValue(item?.status || "active") === "active";
          }),
        );
        const membershipProjectId = String(
          activeMemberships[0]?.project_id || activeMemberships[0]?.projectId || "",
        ).trim();
        if (membershipProjectId) {
          hints = mergeWorkspaceSelectionHints(hints, { projectId: membershipProjectId });
        }
      } catch (error) {
        // Ignore membership lookup failures so dashboard context can still load.
      }
    }

    if (hints.projectId) {
      const alreadyIncludesHintedProject = entitlements.some(function (item) {
        return getProjectIdFromRecord(item) === hints.projectId;
      });
      if (!alreadyIncludesHintedProject) {
        try {
          const hintedEntitlement = await fetchProjectEntitlementByProjectId(
            hints.projectId,
          );
          if (hintedEntitlement && hasKnownPackage(hintedEntitlement)) {
            entitlements = [hintedEntitlement].concat(entitlements);
          }
        } catch (error) {
          // Ignore supplemental entitlement lookup so dashboard context can still load.
        }
      }
    }

    let currentWorkspace = resolveCurrentWorkspace(
      orders,
      entitlements,
      projects,
      hints,
    );
    const paidOrder = currentWorkspace?.paidOrder || getPaidOrder(orders);
    const activeEntitlement =
      currentWorkspace?.activeEntitlement || getActiveEntitlement(entitlements);
    let activeProject =
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

    const shouldBackfillFamilyId =
      (packageLane === "household" || packageLane === "network") &&
      !getFamilyIdFromRecord(activeProject);

    if (shouldBackfillFamilyId) {
      try {
        const latestSubmission = await fetchLatestIntakeSubmissionSafe();
        const submissionFamilyId = getFamilyIdFromSubmission(latestSubmission);
        const submissionProjectId = String(
          latestSubmission?.project_id || latestSubmission?.projectId || "",
        ).trim();
        const activeProjectId = getProjectIdFromRecord(activeProject);

        if (
          submissionFamilyId &&
          (!submissionProjectId ||
            !activeProjectId ||
            submissionProjectId === activeProjectId)
        ) {
          activeProject = Object.assign({}, activeProject || {}, {
            family_id: submissionFamilyId,
          });

          if (currentWorkspace?.activeProject) {
            currentWorkspace = Object.assign({}, currentWorkspace, {
              activeProject: Object.assign(
                {},
                currentWorkspace.activeProject,
                {
                  family_id: submissionFamilyId,
                },
              ),
            });
          }
        }
      } catch (error) {
        // Ignore supplemental intake lookups so dashboard context can still load.
      }
    }

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
    const hints = mergeWorkspaceSelectionHints(
      getWorkspaceSelectionHints(),
      getWorkspaceHintsFromUser(user),
    );
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

      if (password.length < 12) {
        app.setStatus(
          statusNode,
          "Password must be at least 12 characters long.",
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

        const loginResult = await handleLogin(email, password);
        if (loginResult.status !== "authenticated") {
          throw new Error(
            "Account created. Please sign in to complete secure verification.",
          );
        }
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
    const enrollmentPanel = document.querySelector(
      "[data-mfa-enrollment-panel]",
    );
    const enrollmentSetup = document.querySelector(
      "[data-mfa-enrollment-setup]",
    );
    const enrollmentVerifyArea = document.querySelector(
      "[data-mfa-enrollment-verify-area]",
    );
    const enrollmentForm = document.querySelector(
      "[data-mfa-enrollment-form]",
    );
    const enrollmentStatus = document.querySelector(
      "[data-mfa-enrollment-status]",
    );
    const enrollmentSubmitBtn =
      enrollmentForm && enrollmentForm.querySelector("[data-submit-btn]");
    const enrollmentSecretNode = document.querySelector(
      "[data-mfa-enrollment-secret]",
    );
    const enrollmentOtpauthNode = document.querySelector(
      "[data-mfa-otpauth-url]",
    );
    const enrollmentOtpauthLink = document.querySelector(
      "[data-mfa-otpauth-link]",
    );
    const backupCodesPanel = document.querySelector(
      "[data-mfa-backup-codes-panel]",
    );
    const backupCodesList = document.querySelector("[data-mfa-backup-codes]");
    const continueDashboardBtn = document.querySelector(
      "[data-mfa-continue-dashboard]",
    );
    const verificationPanel = document.querySelector(
      "[data-mfa-verification-panel]",
    );
    const verificationForm = document.querySelector(
      "[data-mfa-verification-form]",
    );
    const verificationStatus = document.querySelector(
      "[data-mfa-verification-status]",
    );
    const verificationSubmitBtn =
      verificationForm && verificationForm.querySelector("[data-submit-btn]");
    const resetButtons = document.querySelectorAll("[data-mfa-reset]");
    let activeMfaChallengeToken = "";
    let activeMfaSetupToken = "";

    function setHidden(element, hidden) {
      if (element) {
        element.hidden = Boolean(hidden);
      }
    }

    function normalizeMfaEntry(value) {
      return String(value || "")
        .trim()
        .replace(/\s+/g, "");
    }

    function focusFirstInput(container) {
      if (!container) return;
      const input = container.querySelector("input, textarea, button, a");
      if (input && typeof input.focus === "function") {
        input.focus();
      }
    }

    function setBusy(button, busy, busyLabel, defaultLabel) {
      if (!button) return;
      button.disabled = Boolean(busy);
      button.textContent = busy ? busyLabel : defaultLabel;
    }

    function setMfaFlowVisible(flowName) {
      const isEnrollment = flowName === "enrollment";
      const isVerification = flowName === "verification";
      form.hidden = isEnrollment || isVerification;
      setHidden(enrollmentPanel, !isEnrollment);
      setHidden(verificationPanel, !isVerification);
      app.clearStatus(statusNode);
    }

    function resetMfaFlow() {
      activeMfaChallengeToken = "";
      activeMfaSetupToken = "";
      form.hidden = false;
      if (typeof form.reset === "function") {
        form.reset();
      }
      if (enrollmentForm && typeof enrollmentForm.reset === "function") {
        enrollmentForm.reset();
      }
      if (verificationForm && typeof verificationForm.reset === "function") {
        verificationForm.reset();
      }
      if (enrollmentSecretNode) {
        enrollmentSecretNode.textContent = "";
      }
      if (enrollmentOtpauthNode) {
        enrollmentOtpauthNode.value = "";
      }
      if (enrollmentOtpauthLink) {
        enrollmentOtpauthLink.removeAttribute("href");
      }
      if (backupCodesList) {
        backupCodesList.innerHTML = "";
      }
      setHidden(enrollmentPanel, true);
      setHidden(verificationPanel, true);
      setHidden(enrollmentSetup, false);
      setHidden(enrollmentVerifyArea, true);
      setHidden(backupCodesPanel, true);
      app.clearStatus(statusNode);
      app.clearStatus(enrollmentStatus);
      app.clearStatus(verificationStatus);
      setBusy(submitBtn, false, "Signing In...", defaultSubmitLabel);
      setBusy(
        enrollmentSubmitBtn,
        false,
        "Verifying...",
        "Activate MFA",
      );
      setBusy(
        verificationSubmitBtn,
        false,
        "Verifying...",
        "Verify and Enter Portal",
      );
    }

    async function startMfaEnrollment(mfaChallengeToken) {
      activeMfaChallengeToken = mfaChallengeToken;
      activeMfaSetupToken = "";
      setMfaFlowVisible("enrollment");
      setHidden(enrollmentSetup, false);
      setHidden(enrollmentVerifyArea, true);
      setHidden(backupCodesPanel, true);
      app.setStatus(
        enrollmentStatus,
        "Preparing your authenticator setup...",
        "info",
      );

      try {
        const setupData = await beginMfaEnrollment(activeMfaChallengeToken);
        activeMfaSetupToken = String(setupData?.setup_token || "").trim();
        if (!activeMfaSetupToken) {
          throw new Error("MFA setup could not be started.");
        }

        const secret = String(setupData?.secret || "").trim();
        const otpauthUrl = String(setupData?.otpauth_url || "").trim();
        if (enrollmentSecretNode) {
          enrollmentSecretNode.textContent = secret || "Unavailable";
        }
        if (enrollmentOtpauthNode) {
          enrollmentOtpauthNode.value = otpauthUrl;
        }
        if (enrollmentOtpauthLink && otpauthUrl) {
          enrollmentOtpauthLink.href = otpauthUrl;
        }

        setHidden(enrollmentVerifyArea, false);
        app.setStatus(
          enrollmentStatus,
          "Add this key to your authenticator app, then enter the first code it creates.",
          "info",
        );
        focusFirstInput(enrollmentVerifyArea);
      } catch (error) {
        app.setStatus(
          enrollmentStatus,
          getErrorMessage(error) || "MFA enrollment could not be started.",
          "error",
        );
      }
    }

    function startMfaVerification(mfaChallengeToken) {
      activeMfaChallengeToken = mfaChallengeToken;
      setMfaFlowVisible("verification");
      app.setStatus(
        verificationStatus,
        "Enter an authenticator code or one recovery code to continue.",
        "info",
      );
      focusFirstInput(verificationPanel);
    }

    function showBackupCodes(backupCodes) {
      const codes = Array.isArray(backupCodes) ? backupCodes : [];
      if (backupCodesList) {
        backupCodesList.innerHTML = "";
        if (codes.length) {
          codes.forEach(function (code) {
            const item = document.createElement("li");
            item.textContent = code;
            backupCodesList.appendChild(item);
          });
        } else {
          const item = document.createElement("li");
          item.textContent =
            "No backup codes were returned for this session.";
          backupCodesList.appendChild(item);
        }
      }

      setHidden(enrollmentSetup, true);
      setHidden(enrollmentVerifyArea, true);
      setHidden(backupCodesPanel, false);
      app.setStatus(
        enrollmentStatus,
        "MFA is active. Keep these recovery codes before opening the dashboard.",
        "success",
      );
      if (continueDashboardBtn && typeof continueDashboardBtn.focus === "function") {
        continueDashboardBtn.focus();
      }
    }

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
        const loginResult = await handleLogin(email, password);
        if (loginResult.status === "authenticated") {
          app.setStatus(statusNode, "Portal access granted.", "success");
          redirectAfterLogin();
          return;
        }

        if (loginResult.status === "mfa_enrollment_required") {
          await startMfaEnrollment(loginResult.mfaChallengeToken);
          return;
        }

        if (loginResult.status === "mfa_required") {
          startMfaVerification(loginResult.mfaChallengeToken);
          return;
        }

        throw new Error("Login could not be completed.");
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

    if (enrollmentForm) {
      enrollmentForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        app.clearStatus(enrollmentStatus);

        if (
          typeof enrollmentForm.reportValidity === "function" &&
          !enrollmentForm.reportValidity()
        ) {
          return;
        }

        const formData = new FormData(enrollmentForm);
        const code = normalizeMfaEntry(formData.get("code"));

        if (!activeMfaSetupToken) {
          app.setStatus(
            enrollmentStatus,
            "MFA setup has expired. Please sign in again.",
            "error",
          );
          return;
        }

        if (!code) {
          app.setStatus(
            enrollmentStatus,
            "Enter the code from your authenticator app.",
            "error",
          );
          return;
        }

        setBusy(enrollmentSubmitBtn, true, "Verifying...", "Activate MFA");

        try {
          const result = await verifyMfaEnrollment(activeMfaSetupToken, code);
          showBackupCodes(result.loginData?.backup_codes);
        } catch (error) {
          app.setStatus(
            enrollmentStatus,
            getErrorMessage(error) || "MFA enrollment could not be verified.",
            "error",
          );
        } finally {
          setBusy(enrollmentSubmitBtn, false, "Verifying...", "Activate MFA");
        }
      });
    }

    if (verificationForm) {
      verificationForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        app.clearStatus(verificationStatus);

        if (
          typeof verificationForm.reportValidity === "function" &&
          !verificationForm.reportValidity()
        ) {
          return;
        }

        const formData = new FormData(verificationForm);
        const code = normalizeMfaEntry(formData.get("code"));
        const recoveryCode = normalizeMfaEntry(formData.get("recovery_code"));

        if (!activeMfaChallengeToken) {
          app.setStatus(
            verificationStatus,
            "MFA verification has expired. Please sign in again.",
            "error",
          );
          return;
        }

        if (!code && !recoveryCode) {
          app.setStatus(
            verificationStatus,
            "Enter an authenticator code or recovery code.",
            "error",
          );
          return;
        }

        if (code && recoveryCode) {
          app.setStatus(
            verificationStatus,
            "Use either an authenticator code or a recovery code.",
            "error",
          );
          return;
        }

        setBusy(
          verificationSubmitBtn,
          true,
          "Verifying...",
          "Verify and Enter Portal",
        );

        try {
          await verifyMfaLogin(activeMfaChallengeToken, code, recoveryCode);
          app.setStatus(verificationStatus, "Portal access granted.", "success");
          redirectAfterLogin();
        } catch (error) {
          app.setStatus(
            verificationStatus,
            getErrorMessage(error) || "MFA verification failed.",
            "error",
          );
        } finally {
          setBusy(
            verificationSubmitBtn,
            false,
            "Verifying...",
            "Verify and Enter Portal",
          );
        }
      });
    }

    resetButtons.forEach(function (button) {
      button.addEventListener("click", resetMfaFlow);
    });

    if (continueDashboardBtn) {
      continueDashboardBtn.addEventListener("click", redirectAfterLogin);
    }
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
      // Pre-apply admin portal mode from cached user so CSS can hide customer
      // sections before [data-auth-required] is revealed, preventing FOUC.
      if (isInternalRole(savedUser)) {
        document.body.dataset.portalMode = "admin";
      }
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

      // Publish the resolved user for co-loaded scripts (e.g. dashboard-admin.js)
      // so they do not need to make a duplicate /auth/me request.
      window.TOLResolvedUser = me;
      window.dispatchEvent(
        new CustomEvent("tol:user-resolved", { detail: { user: me } }),
      );

      if (isInternalRole(me)) {
        document.body.dataset.portalMode = "admin";
        if (authRequired) authRequired.style.display = "block";
        app.setStatus(
          statusNode,
          "You are signed in to the Tomb of Light internal operations portal.",
          "success",
        );
        return;
      }

      // Customer path: reveal portal content after confirming role.
      document.body.dataset.portalMode = "customer";
      if (authRequired) authRequired.style.display = "block";
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
      updateCustomerProfileFields(context, refs);
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
    const portraitUploadPages = new Set(["portrait-upload.html"]);
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
      !portraitUploadPages.has(page) &&
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
        window.location.href = "dashboard.html?admin_workspace=1";
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

      if (portraitUploadPages.has(page) && !resolved.can_upload_portraits) {
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
    if (hasLogoutBinding) return;
    hasLogoutBinding = true;

    document.addEventListener("click", function (event) {
      const button = event.target.closest("[data-logout-btn]");
      if (!button) return;

      event.preventDefault();
      if (button.disabled) return;
      button.disabled = true;

      // Clear the local session immediately so the redirect is not blocked by
      // network latency or a backend timeout (the API call can take up to 15 s).
      try {
        if (app && typeof app.clearSession === "function") {
          app.clearSession();
        }
      } catch (_error) {
        // Best-effort local cleanup.
      }

      clearCachedDashboardContext();

      // Notify the backend in the background — do not await.  The local session
      // is already cleared, so the user is logged out regardless of the outcome.
      if (app && typeof app.logoutUser === "function") {
        app.logoutUser().catch(function (err) {
          console.warn("Background logout request failed:", err);
        });
      }

      window.location.href = "signin.html";
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
    preserveInviteContextOnAuthLinks();
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
    fetchProjectEntitlementByProjectId,
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
