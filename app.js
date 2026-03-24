(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

  const DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
  const DEFAULT_LIVE_API_BASE_URL = "https://tomboflight-api.onrender.com";

  const TOKEN_KEY = "tol_access_token";
  const USER_KEY = "tol_user";
  const COOKIE_CHOICE_KEY = "tol_cookie_choice";
  const COOKIE_SESSION_MARKER = "__cookie_session__";

  function isLocalApp() {
    return LOCAL_HOSTS.has(window.location.hostname);
  }

  function getApiBaseUrl() {
    const configured =
      window.TOL_CONFIG && typeof window.TOL_CONFIG.API_BASE_URL === "string"
        ? window.TOL_CONFIG.API_BASE_URL.trim()
        : "";

    if (configured) {
      return configured;
    }

    return isLocalApp()
      ? DEFAULT_LOCAL_API_BASE_URL
      : DEFAULT_LIVE_API_BASE_URL;
  }

  function getPaymentLinks() {
    return (window.TOL_CONFIG && window.TOL_CONFIG.PAYMENT_LINKS) || {};
  }

  function isCookieSessionMarker(value) {
    return value === COOKIE_SESSION_MARKER;
  }

  function saveToken(token) {
    if (typeof token === "string" && token.trim()) {
      // Store only a non-sensitive session marker for the frontend.
      localStorage.setItem(TOKEN_KEY, COOKIE_SESSION_MARKER);
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
    const apiBaseUrl = getApiBaseUrl();
    const token = getToken();

    const headers = {
      Accept: "application/json",
      ...(options.headers || {}),
    };

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (token && !isCookieSessionMarker(token)) {
      headers.Authorization = `Bearer ${token}`;
    }

    let response;

    try {
      response = await fetch(`${apiBaseUrl}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    } catch (networkError) {
      throw new Error(
        `Network error calling API.\n\n` +
          `API_BASE_URL: ${apiBaseUrl}\n` +
          `Page origin: ${window.location.origin}\n\n` +
          `Local frontend should usually run on http://127.0.0.1:5500\n` +
          `Local backend should usually run on http://127.0.0.1:8000`,
      );
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
    try {
      await apiRequest("/auth/logout", {
        method: "POST",
      });
    } finally {
      clearSession();
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

    if (!header || !toggle) return;

    function closeMenu() {
      header.classList.remove("open");
      document.body.classList.remove("menu-open");
      toggle.setAttribute("aria-expanded", "false");
    }

    function openMenu() {
      header.classList.add("open");
      document.body.classList.add("menu-open");
      toggle.setAttribute("aria-expanded", "true");
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
        // ignore malformed hrefs
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

  document.addEventListener("DOMContentLoaded", function () {
    setupMobileMenu();
    markActiveNavLink();
    updateCookieStatus();
    setupCookieBanner();
    applyPaymentLinks();
    syncPublicAuthCtas();
  });

  const sharedApi = {
    isLocalApp,
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
  };

  window.TOLApp = sharedApi;
  window.TOLAuth = sharedApi;
})();
