(function () {
  "use strict";

  const TOL_PRICING = {
    corePackages: [
      {
        lane: "portrait",
        name: "Legacy Snapshot",
        slug: "legacy_snapshot",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_snapshot",
      },
      {
        lane: "portrait",
        name: "Legacy Portrait Intro",
        slug: "legacy_portrait_intro",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_portrait_intro",
      },
      {
        lane: "portrait",
        name: "Digital Legacy Portrait",
        slug: "digital_legacy_portrait",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=digital_legacy_portrait",
      },
      {
        lane: "household",
        name: "Household Foundation",
        slug: "household_foundation",
        legacyAlias: "Starter Family Tree",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=household_foundation",
      },
      {
        lane: "household",
        name: "Heirloom Legacy Tree",
        slug: "heirloom_legacy_tree",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=heirloom_legacy_tree",
      },
      {
        lane: "household",
        name: "Legacy Plus",
        slug: "legacy_plus",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_plus",
      },
      {
        lane: "network",
        name: "Family Estate Concierge",
        slug: "family_estate_concierge",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=family_estate_concierge",
      },
      {
        lane: "organization",
        name: "Command Structure Network",
        slug: "command_structure_network",
        priceLabel: "",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=command_structure_network",
      },
    ],
    addons: [
      {
        name: "Extra Upload Pack",
        slug: "extra_upload_pack",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=extra_upload_pack",
      },
      {
        name: "Extra Storage",
        slug: "extra_storage",
        type: "addon",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_storage",
      },
      {
        name: "Portrait Polish",
        slug: "portrait_polish",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=portrait_polish",
      },
      {
        name: "Tribute Narration",
        slug: "tribute_narration",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=tribute_narration",
      },
      {
        name: "Extra Mapped Person",
        slug: "extra_mapped_person",
        type: "addon",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_mapped_person",
      },
      {
        name: "Extra Zoom Layer",
        slug: "extra_zoom_layer",
        type: "addon",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_zoom_layer",
      },
      {
        name: "Additional Narration Minute",
        slug: "additional_narration_minute",
        type: "addon",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=additional_narration_minute",
      },
      {
        name: "On-Site Photo Scanning",
        slug: "on_site_photo_scanning",
        type: "addon",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=on_site_photo_scanning",
      },
      {
        name: "Extra Linked Household",
        slug: "extra_linked_household",
        type: "extra",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_linked_household",
      },
      {
        name: "Extra Branch",
        slug: "extra_branch",
        type: "extra",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_branch",
      },
      {
        name: "White-Glove Archive Support",
        slug: "white_glove_archive_support",
        type: "extra",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=white_glove_archive_support",
      },
      {
        name: "Extra Organization Node",
        slug: "extra_org_node",
        type: "extra",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_org_node",
      },
      {
        name: "Extra Organization Level",
        slug: "extra_org_level",
        type: "extra",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_org_level",
      },
      {
        name: "Extra Admin Seat",
        slug: "extra_admin_seat",
        type: "extra",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_admin_seat",
      },
      {
        name: "Command Report Add-On",
        slug: "command_report_addon",
        type: "addon",
        priceLabel: "Pricing being updated",
        checkoutUrl: "",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=command_report_addon",
      },
    ],
    maintenance: [
      {
        packageSlug: "legacy_snapshot",
        monthly: {
          name: "Legacy Snapshot Maintenance Monthly",
          slug: "legacy_snapshot_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_snapshot_monthly",
        },
        yearly: {
          name: "Legacy Snapshot Maintenance Yearly",
          slug: "legacy_snapshot_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_snapshot_yearly",
        },
      },
      {
        packageSlug: "legacy_portrait_intro",
        monthly: {
          slug: "legacy_portrait_intro_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_portrait_intro_monthly",
        },
        yearly: {
          slug: "legacy_portrait_intro_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_portrait_intro_yearly",
        },
      },
      {
        packageSlug: "digital_legacy_portrait",
        monthly: {
          slug: "digital_legacy_portrait_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=digital_legacy_portrait_monthly",
        },
        yearly: {
          slug: "digital_legacy_portrait_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=digital_legacy_portrait_yearly",
        },
      },
      {
        packageSlug: "household_foundation",
        monthly: {
          slug: "household_foundation_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=household_foundation_monthly",
        },
        yearly: {
          slug: "household_foundation_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=household_foundation_yearly",
        },
      },
      {
        packageSlug: "heirloom_legacy_tree",
        monthly: {
          slug: "heirloom_legacy_tree_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=heirloom_legacy_tree_monthly",
        },
        yearly: {
          slug: "heirloom_legacy_tree_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=heirloom_legacy_tree_yearly",
        },
      },
      {
        packageSlug: "legacy_plus",
        monthly: {
          slug: "legacy_plus_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_plus_monthly",
        },
        yearly: {
          slug: "legacy_plus_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_plus_yearly",
        },
      },
      {
        packageSlug: "family_estate_concierge",
        monthly: {
          slug: "family_estate_concierge_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=family_estate_concierge_monthly",
        },
        yearly: {
          slug: "family_estate_concierge_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=family_estate_concierge_yearly",
        },
      },
      {
        packageSlug: "command_structure_network",
        monthly: {
          slug: "command_structure_network_monthly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=command_structure_network_monthly",
        },
        yearly: {
          slug: "command_structure_network_yearly",
          priceLabel: "",
          checkoutUrl: "",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=command_structure_network_yearly",
        },
      },
    ],
  };

  function buildPaymentLinksFromPricing(pricing) {
    const links = {};
    (pricing.corePackages || []).forEach(function (item) {
      if (item?.slug && item?.checkoutUrl) {
        links[item.slug] = item.checkoutUrl;
      }
    });
    (pricing.addons || []).forEach(function (item) {
      if (item?.slug && item?.checkoutUrl) {
        links[item.slug] = item.checkoutUrl;
      }
    });
    (pricing.maintenance || []).forEach(function (entry) {
      const packageSlug = String(entry?.packageSlug || "").trim();
      ["monthly", "yearly"].forEach(function (period) {
        const option = entry?.[period];
        if (!option?.checkoutUrl) return;
        const slug = String(option.slug || "").trim();
        if (slug) {
          links[slug] = option.checkoutUrl;
        }
        if (packageSlug) {
          links[`${packageSlug}_maintenance_${period}`] = option.checkoutUrl;
        }
      });
    });
    if (links.household_foundation) {
      links.starter_family_tree = links.household_foundation;
    }
    return links;
  }

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);
  const localHost = String(window.location.hostname || "").toLowerCase();
  const isLocal = LOCAL_HOSTS.has(localHost);
  const preferredLocalApiBaseUrl =
    localHost === "localhost"
      ? "http://localhost:8000"
      : localHost === "::1" || localHost === "[::1]"
      ? "http://[::1]:8000"
      : "http://127.0.0.1:8000";
  const localApiBaseUrls = Array.from(
    new Set([
      preferredLocalApiBaseUrl,
      "http://127.0.0.1:8000",
      "http://localhost:8000",
      "http://[::1]:8000",
    ]),
  );

  window.TOL_CONFIG = Object.assign({}, window.TOL_CONFIG || {}, {
    TOL_PRICING,
    API_BASE_URL: isLocal
      ? preferredLocalApiBaseUrl
      : "https://tomboflight-api.onrender.com",
    API_BASE_URLS: isLocal
      ? localApiBaseUrls
      : [
          "https://tomboflight-api.onrender.com",
          "https://api.tomboflight.com",
        ],
    INVITE_API_BASE_URL_FALLBACKS: isLocal
      ? localApiBaseUrls
      : [
          "https://tomboflight-api.onrender.com",
          "https://api.tomboflight.com",
        ],

    PAYMENT_LINKS: Object.assign({}, buildPaymentLinksFromPricing(TOL_PRICING)),
  });
})();
