import { expect, test } from "@playwright/test";

test(
  "[revenue] direct Stripe links preserve the active project checkout context",
  async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem(
        "tol_user",
        JSON.stringify({
          id: "user-revenue-test",
          email: "customer@example.com",
          active_project_id: "project-revenue-test",
        }),
      );
    });

    await page.goto("/pricing.html");
    const checkoutLink = page
      .locator('[data-payment-link="digital_legacy_portrait"]')
      .first();
    await expect(checkoutLink).toHaveAttribute(
      "href",
      /^https:\/\/buy\.stripe\.com\//,
    );

    const checkoutHref = await checkoutLink.evaluate((link) => {
      link.addEventListener("click", (event) => event.preventDefault(), {
        once: true,
      });
      link.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
      return link.href;
    });
    const checkoutUrl = new URL(checkoutHref);

    expect(checkoutUrl.origin).toBe("https://buy.stripe.com");
    expect(checkoutUrl.searchParams.get("client_reference_id")).toBe(
      "tol:v=1&u=user-revenue-test&p=project-revenue-test&k=digital_legacy_portrait&t=package&b=one_time",
    );
    expect(checkoutUrl.searchParams.get("prefilled_email")).toBe(
      "customer@example.com",
    );
  },
);
