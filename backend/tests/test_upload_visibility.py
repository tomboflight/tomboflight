import unittest
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import uploads as upload_routes


class FakeCursor(list):
    def sort(self, field_name, direction):
        self.sort_key = field_name
        reverse = direction < 0
        return FakeCursor(
            sorted(self, key=lambda item: str(item.get(field_name) or ""), reverse=reverse)
        )


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query=None):
        query = query or {}
        for item in self.documents:
            if self._matches(item, query):
                return item
        return None

    def find(self, query=None):
        query = query or {}
        return FakeCursor([item for item in self.documents if self._matches(item, query)])

    def _matches(self, item, query):
        for key, expected in (query or {}).items():
            if key == "$or":
                if not any(self._matches(item, option) for option in expected):
                    return False
                continue

            value = item.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if value not in expected["$in"]:
                        return False
                elif "$ne" in expected:
                    if value == expected["$ne"]:
                        return False
                elif "$nin" in expected:
                    if value in expected["$nin"]:
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


def workspace_context():
    return {
        "member": {"_id": "member-1"},
        "family": {"_id": "family-1"},
        "project": {"_id": "project-1"},
        "is_admin": False,
        "resolved_entitlements": {
            "can_upload_verification_docs": True,
            "can_upload_portraits": True,
        },
    }


class UploadVisibilityTests(unittest.TestCase):
    def test_member_uploads_include_owner_private_verification_records(self):
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {
                        "_id": ObjectId(),
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "category": "verification_evidence",
                        "original_filename": "marquis-id.pdf",
                        "uploaded_by_user_id": "owner-1",
                        "customer_visible": False,
                        "internal_only": False,
                        "privacy_classification": "owner_only",
                        "created_at": "2026-04-13T20:00:00Z",
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "category": "verification_evidence",
                        "original_filename": "other-private.pdf",
                        "uploaded_by_user_id": "other-user",
                        "customer_visible": False,
                        "internal_only": False,
                        "privacy_classification": "owner_only",
                        "created_at": "2026-04-13T20:01:00Z",
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "category": "verification_evidence",
                        "original_filename": "admin-redacted.pdf",
                        "uploaded_by_user_id": "owner-1",
                        "customer_visible": False,
                        "internal_only": True,
                        "privacy_classification": "admin_only",
                        "created_at": "2026-04-13T20:02:00Z",
                    },
                ]
            }
        )

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(upload_routes, "require_workspace_capability", return_value=workspace_context()),
        ):
            payload = upload_routes.list_member_uploads(
                "member-1",
                category="verification_evidence",
                current_user={"id": "owner-1", "email": "marquis@example.com"},
            )

        filenames = {item["original_filename"] for item in payload["uploads"]}
        self.assertEqual(payload["count"], 1)
        self.assertEqual(filenames, {"marquis-id.pdf"})

    def test_family_uploads_include_owner_private_records_without_member_filter(self):
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {
                        "_id": ObjectId(),
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "category": "verification_evidence",
                        "original_filename": "marquis-record.pdf",
                        "uploaded_by_user_id": "owner-1",
                        "customer_visible": False,
                        "internal_only": False,
                        "privacy_classification": "owner_only",
                        "created_at": "2026-04-13T20:00:00Z",
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": "project-2",
                        "family_id": "family-2",
                        "member_id": "member-2",
                        "category": "verification_evidence",
                        "original_filename": "larry-record.pdf",
                        "uploaded_by_user_id": "owner-1",
                        "customer_visible": False,
                        "internal_only": False,
                        "privacy_classification": "owner_only",
                        "created_at": "2026-04-13T20:01:00Z",
                    },
                ]
            }
        )

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(upload_routes, "require_workspace_capability", return_value=workspace_context()),
        ):
            payload = upload_routes.list_family_uploads(
                "family-1",
                category="verification_evidence",
                current_user={"id": "owner-1", "email": "marquis@example.com"},
            )

        filenames = {item["original_filename"] for item in payload["uploads"]}
        self.assertEqual(payload["count"], 1)
        self.assertEqual(filenames, {"marquis-record.pdf"})

    def test_owner_can_download_legacy_internal_verification_upload(self):
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
                        "internal_only": True,
                        "privacy_classification": "owner_only",
                    }
                ]
            }
        )

        with patch.object(
            upload_routes,
            "require_workspace_capability",
            return_value={"project": {"_id": "project-1"}, "is_admin": False},
        ):
            upload_record, _context = upload_routes._require_upload_access(
                str(upload_id),
                db,
                {"id": "owner-1", "email": "marquis@example.com"},
                detail="test",
            )

        self.assertEqual(str(upload_record["_id"]), str(upload_id))

    def test_non_owner_cannot_download_internal_verification_upload(self):
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
                        "internal_only": True,
                        "privacy_classification": "owner_only",
                    }
                ]
            }
        )

        with patch.object(
            upload_routes,
            "require_workspace_capability",
            return_value={"project": {"_id": "project-1"}, "is_admin": False},
        ):
            with self.assertRaises(HTTPException):
                upload_routes._require_upload_access(
                    str(upload_id),
                    db,
                    {"id": "other-user", "email": "other@example.com"},
                    detail="test",
                )


if __name__ == "__main__":
    unittest.main()
