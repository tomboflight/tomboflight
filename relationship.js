(function () {
  'use strict';

  async function setupRelationshipForm() {
    const form = document.querySelector('[data-relationship-form]');
    if (!form || !window.TOLAuth) return;

    const familySelect = form.querySelector('[name="family_id"]');
    const sourceInput = form.querySelector('[name="source_member_id"]');
    const targetInput = form.querySelector('[name="target_member_id"]');
    const typeSelect = form.querySelector('[name="relationship_type"]');
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
        notes: String(notesInput.value || '').trim() || null,
        created_by: String(createdByInput.value || '').trim() || null
      };

      if (!payload.family_id || !payload.source_member_id || !payload.target_member_id || !payload.relationship_type) {
        showStatus(statusNode, 'Please complete all required fields.', 'error');
        return;
      }

      if (payload.source_member_id === payload.target_member_id) {
        showStatus(statusNode, 'Source and target member IDs must be different.', 'error');
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
        form.reset();

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