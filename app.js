// Tomb of Light Frontend JS (light theme) — nav, auth handlers, cookie consent with GPC

/* -----------------------
   Mobile Navigation Toggle
------------------------ */
const navToggle = document.getElementById("nav-toggle");
const navMenu = document.getElementById("nav-menu");
if (navToggle && navMenu) {
  navToggle.addEventListener("click", () => navMenu.classList.toggle("open"));
}

/* -----------------------
   Cookie Consent + GPC
------------------------ */
(function () {
  const KEY = "tol_cookies"; // 'accepted' | 'declined'
  const banner = document.getElementById("cookies-banner");
  const btnAccept = document.getElementById("cookies-accept");
  const btnDecline = document.getElementById("cookies-decline");

  function hasGPC() {
    try {
      return navigator.globalPrivacyControl === true;
    } catch {
      return false;
    }
  }

  function setChoice(v) {
    localStorage.setItem(KEY, v);
  }
  function getChoice() {
    if (hasGPC()) return "declined";
    return localStorage.getItem(KEY);
  }

  function showBanner() {
    if (banner) banner.classList.add("show");
  }
  function hideBanner() {
    if (banner) banner.classList.remove("show");
  }

  function maybeLoadOptional() {
    // Only load analytics/ads AFTER explicit consent
    if (getChoice() === "accepted") {
      // Example: dynamically load analytics
      // const s = document.createElement('script');
      // s.src = 'https://example-analytics.js';
      // s.async = true;
      // document.head.appendChild(s);
    }
  }

  // Init
  const choice = getChoice();
  if (!choice) showBanner();
  else hideBanner();
  maybeLoadOptional();

  // Wire buttons
  if (btnAccept)
    btnAccept.addEventListener("click", () => {
      setChoice("accepted");
      hideBanner();
      maybeLoadOptional();
    });
  if (btnDecline)
    btnDecline.addEventListener("click", () => {
      setChoice("declined");
      hideBanner();
    });
})();

/* -----------------------
   Sign-Up Form
------------------------ */
const signupForm = document.getElementById("signup-form");
if (signupForm) {
  signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = (document.getElementById("name") || {}).value?.trim();
    const email = (document.getElementById("email") || {}).value?.trim();
    const password = (document.getElementById("password") || {}).value;
    const confirm = (document.getElementById("confirm_password") || {}).value;
    const agree = (document.getElementById("agree") || {}).checked;
    const errEl = document.getElementById("confirm-error");
    if (errEl) errEl.textContent = "";

    if (!name || !email || !password || !confirm) {
      alert("Please fill out all required fields.");
      return;
    }
    if (!agree) {
      alert("You must agree to the Terms and Privacy Policy.");
      return;
    }
    if (password.length < 8) {
      alert("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      if (errEl) errEl.textContent = "Passwords do not match.";
      return;
    }

    // TODO: Replace with your backend (FastAPI/Firebase/Supabase)
    // Example FastAPI call:
    // const res = await fetch('/api/signup', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ name, email, password })
    // });
    // if (!res.ok) { const m = await res.text(); return alert(m || 'Signup failed'); }

    alert("Account created successfully! Please sign in.");
    window.location.href = "signin.html";
  });
}

/* -----------------------
   Sign-In Form
------------------------ */
const signinForm = document.getElementById("signin-form");
if (signinForm) {
  signinForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = (document.getElementById("signin-email") || {}).value?.trim();
    const password = (document.getElementById("signin-password") || {}).value;
    if (!email || !password) {
      alert("Please enter your email and password.");
      return;
    }

    // TODO: Replace with your backend (FastAPI/Firebase/Supabase)
    // const res = await fetch('/api/login', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ email, password })
    // });
    // if (!res.ok) return alert('Invalid credentials.');

    alert("Sign-in successful!");
    // window.location.href = '/dashboard.html';
    window.location.href = "index.html";
  });
}
