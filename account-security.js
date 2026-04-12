(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  function query(name) {
    try {
      const params = new URLSearchParams(window.location.search);
      return String(params.get(name) || "").trim();
    } catch (_error) {
      return "";
    }
  }

  function getErrorMessage(error) {
    return String((error && error.message) || error || "Unknown error");
  }

  function focusResetConfirmFromLink() {
    const mode = query("mode").toLowerCase();
    const token = query("token");
    if (mode !== "reset" || !token) {
      return;
    }

    const panel = document.getElementById("reset-confirm");
    const tokenField = document.querySelector(
      '[data-password-reset-confirm-form] input[name="token"]',
    );

    if (panel && typeof panel.scrollIntoView === "function") {
      panel.scrollIntoView({ block: "start" });
    }
    if (tokenField && typeof tokenField.focus === "function") {
      tokenField.focus();
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
          "Sign in first if you want to change your password from inside the protected workspace. Reset requests and one-time reset tokens still work here without a live session.";
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

    const tokenField = form.querySelector('input[name="token"]');
    if (tokenField) {
      tokenField.value = query("token");
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      app.clearStatus(statusNode);

      const formData = new FormData(form);
      const token = String(formData.get("token") || "").trim();
      const newPassword = String(formData.get("new_password") || "").trim();
      const confirmPassword = String(
        formData.get("confirm_new_password") || "",
      ).trim();

      if (!token || !newPassword || !confirmPassword) {
        app.setStatus(statusNode, "Please complete all reset fields.", "error");
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
      const currentPassword = String(
        formData.get("current_password") || "",
      ).trim();
      const newPassword = String(formData.get("new_password") || "").trim();
      const confirmPassword = String(
        formData.get("confirm_new_password") || "",
      ).trim();

      if (!currentPassword || !newPassword || !confirmPassword) {
        app.setStatus(statusNode, "Please complete all password fields.", "error");
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
    await populateSignedInState();
    setupResetRequestForm();
    setupResetConfirmForm();
    setupPasswordChangeForm();
    focusResetConfirmFromLink();
  });
})();
