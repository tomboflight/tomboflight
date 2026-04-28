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
            "tree-view.html",
            "lineage-certificate.html",
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

        self.assertRegex(
            contents,
            r'<a[^>]*class="[^"]*\bhero-viewer-link\b[^"]*"[^>]*href="platform\.html"',
        )
        self.assertIn('class="hero-viewer-static"', contents)
        self.assertNotIn("Manifest Required", contents)
        embed_match = re.search(
            r'<div class="hero-demo-embed hero-viewer-embed">(.*?)</div>\s*</div>',
            contents,
            re.DOTALL,
        )
        self.assertIsNotNone(embed_match)
        self.assertNotIn("<iframe", embed_match.group(1))
        self.assertIn('class="btn btn-primary" href="viewer/index.html?preview=1"', contents)
        self.assertNotIn('class="mini-link hero-viewer-link" href="viewer/"', contents)


if __name__ == "__main__":
    unittest.main()
