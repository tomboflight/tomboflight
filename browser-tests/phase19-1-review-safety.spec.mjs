import { expect, test } from "@playwright/test";


const BLOCKED_REVIEW_ITEM = {
  id: "upload-phase19-1-blocked",
  member_name: "Review Safety Fixture",
  family_name: "Fixture Family",
  original_filename: "legacy-record.pdf",
  verification_type: "government_id",
  scan_status: "pending",
  quarantined: false,
  durable_private_storage: false,
  preview_available: false,
  preview_blockers: [
    "security_scan_not_clean",
    "durable_private_storage_missing",
  ],
  preview_blocker_message:
    "Run the security scan and obtain a clean verdict before previewing this file. Private storage migration must complete before preview.",
  possible_duplicate: true,
  possible_duplicate_count: 2,
  consent_attested: false,
  authority_attested: false,
  orphaned_project_reference: false,
  orphaned_family_reference: false,
  orphaned_member_reference: false,
};


test("[phase19.1 review safety] blocks unsafe portrait and evidence previews with exact remediation", async ({ page }) => {
  let previewRequests = 0;
  await page.addInitScript(() => {
    localStorage.setItem("tol_access_token", "phase19-1-review-fixture");
    localStorage.setItem("tol_api_base_url", window.location.origin);
  });
  await page.route("**/*", async (route) => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.pathname === "/auth/me") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "ceo-fixture",
          email: "ceo.fixture@tomboflight.test",
          role: "ceo_master_admin",
        }),
      });
    }
    if (requestUrl.pathname === "/uploads/admin/review") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          raw_count: 1,
          duplicates_suppressed: 0,
          items: [BLOCKED_REVIEW_ITEM],
        }),
      });
    }
    if (/\/uploads\/[^/]+\/admin-preview$/.test(requestUrl.pathname)) {
      previewRequests += 1;
      return route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Preview must remain blocked." }),
      });
    }
    return route.continue();
  });

  await page.goto("/admin-portrait-review.html");
  const portraitPreview = page.getByRole("button", { name: "Preview Blocked" });
  await expect(portraitPreview).toBeDisabled();
  await expect(page.locator("[data-preview-blockers]")).toContainText(
    "Private storage migration must complete before preview",
  );
  await expect(page.locator("[data-review-list]")).toContainText(
    "2 distinct upload records",
  );

  await page.goto("/admin-verification-review.html");
  const evidencePreview = page.getByRole("button", { name: "Preview Blocked" });
  await expect(evidencePreview).toBeDisabled();
  await expect(page.locator("[data-evidence-preview-blockers]")).toContainText(
    "clean verdict",
  );
  await expect(page.locator("[data-verification-review-list]")).toContainText(
    "2 distinct upload records",
  );
  expect(previewRequests).toBe(0);
});
