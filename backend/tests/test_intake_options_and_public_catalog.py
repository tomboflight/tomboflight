import unittest

from app.core.package_catalog import get_package, get_public_package_catalog
from app.core.dropdown_registry import get_intake_dropdowns, get_privacy_scope_canonical_map
from app.routes.intake_options import get_intake_options_route


class IntakeOptionsTests(unittest.TestCase):
    def test_intake_options_include_guided_dropdowns_and_defaults(self):
        payload = get_intake_options_route()
        dropdowns = payload["dropdowns"]
        self.assertIn("who_are_you_adding", dropdowns)
        self.assertIn("exact_relationship_type", dropdowns)
        self.assertIn("privacy_scope", dropdowns)
        self.assertEqual(payload["defaults"]["where_should_this_belong"], "auto")
        self.assertEqual(payload["defaults"]["release_mode"], "immediate")

    def test_privacy_scope_mapping_targets_existing_canonical_values(self):
        mapping = get_privacy_scope_canonical_map()
        self.assertEqual(mapping["only_me"], "private_to_owner")
        self.assertEqual(mapping["linked_household_shared"], "linked_family_shared")


class PublicCatalogEntitlementTests(unittest.TestCase):
    def test_public_catalog_exposes_new_vault_entitlements(self):
        packages = {item["package_code"]: item for item in get_public_package_catalog()}
        self.assertTrue(packages["digital_legacy_portrait"]["can_use_scheduled_reveal"])
        self.assertTrue(packages["family_estate_concierge"]["can_use_linked_household_vault"])
        self.assertTrue(packages["command_structure_network"]["can_use_organization_records_vault"])

    def test_package_copy_includes_allowed_visibility_scopes(self):
        package = get_package("legacy_snapshot")
        assert package is not None
        self.assertIn("allowed_visibility_scopes", package)
        self.assertIn("minor_protected", package["allowed_visibility_scopes"])


if __name__ == "__main__":
    unittest.main()
