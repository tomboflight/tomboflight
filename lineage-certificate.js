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

      (families || []).forEach(function (family) {
        const option = document.createElement('option');
        option.value = family.id || family._id || '';
        option.textContent = `${family.family_name || 'Unnamed Family'} (${family.created_by || 'Unknown'})`;
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
      const raw = await window.TOLAuth.apiRequest(`/lineage-certificate/${encodeURIComponent(familyId)}`, {
        method: 'GET'
      });

      // ✅ IMPORTANT: unwrap common API response shapes
      const certificate = unwrapCertificate(raw);

      renderExecutiveCertificate(certificate, outputNode);
      outputNode.style.display = 'block';

      if (emptyNode) emptyNode.style.display = 'none';

      showStatus(statusNode, 'Executive lineage certificate loaded successfully.', 'success');
    } catch (error) {
      if (emptyNode) emptyNode.style.display = 'block';
      showStatus(statusNode, error.message || 'Failed to load lineage certificate.', 'error');
    }
  }

  function unwrapCertificate(raw) {
    if (!raw) return {};

    // If backend returns {success, data:{...}}
    if (raw.data && typeof raw.data === 'object') return raw.data;

    // If backend returns {success, certificate:{...}}
    if (raw.certificate && typeof raw.certificate === 'object') return raw.certificate;

    // If backend returns {result:{...}} or {payload:{...}}
    if (raw.result && typeof raw.result === 'object') return raw.result;
    if (raw.payload && typeof raw.payload === 'object') return raw.payload;

    // If backend returns {success:true, ...certificateFields}
    return raw;
  }

  function renderExecutiveCertificate(certificate, outputNode) {
    const certificateId =
      certificate.certificate_id ||
      certificate.id ||
      certificate.record_id ||
      'Pending';

    const familyName =
      certificate.family_name ||
      certificate.family?.family_name ||
      certificate.family?.name ||
      certificate.family ||
      'Unknown Family';

    const issuedBy =
      certificate.created_by ||
      certificate.issued_by ||
      certificate.family?.created_by ||
      certificate.owner ||
      'Unknown';

    const issuedAt =
      certificate.issued_at ||
      certificate.created_at ||
      certificate.generated_at ||
      certificate.issue_date ||
      'Not provided';

    // Counts (if your backend provides them)
    const memberCount =
      certificate.member_count ??
      certificate.members_count ??
      certificate.members?.length ??
      null;

    const relationshipCount =
      certificate.relationship_count ??
      certificate.relationships_count ??
      certificate.relationships?.length ??
      null;

    const generationCount =
      certificate.generation_count ??
      certificate.generations_count ??
      certificate.generations ??
      null;

    // Executive summaries
    const keyLineagePath = normalizeText(
      certificate.key_lineage_path ||
      certificate.key_path ||
      certificate.primary_lineage ||
      ''
    );

    const verifiedBranches = normalizeText(
      certificate.verified_branches ||
      certificate.branch_summary ||
      ''
    );

    const descendantSummary = normalizeText(
      certificate.descendant_summary ||
      certificate.descendants_summary ||
      ''
    );

    outputNode.innerHTML = `
      <div class="exec-cert">
        <div class="exec-cert__paper">
          <div class="exec-cert__watermark" aria-hidden="true"></div>

          <div class="exec-cert__topline">
            <div class="exec-cert__brand">
              <div class="exec-cert__brand-name">Tomb of Light</div>
              <div class="exec-cert__badge">Certified Executive Record</div>
            </div>
            <div class="exec-cert__seal">Certified Executive Record</div>
          </div>

          <div class="exec-cert__title">
            <div class="exec-cert__eyebrow">CERTIFIED LINEAGE RECORD</div>
            <h2>Executive Lineage Certificate</h2>
            <p>Official summary certification of a recorded family lineage within the Tomb of Light verification system.</p>
          </div>

          <div class="exec-cert__grid">
            ${metric('Certificate ID', certificateId)}
            ${metric('Family Name', familyName)}
            ${metric('Issued By', issuedBy)}
            ${metric('Issue Date', issuedAt)}
            ${metric('Members Recorded', memberCount == null ? 'Not available' : String(memberCount))}
            ${metric('Relationships Recorded', relationshipCount == null ? 'Not available' : String(relationshipCount))}
            ${metric('Generations Recorded', generationCount == null ? 'Not available' : String(generationCount))}
            ${metric('Record Integrity', 'Recorded')}
          </div>

          <div class="exec-cert__sections">
            <div class="exec-cert__section">
              <div class="exec-cert__section-label">KEY LINEAGE PATH</div>
              <div class="exec-cert__section-value">${escapeHtml(keyLineagePath || 'Key lineage path not available.')}</div>
            </div>

            <div class="exec-cert__section">
              <div class="exec-cert__section-label">VERIFIED BRANCHES</div>
              <div class="exec-cert__section-value">${escapeHtml(verifiedBranches || 'Branch summary not available.')}</div>
            </div>

            <div class="exec-cert__section">
              <div class="exec-cert__section-label">DESCENDANT SUMMARY</div>
              <div class="exec-cert__section-value">${escapeHtml(descendantSummary || 'No descendant records summarized on this certificate.')}</div>
            </div>
          </div>

          <div class="exec-cert__attestation">
            This document certifies that the lineage structure shown for this family has been recorded and verified within the Tomb of Light system as of the issue date above.
          </div>

          <div class="exec-cert__sign">
            <div class="exec-cert__sig">
              <div class="exec-cert__sig-line"></div>
              <div class="exec-cert__sig-label">Authorized Signature</div>
            </div>
            <div class="exec-cert__sig">
              <div class="exec-cert__sig-line"></div>
              <div class="exec-cert__sig-label">Tomb of Light Certification Authority</div>
            </div>
          </div>

          <div class="exec-cert__actions no-print">
            <button class="btn btn-secondary" type="button" onclick="window.print()">Print Certificate</button>
          </div>
        </div>
      </div>
    `;
  }

  function metric(label, value) {
    return `
      <div class="exec-cert__metric">
        <div class="exec-cert__metric-label">${escapeHtml(label)}</div>
        <div class="exec-cert__metric-value">${escapeHtml(String(value))}</div>
      </div>
    `;
  }

  function normalizeText(value) {
    if (value == null) return '';
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    if (Array.isArray(value)) return value.map(v => String(v)).join(' • ');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function showStatus(node, message, type) {
    if (!node) return;
    node.style.display = 'block';
    node.textContent = message;
    node.style.color =
      type === 'error'
        ? '#ffb3b3'
        : type === 'success'
          ? '#cfe8cf'
          : '#d6e6ff';
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