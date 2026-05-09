import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_HREF_PATTERN = re.compile(r'href\s*=\s*"(#|javascript:void\(0\)|)"', re.IGNORECASE)
EMPTY_DATA_ACTION_PATTERN = re.compile(r'data-action\s*=\s*""', re.IGNORECASE)


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
            "Preview the Moreland family structure, then open the full demo to explore parent, sibling, spouse, and descendant branches.",
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
        self.assertNotIn('data-cookie-decline"', homepage)
        self.assertNotIn('data-cookie-decline"', platform)

    def test_core_package_checkout_links_are_mapped_and_safe(self):
        config_source = (REPO_ROOT / "config.js").read_text(encoding="utf-8")
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")

        expected = {
            "legacy_snapshot": "https://buy.stripe.com/bJe7sL6ge27Z2eOcNDbEA0F",
            "legacy_portrait_intro": "https://buy.stripe.com/7sY7sLfQO8wn3iS14VbEA0B",
            "digital_legacy_portrait": "https://buy.stripe.com/3cIaEXdIG8wn5r08xnbEA0G",
            "household_foundation": "https://buy.stripe.com/28E4gz1ZY8wn7z800RbEA0H",
            "heirloom_legacy_tree": "https://buy.stripe.com/7sY6oHbAybIzf1A6pfbEA00",
            "legacy_plus": "https://buy.stripe.com/dRmaEXeMK9Ar1aKaFvbEA0y",
            "family_estate_concierge": "https://buy.stripe.com/eVqeVdbAyh2T9HgbJzbEA0I",
            "command_structure_network": "https://buy.stripe.com/3cIdR96geeULg5E6pfbEA0J",
        }

        for slug, checkout_url in expected.items():
            self.assertIn(f'slug: "{slug}"', config_source)
            self.assertIn(f'checkoutUrl: "{checkout_url}"', config_source)
            self.assertIn(f'data-payment-link="{slug}"', homepage)

        self.assertIn('link.target = "_blank"', app_source)
        self.assertIn('link.rel = "noopener noreferrer"', app_source)
        self.assertIn("Opening secure checkout...", app_source)

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
