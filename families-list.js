(function () {
  'use strict';

  async function loadFamilies() {
    const listNode = document.querySelector('[data-families-list]');
    const emptyNode = document.querySelector('[data-families-empty]');
    const errorNode = document.querySelector('[data-families-error]');
    const countNode = document.querySelector('[data-families-count]');

    if (!listNode || !window.TOLAuth) return;

    const token = window.TOLAuth.getToken();
    if (!token) return;

    listNode.innerHTML = '';

    if (emptyNode) {
      emptyNode.style.display = 'none';
    }

    if (errorNode) {
      errorNode.style.display = 'none';
      errorNode.textContent = '';
    }

    if (countNode) {
      countNode.textContent = 'Loading...';
    }

    try {
      const families = await window.TOLAuth.apiRequest('/families/', {
        method: 'GET'
      });

      if (!Array.isArray(families) || families.length === 0) {
        if (countNode) {
          countNode.textContent = '0 family records';
        }

        if (emptyNode) {
          emptyNode.style.display = 'block';
        }

        return;
      }

      if (countNode) {
        countNode.textContent = `${families.length} family record${families.length === 1 ? '' : 's'}`;
      }

      families.forEach(function (family, index) {
        const card = document.createElement('div');
        card.className = 'family-record-card';

        const createdAt = family.created_at
          ? new Date(family.created_at).toLocaleString()
          : 'Unknown';

        card.innerHTML = `
          <div class="card-number">${index + 1}</div>
          <h3>${escapeHtml(family.family_name || 'Unnamed Family')}</h3>
          <p class="card-copy"><strong>Created By:</strong> ${escapeHtml(family.created_by || 'Unknown')}</p>
          <p class="card-copy"><strong>Description:</strong> ${escapeHtml(family.description || 'No description provided.')}</p>
          <p class="card-copy"><strong>Created:</strong> ${escapeHtml(createdAt)}</p>
          <p class="card-copy"><strong>Family ID:</strong> ${escapeHtml(family.id || '')}</p>
        `;

        listNode.appendChild(card);
      });
    } catch (error) {
      if (countNode) {
        countNode.textContent = 'Unable to load families';
      }

      if (errorNode) {
        errorNode.style.display = 'block';
        errorNode.textContent = error.message || 'Failed to load family records.';
      }
    }
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
    loadFamilies();
  });

  window.TOLFamilies = {
    loadFamilies
  };
})();