(function () {
  'use strict';

  async function setupLineageCertificatePage() {
    if (!window.TOLAuth) return;

    const page = document.querySelector('[data-lineage-certificate-page]');
    if (!page) return;

    const familySelect = document.querySelector('[data-certificate-family-select]');
    const statusNode = document.querySelector('[data-certificate-status]');
    const outputNode = document.querySelector('[data-certificate-output]');
    const emptyNode = document.querySelector('[data-certificate-empty]');
    const loadBtn = document.querySelector('[data-load-certificate-btn]');

    const token = window.TOLAuth.getToken();
    if (!token) {
      window.location.href = 'signin.html';
      return;
    }

    try {
      await window.TOLAuth.apiRequest('/auth/me', { method: 'GET' });
    } catch (error) {
      window.TOLAuth.clearSession();
      window.location.href = 'signin.html';
      return;
    }

    await loadFamilyOptions(familySelect, statusNode);

    if (loadBtn) {
      loadBtn.addEventListener('click', async function () {
        const familyId = familySelect ? familySelect.value : '';
        if (!familyId) {
          showStatus(statusNode, 'Please select a family first.', 'error');
          return;
        }

        await loadCertificate(familyId, outputNode, emptyNode, statusNode);
      });
    }

    // auto-load on change (optional)
    if (familySelect) {
      familySelect.addEventListener('change', async function () {
        const familyId = familySelect.value;
        if (!familyId) return;
        await loadCertificate(familyId, outputNode, emptyNode, statusNode);
      });
    }
  }

  async function loadFamilyOptions(selectNode, statusNode) {
    if (!selectNode || !window.TOLAuth) return;

    selectNode.innerHTML = '<option value="">Select a family</option>';

    try {
      const families = await window.TOLAuth.apiRequest('/families/', { method: 'GET' });

      families.forEach(function (family) {
        const option = document.createElement('option');
        option.value = family.id;
        option.textContent = `${family.family_name} (${family.created_by})`;
        selectNode.appendChild(option);
      });

      hideStatus(statusNode);
    } catch (error) {
      showStatus(statusNode, error.message || 'Unable to load families.', 'error');
    }
  }

  async function loadCertificate(familyId, outputNode, emptyNode, statusNode) {
    if (!outputNode || !window.TOLAuth) return;

    showStatus(statusNode, 'Loading executive lineage certificate...', 'info');
    outputNode.style.display = 'none';
    outputNode.innerHTML = '';

    try {
      const data = await window.TOLAuth.apiRequest(`/lineage-certificate/${familyId}`, { method: 'GET' });

      // IMPORTANT: backend returns { success, certificate: {...} }
      const payload = data && data.certificate ? data.certificate : data;

      renderExecutiveCertificate(payload, outputNode);
      outputNode.style.display = 'block';

      if (emptyNode) emptyNode.style.display = 'none';
      showStatus(statusNode, 'Executive lineage certificate loaded successfully.', 'success');
    } catch (error) {
      if (emptyNode) emptyNode.style.display = 'block';
      showStatus(statusNode, error.message || 'Failed to load lineage certificate.', 'error');
    }
  }

  function renderExecutiveCertificate(cert, outputNode) {
    const family = cert.family || {};
    const summary = cert.summary || {};
    const exec = cert.executive || {};

    const certificateId = cert.certificate_id || 'Pending';
    const familyName = family.family_name || 'Unknown Family';
    const issuedBy = family.created_by || 'Unknown';
    const issuedAt = cert.issued_at || 'Not provided';

    const membersRecorded = numberOrFallback(summary.member_count, 'Not available');
    const relationshipsRecorded = numberOrFallback(summary.relationship_count, 'Not available');
    const generationsRecorded = numberOrFallback(summary.generation_count, 'Not available');

    const recordIntegrity = exec.record_integrity || (cert.status ? titleCase(cert.status) : 'Recorded');

    const foundingLine = exec.founding_line || 'Founding lineage not available.';
    const verifiedBranches = exec.verified_branches || 'Branch summary not available.';
    const keyLineagePath = normalizeList(exec.key_lineage_path || []);
    const descendantSummary = exec.descendant_summary || 'No descendant records summarized on this certificate.';

    outputNode.innerHTML = `
      <div class="exec-certificate" data-print-certificate>
        <div class="exec-cert-header">
          <div class="exec-cert-brand">
            <img class="exec-cert-logo" src="images/tol-watermark-clean.png" alt="Tomb of Light logo" />
            <div class="exec-cert-brandtext">
              <div class="exec-cert-brandname">Tomb of Light</div>
              <div class="exec-cert-brandsub">Certified Executive Record</div>
            </div>
          </div>

          <div class="exec-cert-badge">Certified Executive Record</div>
        </div>

        <div class="exec-cert-title">
          <div class="exec-cert-eyebrow">CERTIFIED LINEAGE RECORD</div>
          <h2>Executive Lineage Certificate</h2>
          <p>Official summary certification of a recorded family lineage within the Tomb of Light verification system.</p>
        </div>

        <div class="exec-cert-watermark" aria-hidden="true"></div>

        <div class="exec-cert-grid">
          ${card('Certificate ID', certificateId)}
          ${card('Family Name', familyName)}
          ${card('Issued By', issuedBy)}
          ${card('Issue Date', formatDate(issuedAt))}
          ${card('Members Recorded', membersRecorded)}
          ${card('Relationships Recorded', relationshipsRecorded)}
          ${card('Generations Recorded', generationsRecorded)}
          ${card('Record Integrity', recordIntegrity)}
        </div>

        <div class="exec-cert-wide">
          ${wideCard('Founding Line', foundingLine)}
          ${wideCard('Verified Branches', verifiedBranches)}
          ${wideCard('Key Lineage Path', renderBulletList(keyLineagePath, 'Key lineage path not available.'))}
          ${wideCard('Descendant Summary', descendantSummary)}
        </div>

        <div class="exec-cert-footer">
          <div class="exec-cert-statement">
            This document certifies that the lineage structure shown for this family has been recorded and verified within the Tomb of Light system as of the issue date above.
          </div>

          <div class="exec-cert-signatures">
            <div class="exec-cert-sign">
              <div class="exec-cert-line"></div>
              <div class="exec-cert-signlabel">Authorized Signature</div>
            </div>
            <div class="exec-cert-sign">
              <div class="exec-cert-line"></div>
              <div class="exec-cert-signlabel">Tomb of Light Certification Authority</div>
            </div>
          </div>

          <div class="exec-cert-actions">
            <button class="btn btn-secondary" type="button" onclick="window.print()">Print Certificate</button>
          </div>
        </div>
      </div>
    `;
  }

  function card(label, value) {
    return `
      <div class="exec-cert-card">
        <div class="exec-cert-label">${escapeHtml(label)}</div>
        <div class="exec-cert-value">${escapeHtml(String(value))}</div>
      </div>
    `;
  }

  function wideCard(label, valueHtml) {
    return `
      <div class="exec-cert-card exec-cert-card-wide">
        <div class="exec-cert-label">${escapeHtml(label)}</div>
        <div class="exec-cert-value">${typeof valueHtml === 'string' ? valueHtml : ''}</div>
      </div>
    `;
  }

  function renderBulletList(items, emptyText) {
    if (!items || !items.length) {
      return `<div>${escapeHtml(emptyText)}</div>`;
    }
    return `
      <ul class="exec-cert-list">
        ${items.map(item => `<li>${escapeHtml(String(item))}</li>`).join('')}
      </ul>
    `;
  }

  function normalizeList(value) {
    if (!Array.isArray(value)) return [];
    return value.map(v => (v == null ? '' : String(v))).filter(Boolean);
  }

  function numberOrFallback(value, fallback) {
    if (typeof value === 'number') return String(value);
    if (typeof value === 'string' && value.trim() !== '') return value;
    return fallback;
  }

  function formatDate(value) {
    try {
      const dt = new Date(value);
      if (Number.isNaN(dt.getTime())) return String(value);
      return dt.toLocaleString();
    } catch {
      return String(value);
    }
  }

  function titleCase(value) {
    return String(value).replace(/\b\w/g, c => c.toUpperCase());
  }

  function showStatus(node, message, type) {
    if (!node) return;
    node.style.display = 'block';
    node.textContent = message;
    node.style.color =
      type === 'error' ? '#ffb3b3' :
      type === 'success' ? '#cfe8cf' :
      '#d6e6ff';
  }

  function hideStatus(node) {
    if (!node) return;
    node.style.display = 'none';
    node.textContent = '';
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupLineageCertificatePage();
  });
})();