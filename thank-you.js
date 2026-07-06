(function () {
  "use strict";

  const app = window.TOLApp || window.TOLAuth;
  if (
    !app ||
    typeof app.normalizePackageCode !== "function" ||
    typeof app.resolvePackageLane !== "function"
  ) {
    console.error("thank-you.js requires package helpers from app.js.");
    return;
  }
  const PENDING_CHECKOUT_KEY = "tol_pending_checkout";
  const LIGHT_NEVER_DIES_CAMPAIGN = "LIGHT_NEVER_DIES";
  const PORTRAIT_PACKAGE_CODES = new Set([
    "legacy_snapshot",
    "legacy_portrait_intro",
    "digital_legacy_portrait",
  ]);
  const HOUSEHOLD_PACKAGE_CODES = new Set([
    "household_foundation",
    "heirloom_legacy_tree",
    "legacy_plus",
  ]);
  const NETWORK_PACKAGE_CODES = new Set(["family_estate_concierge"]);
  const ORGANIZATION_PACKAGE_CODES = new Set(["command_structure_network"]);
  const PORTRAIT_FLOW_ADDONS = new Set([
    "extra_upload_pack",
    "extra_storage",
    "extra_storage_10gb_monthly",
    "extra_storage_10gb_yearly",
    "vault_expansion_25gb_monthly",
    "vault_expansion_25gb_yearly",
    "vault_expansion_50gb_monthly",
    "vault_expansion_50gb_yearly",
    "private_vault_export",
    "portrait_polish",
    "tribute_narration",
    "additional_narration_minute",
    "emergency_retrieval_support",
    "family_correction_cycle",
    "document_record_review_pack",
    "nft_lineage_record",
    "additional_nft_copy_mint",
    "nft_metadata_revision",
    "rush_delivery_snapshot_portrait_intro",
    "rush_delivery_digital_legacy_portrait",
  ]);
  const FAMILY_FLOW_EXTRAS = new Set([
    "extra_mapped_person",
    "extra_zoom_layer",
    "on_site_photo_scanning",
    "extra_linked_household",
    "extra_branch",
    "white_glove_archive_support",
    "family_correction_cycle",
    "emergency_retrieval_support",
    "document_record_review_pack",
    "rush_delivery_household_foundation",
    "rush_delivery_heirloom_legacy_tree",
    "rush_delivery_legacy_plus",
  ]);
  const ORGANIZATION_FLOW_EXTRAS = new Set([
    "extra_org_node",
    "extra_org_level",
    "extra_admin_seat",
    "extra_admin_seat_monthly",
    "extra_admin_seat_yearly",
    "command_report_addon",
    "organization_correction_cycle",
    "document_record_review_pack",
    "nft_metadata_revision",
    "rush_delivery_estate_command_minimum",
  ]);

  function getParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function getPendingCheckout() {
    try {
      const raw = localStorage.getItem(PENDING_CHECKOUT_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function normalizeCampaign(value) {
    return String(value || "")
      .trim()
      .toUpperCase();
  }

  function clearPendingCheckout() {
    try {
      localStorage.removeItem(PENDING_CHECKOUT_KEY);
    } catch (_error) {
      // Ignore storage cleanup errors.
    }
  }

  function humanize(value) {
    return String(value || "not_provided")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, function (char) {
        return char.toUpperCase();
      });
  }

  function normalizePackageCode(packageCode) {
    return app.normalizePackageCode(packageCode);
  }

  function inferType(type, packageCode) {
    const normalizedType = String(type || "")
      .trim()
      .toLowerCase();
    const normalizedPackage = normalizePackageCode(packageCode);

    if (
      normalizedType === "maintenance" ||
      normalizedType === "addon" ||
      normalizedType === "extra"
    ) {
      return normalizedType;
    }

    if (
      normalizedPackage.endsWith("_monthly") ||
      normalizedPackage.endsWith("_yearly")
    ) {
      return "maintenance";
    }

    if (
      PORTRAIT_FLOW_ADDONS.has(normalizedPackage) ||
      normalizedPackage === "command_report_addon"
    ) {
      return "addon";
    }

    if (
      FAMILY_FLOW_EXTRAS.has(normalizedPackage) ||
      ORGANIZATION_FLOW_EXTRAS.has(normalizedPackage)
    ) {
      return "extra";
    }

    return "package";
  }

  function basePackageCode(packageCode) {
    const normalizedPackage = normalizePackageCode(packageCode);

    if (normalizedPackage.endsWith("_maintenance_monthly")) {
      return normalizedPackage.slice(
        0,
        normalizedPackage.length - "_maintenance_monthly".length,
      );
    }

    if (normalizedPackage.endsWith("_maintenance_yearly")) {
      return normalizedPackage.slice(
        0,
        normalizedPackage.length - "_maintenance_yearly".length,
      );
    }

    if (normalizedPackage.endsWith("_monthly")) {
      return normalizedPackage.slice(0, normalizedPackage.length - "_monthly".length);
    }

    if (normalizedPackage.endsWith("_yearly")) {
      return normalizedPackage.slice(0, normalizedPackage.length - "_yearly".length);
    }

    return normalizedPackage;
  }

  function packageLane(packageCode) {
    const normalizedBase = basePackageCode(packageCode);
    const resolvedLane = app.resolvePackageLane(normalizedBase);
    if (resolvedLane && resolvedLane !== "unknown") {
      return resolvedLane;
    }

    if (PORTRAIT_PACKAGE_CODES.has(normalizedBase)) return "portrait";
    if (HOUSEHOLD_PACKAGE_CODES.has(normalizedBase)) return "household";
    if (NETWORK_PACKAGE_CODES.has(normalizedBase)) return "network";
    if (ORGANIZATION_PACKAGE_CODES.has(normalizedBase)) return "organization";
    if (PORTRAIT_FLOW_ADDONS.has(normalizedBase)) return "portrait";
    if (FAMILY_FLOW_EXTRAS.has(normalizedBase)) return "household";
    if (ORGANIZATION_FLOW_EXTRAS.has(normalizedBase)) return "organization";
    return "general";
  }

  function nextStepMessage(type, packageCode) {
    const normalizedType = inferType(type, packageCode);
    const lane = packageLane(packageCode);

    if (normalizedType === "maintenance") {
      return "Your maintenance subscription selection was received. Return to your dashboard for account access and package status.";
    }

    if (normalizedType === "addon" || normalizedType === "extra") {
      if (lane === "organization") {
        return "Your organization add-on purchase was received. It will be applied to the correct command structure workspace after payment confirmation.";
      }

      if (lane === "household" || lane === "network") {
        return "Your family build add-on purchase was received. It will be applied to the correct household or network workspace after payment confirmation.";
      }

      return "Your add-on purchase was received. It will be applied to the correct Tomb of Light project or package workflow.";
    }

    if (lane === "portrait") {
      return "Your portrait package purchase was received. Continue to your dashboard and upload your portrait and supporting records.";
    }

    if (lane === "household") {
      return "Your household or family package purchase was received. Continue to your dashboard to begin or continue your family build.";
    }

    if (lane === "network") {
      return "Your network package purchase was received. Continue to your dashboard to begin or continue your family estate build.";
    }

    if (lane === "organization") {
      return "Your organizational package purchase was received. Continue to your dashboard to begin your command or leadership structure build.";
    }

    return "Your payment was received successfully. Continue to your dashboard for the next step.";
  }

  function actionConfig(type, packageCode) {
    const normalizedType = inferType(type, packageCode);
    const lane = packageLane(packageCode);

    const primary = {
      href: "dashboard.html",
      label: "Go to Dashboard",
    };

    if (normalizedType === "maintenance") {
      return {
        primary,
        secondary: {
          href: "billing.html",
          label: "Open Billing",
        },
      };
    }

    if (lane === "portrait") {
      return {
        primary,
        secondary: {
          href: "verification-upload.html",
          label: "Upload Records",
        },
      };
    }

    if (lane === "household" || lane === "network") {
      return {
        primary,
        secondary: {
          href: "tree-view.html",
          label: normalizedType === "package" ? "Open Family Tree" : "Open Family Build",
        },
      };
    }

    if (lane === "organization") {
      return {
        primary,
        secondary: {
          href: "dashboard.html",
          label: "Open Workspace",
        },
      };
    }

    return {
      primary,
      secondary: {
        href: "dashboard.html",
        label: "Open Workspace",
      },
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    const sessionNode = document.querySelector("[data-thank-you-session-id]");
    const typeNode = document.querySelector("[data-thank-you-type]");
    const packageNode = document.querySelector("[data-thank-you-package-code]");
    const nextStepNode = document.querySelector("[data-thank-you-next-step]");
    const primaryAction = document.querySelector("[data-thank-you-primary-action]");
    const secondaryAction = document.querySelector("[data-thank-you-secondary-action]");
    const pendingCheckout = getPendingCheckout();

    const sessionId = getParam("session_id");
    const packageCode = getParam("package") || (pendingCheckout && pendingCheckout.packageCode) || "";
    const campaign = normalizeCampaign(
      getParam("campaign") ||
        (pendingCheckout && pendingCheckout.campaign) ||
        (app.getActiveCampaignCode ? app.getActiveCampaignCode() : ""),
    );
    const type =
      getParam("type") ||
      (pendingCheckout && pendingCheckout.purchaseType) ||
      inferType("", packageCode);
    const normalizedType = inferType(type, packageCode);
    const actions = actionConfig(type, packageCode);
    const normalizedPackageCode = normalizePackageCode(packageCode);
    const basePackage = basePackageCode(normalizedPackageCode);
    const isFounderCampaign = normalizeCampaign(campaign) === LIGHT_NEVER_DIES_CAMPAIGN;
    const paymentLinks = (window.TOL_CONFIG && window.TOL_CONFIG.PAYMENT_LINKS) || {};
    const requiredMonthlyMaintenanceSlug = `${basePackage}_maintenance_monthly`;
    const requiredMonthlyMaintenanceUrl = paymentLinks[requiredMonthlyMaintenanceSlug] || "";

    if (sessionNode) {
      sessionNode.textContent = sessionId || "Not provided";
    }

    if (typeNode) {
      typeNode.textContent = humanize(type);
    }

    if (packageNode) {
      packageNode.textContent = packageCode ? humanize(packageCode) : "Not provided";
    }

    if (nextStepNode) {
      nextStepNode.textContent = nextStepMessage(type, packageCode);
    }

    if (isFounderCampaign && normalizedType === "package") {
      if (
        app &&
        typeof app.setFounderMaintenancePending === "function" &&
        basePackage
      ) {
        app.setFounderMaintenancePending({
          campaign: LIGHT_NEVER_DIES_CAMPAIGN,
          packageCode: basePackage,
          requiredBillingInterval: "monthly",
          createdAt: new Date().toISOString(),
        });
      }
      if (nextStepNode) {
        nextStepNode.textContent =
          "Your founder package payment was received. Monthly maintenance setup is required now to keep your Tomb of Light continuity active.";
      }
      const checkoutUrl =
        requiredMonthlyMaintenanceUrl &&
        app &&
        typeof app.buildCheckoutLinkWithContext === "function"
          ? app.buildCheckoutLinkWithContext(requiredMonthlyMaintenanceUrl, {
              slug: requiredMonthlyMaintenanceSlug,
              purchaseType: "maintenance",
              campaign: LIGHT_NEVER_DIES_CAMPAIGN,
            })
          : requiredMonthlyMaintenanceUrl;
      if (primaryAction) {
        if (checkoutUrl) {
          primaryAction.setAttribute("href", checkoutUrl);
          primaryAction.setAttribute("target", "_blank");
          primaryAction.setAttribute("rel", "noopener noreferrer");
          primaryAction.textContent = "Start Required Monthly Maintenance";
        } else {
          primaryAction.setAttribute("href", "billing.html");
          primaryAction.textContent = "Open Billing";
        }
      }
      if (secondaryAction) {
        secondaryAction.setAttribute("href", "billing.html");
        secondaryAction.textContent = "Open Billing";
      }
    } else {
      if (primaryAction) {
        primaryAction.setAttribute("href", actions.primary.href);
        primaryAction.textContent = actions.primary.label;
      }

      if (secondaryAction) {
        secondaryAction.setAttribute("href", actions.secondary.href);
        secondaryAction.textContent = actions.secondary.label;
      }
    }

    if (isFounderCampaign && normalizedType === "maintenance") {
      if (app && typeof app.clearFounderMaintenancePending === "function") {
        app.clearFounderMaintenancePending();
      }
    }

    if (packageCode) {
      clearPendingCheckout();
    }
  });
})();
