import unittest

from app.core.package_mapping import (
    resolve_package_identity,
    translate_package_code_to_slug,
    translate_package_slug_to_code,
)
from app.routes.admin_control_center import router as admin_control_router
from app.routes.package_catalog import get_package_catalog_route


class PackageMappingTests(unittest.TestCase):
    def test_resolve_known_package_slug(self):
        identity = resolve_package_identity("digital-legacy-portrait")
        self.assertTrue(identity["known"])
        self.assertEqual(identity["package_slug"], "digital-legacy-portrait")
        self.assertEqual(identity["package_code"], "digital_legacy_portrait")
        self.assertEqual(identity["display_name"], "Digital Legacy Portrait")
        self.assertEqual(identity["lane"], "portrait")
        self.assertEqual(identity["anchor_type"], "portrait_anchor")

    def test_translation_helpers_round_trip(self):
        code = translate_package_slug_to_code("household-foundation")
        slug = translate_package_code_to_slug(code)
        self.assertEqual(code, "household_foundation")
        self.assertEqual(slug, "household-foundation")

    def test_starter_family_tree_alias_normalizes_to_household_foundation(self):
        identity = resolve_package_identity("starter-family-tree")
        self.assertTrue(identity["known"])
        self.assertEqual(identity["package_code"], "household_foundation")
        self.assertEqual(identity["package_slug"], "household-foundation")
        self.assertEqual(identity["display_name"], "Household Foundation")

    def test_catalog_exposes_package_map(self):
        payload = get_package_catalog_route()
        self.assertIn("package_map", payload)
        self.assertIn("packages", payload["package_map"])
        self.assertIn("digital-legacy-portrait", payload["package_map"]["packages"])
        self.assertIn("organization_templates", payload)

    def test_admin_repairs_routes_registered(self):
        paths = {str(getattr(route, "path", "")) for route in admin_control_router.routes}
        self.assertIn("/admin/control-center/repairs/missing-entitlements", paths)
        self.assertIn("/admin/control-center/repairs/missing-lanes", paths)
        self.assertIn("/admin/control-center/repairs/unlinked-paid-orders", paths)


if __name__ == "__main__":
    unittest.main()
