/**
 * Tomb of Light - Main Application Script
 * Accessibility, navigation, cookie preference handling,
 * backend connectivity, request access form submission,
 * thank-you order recording, dashboard order loading,
 * paid-access gating, intake onboarding routing,
 * and backend intake submission.
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
      price_label: '$399',
      summary: 'Portrait-focused onboarding with uploads, consent, and NFT/share preparation.',
      steps: [
        'Household / buyer setup',
        'Upload collection',
        'Consent and visibility',
        'Review and submit'
      ]
    },
    'starter-family-tree': {
      slug: 'starter-family-tree',
      name: 'Starter Family Tree',
      price_label: '$799',
      summary: 'Small family onboarding with household setup, family map, and first lineage structure.',
      steps: [
        'Household setup',
        'Family map',
        'Uploads',
        'Consent',
        'Review and submit'
      ]
    },
    'heirloom-legacy-tree': {
      slug: 'heirloom-legacy-tree',
      name: 'Heirloom Legacy Tree',
      price_label: '$1,500',
      summary: 'Multi-generation onboarding with deeper family mapping, narrative, and verification preparation.',
      steps: [
        'Household setup',
        'Family map',
        'Relationships',
        'Uploads',
        'Consent',
        'Verification and narrative',
        'Review and submit'
      ]
    },
    'legacy-plus': {
      slug: 'legacy-plus',
      name: 'Legacy Plus',
      price_label: '$3,200',
      summary: 'Expanded archive onboarding for larger families with broader scope and deeper preparation.',
      steps: [
        'Household setup',
        'Family map',
        'Relationships',
        'Uploads',
        'Consent',
        'Verification and narrative',
        'Expanded archive review',
        'Review and submit'
      ]
    },
    'family-estate-concierge': {
      slug: 'family-estate-concierge',
      name: 'Family Estate Concierge',
      price_label: '$6,500–$12,000',
      summary: 'White-glove onboarding for advanced household and branch-based legacy projects.',
      steps: [
        'Household setup',
        'Family branch planning',
        'Uploads and archive intake',
        'Consent and privacy review',
        'Verification and narrative planning',
        'Concierge review and submit'
      ]
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
      price_label: 'Package selected',
      summary: 'Package-aware onboarding is being prepared for this order.',
      steps: ['Household setup', 'Review and submit']
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

    if (!ordersList || !ordersStatus) return [];

    if (!Array.isArray(orders) || !orders.length) {
      ordersStatus.textContent = 'No purchases have been recorded yet.';
      ordersList.innerHTML = '';
      setPaidAccessState(false, []);
      return [];
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

    return orders;
  }

  async function loadDashboardOrders() {
    const dashboard = doc.querySelector('[data-dashboard]');
    if (!dashboard) return [];

    const ordersStatus = doc.querySelector('[data-orders-status]');
    if (ordersStatus) {
      ordersStatus.textContent = 'Loading your purchases...';
    }

    try {
      const response = await apiRequest('/orders/my-orders', { method: 'GET' });
      const orders = Array.isArray(response) ? response : (response.orders || []);
      return renderOrders(orders);
    } catch (error) {
      if (ordersStatus) {
        ordersStatus.textContent = 'Orders are not available yet. The account is ready, but the order API still needs to be connected.';
      }
      setPaidAccessState(false, []);
      console.error('Dashboard orders load failed:', error);
      return [];
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

  async function setupIntakeWelcome() {
    const intakePage = doc.querySelector('[data-intake-welcome]');
    if (!intakePage) return;

    const statusNode = doc.querySelector('[data-intake-status]');
    const packageNameNode = doc.querySelector('[data-package-name]');
    const packageSummaryNode = doc.querySelector('[data-package-summary]');
    const packagePathNode = doc.querySelector('[data-package-path]');
    const startButton = doc.querySelector('[data-intake-start]');
    const token = getToken();

    if (!token) {
      if (statusNode) {
        statusNode.textContent = 'Please sign in to continue your intake.';
      }
      if (startButton) {
        startButton.setAttribute('href', 'signin.html');
        startButton.textContent = 'Sign In';
      }
      return;
    }

    try {
      const response = await apiRequest('/orders/my-orders', { method: 'GET' });
      const orders = Array.isArray(response) ? response : (response.orders || []);
      const firstOrder = Array.isArray(orders) && orders.length ? orders[0] : null;

      if (!firstOrder) {
        if (statusNode) {
          statusNode.textContent = 'No paid package was found for this account. Purchase a package to begin intake.';
        }
        if (packageNameNode) {
          packageNameNode.textContent = 'No active package found';
        }
        if (packageSummaryNode) {
          packageSummaryNode.textContent = 'Your account does not yet have an unlocked onboarding path.';
        }
        if (packagePathNode) {
          packagePathNode.innerHTML = `
            <div>
              <div class="card-number">!</div>
              <h3>Purchase required</h3>
              <p class="card-copy">
                Buy a package first so Tomb of Light can unlock your guided onboarding flow.
              </p>
            </div>
          `;
        }
        if (startButton) {
          startButton.setAttribute('href', 'index.html#pricing');
          startButton.textContent = 'View Packages';
        }
        return;
      }

      const pkg = PACKAGE_CATALOG[firstOrder.package_slug] || {
        name: firstOrder.package_name || 'Purchased Package',
        price_label: firstOrder.price_label || '',
        summary: 'Your package-specific onboarding is being prepared.',
        steps: ['Household setup', 'Review and submit']
      };

      if (statusNode) {
        statusNode.textContent = 'Your paid onboarding path is unlocked and ready.';
      }

      if (packageNameNode) {
        packageNameNode.textContent = `${pkg.name}${pkg.price_label ? ` — ${pkg.price_label}` : ''}`;
      }

      if (packageSummaryNode) {
        packageSummaryNode.textContent = pkg.summary;
      }

      if (packagePathNode) {
        packagePathNode.innerHTML = pkg.steps.map(function (step, index) {
          const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
          return `
            <div>
              <div class="card-number">${labels[index] || index + 1}</div>
              <h3>${step}</h3>
              <p class="card-copy">
                This step is part of your purchased Tomb of Light onboarding path.
              </p>
            </div>
          `;
        }).join('');
      }

      if (startButton) {
        startButton.setAttribute('href', 'intake-household.html');
        startButton.textContent = 'Start Intake';
      }
    } catch (error) {
      console.error('Intake welcome setup failed:', error);

      if (statusNode) {
        statusNode.textContent = 'We could not load your intake path right now. Please try again.';
      }

      if (packageNameNode) {
        packageNameNode.textContent = 'Intake unavailable';
      }

      if (packageSummaryNode) {
        packageSummaryNode.textContent = 'Your package details could not be loaded from the platform.';
      }
    }
  }

  function setLocalIntakeData(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('[TOL intake] failed to save local intake data:', error);
    }
  }

  function getLocalIntakeData(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function getCurrentPackageFromOrders() {
    try {
      const raw = localStorage.getItem('tol_current_order');
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function setCurrentPackageFromOrders(orders) {
    try {
      const firstOrder = Array.isArray(orders) && orders.length ? orders[0] : null;
      if (!firstOrder) return;

      const packageData = {
        package_slug: firstOrder.package_slug || '',
        package_name: firstOrder.package_name || '',
        price_label: firstOrder.price_label || ''
      };

      localStorage.setItem('tol_current_order', JSON.stringify(packageData));
    } catch (error) {
      console.error('[TOL intake] failed to save current order:', error);
    }
  }

  function setupIntakeHousehold() {
    const householdPage = doc.querySelector('[data-intake-household]');
    if (!householdPage) return;

    const form = doc.querySelector('[data-household-form]');
    const statusNode = doc.querySelector('[data-household-form-status]');
    const submitBtn = doc.querySelector('[data-household-submit-btn]');

    if (!form) return;

    const saved = getLocalIntakeData('tol_intake_household');
    if (saved) {
      Object.keys(saved).forEach(function (key) {
        const field = form.elements[key];
        if (field) {
          field.value = saved[key] || '';
        }
      });
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();

      if (statusNode) {
        statusNode.style.display = 'none';
        statusNode.textContent = '';
      }

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);

      const payload = {
        household_name: String(formData.get('household_name') || '').trim(),
        primary_contact_name: String(formData.get('primary_contact_name') || '').trim(),
        primary_contact_email: String(formData.get('primary_contact_email') || '').trim(),
        primary_contact_phone: String(formData.get('primary_contact_phone') || '').trim(),
        co_owner_name: String(formData.get('co_owner_name') || '').trim(),
        household_role: String(formData.get('household_role') || '').trim(),
        project_scope: String(formData.get('project_scope') || '').trim(),
        special_notes: String(formData.get('special_notes') || '').trim()
      };

      setLocalIntakeData('tol_intake_household', payload);

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saved';
      }

      if (statusNode) {
        statusNode.style.display = 'block';
        statusNode.textContent = 'Household setup saved locally. You can continue to the Family Map step.';
        statusNode.dataset.state = 'success';
        statusNode.style.color = '#cfe8cf';
      }

      setTimeout(function () {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Household Setup';
        }
      }, 800);
    });
  }

  function setupIntakeFamilyMap() {
    const familyMapPage = doc.querySelector('[data-intake-family-map]');
    if (!familyMapPage) return;

    const form = doc.querySelector('[data-family-map-form]');
    const statusNode = doc.querySelector('[data-family-map-form-status]');
    const submitBtn = doc.querySelector('[data-family-map-submit-btn]');

    if (!form) return;

    const saved = getLocalIntakeData('tol_intake_family_map');
    if (saved) {
      Object.keys(saved).forEach(function (key) {
        const field = form.elements[key];
        if (field) {
          field.value = saved[key] || '';
        }
      });
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();

      if (statusNode) {
        statusNode.style.display = 'none';
        statusNode.textContent = '';
      }

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);

      const payload = {
        family_branch_name: String(formData.get('family_branch_name') || '').trim(),
        people_in_scope: String(formData.get('people_in_scope') || '').trim(),
        parent_one: String(formData.get('parent_one') || '').trim(),
        parent_two: String(formData.get('parent_two') || '').trim(),
        spouse_partner: String(formData.get('spouse_partner') || '').trim(),
        children_names: String(formData.get('children_names') || '').trim(),
        family_structure_summary: String(formData.get('family_structure_summary') || '').trim(),
        branch_notes: String(formData.get('branch_notes') || '').trim()
      };

      setLocalIntakeData('tol_intake_family_map', payload);

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saved';
      }

      if (statusNode) {
        statusNode.style.display = 'block';
        statusNode.textContent = 'Family map saved locally. You can continue to the Review step.';
        statusNode.dataset.state = 'success';
        statusNode.style.color = '#cfe8cf';
      }

      setTimeout(function () {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Family Map';
        }
      }, 800);
    });
  }

  function setupIntakeReview() {
    const reviewPage = doc.querySelector('[data-intake-review]');
    if (!reviewPage) return;

    const householdSummaryNode = doc.querySelector('[data-review-household-summary]');
    const familyMapSummaryNode = doc.querySelector('[data-review-family-map-summary]');
    const form = doc.querySelector('[data-intake-review-form]');
    const statusNode = doc.querySelector('[data-intake-review-form-status]');
    const submitBtn = doc.querySelector('[data-intake-review-submit-btn]');

    const household = getLocalIntakeData('tol_intake_household');
    const familyMap = getLocalIntakeData('tol_intake_family_map');
    const savedReview = getLocalIntakeData('tol_intake_review');

    if (householdSummaryNode) {
      if (household) {
        householdSummaryNode.innerHTML = `
          <div>
            <div class="card-number">1</div>
            <h3>${household.household_name || 'Household not named'}</h3>
            <p class="card-copy"><strong>Primary Contact:</strong> ${household.primary_contact_name || '—'}</p>
            <p class="card-copy"><strong>Email:</strong> ${household.primary_contact_email || '—'}</p>
            <p class="card-copy"><strong>Phone:</strong> ${household.primary_contact_phone || '—'}</p>
            <p class="card-copy"><strong>Co-Owner / Spouse:</strong> ${household.co_owner_name || '—'}</p>
            <p class="card-copy"><strong>Role:</strong> ${household.household_role || '—'}</p>
          </div>
          <div>
            <div class="card-number">2</div>
            <h3>Project Scope</h3>
            <p class="card-copy">${household.project_scope || '—'}</p>
            <p class="card-copy"><strong>Special Notes:</strong> ${household.special_notes || 'None provided'}</p>
          </div>
        `;
      } else {
        householdSummaryNode.innerHTML = `
          <div>
            <div class="card-number">1</div>
            <h3>No household data saved</h3>
            <p class="card-copy">Complete the Household Setup step before reviewing your intake.</p>
          </div>
        `;
      }
    }

    if (familyMapSummaryNode) {
      if (familyMap) {
        familyMapSummaryNode.innerHTML = `
          <div>
            <div class="card-number">3</div>
            <h3>${familyMap.family_branch_name || 'Unnamed branch'}</h3>
            <p class="card-copy"><strong>People in Scope:</strong> ${familyMap.people_in_scope || '—'}</p>
            <p class="card-copy"><strong>Parent One:</strong> ${familyMap.parent_one || '—'}</p>
            <p class="card-copy"><strong>Parent Two:</strong> ${familyMap.parent_two || '—'}</p>
            <p class="card-copy"><strong>Spouse / Partner:</strong> ${familyMap.spouse_partner || '—'}</p>
            <p class="card-copy"><strong>Children:</strong> ${familyMap.children_names || '—'}</p>
          </div>
          <div>
            <div class="card-number">4</div>
            <h3>Structure Notes</h3>
            <p class="card-copy"><strong>Summary:</strong> ${familyMap.family_structure_summary || '—'}</p>
            <p class="card-copy"><strong>Branch Notes:</strong> ${familyMap.branch_notes || 'None provided'}</p>
          </div>
        `;
      } else {
        familyMapSummaryNode.innerHTML = `
          <div>
            <div class="card-number">2</div>
            <h3>No family map saved</h3>
            <p class="card-copy">Complete the Family Map step before reviewing your intake.</p>
          </div>
        `;
      }
    }

    if (!form) return;

    if (savedReview) {
      if (form.elements.final_intake_notes) {
        form.elements.final_intake_notes.value = savedReview.final_intake_notes || '';
      }
      if (form.elements.confirm_accuracy) {
        form.elements.confirm_accuracy.checked = !!savedReview.confirm_accuracy;
      }
    }

    form.addEventListener('submit', async function (event) {
      event.preventDefault();

      if (statusNode) {
        statusNode.style.display = 'none';
        statusNode.textContent = '';
      }

      if (!household || !familyMap) {
        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.textContent = 'Complete the Household and Family Map steps before saving the review step.';
          statusNode.dataset.state = 'error';
          statusNode.style.color = '#ffb3b3';
        }
        return;
      }

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);

      const reviewPayload = {
        final_intake_notes: String(formData.get('final_intake_notes') || '').trim(),
        confirm_accuracy: !!form.elements.confirm_accuracy.checked
      };

      setLocalIntakeData('tol_intake_review', reviewPayload);

      if (!reviewPayload.confirm_accuracy) {
        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.textContent = 'You must confirm the intake accuracy before submitting.';
          statusNode.dataset.state = 'error';
          statusNode.style.color = '#ffb3b3';
        }
        return;
      }

      const currentOrder = getCurrentPackageFromOrders();

      if (!currentOrder || !currentOrder.package_slug || !currentOrder.package_name) {
        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.textContent = 'No package was found for this intake. Return to your dashboard and refresh your order data.';
          statusNode.dataset.state = 'error';
          statusNode.style.color = '#ffb3b3';
        }
        return;
      }

      const payload = {
        package_slug: currentOrder.package_slug,
        package_name: currentOrder.package_name,
        household: household,
        family_map: familyMap,
        review: reviewPayload
      };

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Submitting...';
        }

        const response = await apiRequest('/intake-submissions', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        setLocalIntakeData('tol_intake_submission_result', response);

        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.textContent =
            `Intake submitted successfully. Submission ID: ${response.id}`;
          statusNode.dataset.state = 'success';
          statusNode.style.color = '#cfe8cf';
        }

        if (submitBtn) {
          submitBtn.textContent = 'Submitted';
        }
      } catch (error) {
        console.error('Intake submission failed:', error);

        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.textContent =
            error.message || 'Intake submission failed. Please try again.';
          statusNode.dataset.state = 'error';
          statusNode.style.color = '#ffb3b3';
        }

        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Review Step';
        }
        return;
      }

      setTimeout(function () {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Save Review Step';
        }
      }, 1200);
    });
  }

  async function primeCurrentOrderCache() {
    try {
      const response = await apiRequest('/orders/my-orders', { method: 'GET' });
      const orders = Array.isArray(response) ? response : (response.orders || []);
      setCurrentPackageFromOrders(orders);
    } catch (error) {
      console.error('[TOL intake] could not prime current order cache:', error);
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
    primeCurrentOrderCache();
    setupIntakeWelcome();
    setupIntakeHousehold();
    setupIntakeFamilyMap();
    setupIntakeReview();

    console.log('[TOL] API_BASE_URL:', API_BASE_URL);
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();