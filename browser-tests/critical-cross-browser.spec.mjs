import { expect, test } from "@playwright/test";


test.describe("critical customer entry points", () => {
  test("sign-in gateway remains visible and keyboard operable", async ({ page }) => {
    const response = await page.goto("/signin.html", {
      waitUntil: "domcontentloaded",
    });

    expect(response).not.toBeNull();
    expect(response.ok()).toBeTruthy();

    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Enter the private Tomb of Light portal.",
      }),
    ).toBeVisible();

    const email = page.locator('input[name="email"]');
    const password = page.locator('input[name="password"]');
    const submit = page.locator("[data-submit-btn]");

    await expect(email).toBeVisible();
    await expect(password).toBeVisible();
    await expect(submit).toBeVisible();

    await email.focus();
    await expect(email).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(password).toBeFocused();
  });

  test("Moreland demo viewer loads and completes core navigation", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.setInterval = () => 1;
      window.clearInterval = () => undefined;
    });

    const response = await page.goto("/viewer/?demo=malik-moreland");

    expect(response).not.toBeNull();
    expect(response.ok()).toBeTruthy();

    const viewerTitle = page.locator("#viewerTitle");
    await expect(viewerTitle).toHaveText("Malik Moreland");
    await expect(page.locator("#navRightBtn")).toBeVisible();
    await expect(page.locator("#resetViewerBtn")).toBeVisible();

    await page.waitForTimeout(200);
    await page.locator("#navRightBtn").click();
    await expect(viewerTitle).toHaveText("Malik Descendants");

    await page.waitForTimeout(200);
    await page.locator("#resetViewerBtn").click();
    await expect(viewerTitle).toHaveText("Malik Moreland");
  });
});
