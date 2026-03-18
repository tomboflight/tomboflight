/**
 * Tomb of Light - Main Application Script
 * Dashboard: orders + intake status + intake history
 */

(function () {
  'use strict';

  const doc = document;
  const body = doc.body;

  const API_BASE_URL =
    (window.TOL_CONFIG && window.TOL_CONFIG.API_BASE_URL) ||
    'http://127.0.0.1:8000';

  const TOKEN_KEY = 'tol_access_token';
  const CURRENT_ORDER_CACHE_KEY = 'tol_current_order';
  const LATEST_INTAKE_CACHE_KEY = 'tol_latest_intake_submission';

  const menuToggle = doc.querySelector('.menu-toggle, .nav-toggle');
  const siteNav = doc.querySelector('#site-nav, .site-nav');
  const siteHeader = doc.querySelector('.site-header');

  const cookieBanner = doc.querySelector('[data-cookie-banner]');
  const cookieStatuses = Array.from(doc.querySelectorAll('[data-cookie-status]'));
  const acceptBtn = doc.querySelector('[data-cookie-accept]');
  const declineBtn = doc.querySelector('[data-cookie-decline]');
  const COOKIE_NAME = 'tol_cookie_preference';
  const COOKIE_EXPIRY_DAYS = 365;

  const PACKAGE_CATALOG = {
    'digital-legacy-portrait': { name: 'Digital Legacy Portrait' },
    'starter-family-tree': { name: 'Starter Family Tree' },
    'heirloom-legacy-tree': { name: 'Heirloom Legacy Tree' },
    'legacy-plus': { name: 'Legacy Plus' },
    'family-estate-concierge': { name: 'Family Estate Concierge' }
  };

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getAuthHeaders(extraHeaders = {}) {
    const token = getToken();
    const headers = { Accept: 'application/json', ...extraHeaders };
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  async function apiRequest(path, options = {}) {
    const headers = getAuthHeaders(options.headers || {});
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

    const contentType = response.headers.get('content-type') || '';
    let data = null;

    try {
      if (contentType.includes('application/json')) data = await response.json();
      else {
        const text = await response.text();
        data = text ? { detail: text } : null;
      }
    } catch (_) {
      data = null;
    }

    if (!response.ok) {
      const message =
        (data && (data.detail || data.message || data.error)) ||
        `Request failed with status ${response.status}`;
      throw new Error(message);
    }

    return data;
  }

  // ---- Menu
  function closeMenu() {
    if (!menuToggle || !siteHeader) return;
    menuToggle.setAttribute('aria-expanded', 'false');
    siteHeader.classList.remove('open');
    body.classList.remove('menu-open');
  }

  function openMenu() {
    if (!menuToggle || !siteHeader) return;
    menuToggle.setAttribute('aria-expanded', 'true');
    siteHeader.classList.add('open');
    body.classList.add('menu-open');
  }

  function setupMobileMenu() {
    if (!menuToggle || !siteNav || !siteHeader) return;
    if (!siteNav.id) siteNav.id = 'site-nav';
    if (!menuToggle.hasAttribute('aria-controls')) menuToggle.setAttribute('aria-controls', siteNav.id);
    if (!menuToggle.hasAttribute('aria-expanded')) menuToggle.setAttribute('aria-expanded', 'false');

    menuToggle.addEventListener('click', function () {
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      isExpanded ? closeMenu() : openMenu();
    });

    siteNav.addEventListener('click', function (event) {
      const clickedLink = event.target.closest('a');
      if (clickedLink) closeMenu();
    });

    doc.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
        closeMenu();
        menuToggle.focus();
      }
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 860) closeMenu();
    });
  }

  // ---- Cookies
  function setCookie(name, value, days) {
    const expiryDate = new Date();
    expiryDate.setTime(expiryDate.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${value};expires=${expiryDate.toUTCString()};path=/;SameSite=Strict`;
  }

  function getCookie(name) {
    const cookieName = `${name}=`;
    const cookies = decodeURIComponent(document.cookie).split(';');
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.indexOf(cookieName) === 0) return cookie.substring(cookieName.length);
    }
    return null;
  }

  function updateCookieStatus(preference) {
    if (!cookieStatuses.length) return;
    let message = 'Your cookie preference has not been set yet.';
    if (preference === 'true') message = 'Analytics cookies are enabled.';
    if (preference === 'false') message = 'Analytics cookies are disabled.';
    cookieStatuses.forEach((n) => (n.textContent = message));
  }

  function showCookieBanner() {
    if (!cookieBanner) return;
    cookieBanner.classList.add('visible');
    cookieBanner.removeAttribute('aria-hidden');
  }

  function hideCookieBanner() {
    if (!cookieBanner) return;
    cookieBanner.classList.remove('visible');
    cookieBanner.setAttribute('aria-hidden', 'true');
  }

  function setupCookiePreferences() {
    const savedPreference = getCookie(COOKIE_NAME);
    if (savedPreference === 'true' || savedPreference === 'false') {
      updateCookieStatus(savedPreference);
      hideCookieBanner();
    } else {
      updateCookieStatus(null);
      showCookieBanner();
    }

    if (acceptBtn) {
      acceptBtn.addEventListener('click', function (event) {
        event.preventDefault();
        setCookie(COOKIE_NAME, 'true', COOKIE_EXPIRY_DAYS);
        updateCookieStatus('true');
        hideCookieBanner();
      });
    }

    if (declineBtn) {
      declineBtn.addEventListener('click', function (event) {
        event.preventDefault();
        setCookie(COOKIE_NAME, 'false', COOKIE_EXPIRY_DAYS);
        updateCookieStatus('false');
        hideCookieBanner();
      });
    }
  }

  // ---- Cache helpers
  function setCurrentOrderCache(order) {
    try { localStorage.setItem(CURRENT_ORDER_CACHE_KEY, JSON.stringify(order || null)); } catch (_) {}
  }

  function getCurrentOrderCache() {
    try {
      const raw = localStorage.getItem(CURRENT_ORDER_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function cacheLatestIntake(submission) {
    try { localStorage.setItem(LATEST_INTAKE_CACHE_KEY, JSON.stringify(submission || null)); } catch (_) {}
  }

  function getCachedLatestIntake() {
    try {
      const raw = localStorage.getItem(LATEST_INTAKE_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  // ---- Orders UI
  function setPaidAccessState(hasPaidOrder, orders) {
    const accessStatus = doc.querySelector('[data-access-status]');
    const paidActions = Array.from(doc.querySelectorAll('[data-paid-action]'));
    const upgradeActions = Array.from(doc.querySelectorAll('[data-upgrade-action]'));

    function setNode(node, enabled) {
      if (!node) return;
      if (enabled) {
        node.classList.remove('is-disabled');
        node.removeAttribute('aria-disabled');
        node.removeAttribute('title');
        node.style.pointerEvents = '';
        node.style.opacity = '';
        if (node.dataset.originalHref) node.setAttribute('href', node.dataset.originalHref);
        return;
      }
      if (node.tagName.toLowerCase() === 'a' && !node.dataset.originalHref) {
        node.dataset.originalHref = node.getAttribute('href') || '';
      }
      node.classList.add('is-disabled');
      node.setAttribute('aria-disabled', 'true');
      node.setAttribute('title', 'Purchase a package to unlock this feature');
      node.style.pointerEvents = 'none';
      node.style.opacity = '0.55';
    }

    if (hasPaidOrder) {
      if (accessStatus) {
        const first = orders && orders.length ? orders[0] : null;
        const packageName = first?.package_name || first?.package_slug || 'your package';
        accessStatus.textContent = `Access unlocked. Your account has an active purchase record for ${packageName}.`;
      }
      paidActions.forEach((n) => setNode(n, true));
      upgradeActions.forEach((n) => (n.textContent = 'View Packages'));
      return;
    }

    if (accessStatus) accessStatus.textContent = 'Purchase required. Buy a Tomb of Light package to unlock platform tools.';
    paidActions.forEach((n) => setNode(n, false));
    upgradeActions.forEach((n) => (n.textContent = 'Unlock Access'));
  }

  function renderOrders(orders) {
    const ordersList = doc.querySelector('[data-orders-list]');
    const ordersStatus = doc.querySelector('[data-orders-status]');
    if (!ordersList || !ordersStatus) return;

    if (!Array.isArray(orders) || !orders.length) {
      ordersStatus.textContent = 'No purchases have been recorded yet.';
      ordersList.innerHTML = '';
      setPaidAccessState(false, []);
      setCurrentOrderCache(null);
      return;
    }

    ordersStatus.textContent = 'Your purchases are recorded below.';
    setPaidAccessState(true, orders);
    setCurrentOrderCache(orders[0]);

    ordersList.innerHTML = orders.map(function (order, index) {
      const packageName = order.package_name || order.package_slug || 'Package';
      const priceLabel = order.price_label || '';
      const status = order.status || 'received';
      const createdAt = order.created_at ? new Date(order.created_at).toLocaleString() : 'Just now';

      return `
        <div>
          <div class="card-number">${index + 1}</div>
          <h3>${packageName}</h3>
          <p class="card-copy"><strong>Status:</strong> ${status}</p>
          <p class="card-copy"><strong>Price:</strong> ${priceLabel}</p>
          <p class="card-copy"><strong>Recorded:</strong> ${createdAt}</p>
        </div>
      `;
    }).join('');
  }

  async function loadDashboardOrders() {
    const dashboard = doc.querySelector('[data-dashboard]');
    if (!dashboard) return [];

    const ordersStatus = doc.querySelector('[data-orders-status]');
    if (ordersStatus) ordersStatus.textContent = 'Loading your purchases...';

    try {
      const response = await apiRequest('/orders/my-orders', { method: 'GET' });
      const orders = Array.isArray(response) ? response : (response.orders || []);
      renderOrders(orders);
      return orders;
    } catch (error) {
      if (ordersStatus) ordersStatus.textContent = 'Orders unavailable right now.';
      setPaidAccessState(false, []);
      return [];
    }
  }

  // ---- Intake Status UI
  function updateDashboardIntakeCard(submission) {
    const cardStatus = doc.querySelector('[data-intake-card-status]');
    const currentPackageNode = doc.querySelector('[data-intake-current-package]');
    const statusBadgeNode = doc.querySelector('[data-intake-status-badge]');
    const submissionIdNode = doc.querySelector('[data-intake-submission-id]');
    const submittedAtNode = doc.querySelector('[data-intake-submitted-at]');
    const nextStepNode = doc.querySelector('[data-intake-next-step]');
    const lockNoteNode = doc.querySelector('[data-intake-lock-note]');
    const openActionNode = doc.querySelector('[data-intake-open-action]');

    if (!cardStatus || !currentPackageNode || !statusBadgeNode || !submissionIdNode || !submittedAtNode || !nextStepNode || !lockNoteNode || !openActionNode) return;

    const order = getCurrentOrderCache();
    const packageName =
      submission?.package_name ||
      order?.package_name ||
      (order?.package_slug ? (PACKAGE_CATALOG[order.package_slug]?.name || order.package_slug) : 'No package detected');

    currentPackageNode.textContent = packageName;

    if (!submission) {
      cardStatus.textContent = 'No intake submission found yet.';
      statusBadgeNode.textContent = 'Not submitted';
      submissionIdNode.textContent = '—';
      submittedAtNode.textContent = '—';
      nextStepNode.textContent = 'Open your intake flow and submit the review step.';
      lockNoteNode.textContent = 'Editing is open because no final submission exists yet.';
      openActionNode.textContent = 'Open Intake';
      openActionNode.setAttribute('href', 'intake-welcome.html');
      return;
    }

    cardStatus.textContent = 'Your latest intake submission is recorded.';
    statusBadgeNode.textContent = submission.status || 'submitted';
    submissionIdNode.textContent = submission.id || '—';
    submittedAtNode.textContent = submission.created_at ? new Date(submission.created_at).toLocaleString() : '—';
    nextStepNode.textContent = 'Your intake is now ready for the next onboarding stage (uploads/consent) and production review.';
    lockNoteNode.textContent = 'This intake is submitted. Use review for reference; edits should be handled in the next stage.';
    openActionNode.textContent = 'View Intake';
    openActionNode.setAttribute('href', 'intake-review.html');
  }

  async function loadDashboardIntakeStatus() {
    const dashboard = doc.querySelector('[data-dashboard]');
    if (!dashboard) return;

    try {
      const submission = await apiRequest('/intake-submissions/my-latest', { method: 'GET' });
      cacheLatestIntake(submission);
      updateDashboardIntakeCard(submission);
    } catch (error) {
      const cached = getCachedLatestIntake();
      updateDashboardIntakeCard(cached);
    }
  }

  // ---- Intake History UI
  function renderIntakeHistory(items) {
    const statusNode = doc.querySelector('[data-intake-history-status]');
    const listNode = doc.querySelector('[data-intake-history-list]');
    if (!statusNode || !listNode) return;

    if (!Array.isArray(items) || items.length === 0) {
      statusNode.textContent = 'No intake submissions found yet.';
      listNode.innerHTML = '';
      return;
    }

    statusNode.textContent = 'Your intake submission history is listed below.';

    listNode.innerHTML = items.map(function (item, index) {
      const pkg = item.package_name || item.package_slug || 'Package';
      const status = item.status || 'submitted';
      const createdAt = item.created_at ? new Date(item.created_at).toLocaleString() : '—';
      const id = item.id || '—';

      return `
        <div>
          <div class="card-number">${index + 1}</div>
          <h3>${pkg}</h3>
          <p class="card-copy"><strong>Status:</strong> ${status}</p>
          <p class="card-copy"><strong>Submitted:</strong> ${createdAt}</p>
          <p class="card-copy"><strong>ID:</strong> ${id}</p>
        </div>
      `;
    }).join('');
  }

  async function loadDashboardIntakeHistory() {
    const dashboard = doc.querySelector('[data-dashboard]');
    if (!dashboard) return;

    const statusNode = doc.querySelector('[data-intake-history-status]');
    if (statusNode) statusNode.textContent = 'Loading your intake history...';

    try {
      const list = await apiRequest('/intake-submissions/my-list?limit=10', { method: 'GET' });
      renderIntakeHistory(list);
    } catch (error) {
      if (statusNode) statusNode.textContent = 'Intake history unavailable right now.';
      renderIntakeHistory([]);
    }
  }

  // ---- Init
  function init() {
    setupMobileMenu();
    setupCookiePreferences();

    loadDashboardOrders().then(function () {
      loadDashboardIntakeStatus();
      loadDashboardIntakeHistory();
    });

    console.log('[TOL] API_BASE_URL:', API_BASE_URL);
  }

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init);
  else init();
})();