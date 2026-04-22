import unittest

from app.core.organization_template_catalog import (
    ORGANIZATION_TYPE_OPTIONS,
    get_organization_template_catalog,
)
from app.routes.package_catalog import get_organization_templates_route


class OrganizationTemplateCatalogTests(unittest.TestCase):
    def test_catalog_contains_required_type_options(self):
        catalog = get_organization_template_catalog()
        self.assertEqual(
            catalog.get("organization_type_options"),
            ORGANIZATION_TYPE_OPTIONS,
        )

    def test_all_types_have_template_entries(self):
        catalog = get_organization_template_catalog()
        templates = catalog.get("templates") or {}
        self.assertEqual(set(templates.keys()), set(ORGANIZATION_TYPE_OPTIONS))
        self.assertEqual(
            list((templates.get("military_unit") or {}).get("suggested_structural_nodes") or []),
            list((templates.get("military_unit") or {}).get("suggested_nodes") or []),
        )

    def test_templates_are_helper_only_and_customizable(self):
        catalog = get_organization_template_catalog()
        self.assertTrue(bool(catalog.get("templates_are_helpers")))
        elected = (catalog.get("templates") or {}).get("elected_office") or {}
        customization = elected.get("customization") or {}
        self.assertTrue(bool(customization.get("template_is_helper_only")))
        self.assertTrue(bool(customization.get("allow_custom_profile_fields")))
        self.assertTrue(bool(customization.get("allow_custom_nodes")))
        self.assertTrue(bool(customization.get("allow_custom_role_seats")))
        self.assertTrue(bool(customization.get("allow_custom_transition_event_types")))
        self.assertTrue(bool(customization.get("allow_custom_support_record_types")))
        self.assertTrue(bool(customization.get("allow_custom_role_titles")))
        self.assertTrue(bool(customization.get("allow_custom_departments")))
        self.assertTrue(bool(customization.get("allow_custom_offices")))
        self.assertTrue(bool(customization.get("allow_custom_jurisdictions")))
        self.assertTrue(bool(customization.get("allow_custom_positions")))

    def test_elected_office_template_includes_requested_samples(self):
        templates = get_organization_template_catalog().get("templates") or {}
        elected = templates.get("elected_office") or {}
        self.assertIn("office_level", list(elected.get("suggested_profile_fields") or []))
        self.assertIn("district", list(elected.get("suggested_profile_fields") or []))
        self.assertIn("Main Office", list(elected.get("suggested_nodes") or []))
        self.assertIn("Senator", list(elected.get("suggested_role_seats") or []))
        self.assertIn("Sheriff", list(elected.get("suggested_role_seats") or []))
        self.assertIn(
            "county",
            list(elected.get("supported_jurisdiction_levels") or []),
        )
        self.assertIn(
            "U.S. Senate office",
            list(elected.get("supported_office_examples") or []),
        )
        self.assertIn(
            "committee_assignment_changed",
            list(elected.get("suggested_transition_event_types") or []),
        )
        self.assertIn(
            "oath_of_office",
            list(elected.get("suggested_support_record_types") or []),
        )

    def test_police_template_includes_requested_samples(self):
        templates = get_organization_template_catalog().get("templates") or {}
        police = templates.get("police_department") or {}
        self.assertIn("Precinct", list(police.get("suggested_nodes") or []))
        self.assertIn("Chief of Police", list(police.get("suggested_role_seats") or []))
        self.assertIn(
            "command_changed",
            list(police.get("suggested_transition_event_types") or []),
        )
        self.assertIn(
            "badge_assignment_record",
            list(police.get("suggested_support_record_types") or []),
        )

    def test_custom_template_has_required_enforcement(self):
        templates = get_organization_template_catalog().get("templates") or {}
        custom = templates.get("custom") or {}
        capabilities = custom.get("custom_template_capabilities") or {}
        self.assertTrue(bool(capabilities.get("allow_custom_organization_type_label")))
        self.assertTrue(bool(capabilities.get("allow_custom_nodes")))
        self.assertTrue(bool(capabilities.get("allow_custom_role_seats")))
        self.assertTrue(bool(capabilities.get("allow_custom_transition_events")))
        self.assertTrue(bool(capabilities.get("allow_custom_transition_event_types")))
        self.assertTrue(bool(capabilities.get("allow_custom_support_record_labels")))
        self.assertTrue(bool(capabilities.get("allow_custom_statuses")))
        self.assertTrue(bool(capabilities.get("allow_custom_hierarchy_labels")))
        enforcement = custom.get("enforcement") or {}
        self.assertTrue(bool(enforcement.get("enforce_package_node_cap")))
        self.assertTrue(bool(enforcement.get("enforce_upload_cap")))
        self.assertTrue(bool(enforcement.get("enforce_permission_gates")))
        self.assertTrue(bool(enforcement.get("enforce_audit_logging")))
        self.assertTrue(bool(enforcement.get("enforce_no_duplicate_records")))

    def test_route_returns_catalog(self):
        payload = get_organization_templates_route()
        self.assertIn("organization_type_options", payload)
        self.assertIn("templates", payload)


if __name__ == "__main__":
    unittest.main()
