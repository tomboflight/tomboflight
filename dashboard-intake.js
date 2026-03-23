(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;

  if (!app || typeof app.apiRequest !== "function") {
    return;
  }

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

  function normalizeStatus(status) {
    return String(status || "")
      .trim()
      .toLowerCase();
  }

  function normalizeRole(role) {
    return String(role || "")
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

  function isLockedStatus(status) {
    return LOCKED_STATUSES.has(normalizeStatus(status));
  }

  function isInternalRole(role) {
    return [
      "admin",
      "super_admin",
      "platform_admin",
      "operations_admin",
      "finance_admin",
      "marketing_admin",
    ].includes(normalizeRole(role));
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

  async function getCurrentUser() {
    return await app.apiRequest("/auth/me", { method: "GET" });
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

  async function getPaidOrder() {
    try {
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
          return ["paid", "complete", "completed", "succeeded"].includes(
            status,
          );
        }) || null
      );
    } catch (error) {
      return null;
    }
  }

  function nextStepForStatus(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "submitted") return "Waiting for review to begin.";
    if (normalized === "in_review")
      return "Reviewer is evaluating your intake.";
    if (normalized === "approved")
      return "Approved and waiting for production provisioning.";
    if (normalized === "build_ready")
      return "Production records are created. Next step is building members and relationships.";
    if (normalized === "in_production")
      return "Your lineage build is currently in production.";
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

  function workspaceCopyForStatus(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "build_ready") {
      return "Your intake has been approved and provisioned. This workspace now moves from onboarding into the real family build stage.";
    }

    if (normalized === "in_production") {
      return "Your approved family build is now in production and moving through the Tomb of Light workflow.";
    }

    if (normalized === "submitted" || normalized === "in_review") {
      return "Your intake is in the review pipeline. This workspace will update as your build moves forward.";
    }

    if (normalized === "approved") {
      return "Your intake is approved and waiting for production provisioning.";
    }

    if (normalized === "rejected") {
      return "Your intake needs revision before it can move into production.";
    }

    return "Your Tomb of Light customer workspace connects package access, onboarding, family structure, and lineage tools in one place.";
  }

  function lockNoteForStatus(status, reviewLocked) {
    const normalized = normalizeStatus(status);

    if (normalized === "rejected") {
      return "Editing is open because the submission was rejected.";
    }

    if (normalized === "build_ready") {
      return "Editing is locked. This intake has already been approved and provisioned.";
    }

    if (
      normalized === "in_production" ||
      normalized === "qa_review" ||
      normalized === "client_review" ||
      normalized === "delivered" ||
      normalized === "archived"
    ) {
      return "Editing is locked because this project is already in the production workflow.";
    }

    if (isLockedStatus(normalized)) {
      return "Editing is locked after final submission.";
    }

    return reviewLocked
      ? "Editing is locked after final submission."
      : "Editing is currently open.";
  }

  function intakeCardCopyForStatus(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "build_ready") {
      return "Your intake has been approved and provisioned for production.";
    }

    if (normalized === "in_production") {
      return "Your family build is currently in production.";
    }

    if (normalized === "submitted") {
      return "Your intake has been submitted and is waiting for review.";
    }

    if (normalized === "in_review") {
      return "Your intake is currently under review.";
    }

    if (normalized === "approved") {
      return "Your intake is approved and awaiting production provisioning.";
    }

    if (normalized === "rejected") {
      return "Your intake was rejected and can be updated and resubmitted.";
    }

    return "Your most recent intake submission is shown below.";
  }

  function updatePrimaryIntakeAction(status, actionNode) {
    if (!actionNode) return;

    const normalized = normalizeStatus(status);

    if (normalized === "rejected") {
      actionNode.textContent = "Resume Intake";
      actionNode.setAttribute("href", "intake-household.html");
      return;
    }

    if (
      normalized === "build_ready" ||
      normalized === "in_production" ||
      normalized === "qa_review" ||
      normalized === "client_review" ||
      normalized === "delivered" ||
      normalized === "archived"
    ) {
      actionNode.textContent = "View Intake Record";
      actionNode.setAttribute("href", "intake-review.html");
      return;
    }

    if (isLockedStatus(normalized)) {
      actionNode.textContent = "View Intake";
      actionNode.setAttribute("href", "intake-review.html");
      return;
    }

    actionNode.textContent = "Open Intake";
    actionNode.setAttribute("href", "intake-welcome.html");
  }

  function updateSecondaryFamilyAction(status, actionNode) {
    if (!actionNode) return;

    const normalized = normalizeStatus(status);

    if (
      normalized === "build_ready" ||
      normalized === "in_production" ||
      normalized === "qa_review" ||
      normalized === "client_review" ||
      normalized === "delivered" ||
      normalized === "archived"
    ) {
      actionNode.textContent = "Open Family Tree";
      actionNode.setAttribute("href", "tree-view.html");
      return;
    }

    actionNode.textContent = "Open Family Tree";
    actionNode.setAttribute("href", "tree-view.html");
  }

  async function setupDashboardIntake() {
    const dashboard = document.querySelector("[data-dashboard]");
    if (!dashboard) return;

    let me = null;

    try {
      me = await getCurrentUser();
    } catch (error) {
      return;
    }

    if (isInternalRole(me && me.role)) {
      const statusNode = document.querySelector("[data-dashboard-status]");
      if (statusNode) {
        statusNode.textContent =
          "You are signed in to the Tomb of Light internal operations portal.";
      }
      return;
    }

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
    const accessStatus = document.querySelector("[data-access-status]");
    const workspaceCopy = document.querySelector(
      "[data-dashboard-workspace-copy]",
    );
    const secondaryFamilyAction = document.querySelector(
      "[data-dashboard-next-family-action]",
    );
    const dashboardStatus = document.querySelector("[data-dashboard-status]");

    try {
      const latest = await getLatestSubmission();
      const paidOrder = await getPaidOrder();

      if (paidOrder) {
        text(
          accessStatus,
          `Access unlocked through ${paidOrder.package_name || paidOrder.package_slug || "your active package"}.`,
        );
        text(
          dashboardStatus,
          `Your package is active: ${paidOrder.package_name || "Active Package"}.`,
        );
      } else {
        text(
          accessStatus,
          "Purchase required before family build tools unlock.",
        );
        text(
          dashboardStatus,
          "Your customer workspace is connected, but no paid package is active yet.",
        );
      }

      if (!latest) {
        text(
          workspaceCopy,
          "Your Tomb of Light customer workspace connects package access, onboarding, family structure, and lineage tools in one place.",
        );
        text(intakeCardStatus, "No intake submission found yet.");
        text(currentPackage, paidOrder?.package_name || "No package detected");
        text(statusBadge, "Not submitted");
        text(submissionId, "—");
        text(submittedAt, "—");
        text(
          nextStep,
          paidOrder
            ? "Open your intake flow and submit the review step."
            : "Purchase a package first to unlock intake.",
        );
        text(
          lockNote,
          paidOrder
            ? "Editing is open because no final submission exists yet."
            : "Intake is locked until a paid package exists.",
        );

        if (openAction) {
          openAction.textContent = paidOrder ? "Open Intake" : "View Packages";
          openAction.setAttribute(
            "href",
            paidOrder ? "intake-welcome.html" : "index.html#pricing",
          );
        }

        updateSecondaryFamilyAction("", secondaryFamilyAction);
      } else {
        const status = normalizeStatus(latest.status);

        text(workspaceCopy, workspaceCopyForStatus(status));
        text(intakeCardStatus, intakeCardCopyForStatus(status));
        text(
          currentPackage,
          latest.package_name ||
            latest.package_slug ||
            paidOrder?.package_name ||
            "—",
        );
        text(statusBadge, humanizeStatus(status));
        text(submissionId, latest.id || "—");
        text(submittedAt, formatDate(latest.submitted_at || latest.created_at));
        text(nextStep, nextStepForStatus(status));
        text(lockNote, lockNoteForStatus(status, latest.review_locked));

        updatePrimaryIntakeAction(status, openAction);
        updateSecondaryFamilyAction(status, secondaryFamilyAction);
      }

      const history = await getSubmissionHistory();

      if (!Array.isArray(history) || history.length === 0) {
        text(historyStatus, "No intake submissions found yet.");
        if (historyList) historyList.innerHTML = "";
      } else {
        text(historyStatus, "Your recent intake submissions are listed below.");
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
