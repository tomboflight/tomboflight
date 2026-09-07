import fs from "node:fs";
import vm from "node:vm";
import { expect, test } from "@playwright/test";

const source = fs.readFileSync(new URL("../billing-api-origin.js", import.meta.url), "utf8");

function runBootstrap(origin, savedBase = "") {
  const storage = new Map();
  if (savedBase) storage.set("tol_api_base_url", savedBase);
  const url = new URL(origin);
  const window = {
    location: {
      origin: url.origin,
      hostname: url.hostname,
    },
    TOL_CONFIG: {
      API_BASE_URL: "https://tomboflight.com/api-gateway",
      API_BASE_URLS: [
        "https://tomboflight.com/api-gateway",
        "https://tomboflight-api.onrender.com",
      ],
    },
    sessionStorage: {
      getItem(key) {
        return storage.get(key) || null;
      },
      removeItem(key) {
        storage.delete(key);
      },
    },
  };
  vm.runInNewContext(source, { window });
  return { config: window.TOL_CONFIG, storage };
}

test("[billing-p0] www production billing binds gateway to the active origin", () => {
  const result = runBootstrap(
    "https://www.tomboflight.com/billing.html",
    "https://tomboflight.com/api-gateway",
  );

  expect(result.config.API_BASE_URL).toBe("https://www.tomboflight.com/api-gateway");
  expect(result.config.API_BASE_URLS).toEqual([
    "https://www.tomboflight.com/api-gateway",
    "https://tomboflight-api.onrender.com",
  ]);
  expect(result.storage.has("tol_api_base_url")).toBe(false);
});

test("[billing-p0] apex production billing preserves apex same-origin gateway", () => {
  const result = runBootstrap("https://tomboflight.com/billing.html");

  expect(result.config.API_BASE_URL).toBe("https://tomboflight.com/api-gateway");
  expect(result.config.API_BASE_URLS).toEqual([
    "https://tomboflight.com/api-gateway",
    "https://tomboflight-api.onrender.com",
  ]);
});

test("[billing-p0] local development routing is not overridden", () => {
  const result = runBootstrap("http://127.0.0.1:5500/billing.html");

  expect(result.config.API_BASE_URL).toBe("https://tomboflight.com/api-gateway");
});
