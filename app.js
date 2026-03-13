/**
 * Tomb of Light - Main Application Script
 * Accessibility & UX Enhancements
 */

(function() {
  'use strict';

  // ================= MOBILE MENU TOGGLE =================

  const menuToggle = document.querySelector('.menu-toggle');
  const siteNav = document.querySelector('#site-nav');
  const siteHeader = document.querySelector('.site-header');

  if (menuToggle && siteNav) {
    menuToggle.addEventListener('click', function() {
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      
      menuToggle.setAttribute('aria-expanded', !isExpanded);
      siteHeader.classList.toggle('open');
      document.body.classList.toggle('menu-open');

      // Close menu when a link is clicked
      const navLinks = siteNav.querySelectorAll('a');
      navLinks.forEach(link => {
        link.addEventListener('click', closeMenu);
      });
    });

    // Close menu on Escape key
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
        closeMenu();
      }
    });

    function closeMenu() {
      menuToggle.setAttribute('aria-expanded', 'false');
      siteHeader.classList.remove('open');
      document.body.classList.remove('menu-open');
    }
  }

  // ================= COOKIE BANNER MANAGEMENT =================

  const cookieBanner = document.querySelector('[data-cookie-banner]');
  const cookieStatus = document.querySelector('[data-cookie-status]');
  const acceptBtn = document.querySelector('[data-cookie-accept]');
  const declineBtn = document.querySelector('[data-cookie-decline]');
  const COOKIE_NAME = 'tol_cookie_preference';
  const COOKIE_EXPIRY = 365; // days

  function setCookiePreference(accepted) {
    try {
      const expiryDate = new Date();
      expiryDate.setTime(expiryDate.getTime() + (COOKIE_EXPIRY * 24 * 60 * 60 * 1000));
      const expires = 'expires=' + expiryDate.toUTCString();
      document.cookie = `${COOKIE_NAME}=${accepted};${expires};path=/;SameSite=Strict`;

      updateCookieStatus(accepted);
      hideCookieBanner();
      console.log('Cookie preference saved:', accepted);
    } catch (error) {
      console.error('Error setting cookie preference:', error);
    }
  }

  function getCookiePreference() {
    try {
      const name = COOKIE_NAME + '=';
      const decodedCookie = decodeURIComponent(document.cookie);
      const cookieArray = decodedCookie.split(';');

      for (let cookie of cookieArray) {
        cookie = cookie.trim();
        if (cookie.indexOf(name) === 0) {
          return cookie.substring(name.length, cookie.length);
        }
      }

      return null;
    } catch (error) {
      console.error('Error reading cookie preference:', error);
      return null;
    }
  }

  function updateCookieStatus(accepted) {
    try {
      if (cookieStatus) {
        if (accepted === 'true') {
          cookieStatus.textContent = 'Analytics cookies are enabled.';
        } else {
          cookieStatus.textContent = 'Analytics cookies are disabled.';
        }
      }

      // Initialize analytics if accepted
      if (accepted === 'true') {
        initializeAnalytics();
      }
    } catch (error) {
      console.error('Error updating cookie status:', error);
    }
  }

  function hideCookieBanner() {
    try {
      if (cookieBanner) {
        cookieBanner.classList.remove('visible');
        cookieBanner.setAttribute('aria-hidden', 'true');
      }
    } catch (error) {
      console.error('Error hiding cookie banner:', error);
    }
  }

  function showCookieBanner() {
    try {
      if (cookieBanner) {
        cookieBanner.classList.add('visible');
        cookieBanner.removeAttribute('aria-hidden');
        if (acceptBtn) acceptBtn.focus();
      }
    } catch (error) {
      console.error('Error showing cookie banner:', error);
    }
  }

  function initializeAnalytics() {
    try {
      // Add your analytics initialization code here
      // Example: Google Analytics, Mixpanel, etc.
      console.log('Analytics initialized');
    } catch (error) {
      console.error('Error initializing analytics:', error);
    }
  }

  // Initialize cookie preference on page load
  function initializeCookiePreference() {
    try {
      const preference = getCookiePreference();
      
      if (preference) {
        updateCookieStatus(preference);
      } else {
        // Show banner if no preference is set
        showCookieBanner();
      }
    } catch (error) {
      console.error('Error initializing cookie preference:', error);
    }
  }

  // Add event listeners to cookie buttons
  function setupCookieListeners() {
    try {
      if (acceptBtn) {
        acceptBtn.addEventListener('click', function(e) {
          e.preventDefault();
          setCookiePreference('true');
        });
      }

      if (declineBtn) {
        declineBtn.addEventListener('click', function(e) {
          e.preventDefault();
          setCookiePreference('false');
        });
      }
    } catch (error) {
      console.error('Error setting up cookie listeners:', error);
    }
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      initializeCookiePreference();
      setupCookieListeners();
    });
  } else {
    initializeCookiePreference();
    setupCookieListeners();
  }

})();
