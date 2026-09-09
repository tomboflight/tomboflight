import { expect, test } from "@playwright/test";

const CUSTOMER = {
  _id: "step9-customer",
  id: "step9-customer",
  email: "step9.customer@tomboflight.test",
  full_name: "Step 9 Customer",
  role: "user",
  account_type: "customer",
  status: "active",
};

const WORKSPACE = {
  status: "active",
  workspace: {
    project_id: "project-step9",
    project_name: "Step 9 Family Legacy",
    family_id: "family-step9",
    lane: "household",
  },
  package: {
    code: "legacy_plus",
    display_name: "Legacy Plus",
    lane: "household",
    status: "paid",
  },
  entitlements: {
    can_upload_portraits: true,
    can_upload_verification_docs: true,
    can_use_household_vault: true,
  },
};

async function seedSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "step9-fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
  }, CUSTOMER);
}

async function installRoutes(page, options = {}) {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (payload, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(payload),
      });

    if (method === "GET" && path === "/auth/me") return json(CUSTOMER);
    if (method === "GET" && path === "/users/me/workspace-context") {
      if (options.workspaceStatus) {
        return json({ detail: "workspace unavailable" }, options.workspaceStatus);
      }
      return json(WORKSPACE);
    }
    if (
      method === "GET" &&
      path === "/uploads/family/family-step9" &&
      url.searchParams.get("category") === "member_photo"
    ) {
      return json({
        uploads: [
          {
            id: "portrait-blocked",
            original_filename: "family.jpg",
            category: "member_photo",
            scan_status: "error",
            verification_status: "pending",
            quarantined: false,
            is_current_version: true,
          },
        ],
      });
    }
    if (
      method === "GET" &&
      path === "/uploads/family/family-step9" &&
      url.searchParams.get("category") === "verification_evidence"
    ) {
      if (options.verificationStatus) {
        return json({ detail: "verification inventory unavailable" }, options.verificationStatus);
      }
      return json({
        uploads: [
          {
            id: "verification-approved",
            original_filename: "birth-record.pdf",
            category: "verification_evidence",
            scan_status: "clean",
            verification_status: "approved",
            is_current_version: true,
          },
        ],
      });
    }
    if (
      method === "GET" &&
      path === "/uploads/vault/project/project-step9" &&
      url.searchParams.get("category") === "private_media"
    ) {
      return json({
        items: [
          {
            id: "vault-2",
            original_filename: "message.mp4",
            category: "private_media",
            scan_status: "clean",
            verification_status: "pending",
            is_current_version: true,
          },
          {
            id: "vault-1",
            original_filename: "voice.mp3",
            category: "private_media",
            scan_status: "clean",
            verification_status: "pending",
            is_current_version: true,
          },
        ],
      });
    }

    if (path.startsWith("/auth/") || path.startsWith("/users/") || path.startsWith("/uploads/")) {
      return json({ ok: true });
    }
    return route.continue();
  });
}

async function openHub(page, options = {}) {
  await seedSession(page);
  await installRoutes(page, options);
  await page.goto("/upload-hub.html", { waitUntil: "networkidle" });
}

test.describe("Step 9 upload infrastructure truth", () => {
  test("Upload Hub reports real lane counts and security state before review state", async ({ page }) => {
    await page.setViewportSize({ width: 960, height: 900 });
    await openHub(page);

    const portrait = page.locator('[data-upload-overview-lane="portraits"]');
    await expect(portrait.locator("[data-upload-overview-state]")).toHaveText("Security blocked");
    await expect(portrait.locator("[data-upload-overview-count]")).toHaveText("1 current file");
    await expect(portrait).toContainText("family.jpg · Security blocked");

    const verification = page.locator('[data-upload-overview-lane="verification"]');
    await expect(verification.locator("[data-upload-overview-state]")).toHaveText("Approved");
    await expect(verification.locator("[data-upload-overview-count]")).toHaveText("1 current file");

    const vault = page.locator('[data-upload-overview-lane="vault"]');
    await expect(vault.locator("[data-upload-overview-state]")).toHaveText("Ready");
    await expect(vault.locator("[data-upload-overview-count]")).toHaveText("2 current files");

    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });

  test("a failed lane is unavailable and is never converted to a fake zero", async ({ page }) => {
    await openHub(page, { verificationStatus: 503 });

    const verification = page.locator('[data-upload-overview-lane="verification"]');
    await expect(verification.locator("[data-upload-overview-state]")).toHaveText("Status unavailable");
    await expect(verification.locator("[data-upload-overview-count]")).toContainText(
      "could not confirm the live file inventory",
    );
    await expect(verification.locator("[data-upload-overview-count]")).not.toContainText("0 current files");
    await expect(page.locator("[data-upload-overview-message]")).toContainText("unavailable lanes");
  });

  test("workspace failure fails closed without fabricated file cards", async ({ page }) => {
    await openHub(page, { workspaceStatus: 503 });

    await expect(page.locator("[data-upload-overview-message]")).toContainText(
      "Unable to confirm the live upload inventory",
    );
    await expect(page.locator("[data-upload-overview-lane]")).toHaveCount(0);
    await expect(page.getByText(/0 current files/i)).toHaveCount(0);
  });

  test("mobile Upload Hub overview stays within the viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openHub(page);

    await expect(page.locator("[data-upload-overview]")).toBeVisible();
    const width = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(width.document).toBeLessThanOrEqual(width.viewport + 1);
  });
});
