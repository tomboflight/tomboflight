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
    const expiryDate = new Date();
    expiryDate.setTime(expiryDate.getTime() + (COOKIE_EXPIRY * 24 * 60 * 60 * 1000));
    const expires = 'expires=' + expiryDate.toUTCString();
    document.cookie = `${COOKIE_NAME}=${accepted};${expires};path=/;SameSite=Strict`;

    updateCookieStatus(accepted);
    hideCookieBanner();
  }

  function getCookiePreference() {
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
  }

  function updateCookieStatus(accepted) {
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
  }

  function hideCookieBanner() {
    if (cookieBanner) {
      cookieBanner.classList.remove('visible');
      cookieBanner.setAttribute('aria-hidden', 'true');
    }
  }

  function showCookieBanner() {
    if (cookieBanner) {
      cookieBanner.classList.add('visible');
      cookieBanner.removeAttribute('aria-hidden');
      if (acceptBtn) acceptBtn.focus();
    }
  }

  function initializeAnalytics() {
    // Add your analytics initialization code here
    // Example: Google Analytics, Mixpanel, etc.
    console.log('Analytics initialized');
  }

  // Initialize cookie preference on page load
  function initializeCookiePreference() {
    const preference = getCookiePreference();
    
    if (preference === null) {
      // No preference set, show banner
      showCookieBanner();
    } else {
      // Preference already set, update status
      updateCookieStatus(preference);
      hideCookieBanner();
    }
  }

  // Event listeners for cookie buttons
  if (acceptBtn) {
    acceptBtn.addEventListener('click', function() {
      setCookiePreference('true');
    });
  }

  if (declineBtn) {
    declineBtn.addEventListener('click', function() {
      setCookiePreference('false');
    });
  }

  // Initialize on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCookiePreference);
  } else {
    initializeCookiePreference();
  }

  // ================= SMOOTH SCROLL FALLBACK =================

  // For browsers that don't support scroll-behavior: smooth
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href !== '#' && document.querySelector(href)) {
        e.preventDefault();
        const target = document.querySelector(href);
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ================= ACTIVE LINK HIGHLIGHTING =================

  function setActiveLink() {
    const currentLocation = location.pathname;
    const navLinks = document.querySelectorAll('.site-nav a');

    navLinks.forEach(link => {
      const href = link.getAttribute('href');
      if (href === currentLocation || (currentLocation === '/' && href === 'index.html')) {
        link.classList.add('active');
        link.setAttribute('aria-current', 'page');
      } else {
        link.classList.remove('active');
        link.removeAttribute('aria-current');
      }
    });
  }

  setActiveLink();

  // ================= FORM VALIDATION =================

  function initializeFormValidation() {
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
      form.addEventListener('submit', function(e) {
        const inputs = form.querySelectorAll('input[required], textarea[required]');
        let isValid = true;

        inputs.forEach(input => {
          if (!input.value.trim()) {
            input.setAttribute('aria-invalid', 'true');
            isValid = false;
          } else {
            input.removeAttribute('aria-invalid');
          }
        });

        if (!isValid) {
          e.preventDefault();
          // Focus on first invalid field
          const firstInvalid = form.querySelector('[aria-invalid="true"]');
          if (firstInvalid) {
            firstInvalid.focus();
            firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }
      });

      // Real-time validation
      const inputs = form.querySelectorAll('input, textarea');
      inputs.forEach(input => {
        input.addEventListener('blur', function() {
          if (this.hasAttribute('required') && !this.value.trim()) {
            this.setAttribute('aria-invalid', 'true');
          } else {
            this.removeAttribute('aria-invalid');
          }
        });

        input.addEventListener('input', function() {
          if (this.value.trim()) {
            this.removeAttribute('aria-invalid');
          }
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeFormValidation);
  } else {
    initializeFormValidation();
  }

  // ================= KEYBOARD ACCESSIBILITY =================

  // Trap focus in modal-like elements (cookie banner)
  document.addEventListener('keydown', function(e) {
    if (cookieBanner && cookieBanner.classList.contains('visible') && e.key === 'Tab') {
      const focusableElements = cookieBanner.querySelectorAll(
        'button, a, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  });

  // ================= SCROLL-TO-TOP BUTTON (Optional) =================

  // Uncomment if you want a scroll-to-top button
  /*
  const scrollTopBtn = document.querySelector('[data-scroll-top]');
  if (scrollTopBtn) {
    window.addEventListener('scroll', function() {
      if (window.scrollY > 300) {
        scrollTopBtn.classList.add('visible');
      } else {
        scrollTopBtn.classList.remove('visible');
      }
    });

    scrollTopBtn.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
  */

  console.log('Tomb of Light - Accessibility features initialized');

})();