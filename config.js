(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);
  const localHost = String(window.location.hostname || "").toLowerCase();
  const isLocal = LOCAL_HOSTS.has(localHost);
  const preferredLocalApiBaseUrl =
    localHost === "localhost"
      ? "http://localhost:8000"
      : localHost === "::1" || localHost === "[::1]"
      ? "http://[::1]:8000"
      : "http://127.0.0.1:8000";

  window.TOL_CONFIG = Object.assign({}, window.TOL_CONFIG || {}, {
    API_BASE_URL: isLocal
      ? preferredLocalApiBaseUrl
      : "https://tomboflight-api.onrender.com",
    API_BASE_URLS: isLocal
      ? [preferredLocalApiBaseUrl, "http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"]
      : [
          "https://api.tomboflight.com",
          "https://tomboflight-api.onrender.com",
        ],

    PAYMENT_LINKS: Object.assign(
      {},
      (window.TOL_CONFIG && window.TOL_CONFIG.PAYMENT_LINKS) || {},
      {
        /* =========================
           MAIN PACKAGES
        ========================= */
        legacy_snapshot: "https://buy.stripe.com/bJe7sL6ge27Z2eOcNDbEA0F",

        legacy_portrait_intro: "https://buy.stripe.com/7sY7sLfQO8wn3iS14VbEA0B",

        digital_legacy_portrait:
          "https://buy.stripe.com/3cIaEXdIG8wn5r08xnbEA0G",

        household_foundation: "https://buy.stripe.com/28E4gz1ZY8wn7z800RbEA0H",

        heirloom_legacy_tree: "https://buy.stripe.com/7sY6oHbAybIzf1A6pfbEA00",

        legacy_plus: "https://buy.stripe.com/dRmaEXeMK9Ar1aKaFvbEA0y",

        family_estate_concierge:
          "https://buy.stripe.com/eVqeVdbAyh2T9HgbJzbEA0I",

        command_structure_network:
          "https://buy.stripe.com/3cIdR96geeULg5E6pfbEA0J",

        /* =========================
           BACKWARD-COMPATIBILITY ALIASES
        ========================= */
        starter_family_tree: "https://buy.stripe.com/28E4gz1ZY8wn7z800RbEA0H",

        /* =========================
           ADD-ONS
        ========================= */
        extra_upload_pack: "https://buy.stripe.com/4gMaEXawu8wncTseVLbEA0z",

        extra_storage: "https://buy.stripe.com/7sY5kD1ZY9Arg5EcNDbEA0q",

        portrait_polish: "https://buy.stripe.com/00w00j0VU5kbg5EaFvbEA0A",

        tribute_narration: "https://buy.stripe.com/cNi7sL9sqaEvg5E4h7bEA0K",

        extra_mapped_person: "https://buy.stripe.com/28E14nawuh2T2eO9BrbEA0n",

        extra_zoom_layer: "https://buy.stripe.com/6oUeVddIG8wncTs7tjbEA0o",

        additional_narration_minute:
          "https://buy.stripe.com/5kQ4gz5ca13VdXwcNDbEA0p",

        on_site_photo_scanning:
          "https://buy.stripe.com/28EbJ10VU8wn6v43d3bEA0s",

        extra_linked_household:
          "https://buy.stripe.com/9B67sL8om3c32eO7tjbEA0L",

        extra_branch: "https://buy.stripe.com/bJe00j7kidQH06G14VbEA0M",

        white_glove_archive_support:
          "https://buy.stripe.com/8x214n48613V2eO14VbEA0N",

        extra_org_node: "https://buy.stripe.com/8x2eVd342cMD8Dc6pfbEA0O",

        extra_org_level: "https://buy.stripe.com/aFabJ1awu8wn3iS14VbEA0P",

        extra_admin_seat: "https://buy.stripe.com/28E9AT3426ofdXw9BrbEA0Q",

        command_report_addon: "https://buy.stripe.com/8x2eVdeMKcMD2eO00RbEA0R",

        /* =========================
           MAINTENANCE — MONTHLY
        ========================= */
        legacy_snapshot_maintenance_monthly:
          "https://buy.stripe.com/eVq6oHbAy8wn4mW8xnbEA0C",

        legacy_portrait_intro_maintenance_monthly:
          "https://buy.stripe.com/aFabJ13425kb4mWfZPbEA0S",

        digital_legacy_portrait_maintenance_monthly:
          "https://buy.stripe.com/bJe00jgUS7sj6v43d3bEA0e",

        household_foundation_maintenance_monthly:
          "https://buy.stripe.com/cNicN51ZY5kbaLk3d3bEA0U",

        heirloom_legacy_tree_maintenance_monthly:
          "https://buy.stripe.com/4gM4gzawu4g76v4cNDbEA0i",

        legacy_plus_maintenance_monthly:
          "https://buy.stripe.com/4gM5kD1ZYdQH8Dc3d3bEA0k",

        family_estate_concierge_maintenance_monthly:
          "https://buy.stripe.com/00waEX0VU13V7z8bJzbEA0l",

        command_structure_network_maintenance_monthly:
          "https://buy.stripe.com/28E9AT342h2T2eOcNDbEA0W",

        /* =========================
           MAINTENANCE — YEARLY
        ========================= */
        legacy_snapshot_maintenance_yearly:
          "https://buy.stripe.com/00wfZh4864g7cTsbJzbEA0Y",

        legacy_portrait_intro_maintenance_yearly:
          "https://buy.stripe.com/00w5kDdIGeULcTscNDbEA0T",

        digital_legacy_portrait_maintenance_yearly:
          "https://buy.stripe.com/3cI00jawuh2TaLkaFvbEA0f",

        household_foundation_maintenance_yearly:
          "https://buy.stripe.com/cNi14n486fYPf1A7tjbEA0V",

        heirloom_legacy_tree_maintenance_yearly:
          "https://buy.stripe.com/14AdR9fQO4g73iSfZPbEA0j",

        legacy_plus_maintenance_yearly:
          "https://buy.stripe.com/9B6bJ11ZYfYP9HgeVLbEA0E",

        family_estate_concierge_maintenance_yearly:
          "https://buy.stripe.com/7sYfZhfQO5kbdXwbJzbEA0m",

        command_structure_network_maintenance_yearly:
          "https://buy.stripe.com/fZu5kDeMK4g72eO3d3bEA0X",
      },
    ),
  });
})();
