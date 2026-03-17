:root {
  --bg: #03060d;
  --bg-soft: #07101d;
  --panel: rgba(10, 16, 28, 0.82);
  --panel-2: rgba(7, 12, 22, 0.92);
  --panel-3: rgba(255, 255, 255, 0.025);
  --border: rgba(255, 255, 255, 0.1);
  --border-soft: rgba(255, 255, 255, 0.06);
  --border-strong: rgba(214, 176, 102, 0.24);
  --text: #f4f7fb;
  --muted: #c8d1e0;
  --muted-2: #8d9aae;
  --gold: #d6b066;
  --white-btn: #f4f5f8;
  --white-btn-text: #12161f;
  --shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
  --radius: 28px;
  --radius-sm: 18px;
  --container: 1240px;
  --transition: 180ms ease;
}

*,
*::before,
*::after { box-sizing: border-box; }

html { scroll-behavior: smooth; }

body {
  margin: 0;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(21, 48, 108, 0.12), transparent 28%),
    radial-gradient(circle at top right, rgba(7, 20, 58, 0.14), transparent 30%),
    linear-gradient(180deg, #010309 0%, #04070e 44%, #02050b 100%);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.6;
  min-height: 100vh;
  position: relative;
}

body.menu-open { overflow: hidden; }

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

.skip-to-content {
  position: absolute;
  left: -9999px;
  top: auto;
  width: 1px;
  height: 1px;
  overflow: hidden;
}
.skip-to-content:focus {
  left: 16px;
  top: 16px;
  width: auto;
  height: auto;
  overflow: visible;
  background: var(--white-btn);
  color: var(--white-btn-text);
  padding: 12px 18px;
  z-index: 9999;
  font-weight: 700;
  border-radius: 12px;
  outline: 2px solid var(--gold);
  outline-offset: 2px;
  text-decoration: none;
}

.site-watermark {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image: url("images/tol-watermark-clean.png");
  background-repeat: no-repeat;
  background-position: center center;
  background-size: 700px;
  opacity: 0.18;
  filter: brightness(1.32) contrast(1.08);
}

img { max-width: 100%; display: block; }
a { color: inherit; text-decoration: none; }
button, input, textarea, select { font: inherit; }

.container { width: min(var(--container), calc(100% - 40px)); margin: 0 auto; }

.page-wrap { min-height: 100vh; position: relative; z-index: 1; }

.site-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  backdrop-filter: blur(18px);
  background: rgba(2, 6, 14, 0.76);
  border-bottom: 1px solid var(--border-soft);
}

.site-header-inner {
  min-height: 88px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 1.85rem;
  font-weight: 800;
  letter-spacing: -0.045em;
  white-space: nowrap;
}
.brand:focus {
  outline: 2px solid var(--gold);
  outline-offset: 4px;
  border-radius: 8px;
}
.brand-symbol { font-size: 0.8em; vertical-align: super; }

.site-nav {
  display: flex;
  align-items: center;
  gap: 30px;
  margin-left: auto;
}
.site-nav a {
  color: var(--muted);
  font-weight: 600;
  transition: color var(--transition);
  position: relative;
}
.site-nav a:hover,
.site-nav a.active { color: var(--text); }
.site-nav a:focus {
  outline: 2px solid var(--gold);
  outline-offset: 4px;
  border-radius: 4px;
}

.header-actions { display: flex; align-items: center; gap: 14px; }

.menu-toggle {
  display: none;
  appearance: none;
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 14px;
  cursor: pointer;
  font-weight: 600;
  transition: all var(--transition);
}
.menu-toggle:hover {
  border-color: rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
}
.menu-toggle:focus { outline: 2px solid var(--gold); outline-offset: 2px; }
.menu-toggle[aria-expanded="true"] { background: rgba(255, 255, 255, 0.1); border-color: var(--border); }

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 54px;
  padding: 0 24px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text);
  background: rgba(255, 255, 255, 0.03);
  font-weight: 700;
  transition: transform var(--transition), background var(--transition), border-color var(--transition), color var(--transition), box-shadow var(--transition);
  cursor: pointer;
}
.btn:hover { transform: translateY(-1px); border-color: rgba(255, 255, 255, 0.18); box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18); }
.btn:focus { outline: 2px solid var(--gold); outline-offset: 2px; }
.btn:active { transform: translateY(0); }

.btn-primary { background: var(--white-btn); color: var(--white-btn-text); border-color: transparent; }
.btn-primary:hover { background: #ffffff; }
.btn-secondary { background: rgba(255, 255, 255, 0.02); }
.btn-ghost { background: transparent; color: var(--muted); }
.btn-ghost:hover { color: var(--text); }

.mini-link { color: var(--muted); font-weight: 700; font-size: 0.94rem; transition: color var(--transition); }
.mini-link:hover { color: var(--text); }
.mini-link:focus { outline: 2px solid var(--gold); outline-offset: 2px; border-radius: 4px; }

.hero { padding: 72px 0 42px; }

.eyebrow {
  display: inline-block;
  margin-bottom: 16px;
  color: var(--gold);
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: 0.24em;
  text-transform: uppercase;
}

.hero-copy,
.hero-visual-card,
.section-card,
.feature-card,
.viewer-panel,
.trust-card,
.policy-card,
.footer-card,
.cta-panel,
.page-hero-panel,
.form-panel,
.architecture-panel,
.thank-you-card {
  background: linear-gradient(180deg, rgba(10, 16, 28, 0.82), rgba(6, 10, 18, 0.92));
  border: 1px solid var(--border);
  border-radius: 32px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
}

.hero-copy-premium,
.hero-visual-card,
.architecture-panel,
.viewer-panel,
.feature-card,
.trust-card,
.cta-panel,
.footer-card {
  position: relative;
  overflow: hidden;
}
.hero-copy-premium::before,
.hero-visual-card::before,
.architecture-panel::before,
.viewer-panel::before,
.feature-card::before,
.trust-card::before,
.cta-panel::before,
.footer-card::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent 18%),
    radial-gradient(circle at top right, rgba(214, 176, 102, 0.08), transparent 28%);
  opacity: 0.9;
}
.hero-copy-premium > *,
.hero-visual-card > *,
.architecture-panel > *,
.viewer-panel > *,
.feature-card > *,
.trust-card > *,
.cta-panel > *,
.footer-card > * { position: relative; z-index: 1; }

.feature-card,
.section-card,
.trust-card,
.policy-card,
.form-panel,
.viewer-step {
  /* critical: prevents "words outside bubble" while still allowing wrap */
  overflow: hidden;
}

.feature-card *,
.section-card *,
.trust-card *,
.policy-card *,
.form-panel *,
.viewer-step * {
  overflow-wrap: break-word;
  word-break: break-word;
  hyphens: auto;
}

/* ================= COOKIE ================= */
.cookie-banner {
  position: fixed;
  left: 20px;
  right: 20px;
  bottom: 20px;
  z-index: 2500; /* keep above everything */
  display: none;
}
.cookie-banner.visible { display: block; animation: slideUp 300ms ease; }

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.cookie-inner {
  width: min(1100px, 100%);
  margin: 0 auto;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid var(--border);
  background: rgba(7, 11, 21, 0.95);
  backdrop-filter: blur(18px);
  box-shadow: var(--shadow);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 14px 18px;
}
.cookie-copy { flex: 1 1 520px; min-width: 260px; color: var(--muted); font-size: 0.96rem; }
.cookie-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: flex-end; }
.cookie-actions .btn { width: auto !important; min-width: 140px; white-space: nowrap; }
.cookie-status { color: var(--muted-2); font-size: 0.94rem; margin-top: 8px; }

@media (max-width: 860px) {
  .cookie-inner { flex-direction: column; align-items: stretch; padding: 16px; }
  .cookie-actions { justify-content: stretch; width: 100%; }
  .cookie-actions .btn { flex: 1 1 0; min-width: 0; width: auto !important; white-space: normal; }
}

/* ================= EXEC CERTIFICATE (ON-SCREEN) ================= */
.exec-certificate {
  position: relative;
  background: #ffffff;
  color: #111111;
  border-radius: 28px;
  border: 1px solid #e6e6e6;
  padding: 34px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

.exec-cert-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.exec-cert-brand {
  display: flex;
  gap: 14px;
  align-items: center;
}

.exec-cert-logo { width: 44px; height: 44px; object-fit: contain; }

.exec-cert-brandname { font-weight: 800; font-size: 1.05rem; }
.exec-cert-brandsub { color: #666; font-weight: 700; margin-top: 2px; }

.exec-cert-badge {
  font-weight: 800;
  color: #3a3a3a;
  background: #f6f6f6;
  border: 1px solid #e2e2e2;
  padding: 10px 14px;
  border-radius: 999px;
  white-space: nowrap;
}

.exec-cert-title { margin-top: 18px; text-align: center; }

.exec-cert-eyebrow {
  letter-spacing: 0.22em;
  font-weight: 900;
  font-size: 0.82rem;
  color: #8a6a2f;
  margin-bottom: 10px;
}

.exec-cert-title h2 {
  margin: 0 0 10px;
  font-size: 2.3rem;
  letter-spacing: -0.04em;
}
.exec-cert-title p { margin: 0; color: #444; font-weight: 600; }

.exec-cert-watermark {
  position: absolute;
  inset: 0;
  background-image: url("images/tol-watermark-clean.png");
  background-repeat: no-repeat;
  background-position: center 56%;
  background-size: min(560px, 78%);
  opacity: 0.06;
  pointer-events: none;
}

.exec-cert-grid {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.exec-cert-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e5e5e5;
  border-radius: 18px;
  padding: 14px 16px;
}

.exec-cert-card-wide { grid-column: 1 / -1; }

.exec-cert-label {
  font-size: 0.82rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 900;
  color: #8a6a2f;
  margin-bottom: 6px;
}

.exec-cert-value { font-size: 1.05rem; font-weight: 800; color: #111; }

.exec-cert-wide { margin-top: 14px; display: grid; gap: 14px; }

.exec-cert-list { margin: 10px 0 0; padding-left: 18px; }
.exec-cert-list li + li { margin-top: 4px; }

.exec-cert-footer { margin-top: 16px; }

.exec-cert-statement {
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 18px;
  padding: 14px 16px;
  color: #333;
  font-weight: 650;
}

.exec-cert-signatures {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.exec-cert-line { height: 1px; background: #333; opacity: 0.55; margin-bottom: 8px; }
.exec-cert-signlabel { font-weight: 750; color: #222; }

.exec-cert-actions { margin-top: 16px; }

/* ================= EXEC CERTIFICATE (PRINT ONE PAGE) ================= */
@media print {
  @page { size: letter portrait; margin: 0.4in; }

  html, body { background: #ffffff !important; color: #111111 !important; }

  body * { visibility: hidden !important; }

  [data-certificate-output],
  [data-certificate-output] * { visibility: visible !important; }

  [data-certificate-output] {
    position: absolute !important;
    left: 0 !important;
    top: 0 !important;
    width: 100% !important;
  }

  .exec-certificate {
    box-shadow: none !important;
    border-radius: 0 !important;
    border: 1px solid #d9d9d9 !important;
    padding: 0.28in !important;
    overflow: visible !important;
  }

  .exec-cert-title { margin-top: 10px !important; }
  .exec-cert-title h2 { font-size: 1.9rem !important; margin-bottom: 6px !important; }

  .exec-cert-grid { gap: 10px !important; margin-top: 12px !important; }
  .exec-cert-card { padding: 10px 12px !important; }
  .exec-cert-value { font-size: 0.98rem !important; }
  .exec-cert-watermark { opacity: 0.05 !important; }

  .exec-cert-actions,
  .site-header,
  .footer,
  nav,
  .header-actions { display: none !important; }

  a { text-decoration: none !important; color: inherit !important; }
}

/* ================= RESPONSIVE ================= */
@media (max-width: 860px) {
  .container { width: min(var(--container), calc(100% - 24px)); }
  .site-watermark { background-size: min(84vw, 500px); background-position: center 38%; opacity: 0.10; }

  .site-header-inner { min-height: 78px; padding: 14px 0; flex-wrap: nowrap; }

  .menu-toggle { display: inline-flex; margin-left: auto; }
  .site-nav, .header-actions { display: none; }

  .site-header.open .site-nav,
  .site-header.open .header-actions { display: flex; width: 100%; }

  .site-header.open .site-header-inner { flex-wrap: wrap; align-items: flex-start; }

  .site-nav {
    order: 3;
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
    padding: 14px 0 6px;
    margin-left: 0;
  }

  .header-actions { order: 4; justify-content: flex-start; padding-bottom: 10px; }

  .btn { width: 100%; }
}