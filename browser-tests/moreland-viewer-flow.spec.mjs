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


test("customer family manifests autoplay every approved portrait without requiring narration", async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("tol_access_token", "phase16-test-token");
    let intervalId = 0;
    const callbacks = [];
    window.setInterval = (callback, delay, ...args) => {
      intervalId += 1;
      callbacks.push({ callback, delay, args, intervalId });
      return intervalId;
    };
    window.__runFamilyAutoAdvance = () => {
      const entry = callbacks.find((candidate) => candidate.delay === 5000);
      if (!entry) throw new Error("Customer family autoplay interval was not registered.");
      entry.callback(...entry.args);
    };
  });

  const pixel =
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
  await page.route("**/viewer/manifest?*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        mode: "dynamic",
        navigation_mode: "graph",
        hero_title: "Private Family Viewer",
        path_items: ["Anchor", "Parent", "Return to Anchor", "Child"],
        auto_advance_state_ids: [
          "member-anchor",
          "member-parent",
          "member-anchor",
          "member-child",
        ],
        initial_state_id: "member-anchor",
        controls: {
          allow_lineage_navigation: true,
          allow_zoom: true,
          allow_reset: true,
          allow_auto_advance: true,
          allow_narration_auto_advance: false,
          allow_gaze_navigation: true,
          allow_branch_navigation: true,
          max_zoom_layers: 2,
        },
        branch_options_by_state: {
          "member-anchor": [
            {
              label: "Child / descendant: Child",
              target_state_id: "member-child",
            },
          ],
        },
        states: [
          {
            id: "member-anchor",
            image: pixel,
            title: "Anchor",
            node: "Anchor",
            description: "Anchor description",
            narration: "Paid narration is disabled.",
            left_state_id: "member-parent",
            right_state_id: "member-child",
          },
          {
            id: "member-parent",
            image: pixel,
            title: "Parent",
            node: "Parent",
            left_state_id: "",
            right_state_id: "member-anchor",
          },
          {
            id: "member-child",
            image: pixel,
            title: "Child",
            node: "Child",
            left_state_id: "member-anchor",
            right_state_id: "",
          },
        ],
      }),
    });
  });

  await page.goto("/viewer/?project_id=phase16-family");

  const expectedTitles = ["Anchor", "Parent", "Anchor", "Child"];
  for (let index = 0; index < expectedTitles.length; index += 1) {
    await expect(page.locator("#viewerTitle")).toHaveText(expectedTitles[index]);
    await expect(page.locator(`[data-path-index="${index}"]`)).toHaveClass(/is-current/);
    await expect(page.locator("#narrationDisplay")).toHaveCSS("opacity", "0");
    if (index < expectedTitles.length - 1) {
      await page.evaluate(() => window.__runFamilyAutoAdvance());
      await page.waitForTimeout(200);
    }
  }

  await expect(page.locator("#narrationToggleBtn")).toHaveText("Slideshow: ON");
});


test("dynamic graph zoom controls navigate lineage and pause customer autoplay", async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("tol_access_token", "phase16-test-token");
  });
  const pixel =
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
  await page.route("**/viewer/manifest?*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        mode: "dynamic",
        navigation_mode: "graph",
        path_items: ["Anchor", "Child"],
        auto_advance_state_ids: ["member-anchor", "member-child"],
        initial_state_id: "member-anchor",
        controls: {
          allow_lineage_navigation: true,
          allow_zoom: true,
          allow_reset: true,
          allow_auto_advance: true,
          allow_narration_auto_advance: false,
          allow_gaze_navigation: true,
          allow_branch_navigation: true,
          max_zoom_layers: 2,
        },
        states: [
          {
            id: "member-anchor",
            image: pixel,
            title: "Anchor",
            node: "Anchor",
            right_state_id: "member-child",
          },
          {
            id: "member-child",
            image: pixel,
            title: "Child",
            node: "Child",
            left_state_id: "member-anchor",
          },
        ],
      }),
    });
  });

  await page.goto("/viewer/?project_id=phase16-graph");
  await expect(page.locator("#viewerTitle")).toHaveText("Anchor");
  await page.locator("#zoomInBtn").click();
  await expect(page.locator("#viewerTitle")).toHaveText("Child");
  await expect(page.locator("#narrationToggleBtn")).toHaveText(
    "Resume Slideshow",
  );
  await page.locator("#zoomOutBtn").click();
  await expect(page.locator("#viewerTitle")).toHaveText("Anchor");
});
