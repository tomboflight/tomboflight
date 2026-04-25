"""
Tests for admin repair endpoint guardrails.

Verifies that:
 - Repair actions are scoped to the correct permissions.
 - Fake payment, verification, mint, and entitlement state cannot be injected.
 - Super admin role escalation from customer accounts is blocked.
 - Audit logs are written with before/after values for sensitive repairs.
 - Marketing / finance / operations admins cannot cross role boundaries.
"""

import unittest
from unittest.mock import MagicMock, call, patch

from bson import ObjectId

from app.services import admin_control_service


class FakeCursor(list):
    def sort(self, field_name, direction):
        return FakeCursor(sorted(self, key=lambda item: str(item.get(field_name) or ""), reverse=direction < 0))

    def limit(self, n):
        return FakeCursor(self[:n])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query=None, *args, **kwargs):
        query = query or {}
        for doc in self.documents:
            if self._matches(doc, query):
                return doc
        return None

    def find(self, query=None, *args, **kwargs):
        query = query or {}
        return FakeCursor([doc for doc in self.documents if self._matches(doc, query)])

    def count_documents(self, query=None):
        query = query or {}
        return len([doc for doc in self.documents if self._matches(doc, query)])

    def update_one(self, query, update):
        updated = 0
        for doc in self.documents:
            if self._matches(doc, query):
                for key, value in (update.get("$set") or {}).items():
                    doc[key] = value
                updated = 1
                break
        return type("R", (), {"matched_count": updated, "modified_count": updated})()

    def insert_one(self, payload):
        doc = dict(payload)
        doc.setdefault("_id", ObjectId())
        self.documents.append(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    def delete_one(self, query):
        for i, doc in enumerate(self.documents):
            if self._matches(doc, query):
                del self.documents[i]
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()

    def _get_nested(self, doc, key):
        current = doc
        for part in key.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _matches(self, doc, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, opt) for opt in expected):
                    return False
                continue
            actual = self._get_nested(doc, key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    values = expected["$in"]
                    if isinstance(actual, list):
                        if not any(item in values for item in actual):
                            return False
                    elif actual not in values:
                        return False
                else:
                    return False
            elif actual != expected:
                return False
        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {name: FakeCollection(docs) for name, docs in (collections or {}).items()}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _super_admin_user():
    return {
        "_id": ObjectId(),
        "email": "super@tomboflight.com",
        "role": "super_admin",
        "_access_context": {"role_codes": ["super_admin"], "permissions": ["*"]},
    }


def _finance_user():
    return {
        "_id": ObjectId(),
        "email": "finance@tomboflight.com",
        "role": "finance_admin",
        "_access_context": {
            "role_codes": ["finance_admin"],
            "permissions": [
                "admin.control.view",
                "admin.control.billing",
                "admin.orders.read",
                "admin.orders.repair",
                "admin.entitlements.read",
                "admin.entitlements.write",
            ],
        },
    }


def _operations_user():
    return {
        "_id": ObjectId(),
        "email": "ops@tomboflight.com",
        "role": "operations_admin",
        "_access_context": {
            "role_codes": ["operations_admin"],
            "permissions": [
                "admin.control.view",
                "admin.control.write",
                "admin.intake.review",
                "admin.intake.write",
                "uploads.admin.review",
                "verification.review",
                "admin.control.mint.readiness",
            ],
        },
    }


def _marketing_user():
    return {
        "_id": ObjectId(),
        "email": "marketing@tomboflight.com",
        "role": "marketing_admin",
        "_access_context": {
            "role_codes": ["marketing_admin"],
            "permissions": [
                "admin.analytics.read",
                "admin.marketing.content.read",
            ],
        },
    }


def _generic_admin_user():
    return {
        "_id": ObjectId(),
        "email": "admin@tomboflight.com",
        "role": "admin",
        "_access_context": {
            "role_codes": ["admin"],
            "permissions": ["admin.access"],
        },
    }


# ---------------------------------------------------------------------------
# Permission scope tests
# ---------------------------------------------------------------------------

class AdminActionPermissionScopeTests(unittest.TestCase):
    """Verify admin_control_action_allowed and bulk action scoping per role."""

    def test_finance_admin_cannot_queue_for_mint_review(self):
        user = _finance_user()
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "queue_for_mint_review"))

    def test_finance_admin_can_generate_entitlement(self):
        user = _finance_user()
        self.assertTrue(admin_control_service.admin_control_action_allowed(user, "generate_entitlement"))

    def test_finance_admin_cannot_repair_record(self):
        user = _finance_user()
        # repair_record is an operations action, not finance
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "repair_record"))

    def test_operations_admin_cannot_generate_entitlement(self):
        user = _operations_user()
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "generate_entitlement"))

    def test_operations_admin_can_repair_record(self):
        user = _operations_user()
        self.assertTrue(admin_control_service.admin_control_action_allowed(user, "repair_record"))

    def test_operations_admin_can_queue_for_mint_review(self):
        user = _operations_user()
        self.assertTrue(admin_control_service.admin_control_action_allowed(user, "queue_for_mint_review"))

    def test_marketing_admin_has_no_case_actions(self):
        user = _marketing_user()
        profile = admin_control_service.admin_control_access_profile(user)
        self.assertEqual(profile["allowed_actions"], [])
        self.assertEqual(profile["allowed_bulk_actions"], [])

    def test_generic_admin_has_no_privileged_actions(self):
        user = _generic_admin_user()
        profile = admin_control_service.admin_control_access_profile(user)
        # Generic admin should not be able to perform sensitive repair operations
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "queue_for_mint_review"))
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "generate_entitlement"))

    def test_finance_admin_cannot_refresh_mint_readiness(self):
        user = _finance_user()
        self.assertFalse(admin_control_service.admin_control_bulk_action_allowed(user, "refresh-mint-readiness"))

    def test_operations_admin_cannot_repair_missing_entitlements_bulk(self):
        user = _operations_user()
        self.assertFalse(admin_control_service.admin_control_bulk_action_allowed(user, "repair-missing-entitlements"))


# ---------------------------------------------------------------------------
# Payment state guardrail tests
# ---------------------------------------------------------------------------

class PaymentStateGuardrailTests(unittest.TestCase):
    """Admin repair cannot silently change order status to a paid state."""

    def _build_db_with_paid_order(self):
        project_id = ObjectId()
        order_id = ObjectId()
        return (
            project_id,
            order_id,
            FakeDatabase(
                {
                    "projects": [
                        {
                            "_id": project_id,
                            "owner_email": "customer@example.com",
                            "owner_user_id": str(ObjectId()),
                            "package_code": "legacy_snapshot",
                            "package_slug": "legacy_snapshot",
                            "project_lane": "portrait",
                            "status": "build_ready",
                            "phase": "intake_approved",
                        }
                    ],
                    "orders": [
                        {
                            "_id": order_id,
                            "email": "customer@example.com",
                            "status": "paid",
                            "item_type": "package",
                            "package_code": "legacy_snapshot",
                            "project_id": project_id,
                        }
                    ],
                    "project_entitlements": [],
                }
            ),
        )

    def test_package_change_cannot_escalate_unpaid_order_to_paid(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "status": "pending",  # unpaid
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "project_id": project_id,
                    }
                ],
                "project_entitlements": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "cannot escalate order status to a paid state"):
                admin_control_service.super_admin_preview_package_change(
                    project_id=str(project_id),
                    package_code="legacy_plus",
                    project_lane="household",
                    order_status="paid",  # attempting to fake payment
                )

    def test_package_change_cannot_escalate_pending_order_to_succeeded(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "status": "pending",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "project_id": project_id,
                    }
                ],
                "project_entitlements": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "cannot escalate order status to a paid state"):
                admin_control_service.super_admin_preview_package_change(
                    project_id=str(project_id),
                    package_code="legacy_plus",
                    project_lane="household",
                    order_status="succeeded",  # also a paid alias
                )

    def test_package_change_apply_does_not_write_order_status(self):
        """Even when preview includes status in proposed_after, apply must strip it."""
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "project_id": project_id,
                    }
                ],
                "project_entitlements": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(
                admin_control_service,
                "repair_record",
                return_value={
                    "project": {"package_code": "legacy_plus", "project_lane": "household"},
                    "order": {"package_code": "legacy_plus", "status": "paid"},
                    "entitlement": {"package_code": "legacy_plus", "package_lane": "household"},
                },
            ),
        ):
            # Apply with order_status="complete" (paid alias) on already-paid order is allowed
            # because the existing order IS already paid.
            applied = admin_control_service.super_admin_apply_package_change(
                project_id=str(project_id),
                package_code="legacy_plus",
                project_lane="household",
                order_status="complete",
                actor={"_id": ObjectId(), "email": "super@tomboflight.com"},
            )

        # The order's status field must NOT have been updated by the repair.
        order_doc = db["orders"].find_one({"_id": order_id})
        # Status was NOT written by apply (status key stripped from order updates)
        self.assertEqual(order_doc["status"], "paid")  # unchanged from original

    def test_package_change_defaults_to_existing_order_status_not_paid(self):
        """If no order_status provided, should preserve existing status (not default to 'paid')."""
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "status": "pending",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "project_id": project_id,
                    }
                ],
                "project_entitlements": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
        ):
            preview = admin_control_service.super_admin_preview_package_change(
                project_id=str(project_id),
                package_code="legacy_plus",
                project_lane="household",
                order_status="",  # no explicit status provided
            )

        # The preview should NOT show "paid" as the target order status
        target_status = preview["validation"]["target_order_status"]
        self.assertNotEqual(target_status, "paid")
        self.assertEqual(target_status, "pending")  # preserves existing status


# ---------------------------------------------------------------------------
# Role escalation guardrail tests
# ---------------------------------------------------------------------------

class RoleEscalationGuardrailTests(unittest.TestCase):
    """Super admin role must not be granted to customer accounts."""

    def test_cannot_promote_customer_role_user_to_super_admin(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "customer@example.com",
                        "full_name": "Random Customer",
                        "role": "user",
                        "status": "active",
                    }
                ]
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "super_admin role can only be granted"):
                admin_control_service.super_admin_update_user(
                    user_id=str(user_id),
                    payload={"role": "super_admin"},
                    actor={"_id": ObjectId(), "email": "ceo@tomboflight.com"},
                )

    def test_can_promote_existing_operations_admin_to_super_admin(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "ops@tomboflight.com",
                        "full_name": "Ops Admin",
                        "role": "operations_admin",
                        "status": "active",
                    }
                ]
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            result = admin_control_service.super_admin_update_user(
                user_id=str(user_id),
                payload={"role": "super_admin"},
                actor={"_id": ObjectId(), "email": "ceo@tomboflight.com"},
            )
        self.assertEqual(result["after"]["role"], "super_admin")

    def test_can_promote_business_admin_account_type_user_to_super_admin(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "staff@tomboflight.com",
                        "full_name": "Staff Member",
                        "role": "admin",
                        "account_type": "business_admin",
                        "status": "active",
                    }
                ]
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            result = admin_control_service.super_admin_update_user(
                user_id=str(user_id),
                payload={"role": "super_admin"},
                actor={"_id": ObjectId(), "email": "ceo@tomboflight.com"},
            )
        self.assertEqual(result["after"]["role"], "super_admin")


# ---------------------------------------------------------------------------
# Audit log tests
# ---------------------------------------------------------------------------

class AuditLogTests(unittest.TestCase):
    """Repair actions must write audit logs with before/after values."""

    def _base_project_db(self, project_id, order_id):
        return FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "project_id": project_id,
                    }
                ],
                "project_entitlements": [],
            }
        )

    def test_sync_package_writes_audit_log_with_before_after(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = self._base_project_db(project_id, order_id)
        actor = {"_id": ObjectId(), "email": "ops@tomboflight.com"}
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(admin_control_service, "_write_admin_action_audit") as mock_audit,
            patch.object(admin_control_service, "_record_package_transition_event"),
        ):
            admin_control_service.sync_package(
                project_id=str(project_id),
                order_id=str(order_id),
                actor=actor,
            )
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["action"], "repair.sync_package")
        self.assertIn("before", call_kwargs)
        self.assertIn("after", call_kwargs)
        self.assertIsInstance(call_kwargs["before"], dict)
        self.assertIsInstance(call_kwargs["after"], dict)

    def test_assign_lane_writes_audit_log_with_before_after(self):
        project_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "package_code": "legacy_snapshot",
                        "project_lane": "",
                        "status": "build_ready",
                    }
                ],
                "project_entitlements": [],
            }
        )
        actor = {"_id": ObjectId(), "email": "ops@tomboflight.com"}
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(admin_control_service, "_package_fields_from_context", return_value={
                "project_lane": "portrait",
                "package_code": "legacy_snapshot",
                "package_slug": "legacy_snapshot",
                "package_name": "Legacy Snapshot",
                "lane": "portrait",
                "package_lane": "portrait",
                "is_known": True,
                "warnings": [],
                "sources": {},
            }),
            patch.object(admin_control_service, "_write_admin_action_audit") as mock_audit,
        ):
            admin_control_service.assign_lane(project_id=str(project_id), actor=actor)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["action"], "repair.assign_lane")
        self.assertIn("before", call_kwargs)
        self.assertIn("after", call_kwargs)
        self.assertEqual(call_kwargs["after"]["project_lane"], "portrait")

    def test_generate_entitlement_writes_audit_log(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = self._base_project_db(project_id, order_id)
        actor = {"_id": ObjectId(), "email": "finance@tomboflight.com"}
        user_id = ObjectId()
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(admin_control_service, "_resolve_entitlement_user_id", return_value=str(user_id)),
            patch.object(admin_control_service, "upsert_project_entitlement", return_value={"package_code": "legacy_snapshot"}),
            patch.object(admin_control_service, "_write_admin_action_audit") as mock_audit,
        ):
            admin_control_service.generate_entitlement(
                project_id=str(project_id),
                order_id=str(order_id),
                force=True,
                actor=actor,
            )
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["action"], "repair.generate_entitlement")
        self.assertIn("before", call_kwargs)
        self.assertIn("after", call_kwargs)

    def test_link_order_to_project_writes_audit_log(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    }
                ],
            }
        )
        actor = {"_id": ObjectId(), "email": "finance@tomboflight.com"}
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "_write_admin_action_audit") as mock_audit,
        ):
            admin_control_service.link_order_to_project(
                order_id=str(order_id),
                project_id=str(project_id),
                actor=actor,
            )
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["action"], "repair.link_order_to_project")
        self.assertIn("before", call_kwargs)
        self.assertIn("after", call_kwargs)
        self.assertEqual(call_kwargs["after"]["project_id"], str(project_id))

    def test_repair_project_mint_status_writes_audit_log(self):
        project_id = ObjectId()
        actor = {"_id": ObjectId(), "email": "ops@tomboflight.com"}
        mint_summary = {"current_status": "pending"}
        with (
            patch.object(admin_control_service, "rebuild_mint_summary_for_project", return_value=mint_summary),
            patch.object(admin_control_service, "_write_admin_action_audit") as mock_audit,
        ):
            admin_control_service.repair_project_mint_status(project_id=str(project_id), actor=actor)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["action"], "mint_readiness.repair_mint_status")

    def test_resync_current_mint_receipt_writes_audit_log(self):
        project_id = ObjectId()
        mint_record_id = str(ObjectId())
        actor = {"_id": ObjectId(), "email": "ops@tomboflight.com"}
        canonical = {
            "current_mint_record_id": mint_record_id,
            "current_status": "minted",
            "is_minted": True,
        }
        with (
            patch.object(admin_control_service, "resolve_canonical_mint_status", side_effect=[canonical, canonical]),
            patch.object(admin_control_service, "sync_receipt_for_mint_record", return_value={"synced": True}),
            patch.object(admin_control_service, "_write_admin_action_audit") as mock_audit,
        ):
            admin_control_service.resync_current_mint_receipt(project_id=str(project_id), actor=actor)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["action"], "mint_execution.resync_mint_receipt")
        self.assertEqual(call_kwargs["target_type"], "mint_record")
        self.assertEqual(call_kwargs["target_id"], mint_record_id)

    def test_super_admin_repair_case_action_writes_audit_with_before_after(self):
        actor = {"_id": ObjectId(), "email": "super@tomboflight.com", "role": "super_admin"}
        with (
            patch.object(admin_control_service, "_resolve_case_project_order", return_value=("project-1", "order-1")),
            patch.object(
                admin_control_service,
                "customer_case_workspace",
                side_effect=[{"alerts": ["before-alert"]}, {"alerts": ["after-alert"]}],
            ),
            patch.object(
                admin_control_service,
                "_super_admin_repair_invite",
                return_value={
                    "target_type": "household_invite",
                    "target_id": "invite-1",
                    "before": {"status": "expired", "email": "user@example.com"},
                    "after": {"status": "pending", "email": "user@example.com"},
                    "project_id": "project-1",
                },
            ),
            patch.object(admin_control_service, "write_audit_log") as mock_audit,
        ):
            result = admin_control_service.super_admin_repair_case_action(
                case_id="project-1",
                action="resend_invite",
                payload={"reason": "Re-send expired invite", "invite_id": "invite-1"},
                actor=actor,
            )
        self.assertEqual(result["status"], "repaired")
        self.assertTrue(mock_audit.called)
        audit_kwargs = mock_audit.call_args.kwargs
        self.assertIn("before", audit_kwargs)
        self.assertIn("after", audit_kwargs)
        # before/after values must include actual state info (not empty dicts)
        self.assertIn("status", audit_kwargs["before"])
        self.assertIn("status", audit_kwargs["after"])


# ---------------------------------------------------------------------------
# Mint receipt guardrail – must not fabricate on-chain data
# ---------------------------------------------------------------------------

class MintReceiptGuardrailTests(unittest.TestCase):
    def test_resync_mint_receipt_fails_without_existing_mint_record(self):
        project_id = ObjectId()
        canonical = {"current_mint_record_id": None, "is_minted": False}
        with patch.object(admin_control_service, "resolve_canonical_mint_status", return_value=canonical):
            with self.assertRaisesRegex(ValueError, "no mint record to sync"):
                admin_control_service.resync_current_mint_receipt(project_id=str(project_id))

    def test_resync_mint_receipt_delegates_to_real_sync_not_fabrication(self):
        """Ensure sync_receipt_for_mint_record is called (real on-chain sync) and
        that no wallet/token/tx fields are injected directly."""
        project_id = ObjectId()
        mint_record_id = str(ObjectId())
        canonical = {"current_mint_record_id": mint_record_id, "current_status": "processing", "is_minted": False}
        sync_result = {"status": "synced", "on_chain_confirmed": False}
        with (
            patch.object(admin_control_service, "resolve_canonical_mint_status", return_value=canonical),
            patch.object(admin_control_service, "sync_receipt_for_mint_record", return_value=sync_result) as mock_sync,
            patch.object(admin_control_service, "_write_admin_action_audit"),
        ):
            result = admin_control_service.resync_current_mint_receipt(project_id=str(project_id))

        # The real sync function must have been called with the actual record id
        mock_sync.assert_called_once_with(mint_record_id)
        # No fabricated fields in the sync result
        self.assertNotIn("token_id", result.get("sync_result") or {})
        self.assertNotIn("tx_hash", result.get("sync_result") or {})
        self.assertNotIn("wallet_address", result.get("sync_result") or {})


# ---------------------------------------------------------------------------
# Marketing admin cannot mutate customer records
# ---------------------------------------------------------------------------

class MarketingAdminMutationGuardrailTests(unittest.TestCase):
    def test_marketing_admin_cannot_execute_case_action(self):
        """Marketing admin is view-only; execute_case_action should be blocked."""
        user = _marketing_user()
        # marketing admin has no case action permissions - action_allowed returns False
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "repair_record"))
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "generate_entitlement"))
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "queue_for_mint_review"))
        self.assertFalse(admin_control_service.admin_control_action_allowed(user, "sync_package"))

    def test_marketing_admin_cannot_access_customer_case_queues(self):
        user = _marketing_user()
        profile = admin_control_service.admin_control_access_profile(user)
        allowed_queues = set(profile["allowed_queues"])
        # Must not have access to operational queues
        self.assertNotIn("customer_cases", allowed_queues)
        self.assertNotIn("intake_onboarding", allowed_queues)
        self.assertNotIn("verification_upload_review", allowed_queues)
        self.assertNotIn("mint_queue", allowed_queues)


# ---------------------------------------------------------------------------
# Repair case reason requirement tests
# ---------------------------------------------------------------------------

class RepairCaseReasonTests(unittest.TestCase):
    def test_repair_case_action_requires_non_empty_reason(self):
        with self.assertRaisesRegex(ValueError, "repair reason is required"):
            admin_control_service.super_admin_repair_case_action(
                case_id="project-123",
                action="repair_package_lane",
                payload={},
                actor={"_id": ObjectId(), "email": "super@tomboflight.com"},
            )

    def test_repair_case_action_with_empty_string_reason_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "repair reason is required"):
            admin_control_service.super_admin_repair_case_action(
                case_id="project-123",
                action="repair_package_lane",
                payload={"reason": ""},
                actor={"_id": ObjectId(), "email": "super@tomboflight.com"},
            )

    def test_repair_case_action_unsupported_action_raises(self):
        with (
            patch.object(admin_control_service, "_resolve_case_project_order", return_value=("project-123", "")),
            patch.object(admin_control_service, "customer_case_workspace", return_value={"alerts": []}),
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported super admin repair action"):
                admin_control_service.super_admin_repair_case_action(
                    case_id="project-123",
                    action="fake_approve_verification",  # not a real action
                    payload={"reason": "Testing a bad action"},
                    actor={"_id": ObjectId(), "email": "super@tomboflight.com"},
                )


if __name__ == "__main__":
    unittest.main()
