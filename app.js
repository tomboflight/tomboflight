(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

  const DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
  const DEFAULT_LIVE_API_BASE_URL = "https://tomboflight-api.onrender.com";
  const DEFAULT_LIVE_API_BASE_URLS = [
    "https://api.tomboflight.com",
    DEFAULT_LIVE_API_BASE_URL,
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

  // Canonical set of internal-role values shared across all modules.
  // Any module needing role gating should call app.isInternalRole() rather
  // than maintaining its own copy of this set.
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

  function isInternalRole(user) {
    if (!user || typeof user !== "object") return false;
    return [
      String(user.role || "").trim().toLowerCase(),
      String(user.access_tier || "").trim().toLowerCase(),
      String(user.department_role || "").trim().toLowerCase(),
    ].some(function (v) {
      return v && INTERNAL_ROLE_KEYS.has(v);
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
      ...configuredList,
      configuredSingle,
    ]);
    if (configured.length) {
      return configured;
    }

    return isLocalApp()
      ? [DEFAULT_LOCAL_API_BASE_URL]
      : DEFAULT_LIVE_API_BASE_URLS.slice();
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
    if (saved && configured.includes(saved)) {
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
    if (saved && configured.includes(saved)) {
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

  function parseApiError(data, response) {
    return (
      (data &&
        (data.detail ||
          data.message ||
          data.error ||
          (Array.isArray(data.errors) && data.errors.join(", ")))) ||
      `Request failed with status ${response.status}`
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
      savedApiBaseUrl && configuredApiBaseUrls.includes(savedApiBaseUrl)
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

    for (const apiBaseUrl of apiBaseUrls) {
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

        response = await fetch(`${apiBaseUrl}${path}`, requestOptions);
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
      throw new Error(parseApiError(data, response));
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
    inferPurchaseTypeFromSlug,
    savePendingCheckout,
  };

  window.TOLApp = sharedApi;
  window.TOLAuth = sharedApi;
})();
