(function () {
  "use strict";

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

    function renderCertificate(payload) {
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
      `;
    }

    async function loadFamilyOptions() {
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
          familySelect.innerHTML =
            '<option value="">No families available</option>';
          setStatus("No families were found for this account.", "error");
          return;
        }

        const urlFamilyId = getFamilyIdFromUrl();
        if (urlFamilyId) {
          familySelect.value = urlFamilyId;
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
        const data = await window.TOLAuth.apiRequest(
          `/lineage-certificate/${encodeURIComponent(familyId)}`,
          { method: "GET" },
        );
        renderCertificate(data);
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

    await loadFamilyOptions();

    const urlFamilyId = getFamilyIdFromUrl();
    if (urlFamilyId && familySelect) {
      familySelect.value = urlFamilyId;
      if (familySelect.value) {
        await generateSelectedCertificate();
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupLineageCertificatePage();
  });
})();
