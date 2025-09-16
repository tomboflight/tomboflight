// app.js — consent helper with GPC support + cookie banner hooks

(function () {
  const KEY = 'tol_cookies'; // 'accepted' | 'declined'
  const MODAL_KEY = 'tol_waitlist_modal_dismissed'; // used on index.html

  function hasGPC() {
    try { return navigator.globalPrivacyControl === true; }
    catch { return false; }
  }

  // Public API used by privacy-choices.html and the cookie banner
  window.tolConsent = {
    get() {
      if (hasGPC()) return 'declined';          // respect GPC: treat as essential-only
      return localStorage.getItem(KEY) || 'essential';
    },
    set(v) {
      try { localStorage.setItem(KEY, v); } catch {}
      updateCookieBanner();
    },
    clear() {
      try { localStorage.removeItem(KEY); } catch {}
      updateCookieBanner();
    }
  };

  // ----- Cookie banner control (index.html expects this) -----
  function updateCookieBanner() {
    const el = document.getElementById('cookie-banner');
    if (!el) return;

    const pref = window.tolConsent.get();
    // Show banner if no explicit choice and no GPC
    if (pref === 'essential' && !hasGPC()) {
      el.style.display = 'flex';
    } else {
      el.style.display = 'none';
    }
  }

  // Initialize on load
  document.addEventListener('DOMContentLoaded', updateCookieBanner);

  // Optional: if you use the waitlist modal, expose helpers
  window.tolModal = {
    dismiss() {
      try { localStorage.setItem(MODAL_KEY, '1'); } catch {}
    }
  };
})();
