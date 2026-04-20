(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

  const DEFAULT_LOCAL_API_BASE_URLS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://[::1]:8000",
  ];
  const DEFAULT_LIVE_API_BASE_URL = "https://tomboflight-api.onrender.com";
  const DEFAULT_LIVE_API_BASE_URLS = [
    DEFAULT_LIVE_API_BASE_URL,
    "https://api.tomboflight.com",
  ];

  const TOKEN_KEY = "tol_access_token";
  const USER_KEY = "tol_user";
  const COOKIE_CHOICE_KEY = "tol_cookie_choice";
  const PENDING_CHECKOUT_KEY = "tol_pending_checkout";
  const API_BASE_URL_STORAGE_KEY = "tol_api_base_url";
  const API_REQUEST_TIMEOUT_MS = 15000;

  const ADDON_OR_EXTRA_SLUGS = new Set([
    "extra_upload_pack",
    "extra_storage",
    "portrait_polish",
    "tribute_narration",
    "extra_mapped_person",
    "extra_zoom_layer",
    "additional_narration_minute",
    "on_site_photo_scanning",
    "extra_linked_household",
    "extra_branch",
    "white_glove_archive_support",
    "extra_org_node",
    "extra_org_level",
    "extra_admin_seat",
    "command_report_addon",
  ]);

  const PACKAGE_CODE_ALIASES = {
    "legacy-snapshot": "legacy_snapshot",
    legacy_snapshot: "legacy_snapshot",
    "legacy snapshot": "legacy_snapshot",
    "legacy-portrait-intro": "legacy_portrait_intro",
    legacy_portrait_intro: "legacy_portrait_intro",
    "legacy portrait intro": "legacy_portrait_intro",
    "digital-legacy-portrait": "digital_legacy_portrait",
    digital_legacy_portrait: "digital_legacy_portrait",
    "digital legacy portrait": "digital_legacy_portrait",
    "starter-family-tree": "household_foundation",
    starter_family_tree: "household_foundation",
    "starter family tree": "household_foundation",
    "household-foundation": "household_foundation",
    household_foundation: "household_foundation",
    "household foundation": "household_foundation",
    "heirloom-legacy-tree": "heirloom_legacy_tree",
    heirloom_legacy_tree: "heirloom_legacy_tree",
    "heirloom legacy tree": "heirloom_legacy_tree",
    "legacy-plus": "legacy_plus",
    legacy_plus: "legacy_plus",
    "legacy plus": "legacy_plus",
    "family-estate-concierge": "family_estate_concierge",
    family_estate_concierge: "family_estate_concierge",
    "family estate concierge": "family_estate_concierge",
    "command-structure-network": "command_structure_network",
    command_structure_network: "command_structure_network",
    "command structure network": "command_structure_network",
  };

  const PACKAGE_PROFILES = {
    legacy_snapshot: {
      display_name: "Legacy Snapshot",
      package_lane: "portrait",
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: false,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
    legacy_portrait_intro: {
      display_name: "Legacy Portrait Intro",
      package_lane: "portrait",
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: false,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
    digital_legacy_portrait: {
      display_name: "Digital Legacy Portrait",
      package_lane: "portrait",
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    household_foundation: {
      display_name: "Household Foundation",
      package_lane: "household",
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    heirloom_legacy_tree: {
      display_name: "Heirloom Legacy Tree",
      package_lane: "household",
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    legacy_plus: {
      display_name: "Legacy Plus",
      package_lane: "household",
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: true,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    family_estate_concierge: {
      display_name: "Family Estate Concierge",
      package_lane: "network",
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: true,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    command_structure_network: {
      display_name: "Command Structure Network",
      package_lane: "organization",
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: true,
      can_link_households: false,
      can_link_org_units: true,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: true,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
  };

  function normalizePackageCode(packageCode) {
    const normalized = String(packageCode || "")
      .trim()
      .toLowerCase();
    return PACKAGE_CODE_ALIASES[normalized] || normalized;
  }

  function stripMaintenanceSuffix(packageCode) {
    return normalizePackageCode(packageCode)
      .replace(/_maintenance_monthly$/, "")
      .replace(/_maintenance_yearly$/, "");
  }

  function getPackageProfile(packageCode) {
    const normalized = stripMaintenanceSuffix(packageCode);
    const profile = PACKAGE_PROFILES[normalized];
    return profile ? Object.assign({ package_code: normalized }, profile) : null;
  }

  function resolvePackageLane(packageCode) {
    const profile = getPackageProfile(packageCode);
    return profile && profile.package_lane ? profile.package_lane : "unknown";
  }

  function resolvePackageDisplayName(packageCode) {
    const profile = getPackageProfile(packageCode);
    if (profile && profile.display_name) return profile.display_name;
    const normalized = stripMaintenanceSuffix(packageCode);
    return normalized
      ? normalized.replaceAll("_", " ").replace(/\b\w/g, function (char) {
          return char.toUpperCase();
        })
      : "Package";
  }

  function packageSupportsLinkKeys(packageCode) {
    const profile = getPackageProfile(packageCode);
    return Boolean(profile && profile.can_use_link_keys);
  }

  // Canonical set of internal-role values shared across all modules.
  // Any module needing role gating should call app.isInternalRole() rather
  // than maintaining its own copy of this set.
  const INTERNAL_ROLE_KEYS = new Set([
    "super_admin",
    "executive_tech_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
  ]);

  const INTERNAL_ROLE_ALIASES = {
    superadmin: "super_admin",
    root_admin: "super_admin",
    platform_admin: "super_admin",
    executive_technology: "executive_tech_admin",
    executive_tech_admin: "executive_tech_admin",
    "executive-tech-admin": "executive_tech_admin",
    cto_admin: "executive_tech_admin",
    cfo_admin: "finance_admin",
    cmo_admin: "marketing_admin",
    coo_admin: "operations_admin",
    operations: "operations_admin",
    finance: "finance_admin",
    marketing: "marketing_admin",
  };

  function isInternalRole(user) {
    if (!user || typeof user !== "object") return false;
    const roleCodes = Array.isArray(user.role_codes) ? user.role_codes : [];
    return [
      String(user.role || "").trim().toLowerCase(),
      String(user.access_tier || "").trim().toLowerCase(),
      String(user.department_role || "").trim().toLowerCase(),
      ...roleCodes.map(function (value) {
        return String(value || "").trim().toLowerCase();
      }),
    ].some(function (v) {
      const normalized = INTERNAL_ROLE_ALIASES[v] || v;
      return normalized && INTERNAL_ROLE_KEYS.has(normalized);
    });
  }

  function isLocalApp() {
    return LOCAL_HOSTS.has(window.location.hostname);
  }

  function uniqueNonEmptyValues(values) {
    return Array.from(
      new Set(
        (Array.isArray(values) ? values : [])
          .map(function (value) {
            return typeof value === "string" ? value.trim().replace(/\/+$/, "") : "";
          })
          .filter(Boolean),
      ),
    );
  }

  function isLikelyApiBaseUrl(value) {
    try {
      const parsed = new URL(String(value || "").trim());
      return parsed.protocol === "https:" || parsed.protocol === "http:";
    } catch (_error) {
      return false;
    }
  }

  function isFrontendOriginBaseUrl(value) {
    try {
      const parsed = new URL(String(value || "").trim());
      return parsed.origin === window.location.origin;
    } catch (_error) {
      return false;
    }
  }

  function getConfiguredApiBaseUrls() {
    const configuredList =
      window.TOL_CONFIG && Array.isArray(window.TOL_CONFIG.API_BASE_URLS)
        ? window.TOL_CONFIG.API_BASE_URLS
        : [];
    const configuredSingle =
      window.TOL_CONFIG && typeof window.TOL_CONFIG.API_BASE_URL === "string"
        ? window.TOL_CONFIG.API_BASE_URL
        : "";

    const configured = uniqueNonEmptyValues([
      configuredSingle,
      ...configuredList,
    ]).filter(function (candidate) {
      return isLikelyApiBaseUrl(candidate);
    });
    const backendApiBaseUrls = configured.filter(function (candidate) {
      return !isFrontendOriginBaseUrl(candidate);
    });
    if (backendApiBaseUrls.length) {
      if (isLocalApp()) {
        return backendApiBaseUrls;
      }
      return uniqueNonEmptyValues([
        ...backendApiBaseUrls,
        ...DEFAULT_LIVE_API_BASE_URLS,
      ]);
    }

    if (isLocalApp()) {
      const localHost = String(window.location.hostname || "").toLowerCase();
      const preferredLocalApiBaseUrl =
        localHost === "localhost"
          ? "http://localhost:8000"
          : localHost === "::1" || localHost === "[::1]"
          ? "http://[::1]:8000"
          : "http://127.0.0.1:8000";
      return uniqueNonEmptyValues([
        preferredLocalApiBaseUrl,
        ...DEFAULT_LOCAL_API_BASE_URLS,
      ]);
    }

    return DEFAULT_LIVE_API_BASE_URLS.slice();
  }

  function getSavedApiBaseUrl() {
    try {
      const value = sessionStorage.getItem(API_BASE_URL_STORAGE_KEY);
      return typeof value === "string" ? value.trim().replace(/\/+$/, "") : "";
    } catch (_error) {
      return "";
    }
  }

  function saveApiBaseUrl(value) {
    try {
      if (typeof value === "string" && value.trim()) {
        sessionStorage.setItem(
          API_BASE_URL_STORAGE_KEY,
          value.trim().replace(/\/+$/, ""),
        );
      }
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  function getApiBaseUrls() {
    const configured = getConfiguredApiBaseUrls();
    const saved = getSavedApiBaseUrl();
    if (saved && configured[0] === saved) {
      return [saved].concat(
        configured.filter(function (item) {
          return item !== saved;
        }),
      );
    }
    return configured;
  }

  function getApiBaseUrl() {
    const configured = getApiBaseUrls();
    const saved = getSavedApiBaseUrl();
    if (saved && configured[0] === saved) {
      return saved;
    }
    return configured[0] || "";
  }

  async function discoverApiBaseUrl(candidates) {
    const urls = uniqueNonEmptyValues(candidates);
    const failures = [];
    for (const apiBaseUrl of urls) {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          method: "GET",
          headers: { Accept: "application/json" },
          credentials: "include",
        });
        if (response && response.ok) {
          saveApiBaseUrl(apiBaseUrl);
          return apiBaseUrl;
        }
        failures.push(`${apiBaseUrl} returned ${response.status}`);
      } catch (_error) {
        failures.push(`${apiBaseUrl} could not be reached`);
      }
    }

    if (failures.length) {
      console.warn("Tomb of Light API discovery failed:", failures.join("; "));
    }

    return urls[0] || "";
  }

  function buildNetworkErrorMessage(apiBaseUrls) {
    if (!isLocalApp()) {
      return "Service temporarily unavailable. Please try again in a few minutes.";
    }

    const candidates = uniqueNonEmptyValues(apiBaseUrls);
    const details = [
      "Network error calling API.",
      "",
      `API base candidates: ${candidates.join(", ") || "none configured"}`,
      `Page origin: ${window.location.origin}`,
      "",
      "Local frontend should usually run on http://127.0.0.1:5500",
      "Local backend should usually run on http://127.0.0.1:8000",
    ];

    return details.join("\n");
  }

  function getPaymentLinks() {
    return (window.TOL_CONFIG && window.TOL_CONFIG.PAYMENT_LINKS) || {};
  }

  function inferPurchaseTypeFromSlug(slug) {
    const normalizedSlug = String(slug || "")
      .trim()
      .toLowerCase();

    if (!normalizedSlug) return "package";

    if (
      normalizedSlug.endsWith("_maintenance_monthly") ||
      normalizedSlug.endsWith("_maintenance_yearly")
    ) {
      return "maintenance";
    }

    if (ADDON_OR_EXTRA_SLUGS.has(normalizedSlug)) {
      if (
        normalizedSlug.startsWith("extra_") ||
        normalizedSlug === "white_glove_archive_support"
      ) {
        return "extra";
      }
      return "addon";
    }

    return "package";
  }

  function savePendingCheckout(payload) {
    try {
      localStorage.setItem(PENDING_CHECKOUT_KEY, JSON.stringify(payload || {}));
    } catch (_error) {
      // Ignore storage errors for checkout convenience.
    }
  }

  function saveToken(token) {
    if (typeof token === "string" && token.trim()) {
      localStorage.setItem(TOKEN_KEY, token);
    }
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function saveUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user || {}));
  }

  function getSavedUser() {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function clearUser() {
    localStorage.removeItem(USER_KEY);
  }

  function clearSession() {
    clearToken();
    clearUser();
  }

  function isMeaningfulMessage(value) {
    const text = String(value || "").trim();
    if (!text) return false;
    if (/^\[object Object\](,\s*\[object Object\])*$/i.test(text)) {
      return false;
    }
    return true;
  }

  function normalizeMessage(value) {
    const text = String(value || "").trim();
    return isMeaningfulMessage(text) ? text : "";
  }

  function validationLocationLabel(location) {
    if (!Array.isArray(location)) return "";
    const scopeKeys = new Set(["body", "query", "path", "header", "cookie"]);
    return location
      .map(function (part) {
        return String(part || "").trim();
      })
      .filter(Boolean)
      .filter(function (part) {
        return !scopeKeys.has(part.toLowerCase());
      })
      .join(".");
  }

  function dedupeMessages(messages) {
    const seen = new Set();
    const result = [];
    (messages || []).forEach(function (message) {
      const normalized = normalizeMessage(message);
      if (!normalized) return;
      const key = normalized.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      result.push(normalized);
    });
    return result;
  }

  function collectErrorMessages(value, seen) {
    const visited = seen || new Set();
    if (value === null || typeof value === "undefined") return [];

    if (
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      return normalizeMessage(value) ? [normalizeMessage(value)] : [];
    }

    if (value instanceof Error) {
      return dedupeMessages(
        []
          .concat(collectErrorMessages(value.message, visited))
          .concat(collectErrorMessages(value.detail, visited))
          .concat(collectErrorMessages(value.error, visited))
          .concat(collectErrorMessages(value.responseBody, visited))
          .concat(collectErrorMessages(value.data, visited))
          .concat(collectErrorMessages(value.cause, visited)),
      );
    }

    if (Array.isArray(value)) {
      return dedupeMessages(
        value.flatMap(function (item) {
          return collectErrorMessages(item, visited);
        }),
      );
    }

    if (typeof value === "object") {
      if (visited.has(value)) return [];
      visited.add(value);

      const messages = [];
      const candidateMessage = normalizeMessage(
        value.message ||
          value.error ||
          value.reason ||
          value.description ||
          value.title ||
          value.detail ||
          value.msg,
      );
      const location = validationLocationLabel(value.loc);
      if (candidateMessage) {
        messages.push(location ? `${location}: ${candidateMessage}` : candidateMessage);
      }

      ["detail", "message", "error", "errors"].forEach(function (key) {
        if (!Object.prototype.hasOwnProperty.call(value, key)) return;
        messages.push(...collectErrorMessages(value[key], visited));
      });

      Object.entries(value).forEach(function ([key, nestedValue]) {
        if (
          [
            "detail",
            "message",
            "error",
            "errors",
            "msg",
            "loc",
            "ctx",
            "type",
            "input",
            "reason",
            "description",
            "title",
          ].includes(key)
        ) {
          return;
        }
        const nestedMessages = collectErrorMessages(nestedValue, visited);
        nestedMessages.forEach(function (nestedMessage) {
          const normalizedNested = normalizeMessage(nestedMessage);
          if (!normalizedNested) return;
          if (normalizedNested.toLowerCase().startsWith(`${key.toLowerCase()}:`)) {
            messages.push(normalizedNested);
          } else {
            messages.push(`${key}: ${normalizedNested}`);
          }
        });
      });

      return dedupeMessages(messages);
    }

    return normalizeMessage(value) ? [normalizeMessage(value)] : [];
  }

  function getReadableErrorMessage(value, fallback = "") {
    const messages = dedupeMessages(collectErrorMessages(value));
    if (messages.length) {
      return messages.join(" ");
    }
    return normalizeMessage(fallback);
  }

  function parseApiError(data, response) {
    return getReadableErrorMessage(
      data,
      `Request failed with status ${response.status}`,
    );
  }

  async function apiRequest(path, options = {}) {
    const configuredApiBaseUrls = getApiBaseUrls();
    const savedApiBaseUrl = getSavedApiBaseUrl();
    const token = getToken();

    const headers = {
      Accept: "application/json",
      ...(options.headers || {}),
    };

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (token && !headers.Authorization) {
      headers.Authorization = `Bearer ${token}`;
    }

    const preferredApiBaseUrl =
      savedApiBaseUrl && configuredApiBaseUrls[0] === savedApiBaseUrl
        ? savedApiBaseUrl
        : configuredApiBaseUrls.length > 1
        ? await discoverApiBaseUrl(configuredApiBaseUrls)
        : configuredApiBaseUrls[0] || "";
    const apiBaseUrls = uniqueNonEmptyValues([
      preferredApiBaseUrl,
      ...configuredApiBaseUrls,
    ]);

    let response = null;
    let lastNetworkError = null;
    let lastRequestUrl = "";

    for (let index = 0; index < apiBaseUrls.length; index += 1) {
      const apiBaseUrl = apiBaseUrls[index];
      const hasFallbackCandidate = index < apiBaseUrls.length - 1;
      let timeoutId = null;
      let signalHandler = null;
      try {
        const requestOptions = {
          ...options,
          headers,
          credentials: "include",
        };

        if (typeof AbortController === "function") {
          const controller = new AbortController();
          requestOptions.signal = controller.signal;

          timeoutId = window.setTimeout(function () {
            controller.abort();
          }, API_REQUEST_TIMEOUT_MS);

          if (options.signal) {
            if (options.signal.aborted) {
              controller.abort();
            } else {
              signalHandler = function () {
                controller.abort();
              };
              options.signal.addEventListener("abort", signalHandler, {
                once: true,
              });
            }
          }
        }

        const requestUrl = `${apiBaseUrl}${path}`;
        lastRequestUrl = requestUrl;
        response = await fetch(requestUrl, requestOptions);
        const normalizedPath = String(path || "");
        const shouldRetry404Fallback =
          normalizedPath.startsWith("/workspace-access/") ||
          normalizedPath.startsWith("/workspace_access/") ||
          normalizedPath.startsWith("/household-access/") ||
          normalizedPath.startsWith("/admin/control-center/");
        // Some deployments can expose mixed-version backends behind different
        // API domains where `/health` passes but specific routes lag behind.
        // For these known cross-host-sensitive routes, retry 404s against the
        // next configured API base URL before surfacing an error.
        if (
          response &&
          response.status === 404 &&
          hasFallbackCandidate &&
          shouldRetry404Fallback
        ) {
          console.warn("Tomb of Light API fallback retry after 404.", {
            requestPath: normalizedPath,
            failedApiBaseUrl: apiBaseUrl,
          });
          continue;
        }
        saveApiBaseUrl(apiBaseUrl);
        break;
      } catch (networkError) {
        if (
          networkError &&
          networkError.name === "AbortError" &&
          !response
        ) {
          lastNetworkError = new Error(
            "Request timed out. Please try again in a moment.",
          );
        } else {
          lastNetworkError = networkError;
        }
      } finally {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
        if (options.signal && signalHandler) {
          options.signal.removeEventListener("abort", signalHandler);
        }
      }
    }

    if (!response) {
      const error = new Error(buildNetworkErrorMessage(apiBaseUrls));
      error.status = 0;
      error.apiBaseUrls = apiBaseUrls;
      error.requestUrl = lastRequestUrl;
      if (lastNetworkError) {
        error.cause = lastNetworkError;
      }
      throw error;
    }

    const contentType = response.headers.get("content-type") || "";
    let data = null;

    try {
      if (contentType.includes("application/json")) {
        data = await response.json();
      } else {
        const text = await response.text();
        data = text ? { detail: text } : null;
      }
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      const error = new Error(parseApiError(data, response));
      error.status = response.status;
      error.statusText = response.statusText;
      error.detail = getReadableErrorMessage(
        data && (data.detail || data.message || data.error || data),
      );
      error.data = data;
      error.requestUrl = lastRequestUrl;
      error.responseBody = data;
      throw error;
    }

    return data;
  }

  async function fetchCurrentUser() {
    const user = await apiRequest("/auth/me", { method: "GET" });
    saveUser(user);
    return user;
  }

  async function logoutUser() {
    // Clear the local session immediately so the caller is not blocked on the
    // network round-trip.  The backend call is best-effort: we still attempt it
    // so the server-side httpOnly auth cookie is revoked, but a slow or failing
    // backend cannot prevent the user from being logged out locally.
    clearSession();
    try {
      await apiRequest("/auth/logout", {
        method: "POST",
      });
    } catch (_error) {
      // Ignore – local session already cleared above.
    }
  }

  async function requireSession(redirectTo = "signin.html") {
    const token = getToken();

    if (!token) {
      if (redirectTo) {
        window.location.href = redirectTo;
      }
      return null;
    }

    try {
      return await fetchCurrentUser();
    } catch (error) {
      clearSession();
      if (redirectTo) {
        window.location.href = redirectTo;
      }
      return null;
    }
  }

  function setStatus(node, message, type) {
    if (!node) return;

    const fallbackMessage =
      type === "error"
        ? "Something went wrong. Please try again."
        : "Status updated.";
    const resolvedMessage = getReadableErrorMessage(message, fallbackMessage);

    node.style.display = "block";
    node.textContent = resolvedMessage;
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

  function getCookieChoice() {
    const value = localStorage.getItem(COOKIE_CHOICE_KEY);
    return value === "accepted" || value === "declined" ? value : null;
  }

  function saveCookieChoice(choice) {
    localStorage.setItem(COOKIE_CHOICE_KEY, choice);
    document.documentElement.dataset.cookieChoice = choice;
  }

  function updateCookieStatus() {
    const statusNodes = document.querySelectorAll("[data-cookie-status]");
    if (!statusNodes.length) return;

    const choice = getCookieChoice();
    let message = "Your cookie preference has not been set yet.";

    if (choice === "accepted") {
      message = "You accepted optional analytics cookies.";
    } else if (choice === "declined") {
      message =
        "You declined optional analytics cookies. Only essential site technologies are in use.";
    }

    statusNodes.forEach(function (node) {
      node.textContent = message;
    });
  }

  function setupCookieBanner() {
    const banner = document.querySelector("[data-cookie-banner]");
    if (!banner) return;

    const acceptBtn = banner.querySelector("[data-cookie-accept]");
    const declineBtn = banner.querySelector("[data-cookie-decline]");

    function applyChoice(choice) {
      saveCookieChoice(choice);
      updateCookieStatus();
      banner.classList.remove("visible");
    }

    const existingChoice = getCookieChoice();
    if (!existingChoice) {
      banner.classList.add("visible");
    } else {
      banner.classList.remove("visible");
      updateCookieStatus();
    }

    if (acceptBtn) {
      acceptBtn.addEventListener("click", function () {
        applyChoice("accepted");
      });
    }

    if (declineBtn) {
      declineBtn.addEventListener("click", function () {
        applyChoice("declined");
      });
    }
  }

  function setupMobileMenu() {
    const header = document.querySelector(".site-header");
    const toggle = document.querySelector(".menu-toggle");
    let lastFocusedElement = null;

    if (!header || !toggle) return;

    function closeMenu() {
      header.classList.remove("open");
      document.body.classList.remove("menu-open");
      toggle.setAttribute("aria-expanded", "false");
      if (
        lastFocusedElement &&
        typeof lastFocusedElement.focus === "function" &&
        document.contains(lastFocusedElement)
      ) {
        lastFocusedElement.focus();
      }
    }

    function openMenu() {
      lastFocusedElement = document.activeElement;
      header.classList.add("open");
      document.body.classList.add("menu-open");
      toggle.setAttribute("aria-expanded", "true");

      const firstNavLink = header.querySelector(
        ".site-nav a, .header-actions a, .header-actions button",
      );
      if (firstNavLink && typeof firstNavLink.focus === "function") {
        firstNavLink.focus();
      }
    }

    toggle.addEventListener("click", function () {
      const isOpen = header.classList.contains("open");
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    header
      .querySelectorAll(
        ".site-nav a, .header-actions a, .header-actions button",
      )
      .forEach(function (link) {
        link.addEventListener("click", closeMenu);
      });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeMenu();
      }
    });

    document.addEventListener("click", function (event) {
      if (!header.classList.contains("open")) return;
      if (header.contains(event.target)) return;
      closeMenu();
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) {
        closeMenu();
      }
    });
  }

  function setupHeaderScrollState() {
    const header = document.querySelector(".site-header");
    if (!header) return;

    function syncScrollState() {
      header.classList.toggle("is-scrolled", window.scrollY > 18);
    }

    syncScrollState();
    window.addEventListener("scroll", syncScrollState, { passive: true });
  }

  function markActiveNavLink() {
    const currentPage =
      window.location.pathname.split("/").pop() || "index.html";

    document.querySelectorAll(".site-nav a[href]").forEach(function (link) {
      try {
        const url = new URL(link.getAttribute("href"), window.location.href);
        const linkPage = url.pathname.split("/").pop() || "index.html";

        if (linkPage === currentPage) {
          link.classList.add("active");
        }
      } catch (error) {
        // Ignore malformed hrefs.
      }
    });
  }

  function applyPaymentLinks() {
    const paymentLinks = getPaymentLinks();

    document.querySelectorAll("[data-payment-link]").forEach(function (link) {
      const slug = link.dataset.paymentLink;
      const resolved = paymentLinks[slug];

      if (resolved) {
        link.href = resolved;
        link.addEventListener("click", function () {
          savePendingCheckout({
            packageCode: slug,
            purchaseType: link.dataset.paymentType || inferPurchaseTypeFromSlug(slug),
            paymentLink: resolved,
            selectedAt: new Date().toISOString(),
          });
        });
      }
    });
  }

  async function syncPublicAuthCtas() {
    const ctas = document.querySelectorAll("[data-auth-cta]");
    if (!ctas.length) return;

    const token = getToken();
    if (!token) return;

    try {
      await fetchCurrentUser();

      ctas.forEach(function (cta) {
        cta.textContent = cta.dataset.loggedInLabel || "Dashboard";
        cta.setAttribute("href", cta.dataset.loggedInHref || "dashboard.html");
      });
    } catch (error) {
      clearSession();
    }
  }

  function setupSelectPlaceholderState() {
    document.querySelectorAll("select").forEach(function (select) {
      function syncPlaceholderState() {
        if (!select.value) {
          select.classList.add("placeholder-active");
        } else {
          select.classList.remove("placeholder-active");
        }
      }

      syncPlaceholderState();
      select.addEventListener("change", syncPlaceholderState);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupMobileMenu();
    setupHeaderScrollState();
    markActiveNavLink();
    updateCookieStatus();
    setupCookieBanner();
    applyPaymentLinks();
    syncPublicAuthCtas();
    setupSelectPlaceholderState();
  });

  const sharedApi = {
    isLocalApp,
    isInternalRole,
    getApiBaseUrl,
    getPaymentLinks,
    saveToken,
    getToken,
    clearToken,
    saveUser,
    getSavedUser,
    clearUser,
    clearSession,
    apiRequest,
    fetchCurrentUser,
    logoutUser,
    requireSession,
    setStatus,
    clearStatus,
    normalizePackageCode,
    stripMaintenanceSuffix,
    getPackageProfile,
    resolvePackageLane,
    resolvePackageDisplayName,
    packageSupportsLinkKeys,
    inferPurchaseTypeFromSlug,
    savePendingCheckout,
    getReadableErrorMessage,
  };

  window.TOLApp = sharedApi;
  window.TOLAuth = sharedApi;
})();
