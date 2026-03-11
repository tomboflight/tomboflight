// Tomb of Light Frontend JS
// Handles: mobile nav, cookie consent (including GPC), privacy choices page,
// signup validation, and signin placeholder flow.

/* =========================
   Mobile Navigation
========================= */
(function () {
  const navToggle = document.getElementById('nav-toggle');
  const navMenu = document.getElementById('nav-menu');

  if (!navToggle || !navMenu) return;

  function setMenuState(isOpen) {
    navMenu.classList.toggle('open', isOpen);
    navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  navToggle.addEventListener('click', () => {
    const isOpen = !navMenu.classList.contains('open');
    setMenuState(isOpen);
  });

  // Close menu when a link is clicked
  navMenu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 900) {
        setMenuState(false);
      }
    });
  });

  // Close menu when clicking outside
  document.addEventListener('click', (event) => {
    const clickedInsideMenu = navMenu.contains(event.target);
    const clickedToggle = navToggle.contains(event.target);

    if (!clickedInsideMenu && !clickedToggle && navMenu.classList.contains('open')) {
      setMenuState(false);
    }
  });

  // Reset menu state on resize to desktop
  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) {
      navMenu.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
    }
  });
})();

/* =========================
   Cookie Consent + GPC
========================= */
(function () {
  const KEY = 'tol_cookies'; // accepted | declined
  const banner = document.getElementById('cookies-banner');
  const btnAccept = document.getElementById('cookies-accept');
  const btnDecline = document.getElementById('cookies-decline');

  function hasGPC() {
    try {
      return navigator.globalPrivacyControl === true;
    } catch (error) {
      return false;
    }
  }

  function setChoice(value) {
    localStorage.setItem(KEY, value);
  }

  function getChoice() {
    if (hasGPC()) return 'declined';
    return localStorage.getItem(KEY);
  }

  function clearChoice() {
    localStorage.removeItem(KEY);
  }

  function showBanner() {
    if (banner) banner.classList.add('show');
  }

  function hideBanner() {
    if (banner) banner.classList.remove('show');
  }

  function maybeLoadOptional() {
    if (getChoice() === 'accepted') {
      // Optional scripts go here only AFTER explicit consent.
      // Example:
      // const s = document.createElement('script');
      // s.src = 'https://analytics.example.com/script.js';
      // s.async = true;
      // document.head.appendChild(s);
    }
  }

  // Expose helper globally for privacy-choices.html
  window.tolConsent = {
    set(value) {
      setChoice(value);
      maybeLoadOptional();
    },
    get() {
      return getChoice();
    },
    clear() {
      clearChoice();
    },
    hasGPC() {
      return hasGPC();
    }
  };

  const currentChoice = getChoice();

  if (!currentChoice) {
    showBanner();
  } else {
    hideBanner();
  }

  maybeLoadOptional();

  if (btnAccept) {
    btnAccept.addEventListener('click', () => {
      setChoice('accepted');
      hideBanner();
      maybeLoadOptional();
    });
  }

  if (btnDecline) {
    btnDecline.addEventListener('click', () => {
      setChoice('declined');
      hideBanner();
    });
  }
})();

/* =========================
   Sign-Up Form
========================= */
(function () {
  const signupForm = document.getElementById('signup-form');
  if (!signupForm) return;

  signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = document.getElementById('name')?.value?.trim() || '';
    const email = document.getElementById('email')?.value?.trim() || '';
    const password = document.getElementById('password')?.value || '';
    const confirm = document.getElementById('confirm_password')?.value || '';
    const agree = document.getElementById('agree')?.checked || false;
    const errEl = document.getElementById('confirm-error');

    if (errEl) errEl.textContent = '';

    if (!name || !email || !password || !confirm) {
      alert('Please fill out all required fields.');
      return;
    }

    if (!agree) {
      alert('You must agree to the Terms and Privacy Policy.');
      return;
    }

    if (password.length < 8) {
      alert('Password must be at least 8 characters.');
      return;
    }

    if (password !== confirm) {
      if (errEl) errEl.textContent = 'Passwords do not match.';
      return;
    }

    try {
      // Future backend hookup example:
      // const res = await fetch('/api/signup', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ name, email, password })
      // });
      //
      // if (!res.ok) {
      //   const message = await res.text();
      //   throw new Error(message || 'Signup failed');
      // }

      alert('Account created successfully! Please sign in.');
      window.location.href = 'signin.html';
    } catch (error) {
      alert(error.message || 'Signup failed. Please try again.');
    }
  });
})();

/* =========================
   Sign-In Form
========================= */
(function () {
  const signinForm = document.getElementById('signin-form');
  if (!signinForm) return;

  signinForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('signin-email')?.value?.trim() || '';
    const password = document.getElementById('signin-password')?.value || '';

    if (!email || !password) {
      alert('Please enter your email and password.');
      return;
    }

    try {
      // Future backend hookup example:
      // const res = await fetch('/api/login', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ email, password })
      // });
      //
      // if (!res.ok) {
      //   throw new Error('Invalid credentials');
      // }

      alert('Sign-in successful!');
      window.location.href = 'index.html';
    } catch (error) {
      alert(error.message || 'Sign-in failed. Please try again.');
    }
  });
})();