from __future__ import annotations

import unittest

from bson import ObjectId

from app.core.relationship_catalog import relationship_generation_delta
from app.services.family_placement_service import (
    FamilyPlacementError,
    calculate_family_placement,
)


class _Collection:
    def __init__(self, documents):
        self.documents = list(documents)

    def find(self, query):
        family_values = set((query.get("family_id") or {}).get("$in") or [])
        if not family_values:
            return list(self.documents)
        return [
            item
            for item in self.documents
            if item.get("family_id") in family_values
        ]


class _Database:
    def __init__(self, members, relationships):
        self.collections = {
            "family_members": _Collection(members),
            "relationships": _Collection(relationships),
        }

    def __getitem__(self, name):
        return self.collections[name]


class FamilyPlacementServiceTests(unittest.TestCase):
    def setUp(self):
        self.family_id = str(ObjectId())
        self.parent_id = str(ObjectId())
        self.child_id = str(ObjectId())

    def test_parent_child_is_placed_one_generation_apart(self):
        db = _Database(
            [
                {"_id": ObjectId(self.parent_id), "family_id": self.family_id},
                {"_id": ObjectId(self.child_id), "family_id": self.family_id},
            ],
            [
                {
                    "family_id": self.family_id,
                    "source_member_id": self.parent_id,
                    "target_member_id": self.child_id,
                    "relationship_type": "step_parent",
                }
            ],
        )
        placement = calculate_family_placement(db, self.family_id)
        self.assertEqual(placement["assignments"][self.parent_id], 0)
        self.assertEqual(placement["assignments"][self.child_id], 1)

    def test_conflicting_peer_and_parent_edges_are_rejected(self):
        db = _Database(
            [
                {"_id": ObjectId(self.parent_id), "family_id": self.family_id},
                {"_id": ObjectId(self.child_id), "family_id": self.family_id},
            ],
            [
                {
                    "family_id": self.family_id,
                    "source_member_id": self.parent_id,
                    "target_member_id": self.child_id,
                    "relationship_type": "biological_parent",
                },
                {
                    "family_id": self.family_id,
                    "source_member_id": self.parent_id,
                    "target_member_id": self.child_id,
                    "relationship_type": "spouse",
                },
            ],
        )
        with self.assertRaises(FamilyPlacementError):
            calculate_family_placement(db, self.family_id)

    def test_unrelated_people_are_not_silently_guessed_into_tree(self):
        other_id = str(ObjectId())
        db = _Database(
            [
                {"_id": ObjectId(self.parent_id), "family_id": self.family_id},
                {"_id": ObjectId(other_id), "family_id": self.family_id},
            ],
            [],
        )
        placement = calculate_family_placement(db, self.family_id)
        self.assertEqual(placement["placement_status"][self.parent_id], "unplaced")
        self.assertEqual(placement["placement_status"][other_id], "unplaced")

    def test_inverse_household_bridge_deltas_are_explicit(self):
        self.assertEqual(relationship_generation_delta("step_child"), -1)
        self.assertEqual(relationship_generation_delta("grandchild"), -2)
        self.assertEqual(relationship_generation_delta("identity_bridge"), 0)


if __name__ == "__main__":
    unittest.main()
