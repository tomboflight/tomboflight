import unittest
from unittest.mock import patch

from app.core.dropdown_registry import (
    assert_no_duplicate_dropdown_keys,
    get_all_organization_types,
    get_organization_subtypes,
    get_safe_organization_type,
    get_shared_dropdowns,
)


class DropdownRegistryTests(unittest.TestCase):
    def test_registry_has_required_groups_with_stable_keys_and_labels(self):
        dropdowns = get_shared_dropdowns()
        for required in (
            "organization_type",
            "person_status",
            "assignment_status",
            "transition_event_type",
            "support_record_type",
            "privacy_level",
        ):
            self.assertIn(required, dropdowns)
            self.assertTrue(all("key" in option for option in dropdowns[required]))
            self.assertTrue(all("label" in option for option in dropdowns[required]))

    def test_no_duplicate_dropdown_keys_exist(self):
        assert_no_duplicate_dropdown_keys()

    def test_custom_fallback_uses_custom_type(self):
        self.assertEqual(get_safe_organization_type("not_a_known_org"), "custom")

    def test_political_and_public_office_types_exist(self):
        organization_types = {item["key"] for item in get_all_organization_types()}
        self.assertIn("elected_office", organization_types)
        self.assertIn("legislative_body", organization_types)
        self.assertIn("political_campaign", organization_types)
        self.assertIn("government_agency", organization_types)

    def test_police_and_fire_types_exist(self):
        organization_types = {item["key"] for item in get_all_organization_types()}
        self.assertIn("police_department", organization_types)
        self.assertIn("fire_department", organization_types)

    def test_subtype_helpers_cover_police_and_fire(self):
        police_subtypes = {item["key"] for item in get_organization_subtypes("police_department")}
        fire_subtypes = {item["key"] for item in get_organization_subtypes("fire_department")}
        self.assertIn("municipal_police", police_subtypes)
        self.assertIn("municipal_fire_department", fire_subtypes)

    def test_registry_does_not_write_database_rows(self):
        with patch("app.database.get_database", side_effect=AssertionError("DB access not allowed")):
            get_shared_dropdowns()
            get_all_organization_types()
            get_organization_subtypes("police_department")


if __name__ == "__main__":
    unittest.main()
