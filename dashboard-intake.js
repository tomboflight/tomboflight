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

  function normalizeRole(role) {
    return String(role || "")
      .trim()
      .toLowerCase();
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
        <h3>${String(item.status || "unknown").replaceAll("_", " ")}</h3>
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

  function setHero(textValue) {
    const statusNode = document.querySelector("[data-dashboard-status]");
    if (statusNode) {
      statusNode.textContent = textValue;
    }
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
      setHero(
        "You are signed in to the Tomb of Light internal operations portal.",
      );
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

    try {
      const latest = await getLatestSubmission();
      const paidOrder = await getPaidOrder();

      if (paidOrder) {
        text(
          accessStatus,
          `Access unlocked through ${paidOrder.package_name || paidOrder.package_slug || "your active package"}.`,
        );
        setHero(
          `Your package is active: ${paidOrder.package_name || "Active Package"}.`,
        );
      } else {
        text(
          accessStatus,
          "Purchase required before family build tools unlock.",
        );
        setHero(
          "Your customer workspace is connected, but no paid package is active yet.",
        );
      }

      if (
        workspaceCopy &&
        latest &&
        normalizeStatus(latest.status) === "build_ready"
      ) {
        text(
          workspaceCopy,
          "Your intake has been approved and provisioned. This workspace now moves from onboarding into the real family build stage.",
        );
      }

      if (!latest) {
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
      } else {
        const status = normalizeStatus(latest.status);

        text(
          intakeCardStatus,
          `Your most recent intake submission is shown below.`,
        );
        text(
          currentPackage,
          latest.package_name ||
            latest.package_slug ||
            paidOrder?.package_name ||
            "—",
        );
        text(statusBadge, status);
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
              ? "Editing is locked after final submission."
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
