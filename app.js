// Tomb of Light Frontend JS — nav, cookie consent (GPC), and auth handlers

/* Mobile Navigation */
const navToggle = document.getElementById('nav-toggle');
const navMenu = document.getElementById('nav-menu');
if (navToggle && navMenu) {
  navToggle.addEventListener('click', () => {
    const opened = navMenu.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', opened ? 'true' : 'false');
  });
}

/* Cookie Consent + Global Privacy Control */
(function () {
  const KEY = 'tol_cookies'; // 'accepted' | 'declined'
  const banner = document.getElementById('cookies-banner');
  const btnAccept = document.getElementById('cookies-accept');
  const btnDecline = document.getElementById('cookies-decline');

  function hasGPC() {
    try { return navigator.globalPrivacyControl === true; } catch { return false; }
  }

  function setChoice(v) { localStorage.setItem(KEY, v); }
  function getChoice() { return hasGPC() ? 'declined' : localStorage.getItem(KEY); }

  function showBanner() { if (banner) banner.classList.add('show'); }
  function hideBanner() { if (banner) banner.classList.remove('show'); }

  function maybeLoadOptional() {
    if (getChoice() === 'accepted') {
      // Example: dynamically load analytics only after consent
      // const s = document.createElement('script');
      // s.src = 'https://analytics.example.com/script.js';
      // s.async = true;
      // document.head.appendChild(s);
    }
  }

  const choice = getChoice();
  if (!choice) showBanner(); else hideBanner();
  maybeLoadOptional();

  if (btnAccept) btnAccept.addEventListener('click', () => { setChoice('accepted'); hideBanner(); maybeLoadOptional(); });
  if (btnDecline) btnDecline.addEventListener('click', () => { setChoice('declined'); hideBanner(); });
})();

/* Sign-Up */
const signupForm = document.getElementById('signup-form');
if (signupForm) {
  signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('name')?.value?.trim();
    const email = document.getElementById('email')?.value?.trim();
    const password = document.getElementById('password')?.value;
    const confirm = document.getElementById('confirm_password')?.value;
    const agree = document.getElementById('agree')?.checked;
    const errEl = document.getElementById('confirm-error');
    if (errEl) errEl.textContent = '';

    if (!name || !email || !password || !confirm) return alert('Please fill out all required fields.');
    if (!agree) return alert('You must agree to the Terms and Privacy Policy.');
    if (password.length < 8) return alert('Password must be at least 8 characters.');
    if (password !== confirm) { if (errEl) errEl.textContent = 'Passwords do not match.'; return; }

    // TODO: hook to backend (FastAPI/Firebase/Supabase)
    // const res = await fetch('/api/signup', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ name,email,password }) });
    // if (!res.ok) return alert(await res.text() || 'Signup failed');

    alert('Account created successfully! Please sign in.');
    window.location.href = 'signin.html';
  });
}

/* Sign-In */
const signinForm = document.getElementById('signin-form');
if (signinForm) {
  signinForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('signin-email')?.value?.trim();
    const password = document.getElementById('signin-password')?.value;
    if (!email || !password) return alert('Please enter your email and password.');

    // TODO: hook to backend
    // const res = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ email,password }) });
    // if (!res.ok) return alert('Invalid credentials');

    alert('Sign-in successful!');
    window.location.href = 'index.html';
  });
}
