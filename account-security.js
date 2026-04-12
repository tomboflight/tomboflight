(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  const PASSWORD_POLICY_MESSAGE =
    "Password must be at least 12 characters and include at least one uppercase letter, one lowercase letter, one number, and one special character.";

  function query(name) {
    try {
      const params = new URLSearchParams(window.location.search);
      return String(params.get(name) || "").trim();
    } catch (_error) {
      return "";
    }
  }

  const resetState = {
    mode: query("mode").toLowerCase(),
    token: query("token"),
  };

  function hasResetTokenFromEmailLink() {
    return resetState.mode === "reset" && resetState.token.length >= 16;
  }

  function getErrorMessage(error) {
    return String((error && error.message) || error || "Unknown error");
  }

  function validatePasswordStrength(password) {
    const value = String(password || "");
    if (value.length < 12) {
      return PASSWORD_POLICY_MESSAGE;
    }
    if (!/[A-Z]/.test(value)) {
      return PASSWORD_POLICY_MESSAGE;
    }
    if (!/[a-z]/.test(value)) {
      return PASSWORD_POLICY_MESSAGE;
    }
    if (!/\d/.test(value)) {
      return PASSWORD_POLICY_MESSAGE;
    }
    if (!/[^A-Za-z0-9]/.test(value)) {
      return PASSWORD_POLICY_MESSAGE;
    }
    return "";
  }

  function setupResetModeUi() {
    const requestPanel = document.querySelector(
      "[data-password-reset-request-panel]",
    );
    const confirmPanel = document.querySelector(
      "[data-password-reset-confirm-panel]",
    );
    const changePanel = document.querySelector("[data-password-change-panel]");
    const pageStatus = document.querySelector(
      "[data-account-security-page-status]",
    );

    if (hasResetTokenFromEmailLink()) {
      if (requestPanel) requestPanel.hidden = true;
      if (confirmPanel) confirmPanel.hidden = false;
      if (changePanel) changePanel.hidden = true;
      if (pageStatus) {
        pageStatus.textContent =
          "Choose a new password for your Tomb of Light account. The secure link from your email will be verified when you submit.";
      }
      return;
    }

    if (requestPanel) requestPanel.hidden = false;
    if (confirmPanel) confirmPanel.hidden = true;
    if (changePanel) changePanel.hidden = false;
    if (resetState.mode === "reset" && pageStatus) {
      pageStatus.textContent =
        "This reset link is incomplete. Request a fresh password reset email to continue.";
    }
  }

  function focusResetFormFromLink() {
    if (!hasResetTokenFromEmailLink()) {
      return;
    }

    const panel = document.getElementById("reset-confirm");
    const passwordField = document.querySelector(
      '[data-password-reset-confirm-form] input[name="new_password"]',
    );

    if (panel && typeof panel.scrollIntoView === "function") {
      panel.scrollIntoView({ block: "start" });
    }
    if (passwordField && typeof passwordField.focus === "function") {
      passwordField.focus();
    }
  }

  async function populateSignedInState() {
    const introNode = document.querySelector("[data-password-change-intro]");
    try {
      const me = await app.fetchCurrentUser();
      if (introNode) {
        introNode.textContent =
          "You are signed in. Use this form to change your Tomb of Light password directly inside the protected workspace.";
      }
      return me;
    } catch (_error) {
      if (introNode) {
        introNode.textContent =
          "Sign in first if you want to change your password from inside the protected workspace. Password reset links still work here without a live session.";
      }
      return null;
    }
  }

  function setupResetRequestForm() {
    const form = document.querySelector("[data-password-reset-request-form]");
    if (!form) return;
    const statusNode = document.querySelector(
      "[data-password-reset-request-status]",
    );

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      const formData = new FormData(form);
      const email = String(formData.get("email") || "")
        .trim()
        .toLowerCase();

      if (!email) {
        app.setStatus(statusNode, "Email address is required.", "error");
        return;
      }

      try {
        const payload = await app.apiRequest("/auth/password-reset/request", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        const message = String(
          (payload && payload.message) ||
            "Password reset request created successfully.",
        );
        app.setStatus(statusNode, message, "success");
        form.reset();
      } catch (error) {
        app.setStatus(
          statusNode,
          getErrorMessage(error) || "Unable to request password reset.",
          "error",
        );
      }
    });
  }

  function setupResetConfirmForm() {
    const form = document.querySelector("[data-password-reset-confirm-form]");
    if (!form) return;
    const statusNode = document.querySelector(
      "[data-password-reset-confirm-status]",
    );

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      const formData = new FormData(form);
      const token = String(resetState.token || "").trim();
      const newPassword = String(formData.get("new_password") || "");
      const confirmPassword = String(
        formData.get("confirm_new_password") || "",
      );

      if (!token) {
        app.setStatus(
          statusNode,
          "Use the secure password reset link from your email to continue.",
          "error",
        );
        return;
      }

      if (!newPassword || !confirmPassword) {
        app.setStatus(statusNode, "Please complete all password fields.", "error");
        return;
      }

      const passwordPolicyError = validatePasswordStrength(newPassword);
      if (passwordPolicyError) {
        app.setStatus(statusNode, passwordPolicyError, "error");
        return;
      }

      if (newPassword !== confirmPassword) {
        app.setStatus(statusNode, "New passwords do not match.", "error");
        return;
      }

      try {
        await app.apiRequest("/auth/password-reset/confirm", {
          method: "POST",
          body: JSON.stringify({
            token,
            new_password: newPassword,
          }),
        });
        app.setStatus(
          statusNode,
          "Password reset completed successfully. You can sign in now.",
          "success",
        );
        form.reset();
      } catch (error) {
        app.setStatus(
          statusNode,
          getErrorMessage(error) || "Unable to apply password reset.",
          "error",
        );
      }
    });
  }

  function setupPasswordChangeForm() {
    const form = document.querySelector("[data-password-change-form]");
    if (!form) return;
    const statusNode = document.querySelector("[data-password-change-status]");

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      const formData = new FormData(form);
      const currentPassword = String(formData.get("current_password") || "");
      const newPassword = String(formData.get("new_password") || "");
      const confirmPassword = String(
        formData.get("confirm_new_password") || "",
      );

      if (!currentPassword || !newPassword || !confirmPassword) {
        app.setStatus(statusNode, "Please complete all password fields.", "error");
        return;
      }

      const passwordPolicyError = validatePasswordStrength(newPassword);
      if (passwordPolicyError) {
        app.setStatus(statusNode, passwordPolicyError, "error");
        return;
      }

      if (newPassword !== confirmPassword) {
        app.setStatus(statusNode, "New passwords do not match.", "error");
        return;
      }

      try {
        await app.apiRequest("/auth/password-change", {
          method: "POST",
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
            confirm_new_password: confirmPassword,
          }),
        });
        app.setStatus(statusNode, "Password changed successfully.", "success");
        form.reset();
      } catch (error) {
        app.setStatus(
          statusNode,
          getErrorMessage(error) || "Unable to change password.",
          "error",
        );
      }
    });
  }

  document.addEventListener("DOMContentLoaded", async function () {
    setupResetModeUi();
    await populateSignedInState();
    setupResetRequestForm();
    setupResetConfirmForm();
    setupPasswordChangeForm();
    focusResetFormFromLink();
  });
})();
