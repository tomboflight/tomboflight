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
  let signedInUser = null;

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
      signedInUser = me;
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
      signedInUser = null;
      return null;
    }
  }

  function normalizeMfaEntry(value) {
    return String(value || "")
      .trim()
      .replace(/\s+/g, "");
  }

  function setHidden(element, hidden) {
    if (element) {
      element.hidden = Boolean(hidden);
    }
  }

  function setButtonBusy(button, busy, busyLabel, defaultLabel) {
    if (!button) return;
    button.disabled = Boolean(busy);
    button.textContent = busy ? busyLabel : defaultLabel;
  }

  function renderMfaState(user) {
    const introNode = document.querySelector("[data-mfa-settings-intro]");
    const statusNode = document.querySelector("[data-mfa-settings-status]");
    const disabledControls = document.querySelector("[data-mfa-disabled-controls]");
    const enabledControls = document.querySelector("[data-mfa-enabled-controls]");
    const setupPanel = document.querySelector("[data-mfa-setup-panel]");
    const backupPanel = document.querySelector("[data-mfa-backup-codes-panel]");

    setHidden(setupPanel, true);
    setHidden(backupPanel, true);

    if (!user) {
      if (introNode) {
        introNode.textContent =
          "Sign in to choose whether your account requires an authenticator code at login.";
      }
      setHidden(disabledControls, true);
      setHidden(enabledControls, true);
      app.setStatus(
        statusNode,
        "Sign in before changing authenticator settings.",
        "info",
      );
      return;
    }

    app.clearStatus(statusNode);

    if (user.mfa_enabled) {
      if (introNode) {
        introNode.textContent =
          "Authenticator verification is currently enabled for this account.";
      }
      setHidden(disabledControls, true);
      setHidden(enabledControls, false);
      return;
    }

    if (introNode) {
      introNode.textContent =
        "Authenticator verification is optional. You can enable it here whenever you want an extra sign-in step.";
    }
    setHidden(disabledControls, false);
    setHidden(enabledControls, true);
  }

  async function refreshMfaUserState() {
    try {
      signedInUser = await app.fetchCurrentUser();
    } catch (_error) {
      signedInUser = null;
    }
    renderMfaState(signedInUser);
    return signedInUser;
  }

  function showBackupCodes(codes) {
    const backupPanel = document.querySelector("[data-mfa-backup-codes-panel]");
    const backupList = document.querySelector("[data-mfa-backup-codes]");
    if (backupList) {
      backupList.innerHTML = "";
      const backupCodes = Array.isArray(codes) ? codes : [];
      if (!backupCodes.length) {
        const item = document.createElement("li");
        item.textContent = "No recovery codes were returned for this session.";
        backupList.appendChild(item);
      }
      backupCodes.forEach(function (code) {
        const item = document.createElement("li");
        item.textContent = code;
        backupList.appendChild(item);
      });
    }
    setHidden(backupPanel, false);
  }

  function setupMfaControls() {
    const startButton = document.querySelector("[data-mfa-start-enrollment]");
    const cancelButton = document.querySelector("[data-mfa-cancel-setup]");
    const setupPanel = document.querySelector("[data-mfa-setup-panel]");
    const disabledControls = document.querySelector("[data-mfa-disabled-controls]");
    const enrollmentForm = document.querySelector("[data-mfa-enrollment-form]");
    const disableForm = document.querySelector("[data-mfa-disable-form]");
    const statusNode = document.querySelector("[data-mfa-settings-status]");
    const secretNode = document.querySelector("[data-mfa-enrollment-secret]");
    const otpauthNode = document.querySelector("[data-mfa-otpauth-url]");
    let setupToken = "";

    if (startButton) {
      const defaultLabel = startButton.textContent.trim() || "Set Up Authenticator";
      startButton.addEventListener("click", async function () {
        app.clearStatus(statusNode);
        setButtonBusy(startButton, true, "Preparing...", defaultLabel);

        try {
          const payload = await app.apiRequest("/auth/mfa/enroll/begin-session", {
            method: "POST",
            body: JSON.stringify({}),
          });
          setupToken = String(payload?.setup_token || "").trim();
          if (!setupToken) {
            throw new Error("Authenticator setup could not be started.");
          }

          if (secretNode) {
            secretNode.textContent = String(payload?.secret || "").trim();
          }
          if (otpauthNode) {
            otpauthNode.value = String(payload?.otpauth_url || "").trim();
          }

          setHidden(disabledControls, true);
          setHidden(setupPanel, false);
          app.setStatus(
            statusNode,
            "Add this key to your authenticator app, then enter the first code it creates.",
            "info",
          );
        } catch (error) {
          app.setStatus(
            statusNode,
            getErrorMessage(error) || "Unable to start authenticator setup.",
            "error",
          );
        } finally {
          setButtonBusy(startButton, false, "Preparing...", defaultLabel);
        }
      });
    }

    if (cancelButton) {
      cancelButton.addEventListener("click", function () {
        setupToken = "";
        if (enrollmentForm && typeof enrollmentForm.reset === "function") {
          enrollmentForm.reset();
        }
        if (secretNode) {
          secretNode.textContent = "";
        }
        if (otpauthNode) {
          otpauthNode.value = "";
        }
        setHidden(setupPanel, true);
        setHidden(disabledControls, false);
        app.clearStatus(statusNode);
      });
    }

    if (enrollmentForm) {
      const submitButton = enrollmentForm.querySelector('button[type="submit"]');
      const defaultLabel =
        (submitButton && submitButton.textContent.trim()) || "Activate MFA";

      enrollmentForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        app.clearStatus(statusNode);

        if (
          typeof enrollmentForm.reportValidity === "function" &&
          !enrollmentForm.reportValidity()
        ) {
          return;
        }

        const formData = new FormData(enrollmentForm);
        const code = normalizeMfaEntry(formData.get("code"));
        if (!setupToken) {
          app.setStatus(
            statusNode,
            "Authenticator setup has expired. Start setup again.",
            "error",
          );
          return;
        }
        if (!code) {
          app.setStatus(statusNode, "Enter the authenticator code.", "error");
          return;
        }

        setButtonBusy(submitButton, true, "Activating...", defaultLabel);

        try {
          const payload = await app.apiRequest("/auth/mfa/enroll/verify", {
            method: "POST",
            body: JSON.stringify({ setup_token: setupToken, code }),
          });
          const token = String(payload?.access_token || "").trim();
          if (token) {
            app.saveToken(token);
          }
          setupToken = "";
          if (typeof enrollmentForm.reset === "function") {
            enrollmentForm.reset();
          }
          await refreshMfaUserState();
          showBackupCodes(payload?.backup_codes);
          app.setStatus(
            statusNode,
            "Authenticator MFA is active. Save your recovery codes now.",
            "success",
          );
        } catch (error) {
          app.setStatus(
            statusNode,
            getErrorMessage(error) || "Unable to activate authenticator MFA.",
            "error",
          );
        } finally {
          setButtonBusy(submitButton, false, "Activating...", defaultLabel);
        }
      });
    }

    if (disableForm) {
      const submitButton = disableForm.querySelector('button[type="submit"]');
      const defaultLabel =
        (submitButton && submitButton.textContent.trim()) || "Disable MFA";

      disableForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        app.clearStatus(statusNode);

        const formData = new FormData(disableForm);
        const currentPassword = String(formData.get("current_password") || "");
        const code = normalizeMfaEntry(formData.get("code"));
        const recoveryCode = normalizeMfaEntry(formData.get("recovery_code"));

        if (!currentPassword) {
          app.setStatus(statusNode, "Current password is required.", "error");
          return;
        }
        if (!code && !recoveryCode) {
          app.setStatus(
            statusNode,
            "Enter an authenticator code or recovery code.",
            "error",
          );
          return;
        }
        if (code && recoveryCode) {
          app.setStatus(
            statusNode,
            "Use either an authenticator code or a recovery code.",
            "error",
          );
          return;
        }

        setButtonBusy(submitButton, true, "Disabling...", defaultLabel);

        try {
          await app.apiRequest("/auth/mfa/disable", {
            method: "POST",
            body: JSON.stringify({
              current_password: currentPassword,
              code: code || null,
              recovery_code: recoveryCode || null,
            }),
          });
          if (typeof disableForm.reset === "function") {
            disableForm.reset();
          }
          await refreshMfaUserState();
          app.setStatus(statusNode, "Authenticator MFA is disabled.", "success");
        } catch (error) {
          app.setStatus(
            statusNode,
            getErrorMessage(error) || "Unable to disable authenticator MFA.",
            "error",
          );
        } finally {
          setButtonBusy(submitButton, false, "Disabling...", defaultLabel);
        }
      });
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
    renderMfaState(signedInUser);
    setupResetRequestForm();
    setupResetConfirmForm();
    setupPasswordChangeForm();
    setupMfaControls();
    focusResetFormFromLink();
  });
})();
