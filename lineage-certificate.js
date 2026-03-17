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
      const certificate = await window.TOLAuth.apiRequest(`/lineage-certificate/${familyId}`, {
        method: 'GET'
      });

      renderExecutiveCertificate(certificate, outputNode);
      outputNode.style.display = 'block';

      if (emptyNode) {
        emptyNode.style.display = 'none';
      }

      showStatus(statusNode, 'Executive lineage certificate loaded successfully.', 'success');
    } catch (error) {
      if (emptyNode) {
        emptyNode.style.display = 'block';
      }
      showStatus(statusNode, error.message || 'Failed to load lineage certificate.', 'error');
    }
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
      'This document certifies that the lineage structure shown for this family has been recorded and verified within the Tomb of Light system as of the issue date below.';

    const memberCount =
      certificate.member_count ??
      certificate.members_count ??
      certificate.summary_data?.member_count ??
      certificate.family_member_count ??
      'Not available';

    const relationshipCount =
      certificate.relationship_count ??
      certificate.relationships_count ??
      certificate.summary_data?.relationship_count ??
      'Not available';

    const generationCount =
      certificate.generation_count ??
      certificate.generations_count ??
      certificate.summary_data?.generation_count ??
      'Not available';

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

    const members = normalizeMemberObjects(certificate.members || certificate.family_members || []);
    const relationships = Array.isArray(certificate.relationships) ? certificate.relationships : [];

    const foundingLine = deriveFoundingLine(members, relationships);
    const branches = deriveBranchSummary(members, relationships);
    const keyLine = deriveKeyLineageLine(members, relationships);
    const descendantSummary = buildDescendantSummary(descendants);
    const integrityStatus = relationshipCount === 'Not available' ? 'Recorded' : 'Verified';

    outputNode.innerHTML = `
      <div class="certificate-print-stack">
        <section class="certificate-paper certificate-page certificate-page-executive">
          <div class="certificate-executive-topbar">
            <div class="certificate-mark">Tomb of Light</div>
            <div class="certificate-badge">Certified Executive Record</div>
          </div>

          <div class="certificate-title certificate-title-executive">
            <span class="eyebrow">Certified Lineage Record</span>
            <h2>Executive Lineage Certificate</h2>
            <p class="certificate-subtitle">
              Official summary certification of a recorded family lineage within the Tomb of Light verification system.
            </p>
          </div>

          <div class="certificate-executive-grid">
            <div class="certificate-item">
              <span class="certificate-label">Certificate ID</span>
              <div class="certificate-value certificate-id">${escapeHtml(String(certificateId))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Family Name</span>
              <div class="certificate-value">${escapeHtml(String(familyName))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Issued By</span>
              <div class="certificate-value">${escapeHtml(String(createdBy))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Issue Date</span>
              <div class="certificate-value">${escapeHtml(String(issuedAt))}</div>
            </div>
          </div>

          <div class="certificate-executive-grid certificate-executive-grid-secondary">
            <div class="certificate-item">
              <span class="certificate-label">Members Recorded</span>
              <div class="certificate-value">${escapeHtml(String(memberCount))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Relationships Recorded</span>
              <div class="certificate-value">${escapeHtml(String(relationshipCount))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Generations Recorded</span>
              <div class="certificate-value">${escapeHtml(String(generationCount))}</div>
            </div>

            <div class="certificate-item">
              <span class="certificate-label">Record Integrity</span>
              <div class="certificate-value">${escapeHtml(integrityStatus)}</div>
            </div>
          </div>

          <div class="certificate-executive-proof">
            <div class="certificate-item certificate-item-full">
              <span class="certificate-label">Founding Line</span>
              <div class="certificate-value">${escapeHtml(foundingLine)}</div>
            </div>

            <div class="certificate-item certificate-item-full">
              <span class="certificate-label">Verified Branches</span>
              <div class="certificate-value">${escapeHtml(branches)}</div>
            </div>

            <div class="certificate-item certificate-item-full">
              <span class="certificate-label">Key Lineage Path</span>
              <div class="certificate-value">${escapeHtml(keyLine)}</div>
            </div>

            <div class="certificate-item certificate-item-full">
              <span class="certificate-label">Descendant Summary</span>
              <div class="certificate-value">${escapeHtml(descendantSummary)}</div>
            </div>
          </div>

          <div class="certificate-summary certificate-summary-executive">
            ${escapeHtml(String(summary))}
          </div>

          <div class="certificate-signature-row certificate-signature-row-executive">
            <div class="certificate-signature-block">
              <div class="certificate-signature-line"></div>
              <div class="certificate-signature-label">Authorized Signature</div>
            </div>

            <div class="certificate-signature-block">
              <div class="certificate-signature-line"></div>
              <div class="certificate-signature-label">Tomb of Light Certification Authority</div>
            </div>
          </div>

          <div class="certificate-actions">
            <button class="btn btn-secondary" type="button" onclick="window.print()">Print Certificate</button>
          </div>
        </section>
      </div>
    `;
  }

  function normalizeMemberObjects(items) {
    if (!Array.isArray(items)) return [];

    return items.map(function (item) {
      if (!item || typeof item !== 'object') return null;

      return {
        id: item.id || item._id || item.member_id || '',
        first_name: item.first_name || '',
        last_name: item.last_name || '',
        display_name:
          item.display_name ||
          item.full_name ||
          [item.first_name || '', item.last_name || ''].join(' ').trim(),
        generation: Number.isInteger(item.generation) ? item.generation : null
      };
    }).filter(Boolean);
  }

  function deriveFoundingLine(members, relationships) {
    if (!members.length) return 'Founding lineage not available.';

    const generationZero = members.filter(function (member) {
      return member.generation === 0;
    });

    if (generationZero.length >= 2) {
      const spouseLinks = relationships.filter(function (rel) {
        return rel.relationship_type === 'spouse';
      });

      for (const rel of spouseLinks) {
        const source = generationZero.find(function (m) { return m.id === rel.source_member_id; });
        const target = generationZero.find(function (m) { return m.id === rel.target_member_id; });

        if (source && target) {
          return `${displayName(source)} + ${displayName(target)}`;
        }
      }

      return generationZero.slice(0, 2).map(displayName).join(' + ');
    }

    if (generationZero.length === 1) {
      return displayName(generationZero[0]);
    }

    const sorted = [...members].sort(function (a, b) {
      return (a.generation ?? 999) - (b.generation ?? 999);
    });

    return sorted.length ? displayName(sorted[0]) : 'Founding lineage not available.';
  }

  function deriveBranchSummary(members) {
    if (!members.length) return 'Branch summary not available.';

    const generationOne = members.filter(function (member) {
      return member.generation === 1;
    });

    if (generationOne.length) {
      return generationOne.map(displayName).join(' • ');
    }

    const generationBuckets = [...new Set(
      members
        .map(function (member) { return member.generation; })
        .filter(function (gen) { return Number.isInteger(gen); })
    )].sort(function (a, b) { return a - b; });

    return generationBuckets.length
      ? `Verified across ${generationBuckets.length} generational layer(s)`
      : 'Branch summary not available.';
  }

  function deriveKeyLineageLine(members, relationships) {
    if (!members.length) return 'Key lineage path not available.';

    const byId = new Map();
    members.forEach(function (member) {
      byId.set(member.id, member);
    });

    const parentChild = relationships.filter(function (rel) {
      return rel.relationship_type === 'parent_child';
    });

    if (!parentChild.length) {
      const sorted = [...members].sort(function (a, b) {
        return (a.generation ?? 999) - (b.generation ?? 999);
      });
      return sorted.slice(0, 4).map(displayName).join(' → ') || 'Key lineage path not available.';
    }

    const childToParents = new Map();
    parentChild.forEach(function (rel) {
      if (!childToParents.has(rel.target_member_id)) {
        childToParents.set(rel.target_member_id, []);
      }
      childToParents.get(rel.target_member_id).push(rel.source_member_id);
    });

    const deepestMember = [...members]
      .filter(function (member) { return Number.isInteger(member.generation); })
      .sort(function (a, b) { return (b.generation ?? -1) - (a.generation ?? -1); })[0];

    if (!deepestMember) return 'Key lineage path not available.';

    const path = [deepestMember];
    let current = deepestMember;
    let safety = 0;

    while (current && safety < 10) {
      safety += 1;
      const parents = childToParents.get(current.id) || [];
      if (!parents.length) break;

      const nextParent = parents
        .map(function (id) { return byId.get(id); })
        .filter(Boolean)
        .sort(function (a, b) { return (a.generation ?? 999) - (b.generation ?? 999); })[0];

      if (!nextParent) break;

      path.unshift(nextParent);
      current = nextParent;
    }

    return path.map(displayName).join(' → ');
  }

  function buildDescendantSummary(descendants) {
    if (!descendants.length) return 'No descendant records summarized on this certificate.';
    return descendants.slice(0, 8).join(' • ');
  }

  function displayName(member) {
    return member.display_name || [member.first_name || '', member.last_name || ''].join(' ').trim() || 'Unknown';
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