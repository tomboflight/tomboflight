(function () {
  "use strict";

  const authPages = window.TOLAuthPages || {};

  async function setupLineageCertificatePage() {
    if (!window.TOLAuth) return;

    const page = document.querySelector("[data-lineage-certificate-page]");
    if (!page) return;

    const output = document.querySelector("[data-certificate-output]");
    const emptyState = document.querySelector("[data-certificate-empty]");
    const statusNode = document.querySelector("[data-certificate-status]");
    const familySelect = document.querySelector(
      "[data-certificate-family-select]",
    );
    const loadBtn = document.querySelector("[data-load-certificate-btn]");
    const printBtn = document.querySelector("[data-certificate-print]");

    const token = window.TOLAuth.getToken();
    if (!token) {
      window.location.href = "signin.html";
      return;
    }

    try {
      await window.TOLAuth.apiRequest("/auth/me", { method: "GET" });
    } catch (error) {
      window.TOLAuth.clearSession();
      window.location.href = "signin.html";
      return;
    }

    function setStatus(message, type) {
      if (!statusNode) return;
      statusNode.style.display = "block";
      statusNode.textContent = message;
      statusNode.dataset.state = type || "info";

      if (type === "error") {
        statusNode.style.color = "#ffb3b3";
      } else if (type === "success") {
        statusNode.style.color = "#cfe8cf";
      } else {
        statusNode.style.color = "#d6e6ff";
      }
    }

    function clearStatus() {
      if (!statusNode) return;
      statusNode.style.display = "none";
      statusNode.textContent = "";
      statusNode.dataset.state = "";
    }

    function showEmptyState(show) {
      if (!emptyState) return;
      emptyState.style.display = show ? "block" : "none";
    }

    function showOutput(show) {
      if (!output) return;
      output.style.display = show ? "block" : "none";
    }

    function setLoadButtonState(isLoading) {
      if (!loadBtn) return;
      loadBtn.disabled = isLoading;
      loadBtn.textContent = isLoading
        ? "Generating..."
        : "Generate Certificate";
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function safe(value, fallback = "Not available") {
      if (value === null || value === undefined) return escapeHtml(fallback);
      const str = String(value).trim();
      return escapeHtml(str ? str : fallback);
    }

    function renderList(items) {
      if (!Array.isArray(items) || !items.length) {
        return "<li>Not available</li>";
      }

      return items
        .map(function (item) {
          return `<li>${safe(item)}</li>`;
        })
        .join("");
    }

    function getFamilyIdFromUrl() {
      const params = new URLSearchParams(window.location.search);
      return params.get("family_id") || "";
    }

    function setFamilyIdInUrl(familyId) {
      const url = new URL(window.location.href);
      url.searchParams.set("family_id", familyId);
      window.history.replaceState({}, "", url.toString());
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

    function withWorkspaceHref(href, context, familyIdOverride) {
      if (!href) return href;

      const familyId = String(
        familyIdOverride || getFamilyIdFromUrl() || getPreferredFamilyId(context) || "",
      ).trim();
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

    function updateWorkspaceLinks(context, familyIdOverride) {
      document.querySelectorAll('a[href^="tree-view.html"]').forEach(function (node) {
        node.setAttribute(
          "href",
          withWorkspaceHref("tree-view.html", context, familyIdOverride),
        );
      });
    }

    function getResolvedEntitlements(context) {
      if (context?.resolvedEntitlements) return context.resolvedEntitlements;
      if (typeof authPages.buildFallbackEntitlements === "function") {
        return authPages.buildFallbackEntitlements(
          context?.packageCode,
          context?.packageLane,
        );
      }
      return {};
    }

    async function getCurrentContext() {
      if (
        !authPages ||
        typeof authPages.fetchOrders !== "function" ||
        (typeof authPages.getDashboardContextForCurrentPage !== "function" &&
          typeof authPages.getDashboardContext !== "function")
      ) {
        return null;
      }

      const currentUser = await window.TOLAuth.apiRequest("/auth/me", {
        method: "GET",
      });
      const orders = await authPages.fetchOrders();

      if (typeof authPages.getDashboardContextForCurrentPage === "function") {
        return await authPages.getDashboardContextForCurrentPage(
          currentUser,
          orders,
        );
      }

      const hints =
        typeof authPages.getWorkspaceSelectionHints === "function"
          ? authPages.getWorkspaceSelectionHints()
          : undefined;

      return await authPages.getDashboardContext(currentUser, orders, hints);
    }

    function getPreferredFamilyId(context) {
      return String(
        getFamilyIdFromUrl() ||
          context?.activeProject?.family_id ||
          context?.activeProject?.familyId ||
          "",
      ).trim();
    }

    function populateFamilyDropdown(families) {
      if (!familySelect) return;

      familySelect.innerHTML = '<option value="">Select a family</option>';

      families.forEach(function (family) {
        if (!family || !family.id) return;

        const option = document.createElement("option");
        option.value = family.id;
        option.textContent = family.family_name || family.id;
        familySelect.appendChild(option);
      });
    }

    function getChainExplorerUrl(chain, txHash, tokenId, contractAddress) {
      const normalized = String(chain || "")
        .toLowerCase()
        .replace(/[\s_]/g, "-");

      if (normalized.includes("base-mainnet") || normalized === "base") {
        if (txHash) return `https://basescan.org/tx/${txHash}`;
        if (tokenId && contractAddress) {
          return `https://basescan.org/token/${contractAddress}?a=${tokenId}`;
        }
      }

      if (normalized.includes("base-sepolia") || normalized.includes("sepolia")) {
        if (txHash) return `https://sepolia.basescan.org/tx/${txHash}`;
      }

      return null;
    }

    function renderMintPanel(mintStatus) {
      if (!mintStatus) {
        return `
          <section class="exec-certificate" style="margin-top: 1.5rem;">
            <div class="exec-cert-header">
              <div class="exec-cert-brand">
                <div>
                  <div class="exec-cert-brandname">Blockchain Verification</div>
                  <div class="exec-cert-brandsub">Legacy Anchor · Mint Record</div>
                </div>
              </div>
              <div class="exec-cert-badge">Not Available</div>
            </div>
            <div class="exec-cert-footer" style="margin-top: 1rem;">
              <div class="exec-cert-statement">
                No blockchain mint record is available for this family. A Legacy Anchor will
                appear here once it has been issued and confirmed on-chain.
              </div>
            </div>
          </section>
        `;
      }

      const currentStatus = String(mintStatus.current_status || "none").toLowerCase();
      const isMinted = currentStatus === "minted";

      const chain = String(mintStatus.chain || "Base Mainnet");
      const contractAddress = String(mintStatus.contract_address || "");
      const tokenId = String(mintStatus.token_id || "");
      const txHash = String(mintStatus.tx_hash || "");
      const wallet = String(mintStatus.wallet || "");

      const current = mintStatus.current || mintStatus.latest || {};
      const mintedAt = String(
        current.minted_at || mintStatus.minted_at || "",
      ).trim();
      const publicTokenId = String(
        current.public_token_id || mintStatus.public_token_id || "",
      ).trim();
      const versionNumber = mintStatus.version_number != null
        ? String(mintStatus.version_number)
        : String(current.version_number || "");

      const explorerUrl = isMinted
        ? getChainExplorerUrl(chain, txHash || null, tokenId || null, contractAddress || null)
        : null;

      const statusLabel =
        currentStatus === "minted"
          ? "Minted"
          : currentStatus === "minting"
          ? "Minting in Progress"
          : currentStatus === "queued"
          ? "Queued for Minting"
          : currentStatus === "processing"
          ? "Processing"
          : currentStatus === "approved"
          ? "Approved"
          : currentStatus === "draft" || currentStatus === "pending_approval"
          ? "Pending Approval"
          : currentStatus === "failed"
          ? "Failed"
          : currentStatus === "none"
          ? "Not Minted"
          : safe(currentStatus, "Unknown");

      const notAvailable = '<span style="color:#888;font-style:italic;">Not available</span>';

      const explorerLinkHtml = explorerUrl
        ? `<a href="${escapeHtml(explorerUrl)}" target="_blank" rel="noopener noreferrer" style="color:#8a6a2f;font-weight:700;word-break:break-all;">${escapeHtml(explorerUrl)}</a>`
        : notAvailable;

      return `
        <section class="exec-certificate" style="margin-top: 1.5rem;">
          <div class="exec-cert-watermark" aria-hidden="true"></div>

          <div class="exec-cert-header">
            <div class="exec-cert-brand">
              <div>
                <div class="exec-cert-brandname">Blockchain Verification</div>
                <div class="exec-cert-brandsub">Legacy Anchor · Mint Record</div>
              </div>
            </div>
            <div class="exec-cert-badge">${escapeHtml(statusLabel)}</div>
          </div>

          <div class="exec-cert-title" style="margin-top:12px;">
            <div class="exec-cert-eyebrow">On-Chain Proof of Lineage</div>
          </div>

          <div class="exec-cert-grid" style="margin-top:14px;">
            <div class="exec-cert-card">
              <div class="exec-cert-label">Mint Status</div>
              <div class="exec-cert-value">${escapeHtml(statusLabel)}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Chain</div>
              <div class="exec-cert-value">${chain ? escapeHtml(chain) : notAvailable}</div>
            </div>

            <div class="exec-cert-card exec-cert-card-wide">
              <div class="exec-cert-label">Contract Address</div>
              <div class="exec-cert-value">${contractAddress ? escapeHtml(contractAddress) : notAvailable}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Token ID</div>
              <div class="exec-cert-value">${tokenId ? escapeHtml(tokenId) : notAvailable}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Version</div>
              <div class="exec-cert-value">${versionNumber ? escapeHtml(versionNumber) : notAvailable}</div>
            </div>

            <div class="exec-cert-card exec-cert-card-wide">
              <div class="exec-cert-label">Transaction Hash</div>
              <div class="exec-cert-value">${txHash ? escapeHtml(txHash) : notAvailable}</div>
            </div>

            ${
              publicTokenId
                ? `<div class="exec-cert-card exec-cert-card-wide">
                <div class="exec-cert-label">Public Token ID</div>
                <div class="exec-cert-value">${escapeHtml(publicTokenId)}</div>
              </div>`
                : ""
            }

            <div class="exec-cert-card">
              <div class="exec-cert-label">Minted Date</div>
              <div class="exec-cert-value">${mintedAt ? escapeHtml(mintedAt) : notAvailable}</div>
            </div>

            ${
              wallet
                ? `<div class="exec-cert-card">
                <div class="exec-cert-label">Wallet</div>
                <div class="exec-cert-value">${escapeHtml(wallet)}</div>
              </div>`
                : ""
            }

            <div class="exec-cert-card exec-cert-card-wide">
              <div class="exec-cert-label">Explorer Link</div>
              <div class="exec-cert-value">${explorerLinkHtml}</div>
            </div>
          </div>

          <div class="exec-cert-footer">
            <div class="exec-cert-statement">
              ${
                isMinted
                  ? "This Legacy Anchor has been minted and confirmed on-chain. Use the contract address, token ID, and transaction hash above to independently verify this lineage anchor on the blockchain explorer."
                  : "This Legacy Anchor has not yet been minted on-chain. Blockchain verification will appear here once the minting process is complete."
              }
            </div>
          </div>
        </section>
      `;
    }

    function renderCertificate(payload, mintStatus) {
      const certificate = payload.certificate || {};
      const family = certificate.family || {};
      const summary = certificate.summary || {};
      const executive = certificate.executive || {};

      output.innerHTML = `
        <section class="exec-certificate">
          <div class="exec-cert-watermark" aria-hidden="true"></div>

          <div class="exec-cert-header">
            <div class="exec-cert-brand">
              <img class="exec-cert-logo" src="images/tol-watermark-clean.png" alt="Tomb of Light logo" />
              <div>
                <div class="exec-cert-brandname">Tomb of Light</div>
                <div class="exec-cert-brandsub">Executive Lineage Certificate</div>
              </div>
            </div>
            <div class="exec-cert-badge">${safe(certificate.status, "recorded")}</div>
          </div>

          <div class="exec-cert-title">
            <div class="exec-cert-eyebrow">Certified Lineage Record</div>
            <h2>${safe(family.family_name, "Unnamed Family")}</h2>
            <p>Certificate ID: ${safe(certificate.certificate_id)}</p>
          </div>

          <div class="exec-cert-grid">
            <div class="exec-cert-card">
              <div class="exec-cert-label">Issued At</div>
              <div class="exec-cert-value">${safe(certificate.issued_at)}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Integrity Hash</div>
              <div class="exec-cert-value">${safe(certificate.integrity_hash)}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Created By</div>
              <div class="exec-cert-value">${safe(family.created_by)}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Project ID</div>
              <div class="exec-cert-value">${safe(family.project_id)}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Member Count</div>
              <div class="exec-cert-value">${safe(summary.member_count, "0")}</div>
            </div>

            <div class="exec-cert-card">
              <div class="exec-cert-label">Generation Count</div>
              <div class="exec-cert-value">${safe(summary.generation_count, "0")}</div>
            </div>

            <div class="exec-cert-card exec-cert-card-wide">
              <div class="exec-cert-label">Founding Line</div>
              <div class="exec-cert-value">${safe(executive.founding_line)}</div>
            </div>

            <div class="exec-cert-card exec-cert-card-wide">
              <div class="exec-cert-label">Verified Branches</div>
              <div class="exec-cert-value">${safe(executive.verified_branches)}</div>
            </div>

            <div class="exec-cert-card exec-cert-card-wide">
              <div class="exec-cert-label">Descendant Summary</div>
              <div class="exec-cert-value">${safe(executive.descendant_summary)}</div>
            </div>
          </div>

          <div class="exec-cert-wide">
            <div class="exec-cert-card">
              <div class="exec-cert-label">Key Lineage Path</div>
              <ul class="exec-cert-list">
                ${renderList(executive.key_lineage_path)}
              </ul>
            </div>
          </div>

          <div class="exec-cert-footer">
            <div class="exec-cert-statement">
              This executive certificate reflects the lineage structure, verification state,
              and recorded family summary currently stored in the Tomb of Light platform.
            </div>

            <div class="exec-cert-signatures">
              <div>
                <div class="exec-cert-line"></div>
                <div class="exec-cert-signlabel">Authorized Platform Record</div>
              </div>
              <div>
                <div class="exec-cert-line"></div>
                <div class="exec-cert-signlabel">Founder / Steward Approval</div>
              </div>
            </div>
          </div>
        </section>

        ${renderMintPanel(mintStatus)}
      `;
    }

    async function loadFamilyOptions(preferredFamilyId) {
      if (!familySelect) return;

      familySelect.disabled = true;
      familySelect.innerHTML = '<option value="">Loading families...</option>';

      try {
        const families = await window.TOLAuth.apiRequest("/families", {
          method: "GET",
        });

        if (!Array.isArray(families)) {
          throw new Error("Unexpected family response format.");
        }

        populateFamilyDropdown(families);

        if (!families.length) {
          if (preferredFamilyId) {
            familySelect.innerHTML =
              '<option value="">Select a family</option>';

            const fallbackOption = document.createElement("option");
            fallbackOption.value = preferredFamilyId;
            fallbackOption.textContent = "Current Workspace Family";
            familySelect.appendChild(fallbackOption);
            familySelect.value = preferredFamilyId;
            clearStatus();
            return;
          }

          familySelect.innerHTML =
            '<option value="">No families available</option>';
          setStatus("No families were found for this account.", "error");
          return;
        }

        if (preferredFamilyId) {
          const matched = families.some(function (family) {
            return String(family?.id || "") === preferredFamilyId;
          });

          if (!matched) {
            const fallbackOption = document.createElement("option");
            fallbackOption.value = preferredFamilyId;
            fallbackOption.textContent = "Current Workspace Family";
            familySelect.appendChild(fallbackOption);
          }

          familySelect.value = preferredFamilyId;
        }

        clearStatus();
      } catch (error) {
        familySelect.innerHTML =
          '<option value="">Unable to load families</option>';
        setStatus(error.message || "Failed to load family list.", "error");
      } finally {
        familySelect.disabled = false;
      }
    }

    async function generateSelectedCertificate() {
      if (!familySelect || !output) return;

      const familyId = String(familySelect.value || "").trim();

      if (!familyId) {
        showOutput(false);
        showEmptyState(true);
        output.innerHTML = "";
        setStatus("Please select a family first.", "error");
        return;
      }

      setLoadButtonState(true);
      clearStatus();
      showEmptyState(false);
      showOutput(true);
      output.innerHTML = "<p>Loading certificate...</p>";

      try {
        setFamilyIdInUrl(familyId);
        updateWorkspaceLinks(currentContext, familyId);
        const data = await window.TOLAuth.apiRequest(
          `/lineage-certificate/${encodeURIComponent(familyId)}`,
          { method: "GET" },
        );

        const projectId =
          String(
            (data?.certificate?.family?.project_id) || "",
          ).trim() || getProjectIdFromContext(currentContext);

        let mintStatus = null;
        if (projectId) {
          try {
            mintStatus = await window.TOLAuth.apiRequest(
              `/projects/${encodeURIComponent(projectId)}/mint-status`,
              { method: "GET" },
            );
          } catch (_mintErr) {
            mintStatus = null;
          }
        }

        renderCertificate(data, mintStatus);
        clearStatus();
      } catch (error) {
        output.innerHTML = "";
        showOutput(false);
        showEmptyState(true);
        setStatus(error.message || "Failed to load certificate.", "error");
      } finally {
        setLoadButtonState(false);
      }
    }

    if (loadBtn) {
      loadBtn.addEventListener("click", function () {
        generateSelectedCertificate();
      });
    }

    if (familySelect) {
      familySelect.addEventListener("change", function () {
        updateWorkspaceLinks(currentContext, familySelect.value);
        clearStatus();
      });
    }

    if (printBtn) {
      printBtn.addEventListener("click", function () {
        window.print();
      });
    }

    showEmptyState(true);
    showOutput(false);
    clearStatus();

    let currentContext = null;
    try {
      currentContext = await getCurrentContext();
    } catch (error) {
      currentContext = null;
    }

    const preferredFamilyId = getPreferredFamilyId(currentContext);
    updateWorkspaceLinks(currentContext, preferredFamilyId);

    const resolved = getResolvedEntitlements(currentContext);
    if (
      currentContext &&
      currentContext.hasPackageAccess &&
      !resolved.can_use_lineage_certificate
    ) {
      if (familySelect) familySelect.disabled = true;
      if (loadBtn) loadBtn.disabled = true;
      showEmptyState(true);
      showOutput(false);
      setStatus(
        "Lineage Certificate is not included in your active package.",
        "error",
      );
      return;
    }

    await loadFamilyOptions(preferredFamilyId);

    if (preferredFamilyId && familySelect) {
      familySelect.value = preferredFamilyId;
      if (familySelect.value) {
        await generateSelectedCertificate();
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupLineageCertificatePage();
  });
})();
