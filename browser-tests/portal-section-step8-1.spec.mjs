import { expect, test } from "@playwright/test";

const CUSTOMER = {
  _id: "step81-live-customer",
  id: "step81-live-customer",
  email: "step81.customer@tomboflight.test",
  full_name: "Larry Customer Fixture",
  role: "user",
  account_type: "customer",
  status: "active",
};

function legacyPlusSnapshot() {
  return {
    status: "active",
    workspace: {
      project_id: "project-legacy-plus",
      project_name: "Robinson Family Legacy Production Build",
      family_id: "family-robinson",
      lane: "household",
      viewer_status: "pending",
      manifest_status: "pending",
    },
    package: {
      code: "legacy_plus",
      display_name: "Legacy Plus",
      lane: "household",
      status: "paid",
      payment_required: true,
    },
    acquisition: {
      source: "paid_order",
      payment_required: true,
      record_id: "order-legacy-plus",
    },
    maintenance: {
      status: "scheduled",
      in_grace: false,
      read_only: false,
      write_allowed: true,
    },
    entitlements: {
      package_code: "legacy_plus",
      package_lane: "household",
      can_upload_portraits: true,
      can_upload_verification_docs: true,
      can_build_household: true,
      family_household_scope: true,
      can_build_family_tree: true,
      can_use_link_keys: true,
      can_manage_link_keys: true,
      can_link_households: false,
      can_use_household_vault: true,
      can_use_viewer: true,
      can_use_secure_share_viewer: true,
      can_use_lineage_certificate: true,
      can_open_family_intake: true,
    },
  };
}

const APPROVED_INTAKE = {
  id: "intake-approved-live-shape",
  status: "approved",
  submitted_at: "2026-03-22T06:34:00Z",
  family_root_id: "family-robinson",
  project_id: "project-legacy-plus",
};

async function seedSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "step81-fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, CUSTOMER);
}

async function installRoutes(page, options = {}) {
  const snapshot = options.snapshot || legacyPlusSnapshot();
  const intakeStatus = options.intakeStatus || 200;
  const mintStatus = options.mintStatus || {
    latest: {
      mint_status: "minted",
      token_id: "812",
      tx_hash: "0xabc123",
    },
  };

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
    if (method === "GET" && path === "/users/me/workspace-context") return json(snapshot);
    if (method === "GET" && path === "/intake-submissions/my-latest") {
      if (intakeStatus !== 200) return json({ detail: "temporary intake failure" }, intakeStatus);
      return json(APPROVED_INTAKE);
    }
    if (method === "GET" && path === "/projects/project-legacy-plus/mint-status") {
      return json(mintStatus);
    }
    if (method === "POST" && path === "/auth/logout") return json({ ok: true });

    if (
      path.startsWith("/auth/") ||
      path.startsWith("/orders/") ||
      path.startsWith("/users/") ||
      path.startsWith("/intake-submissions/") ||
      path.startsWith("/projects/")
    ) {
      return json({ ok: true });
    }

    return route.continue();
  });
}

async function openSection(page, section, options = {}) {
  await seedSession(page);
  await installRoutes(page, options);
  await page.goto(`/portal-section.html?section=${section}`, { waitUntil: "networkidle" });
}

test.describe("Step 8.1 customer section hubs", () => {
  test("Legacy Plus Family hub never promotes generic Link Keys as household branch linking", async ({ page }) => {
    await page.setViewportSize({ width: 960, height: 900 });
    await openSection(page, "family");

    await expect(page.locator("[data-portal-section-title]")).toHaveText("Family Workspace");
    await expect(page.locator(".portal-section-rail")).toBeVisible();
    await expect(page.locator(".menu-toggle")).toBeHidden();
    await expect(page.locator(".portal-section-card").filter({ hasText: "Family Tree" })).toBeVisible();
    await expect(page.locator(".portal-section-card").filter({ hasText: "Members & Access" })).toBeVisible();
    await expect(page.getByText("Household Link Keys", { exact: true })).toHaveCount(0);

    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });

  test("Deliverables separates package inclusion from readiness while preserving minted Anchor proof", async ({ page }) => {
    await page.setViewportSize({ width: 960, height: 900 });
    await openSection(page, "deliverables");

    await expect(page.locator("[data-portal-section-title]")).toHaveText("Legacy Deliverables");

    const viewer = page.locator(".portal-section-card").filter({ hasText: "Lineage Cinema / Viewer" });
    await expect(viewer.locator(".portal-section-state")).toHaveText("Pending production");
    await expect(viewer.locator(".portal-section-action")).toHaveAttribute("aria-disabled", "true");

    const certificate = page.locator(".portal-section-card").filter({ hasText: "Lineage Certificate" });
    await expect(certificate.locator(".portal-section-state")).toHaveText("Pending production");
    await expect(certificate.locator(".portal-section-action")).toHaveAttribute("aria-disabled", "true");

    const anchor = page.locator(".portal-section-card").filter({ hasText: "Legacy Anchor" });
    await expect(anchor.locator(".portal-section-state")).toHaveText("Minted");
    await expect(anchor.locator(".portal-section-action")).toHaveText("View Legacy Anchor");

    await expect(page.locator('.portal-section-rail-link[aria-current="page"]')).toHaveText("Deliverables");
  });

  test("approved Project hub never asks the customer to finalize or resubmit intake", async ({ page }) => {
    await openSection(page, "project");

    const intake = page.locator(".portal-section-card").filter({ hasText: "Intake record" });
    await expect(intake.locator(".portal-section-state")).toHaveText("Approved");
    await expect(intake).toContainText("without resubmitting it");
    await expect(page.getByText(/finalize your intake/i)).toHaveCount(0);

    const materials = page.locator(".portal-section-card").filter({ hasText: "Production materials" });
    await expect(materials.locator(".portal-section-state")).toHaveText("Current step");
  });

  test("mobile section navigation stays domain-based and scroll-safe", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openSection(page, "deliverables");

    await expect(page.locator(".portal-section-rail")).toBeHidden();
    const menu = page.locator(".menu-toggle");
    await expect(menu).toBeVisible();
    await menu.click();

    const nav = page.locator("#site-nav");
    await expect(nav.getByText("Home", { exact: true })).toBeVisible();
    await expect(nav.getByText("My Project", { exact: true })).toBeVisible();
    await expect(nav.getByText("Family", { exact: true })).toBeVisible();
    await expect(nav.getByText("Uploads", { exact: true })).toBeVisible();
    await expect(nav.getByText("Vault", { exact: true })).toBeVisible();
    await expect(nav.getByText("Deliverables", { exact: true })).toBeVisible();
    await expect(nav.getByText("Account", { exact: true })).toBeVisible();
    await expect(nav.getByText("Support", { exact: true })).toBeVisible();

    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });

  test("intake API failure is shown as unavailable instead of false Not started state", async ({ page }) => {
    await openSection(page, "project", { intakeStatus: 500 });

    await expect(page.locator("[data-portal-section-message]")).toContainText(
      "Unable to load this workspace section",
    );
    await expect(page.locator(".portal-section-card")).toHaveCount(0);
    await expect(page.getByText("Not started", { exact: true })).toHaveCount(0);
  });
});
