(function () {
  "use strict";

  const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

  const DEFAULT_LOCAL_API_BASE_URLS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://[::1]:8000",
  ];
  const DEFAULT_LIVE_API_BASE_URL = "https://tomboflight-api.onrender.com";
  const DEFAULT_LIVE_API_BASE_URLS = [
    DEFAULT_LIVE_API_BASE_URL,
    "https://api.tomboflight.com",
  ];

  const TOKEN_KEY = "tol_access_token";
  const USER_KEY = "tol_user";
  const COOKIE_CHOICE_KEY = "tol_cookie_choice";
  const ADMIN_APPEARANCE_DEFAULT_KEY = "tol_admin_appearance_default";
  const ADMIN_APPEARANCE_BY_USER_KEY = "tol_admin_appearance_by_user";
  const PENDING_CHECKOUT_KEY = "tol_pending_checkout";
  const FOUNDER_MAINTENANCE_PENDING_KEY = "tol_founder_maintenance_pending";
  const LIGHT_NEVER_DIES_CAMPAIGN = "LIGHT_NEVER_DIES";
  const API_BASE_URL_STORAGE_KEY = "tol_api_base_url";
  const API_REQUEST_TIMEOUT_MS = 15000;

  const ADDON_OR_EXTRA_SLUGS = new Set([
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
    "rush_delivery",
    "rush_delivery_snapshot_portrait_intro",
    "rush_delivery_digital_legacy_portrait",
    "rush_delivery_household_foundation",
    "rush_delivery_heirloom_legacy_tree",
    "rush_delivery_legacy_plus",
    "rush_delivery_estate_command_minimum",
    "extra_mapped_person",
    "extra_zoom_layer",
    "additional_narration_minute",
    "on_site_photo_scanning",
    "extra_linked_household",
    "extra_branch",
    "white_glove_archive_support",
    "extra_org_node",
    "extra_org_level",
    "extra_admin_seat",
    "extra_admin_seat_monthly",
    "extra_admin_seat_yearly",
    "command_report_addon",
    "emergency_retrieval_support",
    "family_correction_cycle",
    "organization_correction_cycle",
    "document_record_review_pack",
    "nft_lineage_record",
    "additional_nft_copy_mint",
    "nft_metadata_revision",
  ]);

  const PACKAGE_CODE_ALIASES = {
    "legacy-snapshot": "legacy_snapshot",
    legacy_snapshot: "legacy_snapshot",
    "legacy snapshot": "legacy_snapshot",
    "legacy-portrait-intro": "legacy_portrait_intro",
    legacy_portrait_intro: "legacy_portrait_intro",
    "legacy portrait intro": "legacy_portrait_intro",
    "digital-legacy-portrait": "digital_legacy_portrait",
    digital_legacy_portrait: "digital_legacy_portrait",
    "digital legacy portrait": "digital_legacy_portrait",
    "starter-family-tree": "household_foundation",
    starter_family_tree: "household_foundation",
    "starter family tree": "household_foundation",
    "household-foundation": "household_foundation",
    household_foundation: "household_foundation",
    "household foundation": "household_foundation",
    "heirloom-legacy-tree": "heirloom_legacy_tree",
    heirloom_legacy_tree: "heirloom_legacy_tree",
    "heirloom legacy tree": "heirloom_legacy_tree",
    "legacy-plus": "legacy_plus",
    legacy_plus: "legacy_plus",
    "legacy plus": "legacy_plus",
    "family-estate-concierge": "family_estate_concierge",
    family_estate_concierge: "family_estate_concierge",
    "family estate concierge": "family_estate_concierge",
    "command-structure-network": "command_structure_network",
    command_structure_network: "command_structure_network",
    "command structure network": "command_structure_network",
  };

  const PACKAGE_PROFILES = {
    legacy_snapshot: {
      display_name: "Legacy Snapshot",
      package_lane: "portrait",
      can_use_household_vault: false,
      can_use_future_message_vault: false,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: false,
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: false,
      can_use_secure_share_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: false,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
    legacy_portrait_intro: {
      display_name: "Legacy Portrait Intro",
      package_lane: "portrait",
      can_use_household_vault: false,
      can_use_future_message_vault: false,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: false,
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: false,
      can_use_secure_share_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: false,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
    digital_legacy_portrait: {
      display_name: "Digital Legacy Portrait",
      package_lane: "portrait",
      can_use_household_vault: true,
      can_use_future_message_vault: false,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: false,
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    household_foundation: {
      display_name: "Household Foundation",
      package_lane: "household",
      can_use_household_vault: true,
      can_use_future_message_vault: false,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: false,
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
    heirloom_legacy_tree: {
      display_name: "Heirloom Legacy Tree",
      package_lane: "household",
      can_use_household_vault: true,
      can_use_future_message_vault: true,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: true,
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      narration_ready_structure: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: false,
      can_manage_link_keys: false,
    },
    legacy_plus: {
      display_name: "Legacy Plus",
      package_lane: "household",
      can_use_household_vault: true,
      can_use_future_message_vault: true,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: true,
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: false,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: true,
      narration_ready_structure: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
    },
    family_estate_concierge: {
      display_name: "Family Estate Concierge",
      package_lane: "network",
      can_use_household_vault: true,
      can_use_future_message_vault: true,
      can_use_linked_household_vault: true,
      can_use_organization_records_vault: false,
      can_use_scheduled_reveal: true,
      can_build_household: true,
      can_build_family_tree: true,
      can_build_org_chart: false,
      can_link_households: true,
      can_link_org_units: false,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
      can_open_org_intake: false,
      can_use_link_keys: true,
      can_manage_link_keys: true,
      protected_workspace: true,
      guided_intake: true,
      premium_consultation_path: true,
      custom_structure_planning: true,
      white_glove_project_handling: true,
      linked_household_structure: true,
      network_branch_scope: true,
      max_family_branches: 3,
      high_capacity_archival_support: true,
      continuity_stewardship_options: true,
      lineage_experience_support: true,
      organization_command_scope: false,
      maintenance_included: false,
    },
    command_structure_network: {
      display_name: "Command Structure Network",
      package_lane: "organization",
      can_use_household_vault: false,
      can_use_future_message_vault: false,
      can_use_linked_household_vault: false,
      can_use_organization_records_vault: true,
      can_use_scheduled_reveal: false,
      can_build_household: false,
      can_build_family_tree: false,
      can_build_org_chart: true,
      can_link_households: false,
      can_link_org_units: true,
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_use_viewer: true,
      can_use_narration: false,
      can_use_lineage_certificate: false,
      can_open_family_intake: false,
      can_open_org_intake: true,
      can_use_link_keys: false,
      can_manage_link_keys: false,
      protected_workspace: true,
      guided_intake: true,
      command_role_mapping_tools: true,
      structured_organization_lineage: true,
      verification_support_record_workflows: true,
      organization_nodes_enabled: true,
      organization_node_limit: 15,
      max_org_nodes: 15,
      max_uploads: 25,
      leadership_structure_viewer: true,
      linked_organization_support: true,
      command_officer_continuity: true,
      admin_seat_expansion_paths: true,
      family_household_scope: false,
      family_branch_network_scope: false,
      organization_command_scope: true,
      maintenance_included: false,
    },
  };

  function normalizePackageCode(packageCode) {
    const normalized = String(packageCode || "")
      .trim()
      .toLowerCase();
    return PACKAGE_CODE_ALIASES[normalized] || normalized;
  }

  function stripMaintenanceSuffix(packageCode) {
    return normalizePackageCode(packageCode)
      .replace(/_maintenance_monthly$/, "")
      .replace(/_maintenance_yearly$/, "");
  }

  function getPackageProfile(packageCode) {
    const normalized = stripMaintenanceSuffix(packageCode);
    const profile = PACKAGE_PROFILES[normalized];
    return profile ? Object.assign({ package_code: normalized }, profile) : null;
  }

  function resolvePackageLane(packageCode) {
    const profile = getPackageProfile(packageCode);
    return profile && profile.package_lane ? profile.package_lane : "unknown";
  }

  function resolvePackageDisplayName(packageCode) {
    const profile = getPackageProfile(packageCode);
    if (profile && profile.display_name) return profile.display_name;
    const normalized = stripMaintenanceSuffix(packageCode);
    return normalized
      ? normalized.replaceAll("_", " ").replace(/\b\w/g, function (char) {
          return char.toUpperCase();
        })
      : "Package";
  }

  function packageSupportsLinkKeys(packageCode) {
    const profile = getPackageProfile(packageCode);
    return Boolean(profile && profile.can_use_link_keys);
  }

  // Canonical set of internal-role values shared across all modules.
  // Any module needing role gating should call app.isInternalRole() rather
  // than maintaining its own copy of this set.
  const INTERNAL_ROLE_KEYS = new Set([
    "super_admin",
    "ceo_master_admin",
    "executive_tech_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
  ]);

  const INTERNAL_ROLE_ALIASES = {
    superadmin: "super_admin",
    root_admin: "super_admin",
    platform_admin: "super_admin",
    ceo_super_admin: "ceo_master_admin",
    "ceo-super-admin": "ceo_master_admin",
    ceo_master_admin: "ceo_master_admin",
    "ceo-master-admin": "ceo_master_admin",
    ceo_admin: "ceo_master_admin",
    ceo: "ceo_master_admin",
    executive_technology: "executive_tech_admin",
    executive_tech_admin: "executive_tech_admin",
    "executive-tech-admin": "executive_tech_admin",
    cto_admin: "executive_tech_admin",
    cfo_admin: "finance_admin",
    cmo_admin: "marketing_admin",
    coo_admin: "operations_admin",
    operations: "operations_admin",
    finance: "finance_admin",
    marketing: "marketing_admin",
  };

  function isInternalRole(user) {
    if (!user || typeof user !== "object") return false;
    const roleCodes = Array.isArray(user.role_codes) ? user.role_codes : [];
    return [
      String(user.role || "").trim().toLowerCase(),
      String(user.access_tier || "").trim().toLowerCase(),
      String(user.department_role || "").trim().toLowerCase(),
      ...roleCodes.map(function (value) {
        return String(value || "").trim().toLowerCase();
      }),
    ].some(function (v) {
      const normalized = INTERNAL_ROLE_ALIASES[v] || v;
      return normalized && INTERNAL_ROLE_KEYS.has(normalized);
    });
  }

  function isLocalApp() {
    return LOCAL_HOSTS.has(window.location.hostname);
  }

  function uniqueNonEmptyValues(values) {
    return Array.from(
      new Set(
        (Array.isArray(values) ? values : [])
          .map(function (value) {
            return typeof value === "string" ? value.trim().replace(/\/+$/, "") : "";
          })
          .filter(Boolean),
      ),
    );
  }

  function isLikelyApiBaseUrl(value) {
    try {
      const parsed = new URL(String(value || "").trim());
      return parsed.protocol === "https:" || parsed.protocol === "http:";
    } catch (_error) {
      return false;
    }
  }

  function isFrontendOriginBaseUrl(value) {
    try {
      const parsed = new URL(String(value || "").trim());
      return parsed.origin === window.location.origin;
    } catch (_error) {
      return false;
    }
  }

  function getConfiguredApiBaseUrls() {
    const configuredList =
      window.TOL_CONFIG && Array.isArray(window.TOL_CONFIG.API_BASE_URLS)
        ? window.TOL_CONFIG.API_BASE_URLS
        : [];
    const configuredSingle =
      window.TOL_CONFIG && typeof window.TOL_CONFIG.API_BASE_URL === "string"
        ? window.TOL_CONFIG.API_BASE_URL
        : "";

    const configured = uniqueNonEmptyValues([
      configuredSingle,
      ...configuredList,
    ]).filter(function (candidate) {
      return isLikelyApiBaseUrl(candidate);
    });
    const backendApiBaseUrls = configured.filter(function (candidate) {
      return !isFrontendOriginBaseUrl(candidate);
    });
    if (backendApiBaseUrls.length) {
      if (isLocalApp()) {
        return backendApiBaseUrls;
      }
      return uniqueNonEmptyValues([
        ...backendApiBaseUrls,
        ...DEFAULT_LIVE_API_BASE_URLS,
      ]);
    }

    if (isLocalApp()) {
      const localHost = String(window.location.hostname || "").toLowerCase();
      const preferredLocalApiBaseUrl =
        localHost === "localhost"
          ? "http://localhost:8000"
          : localHost === "::1" || localHost === "[::1]"
          ? "http://[::1]:8000"
          : "http://127.0.0.1:8000";
      return uniqueNonEmptyValues([
        preferredLocalApiBaseUrl,
        ...DEFAULT_LOCAL_API_BASE_URLS,
      ]);
    }

    return DEFAULT_LIVE_API_BASE_URLS.slice();
  }

  function getSavedApiBaseUrl() {
    try {
      const value = sessionStorage.getItem(API_BASE_URL_STORAGE_KEY);
      return typeof value === "string" ? value.trim().replace(/\/+$/, "") : "";
    } catch (_error) {
      return "";
    }
  }

  function saveApiBaseUrl(value) {
    try {
      if (typeof value === "string" && value.trim()) {
        sessionStorage.setItem(
          API_BASE_URL_STORAGE_KEY,
          value.trim().replace(/\/+$/, ""),
        );
      }
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  function getApiBaseUrls() {
    const configured = getConfiguredApiBaseUrls();
    const saved = getSavedApiBaseUrl();
    if (saved && configured[0] === saved) {
      return [saved].concat(
        configured.filter(function (item) {
          return item !== saved;
        }),
      );
    }
    return configured;
  }

  function getApiBaseUrl() {
    const configured = getApiBaseUrls();
    const saved = getSavedApiBaseUrl();
    if (saved && configured[0] === saved) {
      return saved;
    }
    return configured[0] || "";
  }

  async function discoverApiBaseUrl(candidates) {
    const urls = uniqueNonEmptyValues(candidates);
    const failures = [];
    for (const apiBaseUrl of urls) {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          method: "GET",
          headers: { Accept: "application/json" },
          credentials: "include",
        });
        if (response && response.ok) {
          saveApiBaseUrl(apiBaseUrl);
          return apiBaseUrl;
        }
        failures.push(`${apiBaseUrl} returned ${response.status}`);
      } catch (_error) {
        failures.push(`${apiBaseUrl} could not be reached`);
      }
    }

    if (failures.length) {
      console.warn("Tomb of Light API discovery failed:", failures.join("; "));
    }

    return urls[0] || "";
  }

  function buildNetworkErrorMessage(apiBaseUrls) {
    if (!isLocalApp()) {
      return "Service temporarily unavailable. Please try again in a few minutes.";
    }

    const candidates = uniqueNonEmptyValues(apiBaseUrls);
    const details = [
      "Network error calling API.",
      "",
      `API base candidates: ${candidates.join(", ") || "none configured"}`,
      `Page origin: ${window.location.origin}`,
      "",
      "Local frontend should usually run on http://127.0.0.1:5500",
      "Local backend should usually run on http://127.0.0.1:8000",
    ];

    return details.join("\n");
  }

  function getPaymentLinks() {
    return (window.TOL_CONFIG && window.TOL_CONFIG.PAYMENT_LINKS) || {};
  }

  function getActiveCampaignCode() {
    try {
      const params = new URLSearchParams(window.location.search);
      const campaign =
        params.get("campaign") ||
        params.get("utm_campaign") ||
        params.get("source_campaign") ||
        "";
      return String(campaign || "").trim().toUpperCase();
    } catch (_error) {
      return "";
    }
  }

  function isLightNeverDiesCampaign(value) {
    return String(value || "").trim().toUpperCase() === LIGHT_NEVER_DIES_CAMPAIGN;
  }

  function sanitizeMaintenanceCheckoutUrl(url) {
    const normalized = String(url || "").trim();
    if (!normalized) return "";
    try {
      const parsed = new URL(normalized, window.location.origin);
      [
        "prefilled_promo_code",
        "promo_code",
        "promotion_code",
        "coupon",
        "discount_code",
      ].forEach(function (key) {
        parsed.searchParams.delete(key);
      });
      return parsed.toString();
    } catch (_error) {
      return normalized;
    }
  }

  function getSavedUserProjectId(user) {
    const source = user && typeof user === "object" ? user : getSavedUser() || {};
    return String(
      source.active_project_id ||
        source.activeProjectId ||
        source.project_id ||
        source.projectId ||
        "",
    ).trim();
  }

  function inferBillingInterval(purchaseType, slug) {
    const type = String(purchaseType || "").trim().toLowerCase();
    const normalizedSlug = String(slug || "").trim().toLowerCase();
    if (type === "maintenance") {
      if (normalizedSlug.endsWith("_yearly")) return "yearly";
      return "monthly";
    }
    return "one_time";
  }

  function buildCheckoutClientReference(payload) {
    const input = payload && typeof payload === "object" ? payload : {};
    const params = new URLSearchParams();
    const packageCode = stripMaintenanceSuffix(input.packageCode || input.slug || "");
    params.set("v", "1");
    if (input.userId) params.set("u", String(input.userId).trim());
    if (input.projectId) params.set("p", String(input.projectId).trim());
    if (packageCode) params.set("k", packageCode);
    if (input.itemType) params.set("t", String(input.itemType).trim().toLowerCase());
    if (input.billingInterval) {
      params.set("b", String(input.billingInterval).trim().toLowerCase());
    }
    if (input.campaign) params.set("c", String(input.campaign).trim().toUpperCase());
    return `tol:${params.toString()}`;
  }

  function buildCheckoutLinkWithContext(url, options = {}) {
    const normalizedUrl = String(url || "").trim();
    if (!normalizedUrl) return "";
    const user = getSavedUser() || {};
    const slug = String(options.slug || "").trim().toLowerCase();
    const purchaseType =
      String(options.purchaseType || inferPurchaseTypeFromSlug(slug))
        .trim()
        .toLowerCase() || "package";
    const campaign = String(options.campaign || "").trim().toUpperCase();
    const promoCode = String(options.promoCode || "").trim();
    const userId = String(user.id || user._id || user.user_id || "").trim();
    const projectId = String(options.projectId || getSavedUserProjectId(user)).trim();
    const email = String(user.email || "").trim().toLowerCase();
    const billingInterval = inferBillingInterval(purchaseType, slug);
    const contextReference = buildCheckoutClientReference({
      userId,
      projectId,
      packageCode: slug,
      itemType: purchaseType,
      billingInterval,
      campaign,
    });
    try {
      const parsed = new URL(normalizedUrl, window.location.origin);
      parsed.searchParams.set("client_reference_id", contextReference);
      if (email) {
        parsed.searchParams.set("prefilled_email", email);
      }
      if (purchaseType !== "maintenance" && promoCode) {
        parsed.searchParams.set("prefilled_promo_code", promoCode);
      }
      if (purchaseType === "maintenance") {
        return sanitizeMaintenanceCheckoutUrl(parsed.toString());
      }
      return parsed.toString();
    } catch (_error) {
      return purchaseType === "maintenance"
        ? sanitizeMaintenanceCheckoutUrl(normalizedUrl)
        : normalizedUrl;
    }
  }

  function configureDirectStripeCheckout(link, href) {
    const normalizedHref = String(href || "").trim();
    if (!/^https:\/\/buy\.stripe\.com\//i.test(normalizedHref)) {
      return false;
    }
    link.href = normalizedHref;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.dataset.directStripeCheckout = "true";
    return true;
  }

  function getFounderMaintenancePending() {
    try {
      const raw = localStorage.getItem(FOUNDER_MAINTENANCE_PENDING_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function setFounderMaintenancePending(payload) {
    try {
      localStorage.setItem(
        FOUNDER_MAINTENANCE_PENDING_KEY,
        JSON.stringify(payload || {}),
      );
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  function clearFounderMaintenancePending() {
    try {
      localStorage.removeItem(FOUNDER_MAINTENANCE_PENDING_KEY);
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  function enforceFounderMaintenanceGate() {
    const pending = getFounderMaintenancePending();
    if (!pending || !isLightNeverDiesCampaign(pending.campaign)) return;
    const currentPage =
      String(window.location.pathname || "").split("/").pop() || "index.html";
    if (
      [
        "billing.html",
        "thank-you.html",
        "signin.html",
        "signup.html",
        "index.html",
      ].includes(currentPage)
    ) {
      return;
    }
    const packageCode = stripMaintenanceSuffix(pending.packageCode || "");
    const params = new URLSearchParams();
    params.set("maintenance_required", "1");
    if (packageCode) params.set("package", packageCode);
    params.set("campaign", LIGHT_NEVER_DIES_CAMPAIGN);
    window.location.replace(`billing.html?${params.toString()}`);
  }

  function inferPurchaseTypeFromSlug(slug) {
    const normalizedSlug = String(slug || "")
      .trim()
      .toLowerCase();

    if (!normalizedSlug) return "package";

    if (
      normalizedSlug.endsWith("_maintenance_monthly") ||
      normalizedSlug.endsWith("_maintenance_yearly")
    ) {
      return "maintenance";
    }

    if (ADDON_OR_EXTRA_SLUGS.has(normalizedSlug)) {
      if (
        normalizedSlug.startsWith("extra_") ||
        normalizedSlug === "white_glove_archive_support"
      ) {
        return "extra";
      }
      return "addon";
    }

    return "package";
  }

  function savePendingCheckout(payload) {
    try {
      localStorage.setItem(PENDING_CHECKOUT_KEY, JSON.stringify(payload || {}));
    } catch (_error) {
      // Ignore storage errors for checkout convenience.
    }
  }

  function saveToken(token) {
    if (typeof token === "string" && token.trim()) {
      localStorage.setItem(TOKEN_KEY, token);
    }
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function saveUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user || {}));
  }

  function getSavedUser() {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function clearUser() {
    localStorage.removeItem(USER_KEY);
  }

  function clearSession() {
    clearToken();
    clearUser();
  }

  function isMeaningfulMessage(value) {
    const text = String(value || "").trim();
    if (!text) return false;
    if (/^\[object Object\](,\s*\[object Object\])*$/i.test(text)) {
      return false;
    }
    return true;
  }

  function normalizeMessage(value) {
    const text = String(value || "").trim();
    return isMeaningfulMessage(text) ? text : "";
  }

  function validationLocationLabel(location) {
    if (!Array.isArray(location)) return "";
    const scopeKeys = new Set(["body", "query", "path", "header", "cookie"]);
    return location
      .map(function (part) {
        return String(part || "").trim();
      })
      .filter(Boolean)
      .filter(function (part) {
        return !scopeKeys.has(part.toLowerCase());
      })
      .join(".");
  }

  function dedupeMessages(messages) {
    const seen = new Set();
    const result = [];
    (messages || []).forEach(function (message) {
      const normalized = normalizeMessage(message);
      if (!normalized) return;
      const key = normalized.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      result.push(normalized);
    });
    return result;
  }

  function collectErrorMessages(value, seen) {
    const visited = seen || new Set();
    if (value === null || typeof value === "undefined") return [];

    if (
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      return normalizeMessage(value) ? [normalizeMessage(value)] : [];
    }

    if (value instanceof Error) {
      return dedupeMessages(
        []
          .concat(collectErrorMessages(value.message, visited))
          .concat(collectErrorMessages(value.detail, visited))
          .concat(collectErrorMessages(value.error, visited))
          .concat(collectErrorMessages(value.responseBody, visited))
          .concat(collectErrorMessages(value.data, visited))
          .concat(collectErrorMessages(value.cause, visited)),
      );
    }

    if (Array.isArray(value)) {
      return dedupeMessages(
        value.flatMap(function (item) {
          return collectErrorMessages(item, visited);
        }),
      );
    }

    if (typeof value === "object") {
      if (visited.has(value)) return [];
      visited.add(value);

      const messages = [];
      const candidateMessage = normalizeMessage(
        value.message ||
          value.error ||
          value.reason ||
          value.description ||
          value.title ||
          value.detail ||
          value.msg,
      );
      const location = validationLocationLabel(value.loc);
      if (candidateMessage) {
        messages.push(location ? `${location}: ${candidateMessage}` : candidateMessage);
      }

      ["detail", "message", "error", "errors"].forEach(function (key) {
        if (!Object.prototype.hasOwnProperty.call(value, key)) return;
        messages.push(...collectErrorMessages(value[key], visited));
      });

      Object.entries(value).forEach(function ([key, nestedValue]) {
        if (
          [
            "detail",
            "message",
            "error",
            "errors",
            "msg",
            "loc",
            "ctx",
            "type",
            "input",
            "reason",
            "description",
            "title",
          ].includes(key)
        ) {
          return;
        }
        const nestedMessages = collectErrorMessages(nestedValue, visited);
        nestedMessages.forEach(function (nestedMessage) {
          const normalizedNested = normalizeMessage(nestedMessage);
          if (!normalizedNested) return;
          if (normalizedNested.toLowerCase().startsWith(`${key.toLowerCase()}:`)) {
            messages.push(normalizedNested);
          } else {
            messages.push(`${key}: ${normalizedNested}`);
          }
        });
      });

      return dedupeMessages(messages);
    }

    return normalizeMessage(value) ? [normalizeMessage(value)] : [];
  }

  function getReadableErrorMessage(value, fallback = "") {
    const messages = dedupeMessages(collectErrorMessages(value));
    if (messages.length) {
      return messages.join(" ");
    }
    return normalizeMessage(fallback);
  }

  function parseApiError(data, response) {
    return getReadableErrorMessage(
      data,
      `Request failed with status ${response.status}`,
    );
  }

  async function apiRequest(path, options = {}) {
    const configuredApiBaseUrls = getApiBaseUrls();
    const savedApiBaseUrl = getSavedApiBaseUrl();
    const token = getToken();

    const headers = {
      Accept: "application/json",
      ...(options.headers || {}),
    };

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (token && !headers.Authorization) {
      headers.Authorization = `Bearer ${token}`;
    }

    const preferredApiBaseUrl =
      savedApiBaseUrl && configuredApiBaseUrls[0] === savedApiBaseUrl
        ? savedApiBaseUrl
        : configuredApiBaseUrls.length > 1
        ? await discoverApiBaseUrl(configuredApiBaseUrls)
        : configuredApiBaseUrls[0] || "";
    const apiBaseUrls = uniqueNonEmptyValues([
      preferredApiBaseUrl,
      ...configuredApiBaseUrls,
    ]);

    let response = null;
    let lastNetworkError = null;
    let lastRequestUrl = "";

    for (let index = 0; index < apiBaseUrls.length; index += 1) {
      const apiBaseUrl = apiBaseUrls[index];
      const hasFallbackCandidate = index < apiBaseUrls.length - 1;
      let timeoutId = null;
      let signalHandler = null;
      try {
        const requestOptions = {
          ...options,
          headers,
          credentials: "include",
        };

        if (typeof AbortController === "function") {
          const controller = new AbortController();
          requestOptions.signal = controller.signal;

          timeoutId = window.setTimeout(function () {
            controller.abort();
          }, API_REQUEST_TIMEOUT_MS);

          if (options.signal) {
            if (options.signal.aborted) {
              controller.abort();
            } else {
              signalHandler = function () {
                controller.abort();
              };
              options.signal.addEventListener("abort", signalHandler, {
                once: true,
              });
            }
          }
        }

        const requestUrl = `${apiBaseUrl}${path}`;
        lastRequestUrl = requestUrl;
        response = await fetch(requestUrl, requestOptions);
        const normalizedPath = String(path || "");
        const shouldRetry404Fallback =
          normalizedPath.startsWith("/workspace-access/") ||
          normalizedPath.startsWith("/workspace_access/") ||
          normalizedPath.startsWith("/household-access/") ||
          normalizedPath.startsWith("/admin/control-center/");
        // Some deployments can expose mixed-version backends behind different
        // API domains where `/health` passes but specific routes lag behind.
        // For these known cross-host-sensitive routes, retry 404s against the
        // next configured API base URL before surfacing an error.
        if (
          response &&
          response.status === 404 &&
          hasFallbackCandidate &&
          shouldRetry404Fallback
        ) {
          console.warn("Tomb of Light API fallback retry after 404.", {
            requestPath: normalizedPath,
            failedApiBaseUrl: apiBaseUrl,
          });
          continue;
        }
        saveApiBaseUrl(apiBaseUrl);
        break;
      } catch (networkError) {
        if (
          networkError &&
          networkError.name === "AbortError" &&
          !response
        ) {
          lastNetworkError = new Error(
            "Request timed out. Please try again in a moment.",
          );
        } else {
          lastNetworkError = networkError;
        }
      } finally {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
        if (options.signal && signalHandler) {
          options.signal.removeEventListener("abort", signalHandler);
        }
      }
    }

    if (!response) {
      const error = new Error(buildNetworkErrorMessage(apiBaseUrls));
      error.status = 0;
      error.apiBaseUrls = apiBaseUrls;
      error.requestUrl = lastRequestUrl;
      if (lastNetworkError) {
        error.cause = lastNetworkError;
      }
      throw error;
    }

    const contentType = response.headers.get("content-type") || "";
    let data = null;

    try {
      if (contentType.includes("application/json")) {
        data = await response.json();
      } else {
        const text = await response.text();
        data = text ? { detail: text } : null;
      }
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      const error = new Error(parseApiError(data, response));
      error.status = response.status;
      error.statusText = response.statusText;
      error.detail = getReadableErrorMessage(
        data && (data.detail || data.message || data.error || data),
      );
      error.data = data;
      error.requestUrl = lastRequestUrl;
      error.responseBody = data;
      throw error;
    }

    return data;
  }

  async function fetchCurrentUser() {
    const user = await apiRequest("/auth/me", { method: "GET" });
    saveUser(user);
    setupAdminAppearance(user);
    return user;
  }

  async function logoutUser() {
    // Clear the local session immediately so the caller is not blocked on the
    // network round-trip.  The backend call is best-effort: we still attempt it
    // so the server-side httpOnly auth cookie is revoked, but a slow or failing
    // backend cannot prevent the user from being logged out locally.
    clearSession();
    try {
      await apiRequest("/auth/logout", {
        method: "POST",
      });
    } catch (_error) {
      // Ignore – local session already cleared above.
    }
  }

  async function requireSession(redirectTo = "signin.html") {
    const token = getToken();

    if (!token) {
      if (redirectTo) {
        window.location.href = redirectTo;
      }
      return null;
    }

    try {
      return await fetchCurrentUser();
    } catch (error) {
      clearSession();
      if (redirectTo) {
        window.location.href = redirectTo;
      }
      return null;
    }
  }

  function setStatus(node, message, type) {
    if (!node) return;

    const fallbackMessage =
      type === "error"
        ? "Something went wrong. Please try again."
        : "Status updated.";
    const resolvedMessage = getReadableErrorMessage(message, fallbackMessage);

    node.style.display = "block";
    node.textContent = resolvedMessage;
    node.dataset.state = type || "info";
  }

  function clearStatus(node) {
    if (!node) return;
    node.style.display = "none";
    node.textContent = "";
    node.dataset.state = "";
  }

  function getCookieChoice() {
    try {
      const value = localStorage.getItem(COOKIE_CHOICE_KEY);
      return value === "accepted" || value === "declined" ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function saveCookieChoice(choice) {
    try {
      localStorage.setItem(COOKIE_CHOICE_KEY, choice);
    } catch (_error) {
      // Preference persistence can fail in locked-down browser modes.
    }
    document.documentElement.dataset.cookieChoice = choice;
  }

  function updateCookieStatus() {
    const statusNodes = document.querySelectorAll("[data-cookie-status]");
    if (!statusNodes.length) return;

    const choice = getCookieChoice();
    let message = "Your cookie preference has not been set yet.";

    if (choice === "accepted") {
      message = "You accepted optional analytics cookies.";
    } else if (choice === "declined") {
      message =
        "You declined optional analytics cookies. Only essential site technologies are in use.";
    }

    statusNodes.forEach(function (node) {
      node.textContent = message;
    });
  }

  function setupCookieBanner() {
    const banner = document.querySelector("[data-cookie-banner]");
    const acceptButtons = document.querySelectorAll("[data-cookie-accept]");
    const declineButtons = document.querySelectorAll("[data-cookie-decline]");

    function applyChoice(choice) {
      saveCookieChoice(choice);
      updateCookieStatus();
      if (banner) banner.classList.remove("visible");
    }

    const existingChoice = getCookieChoice();
    if (banner) {
      if (!existingChoice) {
        banner.classList.add("visible");
      } else {
        banner.classList.remove("visible");
      }
    }
    updateCookieStatus();

    acceptButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        applyChoice("accepted");
      });
    });

    declineButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        applyChoice("declined");
      });
    });
  }

  function setupMobileMenu() {
    const header = document.querySelector(".site-header");
    const toggle = document.querySelector(".menu-toggle");
    const nav = header ? header.querySelector(".site-nav") : null;
    let lastFocusedElement = null;

    if (!header || !toggle) return;
    if (nav && !nav.id) nav.id = "site-nav";
    if (nav) {
      toggle.setAttribute("aria-controls", nav.id);
    }
    if (!toggle.hasAttribute("aria-expanded")) {
      toggle.setAttribute("aria-expanded", "false");
    }

    function closeMenu() {
      header.classList.remove("open");
      document.body.classList.remove("menu-open");
      toggle.setAttribute("aria-expanded", "false");
      if (
        lastFocusedElement &&
        typeof lastFocusedElement.focus === "function" &&
        document.contains(lastFocusedElement)
      ) {
        lastFocusedElement.focus();
      }
    }

    function openMenu() {
      lastFocusedElement = document.activeElement;
      header.classList.add("open");
      document.body.classList.add("menu-open");
      toggle.setAttribute("aria-expanded", "true");

      const firstNavLink = header.querySelector(
        ".site-nav a, .header-actions a, .header-actions button",
      );
      if (firstNavLink && typeof firstNavLink.focus === "function") {
        firstNavLink.focus();
      }
    }

    toggle.addEventListener("click", function () {
      const isOpen = header.classList.contains("open");
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    header
      .querySelectorAll(
        ".site-nav a, .header-actions a, .header-actions button",
      )
      .forEach(function (link) {
        link.addEventListener("click", closeMenu);
      });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeMenu();
      }
    });

    document.addEventListener("click", function (event) {
      if (!header.classList.contains("open")) return;
      if (header.contains(event.target)) return;
      closeMenu();
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) {
        closeMenu();
      }
    });
  }

  function setupHeaderScrollState() {
    const header = document.querySelector(".site-header");
    if (!header) return;

    function syncScrollState() {
      header.classList.toggle("is-scrolled", window.scrollY > 18);
    }

    syncScrollState();
    window.addEventListener("scroll", syncScrollState, { passive: true });
  }

  function markActiveNavLink() {
    const currentPage =
      window.location.pathname.split("/").pop() || "index.html";

    document.querySelectorAll(".site-nav a[href]").forEach(function (link) {
      try {
        const url = new URL(link.getAttribute("href"), window.location.href);
        const linkPage = url.pathname.split("/").pop() || "index.html";

        if (linkPage === currentPage) {
          link.classList.add("active");
        }
      } catch (error) {
        // Ignore malformed hrefs.
      }
    });
  }

  function applyPaymentLinks() {
    const paymentLinks = getPaymentLinks();

    document.querySelectorAll("[data-payment-link]").forEach(function (link) {
      const slug = link.dataset.paymentLink;
      const existingHref = String(link.getAttribute("href") || "").trim();
      const hasDirectStripeHref = configureDirectStripeCheckout(link, existingHref);
      const checkoutFrozen = link.getAttribute("aria-disabled") === "true";
      if (checkoutFrozen) {
        if (hasDirectStripeHref) {
          return;
        }
        link.removeAttribute("target");
        link.removeAttribute("rel");
        link.href = "#stripe-catalog-refresh";
        link.title = "Secure checkout is unavailable.";
        link.addEventListener("click", function (event) {
          event.preventDefault();
        });
        return;
      }
      const resolved = paymentLinks[slug];
      const originalLabel = link.textContent.trim() || "Start Checkout";
      const purchaseType =
        link.dataset.paymentType || inferPurchaseTypeFromSlug(slug);
      const campaign = String(
        link.dataset.campaign || getActiveCampaignCode(),
      )
        .trim()
        .toUpperCase();
      const promoCode = String(link.dataset.promoCode || "").trim();

      if (resolved) {
        if (!hasDirectStripeHref) {
          link.href =
            purchaseType === "maintenance"
              ? sanitizeMaintenanceCheckoutUrl(resolved)
              : resolved;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        }
        link.addEventListener("click", function (event) {
          const founderCampaign = isLightNeverDiesCampaign(campaign);
          let checkoutHref = hasDirectStripeHref ? existingHref : "";
          if (!hasDirectStripeHref) {
            checkoutHref = buildCheckoutLinkWithContext(resolved, {
              slug,
              purchaseType,
              campaign,
              promoCode,
            });
            if (checkoutHref) {
              link.href = checkoutHref;
            }
          }
          const normalizedSlug = stripMaintenanceSuffix(slug);
          if (founderCampaign && purchaseType === "package" && normalizedSlug) {
            setFounderMaintenancePending({
              campaign: LIGHT_NEVER_DIES_CAMPAIGN,
              packageCode: normalizedSlug,
              requiredBillingInterval: "monthly",
              createdAt: new Date().toISOString(),
            });
          }
          savePendingCheckout({
            packageCode: slug,
            purchaseType,
            paymentLink: checkoutHref || resolved,
            campaign: campaign || "",
            selectedAt: new Date().toISOString(),
          });
          link.dataset.originalLabel = link.dataset.originalLabel || originalLabel;
          link.setAttribute("aria-busy", "true");
          link.textContent = "Opening secure checkout...";
          window.setTimeout(function () {
            link.removeAttribute("aria-busy");
            link.textContent = link.dataset.originalLabel || originalLabel;
          }, 4500);
        });
      } else {
        if (configureDirectStripeCheckout(link, existingHref)) {
          return;
        }
        link.removeAttribute("target");
        link.removeAttribute("rel");
        link.title = "Secure checkout is unavailable.";
        link.setAttribute(
          "aria-label",
          `${originalLabel}. Secure checkout is temporarily unavailable.`,
        );
        link.addEventListener("click", function (event) {
          event.preventDefault();
        });
      }
    });
  }

  async function syncPublicAuthCtas() {
    const ctas = document.querySelectorAll("[data-auth-cta]");
    if (!ctas.length) return;

    const token = getToken();
    if (!token) return;

    try {
      await fetchCurrentUser();

      ctas.forEach(function (cta) {
        cta.textContent = cta.dataset.loggedInLabel || "Dashboard";
        cta.setAttribute("href", cta.dataset.loggedInHref || "dashboard.html");
      });
    } catch (error) {
      clearSession();
    }
  }

  function normalizeAdminAppearance(raw) {
    const payload = raw && typeof raw === "object" ? raw : {};
    const theme = String(payload.theme || "light").trim().toLowerCase();
    // Canonical text-scale value is "normal"; any previously persisted
    // value other than "large" (including the legacy "default") also
    // normalizes to "normal" below.
    const textScale = String(payload.textScale || "normal").trim().toLowerCase();
    return {
      theme: ["light", "dark", "high-contrast"].includes(theme) ? theme : "light",
      textScale: textScale === "large" ? "large" : "normal",
    };
  }

  function resolveAdminAppearancePrincipal(user) {
    const source = user && typeof user === "object" ? user : getSavedUser() || {};
    const directId = String(source.id || source._id || source.user_id || "").trim();
    if (directId) return `id:${directId}`;
    const email = String(source.email || "").trim().toLowerCase();
    if (email) return `email:${email}`;
    return "";
  }

  function readAdminAppearanceStore() {
    try {
      const raw = localStorage.getItem(ADMIN_APPEARANCE_BY_USER_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function writeAdminAppearanceStore(value) {
    try {
      localStorage.setItem(ADMIN_APPEARANCE_BY_USER_KEY, JSON.stringify(value || {}));
    } catch (_error) {
      // Ignore storage failures.
    }
  }

  function getSavedAdminAppearance(user) {
    const principal = resolveAdminAppearancePrincipal(user);
    const store = readAdminAppearanceStore();
    if (principal && store[principal]) {
      return normalizeAdminAppearance(store[principal]);
    }
    try {
      return normalizeAdminAppearance(JSON.parse(localStorage.getItem(ADMIN_APPEARANCE_DEFAULT_KEY) || "{}"));
    } catch (_error) {
      return normalizeAdminAppearance({});
    }
  }

  function saveAdminAppearance(preference, user) {
    const normalized = normalizeAdminAppearance(preference);
    const principal = resolveAdminAppearancePrincipal(user);
    if (principal) {
      const store = readAdminAppearanceStore();
      store[principal] = normalized;
      writeAdminAppearanceStore(store);
    }
    try {
      localStorage.setItem(ADMIN_APPEARANCE_DEFAULT_KEY, JSON.stringify(normalized));
    } catch (_error) {
      // Ignore storage failures.
    }
    return normalized;
  }

  function shouldEnableAdminAppearance(user) {
    const pageHasAdminMarkers =
      Boolean(document.querySelector("[data-admin-control-center-page]")) ||
      Boolean(document.querySelector("[data-admin-queue-page]")) ||
      Boolean(document.querySelector("[data-admin-family-manager-page]")) ||
      Boolean(document.querySelector("[data-admin-review-page]"));
    if (pageHasAdminMarkers) return true;
    const isDashboardPage = Boolean(document.querySelector("[data-dashboard]"));
    return isDashboardPage && isInternalRole(user || getSavedUser() || {});
  }

  function applyAdminAppearance(preference, user) {
    if (!shouldEnableAdminAppearance(user)) {
      document.body.classList.remove("admin-interface-mode");
      delete document.body.dataset.adminTheme;
      delete document.body.dataset.adminTextScale;
      delete document.documentElement.dataset.adminTheme;
      delete document.documentElement.dataset.adminTextScale;
      return;
    }
    const normalized = normalizeAdminAppearance(preference);
    document.body.classList.add("admin-interface-mode");
    document.body.dataset.adminTheme = normalized.theme;
    document.body.dataset.adminTextScale = normalized.textScale;
    document.documentElement.dataset.adminTheme = normalized.theme;
    document.documentElement.dataset.adminTextScale = normalized.textScale;
  }

  const ADMIN_THEME_OPTIONS = [
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
    { value: "high-contrast", label: "High Contrast" },
  ];

  function injectAdminAppearanceControls(user) {
    if (!shouldEnableAdminAppearance(user)) return;
    const container = document.querySelector(".header-actions");
    if (!container) return;
    if (container.querySelector("[data-admin-appearance-toggle]")) return;
    const appearance = getSavedAdminAppearance(user);
    const wrapper = document.createElement("div");
    wrapper.className = "admin-appearance-controls";

    const themeButtonsMarkup = ADMIN_THEME_OPTIONS.map(function (option) {
      const isSelected = appearance.theme === option.value;
      return (
        `<button type="button" class="admin-appearance-theme-btn" role="radio" ` +
        `data-admin-appearance-theme-option="${option.value}" ` +
        `aria-checked="${isSelected ? "true" : "false"}" ` +
        `tabindex="${isSelected ? "0" : "-1"}">${option.label}</button>`
      );
    }).join("");

    wrapper.innerHTML = `
      <button class="btn btn-secondary" type="button" data-admin-appearance-toggle aria-expanded="false" aria-controls="admin-appearance-panel">Appearance</button>
      <div class="admin-appearance-panel" id="admin-appearance-panel" data-admin-appearance-panel hidden>
        <div class="admin-appearance-theme-group">
          <span class="admin-appearance-group-label" id="admin-appearance-theme-label">Theme</span>
          <div
            class="admin-appearance-theme-buttons"
            data-admin-appearance-theme
            role="radiogroup"
            aria-labelledby="admin-appearance-theme-label"
          >
            ${themeButtonsMarkup}
          </div>
        </div>
        <label class="admin-appearance-checkbox">
          <input type="checkbox" data-admin-appearance-large-text ${appearance.textScale === "large" ? 'checked="checked"' : ""} />
          <span>Larger Text</span>
        </label>
      </div>
    `;
    container.prepend(wrapper);
    const toggle = wrapper.querySelector("[data-admin-appearance-toggle]");
    const panel = wrapper.querySelector("[data-admin-appearance-panel]");
    const themeGroup = wrapper.querySelector("[data-admin-appearance-theme]");
    const themeButtons = Array.from(wrapper.querySelectorAll("[data-admin-appearance-theme-option]"));
    const largeTextInput = wrapper.querySelector("[data-admin-appearance-large-text]");
    if (!toggle || !panel || !themeGroup || !themeButtons.length || !largeTextInput) return;

    toggle.addEventListener("click", function () {
      const isOpen = !panel.hidden;
      panel.hidden = isOpen;
      toggle.setAttribute("aria-expanded", isOpen ? "false" : "true");
    });

    function currentTheme() {
      const active = themeButtons.find(function (btn) {
        return btn.getAttribute("aria-checked") === "true";
      });
      return active ? active.getAttribute("data-admin-appearance-theme-option") : "light";
    }

    function saveAndApply() {
      const updated = saveAdminAppearance(
        {
          theme: currentTheme(),
          textScale: largeTextInput.checked ? "large" : "normal",
        },
        user || getSavedUser() || {},
      );
      applyAdminAppearance(updated, user);
    }

    function selectTheme(value) {
      themeButtons.forEach(function (btn) {
        const isSelected = btn.getAttribute("data-admin-appearance-theme-option") === value;
        btn.setAttribute("aria-checked", isSelected ? "true" : "false");
        btn.setAttribute("tabindex", isSelected ? "0" : "-1");
        btn.classList.toggle("is-selected", isSelected);
      });
      saveAndApply();
    }

    themeButtons.forEach(function (btn, index) {
      btn.addEventListener("click", function () {
        selectTheme(btn.getAttribute("data-admin-appearance-theme-option"));
      });
      btn.addEventListener("keydown", function (event) {
        if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
        event.preventDefault();
        const delta = event.key === "ArrowRight" ? 1 : -1;
        const nextIndex = (index + delta + themeButtons.length) % themeButtons.length;
        const nextBtn = themeButtons[nextIndex];
        nextBtn.focus();
        selectTheme(nextBtn.getAttribute("data-admin-appearance-theme-option"));
      });
    });

    largeTextInput.addEventListener("change", saveAndApply);
  }

  function setupAdminAppearance(user) {
    const saved = getSavedAdminAppearance(user);
    applyAdminAppearance(saved, user);
    injectAdminAppearanceControls(user);
  }

  function setupSelectPlaceholderState() {
    document.querySelectorAll("select").forEach(function (select) {
      function syncPlaceholderState() {
        if (!select.value) {
          select.classList.add("placeholder-active");
        } else {
          select.classList.remove("placeholder-active");
        }
      }

      syncPlaceholderState();
      select.addEventListener("change", syncPlaceholderState);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    enforceFounderMaintenanceGate();
    setupMobileMenu();
    setupHeaderScrollState();
    markActiveNavLink();
    updateCookieStatus();
    setupCookieBanner();
    applyPaymentLinks();
    syncPublicAuthCtas();
    setupSelectPlaceholderState();
    setupAdminAppearance(getSavedUser());
    window.addEventListener("tol:user-resolved", function (event) {
      setupAdminAppearance(event && event.detail ? event.detail.user : null);
    });
  });

  const sharedApi = {
    isLocalApp,
    isInternalRole,
    getApiBaseUrl,
    getPaymentLinks,
    saveToken,
    getToken,
    clearToken,
    saveUser,
    getSavedUser,
    clearUser,
    clearSession,
    apiRequest,
    fetchCurrentUser,
    logoutUser,
    requireSession,
    setStatus,
    clearStatus,
    normalizePackageCode,
    stripMaintenanceSuffix,
    getPackageProfile,
    resolvePackageLane,
    resolvePackageDisplayName,
    packageSupportsLinkKeys,
    inferPurchaseTypeFromSlug,
    savePendingCheckout,
    buildCheckoutLinkWithContext,
    getActiveCampaignCode,
    isLightNeverDiesCampaign,
    getFounderMaintenancePending,
    setFounderMaintenancePending,
    clearFounderMaintenancePending,
    getReadableErrorMessage,
    getSavedAdminAppearance,
    saveAdminAppearance,
    applyAdminAppearance,
    setupAdminAppearance,
  };

  window.TOLApp = sharedApi;
  window.TOLAuth = sharedApi;
})();
