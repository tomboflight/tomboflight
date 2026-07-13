import { expect, test } from "@playwright/test";

const LARRY = {
  _id: "larry-ceo-1",
  id: "larry-ceo-1",
  email: "larry@tomboflight.com",
  role: "admin",
  access_tier: "ceo_master_admin",
  department_role: "executive_tech_admin",
  role_codes: ["ceo_master_admin", "executive_tech_admin"],
};

async function installDashboardRoutes(page, options = {}) {
  const state = {
    authMeCalls: 0,
    controlCenterWrites: 0,
    stripeMutations: 0,
    blockchainOps: 0,
  };
  const failFirstAuthMe = Boolean(options.failFirstAuthMe);
  const failAllAuthMe = Boolean(options.failAllAuthMe);
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (!path.startsWith("/auth/") && !path.startsWith("/admin/") && !path.startsWith("/api/") && !path.startsWith("/packages/")) {
      return route.continue();
    }

    const json = (payload, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });

    if (method === "GET" && path === "/auth/me") {
      state.authMeCalls += 1;
      if (failAllAuthMe) {
        return json({ detail: "Session bootstrap failed." }, 500);
      }
      if (failFirstAuthMe && state.authMeCalls === 1) {
        return json({ detail: "Session bootstrap failed." }, 500);
      }
      return json(LARRY);
    }
    if (method === "POST" && path === "/auth/logout") {
      return json({ ok: true });
    }
    if (path.startsWith("/admin/control-center/") && method !== "GET") {
      state.controlCenterWrites += 1;
    }
    if (path.includes("stripe")) {
      state.stripeMutations += 1;
    }
    if (path.includes("mint") && method !== "GET") {
      state.blockchainOps += 1;
    }
    if (method === "GET" && path === "/admin/control-center/access-profile") {
      return json({
        role_key: "ceo_master_admin",
        is_super_admin: true,
        allowed_queues: ["overview", "customer_cases", "users", "orders", "projects", "entitlements", "mint_queue", "upload_review", "billing_maintenance", "audit", "system_health"],
      });
    }
    if (method === "GET" && path === "/admin/control-center/overview") {
      return json({ summary: { total_users: 1, total_active_projects: 1, paid_orders: 1 } });
    }
    if (method === "GET" && path === "/admin/control-center/cases") {
      return json({ items: [] });
    }
    return json({ ok: true });
  });
  return state;
}

async function openAppearancePanel(page) {
  const toggle = page.locator("[data-admin-appearance-toggle]");
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator("[data-admin-appearance-panel]")).toBeVisible();
}

async function seedInternalSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, LARRY);
}

async function seedTokenOnlySession(page) {
  await page.addInitScript(() => {
    localStorage.setItem("tol_access_token", "fixture-token");
  });
}

test("[dashboard-theme] light/dark/high-contrast + larger text change computed styles and persist", async ({ page }, testInfo) => {
  await seedInternalSession(page);
  await installDashboardRoutes(page);
  await page.goto("/dashboard.html", { waitUntil: "networkidle" });
  await expect(page.locator("[data-admin-tools-panel]")).toBeVisible();

  await openAppearancePanel(page);
  const themeSelect = page.locator("[data-admin-appearance-theme]");
  const largeText = page.locator("[data-admin-appearance-large-text]");

  const readStyles = async () =>
    page.evaluate(() => {
      const bodyStyles = window.getComputedStyle(document.body);
      const panel = document.querySelector("[data-admin-tools-panel]") || document.querySelector(".portal-core-panel");
      const panelStyles = panel ? window.getComputedStyle(panel) : bodyStyles;
      const title = document.querySelector(".portal-core-title") || document.body;
      const titleStyles = window.getComputedStyle(title);
      return {
        bodyBg: bodyStyles.backgroundColor,
        bodyFg: bodyStyles.color,
        bodyFont: bodyStyles.fontSize,
        panelBg: panelStyles.backgroundColor,
        panelFg: panelStyles.color,
        fontSize: titleStyles.fontSize,
        lineHeight: titleStyles.lineHeight,
        htmlTheme: document.documentElement.dataset.adminTheme || "",
      };
    });

  await themeSelect.selectOption("light");
  await page.waitForTimeout(120);
  const light = await readStyles();
  await page.screenshot({ path: testInfo.outputPath("dashboard-light.png"), fullPage: true });

  await themeSelect.selectOption("dark");
  await page.waitForTimeout(120);
  const dark = await readStyles();
  await page.screenshot({ path: testInfo.outputPath("dashboard-dark.png"), fullPage: true });

  await themeSelect.selectOption("high-contrast");
  await page.waitForTimeout(120);
  const highContrast = await readStyles();
  await page.screenshot({ path: testInfo.outputPath("dashboard-high-contrast.png"), fullPage: true });

  await largeText.check();
  await page.waitForTimeout(120);
  const largerText = await readStyles();
  await page.screenshot({ path: testInfo.outputPath("dashboard-high-contrast-large.png"), fullPage: true });

  expect(light.bodyBg).not.toBe(dark.bodyBg);
  expect(light.panelBg).not.toBe(dark.panelBg);
  expect(highContrast.htmlTheme).toBe("high-contrast");
  expect(parseFloat(largerText.bodyFont)).toBeGreaterThan(parseFloat(highContrast.bodyFont));
  expect(parseFloat(largerText.lineHeight) || 0).toBeGreaterThan(0);

  await page.reload({ waitUntil: "networkidle" });
  const persisted = await readStyles();
  expect(persisted.htmlTheme).toBe("high-contrast");
  expect(parseFloat(persisted.bodyFont)).toBeGreaterThan(parseFloat(light.bodyFont));
});

test("[dashboard-bootstrap] ceo role resolves tools and workspace nodes", async ({ page }) => {
  await seedInternalSession(page);
  const state = await installDashboardRoutes(page);
  await page.goto("/dashboard.html", { waitUntil: "networkidle" });

  await expect(page.locator("[data-dashboard-next-focus]")).toContainText("Control Center");
  await expect(page.locator("[data-admin-tools-panel]")).toBeVisible();
  await expect(page.locator("a[href$='admin-control-center.html']")).toBeVisible();
  await expect(page.locator("[data-dashboard-identity-node]")).toContainText("Ready");
  await expect(page.locator("[data-dashboard-package-node]")).toContainText("Ready");
  await expect(page.locator("[data-dashboard-records-node]")).toContainText("Ready");

  expect(state.controlCenterWrites).toBe(0);
  expect(state.stripeMutations).toBe(0);
  expect(state.blockchainOps).toBe(0);
});

test("[dashboard-bootstrap-error] failed bootstrap shows actionable error with retry", async ({ page }) => {
  await seedTokenOnlySession(page);
  await installDashboardRoutes(page, { failAllAuthMe: true });
  await page.goto("/dashboard.html", { waitUntil: "networkidle" });

  await page.waitForTimeout(7300);
  await expect(page.locator("[data-dashboard-status]")).toContainText("failed");
  await expect(page.locator("[data-admin-tools-panel]")).toContainText("Admin Workspace Error");
  await expect(page.locator("[data-admin-tools-panel]")).toContainText("Retry");
});

test("[asset-versioning] dashboard and control center include cache-busting livefix revision", async ({ page }) => {
  await seedInternalSession(page);
  await installDashboardRoutes(page);
  await page.goto("/dashboard.html", { waitUntil: "domcontentloaded" });
  const dashboardScripts = await page.locator("script[src]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("src") || ""),
  );
  expect(dashboardScripts.some((src) => src.includes("app.js?v=20260713-livefix1"))).toBeTruthy();
  expect(dashboardScripts.some((src) => src.includes("dashboard-admin.js?v=20260713-livefix1"))).toBeTruthy();

  await page.goto("/admin-control-center.html", { waitUntil: "domcontentloaded" });
  const controlCenterScripts = await page.locator("script[src]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("src") || ""),
  );
  expect(controlCenterScripts.some((src) => src.includes("app.js?v=20260713-livefix1"))).toBeTruthy();
  expect(controlCenterScripts.some((src) => src.includes("admin-control-center.js?v=20260713-livefix1"))).toBeTruthy();
});
