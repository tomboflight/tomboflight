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
            "portrait-upload.html",
            "verification-upload.html",
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


if __name__ == "__main__":
    unittest.main()
