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
      const [certificateResult, graphResult] = await Promise.allSettled([
        window.TOLAuth.apiRequest(`/lineage-certificate/${familyId}`, { method: 'GET' }),
        window.TOLAuth.apiRequest(`/families/${familyId}/graph`, { method: 'GET' })
      ]);

      const certificate =
        certificateResult.status === 'fulfilled' ? certificateResult.value : {};

      const graph =
        graphResult.status === 'fulfilled' ? graphResult.value : null;

      const merged = buildCertificateViewModel(certificate, graph, familyId);

      renderCertificate(merged, outputNode);
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

  function buildCertificateViewModel(certificate, graph, familyId) {
    const family = graph?.family || certificate.family || {};
    const members = Array.isArray(graph?.members) ? graph.members : [];
    const relationships = Array.isArray(graph?.relationships) ? graph.relationships : [];
    const summary = graph?.summary || {};

    const memberMap = new Map();
    members.forEach(function (member) {
      memberMap.set(member.id, member);
    });

    const lineageProof = buildLineageProof(relationships, memberMap);
    const descendants = buildDescendantRecords(members, summary);

    const certificateId =
      certificate.certificate_id ||
      certificate.id ||
      certificate.record_id ||
      `LC-${String(familyId).slice(-8).toUpperCase()}`;

    const familyName =
      certificate.family_name ||
      family.family_name ||
      certificate.family ||
      'Unknown Family';

    const createdBy =
      certificate.created_by ||
      family.created_by ||
      'Unknown';

    const issuedAt =
      certificate.issued_at ||
      certificate.created_at ||
      certificate.generated_at ||
      new Date().toLocaleString();

    const narrativeSummary =
      certificate.summary ||
      certificate.statement ||
      certificate.description ||
      buildNarrativeSummary(familyName, summary, members, relationships);

    return {
      certificateId,
      familyName,
      createdBy,
      issuedAt,
      lineageProof,
      descendants,
      summary: narrativeSummary,
      metadataEntries: buildMetadataEntries(certificate, summary, members, relationships)
    };
  }

  function buildLineageProof(relationships, memberMap) {
    const parentChildLinks = relationships.filter(function (rel) {
      return rel.relationship_type === 'parent_child';
    });

    if (!parentChildLinks.length) return [];

    return parentChildLinks.map(function (rel) {
      const source = memberMap.get(rel.source_member_id);
      const target = memberMap.get(rel.target_member_id);

      const sourceName = getPersonName(source, rel.source_member_id);
      const targetName = getPersonName(target, rel.target_member_id);

      return `${sourceName} → ${targetName}`;
    });
  }

  function buildDescendantRecords(members, summary) {
    const generationCount = Number.isInteger(summary.generation_count) ? summary.generation_count : 0;
    const memberCount = Number.isInteger(summary.member_count) ? summary.member_count : members.length;

    const generationMap = new Map();
    members.forEach(function (member) {
      const generation = Number.isInteger(member.generation) ? member.generation : 0;
      generationMap.set(generation, (generationMap.get(generation) || 0) + 1);
    });

    const results = [
      `${memberCount} total family members`,
      `${generationCount} total generations`
    ];

    Array.from(generationMap.keys())
      .sort(function (a, b) { return a - b; })
      .forEach(function (generation) {
        results.push(`Generation ${generation}: ${generationMap.get(generation)} member(s)`);
      });

    return results;
  }

  function buildNarrativeSummary(familyName, summary, members, relationships) {
    const memberCount = Number.isInteger(summary.member_count) ? summary.member_count : members.length;
    const relationshipCount = Number.isInteger(summary.relationship_count) ? summary.relationship_count : relationships.length;
    const generationCount = Number.isInteger(summary.generation_count) ? summary.generation_count : 0;

    return `${familyName} currently contains ${memberCount} recorded family member(s), ${relationshipCount} relationship link(s), and spans ${generationCount} generation layer(s) within the Tomb of Light lineage system.`;
  }

  function buildMetadataEntries(certificate, summary, members, relationships) {
    const entries = [];

    entries.push({
      label: 'Member Count',
      value: String(Number.isInteger(summary.member_count) ? summary.member_count : members.length)
    });

    entries.push({
      label: 'Relationship Count',
      value: String(Number.isInteger(summary.relationship_count) ? summary.relationship_count : relationships.length)
    });

    entries.push({
      label: 'Generation Count',
      value: String(Number.isInteger(summary.generation_count) ? summary.generation_count : 0)
    });

    Object.keys(certificate || {}).forEach(function (key) {
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
        'branch_members',
        'success'
      ]);

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

  function renderCertificate(model, outputNode) {
    const appendixProof = model.lineageProof || [];
    const appendixDescendants = model.descendants || [];

    outputNode.innerHTML = `
      <div class="certificate-print-stack">
        <section class="certificate-paper certificate-page certificate-page-main">
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
              <div class="certificate-value certificate-id">${escapeHtml(String(model.certificateId))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Family Name</span>
              <div class="certificate-value">${escapeHtml(String(model.familyName))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Created By</span>
              <div class="certificate-value">${escapeHtml(String(model.createdBy))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Issued At</span>
              <div class="certificate-value">${escapeHtml(String(model.issuedAt))}</div>
            </div>
          </div>

          <div class="certificate-grid certificate-grid-tight">
            <div class="certificate-item">
              <span class="certificate-label">Lineage Proof Summary</span>
              ${renderPreviewList(model.lineageProof, 6)}
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Descendant Records</span>
              ${renderList(model.descendants)}
            </div>
          </div>

          ${model.metadataEntries.length ? `
            <div class="certificate-grid certificate-grid-meta">
              ${model.metadataEntries.map(function (entry) {
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
            ${escapeHtml(String(model.summary))}
          </div>

          <div class="certificate-signature-row">
            <div class="certificate-signature-block">
              <div class="certificate-signature-line"></div>
              <div class="certificate-signature-label">Tomb of Light Lineage Record</div>
            </div>
            <div class="certificate-signature-block">
              <div class="certificate-signature-line"></div>
              <div class="certificate-signature-label">Issued Verification</div>
            </div>
          </div>

          <div class="certificate-actions">
            <button class="btn btn-secondary" type="button" onclick="window.print()">Print Certificate</button>
          </div>
        </section>

        <section class="certificate-paper certificate-page certificate-page-appendix">
          <div class="certificate-title certificate-title-appendix">
            <span class="eyebrow">Appendix A</span>
            <h2>Lineage Proof Appendix</h2>
            <p class="certificate-subtitle">
              Detailed parent-to-child relationship record for ${escapeHtml(String(model.familyName))}.
            </p>
          </div>

          <div class="certificate-appendix-grid">
            <div class="certificate-item certificate-item-full">
              <span class="certificate-label">Full Lineage Proof</span>
              ${renderNumberedList(appendixProof)}
            </div>

            <div class="certificate-item certificate-item-full">
              <span class="certificate-label">Descendant Summary</span>
              ${renderNumberedList(appendixDescendants)}
            </div>
          </div>
        </section>
      </div>
    `;
  }

  function renderPreviewList(items, limit) {
    const safeItems = Array.isArray(items) ? items : [];

    if (!safeItems.length) {
      return '<div class="certificate-value">None recorded.</div>';
    }

    const preview = safeItems.slice(0, limit);
    const remaining = safeItems.length - preview.length;

    return `
      <ul class="certificate-list">
        ${preview.map(function (item) {
          return `<li>${escapeHtml(String(item))}</li>`;
        }).join('')}
        ${remaining > 0 ? `<li><em>+ ${remaining} additional record(s) listed in Appendix A</em></li>` : ''}
      </ul>
    `;
  }

  function renderList(items) {
    if (!items || !items.length) {
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

  function renderNumberedList(items) {
    if (!items || !items.length) {
      return '<div class="certificate-value">None recorded.</div>';
    }

    return `
      <ol class="certificate-list certificate-list-numbered">
        ${items.map(function (item) {
          return `<li>${escapeHtml(String(item))}</li>`;
        }).join('')}
      </ol>
    `;
  }

  function getPersonName(person, fallbackId) {
    if (!person) return `Unknown (${String(fallbackId).slice(-6)})`;

    return (
      person.display_name ||
      `${person.first_name || ''} ${person.last_name || ''}`.trim() ||
      fallbackId ||
      'Unknown'
    );
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