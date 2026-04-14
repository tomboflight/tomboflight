(function () {
  "use strict";

  const app = window.TOLApp || {};
  const authPages = window.TOLAuthPages || {};

  function isInternalRole(user) {
    if (window.TOLApp && typeof window.TOLApp.isInternalRole === "function") {
      return window.TOLApp.isInternalRole(user);
    }
    const INTERNAL_KEYS = [
      "admin",
      "internal",
      "superadmin",
      "staff",
      "support",
      "operations",
      "operator",
    ];
    const role = String(
      (user && (user.role || user.department_role || user.access_tier)) || "",
    ).toLowerCase();
    return INTERNAL_KEYS.some(function (k) {
      return role.includes(k);
    });
  }

  // ── Utility helpers ──────────────────────────────────────────────────

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalizeValue(value) {
    return String(value || "").trim().toLowerCase();
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value || "—";
  }

  function setLink(selector, href, show) {
    const node = document.querySelector(selector);
    if (!node) return;
    if (href) node.setAttribute("href", href);
    node.style.display = show ? "" : "none";
  }

  function show(selector) {
    const node = document.querySelector(selector);
    if (node) node.style.display = "";
  }

  function hide(selector) {
    const node = document.querySelector(selector);
    if (node) node.style.display = "none";
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      const d = new Date(value);
      if (isNaN(d.getTime())) return String(value);
      return d.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    } catch (_e) {
      return String(value);
    }
  }

  function formatDateTime(value) {
    if (!value) return "—";
    try {
      const d = new Date(value);
      if (isNaN(d.getTime())) return String(value);
      return d.toLocaleString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      });
    } catch (_e) {
      return String(value);
    }
  }

  function humanize(value) {
    return String(value || "—")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, function (c) {
        return c.toUpperCase();
      });
  }

  function chainLabel(chain) {
    const n = normalizeValue(chain);
    if (n === "base-mainnet" || n === "base") return "Base Mainnet";
    if (n === "base-sepolia") return "Base Sepolia";
    return chain || "Base Mainnet";
  }

  function baseExplorerUrl(chain) {
    return normalizeValue(chain) === "base-sepolia"
      ? "https://sepolia.basescan.org"
      : "https://basescan.org";
  }

  function buildExplorerLink(data) {
    if (!data) return "";
    const base = baseExplorerUrl(data.chain);
    if (data.tx_hash) return `${base}/tx/${data.tx_hash}`;
    if (data.contract_address && data.token_id) {
      return `${base}/token/${data.contract_address}?a=${encodeURIComponent(data.token_id)}`;
    }
    if (data.contract_address) return `${base}/address/${data.contract_address}`;
    return "";
  }

  function truncateHash(value) {
    const v = String(value || "").trim();
    if (!v || v === "—") return v;
    if (v.startsWith("0x") && v.length > 20) {
      return v.slice(0, 10) + "…" + v.slice(-8);
    }
    return v;
  }

  function setCopyButton(selector, value, label) {
    const node = document.querySelector(selector);
    if (!node) return;
    const normalized = String(value || "").trim();
    node.disabled = !normalized || normalized === "—";
    node.dataset.copyValue = normalized;
    node.dataset.copyLabel = label || selector;
  }

  function setupCopyButtons() {
    document.addEventListener("click", function (evt) {
      const btn = evt.target.closest("[data-copy-value]");
      if (!btn) return;
      const val = btn.dataset.copyValue;
      if (!val) return;
      navigator.clipboard.writeText(val).then(
        function () {
          const original = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(function () {
            btn.textContent = original;
          }, 1500);
        },
        function () {
          // Ignore clipboard errors silently.
        },
      );
    });
  }

  // ── Status badge helpers ─────────────────────────────────────────────

  const STATUS_LABEL_MAP = {
    minted: "Minted",
    minting: "Minting",
    queued: "Queued",
    approved: "Approved",
    pending: "Pending",
    pending_approval: "Pending Approval",
    draft: "Draft",
    failed: "Failed",
    not_started: "Not Started",
    eligible: "Eligible",
    not_eligible: "Not Eligible",
    active: "Active",
    paid: "Paid",
    fulfilled: "Fulfilled",
    confirmed: "Confirmed",
  };

  function humanizeStatus(value) {
    const n = normalizeValue(value);
    return STATUS_LABEL_MAP[n] || humanize(value) || "—";
  }

  function mintStatusClass(status) {
    const n = normalizeValue(status);
    if (n === "minted") return "badge-success";
    if (n === "minting" || n === "queued") return "badge-info";
    if (n === "failed") return "badge-error";
    if (n === "approved" || n === "pending" || n === "pending_approval") return "badge-warning";
    return "";
  }

  function applyBadge(selector, text, extraClass) {
    const node = document.querySelector(selector);
    if (!node) return;
    node.textContent = text || "—";
    node.className = node.className.replace(/badge-\S+/g, "").trim();
    if (extraClass) node.classList.add(extraClass);
  }

  // ── Project ID resolution ───────────────────────────────────────────

  function resolveProjectId(context) {
    if (!context) return "";
    const p = context.activeProject || {};
    return String(
      p.id || p._id || context.projectId || "",
    ).trim();
  }

  // ── Main page renderer ───────────────────────────────────────────────

  async function loadDeliveryPage(context) {
    const projectId = resolveProjectId(context);
    if (!projectId) {
      renderNoAccess("No active project found for this account.");
      return;
    }

    let delivery = null;
    try {
      delivery = await app.apiRequest(
        `/projects/${encodeURIComponent(projectId)}/digital-collectible`,
        { method: "GET" },
      );
    } catch (err) {
      renderNoAccess(
        "Could not load your digital collectible details. Please try again or contact support.",
      );
      return;
    }

    renderDelivery(delivery, projectId);
  }

  function renderNoAccess(message) {
    const statusCopy = document.querySelector("[data-delivery-status-copy]");
    if (statusCopy) statusCopy.textContent = message;
    applyBadge("[data-delivery-status-badge]", "Unavailable", "badge-error");
    hide("[data-delivery-identity-row]");
    hide("[data-delivery-actions]");
    hide("[data-delivery-anchor-panel]");
    hide("[data-delivery-order-panel]");
  }

  function renderDelivery(d, projectId) {
    if (!d) {
      renderNoAccess("Delivery data is not available.");
      return;
    }

    const isMinted = Boolean(d.is_minted);
    const hasPoster = Boolean(d.has_poster);
    const hasMetadata = Boolean(d.has_metadata);
    const mintEnabled = Boolean(d.mint_enabled);
    const isMintPending = Boolean(d.is_mint_pending);
    const mintStatus = String(d.mint_status || "").trim();
    const packageLane = String(d.package_lane || "").trim().toLowerCase();

    // ── Primary status ───────────────────────────────────────────────
    let primaryStatusText = "Your TOMB OF LIGHT digital collectible has been delivered.";
    let primaryBadgeText = "Delivered";
    let primaryBadgeClass = "badge-success";

    if (isMinted) {
      primaryStatusText =
        "Your TOMB OF LIGHT digital collectible is minted and delivered. " +
        "Download your NFT-authenticated digital files below.";
      primaryBadgeText = "Delivered & Minted";
      primaryBadgeClass = "badge-success";
    } else if (isMintPending) {
      primaryStatusText =
        "Your TOMB OF LIGHT digital collectible is active. " +
        "On-chain minting is in progress. Downloads are available below.";
      primaryBadgeText = "Mint Pending";
      primaryBadgeClass = "badge-info";
    } else if (mintEnabled && !isMinted && !isMintPending) {
      primaryStatusText =
        "Your TOMB OF LIGHT digital collectible is active. " +
        "Your package includes on-chain minting. Access your available files below.";
      primaryBadgeText = "Active";
      primaryBadgeClass = "badge-success";
    }

    applyBadge("[data-delivery-status-badge]", primaryBadgeText, primaryBadgeClass);
    const statusCopy = document.querySelector("[data-delivery-status-copy]");
    if (statusCopy) statusCopy.textContent = primaryStatusText;

    // ── Asset identity ───────────────────────────────────────────────
    const assetName = buildAssetName(d);
    const assetSub = buildAssetSub(d);
    setText("[data-delivery-asset-name]", assetName);
    setText("[data-delivery-asset-sub]", assetSub);
    show("[data-delivery-identity-row]");

    // ── Poster preview ───────────────────────────────────────────────
    if (hasPoster) {
      show("[data-delivery-poster-block]");
      const posterImg = document.querySelector("[data-delivery-poster-preview]");
      if (posterImg) {
        posterImg.src = d.poster_image_uri_public;
        posterImg.style.display = "";
      }
      hide("[data-delivery-poster-empty]");
      const posterWrapper = document.querySelector("[data-delivery-poster-link-wrapper]");
      if (posterWrapper) posterWrapper.href = d.poster_image_uri_public;
    }

    // ── Action buttons ───────────────────────────────────────────────
    const posterBtnHref = projectId
      ? `/projects/${encodeURIComponent(projectId)}/delivery/poster`
      : "";
    const metadataBtnHref = projectId
      ? `/projects/${encodeURIComponent(projectId)}/delivery/metadata`
      : "";

    if (hasPoster) {
      setLink("[data-delivery-btn-poster]", posterBtnHref, true);
    } else {
      hide("[data-delivery-btn-poster]");
    }

    if (hasMetadata) {
      setLink("[data-delivery-btn-metadata]", metadataBtnHref, true);
    } else {
      hide("[data-delivery-btn-metadata]");
    }

    const explorerUrl = buildExplorerLink(d);
    if (explorerUrl) {
      setLink("[data-delivery-btn-explorer]", explorerUrl, true);
    } else {
      hide("[data-delivery-btn-explorer]");
    }

    if (!hasPoster && !hasMetadata && !explorerUrl) {
      show("[data-delivery-unavailable-note]");
    } else {
      hide("[data-delivery-unavailable-note]");
    }
    show("[data-delivery-actions]");

    // ── Order & Package ──────────────────────────────────────────────
    setText(
      "[data-delivery-package-name]",
      d.package_name || humanize(d.package_code) || "—",
    );
    setText(
      "[data-delivery-order-status]",
      humanizeStatus(d.order_status) || "—",
    );
    setText(
      "[data-delivery-entitlement-status]",
      humanizeStatus(d.entitlement_status) || "—",
    );
    setText("[data-delivery-order-id]", d.order_id || "—");
    setText("[data-delivery-order-date]", formatDate(d.order_created_at));
    setText("[data-delivery-delivered-at]", formatDate(d.delivered_at) || "—");
    show("[data-delivery-order-panel]");

    // ── On-chain / Legacy Anchor ─────────────────────────────────────
    if (mintEnabled) {
      show("[data-delivery-anchor-panel]");

      const mintBadgeText = isMinted
        ? "Minted"
        : isMintPending
          ? humanizeStatus(mintStatus)
          : "Eligible";
      const mintBadgeClass = mintStatusClass(isMinted ? "minted" : mintStatus);
      applyBadge("[data-delivery-mint-badge]", mintBadgeText, mintBadgeClass);

      let mintCopy = "";
      if (isMinted) {
        mintCopy =
          "Your Legacy Anchor is minted on Base Mainnet. Use the contract address, " +
          "token ID, transaction hash, and explorer link below to verify the anchor.";
      } else if (isMintPending) {
        mintCopy =
          "Your Legacy Anchor is in the minting pipeline. " +
          "On-chain details will appear here once minting is confirmed.";
      } else {
        mintCopy =
          "Your package is eligible for on-chain minting. " +
          "Anchor details will appear here once the minting process is initiated.";
      }
      setText("[data-delivery-mint-copy]", mintCopy);

      setText("[data-delivery-chain]", chainLabel(d.chain) || "—");
      const contractText = d.contract_address
        ? truncateHash(d.contract_address)
        : "Pending mint";
      setText("[data-delivery-contract]", contractText);
      setText("[data-delivery-token-id]", d.token_id || "Pending mint");
      const txText = d.tx_hash ? truncateHash(d.tx_hash) : "Pending mint";
      setText("[data-delivery-tx-hash]", txText);
      setText("[data-delivery-wallet]", d.wallet ? truncateHash(d.wallet) : "—");
      setText("[data-delivery-public-token-id]", d.public_token_id || "—");
      setText("[data-delivery-minted-at]", formatDate(d.minted_at) || "—");
      setText(
        "[data-delivery-version]",
        d.version_number != null ? String(d.version_number) : "—",
      );

      const anchorExplorerUrl = buildExplorerLink(d);
      setLink(
        "[data-delivery-anchor-explorer-link]",
        anchorExplorerUrl,
        Boolean(anchorExplorerUrl),
      );
      setLink(
        "[data-delivery-anchor-metadata-link]",
        d.metadata_uri,
        Boolean(d.metadata_uri),
      );

      setCopyButton(
        "[data-delivery-copy-contract]",
        d.contract_address,
        "Contract Address",
      );
      setCopyButton("[data-delivery-copy-tx]", d.tx_hash, "Transaction Hash");
      setCopyButton("[data-delivery-copy-token]", d.token_id, "Token ID");
      setCopyButton(
        "[data-delivery-copy-public-token]",
        d.public_token_id,
        "Public Token ID",
      );
    } else {
      hide("[data-delivery-anchor-panel]");
    }

    // ── Specimen metadata bar ────────────────────────────────────────
    const specimenUrl = document.querySelector("[data-specimen-url]");
    if (specimenUrl) specimenUrl.textContent = window.location.href;

    const specimenTs = document.querySelector("[data-specimen-timestamp]");
    if (specimenTs) specimenTs.textContent = formatDateTime(new Date().toISOString());

    const specimenAssetId = document.querySelector("[data-specimen-asset-id]");
    if (specimenAssetId) {
      specimenAssetId.textContent =
        d.public_token_id || d.mint_record_id || projectId || "—";
    }

    const specimenOrderId = document.querySelector("[data-specimen-order-id]");
    if (specimenOrderId) specimenOrderId.textContent = d.order_id || "—";
  }

  // ── Asset label builders ─────────────────────────────────────────────

  function buildAssetName(d) {
    if (d.public_token_id) return d.public_token_id;
    if (d.package_name) {
      return `${d.package_name} — NFT-Authenticated Digital Collectible`;
    }
    if (d.package_code) {
      return `${humanize(d.package_code)} — NFT-Authenticated Digital Collectible`;
    }
    return "TOMB OF LIGHT Digital Collectible";
  }

  function buildAssetSub(d) {
    const lane = String(d.package_lane || "").trim().toLowerCase();
    const parts = [];

    if (d.token_type) {
      parts.push(humanize(d.token_type));
    }

    if (lane === "portrait") {
      parts.push("Downloadable Portrait Poster");
      parts.push("Downloadable Metadata Record");
    } else if (lane === "household") {
      parts.push("Downloadable Legacy Poster");
      parts.push("Downloadable Metadata Record");
    } else if (lane === "network") {
      parts.push("Downloadable Legacy Poster");
      parts.push("Downloadable Metadata Record");
    } else if (lane === "organization") {
      parts.push("Downloadable Legacy Poster");
      parts.push("Downloadable Metadata Record");
    } else {
      parts.push("Downloadable Digital Collectible");
      parts.push("Downloadable Metadata Record");
    }

    return parts.join(" · ");
  }

  // ── Page initialiser ─────────────────────────────────────────────────

  async function initDeliveryPage() {
    const page = document.querySelector("[data-digital-collectible-page]");
    if (!page) return;

    setupCopyButtons();

    // Respect the auth gate: auth.js will show [data-auth-required] after
    // verifying the session via setupDashboard (triggered by [data-dashboard]).
    // We wait for the resolved user event before loading delivery data.
    const run = async function () {
      const me = window.TOLResolvedUser;
      if (!me) return;
      if (isInternalRole(me)) return;

      let orders = [];
      try {
        if (authPages.fetchOrders) orders = await authPages.fetchOrders();
      } catch (_e) {
        // non-fatal
      }

      let context = window.TOLDashboardContext;
      if (!context && authPages.getDashboardContextForCurrentPage) {
        try {
          context = await authPages.getDashboardContextForCurrentPage(me, orders);
        } catch (_e) {
          context = null;
        }
      }
      if (!context && authPages.getDashboardContext) {
        try {
          context = await authPages.getDashboardContext(me, orders);
        } catch (_e) {
          context = null;
        }
      }

      if (!context || !context.hasPackageAccess) {
        renderNoAccess(
          "Package access is required to view your digital collectible. " +
            "Please complete your purchase to continue.",
        );
        return;
      }

      await loadDeliveryPage(context);
    };

    // Auth.js may have already resolved the user before this script ran.
    if (window.TOLResolvedUser) {
      run();
    } else {
      window.addEventListener("tol:user-resolved", function () {
        run();
      });
    }

    // Also react to dashboard context becoming ready (covers reload scenarios).
    window.addEventListener("tol:dashboard-context-ready", function (evt) {
      if (evt.detail && window.TOLResolvedUser) {
        run();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initDeliveryPage();
  });
})();
