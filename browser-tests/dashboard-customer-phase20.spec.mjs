import { expect, test } from "@playwright/test";

const RAKIM = {
  _id: "rakim-customer-1",
  id: "rakim-customer-1",
  email: "rakim.fixture@tomboflight.test",
  full_name: "Rakim Customer Fixture",
  role: "user",
  account_type: "customer",
  status: "active",
};

async function seedRakimSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, RAKIM);
}

async function installRakimDashboardRoutes(page) {
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

    if (method === "GET" && path === "/auth/me") {
      return json(RAKIM);
    }
    if (method === "GET" && path === "/orders/my-orders") {
      return json([]);
    }
    if (method === "GET" && path === "/users/me/workspace-context") {
      return json({
        status: "active",
        workspace: {
          project_id: "project-rakim",
          project_name: "Rakim Customer Legacy Project",
          lane: "portrait",
        },
        package: {
          code: "digital_legacy_portrait",
          display_name: "Digital Legacy Portrait",
          lane: "portrait",
          status: "active",
        },
        entitlements: {
          package_code: "digital_legacy_portrait",
          package_lane: "portrait",
          can_upload_portraits: true,
          can_upload_verification_docs: true,
          can_manage_link_keys: true,
          can_use_link_keys: true,
          can_use_viewer: true,
          can_use_secure_share_viewer: true,
        },
      });
    }
    if (method === "GET" && path === "/workspace-access/my-memberships") {
      return json({
        items: [
          {
            project_id: "project-rakim",
            user_id: RAKIM.id,
            email: RAKIM.email,
            member_role: "billing_owner",
            status: "active",
          },
        ],
      });
    }
    if (method === "GET" && path === "/intake-submissions/my-latest") {
      return json({ detail: "No intake submissions found" }, 404);
    }
    if (method === "GET" && path === "/intake-submissions/my-list") {
      return json([]);
    }
    if (method === "GET" && path === "/projects/project-rakim/mint-eligibility") {
      return json({
        eligible: false,
        reasons: ["profile_not_complete"],
        missing_approvals: [],
      });
    }
    if (method === "GET" && path === "/projects/project-rakim/mint-status") {
      return json({ latest: null, items: [] });
    }
    if (method === "POST" && path === "/auth/logout") {
      return json({ ok: true });
    }

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

test.describe("Phase 20 premium customer dashboard", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("puts Rakim's next action first and keeps supporting detail collapsed", async ({ page }) => {
    await seedRakimSession(page);
    await installRakimDashboardRoutes(page);
    await page.goto("/dashboard.html", { waitUntil: "networkidle" });

    await expect(page.locator("[data-dashboard-first-name]")).toHaveText("Rakim");
    await expect(page.locator("[data-dashboard-hero-title]")).toHaveText("Your Portrait Chamber");
    await expect(page.locator("[data-dashboard-status]")).toContainText(
      "Your package is active: Digital Legacy Portrait",
    );
    await expect(page.locator("#dashboard-primary-actions")).toBeVisible();
    await expect(page.locator("[data-workspace-action-bar] [data-dashboard-hero-action]")).toHaveCount(1);

    const overview = page.locator(".portal-workspace-overview-disclosure");
    const tools = page.locator(".portal-tools-access-panel");
    await expect(overview).not.toHaveAttribute("open", "");
    await expect(tools).not.toHaveAttribute("open", "");

    await tools.locator("summary").click();
    await expect(tools).toHaveAttribute("open", "");
    await expect(tools.locator('[data-dashboard-tool="link_keys"] .portal-action-status')).toHaveText("Open");

    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });

  test("opens the governed Legacy Anchor section when the hash targets it", async ({ page }) => {
    await seedRakimSession(page);
    await installRakimDashboardRoutes(page);
    await page.goto("/dashboard.html#legacy-anchor", { waitUntil: "networkidle" });

    await expect(page.locator("#legacy-anchor")).toHaveAttribute("open", "");
    await expect(page.locator("[data-anchor-status-badge]")).toHaveText("Finish Profile First");
    await expect(page.locator("[data-nft-addon-purchase-panel]")).toContainText(
      "No base package includes an NFT.",
    );
  });
});
