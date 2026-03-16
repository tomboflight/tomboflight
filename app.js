/**
 * Tomb of Light - Main Application Script
 * Accessibility, navigation, cookie preference handling,
 * backend connectivity, and request access form submission
 */

(function () {
  'use strict';

  const doc = document;
  const body = doc.body;

  const API_BASE_URL = 'https://tomboflight-api.onrender.com';

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
        const body = buildMailtoBody(form);
        const params = new URLSearchParams({
          subject: subject,
          body: body
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

  function init() {
    setupMobileMenu();
    setupCookiePreferences();
    setupMailtoForms();
    setupRequestAccessForm();
    checkBackendHealth();
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
