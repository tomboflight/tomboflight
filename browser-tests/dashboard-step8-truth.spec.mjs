import { expect, test } from "@playwright/test";

const CUSTOMER = {
  _id: "step8-customer",
  id: "step8-customer",
  email: "step8.customer@tomboflight.test",
  full_name: "Step Eight Customer",
  role: "user",
  account_type: "customer",
  status: "active",
};

function paidFamilyEstateSnapshot(maintenance = {}) {
  return {
    status: "active",
    workspace: {
      project_id: "project-step8",
      project_name: "Step Eight Family Estate",
      family_id: "family-step8",
      lane: "network",
    },
    package: {
      code: "family_estate_concierge",
      display_name: "Family Estate Concierge",
      lane: "network",
      status: "paid",
      payment_required: true,
    },
    acquisition: {
      source: "paid_order",
      payment_required: true,
      record_id: "order-step8",
    },
    maintenance: {
      status: "active",
      in_grace: false,
      read_only: false,
      write_allowed: true,
      ...maintenance,
    },
    entitlements: {
      package_code: "family_estate_concierge",
      package_lane: "network",
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_build_household: true,
      can_build_family_tree: true,
      can_link_households: true,
      can_use_link_keys: true,
      can_manage_link_keys: true,
      can_use_household_vault: true,
      can_use_viewer: true,
      can_use_secure_share_viewer: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
    },
  };
}

function grantedFamilyEstateSnapshot() {
  const snapshot = paidFamilyEstateSnapshot();
  snapshot.package.status = "granted";
  snapshot.package.payment_required = false;
  snapshot.acquisition = {
    source: "governed_grant",
    payment_required: false,
    record_id: "assignment-step8",
    authorization_source: "ceo_master_admin",
    billing_classification: "complimentary_package",
  };
  return snapshot;
}

function approvedIntake() {
  return {
    id: "intake-step8-approved",
    _id: "intake-step8-approved",
    project_id: "project-step8",
    family_root_id: "family-step8",
    package_name: "Family Estate Concierge",
    package_slug: "family_estate_concierge",
    status: "approved",
    submitted_at: "2026-09-07T21:30:00-04:00",
    uploads: {
      key_portraits: "planned",
      supporting_records: "planned",
      approx_upload_count: "8",
      uploads_rights_confirmed: true,
      uploads_minimization_confirmed: true,
    },
    review: { confirm_accuracy: true },
    consent: {
      consent_process: true,
      consent_store: true,
      consent_authority: true,
    },
  };
}

async function seedSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "step8-fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, CUSTOMER);
}

async function installRoutes(page, snapshot, latest = null) {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (payload, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(payload),
      });

    if (method === "GET" && path === "/auth/me") return json(CUSTOMER);
    if (method === "GET" && path === "/orders/my-orders") return json([]);
    if (method === "GET" && path === "/users/me/workspace-context") {
      return json(snapshot);
    }
    if (method === "GET" && path === "/workspace-access/my-memberships") {
      return json({
        items: [
          {
            project_id: "project-step8",
            user_id: CUSTOMER.id,
            email: CUSTOMER.email,
            member_role: "billing_owner",
            status: "active",
          },
        ],
      });
    }
    if (method === "GET" && path === "/intake-submissions/my-latest") {
      return latest ? json(latest) : json({ detail: "No intake submissions found" }, 404);
    }
    if (method === "GET" && path === "/intake-submissions/my-list") {
      return json(latest ? [latest] : []);
    }
    if (method === "GET" && path === "/projects/project-step8/mint-eligibility") {
      return json({
        eligible: false,
        reasons: ["profile_not_complete"],
        missing_approvals: [],
      });
    }
    if (method === "GET" && path === "/projects/project-step8/mint-status") {
      return json({ latest: null, items: [] });
    }
    if (method === "POST" && path === "/auth/logout") return json({ ok: true });

    if (
      path.startsWith("/auth/") ||
      path.startsWith("/orders/") ||
      path.startsWith("/users/") ||
      path.startsWith("/workspace-access/") ||
      path.startsWith("/intake-submissions/") ||
      path.startsWith("/projects/")
    ) {
      return json({ ok: true });
    }

    return route.continue();
  });
}

async function openDashboard(page, snapshot, latest = null) {
  await seedSession(page);
  await installRoutes(page, snapshot, latest);
  await page.goto("/dashboard.html", { waitUntil: "networkidle" });
}

test.describe("Step 8.1 layered customer dashboard truth", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("Family Estate uses domain navigation instead of exposing raw tool catalog on Home", async ({ page }) => {
    await openDashboard(page, paidFamilyEstateSnapshot());

    await expect(page.locator(".tol-home-shell")).toBeVisible();
    await expect(page.locator(".page-sections")).toBeHidden();
    await expect(page.locator(".tol-home-quick-action")).toHaveCount(4);

    const menuToggle = page.locator(".menu-toggle");
    await menuToggle.click();
    const nav = page.locator("#site-nav");
    await expect(nav.getByText("Home", { exact: true })).toBeVisible();
    await expect(nav.getByText("My Project", { exact: true })).toBeVisible();
    await expect(nav.getByText("Family", { exact: true })).toBeVisible();
    await expect(nav.getByText("Uploads", { exact: true })).toBeVisible();
    await expect(nav.getByText("Vault", { exact: true })).toBeVisible();
    await expect(nav.getByText("Deliverables", { exact: true })).toBeVisible();
    await expect(nav.getByText("Account", { exact: true })).toBeVisible();
    await expect(nav.getByText("Support", { exact: true })).toBeVisible();
    await expect(nav.getByText("Link Keys", { exact: true })).toHaveCount(0);
  });

  test("CEO-governed grant stays accessible without becoming a paid package", async ({ page }) => {
    await openDashboard(page, grantedFamilyEstateSnapshot());

    const truth = await page.evaluate(() => ({
      hasPackageAccess: window.TOLDashboardContext?.hasPackageAccess,
      hasPaidPackage: window.TOLDashboardContext?.hasPaidPackage,
      paidOrder: window.TOLDashboardContext?.paidOrder || null,
      acquisitionSource: window.TOLDashboardContext?.acquisitionSource,
      paymentRequired: window.TOLDashboardContext?.paymentRequired,
      packageStatus: window.TOLDashboardContext?.packageStatus,
    }));

    expect(truth).toEqual({
      hasPackageAccess: true,
      hasPaidPackage: false,
      paidOrder: null,
      acquisitionSource: "governed_grant",
      paymentRequired: false,
      packageStatus: "granted",
    });

    await expect(page.locator(".tol-home-shell")).toBeVisible();
    await expect(page.locator("[data-dashboard-package-display]")).toContainText(
      "Granted access",
    );
  });

  test("approved intake moves Home to production materials instead of asking for final submission", async ({ page }) => {
    await openDashboard(page, paidFamilyEstateSnapshot(), approvedIntake());

    await expect(page.locator(".tol-home-next h2")).toHaveText(
      "Upload your production materials",
    );
    await expect(page.locator(".tol-home-primary")).toHaveText("Upload Materials");
    await expect(page.locator(".tol-home-alert")).toContainText("Intake approved");
    await expect(page.locator(".tol-home-shell")).not.toContainText(
      "Continue and finalize your intake",
    );

    const progress = page.locator(".tol-home-progress-step");
    await expect(progress.nth(0)).toHaveClass(/is-complete/);
    await expect(progress.nth(1)).toHaveClass(/is-current/);
    await expect(progress.nth(2)).not.toHaveClass(/is-complete/);
    await expect(progress.nth(3)).not.toHaveClass(/is-complete/);
  });

  test("maintenance grace is visible without falsely locking the workspace", async ({ page }) => {
    await openDashboard(
      page,
      paidFamilyEstateSnapshot({
        status: "past_due",
        in_grace: true,
        read_only: false,
        write_allowed: true,
        grace_ends_at: "2026-09-30T00:00:00+00:00",
      }),
    );

    await expect(page.locator(".tol-home-alert")).toContainText("Maintenance grace period");
    await expect(page.locator(".tol-home-next h2")).not.toHaveText(
      "Restore maintenance billing",
    );
  });

  test("read-only maintenance makes Billing the Home next action", async ({ page }) => {
    await openDashboard(
      page,
      paidFamilyEstateSnapshot({
        status: "past_due",
        in_grace: false,
        read_only: true,
        write_allowed: false,
        grace_ends_at: "2026-08-31T00:00:00+00:00",
      }),
    );

    await expect(page.locator(".tol-home-next h2")).toHaveText(
      "Restore maintenance billing",
    );
    const action = page.locator(".tol-home-primary");
    await expect(action).toHaveText("Open Billing");
    await expect(action).toHaveAttribute("href", /billing\.html/);
    await expect(page.locator(".tol-home-alert")).toContainText(
      "Maintenance billing needs attention",
    );
  });

  test("desktop shows persistent application rail and no long dashboard stack", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openDashboard(page, paidFamilyEstateSnapshot(), approvedIntake());

    await expect(page.locator(".tol-app-rail")).toBeVisible();
    await expect(page.locator('.tol-app-rail-link[data-tol-domain="home"]')).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.locator(".page-sections")).toBeHidden();
    await expect(page.locator(".tol-home-shell")).toBeVisible();
    await expect(page.locator(".tol-home-quick-action")).toHaveCount(4);

    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });
});
