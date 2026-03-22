(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;

  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

  function normalizeStatus(status) {
    return String(status || "")
      .trim()
      .toLowerCase();
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

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleString();
    } catch (error) {
      return String(value);
    }
  }

  function text(node, value) {
    if (!node) return;
    node.textContent = value;
  }

  function renderHistoryItem(item, index) {
    return `
      <div class="family-record-card">
        <div class="card-number">${index + 1}</div>
        <h3>${humanizeStatus(item.status || "unknown")}</h3>
        <p class="card-copy"><strong>Package:</strong> ${item.package_name || item.package_slug || "—"}</p>
        <p class="card-copy"><strong>Created:</strong> ${formatDate(item.created_at)}</p>
        <p class="card-copy"><strong>Submission ID:</strong> ${item.id || "—"}</p>
        <p class="card-copy"><strong>Family Root ID:</strong> ${item.family_root_id || "—"}</p>
        <p class="card-copy"><strong>Project ID:</strong> ${item.project_id || "—"}</p>
      </div>
    `;
  }

  async function getLatestSubmission() {
    try {
      return await app.apiRequest("/intake-submissions/my-latest", {
        method: "GET",
      });
    } catch (error) {
      const message = String(
        error && error.message ? error.message : error,
      ).toLowerCase();
      if (message.includes("no intake submissions found")) {
        return null;
      }
      throw error;
    }
  }

  async function getSubmissionHistory() {
    try {
      return await app.apiRequest("/intake-submissions/my-list?limit=10", {
        method: "GET",
      });
    } catch (error) {
      return [];
    }
  }

  function nextStepForStatus(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "submitted") return "Waiting for review to begin.";
    if (normalized === "in_review")
      return "Reviewer is evaluating your intake.";
    if (normalized === "approved")
      return "Approved. Waiting for internal build provisioning.";
    if (normalized === "build_ready")
      return "Your approved intake has been provisioned for production.";
    if (normalized === "in_production")
      return "Your legacy build is currently in production.";
    if (normalized === "qa_review")
      return "Your project is in internal quality review.";
    if (normalized === "client_review")
      return "Your project is prepared for client review.";
    if (normalized === "delivered") return "Your project has been delivered.";
    if (normalized === "archived") return "Your project has been archived.";
    if (normalized === "rejected")
      return "Review the feedback, update your intake, and resubmit.";
    return "Complete your intake and submit it for review.";
  }

  async function setupDashboardIntake() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    const intakeCardStatus = document.querySelector(
      "[data-intake-card-status]",
    );
    const currentPackage = document.querySelector(
      "[data-intake-current-package]",
    );
    const statusBadge = document.querySelector("[data-intake-status-badge]");
    const submissionId = document.querySelector("[data-intake-submission-id]");
    const submittedAt = document.querySelector("[data-intake-submitted-at]");
    const nextStep = document.querySelector("[data-intake-next-step]");
    const lockNote = document.querySelector("[data-intake-lock-note]");
    const openAction = document.querySelector("[data-intake-open-action]");
    const historyStatus = document.querySelector(
      "[data-intake-history-status]",
    );
    const historyList = document.querySelector("[data-intake-history-list]");

    try {
      const latest = await getLatestSubmission();

      if (!latest) {
        text(intakeCardStatus, "No intake submission found yet.");
        text(currentPackage, "No package detected");
        text(statusBadge, "Not submitted");
        text(submissionId, "—");
        text(submittedAt, "—");
        text(nextStep, "Open your intake flow and submit the review step.");
        text(
          lockNote,
          "Editing is open because no final submission exists yet.",
        );

        if (openAction) {
          openAction.textContent = "Open Intake";
          openAction.setAttribute("href", "intake-welcome.html");
        }
      } else {
        const status = normalizeStatus(latest.status);

        text(
          intakeCardStatus,
          `Latest intake status: ${humanizeStatus(status)}.`,
        );
        text(currentPackage, latest.package_name || latest.package_slug || "—");
        text(statusBadge, humanizeStatus(status));
        text(submissionId, latest.id || "—");
        text(submittedAt, formatDate(latest.submitted_at || latest.created_at));
        text(nextStep, nextStepForStatus(status));

        if (status === "rejected") {
          text(
            lockNote,
            "Editing is open because the submission was rejected.",
          );
          if (openAction) {
            openAction.textContent = "Resume Intake";
            openAction.setAttribute("href", "intake-household.html");
          }
        } else {
          text(
            lockNote,
            latest.review_locked
              ? "Editing is currently locked."
              : "Editing is currently open.",
          );
          if (openAction) {
            openAction.textContent = "View Intake";
            openAction.setAttribute("href", "intake-review.html");
          }
        }
      }

      const history = await getSubmissionHistory();

      if (!Array.isArray(history) || history.length === 0) {
        text(historyStatus, "No intake submissions found yet.");
        if (historyList) historyList.innerHTML = "";
      } else {
        text(historyStatus, "Your intake history is listed below.");
        if (historyList) {
          historyList.innerHTML = history.map(renderHistoryItem).join("");
        }
      }
    } catch (error) {
      text(intakeCardStatus, "Intake status is temporarily unavailable.");
      text(statusBadge, "Unavailable");
      text(nextStep, "Please try again shortly.");
      text(lockNote, "Could not determine current submission lock state.");
      text(historyStatus, "Intake history is temporarily unavailable.");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupDashboardIntake();
  });
})();
