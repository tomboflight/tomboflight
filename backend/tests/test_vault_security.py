import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import vault as vault_routes
from app.schemas.vault import (
    VaultAccessGrantCreate,
    VaultAccessGrantUpdate,
    VaultItemCreate,
    VaultReleaseRuleCreate,
    VaultReleaseRuleUpdate,
)
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

    def test_revoked_grant_cannot_open_vault_item(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "title": "Closed account evidence",
                    }
                ],
                "vault_access_grants": [
                    {
                        "_id": ObjectId(),
                        "vault_item_id": str(item_id),
                        "grantee_user_id": "deleted-user",
                        "permission_role": "viewer",
                        "status": "revoked",
                    }
                ],
            }
        )

        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(item_id),
                    "deleted-user",
                    authorized_project_id="project-a",
                )

    def test_expired_grant_is_inactive(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "selected_relatives",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
                "vault_access_grants": [
                    {
                        "_id": ObjectId(),
                        "vault_item_id": str(item_id),
                        "grantee_user_id": "viewer-1",
                        "permission_role": "viewer",
                        "status": "active",
                        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(item_id),
                    "viewer-1",
                    authorized_project_id="project-a",
                )
            listed = vault_service.list_vault_items(
                "project-a",
                "viewer-1",
                authorized_project_id="project-a",
            )
        self.assertEqual(listed, [])

    def test_private_owner_item_stays_owner_only(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "private_owner",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
                "vault_access_grants": [
                    {
                        "_id": ObjectId(),
                        "vault_item_id": str(item_id),
                        "grantee_user_id": "co-owner-1",
                        "permission_role": "steward",
                        "status": "active",
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(item_id),
                    "co-owner-1",
                    authorized_project_id="project-a",
                    requesting_workspace_role="co_owner",
                    link_status="accepted",
                )

    def test_accepted_co_owner_can_open_released_household_admin_item(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "household_admins",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                    }
                ]
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(item_id),
                    "co-owner-1",
                    authorized_project_id="project-a",
                    requesting_workspace_role="co_owner",
                    link_status="",
                )
            item = vault_service.get_vault_item(
                str(item_id),
                "co-owner-1",
                authorized_project_id="project-a",
                requesting_workspace_role="co_owner",
                link_status="accepted",
            )
        self.assertIsNotNone(item)

    def test_all_linked_requires_verified_active_link_status(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "all_linked",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                    }
                ]
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(item_id),
                    "relative-1",
                    authorized_project_id="project-a",
                    requesting_workspace_role="linked_relative",
                    link_status="",
                )
            linked = vault_service.get_vault_item(
                str(item_id),
                "relative-1",
                authorized_project_id="project-a",
                requesting_workspace_role="linked_relative",
                link_status="accepted",
            )
        self.assertIsNotNone(linked)

    def test_access_disabled_blocks_even_the_owner(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "status": "active",
                        "access_enabled": False,
                    }
                ]
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "not available"):
                vault_service.get_vault_item(
                    str(item_id),
                    "owner-1",
                    authorized_project_id="project-a",
                )

    def test_trustee_rule_is_fail_closed_until_satisfied(self):
        item_id = ObjectId()
        rule_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "selected_relatives",
                        "release_state": "scheduled",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
                "vault_access_grants": [
                    {
                        "_id": ObjectId(),
                        "vault_item_id": str(item_id),
                        "grantee_user_id": "viewer-1",
                        "permission_role": "viewer",
                        "status": "active",
                    }
                ],
                "vault_release_rules": [
                    {
                        "_id": rule_id,
                        "vault_item_id": str(item_id),
                        "trigger_type": "after_trustee_approval",
                        "release_to": "named_list",
                        "named_recipients": ["viewer-1"],
                        "trustee_user_id": "trustee-1",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "not released"):
                vault_service.get_vault_item(
                    str(item_id),
                    "viewer-1",
                    authorized_project_id="project-a",
                )
            with self.assertRaisesRegex(PermissionError, "named trustee"):
                vault_service.update_vault_release_rule(
                    str(item_id),
                    str(rule_id),
                    VaultReleaseRuleUpdate(status="satisfied"),
                    "owner-1",
                    authorized_project_id="project-a",
                )
            updated = vault_service.update_vault_release_rule(
                str(item_id),
                str(rule_id),
                VaultReleaseRuleUpdate(status="satisfied"),
                "trustee-1",
                authorized_project_id="project-a",
            )
            released = vault_service.get_vault_item(
                str(item_id),
                "viewer-1",
                authorized_project_id="project-a",
            )
        self.assertEqual(updated["status"], "satisfied")
        self.assertIsNotNone(released)

    def test_revoke_api_immediately_disables_grant(self):
        item_id = ObjectId()
        grant_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "selected_relatives",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
                "vault_access_grants": [
                    {
                        "_id": grant_id,
                        "vault_item_id": str(item_id),
                        "grantee_user_id": "viewer-1",
                        "permission_role": "viewer",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            renewed = vault_service.update_vault_access_grant(
                str(item_id),
                str(grant_id),
                VaultAccessGrantUpdate(expires_at=None),
                "owner-1",
                authorized_project_id="project-a",
            )
            revoked = vault_service.revoke_vault_access_grant(
                str(item_id),
                str(grant_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(item_id),
                    "viewer-1",
                    authorized_project_id="project-a",
                )
        self.assertIsNone(renewed["expires_at"])
        self.assertEqual(revoked["status"], "revoked")
        self.assertFalse(revoked["access_enabled"])

    def test_new_grantee_trustee_and_named_recipient_references_must_exist(self):
        item_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "selected_relatives",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
                "users": [{"_id": "trustee-existing"}],
            }
        )
        grant = VaultAccessGrantCreate(
            vault_item_id=str(item_id),
            grantee_user_id="missing-user",
        )
        trustee_rule = VaultReleaseRuleCreate(
            vault_item_id=str(item_id),
            trigger_type="after_trustee_approval",
            trustee_user_id="missing-trustee",
            release_to="household",
        )
        named_rule = VaultReleaseRuleCreate(
            vault_item_id=str(item_id),
            trigger_type="to_named",
            named_recipients=["missing-recipient"],
            release_to="named_list",
            trustee_user_id="trustee-existing",
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Vault grantee not found"):
                vault_service.create_vault_access_grant(
                    grant,
                    "owner-1",
                    item_id=str(item_id),
                    authorized_project_id="project-a",
                )
            with self.assertRaisesRegex(ValueError, "Vault trustee not found"):
                vault_service.create_vault_release_rule(
                    trustee_rule,
                    "owner-1",
                    item_id=str(item_id),
                    authorized_project_id="project-a",
                )
            with self.assertRaisesRegex(ValueError, "Named Vault recipient not found"):
                vault_service.create_vault_release_rule(
                    named_rule,
                    "owner-1",
                    item_id=str(item_id),
                    authorized_project_id="project-a",
                )

    def test_named_trustee_can_satisfy_rule_through_route(self):
        item_id = ObjectId()
        rule_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "vault_scope": "household",
                        "privacy": "selected_relatives",
                        "release_state": "scheduled",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
                "vault_release_rules": [
                    {
                        "_id": rule_id,
                        "vault_item_id": str(item_id),
                        "trigger_type": "after_trustee_approval",
                        "release_to": "household",
                        "trustee_user_id": "trustee-1",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
            }
        )

        def enforce_workspace_role(context, *, allowed_roles, detail):
            del detail
            if context["member_role"] not in allowed_roles:
                raise HTTPException(status_code=403, detail="denied")
            return context

        context = {
            "project": {"_id": "project-a"},
            "member_role": "viewer",
            "resolved_entitlements": {
                "can_use_household_vault": True,
                "can_use_scheduled_reveal": True,
                "can_use_future_message_vault": True,
            },
        }
        with (
            patch.object(vault_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
            patch.object(vault_routes, "_resolve_vault_context", return_value=context),
            patch.object(vault_routes, "require_workspace_member_role", side_effect=enforce_workspace_role),
            patch.object(vault_routes, "_require_release_entitlements"),
        ):
            result = vault_routes.update_vault_release_rule_route(
                item_id=str(item_id),
                rule_id=str(rule_id),
                payload=VaultReleaseRuleUpdate(status="satisfied"),
                current_user={"id": "trustee-1"},
            )
        self.assertEqual(result["status"], "satisfied")

    def test_upload_linkage_creates_and_appends_asset_versions(self):
        first_upload_id = ObjectId()
        second_upload_id = ObjectId()
        db = FakeDatabase(
            {
                "families": [{"_id": "family-1", "project_id": "project-a"}],
                "family_members": [{"_id": "member-1", "family_id": "family-1"}],
                "uploaded_files": [
                    {
                        "_id": first_upload_id,
                        "project_id": "project-a",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "uploaded_by_user_id": "owner-1",
                        "asset_type": "vault_photo",
                        "privacy_scope": "private_to_owner_and_co_owner",
                        "vault_scope": "household",
                        "original_filename": "portrait-one.png",
                        "content_type": "image/png",
                        "scan_status": "clean",
                    },
                    {
                        "_id": second_upload_id,
                        "project_id": "project-a",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "uploaded_by_user_id": "owner-1",
                        "asset_type": "vault_photo",
                        "privacy_scope": "private_to_owner_and_co_owner",
                        "vault_scope": "household",
                        "original_filename": "portrait-two.png",
                        "content_type": "image/png",
                        "scan_status": "clean",
                        "version": 2,
                        "replaces_upload_id": str(first_upload_id),
                    },
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            created = vault_service.ensure_vault_item_for_upload(
                str(first_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            replaced = vault_service.ensure_vault_item_for_upload(
                str(second_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    created["id"],
                    "manager-1",
                    authorized_project_id="project-a",
                    requesting_workspace_role="family_manager",
                    link_status="active",
                )
            co_owner_item = vault_service.get_vault_item(
                created["id"],
                "co-owner-1",
                authorized_project_id="project-a",
                requesting_workspace_role="co_owner",
                link_status="accepted",
            )
        self.assertEqual(created["release_state"], "released")
        self.assertEqual(created["privacy"], "owner_and_co_owner")
        self.assertIsNotNone(co_owner_item)
        self.assertEqual(
            vault_service._vault_privacy_for_upload({"privacy_scope": "household_private"}),
            "household_admins",
        )
        self.assertEqual(replaced["current_upload_id"], str(second_upload_id))
        self.assertEqual(replaced["asset_version"], 2)
        self.assertEqual(len(replaced["asset_versions"]), 2)
        first = db["uploaded_files"].find_one({"_id": first_upload_id})
        second = db["uploaded_files"].find_one({"_id": second_upload_id})
        self.assertEqual(first["replaced_by_upload_id"], str(second_upload_id))
        self.assertEqual(second["version"], 2)

    def test_upload_release_fields_preserve_draft_and_future_schedule(self):
        draft_upload_id = ObjectId()
        scheduled_upload_id = ObjectId()
        reveal_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        common = {
            "project_id": "project-a",
            "family_id": "family-1",
            "member_id": "member-1",
            "uploaded_by_user_id": "owner-1",
            "asset_type": "vault_document",
            "privacy_scope": "private_to_owner_and_co_owner",
            "vault_scope": "household",
            "content_type": "application/pdf",
            "scan_status": "clean",
        }
        db = FakeDatabase(
            {
                "families": [{"_id": "family-1", "project_id": "project-a"}],
                "family_members": [{"_id": "member-1", "family_id": "family-1"}],
                "uploaded_files": [
                    {
                        **common,
                        "_id": draft_upload_id,
                        "original_filename": "draft.pdf",
                        "release_state": "draft",
                    },
                    {
                        **common,
                        "_id": scheduled_upload_id,
                        "original_filename": "scheduled.pdf",
                        "release_state": "scheduled",
                        "reveal_at": reveal_at,
                    },
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            draft = vault_service.ensure_vault_item_for_upload(
                str(draft_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            scheduled = vault_service.ensure_vault_item_for_upload(
                str(scheduled_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            for item in (draft, scheduled):
                with self.assertRaisesRegex(ValueError, "not released"):
                    vault_service.get_vault_item(
                        item["id"],
                        "co-owner-1",
                        authorized_project_id="project-a",
                        requesting_workspace_role="co_owner",
                        link_status="accepted",
                    )
        self.assertEqual(draft["release_state"], "draft")
        self.assertEqual(scheduled["release_state"], "scheduled")
        self.assertEqual(scheduled["reveal_at"], reveal_at)

    def test_organization_upload_keeps_canonical_scope_without_family_references(self):
        upload_id = ObjectId()
        db = FakeDatabase(
            {
                "uploaded_files": [
                    {
                        "_id": upload_id,
                        "project_id": "project-a",
                        "uploaded_by_user_id": "owner-1",
                        "asset_type": "vault_document",
                        "privacy_scope": "private_to_owner",
                        "vault_scope": "organization",
                        "original_filename": "board-record.pdf",
                        "content_type": "application/pdf",
                        "scan_status": "clean",
                    }
                ]
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            created = vault_service.ensure_vault_item_for_upload(
                str(upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
        self.assertEqual(created["vault_scope"], "organization")
        self.assertEqual(created["item_type"], "document")
        with self.assertRaisesRegex(ValueError, "cannot reference a family"):
            VaultItemCreate(
                project_id="project-a",
                family_id="family-1",
                title="Invalid organization record",
                vault_scope="organization",
            )

    def test_legacy_missing_release_state_preserves_shared_access_but_governed_data_stays_locked(self):
        shared_id = ObjectId()
        private_id = ObjectId()
        timed_id = ObjectId()
        governed_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": shared_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "owner_and_co_owner",
                        "title": "Legacy shared",
                    },
                    {
                        "_id": private_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "private_owner",
                        "title": "Legacy private",
                    },
                    {
                        "_id": timed_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "owner_and_co_owner",
                        "reveal_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                        "title": "Legacy timed",
                    },
                    {
                        "_id": governed_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "owner_and_co_owner",
                        "title": "Legacy governed",
                    },
                ],
                "vault_release_rules": [
                    {
                        "_id": ObjectId(),
                        "vault_item_id": str(governed_id),
                        "trigger_type": "on_death",
                        "trustee_user_id": "trustee-1",
                        "release_to": "household",
                        "status": "active",
                        "access_enabled": True,
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            shared = vault_service.get_vault_item(
                str(shared_id),
                "co-owner-1",
                authorized_project_id="project-a",
                requesting_workspace_role="co_owner",
                link_status="approved",
            )
            with self.assertRaisesRegex(ValueError, "Access denied"):
                vault_service.get_vault_item(
                    str(private_id),
                    "co-owner-1",
                    authorized_project_id="project-a",
                    requesting_workspace_role="co_owner",
                    link_status="approved",
                )
            for locked_id in (timed_id, governed_id):
                with self.assertRaisesRegex(ValueError, "not released"):
                    vault_service.get_vault_item(
                        str(locked_id),
                        "co-owner-1",
                        authorized_project_id="project-a",
                        requesting_workspace_role="co_owner",
                        link_status="approved",
                    )
        self.assertEqual(shared["effective_release_state"], "released")

    def test_reverse_legacy_current_upload_auth_backfills_exact_linkage(self):
        item_id = ObjectId()
        upload_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "private_owner",
                        "release_state": "released",
                        # Some pre-Phase22 rows persisted raw ObjectIds in the
                        # reverse pointer fields instead of canonical strings.
                        "current_upload_id": upload_id,
                        "upload_id": upload_id,
                        "asset_version": 1,
                    }
                ],
                "uploaded_files": [
                    {
                        "_id": upload_id,
                        "project_id": "project-a",
                        "uploaded_by_user_id": "owner-1",
                        "original_filename": "legacy.jpg",
                        "content_type": "image/jpeg",
                        "scan_status": "clean",
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            authorized = vault_service.authorize_vault_upload_access(
                str(upload_id),
                "owner-1",
                authorized_project_id="project-a",
                require_current=True,
            )
        stored_item = db["vault_items"].find_one({"_id": item_id})
        stored_upload = db["uploaded_files"].find_one({"_id": upload_id})
        self.assertEqual(len(authorized["asset_versions"]), 1)
        self.assertTrue(authorized["asset_versions"][0]["migration_backfilled"])
        self.assertEqual(stored_upload["vault_item_id"], str(item_id))
        self.assertTrue(stored_upload["is_current_version"])
        self.assertEqual(len(stored_item["asset_versions"]), 1)
        self.assertTrue(
            any(
                event["action"] == "backfill_upload_linkage"
                for event in db["vault_audit_events"].documents
            )
        )

    def test_reverse_legacy_upload_auth_rejects_ambiguous_or_noncurrent_linkage(self):
        ambiguous_upload_id = ObjectId()
        stale_upload_id = ObjectId()
        current_upload_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": ObjectId(),
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "current_upload_id": str(ambiguous_upload_id),
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "upload_id": str(ambiguous_upload_id),
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "current_upload_id": str(current_upload_id),
                        "upload_id": str(stale_upload_id),
                    },
                ],
                "uploaded_files": [
                    {
                        "_id": ambiguous_upload_id,
                        "project_id": "project-a",
                        "scan_status": "clean",
                    },
                    {
                        "_id": stale_upload_id,
                        "project_id": "project-a",
                        "scan_status": "clean",
                    },
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(PermissionError, "ambiguous"):
                vault_service.authorize_vault_upload_access(
                    str(ambiguous_upload_id),
                    "owner-1",
                    authorized_project_id="project-a",
                )
            with self.assertRaisesRegex(ValueError, "not linked"):
                vault_service.authorize_vault_upload_access(
                    str(stale_upload_id),
                    "owner-1",
                    authorized_project_id="project-a",
                )

    def test_tombstone_current_vault_version_promotes_clean_prior_and_is_retry_safe(self):
        item_id = ObjectId()
        first_upload_id = ObjectId()
        second_upload_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "private_owner",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                        "upload_id": str(second_upload_id),
                        "current_upload_id": str(second_upload_id),
                        "asset_version": 2,
                        "asset_versions": [
                            {"version": 1, "upload_id": str(first_upload_id)},
                            {
                                "version": 2,
                                "upload_id": str(second_upload_id),
                                "replaces_upload_id": str(first_upload_id),
                            },
                        ],
                    }
                ],
                "uploaded_files": [
                    {
                        "_id": first_upload_id,
                        "vault_item_id": str(item_id),
                        "project_id": "project-a",
                        "scan_status": "clean",
                        "is_current_version": False,
                        "replacement_status": "superseded",
                        "replaced_by_upload_id": str(second_upload_id),
                    },
                    {
                        "_id": second_upload_id,
                        "vault_item_id": str(item_id),
                        "project_id": "project-a",
                        "scan_status": "clean",
                        "is_current_version": True,
                        "replacement_status": "current",
                    },
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            preview = vault_service.preview_vault_upload_version_deletion(
                str(item_id),
                str(second_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            result = vault_service.tombstone_vault_upload_version(
                str(item_id),
                str(second_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
            db["uploaded_files"].delete_one({"_id": second_upload_id})
            retry = vault_service.tombstone_vault_upload_version(
                str(item_id),
                str(second_upload_id),
                "owner-1",
                authorized_project_id="project-a",
            )
        stored_item = db["vault_items"].find_one({"_id": item_id})
        promoted_upload = db["uploaded_files"].find_one({"_id": first_upload_id})
        deleted_entry = next(
            entry
            for entry in stored_item["asset_versions"]
            if entry["upload_id"] == str(second_upload_id)
        )
        self.assertFalse(preview["safe_to_delete_upload"])
        self.assertEqual(result["promoted_upload_id"], str(first_upload_id))
        self.assertTrue(result["safe_to_delete_upload"])
        self.assertEqual(stored_item["current_upload_id"], str(first_upload_id))
        self.assertEqual(stored_item["asset_version"], 1)
        self.assertEqual(deleted_entry["deletion_status"], "deleted")
        self.assertTrue(deleted_entry["was_current_at_deletion"])
        self.assertTrue(promoted_upload["is_current_version"])
        self.assertIsNone(promoted_upload["replaced_by_upload_id"])
        self.assertTrue(retry["already_tombstoned"])
        self.assertTrue(retry["safe_to_delete_upload"])

    def test_tombstone_only_version_closes_item_and_respects_co_owner_privacy_boundary(self):
        item_id = ObjectId()
        upload_id = ObjectId()
        db = FakeDatabase(
            {
                "vault_items": [
                    {
                        "_id": item_id,
                        "project_id": "project-a",
                        "owner_user_id": "owner-1",
                        "privacy": "owner_and_co_owner",
                        "release_state": "released",
                        "status": "active",
                        "access_enabled": True,
                        "upload_id": str(upload_id),
                        "current_upload_id": str(upload_id),
                        "asset_version": 1,
                        "asset_versions": [{"version": 1, "upload_id": str(upload_id)}],
                    }
                ],
                "uploaded_files": [
                    {
                        "_id": upload_id,
                        "vault_item_id": str(item_id),
                        "project_id": "project-a",
                        "scan_status": "clean",
                    }
                ],
            }
        )
        with patch.object(vault_service, "get_database", return_value=db):
            with self.assertRaisesRegex(PermissionError, "authorized Vault manager"):
                vault_service.preview_vault_upload_version_deletion(
                    str(item_id),
                    str(upload_id),
                    "manager-1",
                    authorized_project_id="project-a",
                    workspace_member_role="family_manager",
                )
            result = vault_service.tombstone_vault_upload_version(
                str(item_id),
                str(upload_id),
                "co-owner-1",
                authorized_project_id="project-a",
                workspace_member_role="co_owner",
            )
        stored_item = db["vault_items"].find_one({"_id": item_id})
        self.assertTrue(result["item_closed"])
        self.assertIsNone(stored_item["current_upload_id"])
        self.assertIsNone(stored_item["upload_id"])
        self.assertEqual(stored_item["status"], "closed")
        self.assertFalse(stored_item["access_enabled"])

    def test_vault_scope_entitlements_are_checked_per_operation(self):
        with patch.object(
            vault_routes,
            "require_workspace_capability",
            return_value={"project": {"_id": "project-a"}},
        ) as require_capability:
            vault_routes._resolve_vault_context(
                {"id": "owner-1"},
                project_id="project-a",
                vault_scope="linked_family",
            )
        self.assertEqual(
            require_capability.call_args.kwargs["capabilities"],
            ("can_use_linked_household_vault",),
        )
        with patch.object(
            vault_routes,
            "require_workspace_capability",
            return_value={"project": {"_id": "project-a"}},
        ) as require_capability:
            vault_routes._resolve_vault_context(
                {"id": "owner-1"},
                project_id="project-a",
                vault_scope="organization",
            )
        self.assertEqual(
            require_capability.call_args.kwargs["capabilities"],
            ("can_use_organization_records_vault",),
        )

        with patch.object(vault_routes, "_require_additional_capability") as require_extra:
            vault_routes._require_release_entitlements(
                {"id": "owner-1"},
                project_id="project-a",
                trigger_type="after_trustee_approval",
            )
        self.assertEqual(require_extra.call_count, 2)
        self.assertEqual(
            {call.kwargs["capability"] for call in require_extra.call_args_list},
            {"can_use_scheduled_reveal", "can_use_future_message_vault"},
        )


if __name__ == "__main__":
    unittest.main()
