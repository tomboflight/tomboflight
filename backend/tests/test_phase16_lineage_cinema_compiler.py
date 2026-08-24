from __future__ import annotations

import unittest

from app.core.relationship_catalog import (
    ALLOWED_RELATIONSHIP_TYPES,
    PARENT_RELATIONSHIP_TYPES,
    PARTNER_RELATIONSHIP_TYPES,
    SIBLING_RELATIONSHIP_TYPES,
)
from app.services.lineage_cinema_compiler import (
    LINEAGE_CINEMA_COMPILER_VERSION,
    compile_lineage_cinema,
)


def _state(member_id: str, title: str, generation: int) -> dict:
    return {
        "id": f"member-{member_id}",
        "member_id": member_id,
        "title": title,
        "node": title,
        "generation": generation,
    }


def _relationship(
    source: str,
    target: str,
    relationship_type: str,
    *,
    mode: str = "verified",
    marker: str = "verified",
) -> dict:
    return {
        "source_member_id": source,
        "target_member_id": target,
        "relationship_type": relationship_type,
        "relationship_mode": mode,
        "status_marker": marker,
        "privacy_scope": "household_private",
    }


class Phase16LineageCinemaCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.states = [
            _state("malik", "Malik Moreland", 1),
            _state("elias", "Elias Moreland", 0),
            _state("clara", "Clara Moreland", 0),
            _state("naomi", "Naomi Moreland", 1),
            _state("eli", "Eli Moreland", 2),
            _state("imani", "Imani Benton / Imani Moreland", 2),
            _state("marcus", "Marcus Benton", 2),
            _state("micah", "Micah Benton", 3),
            _state("zara", "Zara Benton", 3),
            _state("selah", "Selah Carter", 1),
            _state("andre", "Andre Carter", 1),
            _state("camille", "Camille Carter", 2),
            _state("julian", "Julian Moreland", 1),
        ]
        self.relationships = [
            _relationship("elias", "clara", "spouse"),
            _relationship("elias", "malik", "biological_parent"),
            _relationship("clara", "malik", "biological_parent"),
            _relationship("elias", "selah", "biological_parent"),
            _relationship("clara", "selah", "biological_parent"),
            _relationship("elias", "julian", "biological_parent"),
            _relationship("clara", "julian", "biological_parent"),
            _relationship("malik", "naomi", "spouse"),
            _relationship("malik", "eli", "biological_parent"),
            _relationship("malik", "imani", "biological_parent"),
            _relationship("imani", "marcus", "spouse"),
            _relationship("imani", "micah", "biological_parent"),
            _relationship("imani", "zara", "biological_parent"),
            _relationship("selah", "andre", "spouse"),
            _relationship("selah", "camille", "biological_parent"),
        ]

    def _compile(self, states=None, relationships=None):
        return compile_lineage_cinema(
            states=list(self.states if states is None else states),
            relationships=list(
                self.relationships if relationships is None else relationships
            ),
            anchor_state_id="member-malik",
        )

    def test_complete_moreland_style_tour_visits_every_approved_member(self):
        compiled = self._compile()

        self.assertEqual(
            compiled["compiler_version"], LINEAGE_CINEMA_COMPILER_VERSION
        )
        self.assertEqual(
            compiled["auto_advance_state_ids"][0], "member-malik"
        )
        self.assertEqual(
            set(compiled["auto_advance_state_ids"]),
            {state["id"] for state in self.states},
        )
        self.assertTrue(compiled["validation"]["complete"])
        self.assertEqual(compiled["validation"]["missing_state_ids"], [])
        self.assertEqual(
            compiled["validation"]["eligible_state_count"], len(self.states)
        )
        self.assertLessEqual(
            compiled["validation"]["tour_step_count"],
            compiled["validation"]["max_tour_steps"],
        )

    def test_repeated_routing_states_use_unique_steps_and_reach_sibling_branches(self):
        compiled = self._compile()
        sequence = compiled["auto_advance_state_ids"]
        step_ids = [step["step_id"] for step in compiled["tour_steps"]]

        self.assertGreater(sequence.count("member-malik"), 1)
        self.assertGreater(len(sequence), len(set(sequence)))
        self.assertIn("member-selah", sequence)
        self.assertIn("member-camille", sequence)
        self.assertIn("member-julian", sequence)
        self.assertEqual(len(step_ids), len(set(step_ids)))
        self.assertTrue(any(item.startswith("Return to ") for item in compiled["path_items"]))

    def test_branch_controls_expose_all_children_partners_and_siblings(self):
        compiled = self._compile()
        malik_navigation = compiled["navigation_by_state"]["member-malik"]

        self.assertEqual(
            set(malik_navigation["parents"]), {"member-elias", "member-clara"}
        )
        self.assertEqual(
            set(malik_navigation["children"]), {"member-eli", "member-imani"}
        )
        self.assertEqual(malik_navigation["partners"], ["member-naomi"])
        self.assertEqual(
            set(malik_navigation["siblings"]), {"member-selah", "member-julian"}
        )
        option_targets = {
            option["target_state_id"]
            for option in compiled["branch_options_by_state"]["member-malik"]
        }
        self.assertTrue(
            {
                "member-elias",
                "member-clara",
                "member-naomi",
                "member-eli",
                "member-imani",
                "member-selah",
                "member-julian",
            }.issubset(option_targets)
        )

    def test_visual_styles_preserve_verified_narrative_and_family_type_meaning(self):
        states = [
            _state("parent", "Parent", 0),
            _state("child", "Child", 1),
            _state("guardian", "Guardian", 0),
            _state("adoptive", "Adoptive Parent", 0),
            _state("former", "Former Partner", 0),
        ]
        relationships = [
            _relationship("parent", "child", "biological_parent"),
            _relationship(
                "guardian",
                "child",
                "guardian",
                mode="narrative",
                marker="narrative",
            ),
            _relationship("adoptive", "child", "adoptive_parent"),
            _relationship(
                "parent",
                "former",
                "former_spouse",
                mode="narrative",
                marker="narrative",
            ),
        ]
        compiled = compile_lineage_cinema(
            states=states,
            relationships=relationships,
            anchor_state_id="member-child",
        )
        styles = {
            edge["relationship_type"]: edge["visual_style"]
            for edge in compiled["relationship_edges"]
        }

        self.assertEqual(styles["biological_parent"], "solid")
        self.assertEqual(styles["guardian"], "dashed")
        self.assertEqual(styles["adoptive_parent"], "double")
        self.assertEqual(styles["former_spouse"], "historical")

    def test_pending_and_disputed_relationships_do_not_enter_published_tour(self):
        states = [_state("a", "A", 0), _state("b", "B", 1)]
        relationships = [
            _relationship(
                "a", "b", "biological_parent", mode="narrative", marker="pending"
            )
        ]
        compiled = compile_lineage_cinema(
            states=states,
            relationships=relationships,
            anchor_state_id="member-a",
        )

        self.assertEqual(compiled["relationship_edges"], [])
        self.assertIn("member-b", compiled["validation"]["disconnected_state_ids"])
        self.assertEqual(
            set(compiled["auto_advance_state_ids"]), {"member-a", "member-b"}
        )

    def test_hidden_parent_still_derives_visible_sibling_navigation(self):
        states = [_state("child-a", "Child A", 1), _state("child-b", "Child B", 1)]
        relationships = [
            _relationship("hidden-parent", "child-a", "biological_parent"),
            _relationship("hidden-parent", "child-b", "biological_parent"),
        ]
        compiled = compile_lineage_cinema(
            states=states,
            relationships=relationships,
            anchor_state_id="member-child-a",
        )

        self.assertEqual(
            compiled["navigation_by_state"]["member-child-a"]["siblings"],
            ["member-child-b"],
        )
        self.assertEqual(compiled["validation"]["disconnected_state_ids"], [])

    def test_output_is_deterministic_when_database_order_changes(self):
        forward = self._compile()
        reversed_input = self._compile(
            states=reversed(self.states),
            relationships=reversed(self.relationships),
        )

        self.assertEqual(
            forward["auto_advance_state_ids"],
            reversed_input["auto_advance_state_ids"],
        )
        self.assertEqual(
            forward["branch_options_by_state"],
            reversed_input["branch_options_by_state"],
        )
        self.assertEqual(
            forward["relationship_edges"],
            reversed_input["relationship_edges"],
        )

    def test_every_supported_family_type_compiles_into_the_correct_navigation_group(self):
        for relationship_type in ALLOWED_RELATIONSHIP_TYPES:
            with self.subTest(relationship_type=relationship_type):
                compiled = compile_lineage_cinema(
                    states=[
                        _state("source", "Source", 0),
                        _state("target", "Target", 1),
                    ],
                    relationships=[
                        _relationship("source", "target", relationship_type)
                    ],
                    anchor_state_id="member-target",
                )
                self.assertEqual(
                    compiled["relationship_edges"][0]["relationship_type"],
                    relationship_type,
                )
                source_navigation = compiled["navigation_by_state"]["member-source"]
                target_navigation = compiled["navigation_by_state"]["member-target"]
                if relationship_type in PARENT_RELATIONSHIP_TYPES or relationship_type == "grandparent":
                    self.assertIn("member-target", source_navigation["children"])
                    self.assertIn("member-source", target_navigation["parents"])
                elif relationship_type in PARTNER_RELATIONSHIP_TYPES:
                    self.assertIn("member-target", source_navigation["partners"])
                    self.assertIn("member-source", target_navigation["partners"])
                elif relationship_type in SIBLING_RELATIONSHIP_TYPES:
                    self.assertIn("member-target", source_navigation["siblings"])
                    self.assertIn("member-source", target_navigation["siblings"])
                else:
                    self.assertIn("member-target", source_navigation["branches"])
                    self.assertIn("member-source", target_navigation["branches"])

    def test_large_family_tour_is_complete_and_bounded(self):
        states = [_state(f"m{index}", f"Member {index:03d}", index) for index in range(250)]
        relationships = [
            _relationship(f"m{index}", f"m{index + 1}", "biological_parent")
            for index in range(249)
        ]
        compiled = compile_lineage_cinema(
            states=states,
            relationships=relationships,
            anchor_state_id="member-m0",
        )

        self.assertTrue(compiled["validation"]["complete"])
        self.assertTrue(compiled["validation"]["tour_bounded"])
        self.assertEqual(
            compiled["validation"]["unique_state_count_in_tour"], 250
        )

    def test_maximum_package_depth_does_not_depend_on_python_recursion(self):
        states = [
            _state(f"m{index}", f"Member {index:03d}", index)
            for index in range(999)
        ]
        relationships = [
            _relationship(f"m{index}", f"m{index + 1}", "biological_parent")
            for index in range(998)
        ]
        compiled = compile_lineage_cinema(
            states=states,
            relationships=relationships,
            anchor_state_id="member-m998",
        )

        self.assertTrue(compiled["validation"]["complete"])
        self.assertTrue(compiled["validation"]["tour_bounded"])
        self.assertEqual(
            compiled["validation"]["unique_state_count_in_tour"], 999
        )


if __name__ == "__main__":
    unittest.main()
