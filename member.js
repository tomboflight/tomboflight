(function () {
  'use strict';

  async function setupAddMemberForm() {
    const form = document.querySelector('[data-add-member-form]');
    if (!form || !window.TOLAuth) return;

    const familySelect = form.querySelector('[name="family_id"]');
    const statusNode = document.querySelector('[data-member-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');

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

    await loadFamiliesIntoSelect(familySelect, statusNode);
    familySelect.addEventListener('change', function () {
      loadExistingMembers(form, familySelect.value, statusNode);
    });

    form.addEventListener('submit', async function (event) {
      event.preventDefault();

      if (statusNode) {
        statusNode.style.display = 'none';
        statusNode.textContent = '';
      }

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);

      const birthYearRaw = String(formData.get('birth_year') || '').trim();
      const payload = {
        family_id: String(formData.get('family_id') || '').trim(),
        first_name: String(formData.get('first_name') || '').trim(),
        last_name: String(formData.get('last_name') || '').trim(),
        birth_year: birthYearRaw ? Number(birthYearRaw) : null,
        generation: null,
        father_id: String(formData.get('father_id') || '').trim() || null,
        mother_id: String(formData.get('mother_id') || '').trim() || null,
        spouse_id: String(formData.get('spouse_id') || '').trim() || null,
        father_relationship_type: String(formData.get('father_relationship_type') || 'biological_parent').trim(),
        mother_relationship_type: String(formData.get('mother_relationship_type') || 'biological_parent').trim(),
        partner_relationship_type: String(formData.get('partner_relationship_type') || 'spouse').trim(),
        relationship_mode: 'narrative',
        privacy_scope: 'household_private',
        identity_matching_consent: Boolean(formData.get('identity_matching_consent')),
        account_required: Boolean(formData.get('account_required')),
        invite_email: String(formData.get('invite_email') || '').trim().toLowerCase() || null,
        account_member_role: String(formData.get('account_member_role') || 'viewer').trim(),
        bio: String(formData.get('bio') || '').trim() || null
      };

      if (!payload.family_id || !payload.first_name || !payload.last_name) {
        showStatus(statusNode, 'Please complete all required fields.', 'error');
        return;
      }

      if (payload.birth_year !== null && !Number.isInteger(payload.birth_year)) {
        showStatus(statusNode, 'Birth year must be a valid number.', 'error');
        return;
      }

      if (payload.account_required && !payload.invite_email) {
        showStatus(statusNode, 'Enter the email for the family member who needs an account.', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Adding Member...';

      try {
        const result = await window.TOLAuth.apiRequest('/family-members', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        showStatus(
          statusNode,
          `Family member created successfully. Member ID: ${result.family_member_id}`,
          'success'
        );

        form.reset();
        await loadFamiliesIntoSelect(familySelect, statusNode, true);

        setTimeout(function () {
          window.location.href = 'dashboard.html';
        }, 1400);
      } catch (error) {
        showStatus(statusNode, error.message || 'Failed to create family member.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Add Family Member';
      }
    });
  }

  async function loadExistingMembers(form, familyId, statusNode) {
    const selects = [
      form.querySelector('[name="father_id"]'),
      form.querySelector('[name="mother_id"]'),
      form.querySelector('[name="spouse_id"]')
    ].filter(Boolean);
    const placeholder = familyId
      ? '<option value="">Loading family members...</option>'
      : '<option value="">Select a family first</option>';
    selects.forEach(function (select) {
      select.innerHTML = placeholder;
    });
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
          return displayName(a).localeCompare(displayName(b));
        })
        .map(function (member) {
          return `<option value="${escapeHtml(member.id)}">${escapeHtml(displayName(member))} — generation ${escapeHtml(member.generation ?? 'unplaced')}</option>`;
        })
        .join('');
      selects.forEach(function (select) {
        select.innerHTML = `<option value="">None / not yet known</option>${options}`;
      });
    } catch (error) {
      selects.forEach(function (select) {
        select.innerHTML = '<option value="">Unable to load members</option>';
      });
      showStatus(statusNode, error.message || 'Unable to load existing family members.', 'error');
    }
  }

  function displayName(member) {
    return String(
      member.full_name ||
      member.display_name ||
      `${member.first_name || ''} ${member.last_name || ''}`
    ).trim() || 'Unnamed family member';
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  async function loadFamiliesIntoSelect(selectNode, statusNode, preservePlaceholder) {
    if (!selectNode || !window.TOLAuth) return;

    const currentValue = preservePlaceholder ? '' : selectNode.value;
    selectNode.innerHTML = '<option value="">Select a family</option>';

    try {
      const families = await window.TOLAuth.apiRequest('/families/', {
        method: 'GET'
      });

      if (!Array.isArray(families) || families.length === 0) {
        showStatus(
          statusNode,
          'No family records found. Please create a family first.',
          'error'
        );
        return;
      }

      families.forEach(function (family) {
        const option = document.createElement('option');
        option.value = family.id;
        option.textContent = `${family.family_name} (${family.created_by})`;
        selectNode.appendChild(option);
      });

      if (currentValue) {
        selectNode.value = currentValue;
      }
    } catch (error) {
      showStatus(
        statusNode,
        error.message || 'Unable to load families.',
        'error'
      );
    }
  }

  function showStatus(node, message, type) {
    if (!node) return;
    node.style.display = 'block';
    node.textContent = message;
    node.style.color = type === 'error' ? '#ffb3b3' : '#cfe8cf';
    node.dataset.state = type || 'info';
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupAddMemberForm();
  });
})();
