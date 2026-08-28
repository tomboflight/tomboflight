import { expect, test } from "@playwright/test";

test.describe("Phase 21.1 mobile recovery", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("mobile navigation remains vertically scrollable", async ({ page }) => {
    await page.goto("/signup.html", { waitUntil: "load" });
    await page.getByRole("button", { name: "Toggle navigation menu" }).click();

    const state = await page.evaluate(() => ({
      bodyOverflowY: window.getComputedStyle(document.body).overflowY,
      headerPosition: window.getComputedStyle(
        document.querySelector(".site-header"),
      ).position,
      menuOpen: document.body.classList.contains("menu-open"),
      scrollHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight,
    }));

    expect(state.menuOpen).toBe(true);
    expect(state.bodyOverflowY).not.toBe("hidden");
    expect(state.headerPosition).toBe("relative");
    expect(state.scrollHeight).toBeGreaterThan(state.viewportHeight);

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  });

  test("account recovery chooses one secure endpoint without exposing state", async ({ page }) => {
    let recoveryRequests = 0;
    await page.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (request.method() === "GET" && url.pathname === "/health") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "ok" }),
        });
      }
      if (request.method() === "GET" && url.pathname === "/auth/me") {
        return route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "No active session." }),
        });
      }
      if (
        request.method() === "POST" &&
        url.pathname.endsWith("/auth/account-recovery/request")
      ) {
        recoveryRequests += 1;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true,
            message:
              "If this email is connected to an account, the appropriate secure access link has been sent.",
          }),
        });
      }
      return route.continue();
    });

    await page.goto("/account-security.html#reset-request", { waitUntil: "load" });
    await page.getByLabel("Email Address").fill("fixture@example.test");
    await page.getByRole("button", { name: "Recover Account Access" }).click();

    await expect(page.locator("[data-password-reset-request-status]")).toContainText(
      "appropriate secure access link",
    );
    expect(recoveryRequests).toBe(1);
  });
});
