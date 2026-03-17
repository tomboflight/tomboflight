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
      const generationRaw = String(formData.get('generation') || '').trim();

      const payload = {
        family_id: String(formData.get('family_id') || '').trim(),
        first_name: String(formData.get('first_name') || '').trim(),
        last_name: String(formData.get('last_name') || '').trim(),
        birth_year: birthYearRaw ? Number(birthYearRaw) : null,
        generation: generationRaw ? Number(generationRaw) : 0,
        father_id: String(formData.get('father_id') || '').trim() || null,
        mother_id: String(formData.get('mother_id') || '').trim() || null,
        spouse_id: String(formData.get('spouse_id') || '').trim() || null,
        bio: String(formData.get('bio') || '').trim() || null
      };

      if (!payload.family_id || !payload.first_name || !payload.last_name) {
        showStatus(statusNode, 'Please complete all required fields.', 'error');
        return;
      }

      if (!Number.isInteger(payload.generation) || payload.generation < 0) {
        showStatus(statusNode, 'Generation must be 0 or greater.', 'error');
        return;
      }

      if (payload.birth_year !== null && !Number.isInteger(payload.birth_year)) {
        showStatus(statusNode, 'Birth year must be a valid number.', 'error');
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