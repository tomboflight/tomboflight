import { expect, test } from "@playwright/test";


test.describe("Phase 15 NFT add-on mint flow", () => {
  test.use({ javaScriptEnabled: false });

  test("public pricing cannot bypass delivered-profile checkout gate", async ({ page }) => {
    await page.goto("/pricing.html");

    const nftLinks = page.locator("[data-nft-addon-catalog-link]");
    await expect(nftLinks).toHaveCount(3);
    for (const link of await nftLinks.all()) {
      await expect(link).toHaveAttribute("href", /dashboard\.html#legacy-anchor$/);
      await expect(link).not.toHaveAttribute("href", /buy\.stripe\.com/);
    }
    await expect(page.locator("[data-nft-addon-catalog-link='nft_lineage_record']").locator("xpath=..")).toContainText("$499 one-time");
    await expect(page.locator("[data-nft-addon-catalog-link='additional_nft_copy_mint']").locator("xpath=..")).toContainText("$399 one-time");
    await expect(page.locator("[data-nft-addon-catalog-link='nft_metadata_revision']").locator("xpath=..")).toContainText("$149 one-time");
  });

  test("customer dashboard contains gated purchase and own-wallet consent controls", async ({ page }) => {
    await page.goto("/dashboard.html#legacy-anchor");

    await expect(page.locator("[data-nft-addon-checkout='nft_lineage_record']")).toHaveCount(1);
    await expect(page.locator("[data-nft-addon-checkout='additional_nft_copy_mint']")).toHaveCount(1);
    await expect(page.locator("[data-nft-addon-checkout='nft_metadata_revision']")).toHaveCount(1);
    await expect(page.locator("[data-nft-customer-wallet]")).toHaveAttribute("placeholder", "0x...");
    await expect(page.locator("[data-nft-public-safe-consent]")).toHaveCount(1);
    await expect(page.locator("[data-nft-addon-purchase-panel]")).toContainText(
      "No base package includes an NFT.",
    );
  });

  test("CEO console exposes separate governed preparation approval and queue steps", async ({ page }) => {
    await page.goto("/admin-control-center.html");

    await expect(page.locator("[data-admin-case-action='queue_for_mint_review']")).toHaveText("Open Mint Review");
    await expect(page.locator("[data-admin-case-action='prepare_legacy_anchor']")).toHaveText("Prepare NFT Approval");
    await expect(page.locator("[data-admin-case-action='approve_legacy_anchor']")).toHaveText("CEO Final Approve");
    await expect(page.locator("[data-admin-case-action='queue_approved_legacy_anchor']")).toHaveText("Queue Approved NFT");
  });
});
