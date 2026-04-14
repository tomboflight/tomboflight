import unittest
from unittest.mock import patch

from bson import ObjectId

from app.dependencies import auth as auth_dependencies
from app.services import admin_control_service


class FakeCursor(list):
    def sort(self, field_name, direction):
        return FakeCursor(
            sorted(
                self,
                key=lambda item: str(item.get(field_name) or ""),
                reverse=direction < 0,
            )
        )

    def limit(self, limit):
        return FakeCursor(self[:limit])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query=None, projection=None, *args, **kwargs):
        del projection, args, kwargs
        query = query or {}
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    def find(self, query=None, projection=None, *args, **kwargs):
        del projection, args, kwargs
        query = query or {}
        return FakeCursor(
            [document for document in self.documents if self._matches(document, query)]
        )

    def count_documents(self, query=None):
        query = query or {}
        return len([document for document in self.documents if self._matches(document, query)])

    def _get_nested(self, document, key):
        current = document
        for part in key.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _matches(self, document, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(document, option) for option in expected):
                    return False
                continue

            actual = self._get_nested(document, key)
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
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class AdminPermissionContextTests(unittest.TestCase):
    def test_finance_role_no_longer_gets_wildcard_permissions(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "user_role_assignments": [],
                "role_permissions": [],
                "projects": [],
                "workflow_events": [],
            }
        )

        with (
            patch.object(
                auth_dependencies,
                "_load_user_by_id",
                return_value={
                    "_id": user_id,
                    "email": "finance@example.com",
                    "role": "finance",
                },
            ),
            patch.object(auth_dependencies, "_db", return_value=db),
            patch.object(auth_dependencies, "list_user_project_entitlements", return_value=[]),
        ):
            context = auth_dependencies.resolve_access_context(str(user_id))

        permissions = set(context["permissions"])
        self.assertNotIn("*", permissions)
        self.assertIn("admin.control.billing", permissions)
        self.assertIn("admin.orders.read", permissions)
        self.assertNotIn("admin.control.mint", permissions)
        self.assertNotIn("uploads.admin.review", permissions)


class AdminControlAccessProfileTests(unittest.TestCase):
    def test_finance_profile_can_handle_billing_but_not_mint_or_upload_review(self):
        current_user = {
            "role": "finance",
            "_access_context": {
                "role_codes": ["finance"],
                "permissions": [
                    "admin.access",
                    "admin.audit.read",
                    "admin.control.view",
                    "admin.control.billing",
                    "admin.entitlements.read",
                    "admin.entitlements.write",
                    "admin.orders.read",
                    "admin.orders.repair",
                ],
            },
        }

        profile = admin_control_service.admin_control_access_profile(current_user)

        self.assertIn("orders", profile["allowed_queues"])
        self.assertIn("entitlements", profile["allowed_queues"])
        self.assertNotIn("mint_queue", profile["allowed_queues"])
        self.assertNotIn("upload_review", profile["allowed_queues"])
        self.assertTrue(admin_control_service.admin_control_action_allowed(current_user, "generate_entitlement"))
        self.assertFalse(admin_control_service.admin_control_action_allowed(current_user, "queue_for_mint_review"))
        self.assertTrue(admin_control_service.admin_control_bulk_action_allowed(current_user, "repair-missing-entitlements"))
        self.assertFalse(admin_control_service.admin_control_bulk_action_allowed(current_user, "refresh-mint-readiness"))

    def test_marketing_profile_is_read_only_with_user_visibility(self):
        current_user = {
            "role": "marketing",
            "_access_context": {
                "role_codes": ["marketing"],
                "permissions": [
                    "admin.access",
                    "admin.audit.read",
                    "admin.control.view",
                    "admin.orders.read",
                    "admin.users.read",
                ],
            },
        }

        profile = admin_control_service.admin_control_access_profile(current_user)

        self.assertIn("users", profile["allowed_queues"])
        self.assertIn("customer_cases", profile["allowed_queues"])
        self.assertIn("run_readiness_check", profile["allowed_actions"])
        self.assertNotIn("sync_package", profile["allowed_actions"])
        self.assertNotIn("generate_entitlement", profile["allowed_actions"])
        self.assertEqual(profile["allowed_bulk_actions"], [])

    def test_wildcard_profile_gets_all_console_controls(self):
        current_user = {
            "role": "root_admin",
            "_access_context": {
                "role_codes": ["root_admin"],
                "permissions": ["*"],
            },
        }

        profile = admin_control_service.admin_control_access_profile(current_user)

        self.assertIn("users", profile["allowed_queues"])
        self.assertIn("mint_queue", profile["allowed_queues"])
        self.assertIn("uploads_verification", profile["allowed_tabs"])
        self.assertIn("queue_for_mint_review", profile["allowed_actions"])
        self.assertIn("repair-all-safe-records", profile["allowed_bulk_actions"])


class AdminUserQueueTests(unittest.TestCase):
    def test_users_queue_lists_customer_and_admin_accounts(self):
        customer_id = ObjectId()
        admin_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": customer_id,
                        "email": "customer@example.com",
                        "full_name": "Customer Person",
                        "role": "user",
                        "status": "active",
                    },
                    {
                        "_id": admin_id,
                        "email": "ops@example.com",
                        "full_name": "Ops Admin",
                        "role": "operations",
                        "status": "active",
                    },
                ],
                "projects": [],
                "orders": [],
                "project_entitlements": [],
                "uploaded_files": [],
                "audit_logs": [],
            }
        )

        with patch.object(admin_control_service, "get_database", return_value=db):
            payload = admin_control_service.list_customer_cases(queue="users", limit=10)

        case_ids = {item["case_id"] for item in payload["items"]}
        self.assertEqual(len(payload["items"]), 2)
        self.assertIn(f"user:{customer_id}", case_ids)
        self.assertIn(f"user:{admin_id}", case_ids)
        self.assertIn("customer", {item["lane"] for item in payload["items"]})
        self.assertIn("admin", {item["lane"] for item in payload["items"]})

    def test_user_case_workspace_loads_legacy_account_without_project(self):
        customer_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": customer_id,
                        "email": "customer@example.com",
                        "full_name": "Customer Person",
                        "role": "user",
                        "status": "active",
                    }
                ],
                "projects": [],
                "orders": [],
                "project_entitlements": [],
                "uploaded_files": [],
                "audit_logs": [],
            }
        )

        with patch.object(admin_control_service, "get_database", return_value=db):
            workspace = admin_control_service.customer_case_workspace(f"user:{customer_id}")

        self.assertEqual(workspace["case_id"], f"user:{customer_id}")
        self.assertEqual(workspace["tabs"]["identity"]["email"], "customer@example.com")
        self.assertEqual(workspace["tabs"]["identity"]["admin_user_relationship"], "customer_record")
        self.assertEqual(workspace["tabs"]["project"]["related_projects"], [])
        self.assertEqual(workspace["tabs"]["entitlements"]["entitlement_status"], "missing")

    def test_project_case_workspace_isolates_related_records_to_selected_project(self):
        larry_user_id = ObjectId()
        larry_project_id = ObjectId()
        larry_other_project_id = ObjectId()
        marquis_project_id = ObjectId()
        selected_order_id = ObjectId()
        larry_other_order_id = ObjectId()
        marquis_order_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": larry_user_id,
                        "email": "larry@example.com",
                        "full_name": "Larry Robinson",
                        "role": "user",
                        "status": "active",
                    }
                ],
                "projects": [
                    {
                        "_id": larry_project_id,
                        "owner_user_id": str(larry_user_id),
                        "owner_email": "larry@example.com",
                        "name": "Larry Selected Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    },
                    {
                        "_id": larry_other_project_id,
                        "owner_user_id": str(larry_user_id),
                        "owner_email": "larry@example.com",
                        "name": "Larry Other Project",
                        "package_code": "legacy_plus",
                        "project_lane": "household",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    },
                    {
                        "_id": marquis_project_id,
                        "owner_email": "marquis@example.com",
                        "name": "Marquis Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    },
                ],
                "orders": [
                    {
                        "_id": selected_order_id,
                        "email": "larry@example.com",
                        "project_id": larry_project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    },
                    {
                        "_id": larry_other_order_id,
                        "email": "larry@example.com",
                        "project_id": larry_other_project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_plus",
                    },
                    {
                        "_id": marquis_order_id,
                        "email": "marquis@example.com",
                        "project_id": marquis_project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    },
                ],
                "project_entitlements": [],
                "uploaded_files": [
                    {
                        "_id": ObjectId(),
                        "project_id": larry_project_id,
                        "uploaded_by": "larry@example.com",
                        "filename": "larry-selected.jpg",
                        "category": "member_photo",
                        "status": "received",
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": larry_other_project_id,
                        "uploaded_by": "larry@example.com",
                        "filename": "larry-other.jpg",
                        "category": "member_photo",
                        "status": "received",
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": marquis_project_id,
                        "uploaded_by": "marquis@example.com",
                        "filename": "marquis.jpg",
                        "category": "member_photo",
                        "status": "received",
                    },
                ],
                "audit_logs": [
                    {
                        "_id": ObjectId(),
                        "target_id": larry_project_id,
                        "actor_email": "larry@example.com",
                        "action": "selected_project_event",
                    },
                    {
                        "_id": ObjectId(),
                        "target_id": str(larry_other_project_id),
                        "actor_email": "larry@example.com",
                        "action": "other_larry_project_event",
                    },
                    {
                        "_id": ObjectId(),
                        "target_id": str(marquis_project_id),
                        "actor_email": "marquis@example.com",
                        "action": "marquis_project_event",
                    },
                ],
                "families": [],
                "households": [],
            }
        )

        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(
                admin_control_service,
                "run_readiness_check",
                return_value={
                    "mint_review_ready": False,
                    "mint_eligible": False,
                    "mint_already_completed": False,
                    "blocking_reasons": [],
                },
            ),
            patch.object(admin_control_service, "_mint_record_snapshot", return_value={}),
        ):
            workspace = admin_control_service.customer_case_workspace(str(larry_project_id))

        related_order_ids = {
            item["id"] for item in workspace["tabs"]["orders_billing"]["related_orders"]
        }
        upload_names = {
            item["filename"] for item in workspace["tabs"]["uploads_verification"]["items"]
        }
        audit_actions = {item["action"] for item in workspace["audit_timeline"]}

        self.assertEqual(workspace["tabs"]["project"]["project_id"], str(larry_project_id))
        self.assertEqual(related_order_ids, {str(selected_order_id)})
        self.assertEqual(upload_names, {"larry-selected.jpg"})
        self.assertEqual(audit_actions, {"selected_project_event"})

    def test_order_case_workspace_does_not_infer_unlinked_project_by_email(self):
        order_id = ObjectId()
        same_email_project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [],
                "projects": [
                    {
                        "_id": same_email_project_id,
                        "owner_email": "genesis@example.com",
                        "name": "Genesis Existing Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "genesis@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    }
                ],
                "project_entitlements": [],
                "uploaded_files": [
                    {
                        "_id": ObjectId(),
                        "project_id": same_email_project_id,
                        "uploaded_by": "genesis@example.com",
                        "filename": "genesis-project.jpg",
                    }
                ],
                "audit_logs": [],
                "families": [],
                "households": [],
            }
        )

        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(admin_control_service, "_mint_record_snapshot", return_value={}),
        ):
            workspace = admin_control_service.customer_case_workspace(f"order:{order_id}")

        related_order_ids = [
            item["id"] for item in workspace["tabs"]["orders_billing"]["related_orders"]
        ]
        self.assertIsNone(workspace["project"])
        self.assertIsNone(workspace["tabs"]["project"]["project_id"])
        self.assertEqual(related_order_ids, [str(order_id)])
        self.assertEqual(workspace["tabs"]["uploads_verification"]["items"], [])

    def test_order_case_actions_do_not_infer_unlinked_project_by_email(self):
        order_id = ObjectId()
        same_email_project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [],
                "projects": [
                    {
                        "_id": same_email_project_id,
                        "owner_email": "genesis@example.com",
                        "name": "Genesis Existing Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "genesis@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    }
                ],
                "project_entitlements": [],
                "uploaded_files": [],
                "audit_logs": [],
                "families": [],
                "households": [],
            }
        )

        with patch.object(admin_control_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "Action requires a linked project."):
                admin_control_service.execute_case_action(
                    case_id=f"order:{order_id}",
                    action="run_readiness_check",
                )
            result = admin_control_service.repair_selected_records(
                project_ids=[],
                order_ids=[str(order_id)],
            )

        self.assertEqual(result["repaired_count"], 0)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["failed"][0]["error"], "Linked project not found.")


if __name__ == "__main__":
    unittest.main()
