(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};

  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  let currentUser = null;
  let currentContext = null;
  let currentProfile = null;
  let stripeClient = null;
  let stripeCardElement = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch (_error) {
      return String(value);
    }
  }

  function getErrorMessage(error) {
    return String((error && error.message) || error || "Unknown error");
  }

  function isInternalUser(user) {
    // Prefer the canonical check from app.js, then the TOLAuthPages export.
    if (app && typeof app.isInternalRole === "function") {
      return app.isInternalRole(user);
    }
    if (authPages && typeof authPages.isInternalRole === "function") {
      return Boolean(authPages.isInternalRole(user));
    }
    return false;
  }

  function isProductionUi() {
    return !(app && typeof app.isLocalApp === "function" && app.isLocalApp());
  }

  function getUserFacingErrorMessage(error) {
    const normalized = String((error && error.message) || error || "").toLowerCase();
    if (normalized.includes("billing_profile_missing")) {
      return "Billing profile has not been created yet.";
    }
    if (normalized.includes("stripe_portal_not_configured")) {
      return "Billing portal is not configured yet.";
    }
    if (typeof console !== "undefined" && typeof console.error === "function") {
      console.error("[Billing] Error details:", error);
    }
    if (isProductionUi()) {
      return "Unable to load data right now.";
    }
    return getErrorMessage(error);
  }

  function getAccountErrorMessage(error) {
    const message = getErrorMessage(error);
    const normalized = message.toLowerCase();
    const safeAccountErrors = [
      "full name is required",
      "enter a valid phone number",
      "street address, city, state or region, and postal code are required",
      "country must use a two-letter country code",
      "current password is incorrect",
      "enter a different email address",
      "that email address is already connected to an account",
      "verification email could not be delivered",
      "email change link is invalid, expired, or already used",
    ];
    if (safeAccountErrors.some(function (safeText) { return normalized.includes(safeText); })) {
      return message.replace(/^\d+\s*:\s*/, "");
    }
    return getUserFacingErrorMessage(error);
  }

  function buildSubscriptionCard(item) {
    const productNames = Array.isArray(item.product_names)
      ? item.product_names.join(", ")
      : "";

    return `
      <div class="family-record-card">
        <div class="card-number">S</div>
        <h3>${escapeHtml(productNames || item.id || "Subscription")}</h3>
        <p class="card-copy"><strong>Status:</strong> ${escapeHtml(item.status || "—")}</p>
        <p class="card-copy"><strong>Collection:</strong> ${escapeHtml(item.collection_method || "—")}</p>
        <p class="card-copy"><strong>Renews:</strong> ${escapeHtml(formatDate(item.current_period_end))}</p>
      </div>
    `;
  }

  function buildCardCard(item) {
    return `
      <div class="family-record-card">
        <div class="card-number">C</div>
        <h3>${escapeHtml((item.brand || "Card").toUpperCase())} •••• ${escapeHtml(item.last4 || "—")}</h3>
        <p class="card-copy"><strong>Expires:</strong> ${escapeHtml(`${item.exp_month || "—"}/${item.exp_year || "—"}`)}</p>
        <p class="card-copy"><strong>Funding:</strong> ${escapeHtml(item.funding || "—")}</p>
        <p class="card-copy"><strong>Default:</strong> ${escapeHtml(item.is_default ? "Yes" : "No")}</p>
        <div class="inline-actions" style="margin-top: 1rem;">
          ${
            item.is_default
              ? ""
              : `<button class="btn btn-secondary" type="button" data-billing-set-default="${escapeHtml(item.id || "")}">Set Default</button>`
          }
          <button class="btn btn-secondary" type="button" data-billing-remove-card="${escapeHtml(item.id || "")}">Remove</button>
        </div>
      </div>
    `;
  }

  function renderMaintenanceLinks() {
    const monthlyLink = document.querySelector("[data-maintenance-monthly-link]");
    const yearlyLink = document.querySelector("[data-maintenance-yearly-link]");
    const paymentLinks = (window.TOL_CONFIG && window.TOL_CONFIG.PAYMENT_LINKS) || {};
    const packageCode = String((currentContext && currentContext.packageCode) || "").trim();
    const monthlyHref = paymentLinks[`${packageCode}_maintenance_monthly`] || "";
    const yearlyHref = paymentLinks[`${packageCode}_maintenance_yearly`] || "";

    if (monthlyLink) {
      monthlyLink.style.display = monthlyHref ? "" : "none";
      if (monthlyHref) {
        monthlyLink.href = monthlyHref;
        monthlyLink.target = "_blank";
        monthlyLink.rel = "noopener noreferrer";
      }
    }
    if (yearlyLink) {
      yearlyLink.style.display = yearlyHref ? "" : "none";
      if (yearlyHref) {
        yearlyLink.href = yearlyHref;
        yearlyLink.target = "_blank";
        yearlyLink.rel = "noopener noreferrer";
      }
    }
  }

  async function loadContext() {
    try {
      const orders = authPages.fetchOrders ? await authPages.fetchOrders() : [];
      currentContext =
        typeof authPages.getDashboardContextForCurrentPage === "function"
          ? await authPages.getDashboardContextForCurrentPage(currentUser, orders)
          : authPages.getDashboardContext
            ? await authPages.getDashboardContext(currentUser, orders)
            : null;
    } catch (error) {
      currentContext = null;
      if (typeof console !== "undefined" && typeof console.error === "function") {
        console.error("[Billing] Failed to resolve customer dashboard context:", error);
      }
    } finally {
      renderMaintenanceLinks();
    }
  }

  function setField(form, name, value) {
    const field = form && form.elements ? form.elements.namedItem(name) : null;
    if (field) field.value = String(value || "");
  }

  async function loadAccountProfile() {
    const form = document.querySelector("[data-account-details-form]");
    const emailNode = document.querySelector("[data-account-current-email]");
    const statusNode = document.querySelector("[data-account-details-status]");
    if (!form) return;
    try {
      currentProfile = await app.apiRequest("/users/me/profile", { method: "GET" });
      const address = (currentProfile && currentProfile.mailing_address) || {};
      setField(form, "full_name", currentProfile && currentProfile.full_name);
      setField(form, "phone_number", currentProfile && currentProfile.phone_number);
      setField(form, "address_line1", address.line1);
      setField(form, "address_line2", address.line2);
      setField(form, "address_city", address.city);
      setField(form, "address_region", address.region);
      setField(form, "address_postal_code", address.postal_code);
      setField(form, "address_country", address.country || "US");
      if (emailNode) {
        emailNode.textContent = String((currentProfile && currentProfile.email) || "—");
      }
      const pendingEmail = String((currentProfile && currentProfile.pending_email) || "");
      if (pendingEmail) {
        app.setStatus(
          document.querySelector("[data-email-change-status]"),
          `Verification is pending for ${pendingEmail}.`,
          "info",
        );
      }
    } catch (error) {
      app.setStatus(statusNode, "Personal details could not be loaded. Try again.", "error");
    }
  }

  async function handleAccountDetailsSave(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const statusNode = document.querySelector("[data-account-details-status]");
    const button = document.querySelector("[data-account-details-save]");
    const formData = new FormData(form);
    const payload = {
      full_name: String(formData.get("full_name") || "").trim(),
      phone_number: String(formData.get("phone_number") || "").trim() || null,
      mailing_address: {
        line1: String(formData.get("address_line1") || "").trim(),
        line2: String(formData.get("address_line2") || "").trim(),
        city: String(formData.get("address_city") || "").trim(),
        region: String(formData.get("address_region") || "").trim(),
        postal_code: String(formData.get("address_postal_code") || "").trim(),
        country: String(formData.get("address_country") || "US").trim().toUpperCase(),
      },
    };
    if (!payload.full_name) {
      app.setStatus(statusNode, "Full name is required.", "error");
      return;
    }
    if (button) button.disabled = true;
    try {
      app.setStatus(statusNode, "Saving your personal details…", "info");
      currentProfile = await app.apiRequest("/users/me/profile", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      const syncStatus = String((currentProfile && currentProfile.billing_sync_status) || "");
      const message = syncStatus === "pending"
        ? "Personal details saved. Billing synchronization is still pending."
        : syncStatus === "synced"
          ? "Personal details saved and your connected billing profile is current."
          : "Personal details saved. No connected billing profile needed updating.";
      app.setStatus(statusNode, message, "success");
    } catch (error) {
      app.setStatus(statusNode, getAccountErrorMessage(error), "error");
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function handleEmailChangeRequest(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const statusNode = document.querySelector("[data-email-change-status]");
    const button = document.querySelector("[data-email-change-submit]");
    const formData = new FormData(form);
    const newEmail = String(formData.get("new_email") || "").trim().toLowerCase();
    const currentPassword = String(formData.get("current_password") || "");
    if (!newEmail || !currentPassword) {
      app.setStatus(statusNode, "New email and current password are required.", "error");
      return;
    }
    if (button) button.disabled = true;
    try {
      const result = await app.apiRequest("/users/me/email-change/request", {
        method: "POST",
        body: JSON.stringify({ new_email: newEmail, current_password: currentPassword }),
      });
      form.reset();
      app.setStatus(
        statusNode,
        String((result && result.message) || "Verification sent to the new email address."),
        "success",
      );
    } catch (error) {
      app.setStatus(statusNode, getAccountErrorMessage(error), "error");
    } finally {
      if (button) button.disabled = false;
    }
  }

  function emailChangeTokenFromHash() {
    const rawHash = String(window.location.hash || "").replace(/^#/, "");
    const params = new URLSearchParams(rawHash);
    return params.get("mode") === "email-change" ? String(params.get("token") || "") : "";
  }

  async function handleEmailChangeConfirmation() {
    const token = emailChangeTokenFromHash();
    if (!token) return false;
    window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.search}`);
    const pageStatus = document.querySelector("[data-billing-page-status]");
    try {
      app.setStatus(pageStatus, "Confirming your new email address…", "info");
      const result = await app.apiRequest("/users/me/email-change/confirm", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      app.clearSession();
      app.setStatus(
        pageStatus,
        String((result && result.message) || "Email updated. Sign in again."),
        "success",
      );
      window.setTimeout(function () {
        window.location.replace("signin.html");
      }, 2200);
    } catch (error) {
      app.setStatus(pageStatus, getAccountErrorMessage(error), "error");
    }
    return true;
  }

  async function refreshOverview() {
    const pageStatus = document.querySelector("[data-billing-page-status]");
    const cardsStatus = document.querySelector("[data-billing-cards-status]");
    const cardsList = document.querySelector("[data-billing-cards-list]");
    const subscriptionsStatus = document.querySelector("[data-billing-subscriptions-status]");
    const subscriptionsList = document.querySelector("[data-billing-subscriptions-list]");
    const addCardCopy = document.querySelector("[data-billing-add-card-copy]");
    const saveCardButton = document.querySelector("[data-billing-save-card]");

    try {
      const payload = await app.apiRequest("/billing/overview", { method: "GET" });
      const paymentMethods = Array.isArray(payload && payload.payment_methods)
        ? payload.payment_methods
        : [];
      const subscriptions = Array.isArray(payload && payload.subscriptions)
        ? payload.subscriptions
        : [];
      const maxCards = Number(payload && payload.max_cards ? payload.max_cards : 3);
      const cardsOnFile = Number(payload && payload.cards_on_file ? payload.cards_on_file : paymentMethods.length);
      const canAddCard = Boolean(payload && payload.can_add_card);
      const payloadErrorCode = String((payload && payload.error_code) || "").trim();
      const payloadMessage = String((payload && payload.message) || "").trim();
      if (payloadErrorCode) {
        if (pageStatus) {
          pageStatus.textContent =
            payloadMessage ||
            getUserFacingErrorMessage(payloadErrorCode) ||
            "Billing profile data is currently unavailable.";
        }
        if (cardsStatus) {
          cardsStatus.textContent = "No saved cards are on file yet.";
        }
        if (subscriptionsStatus) {
          subscriptionsStatus.textContent =
            "No active or historical subscriptions found.";
        }
        if (cardsList) {
          cardsList.innerHTML = `
              <div class="family-record-card">
                <div class="card-number">•</div>
                <h3>No cards saved</h3>
                <p class="card-copy">No saved cards are on file yet.</p>
              </div>
            `;
        }
        if (subscriptionsList) {
          subscriptionsList.innerHTML = `
              <div class="family-record-card">
                <div class="card-number">•</div>
                <h3>No subscriptions found</h3>
                <p class="card-copy">No active or historical subscriptions found.</p>
              </div>
            `;
        }
        if (addCardCopy) {
          addCardCopy.textContent =
            payloadMessage ||
            "Billing profile has not been created yet.";
        }
        if (saveCardButton) {
          saveCardButton.disabled = true;
          saveCardButton.style.opacity = "0.45";
        }
        return;
      }

      if (pageStatus) {
        pageStatus.textContent = `Billing profile connected. ${cardsOnFile} of ${maxCards} saved cards currently on file.`;
      }

      if (cardsStatus) {
        cardsStatus.textContent = paymentMethods.length
          ? "Saved cards are shown below."
          : "No saved cards are on file yet.";
      }

      if (cardsList) {
        cardsList.innerHTML = paymentMethods.length
          ? paymentMethods.map(buildCardCard).join("")
          : `
              <div class="family-record-card">
                <div class="card-number">•</div>
                <h3>No cards saved</h3>
                <p class="card-copy">Add a card below to store up to three payment methods for Tomb of Light billing.</p>
              </div>
            `;
      }

      if (subscriptionsStatus) {
        subscriptionsStatus.textContent = subscriptions.length
          ? "Your Stripe subscriptions and billing records are shown below."
          : "No active or historical subscriptions found.";
      }

      if (subscriptionsList) {
        subscriptionsList.innerHTML = subscriptions.length
          ? subscriptions.map(buildSubscriptionCard).join("")
          : `
              <div class="family-record-card">
                <div class="card-number">•</div>
                <h3>No subscriptions found</h3>
                <p class="card-copy">Use the maintenance links above or your billing portal to begin a continuity plan.</p>
              </div>
            `;
      }

      if (addCardCopy) {
        addCardCopy.textContent = canAddCard
          ? `You can store up to ${maxCards} cards on file for Tomb of Light billing.`
          : `You already have the maximum of ${maxCards} cards on file. Remove one before adding another.`;
      }

      if (saveCardButton) {
        saveCardButton.disabled = !canAddCard;
        saveCardButton.style.opacity = canAddCard ? "" : "0.45";
      }
    } catch (error) {
      if (pageStatus) {
        pageStatus.textContent =
          getUserFacingErrorMessage(error) ||
          "This section is temporarily unavailable.";
      }
      if (cardsStatus) {
        cardsStatus.textContent = "No saved cards are on file yet.";
      }
      if (subscriptionsStatus) {
        subscriptionsStatus.textContent = "No active or historical subscriptions found.";
      }
    }
  }

  async function ensureStripeClient() {
    if (stripeClient && stripeCardElement) return true;

    const mountNode = document.querySelector("[data-stripe-card-element]");
    const statusNode = document.querySelector("[data-billing-card-status]");
    if (!mountNode || typeof window.Stripe !== "function") {
      app.setStatus(statusNode, "Stripe card entry is not available in this browser.", "error");
      return false;
    }

    const config = await app.apiRequest("/billing/config", { method: "GET" });
    if (!config || !config.publishable_key) {
      app.setStatus(statusNode, "Stripe publishable key is not configured yet.", "error");
      return false;
    }

    stripeClient = window.Stripe(config.publishable_key);
    const elements = stripeClient.elements();
    stripeCardElement = elements.create("card", {
      style: {
        base: {
          color: "#f3f5ff",
          fontFamily: "inherit",
          fontSize: "16px",
          "::placeholder": {
            color: "rgba(243,245,255,0.48)",
          },
        },
      },
    });
    stripeCardElement.mount(mountNode);
    return true;
  }

  async function handleCardSave(event) {
    event.preventDefault();
    const statusNode = document.querySelector("[data-billing-card-status]");
    app.clearStatus(statusNode);

    const ready = await ensureStripeClient();
    if (!ready) return;

    try {
      const payload = await app.apiRequest("/billing/setup-intent", {
        method: "POST",
      });
      const clientSecret = String((payload && payload.client_secret) || "").trim();
      if (!clientSecret) {
        throw new Error("Stripe setup intent is missing a client secret.");
      }

      app.setStatus(statusNode, "Saving card...", "info");
      const result = await stripeClient.confirmCardSetup(clientSecret, {
        payment_method: {
          card: stripeCardElement,
          billing_details: {
            email: currentUser && currentUser.email ? currentUser.email : undefined,
            name: currentUser && currentUser.full_name ? currentUser.full_name : undefined,
          },
        },
      });

      if (result.error) {
        throw new Error(result.error.message || "Stripe could not save the card.");
      }

      app.setStatus(statusNode, "Card saved successfully.", "success");
      if (stripeCardElement) {
        stripeCardElement.clear();
      }
      await refreshOverview();
    } catch (error) {
      app.setStatus(
        statusNode,
        getUserFacingErrorMessage(error) || "This section is temporarily unavailable.",
        "error",
      );
    }
  }

  async function openBillingPortal() {
    const pageStatus = document.querySelector("[data-billing-page-status]");
    try {
      app.setStatus(pageStatus, "Opening billing portal...", "info");
      const payload = await app.apiRequest("/billing/portal-session", {
        method: "POST",
        body: JSON.stringify({ return_url: window.location.href }),
      });
      const url = String((payload && payload.url) || "").trim();
      if (!url) {
        throw new Error("Billing portal session did not return a URL.");
      }
      window.location.href = url;
    } catch (error) {
      app.setStatus(
        pageStatus,
        getUserFacingErrorMessage(error) || "Unable to load data right now.",
        "error",
      );
    }
  }

  async function runCardAction(path, successMessage) {
    const statusNode = document.querySelector("[data-billing-card-status]");
    try {
      app.setStatus(statusNode, "Updating card settings...", "info");
      await app.apiRequest(path, { method: path.includes("/default") ? "POST" : "DELETE" });
      app.setStatus(statusNode, successMessage, "success");
      await refreshOverview();
    } catch (error) {
      app.setStatus(
        statusNode,
        getUserFacingErrorMessage(error) || "Unable to load data right now.",
        "error",
      );
    }
  }

  function bindInteractions() {
    const accountDetailsForm = document.querySelector("[data-account-details-form]");
    if (accountDetailsForm) {
      accountDetailsForm.addEventListener("submit", handleAccountDetailsSave);
    }

    const emailChangeForm = document.querySelector("[data-email-change-form]");
    if (emailChangeForm) {
      emailChangeForm.addEventListener("submit", handleEmailChangeRequest);
    }

    const form = document.querySelector("[data-billing-card-form]");
    if (form) {
      form.addEventListener("submit", handleCardSave);
    }

    const portalButton = document.querySelector("[data-open-billing-portal]");
    if (portalButton) {
      portalButton.addEventListener("click", openBillingPortal);
    }

    document
      .querySelectorAll("[data-maintenance-monthly-link], [data-maintenance-yearly-link]")
      .forEach(function (link) {
        const defaultLabel = link.textContent.trim() || "Start Maintenance";
        link.addEventListener("click", function () {
          link.setAttribute("aria-busy", "true");
          link.textContent = "Opening secure checkout...";
          window.setTimeout(function () {
            link.removeAttribute("aria-busy");
            link.textContent = defaultLabel;
          }, 4500);
        });
      });

    document.addEventListener("click", async function (event) {
      const setDefaultButton = event.target.closest("[data-billing-set-default]");
      if (setDefaultButton) {
        const paymentMethodId = setDefaultButton.getAttribute("data-billing-set-default");
        if (!paymentMethodId) return;
        await runCardAction(
          `/billing/payment-methods/${encodeURIComponent(paymentMethodId)}/default`,
          "Default card updated successfully.",
        );
        return;
      }

      const removeButton = event.target.closest("[data-billing-remove-card]");
      if (removeButton) {
        const paymentMethodId = removeButton.getAttribute("data-billing-remove-card");
        if (!paymentMethodId) return;
        if (!window.confirm("Remove this saved card from Tomb of Light billing?")) {
          return;
        }
        await runCardAction(
          `/billing/payment-methods/${encodeURIComponent(paymentMethodId)}`,
          "Card removed successfully.",
        );
      }
    });
  }

  document.addEventListener("DOMContentLoaded", async function () {
    if (await handleEmailChangeConfirmation()) return;
    currentUser = await app.requireSession("signin.html");
    if (!currentUser) return;
    if (isInternalUser(currentUser)) {
      window.location.replace("dashboard.html");
      return;
    }

    bindInteractions();
    await Promise.allSettled([
      loadContext(),
      loadAccountProfile(),
      ensureStripeClient(),
      refreshOverview(),
    ]);
  });
})();
