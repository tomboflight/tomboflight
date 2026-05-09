(function () {
  "use strict";

  const TOL_PRICING = {
    corePackages: [
      {
        lane: "portrait",
        name: "Legacy Snapshot",
        slug: "legacy_snapshot",
        priceLabel: "$99",
        checkoutUrl: "https://buy.stripe.com/bJe7sL6ge27Z2eOcNDbEA0F",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_snapshot",
      },
      {
        lane: "portrait",
        name: "Legacy Portrait Intro",
        slug: "legacy_portrait_intro",
        priceLabel: "$199",
        checkoutUrl: "https://buy.stripe.com/7sY7sLfQO8wn3iS14VbEA0B",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_portrait_intro",
      },
      {
        lane: "portrait",
        name: "Digital Legacy Portrait",
        slug: "digital_legacy_portrait",
        priceLabel: "$399",
        checkoutUrl: "https://buy.stripe.com/3cIaEXdIG8wn5r08xnbEA0G",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=digital_legacy_portrait",
      },
      {
        lane: "household",
        name: "Household Foundation",
        slug: "household_foundation",
        legacyAlias: "Starter Family Tree",
        priceLabel: "$799",
        checkoutUrl: "https://buy.stripe.com/28E4gz1ZY8wn7z800RbEA0H",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=household_foundation",
      },
      {
        lane: "household",
        name: "Heirloom Legacy Tree",
        slug: "heirloom_legacy_tree",
        priceLabel: "$1,500",
        checkoutUrl: "https://buy.stripe.com/7sY6oHbAybIzf1A6pfbEA00",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=heirloom_legacy_tree",
      },
      {
        lane: "household",
        name: "Legacy Plus",
        slug: "legacy_plus",
        priceLabel: "$3,200",
        checkoutUrl: "https://buy.stripe.com/dRmaEXeMK9Ar1aKaFvbEA0y",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_plus",
      },
      {
        lane: "network",
        name: "Family Estate Concierge",
        slug: "family_estate_concierge",
        priceLabel: "$6,500 starter / custom",
        checkoutUrl: "https://buy.stripe.com/eVqeVdbAyh2T9HgbJzbEA0I",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=family_estate_concierge",
      },
      {
        lane: "organization",
        name: "Command Structure Network",
        slug: "command_structure_network",
        priceLabel: "$1,999 starter / custom",
        checkoutUrl: "https://buy.stripe.com/3cIdR96geeULg5E6pfbEA0J",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=command_structure_network",
      },
    ],
    addons: [
      {
        name: "Extra Upload Pack",
        slug: "extra_upload_pack",
        priceLabel: "$49",
        checkoutUrl: "https://buy.stripe.com/4gMaEXawu8wncTseVLbEA0z",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=extra_upload_pack",
      },
      {
        name: "Extra Storage",
        slug: "extra_storage",
        type: "addon",
        priceLabel: "$50",
        checkoutUrl: "https://buy.stripe.com/7sY5kD1ZY9Arg5EcNDbEA0q",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_storage",
      },
      {
        name: "Portrait Polish",
        slug: "portrait_polish",
        priceLabel: "$79",
        checkoutUrl: "https://buy.stripe.com/00w00j0VU5kbg5EaFvbEA0A",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=portrait_polish",
      },
      {
        name: "Tribute Narration",
        slug: "tribute_narration",
        priceLabel: "$99",
        checkoutUrl: "https://buy.stripe.com/cNi7sL9sqaEvg5E4h7bEA0K",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=tribute_narration",
      },
      {
        name: "Extra Mapped Person",
        slug: "extra_mapped_person",
        type: "addon",
        priceLabel: "$35",
        checkoutUrl: "https://buy.stripe.com/28E14nawuh2T2eO9BrbEA0n",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_mapped_person",
      },
      {
        name: "Extra Zoom Layer",
        slug: "extra_zoom_layer",
        type: "addon",
        priceLabel: "$175",
        checkoutUrl: "https://buy.stripe.com/6oUeVddIG8wncTs7tjbEA0o",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_zoom_layer",
      },
      {
        name: "Additional Narration Minute",
        slug: "additional_narration_minute",
        type: "addon",
        priceLabel: "$200",
        checkoutUrl: "https://buy.stripe.com/5kQ4gz5ca13VdXwcNDbEA0p",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=additional_narration_minute",
      },
      {
        name: "On-Site Photo Scanning",
        slug: "on_site_photo_scanning",
        type: "addon",
        priceLabel: "$499",
        checkoutUrl: "https://buy.stripe.com/28EbJ10VU8wn6v43d3bEA0s",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=on_site_photo_scanning",
      },
      {
        name: "Extra Linked Household",
        slug: "extra_linked_household",
        type: "extra",
        priceLabel: "$1,000",
        checkoutUrl: "https://buy.stripe.com/9B67sL8om3c32eO7tjbEA0L",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_linked_household",
      },
      {
        name: "Extra Branch",
        slug: "extra_branch",
        type: "extra",
        priceLabel: "$1,000",
        checkoutUrl: "https://buy.stripe.com/bJe00j7kidQH06G14VbEA0M",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_branch",
      },
      {
        name: "White-Glove Archive Support",
        slug: "white_glove_archive_support",
        type: "extra",
        priceLabel: "$1,499",
        checkoutUrl: "https://buy.stripe.com/8x214n48613V2eO14VbEA0N",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=white_glove_archive_support",
      },
      {
        name: "Extra Organization Node",
        slug: "extra_org_node",
        type: "extra",
        priceLabel: "$45",
        checkoutUrl: "https://buy.stripe.com/8x2eVd342cMD8Dc6pfbEA0O",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_org_node",
      },
      {
        name: "Extra Organization Level",
        slug: "extra_org_level",
        type: "extra",
        priceLabel: "$175",
        checkoutUrl: "https://buy.stripe.com/aFabJ1awu8wn3iS14VbEA0P",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_org_level",
      },
      {
        name: "Extra Admin Seat",
        slug: "extra_admin_seat",
        type: "extra",
        priceLabel: "$99",
        checkoutUrl: "https://buy.stripe.com/28E9AT3426ofdXw9BrbEA0Q",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_admin_seat",
      },
      {
        name: "Command Report Add-On",
        slug: "command_report_addon",
        type: "addon",
        priceLabel: "$149",
        checkoutUrl: "https://buy.stripe.com/8x2eVdeMKcMD2eO00RbEA0R",
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
          priceLabel: "$3/mo",
          checkoutUrl: "https://buy.stripe.com/eVq6oHbAy8wn4mW8xnbEA0C",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_snapshot_monthly",
        },
        yearly: {
          name: "Legacy Snapshot Maintenance Yearly",
          slug: "legacy_snapshot_yearly",
          priceLabel: "$30/yr",
          checkoutUrl: "https://buy.stripe.com/6oU14n7ki9Ar4mW00RbEA0D",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_snapshot_yearly",
        },
      },
      {
        packageSlug: "legacy_portrait_intro",
        monthly: {
          slug: "legacy_portrait_intro_monthly",
          priceLabel: "$4/mo",
          checkoutUrl: "https://buy.stripe.com/aFabJ13425kb4mWfZPbEA0S",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_portrait_intro_monthly",
        },
        yearly: {
          slug: "legacy_portrait_intro_yearly",
          priceLabel: "$40/yr",
          checkoutUrl: "https://buy.stripe.com/00w5kDdIGeULcTscNDbEA0T",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_portrait_intro_yearly",
        },
      },
      {
        packageSlug: "digital_legacy_portrait",
        monthly: {
          slug: "digital_legacy_portrait_monthly",
          priceLabel: "$6/mo",
          checkoutUrl: "https://buy.stripe.com/bJe00jgUS7sj6v43d3bEA0e",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=digital_legacy_portrait_monthly",
        },
        yearly: {
          slug: "digital_legacy_portrait_yearly",
          priceLabel: "$60/yr",
          checkoutUrl: "https://buy.stripe.com/3cI00jawuh2TaLkaFvbEA0f",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=digital_legacy_portrait_yearly",
        },
      },
      {
        packageSlug: "household_foundation",
        monthly: {
          slug: "household_foundation_monthly",
          priceLabel: "$9/mo",
          checkoutUrl: "https://buy.stripe.com/cNicN51ZY5kbaLk3d3bEA0U",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=household_foundation_monthly",
        },
        yearly: {
          slug: "household_foundation_yearly",
          priceLabel: "$95/yr",
          checkoutUrl: "https://buy.stripe.com/cNi14n486fYPf1A7tjbEA0V",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=household_foundation_yearly",
        },
      },
      {
        packageSlug: "heirloom_legacy_tree",
        monthly: {
          slug: "heirloom_legacy_tree_monthly",
          priceLabel: "$18/mo",
          checkoutUrl: "https://buy.stripe.com/4gM4gzawu4g76v4cNDbEA0i",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=heirloom_legacy_tree_monthly",
        },
        yearly: {
          slug: "heirloom_legacy_tree_yearly",
          priceLabel: "$180/yr",
          checkoutUrl: "https://buy.stripe.com/14AdR9fQO4g73iSfZPbEA0j",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=heirloom_legacy_tree_yearly",
        },
      },
      {
        packageSlug: "legacy_plus",
        monthly: {
          slug: "legacy_plus_monthly",
          priceLabel: "$28/mo",
          checkoutUrl: "https://buy.stripe.com/4gM5kD1ZYdQH8Dc3d3bEA0k",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_plus_monthly",
        },
        yearly: {
          slug: "legacy_plus_yearly",
          priceLabel: "$280/yr",
          checkoutUrl: "https://buy.stripe.com/9B6bJ11ZYfYP9HgeVLbEA0E",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_plus_yearly",
        },
      },
      {
        packageSlug: "family_estate_concierge",
        monthly: {
          slug: "family_estate_concierge_monthly",
          priceLabel: "$60/mo",
          checkoutUrl: "https://buy.stripe.com/00waEX0VU13V7z8bJzbEA0l",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=family_estate_concierge_monthly",
        },
        yearly: {
          slug: "family_estate_concierge_yearly",
          priceLabel: "$600/yr",
          checkoutUrl: "https://buy.stripe.com/7sYfZhfQO5kbdXwbJzbEA0m",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=family_estate_concierge_yearly",
        },
      },
      {
        packageSlug: "command_structure_network",
        monthly: {
          slug: "command_structure_network_monthly",
          priceLabel: "$20/mo",
          checkoutUrl: "https://buy.stripe.com/28E9AT342h2T2eOcNDbEA0W",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=command_structure_network_monthly",
        },
        yearly: {
          slug: "command_structure_network_yearly",
          priceLabel: "$200/yr",
          checkoutUrl: "https://buy.stripe.com/fZu5kDeMK4g72eO3d3bEA0X",
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
