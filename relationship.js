(function () {
  'use strict';

  async function setupRelationshipForm() {
    const form = document.querySelector('[data-relationship-form]');
    if (!form || !window.TOLAuth) return;

    const familySelect = form.querySelector('[name="family_id"]');
    const sourceInput = form.querySelector('[name="source_member_id"]');
    const targetInput = form.querySelector('[name="target_member_id"]');
    const typeSelect = form.querySelector('[name="relationship_type"]');
    const modeSelect = form.querySelector('[name="relationship_mode"]');
    const privacySelect = form.querySelector('[name="privacy_scope"]');
    const evidenceSelect = form.querySelector('[name="evidence_record_ids"]');
    const relationshipLabelInput = form.querySelector('[name="relationship_label"]');
    const notesInput = form.querySelector('[name="notes"]');
    const createdByInput = form.querySelector('[name="created_by"]');
    const statusNode = document.querySelector('[data-relationship-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');

    const token = window.TOLAuth.getToken();
    if (!token) {
      window.location.href = 'signin.html';
      return;
    }

    try {
      const me = await window.TOLAuth.apiRequest('/auth/me', { method: 'GET' });

      if (createdByInput && !createdByInput.value.trim()) {
        createdByInput.value = me.full_name || me.email || '';
      }

      await loadFamilies(familySelect);
    } catch (error) {
      window.TOLAuth.clearSession();
      window.location.href = 'signin.html';
      return;
    }

    familySelect.addEventListener('change', function () {
      loadFamilyMembers(familySelect.value, sourceInput, targetInput, statusNode);
      loadApprovedEvidence(familySelect.value, evidenceSelect, statusNode);
    });

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      hideStatus(statusNode);

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const payload = {
        family_id: String(familySelect.value || '').trim(),
        source_member_id: String(sourceInput.value || '').trim(),
        target_member_id: String(targetInput.value || '').trim(),
        relationship_type: String(typeSelect.value || '').trim(),
        relationship_mode: String(modeSelect.value || 'narrative').trim(),
        status_marker:
          String(modeSelect.value || 'narrative').trim() === 'verified'
            ? 'verified'
            : 'narrative',
        privacy_scope: String(privacySelect.value || 'household_private').trim(),
        evidence_record_ids: Array.from(evidenceSelect.selectedOptions || [])
          .map(function (option) { return String(option.value || '').trim(); })
          .filter(Boolean),
        relationship_label: String(relationshipLabelInput.value || '').trim() || null,
        notes: String(notesInput.value || '').trim() || null,
        created_by: String(createdByInput.value || '').trim() || null
      };

      if (!payload.family_id || !payload.source_member_id || !payload.target_member_id || !payload.relationship_type) {
        showStatus(statusNode, 'Please complete all required fields.', 'error');
        return;
      }

      if (payload.source_member_id === payload.target_member_id) {
        showStatus(statusNode, 'Source and target family members must be different.', 'error');
        return;
      }

      if (
        payload.relationship_mode === 'verified' &&
        payload.evidence_record_ids.length === 0
      ) {
        showStatus(
          statusNode,
          'Verified relationships require at least one clean, approved verification record.',
          'error'
        );
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Creating Relationship...';

      try {
        await window.TOLAuth.apiRequest('/relationships', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        showStatus(statusNode, 'Relationship created successfully.', 'success');
        const selectedFamilyId = payload.family_id;
        form.reset();
        familySelect.value = selectedFamilyId;
        await loadFamilyMembers(selectedFamilyId, sourceInput, targetInput, statusNode);
        await loadApprovedEvidence(selectedFamilyId, evidenceSelect, statusNode);

        try {
          const me = await window.TOLAuth.apiRequest('/auth/me', { method: 'GET' });
          if (createdByInput) {
            createdByInput.value = me.full_name || me.email || '';
          }
        } catch (error) {
          // ignore refill failure
        }
      } catch (error) {
        showStatus(statusNode, error.message || 'Error creating relationship.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Relationship';
      }
    });
  }

  async function loadFamilies(selectNode) {
    if (!selectNode || !window.TOLAuth) return;

    selectNode.innerHTML = '<option value="">Select a family</option>';

    const families = await window.TOLAuth.apiRequest('/families/', {
      method: 'GET'
    });

    families.forEach(function (family) {
      const option = document.createElement('option');
      option.value = family.id;
      option.textContent = `${family.family_name} (${family.created_by})`;
      selectNode.appendChild(option);
    });
  }

  async function loadFamilyMembers(familyId, sourceSelect, targetSelect, statusNode) {
    const placeholder = familyId
      ? '<option value="">Loading family members...</option>'
      : '<option value="">Select a family first</option>';
    sourceSelect.innerHTML = placeholder;
    targetSelect.innerHTML = placeholder;
    if (!familyId) return;

    try {
      const graph = await window.TOLAuth.apiRequest(
        `/families/${encodeURIComponent(familyId)}/graph`,
        { method: 'GET' }
      );
      const members = Array.isArray(graph.members) ? graph.members : [];
      const options = members
        .slice()
        .sort(function (a, b) {
          const generationA = Number.isFinite(Number(a.generation)) ? Number(a.generation) : 999;
          const generationB = Number.isFinite(Number(b.generation)) ? Number(b.generation) : 999;
          if (generationA !== generationB) return generationA - generationB;
          return String(a.full_name || '').localeCompare(String(b.full_name || ''));
        })
        .map(function (member) {
          const name = String(
            member.full_name ||
            `${member.first_name || ''} ${member.last_name || ''}`
          ).trim() || 'Unnamed family member';
          return `<option value="${escapeHtml(member.id)}">${escapeHtml(name)} — generation ${escapeHtml(member.generation ?? 'unplaced')}</option>`;
        })
        .join('');
      sourceSelect.innerHTML = `<option value="">Select source family member</option>${options}`;
      targetSelect.innerHTML = `<option value="">Select target family member</option>${options}`;
      if (!members.length) {
        showStatus(statusNode, 'Add family members before creating relationships.', 'error');
      }
    } catch (error) {
      sourceSelect.innerHTML = '<option value="">Unable to load members</option>';
      targetSelect.innerHTML = '<option value="">Unable to load members</option>';
      showStatus(statusNode, error.message || 'Unable to load family members.', 'error');
    }
  }

  async function loadApprovedEvidence(familyId, selectNode, statusNode) {
    if (!selectNode) return;
    selectNode.innerHTML = familyId
      ? '<option value="">Loading approved verification evidence...</option>'
      : '<option value="">Select a family to load approved evidence</option>';
    if (!familyId) return;

    try {
      const payload = await window.TOLAuth.apiRequest(
        `/uploads/family/${encodeURIComponent(familyId)}?category=verification_evidence`,
        { method: 'GET' }
      );
      const uploads = (Array.isArray(payload.uploads) ? payload.uploads : [])
        .filter(function (upload) {
          return (
            String(upload.scan_status || '').toLowerCase() === 'clean' &&
            !upload.quarantined &&
            String(upload.verification_status || '').toLowerCase() === 'approved'
          );
        });
      if (!uploads.length) {
        selectNode.innerHTML = '<option value="">No approved evidence yet — use Verification Uploads first</option>';
        return;
      }
      selectNode.innerHTML = uploads.map(function (upload) {
        const label = [
          upload.verification_type || upload.evidence_kind || 'Verification record',
          upload.original_filename || 'approved file'
        ].join(' — ');
        return `<option value="${escapeHtml(upload.id)}">${escapeHtml(label)}</option>`;
      }).join('');
    } catch (error) {
      selectNode.innerHTML = '<option value="">Unable to load approved evidence</option>';
      showStatus(statusNode, error.message || 'Unable to load verification evidence.', 'error');
    }
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function showStatus(node, message, type) {
    if (!node) return;
    node.style.display = 'block';
    node.textContent = message;
    node.style.color = type === 'error' ? '#ffb3b3' : '#cfe8cf';
  }

  function hideStatus(node) {
    if (!node) return;
    node.style.display = 'none';
    node.textContent = '';
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupRelationshipForm();
  });
})();
