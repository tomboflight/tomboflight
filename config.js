(function () {
  "use strict";

  const TOL_PRICING = {
    corePackages: [
      {
        lane: "portrait",
        name: "Legacy Snapshot",
        slug: "legacy_snapshot",
        priceLabel: "$99 one-time",
        checkoutUrl: "https://buy.stripe.com/bJe5kD1ZYbIzdXw14VbEA11",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_snapshot",
      },
      {
        lane: "portrait",
        name: "Legacy Portrait Intro",
        slug: "legacy_portrait_intro",
        priceLabel: "$199 one-time",
        checkoutUrl: "https://buy.stripe.com/eVq14nfQO13V7z8fZPbEA12",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_portrait_intro",
      },
      {
        lane: "portrait",
        name: "Digital Legacy Portrait",
        slug: "digital_legacy_portrait",
        priceLabel: "$399 one-time",
        checkoutUrl: "https://buy.stripe.com/28E28reMK9Ar6v48xnbEA13",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=digital_legacy_portrait",
      },
      {
        lane: "household",
        name: "Household Foundation",
        slug: "household_foundation",
        legacyAlias: "Starter Family Tree",
        priceLabel: "$799 one-time",
        checkoutUrl: "https://buy.stripe.com/7sYaEXfQObIzcTs28ZbEA14",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=household_foundation",
      },
      {
        lane: "household",
        name: "Heirloom Legacy Tree",
        slug: "heirloom_legacy_tree",
        priceLabel: "$1,500 one-time",
        checkoutUrl: "https://buy.stripe.com/7sY7sL9sq4g74mW9BrbEA15",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=heirloom_legacy_tree",
      },
      {
        lane: "household",
        name: "Legacy Plus",
        slug: "legacy_plus",
        priceLabel: "$3,200 one-time",
        checkoutUrl: "https://buy.stripe.com/14A8wPawubIzg5EaFvbEA16",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=legacy_plus",
      },
      {
        lane: "network",
        name: "Family Estate Concierge",
        slug: "family_estate_concierge",
        priceLabel: "$6,500 one-time",
        checkoutUrl: "https://buy.stripe.com/cNi7sL48613V7z8dRHbEA17",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=family_estate_concierge",
      },
      {
        lane: "organization",
        name: "Command Structure Network",
        slug: "command_structure_network",
        priceLabel: "Starting at $2,999 one-time",
        checkoutUrl: "https://buy.stripe.com/dRm00j8omfYP06G9BrbEA18",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&package=command_structure_network",
      },
    ],
    addons: [
      {
        category: "storage_vault_upgrades",
        name: "Extra Upload Pack",
        slug: "extra_upload_pack",
        type: "addon",
        priceLabel: "$49 one-time",
        checkoutUrl: "https://buy.stripe.com/aFa7sL8om13V3iS6pfbEA1p",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_upload_pack",
      },
      {
        category: "storage_vault_upgrades",
        name: "Extra Storage +10GB Monthly",
        slug: "extra_storage_10gb_monthly",
        type: "addon",
        priceLabel: "$15/month",
        checkoutUrl: "https://buy.stripe.com/8x29ATeMKh2T6v414VbEA1q",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_storage_10gb_monthly",
      },
      {
        category: "storage_vault_upgrades",
        name: "Extra Storage +10GB Annual",
        slug: "extra_storage_10gb_yearly",
        type: "addon",
        priceLabel: "$150/year",
        checkoutUrl: "https://buy.stripe.com/8x2dR97ki9Ar9Hg5lbbEA1r",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_storage_10gb_yearly",
      },
      {
        category: "storage_vault_upgrades",
        name: "Vault Expansion +25GB Monthly",
        slug: "vault_expansion_25gb_monthly",
        type: "addon",
        priceLabel: "$29/month",
        checkoutUrl: "https://buy.stripe.com/dRm28r1ZY27ZdXweVLbEA1s",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=vault_expansion_25gb_monthly",
      },
      {
        category: "storage_vault_upgrades",
        name: "Vault Expansion +25GB Annual",
        slug: "vault_expansion_25gb_yearly",
        type: "addon",
        priceLabel: "$290/year",
        checkoutUrl: "https://buy.stripe.com/14A6oHbAydQH5r0eVLbEA1t",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=vault_expansion_25gb_yearly",
      },
      {
        category: "storage_vault_upgrades",
        name: "Vault Expansion +50GB Monthly",
        slug: "vault_expansion_50gb_monthly",
        type: "addon",
        priceLabel: "$59/month",
        checkoutUrl: "https://buy.stripe.com/9B6fZh7kicMDaLkaFvbEA1u",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=vault_expansion_50gb_monthly",
      },
      {
        category: "storage_vault_upgrades",
        name: "Vault Expansion +50GB Annual",
        slug: "vault_expansion_50gb_yearly",
        type: "addon",
        priceLabel: "$590/year",
        checkoutUrl: "https://buy.stripe.com/8x228r0VUfYPcTsfZPbEA1v",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=vault_expansion_50gb_yearly",
      },
      {
        category: "storage_vault_upgrades",
        name: "Private Vault Export",
        slug: "private_vault_export",
        type: "addon",
        priceLabel: "$199 one-time",
        checkoutUrl: "https://buy.stripe.com/aFa9ATfQOcMD4mW3d3bEA1I",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=private_vault_export",
      },
      {
        category: "portrait_narration_enhancements",
        name: "Portrait Polish",
        slug: "portrait_polish",
        type: "addon",
        priceLabel: "$99 one-time",
        checkoutUrl: "https://buy.stripe.com/9B6dR9awu6of7z85lbbEA1w",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=portrait_polish",
      },
      {
        category: "portrait_narration_enhancements",
        name: "Tribute Narration",
        slug: "tribute_narration",
        type: "addon",
        priceLabel: "$149 one-time",
        checkoutUrl: "https://buy.stripe.com/cNi14n7ki7sj1aKaFvbEA1x",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=tribute_narration",
      },
      {
        category: "portrait_narration_enhancements",
        name: "Additional Narration Minute",
        slug: "additional_narration_minute",
        type: "addon",
        priceLabel: "$200 one-time",
        checkoutUrl: "https://buy.stripe.com/bJe5kD486cMD2eOfZPbEA1y",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=additional_narration_minute",
      },
      {
        category: "portrait_narration_enhancements",
        name: "Extra Mapped Person",
        slug: "extra_mapped_person",
        type: "addon",
        priceLabel: "$49 one-time",
        checkoutUrl: "https://buy.stripe.com/3cIaEXbAy8wnaLk4h7bEA1z",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_mapped_person",
      },
      {
        category: "portrait_narration_enhancements",
        name: "Extra Zoom Layer",
        slug: "extra_zoom_layer",
        type: "addon",
        priceLabel: "$199 one-time",
        checkoutUrl: "https://buy.stripe.com/6oUaEX4866of1aKaFvbEA1A",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=extra_zoom_layer",
      },
      {
        category: "family_organization_expansion",
        name: "Extra Linked Household",
        slug: "extra_linked_household",
        type: "extra",
        priceLabel: "$1,250 one-time",
        checkoutUrl: "https://buy.stripe.com/bJecN57ki27Z06GaFvbEA1B",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_linked_household",
      },
      {
        category: "family_organization_expansion",
        name: "Extra Branch",
        slug: "extra_branch",
        type: "extra",
        priceLabel: "$1,500 one-time",
        checkoutUrl: "https://buy.stripe.com/eVq7sLfQO4g76v47tjbEA1C",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_branch",
      },
      {
        category: "family_organization_expansion",
        name: "Extra Organization Node",
        slug: "extra_org_node",
        type: "extra",
        priceLabel: "$99 one-time",
        checkoutUrl: "https://buy.stripe.com/9B6aEX8om9Ar6v45lbbEA1D",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_org_node",
      },
      {
        category: "family_organization_expansion",
        name: "Extra Organization Level",
        slug: "extra_org_level",
        type: "extra",
        priceLabel: "$299 one-time",
        checkoutUrl: "https://buy.stripe.com/5kQ6oH7ki9Ar9HgdRHbEA1E",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_org_level",
      },
      {
        category: "family_organization_expansion",
        name: "Extra Admin Seat Monthly",
        slug: "extra_admin_seat_monthly",
        type: "extra",
        priceLabel: "$19/month",
        checkoutUrl: "https://buy.stripe.com/14AbJ18omcMDf1A6pfbEA1F",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_admin_seat_monthly",
      },
      {
        category: "family_organization_expansion",
        name: "Extra Admin Seat Annual",
        slug: "extra_admin_seat_yearly",
        type: "extra",
        priceLabel: "$190/year",
        checkoutUrl: "https://buy.stripe.com/6oU8wP0VUbIz5r09BrbEA1G",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=extra_admin_seat_yearly",
      },
      {
        category: "family_organization_expansion",
        name: "Command Report",
        slug: "command_report_addon",
        type: "addon",
        priceLabel: "$299 one-time",
        checkoutUrl: "https://buy.stripe.com/eVq3cvfQO3c39Hg8xnbEA1H",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=command_report_addon",
      },
      {
        category: "review_corrections_records",
        name: "Emergency Retrieval Support",
        slug: "emergency_retrieval_support",
        type: "addon",
        priceLabel: "$249 one-time",
        checkoutUrl: "https://buy.stripe.com/6oUaEXcECfYP4mWcNDbEA1J",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=emergency_retrieval_support",
      },
      {
        category: "review_corrections_records",
        name: "Family Correction Cycle",
        slug: "family_correction_cycle",
        type: "addon",
        priceLabel: "$149 one-time",
        checkoutUrl: "https://buy.stripe.com/6oU14nfQOaEvf1A5lbbEA1K",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=family_correction_cycle",
      },
      {
        category: "review_corrections_records",
        name: "Organization Correction Cycle",
        slug: "organization_correction_cycle",
        type: "addon",
        priceLabel: "$249 one-time",
        checkoutUrl: "https://buy.stripe.com/eVq00j3424g7aLk28ZbEA1L",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=organization_correction_cycle",
      },
      {
        category: "review_corrections_records",
        name: "Document/Record Review Pack",
        slug: "document_record_review_pack",
        type: "addon",
        priceLabel: "$299 one-time",
        checkoutUrl: "https://buy.stripe.com/cNifZh5ca4g7aLk7tjbEA1M",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=document_record_review_pack",
      },
      {
        category: "nft_blockchain_legacy_records",
        name: "NFT Lineage Record",
        slug: "nft_lineage_record",
        type: "addon",
        priceLabel: "$499 one-time",
        checkoutUrl: "https://buy.stripe.com/28E5kDgUSbIzcTs8xnbEA1N",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=nft_lineage_record",
      },
      {
        category: "nft_blockchain_legacy_records",
        name: "Additional NFT Copy / Mint",
        slug: "additional_nft_copy_mint",
        type: "addon",
        priceLabel: "$399 one-time",
        checkoutUrl: "https://buy.stripe.com/dRm14n5ca7sjf1AbJzbEA1O",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=additional_nft_copy_mint",
      },
      {
        category: "nft_blockchain_legacy_records",
        name: "NFT Metadata Revision",
        slug: "nft_metadata_revision",
        type: "addon",
        priceLabel: "$149 one-time",
        checkoutUrl: "https://buy.stripe.com/cNiaEX1ZYaEvaLkfZPbEA1P",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=nft_metadata_revision",
      },
      {
        category: "white_glove_services",
        name: "On-Site Photo Scanning",
        slug: "on_site_photo_scanning",
        type: "addon",
        priceLabel: "Starting at $599",
        checkoutUrl: "https://buy.stripe.com/7sY00jawudQHdXwdRHbEA1Q",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=on_site_photo_scanning",
      },
      {
        category: "white_glove_services",
        name: "White-Glove Archive Support",
        slug: "white_glove_archive_support",
        type: "extra",
        priceLabel: "Starting at $1,999",
        checkoutUrl: "https://buy.stripe.com/28EcN57kibIzcTs5lbbEA1R",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=extra&package=white_glove_archive_support",
      },
      {
        category: "rush_delivery",
        name: "Rush Delivery Snapshot / Portrait Intro",
        slug: "rush_delivery_snapshot_portrait_intro",
        type: "addon",
        priceLabel: "$99 one-time",
        checkoutUrl: "https://buy.stripe.com/00w4gzfQO9Ar3iSfZPbEA1S",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=rush_delivery_snapshot_portrait_intro",
      },
      {
        category: "rush_delivery",
        name: "Rush Delivery Digital Legacy Portrait",
        slug: "rush_delivery_digital_legacy_portrait",
        type: "addon",
        priceLabel: "$199 one-time",
        checkoutUrl: "https://buy.stripe.com/aFafZhawueULf1AbJzbEA1T",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=rush_delivery_digital_legacy_portrait",
      },
      {
        category: "rush_delivery",
        name: "Rush Delivery Household Foundation",
        slug: "rush_delivery_household_foundation",
        type: "addon",
        priceLabel: "$399 one-time",
        checkoutUrl: "https://buy.stripe.com/fZu9AT8omcMDcTsbJzbEA1U",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=rush_delivery_household_foundation",
      },
      {
        category: "rush_delivery",
        name: "Rush Delivery Heirloom Legacy Tree",
        slug: "rush_delivery_heirloom_legacy_tree",
        type: "addon",
        priceLabel: "$750 one-time",
        checkoutUrl: "https://buy.stripe.com/6oU6oH3427sj8DcaFvbEA1V",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=rush_delivery_heirloom_legacy_tree",
      },
      {
        category: "rush_delivery",
        name: "Rush Delivery Legacy Plus",
        slug: "rush_delivery_legacy_plus",
        type: "addon",
        priceLabel: "$1,500 one-time",
        checkoutUrl: "https://buy.stripe.com/28E6oH486fYP6v4eVLbEA1W",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=rush_delivery_legacy_plus",
      },
      {
        category: "rush_delivery",
        name: "Rush Delivery Estate / Command Minimum",
        slug: "rush_delivery_estate_command_minimum",
        type: "addon",
        priceLabel: "$2,000 minimum deposit",
        checkoutUrl: "https://buy.stripe.com/14AdR91ZY13V2eO5lbbEA1X",
        successUrl:
          "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=addon&package=rush_delivery_estate_command_minimum",
      },
    ],
    maintenance: [
      {
        packageSlug: "legacy_snapshot",
        monthly: {
          name: "Legacy Snapshot Maintenance Monthly",
          slug: "legacy_snapshot_monthly",
          priceLabel: "$19/month",
          checkoutUrl: "https://buy.stripe.com/7sYaEXbAy8wnaLk28ZbEA19",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_snapshot_monthly",
        },
        yearly: {
          name: "Legacy Snapshot Maintenance Yearly",
          slug: "legacy_snapshot_yearly",
          priceLabel: "$190/year",
          checkoutUrl: "https://buy.stripe.com/9B65kD8omaEv5r000RbEA1a",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_snapshot_yearly",
        },
      },
      {
        packageSlug: "legacy_portrait_intro",
        monthly: {
          name: "Legacy Portrait Intro Maintenance Monthly",
          slug: "legacy_portrait_intro_monthly",
          priceLabel: "$29/month",
          checkoutUrl: "https://buy.stripe.com/aFadR96ge5kb9Hg00RbEA1b",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_portrait_intro_monthly",
        },
        yearly: {
          name: "Legacy Portrait Intro Maintenance Yearly",
          slug: "legacy_portrait_intro_yearly",
          priceLabel: "$290/year",
          checkoutUrl: "https://buy.stripe.com/14A9AT5ca9ArdXwcNDbEA1c",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_portrait_intro_yearly",
        },
      },
      {
        packageSlug: "digital_legacy_portrait",
        monthly: {
          name: "Digital Legacy Portrait Maintenance Monthly",
          slug: "digital_legacy_portrait_monthly",
          priceLabel: "$39/month",
          checkoutUrl: "https://buy.stripe.com/cNifZh9sq4g7bPocNDbEA1d",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=digital_legacy_portrait_monthly",
        },
        yearly: {
          name: "Digital Legacy Portrait Maintenance Yearly",
          slug: "digital_legacy_portrait_yearly",
          priceLabel: "$390/year",
          checkoutUrl: "https://buy.stripe.com/5kQfZhawuaEv8DceVLbEA1e",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=digital_legacy_portrait_yearly",
        },
      },
      {
        packageSlug: "household_foundation",
        monthly: {
          name: "Household Foundation Maintenance Monthly",
          slug: "household_foundation_monthly",
          priceLabel: "$59/month",
          checkoutUrl: "https://buy.stripe.com/00w7sL7ki7sjf1AbJzbEA1f",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=household_foundation_monthly",
        },
        yearly: {
          name: "Household Foundation Maintenance Yearly",
          slug: "household_foundation_yearly",
          priceLabel: "$590/year",
          checkoutUrl: "https://buy.stripe.com/5kQeVd5ca27Zg5E9BrbEA1g",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=household_foundation_yearly",
        },
      },
      {
        packageSlug: "heirloom_legacy_tree",
        monthly: {
          name: "Heirloom Legacy Tree Maintenance Monthly",
          slug: "heirloom_legacy_tree_monthly",
          priceLabel: "$89/month",
          checkoutUrl: "https://buy.stripe.com/fZubJ11ZYaEv9Hg3d3bEA1h",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=heirloom_legacy_tree_monthly",
        },
        yearly: {
          name: "Heirloom Legacy Tree Maintenance Yearly",
          slug: "heirloom_legacy_tree_yearly",
          priceLabel: "$890/year",
          checkoutUrl: "https://buy.stripe.com/5kQ00jfQOeUL4mW7tjbEA1i",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=heirloom_legacy_tree_yearly",
        },
      },
      {
        packageSlug: "legacy_plus",
        monthly: {
          name: "Legacy Plus Maintenance Monthly",
          slug: "legacy_plus_monthly",
          priceLabel: "$149/month",
          checkoutUrl: "https://buy.stripe.com/dRmdR9dIGfYPaLkcNDbEA1j",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_plus_monthly",
        },
        yearly: {
          name: "Legacy Plus Maintenance Yearly",
          slug: "legacy_plus_yearly",
          priceLabel: "$1,490/year",
          checkoutUrl: "https://buy.stripe.com/7sYaEX1ZYdQH8DcaFvbEA1k",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=legacy_plus_yearly",
        },
      },
      {
        packageSlug: "family_estate_concierge",
        monthly: {
          name: "Family Estate Concierge Maintenance Monthly",
          slug: "family_estate_concierge_monthly",
          priceLabel: "$299/month",
          checkoutUrl: "https://buy.stripe.com/dRm9ATeMK9Arg5E6pfbEA1l",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=family_estate_concierge_monthly",
        },
        yearly: {
          name: "Family Estate Concierge Maintenance Yearly",
          slug: "family_estate_concierge_yearly",
          priceLabel: "$2,990/year",
          checkoutUrl: "https://buy.stripe.com/28E9AT5cabIz06G9BrbEA1m",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=family_estate_concierge_yearly",
        },
      },
      {
        packageSlug: "command_structure_network",
        monthly: {
          name: "Command Structure Network Maintenance Monthly",
          slug: "command_structure_network_monthly",
          priceLabel: "$199/month",
          checkoutUrl: "https://buy.stripe.com/cNidR90VUdQHbPo5lbbEA1n",
          successUrl:
            "/thank-you.html?session_id={CHECKOUT_SESSION_ID}&type=maintenance&package=command_structure_network_monthly",
        },
        yearly: {
          name: "Command Structure Network Maintenance Yearly",
          slug: "command_structure_network_yearly",
          priceLabel: "$1,990/year",
          checkoutUrl: "https://buy.stripe.com/4gM8wP7ki4g7g5E7tjbEA1o",
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
