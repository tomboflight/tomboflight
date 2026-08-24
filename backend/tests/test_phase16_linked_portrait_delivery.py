from __future__ import annotations

import unittest
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import uploads
from app.services import linked_network_service


class _Collection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query):
        return next(
            (
                document
                for document in self.documents
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )


class _Database:
    def __init__(self, upload):
        self.uploads = _Collection([upload])

    def __getitem__(self, name):
        if name == "uploaded_files":
            return self.uploads
        return _Collection()


class Phase16LinkedPortraitDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.upload_id = str(ObjectId())
        self.member_id = str(ObjectId())
        self.upload = {
            "_id": ObjectId(self.upload_id),
            "category": "member_photo",
            "member_id": self.member_id,
            "project_id": "linked-project",
        }
        self.context = {
            "project": {"_id": "root-project"},
            "resolved_entitlements": {"can_link_households": True},
        }
        self.network = {
            "nodes": [
                {
                    "id": self.member_id,
                    "source_project_id": "linked-project",
                    "approved_photo_upload_id": self.upload_id,
                }
            ]
        }

    def test_explicitly_shared_linked_portrait_is_deliverable_from_root_viewer(self):
        with (
            patch.object(
                uploads,
                "require_workspace_capability",
                return_value=self.context,
            ),
            patch.object(uploads, "build_linked_network", return_value=self.network),
        ):
            upload, context = uploads._require_linked_cinematic_upload_access(
                self.upload_id,
                "root-project",
                _Database(self.upload),
                {"id": "root-user"},
            )

        self.assertEqual(str(upload["_id"]), self.upload_id)
        self.assertIs(context, self.context)

    def test_unshared_portrait_cannot_be_unlocked_with_a_guessed_project_query(self):
        with (
            patch.object(
                uploads,
                "require_workspace_capability",
                return_value=self.context,
            ),
            patch.object(uploads, "build_linked_network", return_value={"nodes": []}),
            self.assertRaises(HTTPException) as raised,
        ):
            uploads._require_linked_cinematic_upload_access(
                self.upload_id,
                "root-project",
                _Database(self.upload),
                {"id": "root-user"},
            )

        self.assertEqual(raised.exception.status_code, 403)

    def test_cross_household_portrait_requires_customer_visibility_and_explicit_share(self):
        upload = {
            **self.upload,
            "family_id": "linked-family",
            "scan_status": "clean",
            "quarantined": False,
            "approved_for_cinematic": True,
            "verification_status": "approved",
            "consent_status": "approved",
            "consent_attested": True,
            "authority_attested": True,
            "customer_visible": True,
            "internal_only": False,
            "share_with_linked_families": True,
            "privacy_scope": "linked_family_shared",
        }
        member = {
            "_id": ObjectId(self.member_id),
            "approved_photo_upload_id": self.upload_id,
        }
        collection = _Collection([upload])

        with patch.object(
            linked_network_service,
            "_col",
            return_value=collection,
        ):
            approved = linked_network_service._approved_portrait_for_network(
                member,
                family_id="linked-family",
                is_own_household=False,
            )
            upload["internal_only"] = True
            blocked = linked_network_service._approved_portrait_for_network(
                member,
                family_id="linked-family",
                is_own_household=False,
            )

        self.assertIsNotNone(approved)
        self.assertIsNone(blocked)

    def test_provenance_mismatch_fails_closed(self):
        network = {
            "nodes": [
                {
                    "id": self.member_id,
                    "source_project_id": "different-linked-project",
                    "approved_photo_upload_id": self.upload_id,
                }
            ]
        }
        with (
            patch.object(
                uploads,
                "require_workspace_capability",
                return_value=self.context,
            ),
            patch.object(uploads, "build_linked_network", return_value=network),
            self.assertRaises(HTTPException) as raised,
        ):
            uploads._require_linked_cinematic_upload_access(
                self.upload_id,
                "root-project",
                _Database(self.upload),
                {"id": "root-user"},
            )

        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
