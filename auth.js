(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const POST_LOGIN_REDIRECT = "dashboard.html";

  if (!app) {
    console.error("auth.js requires app.js to be loaded first.");
    return;
  }

  function getAccessTokenFromResponse(loginData) {
    return (
      loginData?.access_token ||
      loginData?.token ||
      loginData?.accessToken ||
      null
    );
  }

  async function handleLogin(email, password) {
    const loginData = await app.apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    const token = getAccessTokenFromResponse(loginData);

    if (!token) {
      throw new Error("Login succeeded but no access token was returned.");
    }

    app.saveToken(token);

    const me = await app.fetchCurrentUser();
    app.saveUser(me);

    return { loginData, me };
  }

  function redirectAfterLogin() {
    window.location.href = POST_LOGIN_REDIRECT;
  }

  function populateUserFields(user, refs) {
    if (!user || !refs) return;

    if (refs.userName) {
      refs.userName.textContent = user.full_name || "User";
    }

    if (refs.userEmail) {
      refs.userEmail.textContent = user.email || "";
    }

    if (refs.userRole) {
      refs.userRole.textContent = user.role || "user";
    }
  }

  function setupSignupForm() {
    const form = document.querySelector("[data-signup-form]");
    if (!form) return;

    const statusNode = document.querySelector("[data-signup-status]");
    const submitBtn = form.querySelector("[data-submit-btn]");

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);
      const fullName = String(formData.get("full_name") || "").trim();
      const email = String(formData.get("email") || "")
        .trim()
        .toLowerCase();
      const password = String(formData.get("password") || "").trim();
      const confirmPassword = String(
        formData.get("confirm_password") || "",
      ).trim();

      if (!fullName || !email || !password || !confirmPassword) {
        app.setStatus(
          statusNode,
          "Please complete all required fields.",
          "error",
        );
        return;
      }

      if (password.length < 8) {
        app.setStatus(
          statusNode,
          "Password must be at least 8 characters long.",
          "error",
        );
        return;
      }

      if (password !== confirmPassword) {
        app.setStatus(statusNode, "Passwords do not match.", "error");
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Creating Account...";
      }

      try {
        await app.apiRequest("/auth/signup", {
          method: "POST",
          body: JSON.stringify({ full_name: fullName, email, password }),
        });

        app.setStatus(
          statusNode,
          "Account created successfully. Signing you in...",
          "success",
        );

        await handleLogin(email, password);
        redirectAfterLogin();
      } catch (error) {
        app.setStatus(statusNode, error.message || "Signup failed.", "error");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Create Account";
        }
      }
    });
  }

  function setupSigninForm() {
    const form = document.querySelector("[data-signin-form]");
    if (!form) return;

    const statusNode = document.querySelector("[data-signin-status]");
    const submitBtn = form.querySelector("[data-submit-btn]");

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const formData = new FormData(form);
      const email = String(formData.get("email") || "")
        .trim()
        .toLowerCase();
      const password = String(formData.get("password") || "").trim();

      if (!email || !password) {
        app.setStatus(
          statusNode,
          "Please enter your email and password.",
          "error",
        );
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Signing In...";
      }

      try {
        await handleLogin(email, password);
        app.setStatus(statusNode, "Sign-in successful.", "success");
        redirectAfterLogin();
      } catch (error) {
        app.setStatus(statusNode, error.message || "Login failed.", "error");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Sign In";
        }
      }
    });
  }

  async function setupDashboard() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    const authRequired = document.querySelector("[data-auth-required]");
    const userName = document.querySelector("[data-user-name]");
    const userEmail = document.querySelector("[data-user-email]");
    const userRole = document.querySelector("[data-user-role]");
    const statusNode = document.querySelector("[data-dashboard-status]");

    const refs = {
      userName,
      userEmail,
      userRole,
    };

    const token = app.getToken();
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    const savedUser = app.getSavedUser();
    if (savedUser) {
      populateUserFields(savedUser, refs);
    }

    try {
      const me = await app.fetchCurrentUser();
      populateUserFields(me, refs);

      if (authRequired) {
        authRequired.style.display = "block";
      }

      app.setStatus(
        statusNode,
        "You are signed in and connected to the Tomb of Light platform.",
        "success",
      );
    } catch (error) {
      app.clearSession();
      app.setStatus(
        statusNode,
        "Your session is not valid. Please sign in again.",
        "error",
      );
      setTimeout(function () {
        window.location.href = "signin.html";
      }, 1200);
    }
  }

  function bindLogoutButtons() {
    document.querySelectorAll("[data-logout-btn]").forEach(function (button) {
      button.addEventListener("click", function () {
        app.clearSession();
        window.location.href = "signin.html";
      });
    });
  }

  function protectAuthPages() {
    const isSigninPage = !!document.querySelector("[data-signin-form]");
    const isSignupPage = !!document.querySelector("[data-signup-form]");
    const token = app.getToken();

    if (!(isSigninPage || isSignupPage) || !token) {
      return;
    }

    app
      .fetchCurrentUser()
      .then(function () {
        redirectAfterLogin();
      })
      .catch(function () {
        app.clearSession();
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    protectAuthPages();
    setupSignupForm();
    setupSigninForm();
    setupDashboard();
    bindLogoutButtons();
  });

  window.TOLAuthPages = {
    handleLogin,
    redirectAfterLogin,
  };
})();
