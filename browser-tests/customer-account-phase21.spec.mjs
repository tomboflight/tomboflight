import { expect, test } from "@playwright/test";

const CUSTOMER = {
  id: "phase21-customer",
  _id: "phase21-customer",
  email: "customer@example.com",
  full_name: "Customer Example",
  role: "user",
  account_type: "customer",
  status: "active",
};

async function seedCustomerSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "phase21-fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, CUSTOMER);
}

test.describe("Phase 21 customer account management", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("updates structured contact details and requests verified email replacement", async ({ page }) => {
    const requests = [];
    await seedCustomerSession(page);
    await page.route("https://js.stripe.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "application/javascript", body: "" }),
    );
    await page.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api-gateway/, "");
      const method = request.method();
      const json = (payload, status = 200) =>
        route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });

      if (method === "GET" && path === "/auth/me") return json(CUSTOMER);
      if (method === "GET" && path === "/users/me/profile") {
        return json({
          ...CUSTOMER,
          created_at: "2026-08-28T00:00:00Z",
          phone_number: "+19125550123",
          mailing_address: {
            line1: "100 Main Street",
            line2: "",
            city: "Savannah",
            region: "GA",
            postal_code: "31401",
            country: "US",
          },
          pending_email: null,
          billing_sync_status: "synced",
          legal_acceptance: {},
        });
      }
      if (method === "PATCH" && path === "/users/me/profile") {
        const body = request.postDataJSON();
        requests.push({ type: "profile", body });
        return json({
          ...CUSTOMER,
          ...body,
          created_at: "2026-08-28T00:00:00Z",
          billing_sync_status: "synced",
          legal_acceptance: {},
        });
      }
      if (method === "POST" && path === "/users/me/email-change/request") {
        const body = request.postDataJSON();
        requests.push({ type: "email", body });
        return json({ success: true, message: "Verification sent to the new email address." });
      }
      if (method === "GET" && path === "/billing/overview") {
        return json({
          customer_id: "cus_fixture",
          max_cards: 3,
          cards_on_file: 0,
          can_add_card: true,
          payment_methods: [],
          subscriptions: [],
        });
      }
      if (method === "GET" && path === "/billing/config") {
        return json({ publishable_key: "", max_cards: 3 });
      }
      if (method === "GET" && path === "/orders/my-orders") return json([]);
      if (method === "POST" && path === "/auth/logout") return json({ ok: true });
      if (path.startsWith("/")) {
        if (request.resourceType() === "document" || ["script", "stylesheet", "image", "font"].includes(request.resourceType())) {
          return route.continue();
        }
        return json({ ok: true });
      }
      return route.continue();
    });

    await page.goto("/billing.html#personal-details", { waitUntil: "load" });
    await expect(page.locator('[name="full_name"]')).toHaveValue("Customer Example");
    await expect(page.locator('[name="address_city"]')).toHaveValue("Savannah");
    await expect(page.locator("[data-account-current-email]")).toHaveText("customer@example.com");

    await page.locator('[name="phone_number"]').fill("(912) 555-0199");
    await page.locator('[name="address_line2"]').fill("Suite 9");
    await page.locator("[data-account-details-save]").click();
    await expect(page.locator("[data-account-details-status]")).toContainText(
      "Personal details saved",
    );

    await page.locator('[name="new_email"]').fill("new@example.com");
    await page.locator('[name="current_password"]').fill("CurrentPassword!123");
    await page.locator("[data-email-change-submit]").click();
    await expect(page.locator("[data-email-change-status]")).toContainText(
      "Verification sent",
    );

    expect(requests[0].body.phone_number).toBe("(912) 555-0199");
    expect(requests[0].body.mailing_address.line2).toBe("Suite 9");
    expect(requests[1].body).toEqual({
      new_email: "new@example.com",
      current_password: "CurrentPassword!123",
    });

    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });
});
