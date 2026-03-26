(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const DRAFT_KEY = "tol_intake_draft_v1";
  const LATEST_SUBMISSION_CACHE_KEY = "tol_latest_intake_submission_v1";
  const POLICY_VERSION = "2026-03-26";

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

  function mergeDraft(sectionKey, values) {
    const draft = loadDraft();
    draft[sectionKey] = {
      ...(draft[sectionKey] || {}),
      ...(values || {}),
      _saved_at: new Date().toISOString(),
      _policy_version: POLICY_VERSION,
    };
    draft._draft_meta = {
      ...(draft._draft_meta || {}),
      last_updated_at: new Date().toISOString(),
      policy_version: POLICY_VERSION,
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

  function validateRequiredForm(form, statusNode) {
    if (!form) return false;

    if (typeof form.reportValidity === "function" && !form.reportValidity()) {
      setStatus(
        statusNode,
        "Please complete all required fields and confirmations before continuing.",
        "error",
      );
      return false;
    }

    return true;
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

  function renderSummaryCard(node, title, number, lines) {
    if (!node) return;
    node.innerHTML = `
      <div>
        <div class="card-number">${escapeHtml(number)}</div>
        <h3>${escapeHtml(title)}</h3>
        <p class="card-copy">${lines.map(escapeHtml).join("<br />")}</p>
      </div>
    `;
  }

  function renderReviewSummaryBlocks(source) {
    const page = document.querySelector("[data-intake-review]");
    if (!page) return;

    const draft = loadDraft();
    const data = source || draft;

    const household = data.household || draft.household || {};
    const familyMap = data.family_map || draft.family_map || {};
    const uploads = data.uploads || draft.uploads || {};
    const consent = data.consent || draft.consent || {};

    const householdNode = document.querySelector(
      "[data-review-household-summary]",
    );
    const familyMapNode = document.querySelector(
      "[data-review-family-map-summary]",
    );
    const uploadsNode = document.querySelector("[data-review-uploads-summary]");
    const consentNode = document.querySelector("[data-review-consent-summary]");

    renderSummaryCard(
      householdNode,
      household.household_name || "Household Setup",
      "1",
      [
        `Primary Contact: ${household.primary_contact_name || "—"}`,
        `Email: ${household.primary_contact_email || "—"}`,
        `Role: ${household.household_role || "—"}`,
      ],
    );

    renderSummaryCard(
      familyMapNode,
      familyMap.family_branch_name || "Family Map",
      "2",
      [
        `People in Scope: ${familyMap.people_in_scope || "—"}`,
        `Parent One: ${familyMap.parent_one || "—"}`,
        `Parent Two: ${familyMap.parent_two || "—"}`,
        `Children: ${familyMap.children_names || "—"}`,
      ],
    );

    renderSummaryCard(uploadsNode, "Uploads", "3", [
      `Approx. Uploads: ${uploads.approx_upload_count || "—"}`,
      `Primary Asset Type: ${uploads.primary_asset_type || "—"}`,
      `Key Portraits: ${uploads.key_portraits || "—"}`,
      `Rights Confirmed: ${uploads.uploads_rights_confirmed ? "Yes" : "No"}`,
      `Data Minimization Confirmed: ${uploads.uploads_minimization_confirmed ? "Yes" : "No"}`,
    ]);

    renderSummaryCard(consentNode, "Consent", "4", [
      `Process Consent: ${consent.consent_process ? "Yes" : "No"}`,
      `Store Consent: ${consent.consent_store ? "Yes" : "No"}`,
      `Authority Confirmed: ${consent.consent_authority ? "Yes" : "No"}`,
      `Review Disclaimer Acknowledged: ${consent.consent_review_disclaimer ? "Yes" : "No"}`,
      `Visibility: ${consent.visibility_preference || "—"}`,
    ]);
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

  function setupLockedReviewState(latestSubmission) {
    const normalized = normalizeStatus(latestSubmission.status);

    const formShell = document.querySelector("[data-intake-review-form-shell]");
    const lockedPanel = document.querySelector(
      "[data-intake-review-locked-panel]",
    );
    const lockedTitle = document.querySelector(
      "[data-intake-review-locked-title]",
    );
    const lockedCopy = document.querySelector(
      "[data-intake-review-locked-copy]",
    );
    const primaryAction = document.querySelector(
      "[data-intake-review-primary-action]",
    );
    const secondaryAction = document.querySelector(
      "[data-intake-review-secondary-action]",
    );
    const inlineStatus = document.querySelector(
      "[data-intake-review-form-status-inline]",
    );

    if (formShell) formShell.style.display = "none";
    if (lockedPanel) lockedPanel.style.display = "block";

    if (lockedTitle) {
      lockedTitle.textContent = humanizeStatus(normalized);
    }

    if (lockedCopy) {
      lockedCopy.textContent = `${statusMessage(normalized)} ${reviewNextStep(normalized)}`;
    }

    if (inlineStatus) {
      clearStatus(inlineStatus);
    }

    if (primaryAction) {
      if (normalized === "build_ready") {
        primaryAction.textContent = "Go to Dashboard";
        primaryAction.setAttribute("href", "dashboard.html");
      } else {
        primaryAction.textContent = "Return to Dashboard";
        primaryAction.setAttribute("href", "dashboard.html");
      }
    }

    if (secondaryAction) {
      if (
        normalized === "build_ready" ||
        normalized === "in_production" ||
        normalized === "qa_review" ||
        normalized === "client_review" ||
        normalized === "delivered"
      ) {
        secondaryAction.style.display = "inline-flex";
        secondaryAction.textContent = "Open Family Tree";
        secondaryAction.setAttribute("href", "tree-view.html");
      } else {
        secondaryAction.style.display = "none";
      }
    }
  }

  function setupEditableReviewState() {
    const formShell = document.querySelector("[data-intake-review-form-shell]");
    const lockedPanel = document.querySelector(
      "[data-intake-review-locked-panel]",
    );

    if (formShell) formShell.style.display = "block";
    if (lockedPanel) lockedPanel.style.display = "none";
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
            <div>
              <div class="card-number">A</div>
              <h3>Household Setup</h3>
              <p class="card-copy">Confirm household ownership and household details.</p>
            </div>
            <div>
              <div class="card-number">B</div>
              <h3>Family Map</h3>
              <p class="card-copy">Outline parents, spouse, children, and branch structure.</p>
            </div>
            <div>
              <div class="card-number">C</div>
              <h3>Uploads</h3>
              <p class="card-copy">Plan photos, records, and supporting files for this build.</p>
            </div>
            <div>
              <div class="card-number">D</div>
              <h3>Consent</h3>
              <p class="card-copy">Confirm privacy, processing, storage, and authority permissions.</p>
            </div>
            <div>
              <div class="card-number">E</div>
              <h3>Review &amp; Submit</h3>
              <p class="card-copy">Review the saved onboarding data before final submission.</p>
            </div>
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

      if (!validateRequiredForm(form, statusNode)) {
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

      if (!validateRequiredForm(form, statusNode)) {
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

      if (!validateRequiredForm(form, statusNode)) {
        return;
      }

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

      if (!validateRequiredForm(form, statusNode)) {
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

  function setupReviewForm() {
    const page = document.querySelector("[data-intake-review]");
    if (!page) return;

    const form = document.querySelector("[data-intake-review-form]");
    const lockedStatusNode = document.querySelector(
      "[data-intake-review-form-status]",
    );
    const inlineStatusNode = document.querySelector(
      "[data-intake-review-form-status-inline]",
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

    const draft = loadDraft();
    renderReviewSummaryBlocks();

    if (notesField && draft.review && draft.review.final_intake_notes) {
      notesField.value = draft.review.final_intake_notes;
    }

    if (confirmField && draft.review) {
      confirmField.checked = Boolean(draft.review.confirm_accuracy);
    }

    getLatestSubmission()
      .then(function (latestSubmission) {
        if (latestSubmission) {
          renderReviewSummaryBlocks(latestSubmission);

          const normalized = normalizeStatus(latestSubmission.status);

          if (reviewHeadline) {
            reviewHeadline.textContent =
              statusMessage(normalized) || reviewHeadline.textContent;
          }

          if (isLockedStatus(normalized)) {
            setupLockedReviewState(latestSubmission);
            if (lockedStatusNode) {
              setStatus(
                lockedStatusNode,
                `${statusMessage(normalized)} ${reviewNextStep(normalized)}`,
                "info",
              );
            }
            return;
          }
        }

        setupEditableReviewState();
      })
      .catch(function () {
        setupEditableReviewState();
      });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearStatus(inlineStatusNode);
      clearStatus(lockedStatusNode);

      if (!validateRequiredForm(form, inlineStatusNode)) {
        return;
      }

      const latestSubmission = await getLatestSubmission().catch(function () {
        return getCachedLatestSubmission();
      });

      if (latestSubmission && isLockedStatus(latestSubmission.status)) {
        setupLockedReviewState(latestSubmission);
        setStatus(
          lockedStatusNode,
          `${statusMessage(latestSubmission.status)} ${reviewNextStep(latestSubmission.status)}`,
          "info",
        );
        return;
      }

      const draft = loadDraft();

      if (
        !draft.household ||
        !draft.family_map ||
        !draft.uploads ||
        !draft.consent
      ) {
        setStatus(
          inlineStatusNode,
          "Household Setup, Family Map, Uploads, and Consent must all be saved before submission.",
          "error",
        );
        return;
      }

      if (
        !draft.uploads.uploads_rights_confirmed ||
        !draft.uploads.uploads_minimization_confirmed
      ) {
        setStatus(
          inlineStatusNode,
          "Upload planning confirmations must be completed before submission.",
          "error",
        );
        return;
      }

      if (
        !draft.consent.consent_process ||
        !draft.consent.consent_store ||
        !draft.consent.consent_authority ||
        !draft.consent.consent_review_disclaimer ||
        !draft.consent.visibility_preference
      ) {
        setStatus(
          inlineStatusNode,
          "Consent confirmations must be completed before submission.",
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
        policy_version: POLICY_VERSION,
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

        setStatus(
          inlineStatusNode,
          "Intake submitted successfully.",
          "success",
        );

        setTimeout(function () {
          window.location.href = "dashboard.html";
        }, 1200);
      } catch (error) {
        setStatus(
          inlineStatusNode,
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
