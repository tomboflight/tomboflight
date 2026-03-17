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
      window.TOLAuth.clearSession?.();
      window.TOLAuth.clearToken?.();
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
  }

  async function loadFamilyOptions(selectNode, statusNode) {
    if (!selectNode || !window.TOLAuth) return;

    selectNode.innerHTML = '<option value="">Select a family</option>';

    try {
      const families = await window.TOLAuth.apiRequest('/families/', { method: 'GET' });

      families.forEach(function (family) {
        const option = document.createElement('option');
        option.value = family.id || family._id || '';
        option.textContent = `${family.family_name || family.name || 'Family'} (${family.created_by || 'Unknown'})`;
        selectNode.appendChild(option);
      });

      hideStatus(statusNode);
    } catch (error) {
      showStatus(statusNode, error.message || 'Unable to load families.', 'error');
    }
  }

  async function loadCertificate(familyId, outputNode, emptyNode, statusNode) {
    if (!outputNode || !window.TOLAuth) return;

    showStatus(statusNode, 'Generating executive lineage certificate...', 'info');
    outputNode.style.display = 'none';
    outputNode.innerHTML = '';

    try {
      const certificate = await window.TOLAuth.apiRequest(`/lineage-certificate/${familyId}`, {
        method: 'GET'
      });

      renderExecutiveCertificate(certificate, outputNode);
      outputNode.style.display = 'block';
      if (emptyNode) emptyNode.style.display = 'none';

      showStatus(statusNode, 'Executive lineage certificate loaded successfully.', 'success');
    } catch (error) {
      if (emptyNode) emptyNode.style.display = 'block';
      showStatus(statusNode, error.message || 'Failed to load lineage certificate.', 'error');
    }
  }

  function renderExecutiveCertificate(c, outputNode) {
    // --- Flexible key picks (prevents "Unknown" when API uses different names) ---
    const certificateId = pickFirst(c, [
      'certificate_id', 'certificateId', 'id', 'record_id', 'recordId'
    ], 'Pending');

    const familyName = pickFirst(c, [
      'family_name', 'familyName', 'family', 'familyTitle'
    ], 'Unknown Family');

    // If family is object, prefer family.family_name
    const familyNameResolved = (typeof familyName === 'object' && familyName)
      ? (familyName.family_name || familyName.name || 'Unknown Family')
      : familyName;

    const createdBy = pickFirst(c, [
      'created_by', 'createdBy', 'issued_by', 'issuedBy', 'owner'
    ], 'Unknown');

    const issuedAt = pickFirst(c, [
      'issued_at', 'issuedAt', 'created_at', 'createdAt', 'generated_at', 'generatedAt'
    ], 'Not provided');

    // Pull lists / summaries
    const lineageProof = normalizeList(
      pickFirst(c, ['lineage_proof', 'lineageProof', 'proof', 'ancestors', 'lineage'], [])
    );

    const descendants = normalizeList(
      pickFirst(c, ['descendants', 'children', 'branch_members', 'branchMembers'], [])
    );

    // Counts (if API provides them, great; else compute best effort)
    const memberCount = toInt(pickFirst(c, ['member_count', 'memberCount', 'members_total', 'membersTotal'], null), null);
    const relationshipCount = toInt(pickFirst(c, ['relationship_count', 'relationshipCount', 'relationships_total', 'relationshipsTotal'], null), null);
    const generationCount = toInt(pickFirst(c, ['generation_count', 'generationCount', 'generations_total', 'generationsTotal'], null), null);

    // If descendants is an array of strings like "Generation 2: 3 member(s)", keep it short
    const branchSummaryLines = summarizeBranches(descendants);

    // Key lineage path: show up to 10 lines for 1-page
    const keyPath = lineageProof.slice(0, 10);

    const integrity = pickFirst(c, ['integrity', 'record_integrity', 'recordIntegrity', 'status'], 'Recorded');

    outputNode.innerHTML = `
      <div class="tol-cert-print-area">
        <div class="tol-cert-paper">
          <div class="tol-cert-watermark" aria-hidden="true"></div>

          <div class="tol-cert-top">
            <div class="tol-cert-brand">
              <div class="tol-cert-brand-title">Tomb of Light</div>
              <div class="tol-cert-brand-sub">Certified Executive Record</div>
            </div>

            <div class="tol-cert-badge">Certified Executive Record</div>
          </div>

          <div class="tol-cert-title">
            <div class="tol-cert-eyebrow">Certified Lineage Record</div>
            <h2>Executive Lineage Certificate</h2>
            <p>
              Official summary certification of a recorded family lineage within the Tomb of Light verification system.
            </p>
          </div>

          <div class="tol-cert-grid">
            ${kvCard('Certificate ID', certificateId)}
            ${kvCard('Family Name', familyNameResolved)}
            ${kvCard('Issued By', createdBy)}
            ${kvCard('Issue Date', formatDate(issuedAt))}
            ${kvCard('Members Recorded', memberCount != null ? String(memberCount) : 'Not available')}
            ${kvCard('Relationships Recorded', relationshipCount != null ? String(relationshipCount) : 'Not available')}
            ${kvCard('Generations Recorded', generationCount != null ? String(generationCount) : 'Not available')}
            ${kvCard('Record Integrity', String(integrity))}
          </div>

          <div class="tol-cert-split">
            <div class="tol-cert-block">
              <div class="tol-cert-label">Key Lineage Path</div>
              ${keyPath.length ? `
                <ul class="tol-cert-list">
                  ${keyPath.map(li => `<li>${escapeHtml(li)}</li>`).join('')}
                </ul>
              ` : `<div class="tol-cert-muted">Key lineage path not available.</div>`}
              ${lineageProof.length > 10 ? `<div class="tol-cert-footnote">Appendix available in full certificate view.</div>` : ``}
            </div>

            <div class="tol-cert-block">
              <div class="tol-cert-label">Verified Branches</div>
              ${branchSummaryLines.length ? `
                <ul class="tol-cert-list">
                  ${branchSummaryLines.map(li => `<li>${escapeHtml(li)}</li>`).join('')}
                </ul>
              ` : `<div class="tol-cert-muted">Branch summary not available.</div>`}

              <div class="tol-cert-label" style="margin-top: 14px;">Descendant Summary</div>
              ${descendants.length ? `
                <div class="tol-cert-muted">
                  ${escapeHtml(descendantsSummary(descendants))}
                </div>
              ` : `<div class="tol-cert-muted">No descendant records summarized on this certificate.</div>`}
            </div>
          </div>

          <div class="tol-cert-statement">
            This document certifies that the lineage structure shown for this family has been recorded and verified within the Tomb of Light system as of the issue date above.
          </div>

          <div class="tol-cert-sign">
            <div class="tol-cert-signbox">
              <div class="tol-cert-signline"></div>
              <div class="tol-cert-signlabel">Authorized Signature</div>
            </div>
            <div class="tol-cert-signbox">
              <div class="tol-cert-signline"></div>
              <div class="tol-cert-signlabel">Tomb of Light Certification Authority</div>
            </div>
          </div>

          <div class="tol-cert-actions no-print">
            <button class="btn btn-secondary" type="button" onclick="window.print()">Print Certificate</button>
          </div>
        </div>
      </div>
    `;
  }

  function kvCard(label, value) {
    return `
      <div class="tol-cert-card">
        <div class="tol-cert-card-label">${escapeHtml(label)}</div>
        <div class="tol-cert-card-value">${escapeHtml(String(value ?? ''))}</div>
      </div>
    `;
  }

  function pickFirst(obj, keys, fallback) {
    for (const k of keys) {
      if (obj && Object.prototype.hasOwnProperty.call(obj, k) && obj[k] != null) return obj[k];
    }
    return fallback;
  }

  function toInt(v, fallback) {
    const n = Number.parseInt(v, 10);
    return Number.isFinite(n) ? n : fallback;
  }

  function normalizeList(value) {
    if (!Array.isArray(value)) return [];
    return value
      .map(item => {
        if (item == null) return '';
        if (typeof item === 'string' || typeof item === 'number') return String(item);
        if (typeof item === 'object') {
          return item.display_name || item.name || item.full_name || item.label || item.id || '';
        }
        return String(item);
      })
      .filter(Boolean);
  }

  function summarizeBranches(descendants) {
    // If your API already returns generation lines, keep up to 6
    const genLines = descendants.filter(x => /generation/i.test(x)).slice(0, 6);
    if (genLines.length) return genLines;

    // Otherwise: just summarize top 6 descendants by name
    return descendants.slice(0, 6);
  }

  function descendantsSummary(descendants) {
    // Prefer a compact sentence instead of dumping everything
    const totalLine = descendants.find(x => /total/i.test(x));
    if (totalLine) return totalLine;
    return `${descendants.length} descendant record(s) captured in the lineage system.`;
  }

  function formatDate(value) {
    if (!value) return 'Not provided';
    // if already formatted, leave it
    if (typeof value === 'string' && (value.includes('/') || value.includes(':') || value.includes('-'))) {
      return value;
    }
    return String(value);
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