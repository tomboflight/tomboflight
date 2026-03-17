(function () {
  'use strict';

  async function setupFamilyGraphPage() {
    if (!window.TOLAuth) return;

    const graphPage = document.querySelector('[data-family-graph-page]');
    if (!graphPage) return;

    const statusNode = document.querySelector('[data-graph-status]');
    const familySelect = document.querySelector('[data-graph-family-select]');
    const summaryNode = document.querySelector('[data-graph-summary]');
    const membersNode = document.querySelector('[data-graph-members]');
    const relationshipsNode = document.querySelector('[data-graph-relationships]');
    const loadBtn = document.querySelector('[data-load-graph-btn]');

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

        await loadGraphForFamily(familyId, statusNode, summaryNode, membersNode, relationshipsNode);
      });
    }

    if (familySelect) {
      familySelect.addEventListener('change', async function () {
        const familyId = familySelect.value;
        clearGraph(summaryNode, membersNode, relationshipsNode);

        if (!familyId) {
          return;
        }

        await loadGraphForFamily(familyId, statusNode, summaryNode, membersNode, relationshipsNode);
      });
    }
  }

  async function loadFamilyOptions(selectNode, statusNode) {
    if (!selectNode || !window.TOLAuth) return;

    selectNode.innerHTML = '<option value="">Select a family</option>';

    try {
      const families = await window.TOLAuth.apiRequest('/families/', {
        method: 'GET'
      });

      if (!Array.isArray(families) || families.length === 0) {
        showStatus(statusNode, 'No family records found yet.', 'error');
        return;
      }

      families.forEach(function (family) {
        const option = document.createElement('option');
        option.value = family.id;
        option.textContent = `${family.family_name} (${family.created_by})`;
        selectNode.appendChild(option);
      });

      hideStatus(statusNode);
    } catch (error) {
      showStatus(statusNode, error.message || 'Unable to load family options.', 'error');
    }
  }

  async function loadGraphForFamily(familyId, statusNode, summaryNode, membersNode, relationshipsNode) {
    if (!window.TOLAuth) return;

    showStatus(statusNode, 'Loading family graph...', 'info');
    clearGraph(summaryNode, membersNode, relationshipsNode);

    try {
      const data = await window.TOLAuth.apiRequest(`/families/${familyId}/graph`, {
        method: 'GET'
      });

      renderSummary(data.summary, data.family, summaryNode);
      renderMembers(data.members || [], membersNode);
      renderRelationships(data.relationships || [], relationshipsNode, data.members || []);

      showStatus(statusNode, 'Family graph loaded successfully.', 'success');
    } catch (error) {
      showStatus(statusNode, error.message || 'Failed to load family graph.', 'error');
    }
  }

  function renderSummary(summary, family, node) {
    if (!node) return;

    const familyName = family && family.family_name ? family.family_name : 'Unknown Family';
    const createdBy = family && family.created_by ? family.created_by : 'Unknown';
    const description = family && family.description ? family.description : 'No description provided.';

    node.innerHTML = `
      <div class="family-record-card">
        <div class="card-number">S</div>
        <h3>${escapeHtml(familyName)}</h3>
        <p class="card-copy"><strong>Created By:</strong> ${escapeHtml(createdBy)}</p>
        <p class="card-copy"><strong>Description:</strong> ${escapeHtml(description)}</p>
        <p class="card-copy"><strong>Members:</strong> ${escapeHtml(String(summary.member_count || 0))}</p>
        <p class="card-copy"><strong>Relationships:</strong> ${escapeHtml(String(summary.relationship_count || 0))}</p>
        <p class="card-copy"><strong>Generations:</strong> ${escapeHtml(String(summary.generation_count || 0))}</p>
      </div>
    `;
  }

  function renderMembers(members, node) {
    if (!node) return;

    if (!Array.isArray(members) || members.length === 0) {
      node.innerHTML = `
        <div class="family-record-card">
          <div class="card-number">0</div>
          <h3>No Members Yet</h3>
          <p class="card-copy">This family does not have any members yet.</p>
        </div>
      `;
      return;
    }

    node.innerHTML = members
      .map(function (member, index) {
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(member.display_name || `${member.first_name || ''} ${member.last_name || ''}`.trim())}</h3>
            <p class="card-copy"><strong>Birth Year:</strong> ${escapeHtml(member.birth_year ? String(member.birth_year) : 'Unknown')}</p>
            <p class="card-copy"><strong>Generation:</strong> ${escapeHtml(String(member.generation ?? 'Unknown'))}</p>
            <p class="card-copy"><strong>Bio:</strong> ${escapeHtml(member.bio || 'No bio provided.')}</p>
            <p class="card-copy"><strong>Member ID:</strong> ${escapeHtml(member.id || '')}</p>
          </div>
        `;
      })
      .join('');
  }

  function renderRelationships(relationships, node, members) {
    if (!node) return;

    const memberMap = new Map();
    (members || []).forEach(function (member) {
      memberMap.set(member.id, member.display_name || `${member.first_name || ''} ${member.last_name || ''}`.trim());
    });

    if (!Array.isArray(relationships) || relationships.length === 0) {
      node.innerHTML = `
        <div class="family-record-card">
          <div class="card-number">0</div>
          <h3>No Relationships Yet</h3>
          <p class="card-copy">This family does not have relationship records yet.</p>
        </div>
      `;
      return;
    }

    node.innerHTML = relationships
      .map(function (relationship, index) {
        const sourceName = memberMap.get(relationship.source_member_id) || relationship.source_member_id;
        const targetName = memberMap.get(relationship.target_member_id) || relationship.target_member_id;

        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>${escapeHtml(relationship.relationship_type || 'relationship')}</h3>
            <p class="card-copy"><strong>Source:</strong> ${escapeHtml(sourceName)}</p>
            <p class="card-copy"><strong>Target:</strong> ${escapeHtml(targetName)}</p>
            <p class="card-copy"><strong>Created By:</strong> ${escapeHtml(relationship.created_by || 'Unknown')}</p>
            <p class="card-copy"><strong>Notes:</strong> ${escapeHtml(relationship.notes || 'No notes provided.')}</p>
          </div>
        `;
      })
      .join('');
  }

  function clearGraph(summaryNode, membersNode, relationshipsNode) {
    if (summaryNode) summaryNode.innerHTML = '';
    if (membersNode) membersNode.innerHTML = '';
    if (relationshipsNode) relationshipsNode.innerHTML = '';
  }

  function showStatus(node, message, type) {
    if (!node) return;
    node.style.display = 'block';
    node.textContent = message;

    if (type === 'error') {
      node.style.color = '#ffb3b3';
    } else if (type === 'success') {
      node.style.color = '#cfe8cf';
    } else {
      node.style.color = '#d6e6ff';
    }
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
    setupFamilyGraphPage();
  });
})();