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

test("[dashboard-theme] uses the standard readable light appearance while custom modes are disabled", async ({ page }) => {
  await seedInternalSession(page);
  await installDashboardRoutes(page);
  await page.addInitScript(() => {
    localStorage.setItem("tol_admin_appearance_default", JSON.stringify({ theme: "high-contrast", textScale: "large" }));
  });
  await page.goto("/dashboard.html", { waitUntil: "networkidle" });
  await expect(page.locator("[data-admin-tools-panel]")).toBeVisible();
  await expect(page.locator("[data-admin-appearance-toggle]")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("data-admin-theme", "light");
  await expect(page.locator("html")).toHaveAttribute("data-admin-text-scale", "normal");
  const styles = await page.locator("[data-admin-tools-panel]").evaluate((node) => {
    const computed = getComputedStyle(node);
    return { background: computed.backgroundColor, color: computed.color };
  });
  expect(styles.background).not.toBe("rgba(0, 0, 0, 0)");
  expect(styles.color).not.toBe("rgba(0, 0, 0, 0)");
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

test("[asset-versioning] dashboard and control center include current cache-busting revisions", async ({ page }) => {
  await seedInternalSession(page);
  await installDashboardRoutes(page);
  await page.goto("/dashboard.html", { waitUntil: "domcontentloaded" });
  const dashboardScripts = await page.locator("script[src]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("src") || ""),
  );
  const dashboardStyles = await page.locator("link[rel='stylesheet']").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("href") || ""),
  );
  expect(dashboardStyles.some((href) => href.includes("styles.css?v=20260824-phase20"))).toBeTruthy();
  expect(dashboardScripts.some((src) => src.includes("app.js?v=20260825-phase20-1"))).toBeTruthy();
  expect(dashboardScripts.some((src) => src.includes("dashboard-intake.js?v=20260824-phase20"))).toBeTruthy();
  expect(dashboardScripts.some((src) => src.includes("dashboard-admin.js?v=20260713-livefix3"))).toBeTruthy();

  await page.goto("/admin-control-center.html", { waitUntil: "domcontentloaded" });
  const controlCenterScripts = await page.locator("script[src]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("src") || ""),
  );
  const controlCenterStyles = await page.locator("link[rel='stylesheet']").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("href") || ""),
  );
  expect(controlCenterStyles.some((href) => href.includes("styles.css?v=20260821-phase10"))).toBeTruthy();
  expect(controlCenterScripts.some((src) => src.includes("app.js?v=20260825-phase20-1"))).toBeTruthy();
  expect(controlCenterScripts.some((src) => src.includes("admin-control-center.js?v=20260824-phase19-1"))).toBeTruthy();
});
