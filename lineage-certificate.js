(function () {
  'use strict';

  const API_BASE_URL =
    (window.TOL_CONFIG && window.TOL_CONFIG.API_BASE_URL) ||
    'http://127.0.0.1:8000';

  const output = document.querySelector('[data-certificate-output]');
  const statusNode = document.querySelector('[data-certificate-status]');
  const printBtn = document.querySelector('[data-certificate-print]');

  function setStatus(message, type) {
    if (!statusNode) return;
    statusNode.textContent = message;
    statusNode.dataset.state = type || 'info';
    statusNode.style.display = 'block';
  }

  function clearStatus() {
    if (!statusNode) return;
    statusNode.textContent = '';
    statusNode.dataset.state = '';
    statusNode.style.display = 'none';
  }

  function getFamilyId() {
    const params = new URLSearchParams(window.location.search);
    return params.get('family_id') || '';
  }

  function getToken() {
    return localStorage.getItem('tol_access_token');
  }

  async function fetchCertificate(familyId) {
    const token = getToken();

    const response = await fetch(`${API_BASE_URL}/lineage-certificate/${encodeURIComponent(familyId)}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Failed to load lineage certificate.');
    }

    return data;
  }

  function safe(value, fallback = 'Not available') {
    if (value === null || value === undefined) return fallback;
    const str = String(value).trim();
    return str ? str : fallback;
  }

  function renderList(items) {
    if (!Array.isArray(items) || !items.length) {
      return '<li>Not available</li>';
    }

    return items.map(function (item) {
      return `<li>${safe(item)}</li>`;
    }).join('');
  }

  function renderCertificate(payload) {
    const certificate = payload.certificate || {};
    const family = certificate.family || {};
    const summary = certificate.summary || {};
    const executive = certificate.executive || {};

    output.innerHTML = `
      <section class="exec-certificate">
        <div class="exec-cert-watermark" aria-hidden="true"></div>

        <div class="exec-cert-header">
          <div class="exec-cert-brand">
            <img class="exec-cert-logo" src="images/tol-watermark-clean.png" alt="Tomb of Light logo" />
            <div>
              <div class="exec-cert-brandname">Tomb of Light</div>
              <div class="exec-cert-brandsub">Executive Lineage Certificate</div>
            </div>
          </div>
          <div class="exec-cert-badge">${safe(certificate.status, 'Recorded')}</div>
        </div>

        <div class="exec-cert-title">
          <div class="exec-cert-eyebrow">Certified Lineage Record</div>
          <h2>${safe(family.family_name, 'Unnamed Family')}</h2>
          <p>Certificate ID: ${safe(certificate.certificate_id)}</p>
        </div>

        <div class="exec-cert-grid">
          <div class="exec-cert-card">
            <div class="exec-cert-label">Issued At</div>
            <div class="exec-cert-value">${safe(certificate.issued_at)}</div>
          </div>

          <div class="exec-cert-card">
            <div class="exec-cert-label">Integrity Hash</div>
            <div class="exec-cert-value">${safe(certificate.integrity_hash)}</div>
          </div>

          <div class="exec-cert-card">
            <div class="exec-cert-label">Created By</div>
            <div class="exec-cert-value">${safe(family.created_by)}</div>
          </div>

          <div class="exec-cert-card">
            <div class="exec-cert-label">Project ID</div>
            <div class="exec-cert-value">${safe(family.project_id)}</div>
          </div>

          <div class="exec-cert-card">
            <div class="exec-cert-label">Member Count</div>
            <div class="exec-cert-value">${safe(summary.member_count, '0')}</div>
          </div>

          <div class="exec-cert-card">
            <div class="exec-cert-label">Generation Count</div>
            <div class="exec-cert-value">${safe(summary.generation_count, '0')}</div>
          </div>

          <div class="exec-cert-card exec-cert-card-wide">
            <div class="exec-cert-label">Founding Line</div>
            <div class="exec-cert-value">${safe(executive.founding_line)}</div>
          </div>

          <div class="exec-cert-card exec-cert-card-wide">
            <div class="exec-cert-label">Verified Branches</div>
            <div class="exec-cert-value">${safe(executive.verified_branches)}</div>
          </div>

          <div class="exec-cert-card exec-cert-card-wide">
            <div class="exec-cert-label">Descendant Summary</div>
            <div class="exec-cert-value">${safe(executive.descendant_summary)}</div>
          </div>
        </div>

        <div class="exec-cert-wide">
          <div class="exec-cert-card">
            <div class="exec-cert-label">Key Lineage Path</div>
            <ul class="exec-cert-list">
              ${renderList(executive.key_lineage_path)}
            </ul>
          </div>
        </div>

        <div class="exec-cert-footer">
          <div class="exec-cert-statement">
            This executive certificate reflects the lineage structure, verification state,
            and recorded family summary currently stored in the Tomb of Light platform.
          </div>

          <div class="exec-cert-signatures">
            <div>
              <div class="exec-cert-line"></div>
              <div class="exec-cert-signlabel">Authorized Platform Record</div>
            </div>
            <div>
              <div class="exec-cert-line"></div>
              <div class="exec-cert-signlabel">Founder / Steward Approval</div>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  async function init() {
    if (!output) return;

    const familyId = getFamilyId();

    if (!familyId) {
      setStatus('Missing family_id in URL. Example: lineage-certificate.html?family_id=YOUR_ID', 'error');
      return;
    }

    clearStatus();
    output.innerHTML = '<p>Loading certificate...</p>';

    try {
      const data = await fetchCertificate(familyId);
      renderCertificate(data);
    } catch (error) {
      output.innerHTML = '';
      setStatus(error.message || 'Failed to load certificate.', 'error');
    }
  }

  if (printBtn) {
    printBtn.addEventListener('click', function () {
      window.print();
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();