import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import family_members as family_member_routes
from app.routes import relationships as relationship_routes
from app.routes import uploads as upload_routes
from app.schemas.relationship import RelationshipCreate
from app.services import access_context_service
from app.services.auth_service import build_user_response
from app.services.workspace_access_service import require_workspace_member_role


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query=None):
        query = query or {}
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    def _matches(self, document, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(document, option) for option in expected):
                    return False
                continue
            if document.get(key) != expected:
                return False
        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self._collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, FakeCollection())


class WorkspaceAccessRoleTests(unittest.TestCase):
    def test_resolve_default_project_uses_project_membership_for_invited_users(self):
        with (
            patch.object(
                access_context_service,
                "list_accessible_project_ids",
                return_value=["project-membership-1"],
            ) as membership_mock,
            patch.object(
                access_context_service,
                "list_user_project_entitlements",
                return_value=[],
            ) as entitlements_mock,
        ):
            project_id = access_context_service.resolve_default_project_id(
                {"id": "user-1", "email": "invitee@example.com"}
            )

        self.assertEqual(project_id, "project-membership-1")
        membership_mock.assert_called_once()
        entitlements_mock.assert_not_called()

    def test_auth_user_response_keeps_active_workspace_identifiers(self):
        payload = build_user_response(
            {
                "_id": "user-1",
                "email": "invitee@example.com",
                "full_name": "Invitee User",
                "role": "user",
                "status": "active",
                "created_at": "2026-04-10T00:00:00Z",
                "active_project_id": "project-123",
                "active_family_id": "family-456",
            }
        )
        self.assertEqual(payload["active_project_id"], "project-123")
        self.assertEqual(payload["active_family_id"], "family-456")

    def test_workspace_member_role_guard_blocks_viewer_write(self):
        with self.assertRaises(HTTPException) as error:
            require_workspace_member_role(
                {"is_admin": False, "member_role": "viewer"},
                allowed_roles=("billing_owner", "co_owner", "family_manager"),
                detail="Denied",
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_family_member_create_blocks_read_only_role(self):
        payload = {"family_id": "507f1f77bcf86cd799439011", "first_name": "Test"}
        context = {
            "family": {"_id": "507f1f77bcf86cd799439011"},
            "member_role": "viewer",
            "is_admin": False,
        }
        with (
            patch.object(
                family_member_routes,
                "get_database",
                return_value=FakeDatabase(),
            ),
            patch.object(
                family_member_routes,
                "require_workspace_capability",
                return_value=context,
            ),
        ):
            with self.assertRaises(HTTPException) as error:
                family_member_routes.create_family_member(
                    payload=payload,
                    current_user={"id": "user-1", "email": "viewer@example.com"},
                )
        self.assertEqual(error.exception.status_code, 403)

    def test_relationship_create_blocks_read_only_role(self):
        payload = RelationshipCreate(
            family_id="507f1f77bcf86cd799439011",
            source_member_id="member-a",
            target_member_id="member-b",
            relationship_type="spouse",
            notes="",
            created_by="",
        )
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(db=FakeDatabase()))
        )
        context = {
            "family": {"_id": "507f1f77bcf86cd799439011"},
            "member_role": "viewer",
            "is_admin": False,
        }
        with patch.object(
            relationship_routes,
            "require_workspace_capability",
            return_value=context,
        ):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(
                    relationship_routes.create_relationship(
                        payload=payload,
                        request=request,
                        current_user={"id": "user-1", "email": "viewer@example.com"},
                    )
                )
        self.assertEqual(error.exception.status_code, 403)

    def test_upload_management_allows_co_owner_even_if_not_uploader(self):
        upload_id = ObjectId()
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {
                        "_id": upload_id,
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "uploaded_by_user_id": "uploader-1",
                    }
                ]
            }
        )
        context = {
            "is_admin": False,
            "member_role": "co_owner",
            "project": {"_id": "project-1", "owner_user_id": "owner-1"},
        }
        with patch.object(upload_routes, "resolve_workspace_context", return_value=context):
            upload_record, resolved = upload_routes._require_upload_management_access(
                str(upload_id),
                db,
                {"id": "co-owner-1", "email": "coowner@example.com"},
            )
        self.assertEqual(str(upload_record["_id"]), str(upload_id))
        self.assertEqual(resolved.get("member_role"), "co_owner")

    def test_upload_management_blocks_viewer_when_not_uploader(self):
        upload_id = ObjectId()
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {
                        "_id": upload_id,
                        "project_id": "project-1",
                        "family_id": "family-1",
                        "uploaded_by_user_id": "uploader-1",
                    }
                ]
            }
        )
        context = {
            "is_admin": False,
            "member_role": "viewer",
            "project": {"_id": "project-1", "owner_user_id": "owner-1"},
        }
        with patch.object(upload_routes, "resolve_workspace_context", return_value=context):
            with self.assertRaises(HTTPException) as error:
                upload_routes._require_upload_management_access(
                    str(upload_id),
                    db,
                    {"id": "viewer-1", "email": "viewer@example.com"},
                )
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
