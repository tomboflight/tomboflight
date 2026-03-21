(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

  const host = window.location.hostname;
  const isLocal = LOCAL_HOSTS.has(host);

  window.TOL_CONFIG = {
    API_BASE_URL: isLocal
      ? "http://127.0.0.1:8000"
      : "https://tomboflight-api.onrender.com",

    PAYMENT_LINKS: isLocal
      ? {
          "digital-legacy-portrait": "REPLACE_WITH_STRIPE_TEST_LINK_1",
          "starter-family-tree": "REPLACE_WITH_STRIPE_TEST_LINK_2",
          "heirloom-legacy-tree": "REPLACE_WITH_STRIPE_TEST_LINK_3",
          "legacy-plus": "REPLACE_WITH_STRIPE_TEST_LINK_4",
        }
      : {
          "digital-legacy-portrait":
            "https://buy.stripe.com/28EeVdeMK4g74mW3d3bEA01",
          "starter-family-tree":
            "https://buy.stripe.com/5kQdR99sq3c32eOdRHbEA02",
          "heirloom-legacy-tree":
            "https://buy.stripe.com/7sY6oHbAybIzf1A6pfbEA00",
          "legacy-plus": "https://buy.stripe.com/9B6aEX7ki8wndXwaFvbEA03",
        },
  };
})();
