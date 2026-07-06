import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_HREF_PATTERN = re.compile(r'href\s*=\s*"(#|javascript:void\(0\)|)"', re.IGNORECASE)
EMPTY_DATA_ACTION_PATTERN = re.compile(r'data-action\s*=\s*""', re.IGNORECASE)
FOUNDER_STYLESHEET_VERSION = "styles.css?v=20260518-founder-polish"


class FrontendLinkIntegrityTests(unittest.TestCase):
    def test_primary_customer_and_admin_pages_do_not_ship_placeholder_links(self):
        pages = [
            "index.html",
            "pricing.html",
            "signup.html",
            "signin.html",
            "dashboard.html",
            "billing.html",
            "intake-uploads.html",
            "upload-hub.html",
            "portrait-upload.html",
            "verification-upload.html",
            "vault-upload.html",
            "household-access.html",
            "link-keys.html",
            "tree-view.html",
            "lineage-certificate.html",
            "account-security.html",
            "admin-control-center.html",
            "digital-collectible.html",
        ]
        violations: list[str] = []
        for relative_path in pages:
            contents = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            if PLACEHOLDER_HREF_PATTERN.search(contents):
                violations.append(f"{relative_path}: placeholder href detected")
            if EMPTY_DATA_ACTION_PATTERN.search(contents):
                violations.append(f"{relative_path}: empty data-action detected")

        self.assertEqual(violations, [])

    def test_marketing_homepage_uses_non_broken_viewer_preview_block(self):
        contents = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertRegex(contents, r'class="[^"]*\bhero-moreland-preview-card\b[^"]*"')
        self.assertIn(
            'class="btn btn-primary moreland-preview-cta" href="/viewer/?demo=malik-moreland"',
            contents,
        )
        self.assertIn("MORELAND FAMILY TREE PREVIEW", contents)
        self.assertIn(
            "Demo package: Family Estate Concierge. This Network Lane demonstration shows how Family Keys connect households without merging private records.",
            contents,
        )
        self.assertIn("View Full Demo Tree", contents)
        self.assertNotIn("Scroll through the Moreland demo tree.", contents)
        self.assertNotIn("Explore linked Moreland branches from Clara and Elias", contents)
        self.assertNotIn("Manifest Required", contents)
        self.assertNotIn("moreland-list-preview", contents)
        self.assertNotIn("moreland-graph-preview", contents)
        self.assertNotIn("moreland-tree-canvas", contents)
        self.assertNotIn("<iframe", contents)
        self.assertNotIn('viewer/index.html?preview=1', contents)
        self.assertNotIn('href="viewer/?demo=malik-moreland"', contents)
        self.assertNotIn('href="viewer?demo=malik-moreland"', contents)
        self.assertNotIn('href="/viewer?demo=malik-moreland"', contents)

    def test_public_demo_ctas_use_demo_tree_language_and_route(self):
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        platform = (REPO_ROOT / "platform.html").read_text(encoding="utf-8")
        how_it_works = (REPO_ROOT / "how-it-works.html").read_text(encoding="utf-8")

        self.assertIn("View Demo Tree", homepage)
        self.assertIn('href="/viewer/?demo=malik-moreland"', homepage)

        self.assertIn('href="viewer/?demo=malik-moreland">View Demo Tree</a>', platform)
        self.assertIn('href="viewer/?demo=malik-moreland">Open Demo Viewer</a>', platform)

        self.assertIn('href="viewer/?demo=malik-moreland">View Demo Tree</a>', how_it_works)
        self.assertNotIn("View Prototype", homepage)
        self.assertNotIn("View Prototype", platform)
        self.assertNotIn("View Prototype", how_it_works)

    def test_cookie_choices_work_from_banner_and_privacy_choices_page(self):
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
        privacy_choices = (REPO_ROOT / "privacy-choices.html").read_text(encoding="utf-8")
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        platform = (REPO_ROOT / "platform.html").read_text(encoding="utf-8")

        self.assertIn('document.querySelectorAll("[data-cookie-accept]")', app_source)
        self.assertIn('document.querySelectorAll("[data-cookie-decline]")', app_source)
        self.assertIn("localStorage.setItem(COOKIE_CHOICE_KEY, choice)", app_source)
        self.assertGreaterEqual(privacy_choices.count("data-cookie-accept"), 2)
        self.assertGreaterEqual(privacy_choices.count("data-cookie-decline"), 2)
        self.assertNotIn('data-cookie-accept"', homepage)
        self.assertNotIn('data-cookie-accept"', platform)
        self.assertNotIn('data-cookie-decline"', homepage)
        self.assertNotIn('data-cookie-decline"', platform)

    def test_core_package_checkout_links_are_live(self):
        config_source = (REPO_ROOT / "config.js").read_text(encoding="utf-8")
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        pricing_page = (REPO_ROOT / "pricing.html").read_text(encoding="utf-8")
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")

        featured_homepage_slugs = [
            "digital_legacy_portrait",
            "heirloom_legacy_tree",
            "family_estate_concierge",
        ]
        expected_pricing_page_slugs = [
            "legacy_snapshot",
            "legacy_portrait_intro",
            "digital_legacy_portrait",
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
            "command_structure_network",
        ]

        for slug in featured_homepage_slugs:
            self.assertIn(f'slug: "{slug}"', config_source)
            self.assertIn(f'data-payment-link="{slug}"', homepage)

        for slug in expected_pricing_page_slugs:
            self.assertIn(f'slug: "{slug}"', config_source)
            self.assertIn(f'data-payment-link="{slug}"', pricing_page)

        self.assertIn("https://buy.stripe.com", config_source)
        self.assertIn("Choose Your Legacy Path", homepage)
        self.assertIn("View Full Pricing", homepage)
        self.assertIn("Private Household Vault", homepage)
        self.assertIn("Private Bridge Event Access", homepage)
        self.assertIn(
            "Every Tomb of Light package requires an active Legacy Care &amp; Maintenance plan beginning at purchase.",
            pricing_page,
        )
        self.assertIn(
            "Digital Legacy Portrait and higher family packages include a Private Household Vault",
            homepage,
        )
        self.assertIn(
            "Organization Records Vault, not a household vault by default.",
            homepage,
        )
        self.assertIn("Full Tomb of Light Pricing", pricing_page)
        self.assertIn("Required Legacy Care &amp; Maintenance", pricing_page)
        self.assertIn("Add-ons &amp; Legacy Services", pricing_page)
        self.assertIn("Private Bridge Event Access", pricing_page)
        self.assertIn("Storage &amp; Vault Upgrades", pricing_page)
        self.assertIn("Rush Delivery", pricing_page)
        self.assertNotIn("Required Legacy Care &amp; Maintenance", homepage)
        self.assertNotIn("Add-ons &amp; Legacy Services", homepage)
        self.assertNotIn("Pricing and checkout links are being refreshed.", homepage)
        self.assertNotIn("Pricing being updated.", homepage)
        self.assertNotIn("Choose your legacy scope", homepage)
        self.assertNotIn("Maintenance starts on delivery", homepage)
        self.assertNotIn("Maintenance starts on activation", homepage)
        self.assertNotIn("Maintenance options are being refreshed", homepage)
        self.assertNotIn('id="section-cta"', homepage)
        self.assertEqual(homepage.count('id="pricing"'), 1)
        self.assertEqual(pricing_page.count('class="cookie-banner"'), 1)
        self.assertIn(
            'href="https://buy.stripe.com/28E28reMK9Ar6v48xnbEA13"',
            homepage,
        )
        self.assertIn(
            'href="https://buy.stripe.com/7sY7sL9sq4g74mW9BrbEA15"',
            homepage,
        )
        self.assertIn(
            'href="https://buy.stripe.com/cNi7sL48613V7z8dRHbEA17"',
            homepage,
        )
        self.assertNotIn("mailto:billing@tomboflight.com", homepage)
        self.assertNotIn("mailto:billing@tomboflight.com", pricing_page)
        self.assertGreaterEqual(homepage.count('target="_blank"'), 3)
        self.assertGreaterEqual(pricing_page.count('target="_blank"'), 20)
        self.assertGreaterEqual(homepage.count('rel="noopener noreferrer"'), 3)
        self.assertGreaterEqual(pricing_page.count('rel="noopener noreferrer"'), 20)

        for package_code in [
            "BRIDGE-TASTE-SNAPSHOT",
            "BRIDGE-TASTE-PORTRAIT",
            "BRIDGE-TASTE-DIGITAL",
            "BRIDGE-TASTE-HOUSEHOLD",
            "BRIDGE-TASTE-HEIRLOOM",
            "BRIDGE-TASTE-PLUS",
            "BRIDGE-TASTE-ESTATE",
            "BRIDGE-TASTE-COMMAND",
        ]:
            self.assertIn(package_code, homepage)

        self.assertNotIn("BRIDGE-PAINT", homepage)
        self.assertNotIn("BRIDGE-LINEAGE", homepage)
        self.assertNotIn("GRANDOPENING", homepage)
        self.assertIn('const checkoutFrozen = link.getAttribute("aria-disabled") === "true";', app_source)
        self.assertIn("prefilled_promo_code", app_source)
        self.assertIn("function configureDirectStripeCheckout(link, href) {", app_source)
        self.assertIn("const hasDirectStripeHref = configureDirectStripeCheckout(link, existingHref);", app_source)
        self.assertIn('let checkoutHref = hasDirectStripeHref ? existingHref : "";', app_source)
        self.assertNotIn("mailto:billing@tomboflight.com", app_source)
        self.assertNotIn("window.location.href = `signin.html?next=", app_source)

    def test_founder_access_redirects_to_pricing(self):
        founder_page = (REPO_ROOT / "founder-access.html").read_text(encoding="utf-8")

        self.assertIn('<meta http-equiv="refresh" content="0; url=index.html#pricing" />', founder_page)
        self.assertIn('href="index.html#pricing">View packages</a>', founder_page)
        self.assertIn('window.location.replace("index.html#pricing")', founder_page)
        self.assertNotIn(FOUNDER_STYLESHEET_VERSION, founder_page)

    def test_checkout_campaign_and_pricing_catalog_engines_are_not_duplicated(self):
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
        thank_you_source = (REPO_ROOT / "thank-you.js").read_text(encoding="utf-8")
        order_service = (REPO_ROOT / "backend" / "app" / "services" / "order_service.py").read_text(
            encoding="utf-8"
        )
        maintenance_service = (
            REPO_ROOT / "backend" / "app" / "services" / "maintenance_subscription_service.py"
        ).read_text(encoding="utf-8")
        config_source = (REPO_ROOT / "config.js").read_text(encoding="utf-8")

        self.assertEqual(
            app_source.count('const LIGHT_NEVER_DIES_CAMPAIGN = "LIGHT_NEVER_DIES";'),
            1,
        )
        self.assertEqual(
            thank_you_source.count('const LIGHT_NEVER_DIES_CAMPAIGN = "LIGHT_NEVER_DIES";'),
            1,
        )
        self.assertEqual(app_source.count("function enforceFounderMaintenanceGate()"), 1)
        self.assertEqual(app_source.count("function buildCheckoutLinkWithContext("), 1)
        self.assertEqual(order_service.count("def _extract_checkout_context("), 1)
        self.assertEqual(maintenance_service.count("def _metadata_project_id("), 1)
        self.assertEqual(app_source.count("const PACKAGE_PROFILES = {"), 1)
        self.assertEqual(config_source.count("const TOL_PRICING = {"), 1)
        self.assertEqual(config_source.count('slug: "legacy_snapshot"'), 1)
        self.assertEqual(config_source.count('slug: "command_structure_network"'), 1)

    def test_public_and_legal_headers_include_platform_nav(self):
        pages = [
            "index.html",
            "platform.html",
            "how-it-works.html",
            "security.html",
            "compliance.html",
            "faq.html",
            "pricing.html",
            "privacy.html",
            "terms.html",
            "cookie-policy.html",
            "accessibility.html",
            "data-request.html",
            "privacy-state-notices.html",
            "refunds-delivery.html",
            "signup.html",
            "signin.html",
            "privacy-choices.html",
        ]
        for relative_path in pages:
            contents = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn('href="platform.html"', contents, relative_path)
            self.assertIn("Platform", contents, relative_path)

    def test_footer_legal_links_are_consistent_where_footer_link_block_exists(self):
        required_labels = [
            "Privacy Policy",
            "Terms",
            "Cookie Policy",
            "Accessibility",
            "Data Requests",
            "State Privacy Notices",
            "Privacy Choices",
            "Refunds, Delivery &amp; Support",
            "Compliance &amp; Legal",
        ]
        for page in REPO_ROOT.rglob("*.html"):
            if any(part in {"out", "cache", "node_modules", "venv"} for part in page.parts):
                continue
            contents = page.read_text(encoding="utf-8")
            if 'class="footer-links"' not in contents:
                continue
            for label in required_labels:
                self.assertIn(label, contents, str(page.relative_to(REPO_ROOT)))

    def test_viewer_demo_navigation_has_deterministic_home_and_guardrails(self):
        viewer_html = (REPO_ROOT / "viewer" / "index.html").read_text(encoding="utf-8")
        viewer_script = (REPO_ROOT / "viewer" / "js" / "script.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('href="/index.html" class="back-link" id="backLink"', viewer_html)
        self.assertIn('backLink.href = "/index.html";', viewer_script)
        self.assertIn('row.setAttribute("data-path-state", targetStateId)', viewer_script)
        self.assertIn("That viewer node is unavailable.", viewer_script)
        self.assertIn("syncControlStates()", viewer_script)

    def test_upload_and_dashboard_paths_do_not_call_missing_routes_or_dead_links(self):
        vault_source = (REPO_ROOT / "vault-upload.js").read_text(encoding="utf-8")
        dashboard = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")

        self.assertNotIn("/families/list", vault_source)
        self.assertIn('app.apiRequest("/families/"', vault_source)
        self.assertIn('type="button"', dashboard)
        self.assertIn("data-dashboard-admin-tools", dashboard)


if __name__ == "__main__":
    unittest.main()
