import { expect, test } from "@playwright/test";

const CUSTOMER = {
  id: "step5-customer",
  _id: "step5-customer",
  email: "customer@example.com",
  full_name: "Customer Example",
  role: "user",
  account_type: "customer",
  status: "active",
  mfa_enabled: false,
};

async function seedSession(page) {
  await page.addInitScript((user) => {
    const currentPage = window.location.pathname.split("/").pop() || "";
    if (currentPage !== "account-security.html") return;
    localStorage.setItem("tol_access_token", "step5-fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, CUSTOMER);
}

async function routeAccountApis(page, { activityItems = null } = {}) {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const resourceType = request.resourceType();
    if (["document", "script", "stylesheet", "image", "font"].includes(resourceType)) {
      return route.continue();
    }

    const url = new URL(request.url());
    const path = url.pathname
      .replace(/^\/api-gateway/, "")
      .replace(/^\/direct-api/, "");
    const method = request.method();
    const json = (payload, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });

    if (method === "GET" && path === "/health") return json({ status: "ok" });
    if (method === "GET" && path === "/auth/me") return json(CUSTOMER);
    if (method === "GET" && path === "/users/me/profile") {
      return json({
        ...CUSTOMER,
        created_at: "2026-08-28T00:00:00Z",
        billing_sync_status: "synced",
        legal_acceptance: {},
      });
    }
    if (method === "GET" && path === "/users/me/workspace-context") {
      return json({
        status: "active",
        workspace: {
          project_id: "project-1",
          project_name: "Robinson Family Legacy Production Build",
          family_id: "family-1",
          family_name: "Robinson Family Legacy",
        },
        package: {
          code: "legacy_plus",
          display_name: "Legacy Plus",
        },
        membership: {
          member_role: "billing_owner",
        },
      });
    }
    if (method === "GET" && path === "/users/me/security-activity") {
      return json({
        items:
          activityItems === null
            ? [
                {
                  action: "password_reset_completed",
                  label: "Password reset completed",
                  result: "success",
                  timestamp: "2026-09-07T01:00:00Z",
                },
                {
                  action: "mfa_enrollment_verified",
                  label: "Authenticator MFA enabled",
                  result: "success",
                  timestamp: "2026-09-06T23:00:00Z",
                },
              ]
            : activityItems,
      });
    }
    if (method === "POST" && path === "/auth/logout") return json({ success: true });
    return json({});
  });
}

test.describe("Step 5 customer account completeness", () => {
  test("renders authoritative account/workspace summary and safe security activity", async ({ page }) => {
    await seedSession(page);
    await routeAccountApis(page);

    await page.goto("/account-security.html", { waitUntil: "load" });

    await expect(page.locator("[data-summary-account-status]")).toHaveText("Active");
    await expect(page.locator("[data-summary-email]")).toHaveText("customer@example.com");
    await expect(page.locator("[data-summary-package]")).toHaveText("Legacy Plus");
    await expect(page.locator("[data-summary-project]")).toHaveText(
      "Robinson Family Legacy Production Build",
    );
    await expect(page.locator("[data-summary-family]")).toHaveText("Robinson Family Legacy");
    await expect(page.locator("[data-summary-member-role]")).toHaveText("Billing Owner");
    await expect(page.locator("[data-summary-billing-sync]")).toHaveText("Synced");

    const activity = page.locator("[data-security-activity-list]");
    await expect(activity).toContainText("Password reset completed");
    await expect(activity).toContainText("Authenticator MFA enabled");
    await expect(activity).not.toContainText("token");
    await expect(activity).not.toContainText("203.0.113");

    const requestLink = page.locator("[data-account-data-requests-link]");
    await expect(requestLink).toHaveAttribute("href", "data-request.html");
    await expect(page.locator("[data-security-activity-panel]")).toContainText(
      "does not immediately erase your account",
    );
  });

  test("renders a clean empty security-activity state", async ({ page }) => {
    await seedSession(page);
    await routeAccountApis(page, { activityItems: [] });

    await page.goto("/account-security.html", { waitUntil: "load" });

    await expect(page.locator("[data-security-activity-status]")).toHaveText(
      "No recent security activity is available for this account.",
    );
    await expect(page.locator("[data-security-activity-list]")).toBeEmpty();
  });
});
