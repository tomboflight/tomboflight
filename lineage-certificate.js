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
      window.TOLAuth.clearToken();
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

    showStatus(statusNode, 'Loading lineage certificate...', 'info');
    outputNode.style.display = 'none';
    outputNode.innerHTML = '';

    try {
      const certificate = await window.TOLAuth.apiRequest(`/lineage-certificate/${familyId}`, {
        method: 'GET'
      });

      renderCertificate(certificate, outputNode);
      outputNode.style.display = 'block';

      if (emptyNode) {
        emptyNode.style.display = 'none';
      }

      showStatus(statusNode, 'Lineage certificate loaded successfully.', 'success');
    } catch (error) {
      if (emptyNode) {
        emptyNode.style.display = 'block';
      }
      showStatus(statusNode, error.message || 'Failed to load lineage certificate.', 'error');
    }
  }

  function renderCertificate(certificate, outputNode) {
    const certificateId =
      certificate.certificate_id ||
      certificate.id ||
      certificate.record_id ||
      'Pending';

    const familyName =
      certificate.family_name ||
      certificate.family?.family_name ||
      certificate.family ||
      'Unknown Family';

    const createdBy =
      certificate.created_by ||
      certificate.family?.created_by ||
      'Unknown';

    const issuedAt =
      certificate.issued_at ||
      certificate.created_at ||
      certificate.generated_at ||
      'Not provided';

    const summary =
      certificate.summary ||
      certificate.statement ||
      certificate.description ||
      'This lineage certificate summarizes the current family lineage record stored within Tomb of Light.';

    const lineageProof = normalizeList(
      certificate.lineage_proof ||
      certificate.ancestors ||
      certificate.proof ||
      certificate.lineage ||
      []
    );

    const descendants = normalizeList(
      certificate.descendants ||
      certificate.children ||
      certificate.branch_members ||
      []
    );

    const metadataEntries = collectMetadataEntries(certificate);

    outputNode.innerHTML = `
      <div class="certificate-paper">
        <div class="certificate-title">
          <span class="eyebrow">Certified Lineage Record</span>
          <h2>Lineage Certificate</h2>
          <p class="certificate-subtitle">
            Tomb of Light lineage verification record for the selected family structure.
          </p>
        </div>

        <div class="certificate-grid">
          <div class="certificate-item">
            <span class="certificate-label">Certificate ID</span>
            <div class="certificate-value certificate-id">${escapeHtml(String(certificateId))}</div>
          </div>

          <div class="certificate-item">
            <span class="certificate-label">Family Name</span>
            <div class="certificate-value">${escapeHtml(String(familyName))}</div>
          </div>

          <div class="certificate-item">
            <span class="certificate-label">Created By</span>
            <div class="certificate-value">${escapeHtml(String(createdBy))}</div>
          </div>

          <div class="certificate-item">
            <span class="certificate-label">Issued At</span>
            <div class="certificate-value">${escapeHtml(String(issuedAt))}</div>
          </div>

          <div class="certificate-item">
            <span class="certificate-label">Lineage Proof</span>
            ${renderList(lineageProof)}
          </div>

          <div class="certificate-item">
            <span class="certificate-label">Descendant Records</span>
            ${renderList(descendants)}
          </div>
        </div>

        ${metadataEntries.length ? `
          <div class="certificate-grid" style="margin-top: 1rem;">
            ${metadataEntries.map(function (entry) {
              return `
                <div class="certificate-item">
                  <span class="certificate-label">${escapeHtml(entry.label)}</span>
                  <div class="certificate-value">${escapeHtml(entry.value)}</div>
                </div>
              `;
            }).join('')}
          </div>
        ` : ''}

        <div class="certificate-summary">
          ${escapeHtml(String(summary))}
        </div>

        <div class="certificate-actions">
          <button class="btn btn-secondary" type="button" onclick="window.print()">Print Certificate</button>
        </div>
      </div>
    `;
  }

  function collectMetadataEntries(certificate) {
    const ignoredKeys = new Set([
      'certificate_id',
      'id',
      'record_id',
      'family_name',
      'family',
      'created_by',
      'issued_at',
      'created_at',
      'generated_at',
      'summary',
      'statement',
      'description',
      'lineage_proof',
      'ancestors',
      'proof',
      'lineage',
      'descendants',
      'children',
      'branch_members'
    ]);

    const entries = [];

    Object.keys(certificate || {}).forEach(function (key) {
      if (ignoredKeys.has(key)) return;

      const value = certificate[key];
      if (value == null) return;
      if (typeof value === 'object') return;

      entries.push({
        label: formatLabel(key),
        value: String(value)
      });
    });

    return entries.slice(0, 6);
  }

  function normalizeList(value) {
    if (!Array.isArray(value)) return [];

    return value.map(function (item) {
      if (item == null) return '';

      if (typeof item === 'string' || typeof item === 'number') {
        return String(item);
      }

      if (typeof item === 'object') {
        return (
          item.display_name ||
          item.name ||
          item.full_name ||
          item.label ||
          item.id ||
          JSON.stringify(item)
        );
      }

      return String(item);
    }).filter(Boolean);
  }

  function renderList(items) {
    if (!items.length) {
      return '<div class="certificate-value">None recorded.</div>';
    }

    return `
      <ul class="certificate-list">
        ${items.map(function (item) {
          return `<li>${escapeHtml(String(item))}</li>`;
        }).join('')}
      </ul>
    `;
  }

  function formatLabel(key) {
    return String(key)
      .replaceAll('_', ' ')
      .replace(/\b\w/g, function (char) {
        return char.toUpperCase();
      });
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