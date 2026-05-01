import re
import unittest
from pathlib import Path


class GenesisPrototypeManifestSafetyTests(unittest.TestCase):
    def setUp(self):
        self.manifest_path = (
            Path(__file__).resolve().parents[2]
            / "viewer"
            / "js"
            / "genesis-prototype-manifest.js"
        )
        self.source = self.manifest_path.read_text(encoding="utf-8")

    def test_uses_only_approved_genesis_images(self):
        approved = {
            "../images/malik.jpg",
            "../images/malik_descendants.jpg",
            "../images/imani.jpg",
            "../images/imani_descendants.jpg",
            "../images/julian.jpg",
            "../images/selah.jpg",
            "../images/selah_descendants.jpg",
            "../images/parents.jpg",
        }
        referenced = set(re.findall(r'image:\s*"([^"]+)"', self.source))
        self.assertEqual(referenced, approved)

    def test_contains_only_confirmed_people_and_states(self):
        expected_state_ids = {
            "malik_anchor",
            "moreland_parents",
            "malik_descendants",
            "imani_anchor",
            "imani_descendants",
            "julian_anchor",
            "selah_anchor",
            "selah_descendants",
        }
        state_ids = set(re.findall(r'id:\s*"([^"]+)"', self.source))
        self.assertTrue(expected_state_ids.issubset(state_ids))

        disallowed_terms = [
            "Naomi",
            "Marcus",
            "Benton",
            "Eli Moreland",
            "Micah",
            "Zara",
            "Andre",
            "Camille",
            "stock",
            "placeholder",
            "random",
            "generated people",
        ]
        for term in disallowed_terms:
            self.assertNotIn(term, self.source)

    def test_parent_overlay_regions_are_defined_only_for_parents_state(self):
        self.assertIn('enabled_on_state_id: "moreland_parents"', self.source)
        self.assertIn("hide_delay_ms: 5000", self.source)
        self.assertIn('{ region: "left", label: "Selah Carter", target_state_id: "selah_anchor" }', self.source)
        self.assertIn('{ region: "center", label: "Malik Moreland", target_state_id: "malik_anchor" }', self.source)
        self.assertIn('{ region: "right", label: "Julian Moreland", target_state_id: "julian_anchor" }', self.source)
        self.assertIn("branch_options_by_state: {}", self.source)

    def test_required_zoom_transition_map_is_exact(self):
        expected_links = {
            "malik_anchor": ("moreland_parents", "malik_descendants"),
            "moreland_parents": ("", "malik_anchor"),
            "malik_descendants": ("malik_anchor", "imani_anchor"),
            "imani_anchor": ("malik_descendants", "imani_descendants"),
            "imani_descendants": ("imani_anchor", ""),
            "selah_anchor": ("moreland_parents", "selah_descendants"),
            "selah_descendants": ("selah_anchor", ""),
            "julian_anchor": ("moreland_parents", ""),
        }

        transitions: dict[str, tuple[str, str]] = {}
        for state_id, left, right in re.findall(
            r'id:\s*"([^"]+?)".*?left_state_id:\s*"([^"]*?)".*?right_state_id:\s*"([^"]*?)"',
            self.source,
            re.DOTALL,
        ):
            transitions[state_id] = (left, right)

        for state_id, link_pair in expected_links.items():
            self.assertEqual(transitions.get(state_id), link_pair)


if __name__ == "__main__":
    unittest.main()
