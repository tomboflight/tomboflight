(function () {
  'use strict';

  const API_BASE_URL =
    (window.TOL_CONFIG && window.TOL_CONFIG.API_BASE_URL) || '';

  const TOKEN_KEY = 'tol_access_token';
  const USER_KEY = 'tol_user';
  const POST_LOGIN_REDIRECT = 'dashboard.html';

  function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function saveUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user || {}));
  }

  function getSavedUser() {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function clearUser() {
    localStorage.removeItem(USER_KEY);
  }

  function clearSession() {
    clearToken();
    clearUser();
  }

  function isLocalApp() {
    const host = window.location.hostname;
    return host === '127.0.0.1' || host === 'localhost' || host === '::1';
  }

  async function apiRequest(path, options = {}) {
    if (!API_BASE_URL) {
      throw new Error(
        isLocalApp()
          ? 'API base URL is missing. Check config.js and make sure the backend is running at http://127.0.0.1:8000.'
          : 'Sign-in is currently available only in the local app environment until the live API is deployed.'
      );
    }

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

    let response;

    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers
      });
    } catch (networkError) {
      throw new Error(
        `Network error calling API.\n\n` +
        `API_BASE_URL: ${API_BASE_URL}\n` +
        `Page origin: ${window.location.origin}\n\n` +
        `Make sure frontend is on http://127.0.0.1:5500 and backend is on http://127.0.0.1:8000.`
      );
    }

    const contentType = response.headers.get('content-type') || '';
    let data = null;

    try {
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        const text = await response.text();
        data = text ? { detail: text } : null;
      }
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      const message =
        (data &&
          (data.detail ||
            data.message ||
            data.error ||
            (Array.isArray(data.errors) && data.errors.join(', ')))) ||
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

    if (type === 'error') {
      node.style.color = '#ffb3b3';
    } else if (type === 'success') {
      node.style.color = '#cfe8cf';
    } else {
      node.style.color = '#d6e6ff';
    }
  }

  function clearStatus(node) {
    if (!node) return;
    node.style.display = 'none';
    node.textContent = '';
    node.dataset.state = '';
  }

  async function handleLogin(email, password) {
    const loginData = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });

    const token =
      loginData?.access_token ||
      loginData?.token ||
      loginData?.accessToken ||
      null;

    if (!token) {
      throw new Error('Login succeeded but no access token was returned.');
    }

    saveToken(token);

    const me = await apiRequest('/auth/me', { method: 'GET' });
    saveUser(me);

    return { loginData, me };
  }

  function redirectAfterLogin() {
    const target = POST_LOGIN_REDIRECT;

    fetch(target, { method: 'HEAD' })
      .then(function (response) {
        if (response.ok) {
          window.location.href = target;
        } else {
          window.location.href = 'index.html';
        }
      })
      .catch(function () {
        window.location.href = 'index.html';
      });
  }

  function setupSignupForm() {
    const form = document.querySelector('[data-signup-form]');
    if (!form) return;

    const statusNode = document.querySelector('[data-signup-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) return;

      const formData = new FormData(form);
      const fullName = String(formData.get('full_name') || '').trim();
      const email = String(formData.get('email') || '').trim().toLowerCase();
      const password = String(formData.get('password') || '').trim();
      const confirmPassword = String(formData.get('confirm_password') || '').trim();

      if (!fullName || !email || !password || !confirmPassword) {
        setStatus(statusNode, 'Please complete all required fields.', 'error');
        return;
      }

      if (password.length < 8) {
        setStatus(statusNode, 'Password must be at least 8 characters long.', 'error');
        return;
      }

      if (password !== confirmPassword) {
        setStatus(statusNode, 'Passwords do not match.', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Creating Account...';

      try {
        await apiRequest('/auth/signup', {
          method: 'POST',
          body: JSON.stringify({ full_name: fullName, email, password })
        });

        setStatus(statusNode, 'Account created successfully. Signing you in...', 'success');

        await handleLogin(email, password);
        redirectAfterLogin();
      } catch (error) {
        setStatus(statusNode, error.message || 'Signup failed.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Account';
      }
    });
  }

  function setupSigninForm() {
    const form = document.querySelector('[data-signin-form]');
    if (!form) return;

    const statusNode = document.querySelector('[data-signin-status]');
    const submitBtn = form.querySelector('[data-submit-btn]');

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === 'function' && !form.reportValidity()) return;

      const formData = new FormData(form);
      const email = String(formData.get('email') || '').trim().toLowerCase();
      const password = String(formData.get('password') || '').trim();

      if (!email || !password) {
        setStatus(statusNode, 'Please enter your email and password.', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Signing In...';

      try {
        await handleLogin(email, password);
        setStatus(statusNode, 'Sign-in successful.', 'success');
        redirectAfterLogin();
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

    const savedUser = getSavedUser();
    if (savedUser) {
      if (userName) userName.textContent = savedUser.full_name || 'User';
      if (userEmail) userEmail.textContent = savedUser.email || '';
      if (userRole) userRole.textContent = savedUser.role || 'user';
    }

    try {
      const me = await apiRequest('/auth/me', { method: 'GET' });
      saveUser(me);

      if (authRequired) authRequired.style.display = 'block';
      if (userName) userName.textContent = me.full_name || 'User';
      if (userEmail) userEmail.textContent = me.email || '';
      if (userRole) userRole.textContent = me.role || 'user';

      setStatus(statusNode, 'You are signed in and connected to the Tomb of Light platform.', 'success');
    } catch (error) {
      clearSession();
      setStatus(statusNode, 'Your session is not valid. Please sign in again.', 'error');
      setTimeout(function () {
        window.location.href = 'signin.html';
      }, 1200);
      return;
    }

    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        clearSession();
        window.location.href = 'signin.html';
      });
    }
  }

  function protectAuthPages() {
    const isSigninPage = !!document.querySelector('[data-signin-form]');
    const isSignupPage = !!document.querySelector('[data-signup-form]');
    const token = getToken();

    if ((isSigninPage || isSignupPage) && token) {
      apiRequest('/auth/me', { method: 'GET' })
        .then(function () {
          redirectAfterLogin();
        })
        .catch(function () {
          clearSession();
        });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    protectAuthPages();
    setupSignupForm();
    setupSigninForm();
    setupDashboard();
  });

  window.TOLAuth = {
    saveToken,
    getToken,
    clearToken,
    saveUser,
    getSavedUser,
    clearUser,
    clearSession,
    apiRequest
  };
})();