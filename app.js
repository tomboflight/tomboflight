/* ======== Waitlist (stub) ======== */
document.addEventListener('submit', (e)=>{
  const form = e.target.closest('form[data-waitlist]');
  if(!form) return;
  e.preventDefault();
  const email = form.querySelector('input[type="email"]')?.value?.trim();
  const name  = form.querySelector('input[name="name"]')?.value?.trim() || '';
  if(!email){ alert('Please enter a valid email.'); return; }
  // TODO: POST to your backend/ESP:
  // fetch('/api/waitlist', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name,email})})
  alert('Thanks! You’ve been added to the waitlist.');
  form.reset();
});

/* ======== Cookie banner + GPC ======== */
(function(){
  const gpc = (navigator.globalPrivacyControl === true);
  const CONSENT_KEY = 'tol_consent';

  function getConsent(){ try { return JSON.parse(localStorage.getItem(CONSENT_KEY)||'null'); } catch { return null; } }
  function setConsent(val){ localStorage.setItem(CONSENT_KEY, JSON.stringify(val)); }
  function removeAdTags(){
    document.querySelectorAll('script[data-analytics],link[data-analytics]').forEach(n=>n.remove());
  }

  let consent = getConsent();
  if(gpc){ removeAdTags(); }
  if(!consent){
    const b = document.querySelector('.cookie-banner');
    if(b){ b.style.display = 'block'; }
  }

  document.addEventListener('click', (e)=>{
    if(e.target.matches('.cookie-accept')){
      setConsent({ads:true, ts:Date.now(), gpc});
      document.querySelector('.cookie-banner')?.remove();
      // Initialize analytics here if any.
    }
    if(e.target.matches('.cookie-decline')){
      setConsent({ads:false, ts:Date.now(), gpc});
      removeAdTags();
      document.querySelector('.cookie-banner')?.remove();
    }
  });
})();
