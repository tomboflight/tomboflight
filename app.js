/**
 * Tomb of Light - Main Application Script
 * Accessibility, navigation, cookie preference handling,
 * backend connectivity, request access form submission,
 * thank-you order recording, dashboard order loading,
 * and paid-access gating.
 */

(function () {
  'use strict';

  const doc = document;
  const body = doc.body;

  const API_BASE_URL =
    (window.TOL_CONFIG && window.TOL_CONFIG.API_BASE_URL) ||
    'http://127.0.0.1:8000';

  const menuToggle = doc.querySelector('.menu-toggle, .nav-toggle');
  const siteNav = doc.querySelector('#site-nav, .site-nav');
  const siteHeader = doc.querySelector('.site-header');

  const cookieBanner = doc.querySelector('[data-cookie-banner]');
  const cookieStatuses = Array.from(doc.querySelectorAll('[data-cookie-status]'));
  const acceptBtn = doc.querySelector('[data-cookie-accept]');
  const declineBtn = doc.querySelector('[data-cookie-decline]');
  const supportEmail = 'support@tomboflight.com';

  const requestAccessForm = doc.querySelector('[data-request-access-form]');
  const formStatus = doc.querySelector('[data-form-status]');
  const submitBtn = doc.querySelector('[data-submit-btn]');

  const COOKIE_NAME = 'tol_cookie_preference';
  const COOKIE_EXPIRY_DAYS = 365;
  const TOKEN_KEY = 'tol_access_token';

  const PACKAGE_CATALOG = {
    'digital-legacy-portrait': {
      slug: 'digital-legacy-portrait',
      name: 'Digital Legacy Portrait',
      price_label: '$399'
    },
    'starter-family-tree': {
      slug: 'starter-family-tree',
      name: 'Starter Family Tree',
      price_label: '$799'
    },
    'heirloom-legacy-tree': {
      slug: 'heirloom-legacy-tree',
      name: 'Heirloom Legacy Tree',
      price_label: '$1,500'
    },
    'legacy-plus': {
      slug: 'legacy-plus',
      name: 'Legacy Plus',
      price_label: '$3,200'
    },
    'family-estate-concierge': {
      slug: 'family-estate-concierge',
      name: 'Family Estate Concierge',
      price_label: '$6,500–$12,000'
    }
  };

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getAuthHeaders(extraHeaders = {}) {
    const token = getToken();
    const headers = {
      Accept: 'application/json',
      ...extraHeaders
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    return headers;
  }

  async function apiRequest(path, options = {}) {
    const headers = getAuthHeaders(options.headers || {});

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers
    });

    const contentType = response.headers.get('content-type') || '';
    let data = null;

    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = text ? { detail: text } : null;
    }

    if (!response.ok) {
      const message =
        (data && (data.detail || data.message || data.error)) ||
        `Request failed with status ${response.status}`;
      throw new Error(message);
    }

    return data;
  }

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

    if (!siteNav.id) {
      siteNav.id = 'site-nav';
    }

    if (!menuToggle.hasAttribute('aria-controls')) {
      menuToggle.setAttribute('aria-controls', siteNav.id);
    }

    if (!menuToggle.hasAttribute('aria-expanded')) {
      menuToggle.setAttribute('aria-expanded', 'false');
    }

    menuToggle.addEventListener('click', function () {
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      if (isExpanded) {
        closeMenu();
      } else {
        openMenu();
      }
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
      if (window.innerWidth > 860) {
        closeMenu();
      }
    });
  }

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
      if (cookie.indexOf(cookieName) === 0) {
        return cookie.substring(cookieName.length);
      }
    }

    return null;
  }

  function initializeAnalytics() {
    try {
      console.log('Analytics initialized');
    } catch (error) {
      console.error('Analytics initialization failed:', error);
    }
  }

  function updateCookieStatus(preference) {
    if (!cookieStatuses.length) return;

    let message = 'Your cookie preference has not been set yet.';

    if (preference === 'true') {
      message = 'Analytics cookies are enabled.';
      initializeAnalytics();
    } else if (preference === 'false') {
      message = 'Analytics cookies are disabled.';
    }

    cookieStatuses.forEach(function (node) {
      node.textContent = message;
    });
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

  function saveCookiePreference(value) {
    setCookie(COOKIE_NAME, value, COOKIE_EXPIRY_DAYS);
    updateCookieStatus(value);
    hideCookieBanner();
  }

  function buildMailtoBody(form) {
    const formData = new FormData(form);
    const lines = [
      'Submitted from the Tomb of Light website.',
      `Page: ${window.location.href}`,
      ''
    ];

    formData.forEach(function (value, key) {
      const normalizedValue = String(value).trim();
      if (!normalizedValue) return;

      const field = form.elements[key];
      const label = field && field.dataset && field.dataset.label
        ? field.dataset.label
        : key.replace(/_/g, ' ');

      lines.push(`${label}: ${normalizedValue}`);
    });

    return lines.join('\n');
  }

  function setupMailtoForms() {
    const forms = Array.from(doc.querySelectorAll('[data-mailto-form]'));
    if (!forms.length) return;

    forms.forEach(function (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();

        if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
          return;
        }

        const subject = form.dataset.formSubject || 'Website inquiry';
        const bodyText = buildMailtoBody(form);
        const params = new URLSearchParams({
          subject: subject,
          body: bodyText
        });

        window.location.href = `mailto:${supportEmail}?${params.toString()}`;
      });
    });
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
        saveCookiePreference('true');
      });
    }

    if (declineBtn) {
      declineBtn.addEventListener('click', function (event) {
        event.preventDefault();
        saveCookiePreference('false');
      });
    }
  }

  async function checkBackendHealth() {
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: {
          Accept: 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Health check failed with status ${response.status}`);
      }

      const data = await response.json();
      console.log('Tomb of Light backend is connected:', data);
      body.dataset.apiStatus = 'online';
    } catch (error) {
      console.error('Tomb of Light backend connection failed:', error);
      body.dataset.apiStatus = 'offline';
    }
  }

  function setFormStatus(message, type) {
    if (!formStatus) return;

    formStatus.style.display = 'block';
    formStatus.textContent = message;
    formStatus.dataset.state = type || 'info';
    formStatus.style.color = type === 'error' ? '#ffb3b3' : '#cfe8cf';
  }

  function clearFormStatus() {
    if (!formStatus) return;
    formStatus.style.display = 'none';
    formStatus.textContent = '';
    formStatus.dataset.state = '';
  }

  async function submitRequestAccessForm(event) {
    event.preventDefault();

    if (!requestAccessForm) return;

    clearFormStatus();

    if (typeof requestAccessForm.reportValidity === 'function' && !requestAccessForm.reportValidity()) {
      return;
    }

    const formData = new FormData(requestAccessForm);

    const payload = {
      full_name: String(formData.get('full_name') || '').trim(),
      email: String(formData.get('email') || '').trim(),
      interest_type: String(formData.get('interest_type') || '').trim(),
      organization: String(formData.get('organization') || '').trim(),
      message: String(formData.get('message') || '').trim()
    };

    if (!payload.full_name || !payload.email || !payload.interest_type || !payload.message) {
      setFormStatus('Please complete all required fields before submitting.', 'error');
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting...';
    }

    try {
      const response = await fetch(`${API_BASE_URL}/intake/request-access`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(payload)
      });

      let responseData = null;

      try {
        responseData = await response.json();
      } catch (jsonError) {
        responseData = null;
      }

      if (!response.ok) {
        const message =
          (responseData && (responseData.detail || responseData.message)) ||
          'Your request could not be submitted right now. Please try again.';
        throw new Error(message);
      }

      requestAccessForm.reset();
      setFormStatus(
        'Your request has been submitted successfully. Tomb of Light will review your information and follow up when appropriate.',
        'success'
      );
    } catch (error) {
      console.error('Request access submission failed:', error);
      setFormStatus(
        error.message || 'Submission failed. Please try again later.',
        'error'
      );
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Request';
      }
    }
  }

  function setupRequestAccessForm() {
    if (!requestAccessForm) return;
    requestAccessForm.addEventListener('submit', submitRequestAccessForm);
  }

  function getPackageFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const slug = params.get('package');
    if (!slug) return null;
    return PACKAGE_CATALOG[slug] || {
      slug: slug,
      name: slug.replace(/-/g, ' '),
      price_label: 'Package selected'
    };
  }

  function setPaidActionNodeState(node, enabled) {
    if (!node) return;

    if (enabled) {
      node.classList.remove('is-disabled');
      node.removeAttribute('aria-disabled');
      node.removeAttribute('title');
      node.style.pointerEvents = '';
      node.style.opacity = '';
      if (node.dataset.originalHref) {
        node.setAttribute('href', node.dataset.originalHref);
      }
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

  function setPaidAccessState(hasPaidOrder, orders) {
    const accessStatus = doc.querySelector('[data-access-status]');
    const paidActions = Array.from(doc.querySelectorAll('[data-paid-action]'));
    const upgradeActions = Array.from(doc.querySelectorAll('[data-upgrade-action]'));

    if (hasPaidOrder) {
      if (accessStatus) {
        const firstOrder = Array.isArray(orders) && orders.length ? orders[0] : null;
        const packageName = firstOrder && firstOrder.package_name ? firstOrder.package_name : 'your paid package';
        accessStatus.textContent = `Access unlocked. Your account has an active purchase record for ${packageName}. You can now begin your family record and platform workflow.`;
      }

      paidActions.forEach(function (node) {
        setPaidActionNodeState(node, true);
      });

      upgradeActions.forEach(function (node) {
        node.textContent = 'View Packages';
      });

      return;
    }

    if (accessStatus) {
      accessStatus.textContent = 'Purchase required. Buy a Tomb of Light package to unlock family creation, lineage tools, and guided intake.';
    }

    paidActions.forEach(function (node) {
      setPaidActionNodeState(node, false);
    });

    upgradeActions.forEach(function (node) {
      node.textContent = 'Unlock Access';
    });
  }

  function renderOrders(orders) {
    const ordersList = doc.querySelector('[data-orders-list]');
    const ordersStatus = doc.querySelector('[data-orders-status]');

    if (!ordersList || !ordersStatus) return;

    if (!Array.isArray(orders) || !orders.length) {
      ordersStatus.textContent = 'No purchases have been recorded yet.';
      ordersList.innerHTML = '';
      setPaidAccessState(false, []);
      return;
    }

    ordersStatus.textContent = 'Your purchases are recorded below.';
    setPaidAccessState(true, orders);

    ordersList.innerHTML = orders.map(function (order, index) {
      const packageName = order.package_name || order.package_slug || 'Package';
      const priceLabel = order.price_label || 'Package recorded';
      const status = order.status || 'received';
      const createdAt = order.created_at
        ? new Date(order.created_at).toLocaleString()
        : 'Just now';

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
    if (!dashboard) return;

    const ordersStatus = doc.querySelector('[data-orders-status]');
    if (ordersStatus) {
      ordersStatus.textContent = 'Loading your purchases...';
    }

    try {
      const response = await apiRequest('/orders/my-orders', { method: 'GET' });
      const orders = Array.isArray(response) ? response : (response.orders || []);
      renderOrders(orders);
    } catch (error) {
      if (ordersStatus) {
        ordersStatus.textContent = 'Orders are not available yet. The account is ready, but the order API still needs to be connected.';
      }
      setPaidAccessState(false, []);
      console.error('Dashboard orders load failed:', error);
    }
  }

  async function recordCheckoutOrder() {
    const thankYouPage = doc.querySelector('[data-thank-you-page]');
    if (!thankYouPage) return;

    const packageNode = doc.querySelector('[data-thank-you-package]');
    const orderStatusNode = doc.querySelector('[data-thank-you-order-status]');
    const token = getToken();
    const selectedPackage = getPackageFromUrl();

    if (!selectedPackage) {
      if (packageNode) {
        packageNode.textContent = 'We could not detect the selected package from the return URL.';
      }
      if (orderStatusNode) {
        orderStatusNode.textContent = 'Order recording is waiting for a valid package redirect.';
      }
      return;
    }

    if (packageNode) {
      packageNode.textContent = `${selectedPackage.name} (${selectedPackage.price_label})`;
    }

    if (!token) {
      if (orderStatusNode) {
        orderStatusNode.textContent = 'Please sign in before purchase so your order can be attached to your account.';
      }
      return;
    }

    try {
      const response = await apiRequest('/orders/record-checkout', {
        method: 'POST',
        body: JSON.stringify({
          package_slug: selectedPackage.slug,
          package_name: selectedPackage.name,
          price_label: selectedPackage.price_label,
          source: 'stripe_payment_link',
          order_status: 'paid'
        })
      });

      const orderId = response.order_id || response.id || 'recorded';
      if (orderStatusNode) {
        orderStatusNode.textContent = `Your order has been recorded to your account successfully. Reference: ${orderId}`;
      }
    } catch (error) {
      if (orderStatusNode) {
        orderStatusNode.textContent = `Your payment page returned successfully, but the order record could not be saved yet: ${error.message}`;
      }
      console.error('Order record failed:', error);
    }
  }

  function init() {
    setupMobileMenu();
    setupCookiePreferences();
    setupMailtoForms();
    setupRequestAccessForm();
    checkBackendHealth();
    recordCheckoutOrder();
    loadDashboardOrders();

    console.log('[TOL] API_BASE_URL:', API_BASE_URL);
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();