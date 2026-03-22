(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const DRAFT_KEY = "tol_intake_draft_v1";
  const LATEST_SUBMISSION_CACHE_KEY = "tol_latest_intake_submission_v1";

  const LOCKED_STATUSES = new Set([
    "submitted",
    "in_review",
    "approved",
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
  ]);

  if (!app || typeof app.apiRequest !== "function") {
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

  function clearDraft() {
    localStorage.removeItem(DRAFT_KEY);
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

  function cacheLatestSubmission(submission) {
    try {
      if (!submission) {
        localStorage.removeItem(LATEST_SUBMISSION_CACHE_KEY);
        return;
      }
      localStorage.setItem(
        LATEST_SUBMISSION_CACHE_KEY,
        JSON.stringify(submission),
      );
    } catch (error) {
      // ignore cache failures
    }
  }

  function getCachedLatestSubmission() {
    try {
      const raw = localStorage.getItem(LATEST_SUBMISSION_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function normalizeStatus(status) {
    return String(status || "")
      .trim()
      .toLowerCase();
  }

  function isLockedStatus(status) {
    return LOCKED_STATUSES.has(normalizeStatus(status));
  }

  function humanizeStatus(status) {
    const normalized = normalizeStatus(status);
    if (!normalized) return "Unknown";

    return normalized
      .split("_")
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function statusMessage(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "submitted") {
      return "Your intake has been submitted and is waiting for review.";
    }
    if (normalized === "in_review") {
      return "Your intake is currently under review.";
    }
    if (normalized === "approved") {
      return "Your intake has been approved.";
    }
    if (normalized === "build_ready") {
      return "Your intake has been approved and provisioned for production.";
    }
    if (normalized === "in_production") {
      return "Your intake has moved into production.";
    }
    if (normalized === "qa_review") {
      return "Your project is in internal quality review.";
    }
    if (normalized === "client_review") {
      return "Your project is prepared for client review.";
    }
    if (normalized === "delivered") {
      return "Your project has been delivered.";
    }
    if (normalized === "archived") {
      return "Your project has been archived.";
    }
    if (normalized === "rejected") {
      return "Your intake was rejected and can be edited and resubmitted.";
    }
    return "";
  }

  function reviewNextStep(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "submitted") {
      return "Waiting for review to begin.";
    }
    if (normalized === "in_review") {
      return "Reviewer is evaluating your intake details.";
    }
    if (normalized === "approved") {
      return "Approved and waiting for production provisioning.";
    }
    if (normalized === "build_ready") {
      return "Production records have been created and the build is ready to move forward.";
    }
    if (normalized === "in_production") {
      return "Your lineage build is actively being produced.";
    }
    if (normalized === "qa_review") {
      return "Your project is being checked in internal quality review.";
    }
    if (normalized === "client_review") {
      return "Your project is ready for your review.";
    }
    if (normalized === "delivered") {
      return "Your project has been delivered.";
    }
    if (normalized === "archived") {
      return "Your project has been archived.";
    }
    if (normalized === "rejected") {
      return "Review the feedback, update your intake, and resubmit.";
    }
    return "Complete your intake and submit it for review.";
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

    return (
      orders.find(function (order) {
        const status = String(order?.status || "").toLowerCase();
        return ["paid", "complete", "completed", "succeeded"].includes(status);
      }) || null
    );
  }

  async function getLatestSubmission() {
    try {
      const latest = await app.apiRequest("/intake-submissions/my-latest", {
        method: "GET",
      });
      cacheLatestSubmission(latest);
      return latest;
    } catch (error) {
      const message = getErrorMessage(error).toLowerCase();
      if (message.includes("no intake submissions found")) {
        cacheLatestSubmission(null);
        return null;
      }
      throw error;
    }
  }

  function lockFormForReview(form, statusNode, latestSubmission) {
    if (!form || !latestSubmission) return;

    const status = normalizeStatus(latestSubmission.status);
    if (!isLockedStatus(status)) return;

    form.querySelectorAll("input, textarea, select").forEach(function (field) {
      if (field.type === "checkbox") {
        field.disabled = true;
      } else {
        field.readOnly = true;
        field.disabled = true;
      }
    });

    form.querySelectorAll('button[type="submit"]').forEach(function (button) {
      button.disabled = true;
      button.textContent = humanizeStatus(status);
    });

    if (statusNode) {
      setStatus(
        statusNode,
        `${statusMessage(status)} ${reviewNextStep(status)}`,
        "info",
      );
    }
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
    const intakeStart = document.querySelector("[data-intake-start]");

    try {
      const paidOrder = await fetchPaidOrder();
      const latestSubmission = await getLatestSubmission();
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

        if (packagePath) {
          packagePath.innerHTML = `
            ${formatReviewBlock("Household Setup", ["Confirm household ownership and household details."], "A")}
            ${formatReviewBlock("Family Map", ["Outline parents, spouse, children, and branch structure."], "B")}
            ${formatReviewBlock("Uploads", ["Plan photos, records, and supporting files for this build."], "C")}
            ${formatReviewBlock("Consent", ["Confirm privacy, processing, and storage permissions."], "D")}
            ${formatReviewBlock("Review & Submit", ["Review the saved onboarding data before final submission."], "E")}
          `;
        }

        if (latestSubmission && isLockedStatus(latestSubmission.status)) {
          if (intakeStatus) {
            intakeStatus.textContent = statusMessage(latestSubmission.status);
          }
          if (packageSummary) {
            packageSummary.textContent = `${statusMessage(latestSubmission.status)} ${reviewNextStep(latestSubmission.status)}`;
          }
          if (intakeStart) {
            intakeStart.textContent = "View Submitted Intake";
            intakeStart.setAttribute("href", "intake-review.html");
          }
        } else if (
          latestSubmission &&
          normalizeStatus(latestSubmission.status) === "rejected"
        ) {
          if (intakeStatus) {
            intakeStatus.textContent =
              "Your intake was rejected. You may update it and resubmit.";
          }
          if (intakeStart) {
            intakeStart.textContent = "Resume Intake";
            intakeStart.setAttribute("href", "intake-household.html");
          }
        } else {
          if (intakeStatus) {
            intakeStatus.textContent = `Your package is active: ${paidOrder.package_name || "Active Package"}. Begin your household onboarding below.`;
          }
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
        if (intakeStart) {
          intakeStart.classList.add("disabled");
          intakeStart.setAttribute("href", "dashboard.html");
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

    const savedUser = app.getSavedUser ? app.getSavedUser() : null;
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

    getLatestSubmission()
      .then(function (latestSubmission) {
        if (latestSubmission) {
          lockFormForReview(form, statusNode, latestSubmission);
        }
      })
      .catch(function () {});

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

    getLatestSubmission()
      .then(function (latestSubmission) {
        if (latestSubmission) {
          lockFormForReview(form, statusNode, latestSubmission);
        }
      })
      .catch(function () {});

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

    getLatestSubmission()
      .then(function (latestSubmission) {
        if (latestSubmission) {
          lockFormForReview(form, statusNode, latestSubmission);
        }
      })
      .catch(function () {});

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

    getLatestSubmission()
      .then(function (latestSubmission) {
        if (latestSubmission) {
          lockFormForReview(form, statusNode, latestSubmission);
        }
      })
      .catch(function () {});

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
    const notesField = form
      ? form.querySelector('[name="final_intake_notes"]')
      : null;
    const confirmField = form
      ? form.querySelector('[name="confirm_accuracy"]')
      : null;

    if (!form) return;

    renderReviewSummaryBlocks();

    getLatestSubmission()
      .then(function (latestSubmission) {
        if (!latestSubmission) return;

        const normalized = normalizeStatus(latestSubmission.status);

        if (reviewHeadline) {
          reviewHeadline.textContent =
            statusMessage(normalized) || reviewHeadline.textContent;
        }

        if (isLockedStatus(normalized)) {
          if (notesField) {
            notesField.readOnly = true;
            notesField.disabled = true;
          }

          if (confirmField) {
            confirmField.disabled = true;
          }

          if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = humanizeStatus(normalized);
          }

          setStatus(
            statusNode,
            `${statusMessage(normalized)} ${reviewNextStep(normalized)}`,
            "info",
          );
        }

        if (normalized === "rejected") {
          setStatus(
            statusNode,
            "This intake was rejected. You may update your intake and submit again after making changes.",
            "error",
          );
        }
      })
      .catch(function () {});

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearStatus(statusNode);

      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const latestSubmission = await getLatestSubmission().catch(function () {
        return getCachedLatestSubmission();
      });

      if (latestSubmission && isLockedStatus(latestSubmission.status)) {
        setStatus(
          statusNode,
          `${statusMessage(latestSubmission.status)} ${reviewNextStep(latestSubmission.status)}`,
          "info",
        );
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

        const response = await app.apiRequest("/intake-submissions", {
          method: "POST",
          body: JSON.stringify(submissionPayload),
        });

        cacheLatestSubmission(response);

        const nextDraft = {
          ...draft,
          submitted: true,
          submission_id: response?.id || null,
          latest_status: response?.status || "submitted",
        };
        saveDraft(nextDraft);

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
