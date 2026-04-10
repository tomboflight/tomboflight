(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};

  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  let currentUser = null;
  let currentContext = null;
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

  function getUserFacingErrorMessage(error) {
    if (typeof console !== "undefined" && typeof console.error === "function") {
      console.error("[Billing] Error details:", error);
    }
    return getErrorMessage(error);
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
      if (monthlyHref) monthlyLink.href = monthlyHref;
    }
    if (yearlyLink) {
      yearlyLink.style.display = yearlyHref ? "" : "none";
      if (yearlyHref) yearlyLink.href = yearlyHref;
    }
  }

  async function loadContext() {
    const orders = authPages.fetchOrders ? await authPages.fetchOrders() : [];
    currentContext =
      typeof authPages.getDashboardContextForCurrentPage === "function"
        ? await authPages.getDashboardContextForCurrentPage(currentUser, orders)
        : authPages.getDashboardContext
          ? await authPages.getDashboardContext(currentUser, orders)
          : null;
    renderMaintenanceLinks();
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
          : "No active or historical Stripe subscriptions were found for this customer profile yet.";
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
        pageStatus.textContent = getUserFacingErrorMessage(error) || "Billing profile could not be loaded.";
      }
      if (cardsStatus) {
        cardsStatus.textContent = "Saved cards could not be loaded.";
      }
      if (subscriptionsStatus) {
        subscriptionsStatus.textContent = "Subscription records could not be loaded.";
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
        getUserFacingErrorMessage(error) || "Unable to save card.",
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
        getUserFacingErrorMessage(error) || "Unable to open billing portal.",
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
        getUserFacingErrorMessage(error) || "Unable to update card.",
        "error",
      );
    }
  }

  function bindInteractions() {
    const form = document.querySelector("[data-billing-card-form]");
    if (form) {
      form.addEventListener("submit", handleCardSave);
    }

    const portalButton = document.querySelector("[data-open-billing-portal]");
    if (portalButton) {
      portalButton.addEventListener("click", openBillingPortal);
    }

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
    currentUser = await app.requireSession("signin.html");
    if (!currentUser) return;

    bindInteractions();
    await loadContext();
    await ensureStripeClient();
    await refreshOverview();
  });
})();
