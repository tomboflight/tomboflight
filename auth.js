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

  function toArray(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.items)) return payload.items;
    if (Array.isArray(payload?.orders)) return payload.orders;
    if (Array.isArray(payload?.data)) return payload.data;
    if (Array.isArray(payload?.submissions)) return payload.submissions;
    return [];
  }

  function getPaidOrder(orders) {
    return (
      orders.find(function (order) {
        const status = String(order?.status || "").toLowerCase();
        return (
          status === "paid" || status === "complete" || status === "succeeded"
        );
      }) || null
    );
  }

  function formatDate(value) {
    if (!value) return "—";

    try {
      return new Date(value).toLocaleString();
    } catch (error) {
      return String(value);
    }
  }

  function setLinkEnabled(element, enabled) {
    if (!element) return;

    if (!element.dataset.originalHref && element.getAttribute("href")) {
      element.dataset.originalHref = element.getAttribute("href");
    }

    if (enabled) {
      element.style.pointerEvents = "";
      element.style.opacity = "";
      element.removeAttribute("aria-disabled");

      if (element.dataset.originalHref) {
        element.setAttribute("href", element.dataset.originalHref);
      }
    } else {
      element.style.pointerEvents = "none";
      element.style.opacity = "0.45";
      element.setAttribute("aria-disabled", "true");
    }
  }

  function setButtonEnabled(element, enabled) {
    if (!element) return;

    element.disabled = !enabled;
    element.style.opacity = enabled ? "" : "0.45";
    element.style.pointerEvents = enabled ? "" : "none";
    element.setAttribute("aria-disabled", enabled ? "false" : "true");
  }

  function setActionEnabled(element, enabled) {
    if (!element) return;

    if (element.tagName === "A") {
      setLinkEnabled(element, enabled);
    } else {
      setButtonEnabled(element, enabled);
    }
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

    if (refs.userName) refs.userName.textContent = user.full_name || "User";
    if (refs.userEmail) refs.userEmail.textContent = user.email || "";
    if (refs.userRole) refs.userRole.textContent = user.role || "user";
  }

  async function fetchOrders() {
    const payload = await app.apiRequest("/orders/my-orders", {
      method: "GET",
    });
    return toArray(payload);
  }

  async function fetchLatestIntake() {
    try {
      return await app.apiRequest("/intake-submissions/my-latest", {
        method: "GET",
      });
    } catch (error) {
      if ((error.message || "").includes("404")) return null;
      throw error;
    }
  }

  async function fetchIntakeHistory() {
    try {
      const payload = await app.apiRequest(
        "/intake-submissions/my-list?limit=10",
        {
          method: "GET",
        },
      );
      return toArray(payload);
    } catch (error) {
      if ((error.message || "").includes("404")) return [];
      throw error;
    }
  }

  function renderOrders(orders) {
    const statusNode = document.querySelector("[data-orders-status]");
    const listNode = document.querySelector("[data-orders-list]");
    if (!statusNode || !listNode) return;

    listNode.innerHTML = "";

    if (!orders.length) {
      statusNode.textContent = "No purchases have been recorded yet.";
      return;
    }

    statusNode.textContent = "Your recorded purchases are listed below.";

    orders.forEach(function (order, index) {
      const card = document.createElement("div");
      card.className = "feature-card feature-card-clean";
      card.innerHTML = `
        <div class="card-number">${index + 1}</div>
        <h3>${order.package_name || order.package_slug || "Package"}</h3>
        <p class="card-copy">Status: ${order.status || "unknown"}</p>
        <p class="card-copy">Price: ${order.price_label || "—"}</p>
        <p class="card-copy">Created: ${formatDate(order.created_at)}</p>
      `;
      listNode.appendChild(card);
    });
  }

  function updateAccessState(paidOrder) {
    const accessStatus = document.querySelector("[data-access-status]");
    const paidActions = document.querySelectorAll("[data-paid-action]");
    const intakeOpenAction = document.querySelector(
      "[data-intake-open-action]",
    );
    const upgradeAction = document.querySelector("[data-upgrade-action]");

    const hasPaidOrder = !!paidOrder;

    paidActions.forEach(function (element) {
      setActionEnabled(element, hasPaidOrder);
    });

    if (intakeOpenAction) {
      setActionEnabled(intakeOpenAction, hasPaidOrder);
      intakeOpenAction.style.display = hasPaidOrder ? "" : "none";
    }

    if (upgradeAction) {
      upgradeAction.style.display = hasPaidOrder ? "none" : "";
    }

    if (!accessStatus) return;

    if (hasPaidOrder) {
      accessStatus.textContent = `Access unlocked through ${paidOrder.package_name || paidOrder.package_slug || "your paid package"}.`;
    } else {
      accessStatus.textContent =
        "Purchase required. Buy a Tomb of Light package to unlock platform tools.";
    }
  }

  function renderNoIntakeBecauseNoPurchase() {
    const intakeStatus = document.querySelector("[data-intake-card-status]");
    const currentPackage = document.querySelector(
      "[data-intake-current-package]",
    );
    const submissionStatus = document.querySelector(
      "[data-intake-status-badge]",
    );
    const submissionId = document.querySelector("[data-intake-submission-id]");
    const submittedAt = document.querySelector("[data-intake-submitted-at]");
    const nextStep = document.querySelector("[data-intake-next-step]");
    const lockNote = document.querySelector("[data-intake-lock-note]");
    const intakeHistoryStatus = document.querySelector(
      "[data-intake-history-status]",
    );
    const intakeHistoryList = document.querySelector(
      "[data-intake-history-list]",
    );

    if (intakeStatus)
      intakeStatus.textContent = "Purchase required before intake opens.";
    if (currentPackage) currentPackage.textContent = "No package detected";
    if (submissionStatus) submissionStatus.textContent = "Not submitted";
    if (submissionId) submissionId.textContent = "—";
    if (submittedAt) submittedAt.textContent = "—";
    if (nextStep)
      nextStep.textContent = "Purchase a package first to unlock intake.";
    if (lockNote)
      lockNote.textContent = "Intake is locked until a paid order exists.";
    if (intakeHistoryStatus)
      intakeHistoryStatus.textContent = "No intake submissions found yet.";
    if (intakeHistoryList) intakeHistoryList.innerHTML = "";
  }

  function renderIntake(latest, history, paidOrder) {
    const intakeStatus = document.querySelector("[data-intake-card-status]");
    const currentPackage = document.querySelector(
      "[data-intake-current-package]",
    );
    const submissionStatus = document.querySelector(
      "[data-intake-status-badge]",
    );
    const submissionId = document.querySelector("[data-intake-submission-id]");
    const submittedAt = document.querySelector("[data-intake-submitted-at]");
    const nextStep = document.querySelector("[data-intake-next-step]");
    const lockNote = document.querySelector("[data-intake-lock-note]");
    const intakeHistoryStatus = document.querySelector(
      "[data-intake-history-status]",
    );
    const intakeHistoryList = document.querySelector(
      "[data-intake-history-list]",
    );

    if (!latest) {
      if (intakeStatus)
        intakeStatus.textContent = "No intake submission found yet.";
      if (currentPackage)
        currentPackage.textContent =
          paidOrder?.package_name || "Paid package detected";
      if (submissionStatus) submissionStatus.textContent = "Not submitted";
      if (submissionId) submissionId.textContent = "—";
      if (submittedAt) submittedAt.textContent = "—";
      if (nextStep)
        nextStep.textContent =
          "Open your intake flow and submit the review step.";
      if (lockNote)
        lockNote.textContent =
          "Editing is open because no final submission exists yet.";
    } else {
      const latestStatus =
        latest.status || latest.submission_status || "submitted";
      const locked =
        String(latestStatus).toLowerCase() === "submitted" ||
        String(latestStatus).toLowerCase() === "final";

      if (intakeStatus)
        intakeStatus.textContent =
          "Your most recent intake submission is shown below.";
      if (currentPackage)
        currentPackage.textContent =
          latest.package_name ||
          paidOrder?.package_name ||
          "Paid package detected";
      if (submissionStatus) submissionStatus.textContent = latestStatus;
      if (submissionId)
        submissionId.textContent = latest.id || latest._id || "—";
      if (submittedAt)
        submittedAt.textContent = formatDate(
          latest.submitted_at || latest.created_at,
        );
      if (nextStep)
        nextStep.textContent = locked
          ? "Your submission is on file for review."
          : "Continue and finalize your intake.";
      if (lockNote)
        lockNote.textContent = locked
          ? "Editing is locked after final submission."
          : "Editing is still open until final submission.";
    }

    if (!intakeHistoryStatus || !intakeHistoryList) return;

    intakeHistoryList.innerHTML = "";

    if (!history.length) {
      intakeHistoryStatus.textContent = "No intake submissions found yet.";
      return;
    }

    intakeHistoryStatus.textContent =
      "Your recent intake submissions are listed below.";

    history.forEach(function (item, index) {
      const card = document.createElement("div");
      card.className = "feature-card feature-card-clean";
      card.innerHTML = `
        <div class="card-number">${index + 1}</div>
        <h3>${item.package_name || "Intake Submission"}</h3>
        <p class="card-copy">Status: ${item.status || item.submission_status || "submitted"}</p>
        <p class="card-copy">Created: ${formatDate(item.created_at || item.submitted_at)}</p>
      `;
      intakeHistoryList.appendChild(card);
    });
  }

  async function setupSignupForm() {
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

    const refs = { userName, userEmail, userRole };

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

      if (authRequired) authRequired.style.display = "block";

      app.setStatus(
        statusNode,
        "You are signed in and connected to the Tomb of Light platform.",
        "success",
      );

      const orders = await fetchOrders();
      renderOrders(orders);

      const paidOrder = getPaidOrder(orders);
      updateAccessState(paidOrder);

      if (!paidOrder) {
        renderNoIntakeBecauseNoPurchase();
        return;
      }

      const [latest, history] = await Promise.all([
        fetchLatestIntake(),
        fetchIntakeHistory(),
      ]);

      renderIntake(latest, history, paidOrder);
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

  async function gatePurchaseRequiredPages() {
    const page = window.location.pathname.split("/").pop() || "";
    const intakePages = new Set([
      "intake-welcome.html",
      "intake-household.html",
      "intake-family-map.html",
      "intake-uploads.html",
      "intake-consent.html",
      "intake-review.html",
    ]);

    if (!intakePages.has(page)) return;

    const user = await app.requireSession("signin.html");
    if (!user) return;

    try {
      const orders = await fetchOrders();
      const paidOrder = getPaidOrder(orders);

      if (!paidOrder) {
        window.location.href = "dashboard.html?purchase_required=1";
      }
    } catch (error) {
      window.location.href = "dashboard.html?purchase_required=1";
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
    gatePurchaseRequiredPages();
  });

  window.TOLAuthPages = {
    handleLogin,
    redirectAfterLogin,
  };
})();
