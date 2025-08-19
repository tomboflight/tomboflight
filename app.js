// Simple consent + "Your Privacy Choices" handling (no analytics loaded here)
const CONSENT_KEY = 'tol-consent'; // values: 'accepted'|'declined'|'essential'

function showCookieBanner(){
  const el = document.getElementById('cookie-banner');
  if(!el) return;
  const v = localStorage.getItem(CONSENT_KEY);
  if(!v){ el.style.display = 'flex'; }
}

function setConsent(value){
  localStorage.setItem(CONSENT_KEY, value);
  const el = document.getElementById('cookie-banner');
  if(el) el.style.display='none';
}

// Expose to Privacy Choices page
window.tolConsent = {
  get:()=>localStorage.getItem(CONSENT_KEY)||'',
  set:setConsent,
  clear:()=>localStorage.removeItem(CONSENT_KEY)
};

document.addEventListener('DOMContentLoaded', showCookieBanner);
