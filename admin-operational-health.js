(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (!app) return;

  function text(value) {
    return String(value == null ? "" : value).trim();
  }

  function escapeHtml(value) {
    return text(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function statusLabel(value) {
    return value ? "READY" : "UNAVAILABLE";
  }

  function ensurePanel() {
    let panel = document.querySelector("[data-admin-operational-health]");
    if (panel) return panel;
    const kernel = document.querySelector("[data-admin-kernel-status]");
    if (!kernel || !kernel.parentNode) return null;
    panel = document.createElement("div");
    panel.className = "admin-warning-strip";
    panel.setAttribute("data-admin-operational-health", "");
    panel.setAttribute("aria-live", "polite");
    panel.style.marginTop = "0.75rem";
    panel.innerHTML =
      '<span>Production Readiness</span><div><strong>Checking scanner and private storage…</strong></div>';
    kernel.insertAdjacentElement("afterend", panel);
    return panel;
  }

  async function fetchOperationalHealth() {
    const base = typeof app.getApiBaseUrl === "function" ? app.getApiBaseUrl() : "";
    const token = typeof app.getToken === "function" ? app.getToken() : "";
    const response = await fetch(`${base}/health/operational`, {
      method: "GET",
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }
    if (response.status === 401 || response.status === 403) {
      throw new Error("Operational readiness is available only to the authorized CEO/super-admin session.");
    }
    if (!payload || typeof payload !== "object") {
      throw new Error("Operational readiness did not return a usable response.");
    }
    return payload;
  }

  function render(payload) {
    const panel = ensurePanel();
    if (!panel) return;
    const components = payload.components || {};
    const scanner = components.upload_scanner || {};
    const staging = components.private_upload_storage || {};
    const objectStorage = components.private_object_storage || {};
    const release = payload.release || {};
    const backlog = objectStorage.legacy_clean_local_uploads;
    const degraded = Array.isArray(payload.operational_degraded_reasons)
      ? payload.operational_degraded_reasons
      : [];

    panel.innerHTML = `
      <span>Production Readiness</span>
      <div style="width:100%">
        <strong>${payload.operational_ready ? "Review infrastructure ready" : "Review infrastructure needs attention"}</strong>
        <div class="grid-3" style="margin-top:.65rem;gap:.55rem">
          <div><span class="eyebrow">Security Scanner</span><p class="card-copy"><strong>${statusLabel(Boolean(scanner.available))}</strong>${scanner.mode ? ` · ${escapeHtml(scanner.mode)}` : ""}</p></div>
          <div><span class="eyebrow">Private R2</span><p class="card-copy"><strong>${statusLabel(Boolean(objectStorage.available))}</strong>${objectStorage.mode ? ` · ${escapeHtml(objectStorage.mode)}` : ""}</p></div>
          <div><span class="eyebrow">Staging Disk</span><p class="card-copy"><strong>${staging.persistent ? "PERSISTENT" : "NOT PERSISTENT"}</strong></p></div>
          <div><span class="eyebrow">Legacy Upload Migration</span><p class="card-copy"><strong>${backlog == null ? "UNKNOWN" : escapeHtml(backlog)}</strong> file${Number(backlog) === 1 ? "" : "s"} pending</p></div>
          <div><span class="eyebrow">Backend Release</span><p class="card-copy"><strong>${escapeHtml(release.commit || "Unknown")}</strong></p></div>
          <div><span class="eyebrow">Operational State</span><p class="card-copy"><strong>${payload.operational_ready ? "READY" : "DEGRADED"}</strong></p></div>
        </div>
        ${degraded.length ? `<p class="card-copy" style="margin-top:.65rem"><strong>Attention:</strong> ${escapeHtml(degraded.join(" · "))}</p>` : ""}
      </div>`;
  }

  function renderError(error) {
    const panel = ensurePanel();
    if (!panel) return;
    panel.innerHTML = `<span>Production Readiness</span><div><strong>Operational status unavailable</strong><p class="card-copy">${escapeHtml(error && error.message ? error.message : "Unable to check scanner and private storage.")}</p></div>`;
  }

  async function setup() {
    if (!document.querySelector("[data-admin-kernel-status]")) return;
    ensurePanel();
    try {
      const payload = await fetchOperationalHealth();
      render(payload);
    } catch (error) {
      renderError(error);
    }
  }

  document.addEventListener("DOMContentLoaded", setup);
})();