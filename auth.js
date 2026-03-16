(function () {
  'use strict';

  const API_BASE_URL = 'https://tomboflight-api.onrender.com';
  const TOKEN_KEY = 'tol_access_token';

  function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  async function apiRequest(path, options = {}) {
    const token = getToken();

    const headers = {
      Accept: 'application/json',
      ...(options.headers || {})
    };

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers
    });

    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      const message =
        (data && (data.detail || data.message || data.error)) ||
        `Request failed with status ${response.status}`;
      throw new Error(message);
    }

    return data;
  }

  function setStatus(node, message, type) {
    if (!node) return;
    node.style.display = 'block';
    node.textContent = message;
    node.dataset.state = type || 'info';
    node.style.color = type === 'error' ? '#ffb3b3' : '#cfe8cf';
  }

  function clearStatus(node) {
    if (!node) return;
    node.style.display = 'none';
    node.textContent = '';
    node.dataset.state = '';
  }

  async function setupSignupForm() {
    const form = document.querySelector('[data-signup-form]');
    if (!form) return;

    const statusNode = document.querySelector('[data-signup-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);
      const password = String(formData.get('password') || '').trim();
      const confirmPassword = String(formData.get('confirm_password') || '').trim();

      if (password !== confirmPassword) {
        setStatus(statusNode, 'Passwords do not match.', 'error');
        return;
      }

      const payload = {
        full_name: String(formData.get('full_name') || '').trim(),
        email: String(formData.get('email') || '').trim(),
        password: password
      };

      if (!payload.full_name || !payload.email || !payload.password) {
        setStatus(statusNode, 'Please complete all required fields.', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Creating Account...';

      try {
        await apiRequest('/auth/signup', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        setStatus(statusNode, 'Account created successfully. Signing you in...', 'success');

        const loginData = await apiRequest('/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email: payload.email,
            password: payload.password
          })
        });

        if (loginData.access_token) {
          saveToken(loginData.access_token);
          window.location.href = 'dashboard.html';
          return;
        }

        setStatus(statusNode, 'Account created. Please sign in.', 'success');
        form.reset();
      } catch (error) {
        setStatus(statusNode, error.message || 'Signup failed.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Account';
      }
    });
  }

  async function setupSigninForm() {
    const form = document.querySelector('[data-signin-form]');
    if (!form) return;

    const statusNode = document.querySelector('[data-signin-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);

      const payload = {
        email: String(formData.get('email') || '').trim(),
        password: String(formData.get('password') || '').trim()
      };

      if (!payload.email || !payload.password) {
        setStatus(statusNode, 'Please enter your email and password.', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Signing In...';

      try {
        const loginData = await apiRequest('/auth/login', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        if (!loginData.access_token) {
          throw new Error('Login succeeded but no access token was returned.');
        }

        saveToken(loginData.access_token);
        window.location.href = 'dashboard.html';
      } catch (error) {
        setStatus(statusNode, error.message || 'Login failed.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In';
      }
    });
  }

  async function setupDashboard() {
    const dashboard = document.querySelector('[data-dashboard]');
    if (!dashboard) return;

    const authRequired = document.querySelector('[data-auth-required]');
    const userName = document.querySelector('[data-user-name]');
    const userEmail = document.querySelector('[data-user-email]');
    const userRole = document.querySelector('[data-user-role]');
    const logoutBtn = document.querySelector('[data-logout-btn]');
    const statusNode = document.querySelector('[data-dashboard-status]');

    const token = getToken();

    if (!token) {
      window.location.href = 'signin.html';
      return;
    }

    try {
      const me = await apiRequest('/auth/me', { method: 'GET' });

      if (authRequired) authRequired.style.display = 'block';
      if (userName) userName.textContent = me.full_name || 'User';
      if (userEmail) userEmail.textContent = me.email || '';
      if (userRole) userRole.textContent = me.role || 'user';

      setStatus(statusNode, 'You are signed in and connected to the Tomb of Light platform.', 'success');
    } catch (error) {
      clearToken();
      setStatus(statusNode, 'Your session expired. Please sign in again.', 'error');
      setTimeout(function () {
        window.location.href = 'signin.html';
      }, 1200);
      return;
    }

    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        clearToken();
        window.location.href = 'signin.html';
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupSignupForm();
    setupSigninForm();
    setupDashboard();
  });

  window.TOLAuth = {
    saveToken,
    getToken,
    clearToken,
    apiRequest
  };
})();