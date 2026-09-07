(function () {
  "use strict";

  const config = window.TOL_CONFIG || (window.TOL_CONFIG = {});
  const hostname = String(window.location && window.location.hostname || "")
    .trim()
    .toLowerCase();
  const isProductionHost =
    hostname === "tomboflight.com" || hostname === "www.tomboflight.com";

  if (!isProductionHost) {
    return;
  }

  const gatewayBase = `${window.location.origin}/api-gateway`;
  const directBackendBase = "https://tomboflight-api.onrender.com";

  config.API_BASE_URL = gatewayBase;
  config.API_BASE_URLS = [gatewayBase, directBackendBase];

  try {
    const saved = String(
      window.sessionStorage.getItem("tol_api_base_url") || "",
    ).trim().replace(/\/+$/, "");
    if (saved && saved.includes("/api-gateway") && saved !== gatewayBase) {
      window.sessionStorage.removeItem("tol_api_base_url");
    }
  } catch (_error) {
    // Storage is an optimization only. Routing must continue without it.
  }
})();
