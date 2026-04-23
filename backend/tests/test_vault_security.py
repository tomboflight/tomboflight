import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import vault as vault_routes
from app.schemas.vault import VaultAccessGrantCreate, VaultItemCreate
from app.services import vault_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


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
        return [item for item in self.documents if self._matches(item, query)]

    def insert_one(self, document):
        stored = dict(document)
        stored["_id"] = stored.get("_id") or ObjectId()
        self.documents.append(stored)
        return FakeInsertResult(stored["_id"])

    def update_one(self, query, update):
        item = self.find_one(query)
        if item:
            item.update(update.get("$set", {}))

    def delete_one(self, query):
        target = self.find_one(query)
        if target:
            self.documents.remove(target)

    def sort(self, *_args, **_kwargs):
        return self

    def _matches(self, item, query):
        for key, expected in query.items():
            value = item.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if value not in expected["$in"]:
                        return False
                else:
                    return False
            elif value != expected:
                return False
        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents) for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class VaultSecurityTests(unittest.TestCase):
    def test_cross_project_create_denied(self):
        payload = VaultItemCreate(project_id="project-a", title="Secret")
        with patch.object(vault_service, "get_database", return_value=FakeDatabase()):
            with self.assertRaises(PermissionError):
                vault_service.create_vault_item(
                    payload,
                    "owner-1",
                    authorized_project_id="project-b",
                )

    def test_cross_project_read_denied(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {"_id": item_id, "project_id": "project-a", "owner_user_id": "owner-1", "title": "Item"}
                ]
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaises(PermissionError):
                vault_service.get_vault_item(
                    str(item_id),
                    "owner-1",
                    authorized_project_id="project-b",
                )

    def test_cross_project_grant_denied(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {"_id": item_id, "project_id": "project-a", "owner_user_id": "owner-1"}
                ]
            }
        )
        payload = VaultAccessGrantCreate(
            vault_item_id=str(item_id),
            grantee_user_id="grantee-1",
            grantee_project_id="project-b",
            permission_role="viewer",
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaises(PermissionError):
                vault_service.create_vault_access_grant(
                    payload,
                    "owner-1",
                    item_id=str(item_id),
                    authorized_project_id="project-a",
                )

    def test_path_payload_mismatch_rejected(self):
        payload = VaultAccessGrantCreate(
            vault_item_id="item-b",
            grantee_user_id="grantee-1",
            permission_role="viewer",
        )
        with self.assertRaises(HTTPException) as ctx:
            vault_routes.create_vault_access_grant_route(
                item_id="item-a",
                payload=payload,
                current_user={"id": "owner-1"},
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unauthorized_role_denied(self):
        payload = VaultItemCreate(project_id="project-a", title="Test")
        with (
            patch.object(vault_routes, "_resolve_vault_context", return_value={"project": {"_id": "project-a"}}),
            patch.object(
                vault_routes,
                "_require_vault_role",
                side_effect=HTTPException(status_code=403, detail="denied"),
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                vault_routes.create_vault_item_route(payload=payload, current_user={"id": "viewer-1"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_authorized_role_allowed(self):
        payload = VaultItemCreate(project_id="project-a", title="Allowed")
        with (
            patch.object(vault_routes, "_resolve_vault_context", return_value={"project": {"_id": "project-a"}}),
            patch.object(vault_routes, "_require_vault_role"),
            patch.object(vault_routes, "create_vault_item", return_value={"id": "item-1"}) as create_mock,
        ):
            result = vault_routes.create_vault_item_route(payload=payload, current_user={"id": "owner-1"})
        self.assertEqual(result["id"], "item-1")
        create_mock.assert_called_once()

    def test_scheduled_item_hidden_before_reveal_for_non_owner(self):
        item_id = ObjectId()
        reveal_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "reveal_at": reveal_at,
                        "release_state": "scheduled",
                    }
                ],
                "vault_access_grants": [
                    {
                        "_id": ObjectId(),
                        "vault_item_id": str(item_id),
                        "grantee_user_id": "grantee-1",
                        "permission_role": "viewer",
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaises(ValueError):
                vault_service.get_vault_item(
                    str(item_id),
                    "grantee-1",
                    authorized_project_id="project-a",
                )
            owner_item = vault_service.get_vault_item(
                str(item_id),
                "owner-1",
                authorized_project_id="project-a",
            )
        assert owner_item is not None
        self.assertEqual(owner_item["id"], str(item_id))


if __name__ == "__main__":
    unittest.main()
