import { expect, test } from "@playwright/test";


const CUSTOMER = {
  id: "vault-customer-1",
  _id: "vault-customer-1",
  email: "vault.customer@tomboflight.test",
  full_name: "Vault Customer",
  role: "user",
  status: "active",
};

const ONE_PIXEL_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);


async function seedCustomerSession(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "vault-phase22-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
    localStorage.setItem("tol_api_base_url", window.location.origin);
  }, CUSTOMER);
}


async function installVaultRoutes(page) {
  let deleted = false;
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

    if (path === "/health") return json({ status: "ok", ready: true });
    if (method === "GET" && path === "/auth/me") return json(CUSTOMER);
    if (method === "GET" && path === "/orders/my-orders") return json([]);
    if (method === "GET" && path === "/users/me/workspace-context") {
      return json({
        status: "active",
        workspace: {
          project_id: "project-vault-1",
          project_name: "Vault Family Project",
          family_id: "family-vault-1",
          lane: "household",
        },
        package: {
          code: "legacy_plus",
          display_name: "Legacy Plus",
          lane: "household",
          status: "active",
        },
        entitlements: {
          package_code: "legacy_plus",
          package_lane: "household",
          can_use_personal_vault: true,
          can_use_household_vault: true,
          can_use_future_message_vault: true,
          can_use_scheduled_reveal: true,
        },
      });
    }
    if (method === "GET" && path === "/families/") {
      return json([{ _id: "family-vault-1", family_name: "Vault Family" }]);
    }
    if (method === "GET" && path === "/families/family-vault-1/graph") {
      return json({
        members: [
          { _id: "member-vault-1", first_name: "Avery", last_name: "Vault" },
        ],
      });
    }
    if (method === "GET" && path === "/uploads/vault/family/family-vault-1") {
      return json({
        family_id: "family-vault-1",
        count: deleted ? 0 : 1,
        items: deleted
          ? []
          : [
              {
                id: "upload-vault-photo-2",
                member_id: "member-vault-1",
                original_filename: "family-photo.png",
                category: "private_media",
                asset_type: "vault_photo",
                privacy_scope: "private_to_owner",
                content_type: "image/png",
                size_bytes: 128,
                uploaded_by: "Vault Customer",
                created_at: "2026-08-29T12:00:00Z",
                scan_status: "clean",
                release_state: "released",
                version: 2,
                root_upload_id: "upload-vault-photo-1",
                is_current_version: true,
                permissions: {
                  can_preview: true,
                  can_download: true,
                  can_replace: true,
                  can_delete: true,
                  can_change_privacy: true,
                  can_manage: true,
                },
              },
            ],
      });
    }
    if (method === "GET" && path === "/uploads/upload-vault-photo-2/preview") {
      expect(request.headers().authorization).toBe("Bearer vault-phase22-token");
      return route.fulfill({ status: 200, contentType: "image/png", body: ONE_PIXEL_PNG });
    }
    if (method === "GET" && path === "/uploads/upload-vault-photo-2/versions") {
      return json({
        root_upload_id: "upload-vault-photo-1",
        count: 2,
        versions: [
          {
            id: "upload-vault-photo-2",
            version: 2,
            is_current_version: true,
            original_filename: "family-photo.png",
            created_at: "2026-08-29T12:00:00Z",
            scan_status: "clean",
          },
          {
            id: "upload-vault-photo-1",
            version: 1,
            is_current_version: false,
            original_filename: "family-photo-old.png",
            created_at: "2026-08-28T12:00:00Z",
            scan_status: "clean",
          },
        ],
      });
    }
    if (method === "DELETE" && path === "/uploads/upload-vault-photo-2") {
      deleted = true;
      return route.fulfill({ status: 204, body: "" });
    }
    if (method === "POST" && path === "/auth/logout") return json({ ok: true });

    if (
      path.startsWith("/auth/") ||
      path.startsWith("/orders/") ||
      path.startsWith("/users/") ||
      path.startsWith("/workspace-access/") ||
      path.startsWith("/project-entitlements/") ||
      path.startsWith("/projects/") ||
      path.startsWith("/intake-submissions/")
    ) {
      return json({ items: [] });
    }
    return route.continue();
  });
}


test("customer securely previews, versions, and deletes a Vault photo", async ({ page }) => {
  await seedCustomerSession(page);
  await installVaultRoutes(page);
  await page.goto("/vault-upload.html?family_id=family-vault-1", {
    waitUntil: "networkidle",
  });

  await page.locator("[data-vault-list-member]").selectOption("member-vault-1");
  await page.locator("[data-vault-load-uploads]").click();

  const card = page.locator('[data-vault-upload-card="upload-vault-photo-2"]');
  await expect(card).toBeVisible();
  await expect(card).toContainText("Version: 2 — current");
  await expect(card.locator("[data-vault-secure-image-id]")).toBeVisible();
  await expect(card.getByRole("button", { name: "Replace with New Version" })).toBeVisible();
  await expect(card.getByRole("button", { name: "Delete" })).toBeVisible();

  await card.getByRole("button", { name: "Version History" }).click();
  const dialog = page.locator("[data-vault-preview-dialog]");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Version 2 — current");
  await expect(dialog).toContainText("Version 1");
  await dialog.getByRole("button", { name: "Close" }).click();

  page.once("dialog", (confirmation) => confirmation.accept());
  await card.getByRole("button", { name: "Delete" }).click();
  await expect(page.locator('[data-vault-upload-card="upload-vault-photo-2"]')).toHaveCount(0);
  await expect(page.locator("[data-vault-uploads-empty]")).toBeVisible();
});
