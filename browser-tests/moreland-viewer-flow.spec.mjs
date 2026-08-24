import { expect, test } from "@playwright/test";


test("Moreland autoplay traverses the complete family tree without looping at Malik's parents", async ({ page }) => {
  await page.addInitScript(() => {
    let intervalId = 0;
    const callbacks = [];

    window.setInterval = (callback, delay, ...args) => {
      intervalId += 1;
      callbacks.push({ callback, delay, args, intervalId });
      return intervalId;
    };

    window.__runMorelandAutoAdvance = () => {
      const entry = callbacks.find((candidate) => candidate.delay === 5000);
      if (!entry) throw new Error("Moreland autoplay interval was not registered.");
      entry.callback(...entry.args);
    };
  });

  await page.goto("/viewer/?demo=malik-moreland");

  const expectedTitles = [
    "Malik Moreland",
    "Elias Moreland + Clara Moreland",
    "Malik Moreland",
    "Malik Descendants",
    "Imani Benton / Imani Moreland",
    "Imani Descendants",
    "Elias Moreland + Clara Moreland",
    "Selah Carter",
    "Selah Descendants",
    "Elias Moreland + Clara Moreland",
    "Julian Moreland",
  ];

  for (let index = 0; index < expectedTitles.length; index += 1) {
    await expect(page.locator("#viewerTitle")).toHaveText(expectedTitles[index]);
    await expect(page.locator(`[data-path-index="${index}"]`)).toHaveClass(/is-current/);
    await page.waitForTimeout(200);
    if (index < expectedTitles.length - 1) {
      await page.evaluate(() => window.__runMorelandAutoAdvance());
    }
  }
});
