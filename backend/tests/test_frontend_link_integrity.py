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

    def test_core_package_ctas_frozen_state(self):
        config_source = (REPO_ROOT / "config.js").read_text(encoding="utf-8")
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")

        expected_slugs = [
            "legacy_snapshot",
            "legacy_portrait_intro",
            "digital_legacy_portrait",
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
            "command_structure_network",
        ]

        for slug in expected_slugs:
            self.assertIn(f'slug: "{slug}"', config_source)
            self.assertIn(f'data-payment-link="{slug}"', homepage)
        self.assertEqual(homepage.count('href="#stripe-catalog-refresh"'), 8)
        self.assertEqual(homepage.count('aria-disabled="true"'), 8)
        self.assertEqual(
            homepage.count('title="Checkout links are being updated."'),
            8,
        )

        self.assertNotIn("https://buy.stripe.com", config_source)
        self.assertNotIn("https://checkout.stripe.com", config_source)
        self.assertNotIn("https://stripe.com/pay", config_source)
        self.assertIn('const checkoutFrozen = link.getAttribute("aria-disabled") === "true";', app_source)
        self.assertIn('link.href = "#stripe-catalog-refresh";', app_source)
        self.assertIn('link.title = "Checkout links are being updated.";', app_source)
        self.assertIn("event.preventDefault();", app_source)
        self.assertIn('id="pricing"', homepage)
        self.assertIn('id="stripe-catalog-refresh"', homepage)
        self.assertIn(
            "Pricing and checkout links are being refreshed. Package details remain available for review.",
            homepage,
        )
        self.assertIn("Choose your legacy scope", homepage)
        self.assertEqual(homepage.count('id="pricing"'), 1)

    def test_founder_access_marketing_layer_is_present_and_campaign_ready(self):
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        founder_page = (REPO_ROOT / "founder-access.html").read_text(encoding="utf-8")

        for required in [
            "LIGHT NEVER DIES",
            "Genesis Founder Release",
            "Founder Access",
            "June 28, 2026",
            "campaign=LIGHT_NEVER_DIES",
        ]:
            self.assertIn(required, homepage)
            self.assertIn(required, founder_page)

        self.assertIn(FOUNDER_STYLESHEET_VERSION, homepage)
        self.assertIn(FOUNDER_STYLESHEET_VERSION, founder_page)

        self.assertEqual(homepage.count("data-founder-access-banner"), 1)
        self.assertEqual(homepage.count("data-founder-access-section"), 1)
        self.assertEqual(founder_page.count('id="founder-access-title"'), 1)
        self.assertEqual(founder_page.count("founder-access-strip"), 2)

        expected_founder_slugs = [
            "legacy_snapshot",
            "legacy_portrait_intro",
            "digital_legacy_portrait",
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
        ]
        for slug in expected_founder_slugs:
            self.assertIn(f'data-payment-link="{slug}"', founder_page)

        self.assertIn("LIGHTNEVERDIES-PORTRAIT", founder_page)
        self.assertNotIn("LIGHTNEVERDIES- PORTRAIT", founder_page)

    def test_checkout_campaign_and_founder_engines_are_not_duplicated(self):
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
        thank_you_source = (REPO_ROOT / "thank-you.js").read_text(encoding="utf-8")
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
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
        self.assertEqual(homepage.count("data-founder-access-banner"), 1)
        self.assertEqual(homepage.count("data-founder-access-section"), 1)

    def test_public_and_legal_headers_include_platform_nav(self):
        pages = [
            "index.html",
            "platform.html",
            "how-it-works.html",
            "security.html",
            "compliance.html",
            "faq.html",
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
