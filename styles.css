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
*::after {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

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

body.menu-open {
  overflow: hidden;
}

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

img {
  max-width: 100%;
  display: block;
}

a {
  color: inherit;
  text-decoration: none;
}

button,
input,
textarea,
select {
  font: inherit;
}

.container {
  width: min(var(--container), calc(100% - 40px));
  margin: 0 auto;
}

.page-wrap {
  min-height: 100vh;
  position: relative;
  z-index: 1;
}

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

.brand-symbol {
  font-size: 0.8em;
  vertical-align: super;
}

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
  text-decoration: none;
}

.site-nav a:hover,
.site-nav a.active {
  color: var(--text);
}

.site-nav a:focus {
  outline: 2px solid var(--gold);
  outline-offset: 4px;
  border-radius: 4px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

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

.menu-toggle:focus {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}

.menu-toggle[aria-expanded="true"] {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--border);
}

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
  transition:
    transform var(--transition),
    background var(--transition),
    border-color var(--transition),
    color var(--transition),
    box-shadow var(--transition);
  cursor: pointer;
  text-decoration: none;
}

.btn:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.18);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
}

.btn:focus {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}

.btn:active {
  transform: translateY(0);
}

.btn-primary {
  background: var(--white-btn);
  color: var(--white-btn-text);
  border-color: transparent;
}

.btn-primary:hover {
  background: #ffffff;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.02);
}

.btn-ghost {
  background: transparent;
  color: var(--muted);
}

.btn-ghost:hover {
  color: var(--text);
}

.mini-link {
  color: var(--muted);
  font-weight: 700;
  font-size: 0.94rem;
  text-decoration: none;
  transition: color var(--transition);
}

.mini-link:hover {
  color: var(--text);
}

.mini-link:focus {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
  border-radius: 4px;
}

.hero {
  padding: 72px 0 42px;
}

.hero-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.04fr) minmax(0, 0.96fr);
  gap: 26px;
  align-items: stretch;
}

.hero-shell-tech {
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  align-items: start;
}

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

/* CRITICAL: keep content from overflowing grid/flex items */
.hero-shell > *,
.hero-visual-grid > *,
.feature-strip > *,
.architecture-grid > *,
.trust-grid > *,
.footer-top > * {
  min-width: 0;
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
.footer-card > * {
  position: relative;
  z-index: 1;
}

.hero-copy-premium {
  padding: 42px;
  min-height: 100%;
}

.hero-copy-tech {
  position: sticky;
  top: 112px;
}

.hero-copy h1,
.page-hero h1 {
  margin: 0 0 18px;
  font-size: clamp(2.9rem, 5vw, 5rem);
  line-height: 0.98;
  letter-spacing: -0.06em;
  max-width: 11.5ch;
}

.hero-gold {
  color: var(--text);
}

.hero-lead,
.hero-copy p,
.page-hero p,
.section-lead,
.card-copy,
.footer-copy {
  color: var(--muted);
  font-size: 1.04rem;
}

/* Prevent long words/URLs from breaking “bubble” boxes */
.feature-card p,
.section-card p,
.trust-card p,
.policy-card p,
.viewer-step p,
.footer-card p,
.feature-card li,
.section-card li,
.trust-card li,
.policy-card li {
  overflow-wrap: break-word;
  word-break: normal;
}

.hero-lead {
  max-width: 58ch;
}

.hero-actions,
.cta-actions,
.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 28px;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.meta-pill {
  padding: 10px 14px;
  border-radius: 999px;
  color: var(--muted);
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
  font-size: 0.94rem;
  font-weight: 600;
}

.signal-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  margin-top: 20px;
  color: var(--muted-2);
  font-size: 0.92rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.signal-row span {
  position: relative;
  padding-left: 14px;
}

.signal-row span::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0.52em;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gold);
  box-shadow: 0 0 12px rgba(214, 176, 102, 0.6);
}

.hero-visual {
  display: grid;
  gap: 20px;
}

.hero-visual-tech {
  gap: 20px;
}

.hero-visual-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 20px;
}

.hero-visual-card {
  padding: 28px;
}

.hero-visual-card:focus {
  outline: 2px solid var(--gold);
  outline-offset: 4px;
}

.hero-demo-card {
  padding: 24px;
}

.hero-demo-card-top {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.hero-demo-card-top .eyebrow {
  margin-bottom: 10px;
}

.hero-demo-card-top h2,
.hero-visual-main h2,
.section-head h2,
.cta-panel h2,
.viewer-panel-top h2 {
  margin: 0 0 12px;
  font-size: clamp(2rem, 3vw, 3.1rem);
  line-height: 1.05;
  letter-spacing: -0.05em;
}

.hero-demo-card-top h2 {
  font-size: clamp(1.4rem, 2vw, 2rem);
  margin-bottom: 0;
}

.hero-copy h1,
.section-head h2,
.cta-panel h2,
.viewer-panel-top h2,
.hero-demo-card-top h2,
.hero-visual-main h2 {
  text-wrap: balance;
}

.hero-demo-embed {
  height: 280px;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid var(--border-soft);
  background: rgba(0, 0, 0, 0.3);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 18px 40px rgba(0, 0, 0, 0.28);
}

.hero-demo-embed iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #000;
}

.hero-visual-main p {
  color: var(--muted);
  margin: 0;
}

.section {
  padding: 28px 0 10px;
}

.section-tight {
  padding-top: 12px;
}

.section-head {
  margin-bottom: 22px;
}

.section-head-wide {
  max-width: 820px;
}

.feature-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
}

.pricing-row-two {
  margin-top: 22px;
}

.feature-card,
.section-card,
.trust-card,
.policy-card {
  padding: 28px;
  transition: all var(--transition);
}

.feature-card:hover,
.section-card:hover,
.trust-card:hover,
.policy-card:hover {
  border-color: rgba(214, 176, 102, 0.3);
}

.feature-card:focus-within,
.section-card:focus-within,
.trust-card:focus-within,
.policy-card:focus-within {
  border-color: var(--gold);
  box-shadow: 0 0 0 2px rgba(214, 176, 102, 0.2);
}

.section-list,
.policy-list {
  margin: 16px 0 0;
  padding-left: 20px;
  color: var(--muted);
}

.architecture-panel {
  padding: 34px;
}

.architecture-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22px;
  margin-top: 24px;
}

.viewer-panel {
  padding: 34px;
}

.viewer-panel-top {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: end;
  margin-bottom: 10px;
}

.viewer-steps {
  display: grid;
  gap: 18px;
  margin-top: 22px;
}

.viewer-steps-premium {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.viewer-step {
  padding: 22px;
  border-radius: 24px;
  border: 1px solid var(--border-soft);
  background: rgba(255, 255, 255, 0.03);
  transition: all var(--transition);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.viewer-step h3 {
  margin: 0 0 8px;
  font-size: 1.12rem;
  letter-spacing: -0.03em;
}

.viewer-step p {
  margin: 0;
  color: var(--muted);
}

.trust-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
}

.cta-panel {
  padding: 40px;
  margin: 22px 0 44px;
}

.page-hero {
  padding: 72px 0 20px;
}

.page-hero-panel {
  padding: 42px;
}

.page-sections {
  padding: 12px 0 34px;
}

.page-stack,
.form-shell,
.form-grid {
  display: grid;
  gap: 22px;
}

.form-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-panel {
  padding: 30px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--muted);
  font-weight: 600;
}

input,
textarea,
select {
  width: 100%;
  min-height: 54px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  padding: 14px 16px;
  transition: all var(--transition);
}

textarea {
  min-height: 150px;
  resize: vertical;
}

.footer {
  padding: 24px 0 44px;
}

.footer-card {
  padding: 34px;
}

.footer-top {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 28px;
  align-items: start;
}

.footer-links {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 30px;
}

.footer-links a {
  color: var(--muted);
  font-weight: 600;
  transition: color var(--transition);
}

.footer-links a:hover {
  color: var(--text);
}

.footer-bottom {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px 20px;
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--muted-2);
  font-size: 0.96rem;
}

/* ================= COOKIE ================= */
.cookie-banner {
  position: fixed;
  left: 20px;
  right: 20px;
  bottom: 20px;
  z-index: 2500;
  display: none;
}

.cookie-banner.visible {
  display: block;
  animation: slideUp 300ms ease;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
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

.cookie-copy {
  flex: 1 1 520px;
  min-width: 260px;
  color: var(--muted);
  font-size: 0.96rem;
}

.cookie-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

.cookie-actions .btn {
  width: auto !important;
  min-width: 140px;
  white-space: nowrap;
}

.cookie-status {
  color: var(--muted-2);
  font-size: 0.94rem;
  margin-top: 8px;
}

@media (max-width: 1180px) {
  .hero-shell,
  .hero-shell-tech,
  .feature-strip,
  .architecture-grid,
  .viewer-steps-premium,
  .trust-grid,
  .footer-top,
  .form-grid.two-col,
  .hero-visual-grid {
    grid-template-columns: 1fr;
  }

  .hero-copy-tech { position: static; }
  .viewer-panel-top { align-items: start; flex-direction: column; }
}

@media (max-width: 860px) {
  .container { width: min(var(--container), calc(100% - 24px)); }

  .site-watermark {
    background-size: min(84vw, 500px);
    background-position: center 38%;
    opacity: 0.10;
  }

  .site-header-inner {
    min-height: 78px;
    padding: 14px 0;
    flex-wrap: nowrap;
  }

  .menu-toggle { display: inline-flex; margin-left: auto; }
  .site-nav, .header-actions { display: none; }

  .site-header.open .site-nav,
  .site-header.open .header-actions {
    display: flex;
    width: 100%;
  }

  .site-header.open .site-header-inner {
    flex-wrap: wrap;
    align-items: flex-start;
  }

  .site-nav {
    order: 3;
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
    padding: 14px 0 6px;
    margin-left: 0;
  }

  .header-actions {
    order: 4;
    justify-content: flex-start;
    padding-bottom: 10px;
  }

  .hero,
  .page-hero {
    padding-top: 42px;
  }

  .hero-copy-premium,
  .hero-visual-card,
  .viewer-panel,
  .feature-card,
  .section-card,
  .trust-card,
  .policy-card,
  .page-hero-panel,
  .footer-card,
  .cta-panel,
  .form-panel,
  .architecture-panel {
    padding: 24px;
    border-radius: 26px;
  }

  .brand { font-size: 1.5rem; }

  .btn { width: 100%; }

  .cookie-inner {
    flex-direction: column;
    align-items: stretch;
  }

  .cookie-actions {
    justify-content: stretch;
  }

  .cookie-actions .btn {
    flex: 1 1 0;
    min-width: 0;
    white-space: normal;
  }
}

/* ================= CERTIFICATE (ON-SCREEN) ================= */
/* Scoped so it cannot break the website cards */
[data-certificate-output] .exec-certificate {
  position: relative;
  background: #ffffff;
  color: #111111;
  border-radius: 28px;
  border: 1px solid #e6e6e6;
  padding: 34px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

[data-certificate-output] .exec-cert-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

[data-certificate-output] .exec-cert-brand {
  display: flex;
  gap: 14px;
  align-items: center;
}

[data-certificate-output] .exec-cert-logo {
  width: 56px;
  height: 56px;
  object-fit: contain;
}

[data-certificate-output] .exec-cert-brandname {
  font-weight: 800;
  font-size: 1.05rem;
}

[data-certificate-output] .exec-cert-brandsub {
  color: #666;
  font-weight: 700;
  margin-top: 2px;
}

[data-certificate-output] .exec-cert-badge {
  font-weight: 800;
  color: #3a3a3a;
  background: #f6f6f6;
  border: 1px solid #e2e2e2;
  padding: 10px 14px;
  border-radius: 999px;
  white-space: nowrap;
}

[data-certificate-output] .exec-cert-title {
  margin-top: 22px;
  text-align: center;
}

[data-certificate-output] .exec-cert-eyebrow {
  letter-spacing: 0.22em;
  font-weight: 900;
  font-size: 0.82rem;
  color: #8a6a2f;
  margin-bottom: 10px;
}

[data-certificate-output] .exec-cert-title h2 {
  margin: 0 0 10px;
  font-size: 2.3rem;
  letter-spacing: -0.04em;
}

[data-certificate-output] .exec-cert-title p {
  margin: 0;
  color: #444;
  font-weight: 600;
}

[data-certificate-output] .exec-cert-watermark {
  position: absolute;
  inset: 0;
  background-image: url("images/tol-watermark-clean.png");
  background-repeat: no-repeat;
  background-position: center 56%;
  background-size: min(560px, 78%);
  opacity: 0.06;
  pointer-events: none;
}

[data-certificate-output] .exec-cert-grid {
  margin-top: 26px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

[data-certificate-output] .exec-cert-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e5e5e5;
  border-radius: 18px;
  padding: 14px 16px;
  min-width: 0;
}

[data-certificate-output] .exec-cert-card-wide {
  grid-column: 1 / -1;
}

[data-certificate-output] .exec-cert-label {
  font-size: 0.82rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 900;
  color: #8a6a2f;
  margin-bottom: 6px;
}

[data-certificate-output] .exec-cert-value {
  font-size: 1.05rem;
  font-weight: 800;
  color: #111;
  overflow-wrap: break-word;
}

[data-certificate-output] .exec-cert-wide {
  margin-top: 14px;
  display: grid;
  gap: 14px;
}

[data-certificate-output] .exec-cert-list {
  margin: 10px 0 0;
  padding-left: 18px;
}

[data-certificate-output] .exec-cert-list li + li {
  margin-top: 4px;
}

[data-certificate-output] .exec-cert-footer {
  margin-top: 16px;
}

[data-certificate-output] .exec-cert-statement {
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 18px;
  padding: 14px 16px;
  color: #333;
  font-weight: 650;
}

[data-certificate-output] .exec-cert-signatures {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

[data-certificate-output] .exec-cert-line {
  height: 1px;
  background: #333;
  opacity: 0.55;
  margin-bottom: 8px;
}

[data-certificate-output] .exec-cert-signlabel {
  font-weight: 750;
  color: #222;
}

[data-certificate-output] .exec-cert-actions {
  margin-top: 16px;
}

/* ================= CERTIFICATE (PRINT ONE PAGE) ================= */
@media print {
  @page {
    size: letter portrait;
    margin: 0.4in;
  }

  html,
  body {
    background: #ffffff !important;
    color: #111111 !important;
  }

  body * {
    visibility: hidden !important;
  }

  [data-certificate-output],
  [data-certificate-output] * {
    visibility: visible !important;
  }

  [data-certificate-output] {
    position: absolute !important;
    left: 0 !important;
    top: 0 !important;
    width: 100% !important;
  }

  [data-certificate-output] .exec-certificate {
    box-shadow: none !important;
    border-radius: 0 !important;
    border: 1px solid #d9d9d9 !important;
    padding: 0.28in !important;
    overflow: visible !important;
  }

  /* tighten spacing so it stays on one page */
  [data-certificate-output] .exec-cert-title { margin-top: 12px !important; }
  [data-certificate-output] .exec-cert-title h2 {
    font-size: 1.9rem !important;
    margin-bottom: 6px !important;
  }

  [data-certificate-output] .exec-cert-grid {
    gap: 10px !important;
    margin-top: 14px !important;
  }

  [data-certificate-output] .exec-cert-card {
    padding: 10px 12px !important;
  }

  [data-certificate-output] .exec-cert-value {
    font-size: 0.98rem !important;
  }

  [data-certificate-output] .exec-cert-watermark {
    opacity: 0.05 !important;
  }

  /* never print buttons/nav/footer */
  .exec-cert-actions,
  .site-header,
  .footer,
  nav,
  .header-actions,
  [data-certificate-status],
  [data-certificate-empty] {
    display: none !important;
  }
}