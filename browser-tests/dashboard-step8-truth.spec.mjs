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

async function seedSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "step8-fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, CUSTOMER);
}

async function installRoutes(page, snapshot) {
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
      return json({ detail: "No intake submissions found" }, 404);
    }
    if (method === "GET" && path === "/intake-submissions/my-list") return json([]);
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

async function openDashboard(page, snapshot) {
  await seedSession(page);
  await installRoutes(page, snapshot);
  await page.goto("/dashboard.html", { waitUntil: "networkidle" });
}

test.describe("Step 8 customer dashboard truth", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("Family Estate exposes household branch Link Keys", async ({ page }) => {
    await openDashboard(page, paidFamilyEstateSnapshot());

    const tools = page.locator(".portal-tools-access-panel");
    await tools.locator("summary").click();
    const linkCard = tools.locator('[data-dashboard-tool="link_keys"]');
    await expect(linkCard).toBeVisible();
    await expect(linkCard.locator(".portal-action-status")).toHaveText("Open");
    await expect(page.locator('.site-nav a[href^="link-keys.html"]')).toBeVisible();
    await expect(page.locator("[data-health-maintenance]")).toHaveText("Active");
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

    await expect(page.locator("[data-dashboard-package-display]")).toContainText(
      "Granted access",
    );
    await expect(page.locator("[data-access-status]")).toContainText(
      "No package payment is required",
    );
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

    await expect(page.locator("[data-health-maintenance]")).toContainText("Grace period");
    await expect(page.locator("[data-dashboard-hero-primary-action]")).not.toHaveText(
      "Restore Maintenance Billing",
    );
  });

  test("read-only maintenance makes billing the next action while Vault stays readable", async ({ page }) => {
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

    await expect(page.locator("[data-health-maintenance]")).toContainText("Read-only");
    await expect(page.locator("[data-dashboard-next-focus]")).toHaveText(
      "Restore maintenance billing",
    );
    const heroAction = page.locator("[data-dashboard-hero-primary-action]");
    await expect(heroAction).toHaveText("Restore Maintenance Billing");
    await expect(heroAction).toHaveAttribute("href", "billing.html");

    const tools = page.locator(".portal-tools-access-panel");
    await tools.locator("summary").click();
    const vaultCard = tools.locator('[data-dashboard-tool="vault"]');
    await expect(vaultCard.locator(".portal-action-status")).toHaveText("Read-only");
    await expect(vaultCard).toHaveAttribute("href", "vault-upload.html");
  });

  test("desktop layout stays within the viewport and keeps the primary action usable", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openDashboard(page, paidFamilyEstateSnapshot());

    await expect(page.locator("#dashboard-primary-actions")).toBeVisible();
    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });
});
