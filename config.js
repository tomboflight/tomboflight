(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

  const host = window.location.hostname;
  const isLocal = LOCAL_HOSTS.has(host);

  window.TOL_CONFIG = {
    API_BASE_URL: isLocal
      ? "http://127.0.0.1:8000"
      : "https://tomboflight-api.onrender.com",
  };
})();
