import { expect, test } from "@playwright/test";

function testApiBases(pageUrl) {
  const origin = new URL(pageUrl).origin;
  return {
    gateway: `${origin}/api-gateway`,
    fallback: `${origin}/direct-api`,
  };
}

async function configureApiBases(page, bases, { saved = "" } = {}) {
  await page.evaluate(
    ({ gateway, fallback, savedBase }) => {
      window.TOL_CONFIG.API_BASE_URL = gateway;
      window.TOL_CONFIG.API_BASE_URLS = [gateway, fallback];
      if (savedBase) {
        window.sessionStorage.setItem("tol_api_base_url", savedBase);
      } else {
        window.sessionStorage.removeItem("tol_api_base_url");
      }
    },
    { ...bases, savedBase: saved },
  );
}

test("[phase20.1 gateway recovery] rejects an HTML health false-positive before login", async ({ page }) => {
  const hits = { gatewayHealth: 0, gatewayLogin: 0, fallbackHealth: 0, fallbackLogin: 0 };

  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api-gateway/health") {
      hits.gatewayHealth += 1;
      return route.fulfill({ status: 200, contentType: "text/html", body: "<html>frontend</html>" });
    }
    if (url.pathname === "/api-gateway/auth/login") {
      hits.gatewayLogin += 1;
      return route.fulfill({ status: 405, contentType: "text/html", body: "<h1>405 Not Allowed</h1>" });
    }
    if (url.pathname === "/direct-api/health") {
      hits.fallbackHealth += 1;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
    }
    if (url.pathname === "/direct-api/auth/login") {
      hits.fallbackLogin += 1;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "fixture-token" }) });
    }
    return route.continue();
  });

  await page.goto("/signin.html");
  const bases = testApiBases(page.url());
  await configureApiBases(page, bases);

  const result = await page.evaluate(() =>
    window.TOLApp.apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "fixture@example.test", password: "fixture-password" }),
    }),
  );

  expect(result.access_token).toBe("fixture-token");
  expect(hits).toEqual({ gatewayHealth: 1, gatewayLogin: 0, fallbackHealth: 1, fallbackLogin: 1 });
});

test("[phase20.1 gateway recovery] fails over a stale saved gateway after an HTML 405", async ({ page }) => {
  const hits = { gatewayLogin: 0, fallbackLogin: 0 };

  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api-gateway/auth/login") {
      hits.gatewayLogin += 1;
      return route.fulfill({ status: 405, contentType: "text/html", body: "<h1>405 Not Allowed</h1>" });
    }
    if (url.pathname === "/direct-api/auth/login") {
      hits.fallbackLogin += 1;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "fallback-token" }) });
    }
    return route.continue();
  });

  await page.goto("/signin.html");
  const bases = testApiBases(page.url());
  await configureApiBases(page, bases, { saved: bases.gateway });

  const result = await page.evaluate(() =>
    window.TOLApp.apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "fixture@example.test", password: "fixture-password" }),
    }),
  );

  expect(result.access_token).toBe("fallback-token");
  expect(hits).toEqual({ gatewayLogin: 1, fallbackLogin: 1 });
});

test("[phase20.1 gateway recovery] preserves legitimate JSON 405 responses", async ({ page }) => {
  let fallbackRequests = 0;

  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api-gateway/auth/login") {
      return route.fulfill({
        status: 405,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Method not allowed by the API." }),
      });
    }
    if (url.pathname === "/direct-api/auth/login") {
      fallbackRequests += 1;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "unexpected" }) });
    }
    return route.continue();
  });

  await page.goto("/signin.html");
  const bases = testApiBases(page.url());
  await configureApiBases(page, bases, { saved: bases.gateway });

  const result = await page.evaluate(async () => {
    try {
      await window.TOLApp.apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: "fixture@example.test", password: "fixture-password" }),
      });
      return { status: 0, message: "unexpected success" };
    } catch (error) {
      return { status: error.status, message: error.message };
    }
  });

  expect(result).toEqual({ status: 405, message: "Method not allowed by the API." });
  expect(fallbackRequests).toBe(0);
});
