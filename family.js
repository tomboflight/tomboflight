(function () {
  'use strict';

  async function setupCreateFamilyForm() {
    const form = document.querySelector('[data-create-family-form]');
    if (!form || !window.TOLAuth) return;

    const statusNode = document.querySelector('[data-family-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');
    const createdByInput = form.querySelector('[name="created_by"]');

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
    } catch (error) {
      window.TOLAuth.clearSession();
      window.location.href = 'signin.html';
      return;
    }

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

      const payload = {
        family_name: String(formData.get('family_name') || '').trim(),
        created_by: String(formData.get('created_by') || '').trim(),
        description: String(formData.get('description') || '').trim() || null
      };

      if (!payload.family_name || !payload.created_by) {
        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.style.color = '#ffb3b3';
          statusNode.textContent = 'Please complete the required fields.';
        }
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Creating Family...';

      try {
        const family = await window.TOLAuth.apiRequest('/families/', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.style.color = '#cfe8cf';
          statusNode.textContent = `Family created successfully: ${family.family_name}`;
        }

        form.reset();

        if (createdByInput) {
          try {
            const me = await window.TOLAuth.apiRequest('/auth/me', { method: 'GET' });
            createdByInput.value = me.full_name || me.email || '';
          } catch (error) {
            createdByInput.value = '';
          }
        }

        setTimeout(function () {
          window.location.href = 'dashboard.html';
        }, 1200);
      } catch (error) {
        if (statusNode) {
          statusNode.style.display = 'block';
          statusNode.style.color = '#ffb3b3';
          statusNode.textContent = error.message || 'Failed to create family.';
        }
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Family';
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupCreateFamilyForm();
  });
})();