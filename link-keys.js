(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  const authPages = window.TOLAuthPages || {};

  if (!app || typeof app.apiRequest !== "function") {
    console.error("link-keys.js requires app.js/auth.js first.");
    return;
  }

  let currentUser = null;
  let currentContext = null;
  let currentProjectId = "";
  let currentKey = null;
  let currentRequests = [];

  function normalizeValue(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function humanizeStatus(status) {
    const normalized = normalizeValue(status);
    if (!normalized) return "Unknown";

    return normalized
      .split("_")
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function setStatus(node, message, type) {
    if (!node) return;

    node.style.display = "block";
    node.textContent = message;

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
  }

  function getFamilyIdFromContext(context) {
    return String(
      context?.activeProject?.family_id || context?.activeProject?.familyId || "",
    ).trim();
  }

  function getProjectIdFromContext(context) {
    return String(
      context?.activeProject?.project_id ||
        context?.activeProject?.projectId ||
        context?.activeProject?.id ||
        context?.activeProject?._id ||
        context?.currentWorkspace?.projectId ||
        "",
    ).trim();
  }

  function withContextHref(href, context) {
    if (!href) return href;

    const familyId = getFamilyIdFromContext(context);
    const projectId = getProjectIdFromContext(context);

    if (!familyId && !projectId) {
      return href;
    }

    try {
      const url = new URL(href, window.location.href);
      if (familyId) {
        url.searchParams.set("family_id", familyId);
      }
      if (projectId) {
        url.searchParams.set("project_id", projectId);
      }
      return `${url.pathname.split("/").pop() || href}${url.search}`;
    } catch (error) {
      return href;
    }
  }

  function getResolvedEntitlements(context) {
    if (context?.resolvedEntitlements) return context.resolvedEntitlements;
    if (authPages.buildFallbackEntitlements) {
      return authPages.buildFallbackEntitlements(
        context?.packageCode,
        context?.packageLane,
      );
    }
    return {};
  }

  function updateNav(context) {
    const resolved = getResolvedEntitlements(context);

    const navTree = document.querySelector(
      '.site-nav a[href="tree-view.html"]',
    );
    const navCertificate = document.querySelector(
      '.site-nav a[href="lineage-certificate.html"]',
    );
    const navIntake = document.querySelector(
      '.site-nav a[href="intake-review.html"]',
    );
    const navVerification = document.querySelector(
      '.site-nav a[href="verification-upload.html"]',
    );

    if (navTree) {
      navTree.style.display = resolved.can_build_family_tree ? "" : "none";
      navTree.setAttribute("href", withContextHref("tree-view.html", context));
    }

    if (navCertificate) {
      navCertificate.style.display = resolved.can_use_lineage_certificate
        ? ""
        : "none";
      navCertificate.setAttribute(
        "href",
        withContextHref("lineage-certificate.html", context),
      );
    }

    if (navIntake) {
      navIntake.style.display = resolved.can_open_family_intake ? "" : "none";
      navIntake.setAttribute(
        "href",
        withContextHref("intake-review.html", context),
      );
    }

    if (navVerification) {
      navVerification.style.display =
        resolved.can_upload_verification_docs || resolved.can_upload_portraits
          ? ""
          : "none";
      navVerification.setAttribute(
        "href",
        withContextHref("verification-upload.html", context),
      );
    }
  }

  function renderWorkspaceSummary(context) {
    const resolved = getResolvedEntitlements(context);

    const packageNameNode = document.querySelector("[data-link-package-name]");
    const laneNode = document.querySelector("[data-link-package-lane]");
    const projectNode = document.querySelector("[data-link-project-name]");

    if (packageNameNode) {
      packageNameNode.textContent = context?.packageName || "Active Package";
    }

    if (laneNode) {
      laneNode.textContent =
        resolved.package_lane || context?.packageLane || "unknown";
    }

    if (projectNode) {
      projectNode.textContent =
        context?.activeProject?.project_name ||
        context?.activeProject?.name ||
        "Current Workspace";
    }
  }

  function renderCurrentKey() {
    const keyInput = document.querySelector("[data-link-key-value]");
    const generateBtn = document.querySelector("[data-link-key-generate]");
    const revokeBtn = document.querySelector("[data-link-key-revoke]");

    if (keyInput) {
      keyInput.value = currentKey?.key_value || "";
      keyInput.placeholder = currentKey ? "" : "No active key yet";
    }

    if (generateBtn) {
      generateBtn.textContent = currentKey
        ? "Regenerate Link Key"
        : "Generate Link Key";
    }

    if (revokeBtn) {
      revokeBtn.disabled = !currentKey;
      revokeBtn.style.opacity = currentKey ? "" : "0.45";
    }
  }

  function counterpartLabel(item) {
    const isSource = String(item.source_project_id) === currentProjectId;
    if (isSource) {
      return (
        item.target_project_name ||
        item.target_owner_email ||
        item.target_project_id ||
        "Linked Workspace"
      );
    }
    return (
      item.source_project_name ||
      item.source_owner_email ||
      item.source_project_id ||
      "Linked Workspace"
    );
  }

  function requestMeta(item) {
    const label = counterpartLabel(item);
    const lines = [
      `<p class="card-copy"><strong>Workspace:</strong> ${escapeHtml(label)}</p>`,
      `<p class="card-copy"><strong>Status:</strong> ${escapeHtml(humanizeStatus(item.status))}</p>`,
      `<p class="card-copy"><strong>Requested By:</strong> ${escapeHtml(item.requested_by || "—")}</p>`,
      `<p class="card-copy"><strong>Created:</strong> ${escapeHtml(item.created_at || "—")}</p>`,
    ];

    if (item.notes) {
      lines.push(
        `<p class="card-copy"><strong>Notes:</strong> ${escapeHtml(item.notes)}</p>`,
      );
    }

    return lines.join("");
  }

  function renderCardList(node, emptyNode, htmlItems) {
    if (!node) return;

    if (!htmlItems.length) {
      node.innerHTML = "";
      if (emptyNode) emptyNode.style.display = "block";
      return;
    }

    if (emptyNode) emptyNode.style.display = "none";
    node.innerHTML = htmlItems.join("");
  }

  function renderRequests() {
    const incomingNode = document.querySelector("[data-link-incoming-list]");
    const outgoingNode = document.querySelector("[data-link-outgoing-list]");
    const activeNode = document.querySelector("[data-link-active-list]");

    const incomingEmpty = document.querySelector("[data-link-incoming-empty]");
    const outgoingEmpty = document.querySelector("[data-link-outgoing-empty]");
    const activeEmpty = document.querySelector("[data-link-active-empty]");

    const incoming = currentRequests.filter(function (item) {
      return (
        normalizeValue(item.status) === "pending" &&
        String(item.target_project_id) === currentProjectId
      );
    });

    const outgoing = currentRequests.filter(function (item) {
      return (
        normalizeValue(item.status) === "pending" &&
        String(item.source_project_id) === currentProjectId
      );
    });

    const active = currentRequests.filter(function (item) {
      return (
        normalizeValue(item.status) === "approved" &&
        (String(item.source_project_id) === currentProjectId ||
          String(item.target_project_id) === currentProjectId)
      );
    });

    renderCardList(
      incomingNode,
      incomingEmpty,
      incoming.map(function (item, index) {
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>Incoming Request</h3>
            ${requestMeta(item)}
            <div class="inline-actions" style="margin-top: 1rem">
              <button class="btn btn-primary" type="button" data-link-action="approve" data-request-id="${escapeHtml(item.id)}">
                Approve
              </button>
              <button class="btn btn-secondary" type="button" data-link-action="reject" data-request-id="${escapeHtml(item.id)}">
                Reject
              </button>
            </div>
          </div>
        `;
      }),
    );

    renderCardList(
      outgoingNode,
      outgoingEmpty,
      outgoing.map(function (item, index) {
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>Outgoing Request</h3>
            ${requestMeta(item)}
            <div class="inline-actions" style="margin-top: 1rem">
              <button class="btn btn-secondary" type="button" data-link-action="revoke" data-request-id="${escapeHtml(item.id)}">
                Cancel Request
              </button>
            </div>
          </div>
        `;
      }),
    );

    renderCardList(
      activeNode,
      activeEmpty,
      active.map(function (item, index) {
        return `
          <div class="family-record-card">
            <div class="card-number">${index + 1}</div>
            <h3>Active Link</h3>
            ${requestMeta(item)}
            <div class="inline-actions" style="margin-top: 1rem">
              <button class="btn btn-secondary" type="button" data-link-action="revoke" data-request-id="${escapeHtml(item.id)}">
                Remove Link
              </button>
            </div>
          </div>
        `;
      }),
    );
  }

  async function loadCurrentKey() {
    const statusNode = document.querySelector("[data-link-key-status]");
    clearStatus(statusNode);

    try {
      const key = await app.apiRequest(
        `/link-keys/my-active?project_id=${encodeURIComponent(currentProjectId)}`,
        { method: "GET" },
      );
      currentKey = key || null;
    } catch (error) {
      const message = String(error?.message || error).toLowerCase();
      if (message.includes("404") || message.includes("no active link key")) {
        currentKey = null;
      } else {
        currentKey = null;
        setStatus(
          statusNode,
          error.message || "Unable to load link key.",
          "error",
        );
      }
    }

    renderCurrentKey();
  }

  async function loadRequests() {
    const statusNode = document.querySelector("[data-link-request-status]");
    clearStatus(statusNode);

    try {
      const payload = await app.apiRequest(
        `/link-requests/my-list?project_id=${encodeURIComponent(currentProjectId)}`,
        { method: "GET" },
      );
      currentRequests = Array.isArray(payload?.items) ? payload.items : [];
      renderRequests();
    } catch (error) {
      currentRequests = [];
      renderRequests();
      setStatus(
        statusNode,
        error.message || "Unable to load link requests.",
        "error",
      );
    }
  }

  async function generateLinkKey() {
    const statusNode = document.querySelector("[data-link-key-status]");
    setStatus(statusNode, "Generating link key...", "info");

    try {
      currentKey = await app.apiRequest(
        `/link-keys/project/${encodeURIComponent(currentProjectId)}/generate`,
        { method: "POST" },
      );
      renderCurrentKey();
      setStatus(statusNode, "Link key generated successfully.", "success");
    } catch (error) {
      setStatus(
        statusNode,
        error.message || "Unable to generate link key.",
        "error",
      );
    }
  }

  async function revokeCurrentKey() {
    const statusNode = document.querySelector("[data-link-key-status]");
    if (!currentKey?.id) {
      setStatus(statusNode, "There is no active key to revoke.", "error");
      return;
    }

    const confirmed = window.confirm(
      "Revoke this link key? Existing requests are not deleted, but this key can no longer be used for new link requests.",
    );
    if (!confirmed) return;

    setStatus(statusNode, "Revoking link key...", "info");

    try {
      await app.apiRequest(
        `/link-keys/${encodeURIComponent(currentKey.id)}/revoke`,
        {
          method: "POST",
        },
      );
      currentKey = null;
      renderCurrentKey();
      setStatus(statusNode, "Link key revoked successfully.", "success");
    } catch (error) {
      setStatus(
        statusNode,
        error.message || "Unable to revoke link key.",
        "error",
      );
    }
  }

  async function copyCurrentKey() {
    const statusNode = document.querySelector("[data-link-key-status]");
    if (!currentKey?.key_value) {
      setStatus(statusNode, "Generate a link key first.", "error");
      return;
    }

    try {
      await navigator.clipboard.writeText(currentKey.key_value);
      setStatus(statusNode, "Link key copied to clipboard.", "success");
    } catch (error) {
      setStatus(
        statusNode,
        "Unable to copy link key in this browser.",
        "error",
      );
    }
  }

  async function submitLinkRequest(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const statusNode = document.querySelector("[data-link-request-status]");
    clearStatus(statusNode);

    if (!currentKey?.key_value) {
      setStatus(
        statusNode,
        "Generate your link key before sending a request.",
        "error",
      );
      return;
    }

    const targetKey = String(form.target_key.value || "").trim();
    const notes = String(form.notes.value || "").trim();

    if (!targetKey) {
      setStatus(statusNode, "Target link key is required.", "error");
      return;
    }

    setStatus(statusNode, "Sending link request...", "info");

    try {
      await app.apiRequest("/link-requests", {
        method: "POST",
        body: JSON.stringify({
          source_project_id: currentProjectId,
          target_key: targetKey,
          notes: notes || null,
        }),
      });

      form.reset();
      await loadRequests();
      setStatus(statusNode, "Link request sent successfully.", "success");
    } catch (error) {
      setStatus(
        statusNode,
        error.message || "Unable to send link request.",
        "error",
      );
    }
  }

  async function runRequestAction(requestId, action) {
    const statusNode = document.querySelector("[data-link-request-status]");
    let notes = "";

    if (action === "reject") {
      notes = window.prompt("Optional rejection note:", "") || "";
    } else if (action === "revoke") {
      notes = window.prompt("Optional revoke note:", "") || "";
    } else if (action === "approve") {
      notes = window.prompt("Optional approval note:", "") || "";
    }

    setStatus(statusNode, "Updating link request...", "info");

    try {
      await app.apiRequest(
        `/link-requests/${encodeURIComponent(requestId)}/${action}`,
        {
          method: "POST",
          body: JSON.stringify({ notes: notes || null }),
        },
      );

      await loadRequests();
      setStatus(statusNode, `Request ${action}d successfully.`, "success");
    } catch (error) {
      setStatus(
        statusNode,
        error.message || "Unable to update link request.",
        "error",
      );
    }
  }

  function bindActions() {
    const generateBtn = document.querySelector("[data-link-key-generate]");
    const copyBtn = document.querySelector("[data-link-key-copy]");
    const revokeBtn = document.querySelector("[data-link-key-revoke]");
    const requestForm = document.querySelector("[data-link-request-form]");

    if (generateBtn) {
      generateBtn.addEventListener("click", generateLinkKey);
    }

    if (copyBtn) {
      copyBtn.addEventListener("click", copyCurrentKey);
    }

    if (revokeBtn) {
      revokeBtn.addEventListener("click", revokeCurrentKey);
    }

    if (requestForm) {
      requestForm.addEventListener("submit", submitLinkRequest);
    }

    document.addEventListener("click", function (event) {
      const actionButton = event.target.closest("[data-link-action]");
      if (!actionButton) return;

      const action = actionButton.getAttribute("data-link-action");
      const requestId = actionButton.getAttribute("data-request-id");
      if (!action || !requestId) return;

      runRequestAction(requestId, action);
    });

    document.querySelectorAll("[data-logout-btn]").forEach(function (button) {
      button.addEventListener("click", async function () {
        try {
          if (app.logoutUser) {
            await app.logoutUser();
          } else {
            app.clearSession();
          }
        } catch (error) {
          app.clearSession();
        }

        window.location.href = "signin.html";
      });
    });
  }

  async function setupLinkKeysPage() {
    const page = document.querySelector("[data-link-keys-page]");
    if (!page) return;

    const pageStatusNode = document.querySelector(
      "[data-link-keys-page-status]",
    );
    const workspaceStatusNode = document.querySelector(
      "[data-link-keys-workspace-status]",
    );
    const mainPanel = document.querySelector("[data-link-keys-main-panel]");
    const requestPanel = document.querySelector("[data-link-request-panel]");
    const incomingPanel = document.querySelector("[data-link-incoming-panel]");
    const outgoingPanel = document.querySelector("[data-link-outgoing-panel]");
    const activePanel = document.querySelector("[data-link-active-panel]");

    try {
      const token = app.getToken ? app.getToken() : null;
      if (!token) {
        window.location.href = "signin.html";
        return;
      }

      currentUser = await app.apiRequest("/auth/me", { method: "GET" });

      const orders = authPages.fetchOrders ? await authPages.fetchOrders() : [];
      currentContext =
        typeof authPages.getDashboardContextForCurrentPage === "function"
          ? await authPages.getDashboardContextForCurrentPage(
              currentUser,
              orders,
            )
          : authPages.getDashboardContext
            ? await authPages.getDashboardContext(currentUser, orders)
            : null;

      if (!currentContext || !currentContext.hasPackageAccess) {
        throw new Error("No active package is attached to this account yet.");
      }

      currentProjectId = getProjectIdFromContext(currentContext);
      if (!currentProjectId) {
        throw new Error("No active project is attached to this account yet.");
      }

      const resolved = getResolvedEntitlements(currentContext);
      if (!resolved.can_use_link_keys) {
        throw new Error(
          "Link capabilities are not included in your active package.",
        );
      }

      renderWorkspaceSummary(currentContext);
      updateNav(currentContext);

      if (pageStatusNode) {
        pageStatusNode.textContent = `Link capabilities are active for ${currentContext.packageName || "your package"}.`;
      }

      if (workspaceStatusNode) {
        setStatus(
          workspaceStatusNode,
          "This workspace can generate a project link key, send link requests, and manage active links.",
          "success",
        );
      }

      [
        mainPanel,
        requestPanel,
        incomingPanel,
        outgoingPanel,
        activePanel,
      ].forEach(function (node) {
        if (node) node.style.display = "";
      });

      await loadCurrentKey();
      await loadRequests();
      bindActions();
    } catch (error) {
      if (pageStatusNode) {
        pageStatusNode.textContent =
          error.message || "Link workspace could not be loaded.";
      }

      if (workspaceStatusNode) {
        setStatus(
          workspaceStatusNode,
          error.message || "Link workspace could not be loaded.",
          "error",
        );
      }

      [
        mainPanel,
        requestPanel,
        incomingPanel,
        outgoingPanel,
        activePanel,
      ].forEach(function (node) {
        if (node) node.style.display = "none";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupLinkKeysPage();
  });
})();
