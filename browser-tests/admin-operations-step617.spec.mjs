import { expect, test } from "@playwright/test";

const ADMIN = {
  id: "admin-step617",
  _id: "admin-step617",
  email: "ceo@tomboflight.test",
  full_name: "CEO Administrator",
  role: "admin",
  access_tier: "ceo_master_admin",
  role_codes: ["ceo_master_admin"],
  is_admin: true,
  admin_roles: ["ceo_master_admin"],
  officer_roles: ["ceo_master_admin"],
  admin_permissions: ["admin.control_center.access"],
  dashboard_type: "admin",
  allowed_rails: ["admin"],
  status: "active",
  mfa_enabled: false,
};

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZfGQAAAAASUVORK5CYII=",
  "base64",
);
const PDF = Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n");

function normalizedPath(urlString) {
  return new URL(urlString).pathname
    .replace(/^\/api-gateway/, "")
    .replace(/^\/direct-api/, "");
}

async function seedAdmin(page) {
  await page.addInitScript((user) => {
    localStorage.setItem("tol_access_token", "step617-admin-token");
    localStorage.setItem("tol_user", JSON.stringify(user));
    localStorage.setItem("tol_api_base_url", window.location.origin);
  }, ADMIN);
}

function json(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

async function installControlCenterRoutes(page) {
  const state = { caseListCalls: 0, caseDetailCalls: 0, healthCalls: 0 };
  await page.route("**/*", async (route) => {
    const request = route.request();
    const resourceType = request.resourceType();
    if (["document", "script", "stylesheet", "image", "font"].includes(resourceType)) {
      return route.continue();
    }
    const url = new URL(request.url());
    const path = normalizedPath(request.url());
    const method = request.method();

    if (method === "GET" && path === "/auth/me") return json(route, ADMIN);
    if (method === "POST" && path === "/auth/logout") return json(route, { ok: true });
    if (method === "GET" && path === "/admin/control-center/access-profile") {
      return json(route, {
        role_key: "ceo_master_admin",
        is_super_admin: false,
        allowed_queues: ["overview", "customer_cases", "verification_upload_review", "users", "system_health"],
      });
    }
    if (method === "GET" && path === "/admin/control-center/kernel/status") {
      return json(route, {
        execution_enabled: true,
        one_step_execution_allowed: true,
        version: "v13.0.0",
        available_actions: [],
      });
    }
    if (method === "GET" && path === "/admin/control-center/overview") {
      return json(route, { summary: { total_users: 2, total_active_projects: 1, paid_orders: 1 } });
    }
    if (method === "GET" && path === "/health/operational") {
      state.healthCalls += 1;
      return json(route, {
        operational_ready: true,
        release: { commit: "675eb26d074999c6bc61b8a520cb2c54971c99b3" },
        components: {
          upload_scanner: { configured: true, available: true, fail_closed: true, mode: "active" },
          private_upload_storage: { persistent: true, mode: "staging_disk" },
          private_object_storage: { configured: true, available: true, mode: "private_r2", legacy_clean_local_uploads: 0 },
        },
        operational_degraded_reasons: [],
      });
    }
    if (method === "GET" && path === "/admin/control-center/cases") {
      state.caseListCalls += 1;
      const search = String(url.searchParams.get("search") || "").trim();
      return json(route, {
        items: search.length >= 2
          ? [
              {
                case_id: "case-robinson",
                project_id: "project-robinson",
                name: "Larry Robinson",
                email: "larry@example.test",
                project: "Robinson Family Legacy",
                package: "Legacy Plus",
                package_name: "Legacy Plus",
                package_code: "legacy_plus",
                lane: "household",
                status: "active",
                tags: [],
                alerts: [],
              },
            ]
          : [],
      });
    }
    if (method === "GET" && path === "/admin/control-center/cases/case-robinson") {
      state.caseDetailCalls += 1;
      return json(route, {
        case_id: "case-robinson",
        tabs: {
          identity: { full_name: "Larry Robinson", email: "larry@example.test" },
          package_lane: { package_name: "Legacy Plus", package_code: "legacy_plus", project_lane: "household" },
          project: { project_id: "project-robinson", project_name: "Robinson Family Legacy", build_status: "active" },
        },
        project: { id: "project-robinson", name: "Robinson Family Legacy", status: "active" },
        alerts: [],
        operator_guidance: [],
      });
    }
    if (path.startsWith("/admin/") || path.startsWith("/packages/") || path.startsWith("/health/")) {
      return json(route, {});
    }
    return route.continue();
  });
  return state;
}

test("[step617] Control Center starts private/search-first and opens a customer only after explicit selection", async ({ page }) => {
  await seedAdmin(page);
  const state = await installControlCenterRoutes(page);
  await page.goto("/admin-control-center.html", { waitUntil: "networkidle" });

  await expect(page.locator("[data-admin-case-heading]")).toHaveText("No case selected");
  await expect(page.locator(".admin-search-first-state")).toContainText("Find the customer or record you intend to work on");
  await expect(page.locator("[data-admin-case-list]")).not.toContainText("Larry Robinson");
  await expect(page.locator(".admin-case-workspace-panel")).toHaveAttribute("data-case-selected", "false");
  await expect(page.locator(".admin-case-action-grid")).toBeHidden();
  expect(state.caseListCalls).toBe(0);
  expect(state.caseDetailCalls).toBe(0);

  const search = page.locator("[data-admin-case-search]");
  await search.fill("Robinson");
  await page.waitForTimeout(450);
  await expect(page.locator("[data-admin-case-list]")).toContainText("Larry Robinson");
  expect(state.caseListCalls).toBeGreaterThan(0);
  expect(state.caseDetailCalls).toBe(0);

  await page.locator('[data-open-case="case-robinson"]').click();
  await expect(page.locator("[data-admin-case-heading]")).toContainText("Larry Robinson");
  await expect(page.locator(".admin-case-workspace-panel")).toHaveAttribute("data-case-selected", "true");
  expect(state.caseDetailCalls).toBe(1);

  await page.locator("[data-admin-clear-case]").click();
  await expect(page.locator("[data-admin-case-heading]")).toHaveText("No case selected");
  await expect(page.locator(".admin-case-workspace-panel")).toHaveAttribute("data-case-selected", "false");
});

test("[step617] Control Center explains commands, separates bulk work, supports command search, and reports operational truth", async ({ page }) => {
  await seedAdmin(page);
  const state = await installControlCenterRoutes(page);
  await page.goto("/admin-control-center.html", { waitUntil: "networkidle" });

  const caseButtons = page.locator("[data-admin-case-action]");
  expect(await caseButtons.count()).toBeGreaterThan(0);
  for (let index = 0; index < await caseButtons.count(); index += 1) {
    const help = await caseButtons.nth(index).getAttribute("data-action-help");
    expect(String(help || "").length).toBeGreaterThan(20);
  }
  const bulkButtons = page.locator("[data-admin-bulk-action]");
  expect(await bulkButtons.count()).toBeGreaterThan(0);
  for (let index = 0; index < await bulkButtons.count(); index += 1) {
    const help = await bulkButtons.nth(index).getAttribute("data-action-help");
    expect(String(help || "").length).toBeGreaterThan(20);
  }
  await expect(page.locator(".admin-console-priority").first()).toContainText("Bulk actions affect more than one record");

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.locator("[data-admin-case-search]")).toBeFocused();

  await expect(page.locator("[data-admin-operational-health]")).toContainText("Security Scanner");
  await expect(page.locator("[data-admin-operational-health]")).toContainText("Private R2");
  await expect(page.locator("[data-admin-operational-health]")).toContainText("READY");
  expect(state.healthCalls).toBeGreaterThan(0);
});

test("[step617] internal Account Security uses admin identity and never calls customer self-service endpoints", async ({ page }) => {
  await seedAdmin(page);
  const calls = { customer: 0 };
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (["document", "script", "stylesheet", "image", "font"].includes(request.resourceType())) return route.continue();
    const path = normalizedPath(request.url());
    if (request.method() === "GET" && path === "/auth/me") return json(route, ADMIN);
    if (["/users/me/profile", "/users/me/workspace-context", "/users/me/security-activity"].includes(path)) {
      calls.customer += 1;
      return json(route, { detail: "customer-only" }, 403);
    }
    return json(route, {});
  });

  await page.goto("/account-security.html", { waitUntil: "networkidle" });
  await expect(page.locator("[data-customer-account-summary-status]")).toContainText("Internal administrator account");
  await expect(page.locator("[data-summary-package]")).toHaveText("Internal Operations");
  await expect(page.locator("[data-summary-project]")).toHaveText("Administrator Workspace");
  await expect(page.locator("[data-summary-family]")).toHaveText("Authorized");
  await expect(page.locator("[data-summary-billing-sync]")).toContainText("Optional");
  await expect(page.locator("#site-nav")).toContainText("Control Center");
  await expect(page.locator("#site-nav")).toContainText("Portrait Review");
  expect(calls.customer).toBe(0);
});

test("[step617] Family Manager shows no family by default, clears stale context on selection change, and previews protected uploads inline", async ({ page }) => {
  await seedAdmin(page);
  const state = { graphCalls: 0, downloadCalls: 0, previewCalls: 0 };
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (["document", "script", "stylesheet", "image", "font"].includes(request.resourceType())) return route.continue();
    const path = normalizedPath(request.url());
    const method = request.method();
    if (method === "GET" && path === "/auth/me") return json(route, ADMIN);
    if (method === "GET" && path === "/admin/intake-submissions") {
      return json(route, [
        { family_root_id: "family-1", package_code: "legacy_plus", package_name: "Legacy Plus", customer_email: "one@example.test" },
        { family_root_id: "family-2", package_code: "legacy_plus", package_name: "Legacy Plus", customer_email: "two@example.test" },
      ]);
    }
    if (method === "GET" && path === "/families/family-1/graph") {
      state.graphCalls += 1;
      return json(route, {
        members: [{ id: "member-1", first_name: "Larry", last_name: "Robinson", generation: 1 }],
        relationships: [],
      });
    }
    if (method === "GET" && path.startsWith("/uploads/member/member-1")) {
      return json(route, {
        uploads: [{
          id: "family-upload-1",
          category: "member_photo",
          original_filename: "portrait.png",
          content_type: "image/png",
          size_bytes: 68,
          scan_status: "clean",
          verification_status: "pending",
          permissions: { can_preview: true },
        }],
      });
    }
    if (method === "GET" && path === "/uploads/family-upload-1/admin-preview") {
      state.previewCalls += 1;
      return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    }
    if (path.includes("/download")) {
      state.downloadCalls += 1;
      return json(route, { detail: "download should not be used" }, 500);
    }
    return json(route, {});
  });

  await page.goto("/admin-family-manager.html", { waitUntil: "networkidle" });
  await expect(page.locator("[data-admin-family-summary]")).toContainText("No family selected");
  expect(state.graphCalls).toBe(0);
  await expect(page.locator('[data-admin-member-form] button[type="submit"]')).toBeDisabled();

  const familySelect = page.locator("[data-admin-family-select]");
  await familySelect.selectOption("family-1");
  expect(state.graphCalls).toBe(0);
  await page.locator("[data-admin-load-family]").click();
  await expect(page.locator("[data-admin-current-members]")).toContainText("Larry Robinson");
  expect(state.graphCalls).toBe(1);
  await expect(page.locator('[data-admin-member-form] button[type="submit"]')).toBeEnabled();

  await page.locator("[data-admin-uploads-member]").selectOption("member-1");
  await page.locator("[data-admin-load-member-uploads]").click();
  await expect(page.locator("[data-admin-member-uploads-list]")).toContainText("portrait.png");
  await page.getByRole("button", { name: "Secure Preview" }).click();
  await expect(page.locator('[data-admin-upload-preview-frame="family-upload-1"] img')).toBeVisible();
  expect(state.previewCalls).toBe(1);
  expect(state.downloadCalls).toBe(0);

  await familySelect.selectOption("family-2");
  await expect(page.locator("[data-admin-family-summary]")).toContainText("No family loaded");
  await expect(page.locator('[data-admin-member-form] button[type="submit"]')).toBeDisabled();
  expect(state.graphCalls).toBe(1);
});

test("[step617] Portrait Review renders a complete protected image inline and keeps approval fail-closed until prerequisites are satisfied", async ({ page }) => {
  await seedAdmin(page);
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (["document", "script", "stylesheet", "image", "font"].includes(request.resourceType())) return route.continue();
    const url = new URL(request.url());
    const path = normalizedPath(request.url());
    if (request.method() === "GET" && path === "/auth/me") return json(route, ADMIN);
    if (request.method() === "GET" && path === "/uploads/admin/review" && url.searchParams.get("category") === "member_photo") {
      return json(route, { items: [{
        id: "portrait-ready",
        member_name: "Larry Robinson",
        family_name: "Robinson Family Legacy",
        original_filename: "portrait.png",
        scan_status: "clean",
        quarantined: false,
        durable_private_storage: true,
        preview_available: true,
        consent_attested: true,
        authority_attested: true,
        master_review_status: "pending",
        orphaned_project_reference: false,
        orphaned_family_reference: false,
        orphaned_member_reference: false,
      }] });
    }
    if (request.method() === "GET" && path === "/uploads/portrait-ready/admin-preview") {
      return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    }
    return json(route, {});
  });

  await page.goto("/admin-portrait-review.html", { waitUntil: "networkidle" });
  await expect(page.getByRole("button", { name: "Approve & Place" })).toBeEnabled();
  await page.getByRole("button", { name: "View Secure Portrait" }).click();
  const image = page.locator('[data-review-card="portrait-ready"] [data-review-preview] img');
  await expect(image).toBeVisible();
  expect(await image.evaluate((node) => getComputedStyle(node).objectFit)).toBe("contain");
  await expect(page.locator('[data-review-card="portrait-ready"] [data-review-notes]')).toBeVisible();
  await expect(page.locator('[data-review-card="portrait-ready"] [data-review-reason]')).toBeVisible();
});

test("[step617] Evidence Review renders protected images and PDFs inline without opening or downloading customer files", async ({ page }) => {
  await seedAdmin(page);
  const state = { previewCalls: 0 };
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (["document", "script", "stylesheet", "image", "font"].includes(request.resourceType())) return route.continue();
    const url = new URL(request.url());
    const path = normalizedPath(request.url());
    if (request.method() === "GET" && path === "/auth/me") return json(route, ADMIN);
    if (request.method() === "GET" && path === "/uploads/admin/review" && url.searchParams.get("category") === "verification_evidence") {
      return json(route, { items: [
        {
          id: "evidence-image",
          member_name: "Image Evidence",
          family_name: "Robinson",
          original_filename: "record.png",
          verification_type: "birth_certificate",
          verification_status: "pending",
          scan_status: "clean",
          quarantined: false,
          durable_private_storage: true,
          preview_available: true,
        },
        {
          id: "evidence-pdf",
          member_name: "PDF Evidence",
          family_name: "Robinson",
          original_filename: "record.pdf",
          verification_type: "government_id",
          verification_status: "pending",
          scan_status: "clean",
          quarantined: false,
          durable_private_storage: true,
          preview_available: true,
        },
      ] });
    }
    if (request.method() === "GET" && path === "/uploads/evidence-image/admin-preview") {
      state.previewCalls += 1;
      return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    }
    if (request.method() === "GET" && path === "/uploads/evidence-pdf/admin-preview") {
      state.previewCalls += 1;
      return route.fulfill({ status: 200, contentType: "application/pdf", body: PDF });
    }
    return json(route, {});
  });

  await page.goto("/admin-verification-review.html", { waitUntil: "networkidle" });
  const buttons = page.getByRole("button", { name: "View Secure Evidence" });
  await buttons.nth(0).click();
  await expect(page.locator('[data-evidence-card="evidence-image"] [data-evidence-preview-frame] img')).toBeVisible();
  await buttons.nth(1).click();
  await expect(page.locator('[data-evidence-card="evidence-pdf"] [data-evidence-preview-frame] iframe')).toBeVisible();
  expect(state.previewCalls).toBe(2);
});

test("[step617] Prepare Secure Preview drives governed scan/storage preparation and auto-opens the newly safe portrait", async ({ page }) => {
  await seedAdmin(page);
  let prepared = false;
  let executeCalls = 0;
  let previewCalls = 0;
  page.on("dialog", (dialog) => dialog.accept());
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (["document", "script", "stylesheet", "image", "font"].includes(request.resourceType())) return route.continue();
    const url = new URL(request.url());
    const path = normalizedPath(request.url());
    const method = request.method();
    if (method === "GET" && path === "/auth/me") return json(route, ADMIN);
    if (method === "GET" && path === "/uploads/admin/review" && url.searchParams.get("category") === "member_photo") {
      return json(route, { items: [{
        id: "portrait-prepare",
        member_name: "Prepare Fixture",
        family_name: "Fixture Family",
        original_filename: "prepare.png",
        scan_status: prepared ? "clean" : "pending",
        quarantined: false,
        durable_private_storage: prepared,
        preview_available: prepared,
        consent_attested: true,
        authority_attested: true,
        master_review_status: "pending",
      }] });
    }
    if (method === "GET" && path === "/admin/control-center/kernel/status") {
      return json(route, { execution_enabled: true, one_step_execution_allowed: true });
    }
    if (method === "POST" && path === "/admin/control-center/kernel/execute") {
      executeCalls += 1;
      const body = request.postDataJSON();
      expect(body.action).toBe("upload_rescan");
      prepared = true;
      return json(route, { state: "audit_closed", execution_result: { scan_status: "clean", storage_provider: "r2" } });
    }
    if (method === "GET" && path === "/uploads/portrait-prepare/admin-preview") {
      previewCalls += 1;
      return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    }
    return json(route, {});
  });

  await page.goto("/admin-portrait-review.html", { waitUntil: "networkidle" });
  await expect(page.getByRole("button", { name: "Approve & Place" })).toBeDisabled();
  await page.getByRole("button", { name: "Prepare Secure Preview" }).click();
  await expect(page.locator('[data-review-card="portrait-prepare"] [data-review-preview] img')).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve & Place" })).toBeEnabled();
  expect(executeCalls).toBe(1);
  expect(previewCalls).toBe(1);
});
