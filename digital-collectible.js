(function () {
  "use strict";

  const app = window.TOLApp || {};
  const authPages = window.TOLAuthPages || {};
  const MIN_RENDERABLE_POSTER_DIMENSION_PX = 2;
  let posterPreviewLoadSeq = 0;

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

  function setTagline(value) {
    const node = document.querySelector("[data-delivery-tagline]");
    if (node) node.textContent = value || "";
  }

  function setHeroSummaryTagline() {
    setTagline(
      "Your NFT-authenticated delivery status, files, and verification record are shown below.",
    );
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
  const MINT_PENDING_STATUSES = new Set([
    "pending",
    "queued",
    "approved",
    "minting",
    "pending_approval",
    "draft",
  ]);
  const PAID_ORDER_STATUSES = new Set([
    "paid",
    "active",
    "fulfilled",
    "confirmed",
    "complete",
    "completed",
    "succeeded",
  ]);

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

  function getWorkspaceHints() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return {
        projectId: String(params.get("project_id") || "").trim(),
        familyId: String(params.get("family_id") || "").trim(),
      };
    } catch (_e) {
      return { projectId: "", familyId: "" };
    }
  }

  function getProjectIdFromRecord(record) {
    if (!record || typeof record !== "object") return "";
    return String(
      record.project_id || record.projectId || record.id || record._id || "",
    ).trim();
  }

  function resolveProjectId(context, hints) {
    if (hints && hints.projectId) return hints.projectId;
    if (!context) return "";
    const p = context.activeProject || {};
    const fallbackRecords = [
      context.currentWorkspace,
      context.activeEntitlement,
      context.paidOrder,
      context.latestSubmission,
    ];
    for (const record of fallbackRecords) {
      const candidate =
        String((record && record.projectId) || "").trim() ||
        getProjectIdFromRecord(record);
      if (candidate) return candidate;
    }
    return String(
      p.project_id || p.projectId || p.id || p._id || context.projectId || "",
    ).trim();
  }

  function buildDeliveryFallback(context, mintStatus, mintEligibility, projectId) {
    const latest = (mintStatus && mintStatus.latest) || {};
    const mintStatusValue = String(
      (mintStatus && (mintStatus.current_status || mintStatus.canonical_status)) ||
        latest.mint_status ||
        "",
    ).trim();
    const mintEnabled = Boolean(
      (mintStatus && mintStatus.mint_enabled) ||
        (mintEligibility &&
          mintEligibility.mint_policy &&
          mintEligibility.mint_policy.product_includes_onchain_anchor),
    );
    const isMinted = normalizeValue(mintStatusValue) === "minted";
    const isMintPending =
      mintEnabled &&
      MINT_PENDING_STATUSES.has(normalizeValue(mintStatusValue));

    const entitlement = context && context.activeEntitlement ? context.activeEntitlement : {};
    const paidOrder = context && context.paidOrder ? context.paidOrder : {};

    const packageName =
      entitlement.package_name ||
      (context && context.packageName) ||
      paidOrder.package_name ||
      "";
    const packageCode =
      entitlement.package_code ||
      (context && context.packageCode) ||
      paidOrder.package_code ||
      "";
    const packageLane =
      entitlement.package_lane ||
      (context && context.packageLane) ||
      (context && context.activeProject && context.activeProject.project_lane) ||
      "";

    return {
      project_id: projectId,
      package_name: packageName,
      package_code: packageCode,
      package_lane: packageLane,
      entitlement_status: entitlement.status || "",
      delivered_at: entitlement.delivered_at || "",
      order_id: paidOrder.id || paidOrder._id || "",
      order_status: paidOrder.status || "",
      order_created_at: paidOrder.created_at || "",
      mint_enabled: mintEnabled,
      mint_status: mintStatusValue,
      mint_record_id: latest.mint_record_id || "",
      chain: latest.chain || "",
      contract_address: latest.contract_address || "",
      token_id: latest.token_id || "",
      tx_hash: latest.tx_hash || "",
      public_token_id: latest.public_token_id || "",
      // mint-status historically returns customer_wallet while delivery route
      // returns wallet, so preserve both lookup keys in fallback mode.
      wallet: latest.wallet || latest.customer_wallet || "",
      minted_at: latest.minted_at || "",
      version_number: latest.version_number,
      token_type: latest.token_type || "",
      metadata_uri: latest.metadata_uri || "",
      poster_image_uri_public: latest.poster_image_uri_public || "",
      has_poster: Boolean(latest.poster_image_uri_public),
      has_metadata: Boolean(latest.metadata_uri),
      is_minted: isMinted,
      is_mint_pending: isMintPending,
    };
  }

  async function loadDeliveryFallback(context, projectId) {
    const [mintStatusResult, mintEligibilityResult] = await Promise.allSettled([
      app.apiRequest(`/projects/${encodeURIComponent(projectId)}/mint-status`, {
        method: "GET",
      }),
      app.apiRequest(`/projects/${encodeURIComponent(projectId)}/mint-eligibility`, {
        method: "GET",
      }),
    ]);

    const mintStatus =
      mintStatusResult.status === "fulfilled" ? mintStatusResult.value : null;
    const mintEligibility =
      mintEligibilityResult.status === "fulfilled"
        ? mintEligibilityResult.value
        : null;

    if (!mintStatus && !mintEligibility) {
      const firstError =
        mintStatusResult.status === "rejected"
          ? mintStatusResult.reason
          : mintEligibilityResult.reason;
      throw firstError || new Error("Digital collectible fallback source unavailable.");
    }

    return buildDeliveryFallback(context, mintStatus, mintEligibility, projectId);
  }

  function renderSpecimenRecord(projectId, payload) {
    const specimenUrl = document.querySelector("[data-specimen-url]");
    if (specimenUrl) specimenUrl.textContent = window.location.href;

    const specimenTs = document.querySelector("[data-specimen-timestamp]");
    if (specimenTs) specimenTs.textContent = formatDateTime(new Date().toISOString());

    const specimenAssetId = document.querySelector("[data-specimen-asset-id]");
    if (specimenAssetId) {
      specimenAssetId.textContent =
        (payload && (payload.public_token_id || payload.mint_record_id)) ||
        projectId ||
        "—";
    }

    const specimenOrderId = document.querySelector("[data-specimen-order-id]");
    if (specimenOrderId) specimenOrderId.textContent = (payload && payload.order_id) || "—";
  }

  function renderServiceError(err) {
    const status = Number(err && err.status);
    let message =
      "Digital collectible delivery service is temporarily unavailable. Please try again shortly.";
    let badge = "Service Error";

    if (status === 401 || status === 403) {
      message =
        "Authentication is required to view this digital collectible. Please sign in again.";
      badge = "Auth Required";
    } else if (status === 404) {
      message =
        "No digital collectible delivery record exists for this workspace yet.";
      badge = "Unavailable";
    } else if (status === 422) {
      message =
        "Project context is invalid for this page. Open this page from your dashboard workspace.";
      badge = "Context Error";
    }

    const statusCopy = document.querySelector("[data-delivery-status-copy]");
    if (statusCopy) statusCopy.textContent = message;
    setHeroSummaryTagline();
    applyBadge("[data-delivery-status-badge]", badge, "badge-error");
    hide("[data-delivery-identity-row]");
    hide("[data-delivery-actions]");
    hide("[data-delivery-anchor-panel]");
    hide("[data-delivery-order-panel]");
    renderSpecimenRecord("", null);
  }

  // ── Main page renderer ───────────────────────────────────────────────

  async function loadDeliveryPage(context) {
    const hints = getWorkspaceHints();
    const projectId = resolveProjectId(context, hints);
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
      try {
        delivery = await loadDeliveryFallback(context, projectId);
      } catch (_fallbackError) {
        renderServiceError(err);
        return;
      }
    }

    renderDelivery(delivery, projectId);
  }

  function renderNoAccess(message) {
    const statusCopy = document.querySelector("[data-delivery-status-copy]");
    if (statusCopy) statusCopy.textContent = message;
    setHeroSummaryTagline();
    applyBadge("[data-delivery-status-badge]", "Unavailable", "badge-error");
    hide("[data-delivery-identity-row]");
    hide("[data-delivery-actions]");
    hide("[data-delivery-anchor-panel]");
    hide("[data-delivery-order-panel]");
    renderSpecimenRecord("", null);
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
    const hasAnyFile = hasPoster || hasMetadata;
    const isPaid =
      PAID_ORDER_STATUSES.has(normalizeValue(d.order_status)) ||
      ["active", "fulfilled", "delivered"].includes(
        normalizeValue(d.entitlement_status),
      );

    // ── Primary status ───────────────────────────────────────────────
    let primaryStatusText =
      "Your digital collectible record is active. Delivery files will appear as they become available.";
    let primaryBadgeText = "Active";
    let primaryBadgeClass = "badge-info";

    if (isPaid && isMinted && hasPoster && hasMetadata) {
      primaryStatusText =
        "Your TOMB OF LIGHT digital collectible is minted and delivered. " +
        "Download your NFT-authenticated digital files below.";
      primaryBadgeText = "Delivered & Minted";
      primaryBadgeClass = "badge-success";
    } else if (isPaid && isMinted && hasAnyFile) {
      primaryStatusText =
        "Your Legacy Anchor is minted. Some delivery files are still being finalized.";
      primaryBadgeText = "Partial Delivery";
      primaryBadgeClass = "badge-info";
    } else if (isPaid && isMintPending) {
      primaryStatusText =
        "Your TOMB OF LIGHT digital collectible is active. " +
        "On-chain minting is in progress.";
      primaryBadgeText = "Mint Pending";
      primaryBadgeClass = "badge-info";
    } else if (isPaid && hasAnyFile) {
      primaryStatusText =
        "Your digital collectible delivery files are available below.";
      primaryBadgeText = "Delivered";
      primaryBadgeClass = "badge-success";
    } else if (isPaid && mintEnabled && !isMinted && !isMintPending) {
      primaryStatusText =
        "Your TOMB OF LIGHT digital collectible is active. " +
        "Your package includes on-chain minting.";
      primaryBadgeText = "Active";
      primaryBadgeClass = "badge-info";
    } else if (!isPaid && !hasAnyFile && !isMinted) {
      primaryStatusText =
        "A delivered digital collectible is not yet available for this workspace.";
      primaryBadgeText = "Unavailable";
      primaryBadgeClass = "badge-error";
    }

    applyBadge("[data-delivery-status-badge]", primaryBadgeText, primaryBadgeClass);
    const statusCopy = document.querySelector("[data-delivery-status-copy]");
    if (statusCopy) statusCopy.textContent = primaryStatusText;
    setHeroSummaryTagline();

    // ── Asset identity ───────────────────────────────────────────────
    const assetName = buildAssetName(d);
    const assetSub = buildAssetSub(d);
    setText("[data-delivery-asset-name]", assetName);
    setText("[data-delivery-asset-sub]", assetSub);
    show("[data-delivery-identity-row]");

    // ── Poster preview ───────────────────────────────────────────────
    renderPosterPreview(d);

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
    renderSpecimenRecord(projectId, d);
  }

  function setPosterState(state, options) {
    const posterBlock = document.querySelector("[data-delivery-poster-block]");
    const posterImg = document.querySelector("[data-delivery-poster-preview]");
    const posterEmpty = document.querySelector("[data-delivery-poster-empty]");
    const posterWrapper = document.querySelector("[data-delivery-poster-link-wrapper]");
    if (!posterBlock || !posterImg || !posterEmpty || !posterWrapper) return;

    const fallbackText = options?.fallbackText || "Poster preview unavailable.";
    const href = options?.href || "";

    posterBlock.setAttribute("data-poster-state", state);
    posterEmpty.textContent = fallbackText;

    if (href) {
      posterWrapper.setAttribute("href", href);
      posterWrapper.setAttribute("target", "_blank");
      posterWrapper.setAttribute("rel", "noopener noreferrer");
      posterWrapper.removeAttribute("aria-disabled");
      posterWrapper.tabIndex = 0;
    } else {
      posterWrapper.setAttribute("href", "#");
      posterWrapper.removeAttribute("target");
      posterWrapper.removeAttribute("rel");
      posterWrapper.setAttribute("aria-disabled", "true");
      posterWrapper.tabIndex = -1;
    }

    const isReady = state === "ready";
    posterImg.style.display = isReady ? "" : "none";
    posterEmpty.style.display = isReady ? "none" : "";
  }

  function renderPosterPreview(d) {
    const posterBlock = document.querySelector("[data-delivery-poster-block]");
    const posterImg = document.querySelector("[data-delivery-poster-preview]");
    const posterUrl = (d?.poster_image_uri_public || "").trim();
    if (!posterBlock || !posterImg) return;

    if (!posterUrl) {
      hide("[data-delivery-poster-block]");
      return;
    }

    show("[data-delivery-poster-block]");
    setPosterState("loading", {
      href: posterUrl,
      fallbackText: "Loading poster preview…",
    });

    posterPreviewLoadSeq += 1;
    const previewLoadToken = posterPreviewLoadSeq;
    posterBlock.setAttribute("data-poster-load-token", previewLoadToken);

    function clearPosterImageHandlers() {
      posterImg.onload = null;
      posterImg.onerror = null;
    }

    function isCurrentLoadToken() {
      return Number(posterBlock.getAttribute("data-poster-load-token")) === previewLoadToken;
    }

    posterImg.onload = function () {
      if (!isCurrentLoadToken()) return;
      const hasRenderableImage =
        Number.isFinite(posterImg.naturalWidth) &&
        Number.isFinite(posterImg.naturalHeight) &&
        posterImg.naturalWidth >= MIN_RENDERABLE_POSTER_DIMENSION_PX &&
        posterImg.naturalHeight >= MIN_RENDERABLE_POSTER_DIMENSION_PX;
      if (!hasRenderableImage) {
        setPosterState("unavailable", {
          href: "",
          fallbackText: "Poster preview unavailable.",
        });
        clearPosterImageHandlers();
        return;
      }
      setPosterState("ready", {
        href: posterUrl,
      });
      clearPosterImageHandlers();
    };

    posterImg.onerror = function () {
      if (!isCurrentLoadToken()) return;
      setPosterState("unavailable", {
        href: "",
        fallbackText: "Poster preview unavailable.",
      });
      clearPosterImageHandlers();
    };

    // Clear existing src first so the browser treats the next src assignment as a new load request.
    posterImg.removeAttribute("src");
    posterImg.src = posterUrl;
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
