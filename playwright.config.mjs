import { defineConfig, devices } from "@playwright/test";

const criticalCrossBrowserTest = /critical-cross-browser\.spec\.mjs/;

export default defineConfig({
  testDir: "./browser-tests",
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "browser-test-results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium-desktop-full",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1600, height: 1100 },
      },
    },
    {
      name: "webkit-desktop-critical",
      testMatch: criticalCrossBrowserTest,
      use: {
        ...devices["Desktop Safari"],
      },
    },
    {
      name: "webkit-mobile-critical",
      testMatch: criticalCrossBrowserTest,
      use: {
        ...devices["iPhone 13"],
      },
    },
  ],
  webServer: {
    command: "python3 -m http.server 4173 --bind 127.0.0.1",
    url: "http://127.0.0.1:4173/admin-control-center.html",
    timeout: 120_000,
    reuseExistingServer: true,
  },
});
