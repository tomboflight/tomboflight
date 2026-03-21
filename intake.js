(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const DRAFT_KEY = "tol_intake_draft_v1";

  if (!app) {
    console.error("intake.js requires app.js/auth.js to be loaded first.");
    return;
  }

  function getErrorMessage(error) {
    if (!error) return "Unknown error";
    if (typeof error === "string") return error;
    if (error.message) return String(error.message);
    return String(error);
  }

  function loadDraft() {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  }

  function saveDraft(nextDraft) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(nextDraft || {}));
  }

  function mergeDraft(sectionKey, values) {
    const draft = loadDraft();
    draft[sectionKey] = {
      ...(draft[sectionKey] || {}),
      ...(values || {}),
    };
    saveDraft(draft);
    return draft;
  }

  function setStatus(node, message, type) {
    if (!node) return;
    node.style.display = "block";
    node.textContent = message;
    node.dataset.state = type || "info";

    if (type === "error") {
      node.style.color = "#ffb3b3";
    } else if (type === "success") {
      node.style.color = "#cfe8cf";
    } else {
      node.style.color = "#d6e6ff";
    }
  }

  function clearStatus(node) {
    if (!node) return;
    node.style.display = "none";
    node.textContent = "";
    node.dataset.state = "";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function hydrateForm(form, values) {
    if (!form || !values) return;

    Object.entries(values).forEach(function ([key, value]) {
      const field = form.querySelector(`[name="${key}"]`);
      if (!field) return;

      if (field.type === "checkbox") {
        field.checked = Boolean(value);
      } else {
        field.value = value ?? "";
      }
    });
  }

  function formToObject(form) {
    const data = {};

    form.querySelectorAll("input, textarea, select").forEach(function (field) {
      if (!field.name) return;

      if (field.type === "checkbox") {
        data[field.name] = field.checked;
      } else {
        data[field.name] = field.value;
      }
    });

    return data;
  }

  function getPaidOrder(orders) {
    return (
      orders.find(function (order) {
        const status = String(order?.status || "").toLowerCase();
        return (
          status === "paid" ||
          status === "complete" ||
          status === "completed" ||
          status === "succeeded"
        );
      }) || null
    );
  }

  async function fetchPaidOrder() {
    const payload = await app.apiRequest("/orders/my-orders", {
      method: "GET",
    });
    const orders = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.orders)
        ? payload.orders
        : Array.isArray(payload?.data)
          ? payload.data
          : [];
    return getPaidOrder(orders);
  }

  function formatReviewBlock(title, lines, number) {
    const safeLines = (lines || []).filter(Boolean);

    return `
      <div>
        <div class="card-number">${escapeHtml(number)}</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${safeLines.map(escapeHtml).join("<br />")}</p>
      </div>
    `;
  }

  async function setupIntakeWelcome() {
    const page = document.querySelector("[data-intake-welcome]");
    if (!page) return;

    const intakeStatus = document.querySelector("[data-intake-status]");
    const packageName = document.querySelector("[data-package-name]");
    const packageSummary = document.querySelector("[data-package-summary]");
    const packagePath = document.querySelector("[data-package-path]");

    try {
      const paidOrder = await fetchPaidOrder();
      const draft = loadDraft();

      if (paidOrder) {
        draft.package_name =
          paidOrder.package_name || draft.package_name || "Active Package";
        draft.package_slug = paidOrder.package_slug || draft.package_slug || "";
        saveDraft(draft);

        if (packageName) {
          packageName.textContent = paidOrder.package_name || "Active Package";
        }

        if (packageSummary) {
          packageSummary.textContent = `Your package is active and ready for onboarding. Current unlocked package: ${paidOrder.package_name || "Active Package"}.`;
        }

        if (intakeStatus) {
          intakeStatus.textContent = `Your package is active: ${paidOrder.package_name || "Active Package"}. Begin your household onboarding below.`;
        }

        if (packagePath) {
          packagePath.innerHTML = `
            ${formatReviewBlock("Household Setup", ["Confirm household ownership and household details."], "A")}
            ${formatReviewBlock("Family Map", ["Outline parents, spouse, children, and branch structure."], "B")}
            ${formatReviewBlock("Uploads", ["Plan photos, records, and supporting files for this build."], "C")}
            ${formatReviewBlock("Consent", ["Confirm privacy, processing, and storage permissions."], "D")}
            ${formatReviewBlock("Review & Submit", ["Review the saved onboarding data before final submission."], "E")}
          `;
        }
      } else {
        if (packageName) packageName.textContent = "No active package detected";
        if (packageSummary) {
          packageSummary.textContent =
            "We could not confirm a paid package for this account yet.";
        }
        if (intakeStatus) {
          intakeStatus.textContent =
            "Purchase is required before onboarding can continue.";
        }
      }
    } catch (error) {
      if (intakeStatus) {
        intakeStatus.textContent =
          "Your onboarding path could not be loaded right now.";
      }
    }
  }

  function setupHouseholdForm() {
    const page = document.querySelector("[data-intake-household]");
    if (!page) return;

    const form = document.querySelector("[data-household-form]");
    const statusNode = document.querySelector("[data-household-form-status]");
    const headlineStatus = document.querySelector("[data-household-status]");
    const submitBtn = document.querySelector("[data-household-submit-btn]");

    if (!form) return;

    const draft = loadDraft();
    hydrateForm(form, draft.household || {});

    const savedUser = app.getSavedUser();
    if (savedUser) {
      const current = formToObject(form);

      if (!current.primary_contact_name) {
        const field = form.querySelector('[name="primary_contact_name"]');
        if (field) field.value = savedUser.full_name || "";
      }

      if (!current.primary_contact_email) {
        const field = form.querySelector('[name="primary_contact_email"]');
        if (field) field.value = savedUser.email || "";
      }
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const values = formToObject(form);
      mergeDraft("household", values);

      if (headlineStatus) {
        headlineStatus.textContent =
          "Household setup has been saved for this onboarding draft.";
      }

      setStatus(statusNode, "Household setup saved successfully.", "success");

      if (submitBtn) {
        submitBtn.blur();
      }
    });
  }

  function setupFamilyMapForm() {
    const page = document.querySelector("[data-intake-family-map]");
    if (!page) return;

    const form = document.querySelector("[data-family-map-form]");
    const statusNode = document.querySelector("[data-family-map-form-status]");
    const headlineStatus = document.querySelector("[data-family-map-status]");
    const submitBtn = document.querySelector("[data-family-map-submit-btn]");

    if (!form) return;

    const draft = loadDraft();
    hydrateForm(form, draft.family_map || {});

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const values = formToObject(form);
      mergeDraft("family_map", values);

      if (headlineStatus) {
        headlineStatus.textContent =
          "Family map has been saved for this onboarding draft.";
      }

      setStatus(statusNode, "Family map saved successfully.", "success");

      if (submitBtn) {
        submitBtn.blur();
      }
    });
  }

  function setupUploadsForm() {
    const page = document.querySelector("[data-intake-uploads]");
    if (!page) return;

    const form = document.querySelector("[data-intake-uploads-form]");
    const statusNode = document.querySelector(
      "[data-intake-uploads-form-status]",
    );
    const submitBtn = document.querySelector(
      "[data-intake-uploads-submit-btn]",
    );

    if (!form) return;

    const draft = loadDraft();
    hydrateForm(form, draft.uploads || {});

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      const values = formToObject(form);
      mergeDraft("uploads", values);

      setStatus(statusNode, "Upload plan saved successfully.", "success");

      if (submitBtn) {
        submitBtn.blur();
      }
    });
  }

  function setupConsentForm() {
    const page = document.querySelector("[data-intake-consent]");
    if (!page) return;

    const form = document.querySelector("[data-intake-consent-form]");
    const statusNode = document.querySelector(
      "[data-intake-consent-form-status]",
    );
    const submitBtn = document.querySelector(
      "[data-intake-consent-submit-btn]",
    );

    if (!form) return;

    const draft = loadDraft();
    hydrateForm(form, draft.consent || {});

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const values = formToObject(form);
      mergeDraft("consent", values);

      setStatus(statusNode, "Consent saved successfully.", "success");

      if (submitBtn) {
        submitBtn.blur();
      }
    });
  }

  function renderReviewSummaryBlocks() {
    const page = document.querySelector("[data-intake-review]");
    if (!page) return;

    const draft = loadDraft();

    const householdNode = document.querySelector(
      "[data-review-household-summary]",
    );
    const familyMapNode = document.querySelector(
      "[data-review-family-map-summary]",
    );
    const uploadsNode = document.querySelector("[data-review-uploads-summary]");
    const consentNode = document.querySelector("[data-review-consent-summary]");

    if (householdNode) {
      const h = draft.household || {};
      householdNode.innerHTML = formatReviewBlock(
        h.household_name || "Household Setup",
        [
          `Primary Contact: ${h.primary_contact_name || "—"}`,
          `Email: ${h.primary_contact_email || "—"}`,
          `Role: ${h.household_role || "—"}`,
        ],
        "1",
      );
    }

    if (familyMapNode) {
      const f = draft.family_map || {};
      familyMapNode.innerHTML = formatReviewBlock(
        f.family_branch_name || "Family Map",
        [
          `People in Scope: ${f.people_in_scope || "—"}`,
          `Parent One: ${f.parent_one || "—"}`,
          `Parent Two: ${f.parent_two || "—"}`,
          `Children: ${f.children_names || "—"}`,
        ],
        "2",
      );
    }

    if (uploadsNode) {
      const u = draft.uploads || {};
      uploadsNode.innerHTML = formatReviewBlock(
        "Uploads",
        [
          `Approx. Uploads: ${u.approx_upload_count || "—"}`,
          `Primary Asset Type: ${u.primary_asset_type || "—"}`,
          `Key Portraits: ${u.key_portraits || "—"}`,
        ],
        "3",
      );
    }

    if (consentNode) {
      const c = draft.consent || {};
      consentNode.innerHTML = formatReviewBlock(
        "Consent",
        [
          `Process Consent: ${c.consent_process ? "Yes" : "No"}`,
          `Store Consent: ${c.consent_store ? "Yes" : "No"}`,
          `Visibility: ${c.visibility_preference || "—"}`,
        ],
        "4",
      );
    }
  }

  function setupReviewForm() {
    const page = document.querySelector("[data-intake-review]");
    if (!page) return;

    const form = document.querySelector("[data-intake-review-form]");
    const statusNode = document.querySelector(
      "[data-intake-review-form-status]",
    );
    const reviewHeadline = document.querySelector(
      "[data-intake-review-status]",
    );
    const submitBtn = document.querySelector("[data-intake-review-submit-btn]");

    if (!form) return;

    renderReviewSummaryBlocks();

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const draft = loadDraft();

      if (!draft.household || !draft.family_map) {
        setStatus(
          statusNode,
          "Household Setup and Family Map must be saved before submission.",
          "error",
        );
        return;
      }

      const formValues = formToObject(form);
      mergeDraft("review", formValues);

      const submissionPayload = {
        package_name: draft.package_name || "",
        package_slug: draft.package_slug || "",
        household: draft.household || {},
        family_map: draft.family_map || {},
        uploads: draft.uploads || {},
        consent: draft.consent || {},
        review: {
          final_intake_notes: formValues.final_intake_notes || "",
          confirm_accuracy: Boolean(formValues.confirm_accuracy),
        },
        status: "submitted",
        source: "web",
        submitted_at: new Date().toISOString(),
      };

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "Submitting Intake...";
        }

        const response = await app.apiRequest("/intake-submissions/", {
          method: "POST",
          body: JSON.stringify(submissionPayload),
        });

        saveDraft({
          ...draft,
          submitted: true,
          submission_id:
            response?.id || response?.submission_id || response?._id || null,
        });

        if (reviewHeadline) {
          reviewHeadline.textContent =
            "Your intake review has been submitted successfully.";
        }

        setStatus(statusNode, "Intake submitted successfully.", "success");

        setTimeout(function () {
          window.location.href = "dashboard.html";
        }, 1200);
      } catch (error) {
        setStatus(
          statusNode,
          `Submission failed: ${getErrorMessage(error)}`,
          "error",
        );
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Submit Intake Review";
        }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupIntakeWelcome();
    setupHouseholdForm();
    setupFamilyMapForm();
    setupUploadsForm();
    setupConsentForm();
    setupReviewForm();
  });
})();
