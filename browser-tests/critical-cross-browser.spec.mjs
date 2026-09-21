import { expect, test } from "@playwright/test";


test.describe("critical customer entry points", () => {
  test("sign-in gateway supports the primary input method", async ({ page }, testInfo) => {
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
    const submit = page.getByRole("button", {
      name: "Enter Private Portal",
      exact: true,
    });

    await expect(email).toBeVisible();
    await expect(password).toBeVisible();
    await expect(submit).toBeVisible();

    await email.focus();
    await expect(email).toBeFocused();

    if (testInfo.project.name === "webkit-mobile-critical") {
      await password.tap();
    } else {
      await page.keyboard.press("Tab");
    }
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
    const navigateToParents = page.locator("#navLeftBtn");
    const navigateToDescendants = page.locator("#navRightBtn");
    const resetViewer = page.locator("#resetViewerBtn");

    await expect(viewerTitle).toHaveText("Malik Moreland");
    await expect(navigateToParents).toBeVisible();
    await expect(navigateToDescendants).toBeVisible();
    await expect(resetViewer).toBeHidden();

    await page.waitForTimeout(200);
    await navigateToDescendants.click();
    await expect(viewerTitle).toHaveText("Malik Descendants");
    await expect(resetViewer).toBeHidden();

    await page.waitForTimeout(200);
    await navigateToParents.click();
    await expect(viewerTitle).toHaveText("Malik Moreland");
    await expect(resetViewer).toBeHidden();
  });
});
