import { expect, test } from "@playwright/test";

const PACKAGES = [
  "legacy_snapshot",
  "legacy_portrait_intro",
  "digital_legacy_portrait",
  "household_foundation",
  "heirloom_legacy_tree",
  "legacy_plus",
  "family_estate_concierge",
  "command_structure_network",
];

function json(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

test.describe("secure private event access", () => {
  test("public page requires a one-time fragment and never renders an offer value", async ({ page }) => {
    let submitted = null;
    await page.route("**/*", async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname.replace(/^\/api-gateway/, "");
      if (request.method() === "GET" && path === "/health") {
        return json(route, { status: "ok" });
      }
      if (request.method() === "POST" && path === "/bridge-events/paint/access/request") {
        submitted = request.postDataJSON();
        return json(route, {
          success: true,
          message:
            "If this invitation is valid and matches the invited email address, the private event offer will be sent to that mailbox.",
        });
      }
      return route.continue();
    });

    await page.goto("/bridge-paint.html", { waitUntil: "load" });
    await expect(page.locator("[data-bridge-paint-access-submit]")).toBeDisabled();
    await expect(page.locator("body")).not.toContainText(/BRIDGE-PAINT-[A-Z0-9]/);

    const token = "tolbe_browser_fixture_with_enough_entropy_123456";
    await page.goto(`/bridge-paint.html#invite=${token}`, { waitUntil: "load" });
    await expect(page).not.toHaveURL(/#invite=/);
    await page.getByLabel("Invited Email Address").fill("invitee@example.test");
    await page.getByRole("button", { name: "Request My Private Offer" }).click();

    await expect(page.locator("[data-bridge-paint-access-status]")).toContainText(
      "private event offer will be sent",
    );
    expect(submitted).toEqual({ email: "invitee@example.test", access_token: token });
    expect(
      await page.evaluate(() => sessionStorage.getItem("tol_bridge_paint_invite_token")),
    ).toBeNull();
  });

  test("CEO console receives readiness and delivery state but no protected value", async ({ page }) => {
    const admin = {
      id: "ceo-fixture",
      _id: "ceo-fixture",
      email: "ceo@example.test",
      role_codes: ["ceo_master_admin"],
    };
    const records = [];
    let createRequest = null;
    await page.addInitScript((user) => {
      localStorage.setItem("tol_access_token", "secure-event-admin-fixture");
      localStorage.setItem("tol_user", JSON.stringify(user));
    }, admin);
    await page.route("**/*", async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname.replace(/^\/api-gateway/, "");
      if (request.method() === "GET" && path === "/health") {
        return json(route, { status: "ok" });
      }
      if (request.method() === "GET" && path === "/auth/me") {
        return json(route, admin);
      }
      if (request.method() === "GET" && path === "/bridge-events/paint/invitations") {
        return json(route, {
          configuration: {
            configured: true,
            configured_packages: PACKAGES,
            required_packages: PACKAGES,
            expires_at: "2026-08-30T03:59:00Z",
            configuration_error: null,
          },
          count: records.length,
          items: records,
        });
      }
      if (request.method() === "POST" && path === "/bridge-events/paint/invitations") {
        createRequest = request.postDataJSON();
        records.unshift({
          id: "invitation-fixture",
          email: createRequest.email,
          package_code: createRequest.package_code,
          package_name: "Legacy Snapshot",
          status: "delivered",
          invitation_delivery_status: "sent",
          promotion_delivery_status: "not_requested",
          created_at: "2026-08-28T12:00:00Z",
          expires_at: "2026-08-30T03:59:00Z",
        });
        return json(route, records[0], 201);
      }
      return route.continue();
    });

    await page.goto("/admin-event-access.html", { waitUntil: "load" });
    await expect(page.locator("[data-admin-event-configuration]")).toContainText(
      "All 8 package values are protected",
    );
    await expect(page.locator("[data-admin-event-send]")).toBeEnabled();
    await page.getByLabel("Invited Email Address").fill("invitee@example.test");
    await page.getByLabel("Selected Package", { exact: true }).selectOption("legacy_snapshot");
    await page.getByLabel("Internal Reason").fill("Verified Event 2 guest registration");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Send Secure Invitation" }).click();

    await expect(page.locator("[data-admin-event-action-status]")).toContainText(
      "Secure invitation sent",
    );
    expect(createRequest).toEqual({
      email: "invitee@example.test",
      package_code: "legacy_snapshot",
      reason: "Verified Event 2 guest registration",
      confirmed: true,
    });
    expect(JSON.stringify(createRequest)).not.toContain("promotion_code");
    expect(JSON.stringify(createRequest)).not.toContain("access_token");
  });
});
