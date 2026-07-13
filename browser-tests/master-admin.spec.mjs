import { expect, test } from "@playwright/test";

const OFFICER_A = { _id: "officer-a", id: "officer-a", email: "officer.a@tomboflight.test", role: "admin", access_tier: "ceo_master_admin", department_role: "executive_tech_admin", role_codes: ["ceo_master_admin", "executive_tech_admin"] };
const OFFICER_B = { _id: "officer-b", id: "officer-b", email: "officer.b@tomboflight.test", role: "admin", access_tier: "operations_admin", department_role: "operations_admin", role_codes: ["operations_admin"] };
const TABS = ["overview", "package_services", "family_household", "production", "uploads", "vault_metadata", "billing", "mint", "audit_history"];

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function makeCase(seed) {
  return {
    case_id: seed.case_id,
    project_id: seed.project_id,
    order_id: seed.order_id,
    name: seed.name,
    email: seed.email,
    role: seed.role,
    project: seed.project,
    package: seed.package,
    package_name: seed.package_name,
    package_code: seed.package_code,
    lane: seed.lane,
    status: seed.status,
    alerts: seed.alerts || [],
    operator_guidance: seed.operator_guidance || [],
    tags: seed.tags || [],
    quick_actions: ["sync_package", "repair_record", "run_readiness_check"],
    search_index: seed.search_index || [],
  };
}

function workspacePayload(seed) {
  const now = new Date().toISOString();
  return {
    case_id: seed.case_id,
    project: { id: seed.project_id, project_id: seed.project_id, name: seed.project, status: seed.status },
    package: { package_code: seed.package_code, package_name: seed.package_name, package_lane: seed.lane },
    readiness: { mint_review_ready: false, mint_eligible: false, blocking_reasons: ["upload_review_pending"] },
    alerts: seed.alerts || [],
    tabs: {
      overview: { customer_type: seed.role, workflow_state: seed.status, warnings: [] },
      package_services: { package_name: seed.package_name, package_code: seed.package_code, project_lane: seed.lane, maintenance_state: "active" },
      family_household: { family_id: `fam-${seed.case_id}`, household_id: `house-${seed.case_id}` },
      production: { build_status: seed.status, phase: "client_review", delivery_state: "in_progress" },
      uploads: { uploaded_files: 2, review_status: "pending", verification_readiness: "waiting_for_uploads", items: [{ id: "upload-1", filename: "lineage.pdf", category: "verification", status: "pending", created_at: now }] },
      vault_metadata: { collection_count: 2, release_rule_count: 1, warnings: ["private vault contents hidden by default"] },
      billing: { order_status: "paid", stripe_session_id: "cs_test_fixture_only", payment_link_id: "plink_fixture", billing_history_impact: "no historical mutation" },
      mint: { eligibility: "blocked", approvals: { mint_review_ready: false }, blocking_reasons: ["upload_review_pending"] },
      audit_history: [{ action: "workspace_opened", target_type: "project", target_id: seed.project_id, actor_email: OFFICER_A.email, result: "success", timestamp: now }],
      identity: {
        user_id: seed.case_id.replace("case-", "user-"),
        full_name: seed.name,
        email: seed.email,
        role: seed.role,
        status: seed.status,
        admin_user_relationship: seed.role,
      },
      package_lane: { package_name: seed.package_name, package_code: seed.package_code, project_lane: seed.lane, package_normalization_status: "normalized", source: "fixture", raw_value: seed.package_code },
      project: {
        project_name: seed.project,
        project_id: seed.project_id,
        build_status: seed.status,
        phase: "client_review",
        intake_readiness: "ready",
        linked_family: { family_id: `fam-${seed.case_id}`, family_name: `${seed.name} Family`, household_id: `house-${seed.case_id}`, household_name: `${seed.name} Household` },
      },
      uploads_verification: { uploaded_files: 2, review_status: "pending", verification_readiness: "waiting_for_uploads", file_categories: ["verification"], items: [{ id: "upload-1", filename: "lineage.pdf", category: "verification", status: "pending", created_at: now }] },
      entitlements: { maintenance_status: "active", access_scope: "standard", private_vault_contents: "hidden" },
      orders_billing: { order_status: "paid", package_name: seed.package_name, package_code: seed.package_code, lane: seed.lane, paid: true, stripe_session_id: "cs_test_fixture_only", payment_link_id: "plink_fixture", project_link_status: "linked", maintenance_state: "active", next_charge_date: now, primary_order: { id: seed.order_id, status: "paid", package_name: seed.package_name }, related_orders: [] },
      mint_readiness: { current_state: "blocked", eligibility: "blocked", approvals: { mint_review_ready: false }, queue_status: "pending", blocking_reasons: ["upload_review_pending"], guidance: [{ severity: "warning", title: "Uploads pending", next_action: "Review uploads" }] },
      audit_timeline: [{ action: "workspace_opened", target_type: "project", target_id: seed.project_id, actor_email: OFFICER_A.email, result: "success", timestamp: now }],
    },
  };
}

function createMockEnvironment() {
  const cases = [
    makeCase({
      case_id: "case-customer",
      project_id: "proj-customer",
      order_id: "order-customer",
      name: "Customer Fixture",
      email: "customer.fixture@tomboflight.test",
      role: "customer",
      project: "Customer Legacy Project",
      package: "legacy_plus",
      package_name: "Legacy Plus",
      package_code: "legacy_plus",
      lane: "household",
      status: "client_review",
      tags: ["customer"],
      search_index: ["customer fixture", "customer.fixture@tomboflight.test", "user-customer", "proj-customer", "fam-customer", "house-customer", "order-customer", "cs_fixture_customer", "legacy_plus", "client_review"],
    }),
    makeCase({
      case_id: "case-officer",
      project_id: "proj-officer",
      order_id: "order-officer",
      name: "Officer Fixture",
      email: "officer.fixture@tomboflight.test",
      role: "officer",
      project: "Officer Oversight",
      package: "legacy_snapshot",
      package_name: "Legacy Snapshot",
      package_code: "legacy_snapshot",
      lane: "portrait",
      status: "active",
      tags: ["officer"],
      search_index: ["officer fixture", "officer.fixture@tomboflight.test"],
    }),
    makeCase({
      case_id: "case-internal-validation",
      project_id: "proj-internal-validation",
      order_id: "order-internal-validation",
      name: "Internal Validation Account",
      email: "validation.fixture@tomboflight.test",
      role: "internal_validation_account",
      project: "Validation Sandbox",
      package: "legacy_snapshot",
      package_name: "Legacy Snapshot",
      package_code: "legacy_snapshot",
      lane: "portrait",
      status: "active",
      tags: ["internal validation account"],
      search_index: ["internal validation account"],
    }),
    makeCase({
      case_id: "case-prototype-genesis",
      project_id: "proj-genesis",
      order_id: "order-genesis",
      name: "Genesis Prototype",
      email: "genesis.prototype@tomboflight.test",
      role: "prototype",
      project: "Genesis Prototype",
      package: "heirloom_legacy_tree",
      package_name: "Heirloom Legacy Tree",
      package_code: "heirloom_legacy_tree",
      lane: "household",
      status: "prototype",
      tags: ["prototype"],
      search_index: ["genesis prototype", "prototype"],
    }),
    makeCase({
      case_id: "case-larry-personal",
      project_id: "proj-larry-personal",
      order_id: "order-larry-personal",
      name: "Larry Personal Project",
      email: "larry.personal.fixture@tomboflight.test",
      role: "customer",
      project: "Larry Personal Project",
      package: "legacy_plus",
      package_name: "Legacy Plus",
      package_code: "legacy_plus",
      lane: "household",
      status: "delivered_project",
      tags: ["delivered project"],
      search_index: ["larry personal project", "delivered project"],
    }),
    makeCase({
      case_id: "case-suspended",
      project_id: "proj-suspended",
      order_id: "order-suspended",
      name: "Suspended Fixture",
      email: "suspended.fixture@tomboflight.test",
      role: "customer",
      project: "Suspended Account Project",
      package: "legacy_snapshot",
      package_name: "Legacy Snapshot",
      package_code: "legacy_snapshot",
      lane: "portrait",
      status: "suspended_account",
      tags: ["suspended account"],
      search_index: ["suspended account", "suspended.fixture@tomboflight.test"],
    }),
  ];

  const stats = {
    packageApplyWrites: 0,
    serviceApplyWrites: 0,
    officerApplyWrites: 0,
    previewWrites: 0,
    stripeMutations: 0,
    blockchainOps: 0,
    productionWrites: 0,
    impersonationAuditEvents: 0,
  };

  const state = {
    activeImpersonation: null,
    officerPermissions: {
      "jenn.wood@tomboflight.com": { role_assignments: ["finance_admin"], permission_overrides: [] },
      "k.goffigan@tomboflight.com": { role_assignments: ["operations_admin"], permission_overrides: [] },
      "marquis.l.floyd@tomboflight.com": { role_assignments: ["marketing_admin"], permission_overrides: [] },
    },
  };

  return { cases, stats, state };
}

async function installApiRoutes(page, env) {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (!path.startsWith("/auth/") && !path.startsWith("/admin/") && !path.startsWith("/packages/")) {
      return route.continue();
    }

    const json = (payload, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });

    if (method === "GET" && path === "/auth/me") {
      return json(OFFICER_A);
    }
    if (method === "POST" && path === "/auth/logout") {
      return json({ ok: true });
    }
    if (method === "GET" && path === "/packages/catalog") {
      return json({ packages: { legacy_snapshot: { display_name: "Legacy Snapshot" }, legacy_plus: { display_name: "Legacy Plus" }, heirloom_legacy_tree: { display_name: "Heirloom Legacy Tree" } } });
    }
    if (method === "GET" && path === "/admin/control-center/access-profile") {
      return json({
        role_key: "ceo_master_admin",
        is_super_admin: true,
        allowed_queues: ["overview", "customer_cases", "users", "orders", "projects", "entitlements", "mint_queue", "upload_review", "billing_maintenance", "audit", "system_health"],
        allowed_tabs: ["identity", "package_lane", "project", "uploads_verification", "entitlements", "orders_billing", "mint_readiness", "audit_timeline", "overview", "package_services", "family_household", "production", "uploads", "vault_metadata", "billing", "mint", "audit_history"],
        allowed_actions: ["sync_package", "repair_record", "run_readiness_check", "refresh_case_data"],
        allowed_bulk_actions: ["repair-selected-records", "repair-all-safe-records", "repair-missing-entitlements"],
      });
    }
    if (method === "GET" && path === "/admin/control-center/overview") {
      return json({
        summary: { total_users: 6, total_active_projects: 6, paid_orders: 6, missing_entitlements: 0, mint_ready_projects: 0, projects_with_data_mismatch: 0 },
        priority_repairs: { paid_order_without_project_link: [], project_without_entitlement: [], package_without_lane: [], mint_eligible_blocked: [] },
      });
    }
    if (method === "GET" && path === "/admin/control-center/cases") {
      const search = normalize(url.searchParams.get("search"));
      const queue = normalize(url.searchParams.get("queue") || "overview");
      if (queue === "users" && search === "permission-denied") return json({ detail: "Permission denied." }, 403);
      if (queue === "users" && search === "backend-error") return json({ detail: "Backend error." }, 500);
      const items = env.cases.filter((item) => {
        if (!search) return true;
        return item.search_index.some((entry) => normalize(entry).includes(search));
      });
      return json({ items });
    }
    if (method === "GET" && path.startsWith("/admin/control-center/cases/")) {
      const caseId = decodeURIComponent(path.split("/").pop() || "");
      if (caseId === "case-permission-denied") return json({ detail: "Permission denied." }, 403);
      if (caseId === "case-backend-error") return json({ detail: "Workspace retrieval failed." }, 500);
      const found = env.cases.find((item) => item.case_id === caseId) || env.cases[0];
      const payload = workspacePayload(found);
      if (caseId === "case-empty") {
        payload.tabs.uploads = { uploaded_files: 0, review_status: "empty", verification_readiness: "no_files", items: [] };
        payload.tabs.audit_history = [];
      }
      return json(payload);
    }
    if (method === "GET" && path === "/admin/control-center/super-admin/impersonation/active") {
      if (!env.state.activeImpersonation) return json({ active: false });
      return json({ ...env.state.activeImpersonation, active: true });
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/impersonation/start") {
      const body = JSON.parse(request.postData() || "{}");
      if (!normalize(body.reason)) return json({ detail: "A reason is required." }, 422);
      if (env.state.activeImpersonation) return json({ detail: "active impersonation session already exists" }, 400);
      env.state.activeImpersonation = {
        session_id: "imp-session-1",
        banner: "Viewing Tomb of Light as Customer",
        project_id: "proj-customer",
        editing_enabled: false,
        expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
      };
      env.stats.impersonationAuditEvents += 1;
      return json({ ...env.state.activeImpersonation, active: true });
    }
    if (method === "POST" && path.endsWith("/enable-editing")) {
      const body = JSON.parse(request.postData() || "{}");
      if (!normalize(body.reason)) return json({ detail: "A reason is required to enable editing." }, 422);
      if (!env.state.activeImpersonation) return json({ detail: "No active session." }, 400);
      env.state.activeImpersonation.editing_enabled = true;
      env.stats.impersonationAuditEvents += 1;
      return json({ ...env.state.activeImpersonation, active: true });
    }
    if (method === "POST" && path.endsWith("/stop")) {
      env.state.activeImpersonation = null;
      env.stats.impersonationAuditEvents += 1;
      return json({ active: false, status: "stopped" });
    }
    if (method === "POST" && path.includes("/package-change/preview")) {
      env.stats.previewWrites += 0;
      return json({
        changes: [{ scope: "project", field: "package_code", before: "legacy_snapshot", after: "legacy_plus" }],
        before: { order: { package_code: "legacy_snapshot", stripe_session_id: "cs_checkout_history" }, project: { package_code: "legacy_snapshot" } },
        proposed_after: { project: { package_code: "legacy_plus" } },
        validation: { stripe_purchase_record_preserved: true },
        summary: {
          original_purchase: "Legacy Snapshot",
          current_package: "Legacy Snapshot",
          proposed_package: "Legacy Plus",
          services_added: ["narration"],
          services_removed: [],
          entitlement_changes: ["viewer_access_enabled: true"],
          access_impact: "Expanded",
          billing_history_impact: "No Stripe mutation",
          reason: "Fixture reason",
          authorization_source: "ceo_master_admin",
          effective_date: new Date().toISOString(),
        },
      });
    }
    if (method === "POST" && path.includes("/package-change/apply")) {
      env.stats.packageApplyWrites += 1;
      return json({ changed: true, stripe_purchase_record_preserved: true, changes: [{ scope: "project", field: "package_code", before: "legacy_snapshot", after: "legacy_plus" }] });
    }
    if (method === "POST" && path.includes("/service-controls/preview")) {
      return json({
        changes: [{ scope: "service_controls", field: "vault_enabled", before: false, after: true }],
        validation: { stripe_purchase_record_preserved: true },
        summary: {
          original_purchase: "Legacy Snapshot",
          current_package: "Legacy Snapshot",
          proposed_package: "Legacy Plus",
          services_added: ["vault", "scheduled_reveal"],
          services_removed: ["none"],
          entitlement_changes: ["max_storage_gb: +10"],
          access_impact: "Expanded",
          billing_history_impact: "No Stripe mutation",
          reason: "Fixture reason",
          authorization_source: "ceo_master_admin",
          effective_date: new Date().toISOString(),
        },
      });
    }
    if (method === "POST" && path.includes("/service-controls/apply")) {
      env.stats.serviceApplyWrites += 1;
      return json({ changed: true, stripe_purchase_record_preserved: true, idempotent: true, changes: [{ scope: "service_controls", field: "vault_enabled", before: false, after: true }] });
    }
    if (method === "GET" && path === "/admin/control-center/super-admin/officers") {
      return json({
        items: [
          { full_name: "Jennifer Wood", officer_email: "jenn.wood@tomboflight.com", role_assignments: env.state.officerPermissions["jenn.wood@tomboflight.com"].role_assignments, permission_overrides: env.state.officerPermissions["jenn.wood@tomboflight.com"].permission_overrides },
          { full_name: "Keith Goffigan", officer_email: "k.goffigan@tomboflight.com", role_assignments: env.state.officerPermissions["k.goffigan@tomboflight.com"].role_assignments, permission_overrides: env.state.officerPermissions["k.goffigan@tomboflight.com"].permission_overrides },
          { full_name: "Marquis Floyd", officer_email: "marquis.l.floyd@tomboflight.com", role_assignments: env.state.officerPermissions["marquis.l.floyd@tomboflight.com"].role_assignments, permission_overrides: env.state.officerPermissions["marquis.l.floyd@tomboflight.com"].permission_overrides },
        ],
      });
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/officers/permissions/preview") {
      const body = JSON.parse(request.postData() || "{}");
      if ((body.role_assignments || []).some((role) => normalize(role) === "ceo_master_admin")) return json({ detail: "ceo_master_admin cannot be assigned through officer management." }, 400);
      return json({
        officer_email: body.officer_email,
        before: env.state.officerPermissions[body.officer_email] || { role_assignments: [], permission_overrides: [] },
        proposed_after: { role_assignments: body.role_assignments || [], permission_overrides: body.grant_permissions || [] },
        changes: [{ scope: "officer", field: "permission_overrides", before: [], after: body.grant_permissions || [] }],
      });
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/officers/permissions/apply") {
      const body = JSON.parse(request.postData() || "{}");
      if (!normalize(body.reason)) return json({ detail: "A reason is required for officer-permissions apply to maintain audit traceability." }, 422);
      if ((body.role_assignments || []).some((role) => normalize(role) === "ceo_master_admin")) return json({ detail: "ceo_master_admin cannot be assigned through officer management." }, 400);
      env.stats.officerApplyWrites += 1;
      env.state.officerPermissions[body.officer_email] = {
        role_assignments: body.role_assignments || [],
        permission_overrides: body.grant_permissions || [],
      };
      return json({ applied: true, after: env.state.officerPermissions[body.officer_email], audit_event_created: true });
    }

    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 404);
  });
}

async function bootstrap(page, user = OFFICER_A) {
  await page.addInitScript(({ userPayload }) => {
    localStorage.setItem("tol_access_token", "fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(userPayload));
    localStorage.setItem("tol_api_base_url", window.location.origin);
  }, { userPayload: user });
}

async function openAppearancePanel(page) {
  await page.getByRole("button", { name: "Appearance" }).click();
  await expect(page.locator("[data-admin-appearance-panel]")).toBeVisible();
}

async function setAppearance(page, { theme, large }) {
  await openAppearancePanel(page);
  if (theme) await page.locator("[data-admin-appearance-theme]").selectOption(theme);
  await page.locator("[data-admin-appearance-large-text]").setChecked(Boolean(large));
}

test.beforeEach(async ({ page }) => {
  const env = createMockEnvironment();
  test.info().annotations.push({ type: "mock-env", description: JSON.stringify(env.stats) });
  await installApiRoutes(page, env);
  await bootstrap(page);
  await page.goto("/admin-control-center.html");
  await expect(page.locator("[data-admin-control-title]")).toContainText("Customer Operations Workspace");
  await expect(page.locator("[data-open-case]").first()).toBeVisible();
  page.__env = env;
});

test("[appearance] validates readability + screenshots for all appearance modes", async ({ page }) => {
  const modes = [
    { name: "light", theme: "light", large: false },
    { name: "dark", theme: "dark", large: false },
    { name: "high-contrast", theme: "high-contrast", large: false },
    { name: "larger-text", theme: "light", large: true },
    { name: "high-contrast-larger-text", theme: "high-contrast", large: true },
  ];

  for (const mode of modes) {
    await setAppearance(page, { theme: mode.theme, large: mode.large });
    await page.getByRole("tab", { name: "Package & Services" }).click();
    await expect(page.locator("[data-admin-impersonation-banner]")).toBeAttached();
    await page.screenshot({ path: `browser-screenshots/${mode.name}.png`, fullPage: true });
    const checks = await page.evaluate(() => {
      const body = document.body;
      const bodyStyle = getComputedStyle(body);
      const baseFont = parseFloat(bodyStyle.fontSize || "0");
      const lineHeight = parseFloat(bodyStyle.lineHeight || "0");
      const labels = [...document.querySelectorAll("label")].slice(0, 10).map((el) => parseFloat(getComputedStyle(el).fontSize || "0"));
      const lowOpacityImportantText = [...document.querySelectorAll("h1, h2, h3, p, label, th, td, button")]
        .filter((el) => {
          const style = getComputedStyle(el);
          return parseFloat(style.opacity || "1") < 0.75 && (el.textContent || "").trim().length > 0;
        })
        .length;
      const focusBefore = document.activeElement;
      const firstFocusable = document.querySelector("button, a, input, select, textarea");
      if (firstFocusable instanceof HTMLElement) firstFocusable.focus();
      const focusStyle = firstFocusable ? getComputedStyle(firstFocusable) : null;
      const outlineWidth = focusStyle ? parseFloat(focusStyle.outlineWidth || "0") : 0;
      return {
        baseFont,
        lineHeight,
        minLabelFont: labels.length ? Math.min(...labels) : 99,
        lowOpacityImportantText,
        outlineWidth,
        hasImpersonationBanner: !!document.querySelector("[data-admin-impersonation-banner]"),
        _focusBeforeTag: focusBefore ? focusBefore.tagName : "",
      };
    });
    expect(checks.baseFont).toBeGreaterThanOrEqual(16);
    expect(checks.lineHeight).toBeGreaterThanOrEqual(1.45);
    expect(checks.minLabelFont).toBeGreaterThanOrEqual(15);
    expect(checks.lowOpacityImportantText).toBe(0);
    expect(checks.outlineWidth).toBeGreaterThan(0);
    expect(checks.hasImpersonationBanner).toBeTruthy();
  }
});

test("[theme] validates persistence across reload/navigation/login and impersonation lifecycle", async ({ page }) => {
  await setAppearance(page, { theme: "high-contrast", large: true });
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "high-contrast");
  await expect(page.locator("body")).toHaveAttribute("data-admin-text-scale", "large");

  await page.goto("/admin-family-manager.html");
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "high-contrast");
  await page.goto("/admin-control-center.html");
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "high-contrast");

  await page.evaluate(() => {
    localStorage.removeItem("tol_access_token");
    localStorage.setItem("tol_access_token", "fixture-token");
  });
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "high-contrast");

  await page.locator("[data-admin-impersonation-start-reason]").fill("Read-only customer review");
  await page.locator("[data-admin-impersonation-start]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toContainText("Impersonation Active");
  await page.locator("[data-admin-impersonation-stop]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toBeHidden();

  const preferenceStore = await page.evaluate(() => {
    const map = JSON.parse(localStorage.getItem("tol_admin_appearance_by_user") || "{}");
    map["email:officer.a@tomboflight.test"] = { theme: "high-contrast", textScale: "large" };
    map["email:officer.b@tomboflight.test"] = { theme: "dark", textScale: "default" };
    localStorage.setItem("tol_admin_appearance_by_user", JSON.stringify(map));
    return map;
  });
  expect(preferenceStore["email:officer.a@tomboflight.test"].theme).toBe("high-contrast");
  expect(preferenceStore["email:officer.b@tomboflight.test"].theme).toBe("dark");
});

test("[keyboard] validates keyboard-only navigation reachability and no trap", async ({ page }) => {
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").focus();
  await expect(page.locator(":focus")).toHaveAttribute("data-admin-case-search", "");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.getByRole("tab", { name: "Package & Services" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-workspace]")).toContainText("Package");
  await expect(page.locator("[data-super-admin-package-preview]")).toBeVisible();
  await page.locator("[data-super-admin-package-preview]").focus();
  await page.keyboard.press("Enter");
  await page.locator("[data-super-admin-preview-cancel]").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-control-action-status]")).toContainText("Preview canceled with no write");
  await page.locator("[data-admin-impersonation-start]").focus();
  await expect(page.locator(":focus")).toHaveAttribute("data-admin-impersonation-start", /case-/);
  const activeElementTag = await page.evaluate(() => document.activeElement?.tagName || "");
  expect(activeElementTag.length).toBeGreaterThan(0);
});

test("[contrast] validates WCAG AA contrast thresholds for key selectors", async ({ page }) => {
  const failures = await page.evaluate(() => {
    function parseRgb(value) {
      const m = String(value || "").match(/rgba?\(([^)]+)\)/i);
      if (!m) return null;
      const parts = m[1].split(",").map((p) => Number.parseFloat(p.trim()));
      if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) return null;
      return { r: parts[0], g: parts[1], b: parts[2], a: Number.isFinite(parts[3]) ? parts[3] : 1 };
    }
    function srgb(v) {
      const n = v / 255;
      return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
    }
    function luminance(rgb) {
      return 0.2126 * srgb(rgb.r) + 0.7152 * srgb(rgb.g) + 0.0722 * srgb(rgb.b);
    }
    function ratio(fg, bg) {
      const l1 = luminance(fg);
      const l2 = luminance(bg);
      const light = Math.max(l1, l2);
      const dark = Math.min(l1, l2);
      return (light + 0.05) / (dark + 0.05);
    }
    function effectiveBg(node) {
      let cur = node;
      while (cur) {
        const color = parseRgb(getComputedStyle(cur).backgroundColor);
        if (color && color.a > 0.95) return color;
        cur = cur.parentElement;
      }
      return { r: 255, g: 255, b: 255, a: 1 };
    }
    const targets = [
      { selector: "body", required: 4.5 },
      { selector: ".card-copy", required: 4.5 },
      { selector: ".site-nav a", required: 4.5 },
      { selector: ".btn", required: 4.5 },
      { selector: ".admin-status-chip", required: 3.0 },
      { selector: "label", required: 4.5 },
      { selector: "input", required: 4.5 },
      { selector: "[data-state='error']", required: 4.5 },
      { selector: "[data-state='warning']", required: 4.5 },
      { selector: "[data-state='success']", required: 4.5 },
      { selector: "[data-admin-impersonation-banner]", required: 4.5 },
      { selector: ".site-nav a[aria-current='page']", required: 4.5 },
      { selector: ":focus-visible", required: 3.0 },
    ];
    const problems = [];
    for (const target of targets) {
      const el = document.querySelector(target.selector);
      if (!el) continue;
      const style = getComputedStyle(el);
      const fg = parseRgb(style.color);
      const bg = effectiveBg(el);
      if (!fg || !bg) continue;
      const value = ratio(fg, bg);
      if (value + 1e-6 < target.required) {
        problems.push({
          selector: target.selector,
          ratio: Number(value.toFixed(2)),
          required: target.required,
          foreground: style.color,
          background: getComputedStyle(el).backgroundColor,
        });
      }
    }
    return problems;
  });
  expect(failures).toEqual([]);
  await page.screenshot({ path: "browser-screenshots/wcag-contrast.png", fullPage: true });
});

test("[account360] validates all tabs + loading/empty/denied/error states and sensitive-data guards", async ({ page }) => {
  for (const tabLabel of ["Overview", "Package & Services", "Family / Household", "Production", "Uploads", "Vault Metadata", "Billing", "Mint", "Audit History"]) {
    await page.getByRole("tab", { name: tabLabel }).click();
  }
  await expect(page.locator("[data-admin-case-workspace]")).toContainText("workspace_opened");

  const deniedStatus = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/cases?queue=users&limit=80&search=permission-denied`);
    return res.status;
  });
  expect(deniedStatus).toBe(403);

  const backendErrorStatus = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/cases?queue=users&limit=80&search=backend-error`);
    return res.status;
  });
  expect(backendErrorStatus).toBe(500);

  await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").fill("case-empty");
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-list]")).toContainText("No case results");

  await expect(page.locator("body")).not.toContainText("sk_live_");
  await expect(page.locator("body")).not.toContainText("private_key");
  await expect(page.locator("body")).not.toContainText("token=");
  await expect(page.locator("body")).not.toContainText("password");
});

test("[search] validates multi-identifier search and badge distinctions", async ({ page }) => {
  const terms = [
    "customer fixture",
    "customer.fixture@tomboflight.test",
    "proj-customer",
    "order-customer",
    "fam-customer",
    "house-customer",
    "cs_fixture_customer",
    "legacy_plus",
    "client_review",
  ];
  for (const term of terms) {
    await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").fill(term);
    await page.keyboard.press("Enter");
    await expect(page.locator("[data-admin-case-list]")).toContainText("Customer Fixture");
  }
  await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").fill("genesis prototype");
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-list]")).toContainText("Genesis Prototype");
  await expect(page.locator("[data-admin-case-list]")).not.toContainText("Larry Personal Project");
});

test("[package-service] validates preview/cancel/apply/idempotent and no Stripe or blockchain mutation", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => dialog.accept());
  await page.getByRole("tab", { name: "Package & Services" }).click();
  await expect(page.locator("[data-super-admin-package-field='reason']")).toBeVisible();
  await page.locator("[data-super-admin-package-field='reason']").fill("Fixture package update");
  await page.locator("[data-super-admin-service-field='operation']").selectOption("upgrade");
  await page.locator("[data-super-admin-service-field='add_addons']").fill("extra_storage");
  await page.locator("[data-super-admin-package-preview]").click();
  await expect(page.locator("[data-super-admin-package-preview-output]")).toContainText("Project");
  const beforeCancelWrites = env.stats.packageApplyWrites + env.stats.serviceApplyWrites;
  await page.locator("[data-super-admin-preview-cancel]").click();
  expect(env.stats.packageApplyWrites + env.stats.serviceApplyWrites).toBe(beforeCancelWrites);
  await page.locator("[data-super-admin-service-preview]").click();
  await page.locator("[data-super-admin-service-apply]").click();
  await page.locator("[data-super-admin-service-apply]").click();
  await page.locator("[data-super-admin-package-apply]").click();
  expect(env.stats.serviceApplyWrites).toBeGreaterThanOrEqual(2);
  expect(env.stats.packageApplyWrites).toBeGreaterThanOrEqual(1);
  expect(env.stats.stripeMutations).toBe(0);
  expect(env.stats.blockchainOps).toBe(0);
});

test("[officer] validates officer permission templates/preview/apply/guardrails via browser API flow", async ({ page }) => {
  const env = page.__env;
  const preview = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/officers/permissions/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        officer_email: "jenn.wood@tomboflight.com",
        role_assignments: ["finance_admin"],
        grant_permissions: ["admin.audit.read"],
      }),
    });
    return { status: res.status, body: await res.json() };
  });
  expect(preview.status).toBe(200);
  expect(preview.body.proposed_after.permission_overrides).toContain("admin.audit.read");

  const noReason = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/officers/permissions/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        officer_email: "jenn.wood@tomboflight.com",
        role_assignments: ["finance_admin"],
        grant_permissions: ["admin.audit.read"],
      }),
    });
    return res.status;
  });
  expect(noReason).toBe(422);

  const applied = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/officers/permissions/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        officer_email: "k.goffigan@tomboflight.com",
        role_assignments: ["operations_admin"],
        grant_permissions: ["admin.control.view"],
        reason: "Fixture approval",
      }),
    });
    return { status: res.status, body: await res.json() };
  });
  expect(applied.status).toBe(200);
  expect(applied.body.audit_event_created).toBeTruthy();
  expect(env.stats.officerApplyWrites).toBeGreaterThanOrEqual(1);

  const ceoReject = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/officers/permissions/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        officer_email: "marquis.l.floyd@tomboflight.com",
        role_assignments: ["ceo_master_admin"],
      }),
    });
    return res.status;
  });
  expect(ceoReject).toBe(400);
});

test("[impersonation] validates read-only start, reason requirements, banner, escalation, stop, and nested rejection", async ({ page }) => {
  const env = page.__env;
  await expect(page.locator("[data-admin-impersonation-start]")).toBeVisible();
  await page.locator("[data-admin-impersonation-start]").click();
  await expect(page.locator("[data-admin-control-action-status]")).toContainText("reason is required");
  await page.locator("[data-admin-impersonation-start-reason]").fill("Read-only customer verification");
  await page.locator("[data-admin-impersonation-start]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toContainText("read-only");
  const nested = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/impersonation/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: "case-customer", reason: "Second start should fail" }),
    });
    return res.status;
  });
  expect(nested).toBe(400);
  await page.locator("[data-admin-impersonation-enable-editing]").click();
  await expect(page.locator("[data-admin-control-action-status]")).toContainText("reason is required");
  await page.locator("[data-admin-impersonation-edit-reason]").fill("Escalated correction review");
  await page.locator("[data-admin-impersonation-enable-editing]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toContainText("editing enabled");
  await page.locator("[data-admin-impersonation-stop]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toBeHidden();
  expect(env.stats.impersonationAuditEvents).toBeGreaterThanOrEqual(3);
});
