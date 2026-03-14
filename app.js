/**
 * Tomb of Light - Main Application Script
 * Accessibility, navigation, and cookie preference handling
 */

(function () {
  'use strict';

  const doc = document;
  const body = doc.body;

  const menuToggle = doc.querySelector('.menu-toggle');
  const siteNav = doc.querySelector('#site-nav');
  const siteHeader = doc.querySelector('.site-header');

  const cookieBanner = doc.querySelector('[data-cookie-banner]');
  const cookieStatus = doc.querySelector('[data-cookie-status]');
  const acceptBtn = doc.querySelector('[data-cookie-accept]');
  const declineBtn = doc.querySelector('[data-cookie-decline]');

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
      // Place analytics initialization here when ready.
      console.log('Analytics initialized');
    } catch (error) {
      console.error('Analytics initialization failed:', error);
    }
  }

  function updateCookieStatus(preference) {
    if (!cookieStatus) return;

    if (preference === 'true') {
      cookieStatus.textContent = 'Analytics cookies are enabled.';
      initializeAnalytics();
    } else if (preference === 'false') {
      cookieStatus.textContent = 'Analytics cookies are disabled.';
    } else {
      cookieStatus.textContent = 'Your cookie preference has not been set yet.';
    }
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

  function init() {
    setupMobileMenu();
    setupCookiePreferences();
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
