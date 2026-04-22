import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from app.routes import uploads as upload_routes
from app.services import link_request_service, tree_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class FakeDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query):
        for item in self.documents:
            if self._matches(item, query):
                return item
        return None

    def find(self, query=None, projection=None):
        del projection
        query = query or {}
        return [item for item in self.documents if self._matches(item, query)]

    def insert_one(self, document):
        stored = dict(document)
        stored["_id"] = stored.get("_id") or ObjectId()
        self.documents.append(stored)
        return FakeInsertResult(stored["_id"])

    def update_one(self, query, update):
        item = self.find_one(query)
        if not item:
            return FakeUpdateResult(0)
        item.update(update.get("$set", {}))
        return FakeUpdateResult(1)

    def delete_many(self, query):
        before = len(self.documents)
        self.documents = [item for item in self.documents if not self._matches(item, query)]
        return FakeDeleteResult(before - len(self.documents))

    def aggregate(self, pipeline):
        total = 0
        if pipeline:
            match = (pipeline[0] or {}).get("$match", {})
            for item in self.documents:
                if self._matches(item, match):
                    total += int(item.get("size_bytes") or 0)
        if total <= 0:
            return []
        return [{"_id": None, "total": total}]

    def _matches(self, document, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(document, option) for option in expected):
                    return False
                continue

            value = document.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if value not in expected["$in"]:
                        return False
                elif "$ne" in expected:
                    if value == expected["$ne"]:
                        return False
                else:
                    return False
            elif value != expected:
                return False
        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]

    def __getattr__(self, name):
        return self[name]


class LinkRequestApprovalTests(unittest.TestCase):
    def test_approve_link_request_creates_household_link(self):
        request_id = ObjectId()
        db = FakeDatabase(
            {
                "link_requests": [
                    {
                        "_id": request_id,
                        "source_project_id": "project-a",
                        "target_project_id": "project-b",
                        "source_household_id": "household-a",
                        "target_household_id": "household-b",
                        "source_key": "SRC-KEY",
                        "target_key": "TGT-KEY",
                        "status": "pending",
                    }
                ],
                "household_links": [],
            }
        )

        with (
            patch.object(link_request_service, "get_database", return_value=db),
            patch.object(link_request_service, "user_can_access_project", return_value=True),
            patch.object(link_request_service, "project_supports_link_keys", return_value=True),
            patch.object(
                link_request_service,
                "get_active_key_doc_for_project",
                side_effect=lambda project_id: {
                    "key_value": "SRC-KEY" if project_id == "project-a" else "TGT-KEY"
                },
            ),
            patch.object(
                link_request_service,
                "get_project_summary",
                side_effect=lambda project_id: {
                    "project_name": project_id,
                    "package_code": "legacy_plus",
                    "household_id": "household-a"
                    if project_id == "project-a"
                    else "household-b",
                },
            ),
        ):
            updated = link_request_service.approve_link_request(
                str(request_id),
                approved_by="Approver",
                approver_user_id="user-1",
                is_admin=False,
            )

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["status"], "approved")
        links = db["household_links"].documents
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["source_household_id"], "household-a")
        self.assertEqual(links[0]["target_household_id"], "household-b")
        self.assertEqual(links[0]["link_status"], "approved")

    def test_approve_link_request_rejects_when_workspace_lacks_link_capability(self):
        request_id = ObjectId()
        db = FakeDatabase(
            {
                "link_requests": [
                    {
                        "_id": request_id,
                        "source_project_id": "project-a",
                        "target_project_id": "project-b",
                        "source_household_id": "household-a",
                        "target_household_id": "household-b",
                        "source_key": "SRC-KEY",
                        "target_key": "TGT-KEY",
                        "status": "pending",
                    }
                ],
                "household_links": [],
            }
        )

        with (
            patch.object(link_request_service, "get_database", return_value=db),
            patch.object(link_request_service, "user_can_access_project", return_value=True),
            patch.object(
                link_request_service,
                "project_supports_link_keys",
                side_effect=lambda project_id: project_id == "project-b",
            ),
        ):
            with self.assertRaises(ValueError):
                link_request_service.approve_link_request(
                    str(request_id),
                    approved_by="Approver",
                    approver_user_id="user-1",
                    is_admin=False,
                )

        self.assertEqual(len(db["household_links"].documents), 0)


class LinkedTreeTests(unittest.TestCase):
    def test_private_family_tree_payload_is_json_safe(self):
        family_id = ObjectId()
        parent_id = ObjectId()
        child_id = ObjectId()
        created_at = datetime(2026, 4, 14, 23, 0, tzinfo=timezone.utc)
        db = FakeDatabase(
            {
                "families": [
                    {
                        "_id": family_id,
                        "family_name": "Robinson",
                        "household_id": "household-a",
                        "created_at": created_at,
                    }
                ],
                "family_members": [
                    {
                        "_id": parent_id,
                        "family_id": family_id,
                        "first_name": "Parent",
                        "last_name": "One",
                        "generation": 0,
                        "created_at": created_at,
                    },
                    {
                        "_id": child_id,
                        "family_id": family_id,
                        "first_name": "Child",
                        "last_name": "One",
                        "generation": 1,
                        "created_at": created_at,
                    },
                ],
                "lineage_nodes": [
                    {
                        "_id": ObjectId(),
                        "family_id": family_id,
                        "member_id": child_id,
                        "generation": 1,
                        "created_at": created_at,
                    }
                ],
                "relationships": [
                    {
                        "_id": ObjectId(),
                        "family_id": family_id,
                        "source_member_id": parent_id,
                        "target_member_id": child_id,
                        "relationship_type": "parent_child",
                        "created_at": created_at,
                    }
                ],
            }
        )

        with patch.object(tree_service, "get_database", return_value=db):
            tree = tree_service.get_filtered_family_tree(str(family_id), "private")

        encoded = jsonable_encoder(tree)
        self.assertEqual(encoded["family"]["id"], str(family_id))
        self.assertEqual(encoded["family"]["_id"], str(family_id))
        self.assertEqual(encoded["members"][0]["family_id"], str(family_id))
        self.assertEqual(
            encoded["relationships"][0]["source_member_id"],
            str(parent_id),
        )
        self.assertEqual(encoded["nodes"][0]["member_id"], str(child_id))

    def test_linked_family_tree_includes_approved_household_neighbors(self):
        family_a = ObjectId()
        family_b = ObjectId()
        member_a = ObjectId()
        member_b = ObjectId()
        db = FakeDatabase(
            {
                "families": [
                    {"_id": family_a, "family_name": "A", "household_id": "household-a"},
                    {"_id": family_b, "family_name": "B", "household_id": "household-b"},
                ],
                "household_links": [
                    {
                        "source_household_id": "household-a",
                        "target_household_id": "household-b",
                        "link_status": "approved",
                    }
                ],
                "family_members": [
                    {"_id": member_a, "family_id": str(family_a), "first_name": "A", "last_name": "One"},
                    {"_id": member_b, "family_id": str(family_b), "first_name": "B", "last_name": "One"},
                ],
                "lineage_nodes": [],
                "relationships": [],
            }
        )

        with patch.object(tree_service, "get_database", return_value=db):
            tree = tree_service.get_linked_family_tree(str(family_a))

        self.assertEqual(tree["family_id"], str(family_a))
        self.assertIn(str(family_a), tree["linked_family_ids"])
        self.assertIn(str(family_b), tree["linked_family_ids"])
        member_ids = {item["id"] for item in tree["members"]}
        self.assertIn(str(member_a), member_ids)
        self.assertIn(str(member_b), member_ids)

    def test_tree_model_keeps_spouse_ancestry_and_union_children_separate(self):
        family_id = ObjectId()
        me_id = ObjectId()
        spouse_id = ObjectId()
        my_mother_id = ObjectId()
        spouse_mother_id = ObjectId()
        shared_child_id = ObjectId()
        step_child_id = ObjectId()
        db = FakeDatabase(
            {
                "families": [
                    {"_id": family_id, "family_name": "Household", "household_id": "h-1"},
                ],
                "family_members": [
                    {"_id": me_id, "family_id": str(family_id), "first_name": "Me", "generation": 1, "mother_id": str(my_mother_id)},
                    {"_id": spouse_id, "family_id": str(family_id), "first_name": "Spouse", "generation": 1, "mother_id": str(spouse_mother_id)},
                    {"_id": my_mother_id, "family_id": str(family_id), "first_name": "MyMom", "generation": 0},
                    {"_id": spouse_mother_id, "family_id": str(family_id), "first_name": "SpouseMom", "generation": 0},
                    {"_id": shared_child_id, "family_id": str(family_id), "first_name": "SharedChild", "generation": 2},
                    {"_id": step_child_id, "family_id": str(family_id), "first_name": "StepChild", "generation": 2},
                ],
                "lineage_nodes": [],
                "relationships": [
                    {"_id": ObjectId(), "family_id": str(family_id), "source_member_id": str(me_id), "target_member_id": str(spouse_id), "relationship_type": "spouse"},
                    {"_id": ObjectId(), "family_id": str(family_id), "source_member_id": str(me_id), "target_member_id": str(shared_child_id), "relationship_type": "biological_parent"},
                    {"_id": ObjectId(), "family_id": str(family_id), "source_member_id": str(spouse_id), "target_member_id": str(shared_child_id), "relationship_type": "biological_parent"},
                    {"_id": ObjectId(), "family_id": str(family_id), "source_member_id": str(spouse_id), "target_member_id": str(step_child_id), "relationship_type": "step_parent"},
                ],
            }
        )

        with patch.object(tree_service, "get_database", return_value=db):
            payload = tree_service.get_family_tree(str(family_id))

        model = payload["tree_model"]
        people = {item["person_id"]: item for item in model["people"]}
        spouse = people[str(spouse_id)]
        me = people[str(me_id)]
        self.assertIn(str(spouse_mother_id), spouse["parent_ids"])
        self.assertNotIn(str(spouse_mother_id), me["parent_ids"])
        unions = model["unions"]
        self.assertEqual(len(unions), 1)
        self.assertEqual(unions[0]["shared_child_ids"], [str(shared_child_id)])


class UploadPrivacyAndStorageTests(unittest.TestCase):
    def test_private_upload_allows_owner_download_access(self):
        upload_id = ObjectId()
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {
                        "_id": upload_id,
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "uploaded_by_user_id": "owner-1",
                        "customer_visible": False,
                        "internal_only": False,
                    }
                ]
            }
        )
        current_user = {"id": "owner-1", "email": "owner@example.com"}

        with patch.object(
            upload_routes,
            "require_workspace_capability",
            return_value={"project": {"_id": "project-1"}, "is_admin": False},
        ):
            upload_record, _context = upload_routes._require_upload_access(
                str(upload_id),
                db,
                current_user,
                detail="test",
            )

        self.assertEqual(str(upload_record["_id"]), str(upload_id))

    def test_workspace_storage_limit_enforced(self):
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {"project_id": "project-1", "size_bytes": 500},
                    {"project_id": "project-1", "size_bytes": 600},
                ]
            }
        )
        context = {
            "project": {"_id": "project-1"},
            "family": {"_id": "family-1"},
            "resolved_entitlements": {"max_storage_gb": 0.000001},
        }

        with self.assertRaises(HTTPException):
            upload_routes._enforce_workspace_storage_limit(
                context=context,
                db=db,
                incoming_size_bytes=200,
            )


if __name__ == "__main__":
    unittest.main()
