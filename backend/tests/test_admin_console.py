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

    def update_one(self, query, update):
        updated = 0
        for document in self.documents:
            if self._matches(document, query):
                for key, value in (update.get("$set") or {}).items():
                    document[key] = value
                updated = 1
                break
        return type("Result", (), {"matched_count": updated, "modified_count": updated})()

    def insert_one(self, payload):
        document = dict(payload)
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return type("Result", (), {"inserted_id": document["_id"]})()

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
        capabilities = set(context["capabilities"])
        self.assertIn("manage_billing", capabilities)
        self.assertNotIn("manage_roles", capabilities)
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

        self.assertEqual(
            profile["allowed_queues"],
            [
                "money_now",
                "subscriptions_maintenance",
                "package_revenue",
                "finance_integrity",
                "payroll",
                "reports_exports",
            ],
        )
        self.assertEqual(
            profile["allowed_tabs"],
            [
                "identity",
                "package_lane",
                "orders_billing",
                "project",
                "entitlements",
                "audit_timeline",
            ],
        )
        self.assertNotIn("orders", profile["allowed_queues"])
        self.assertNotIn("entitlements", profile["allowed_queues"])
        self.assertTrue(admin_control_service.admin_control_queue_allowed(current_user, "money_now"))
        self.assertFalse(admin_control_service.admin_control_queue_allowed(current_user, "mint_queue"))
        self.assertNotIn("mint_queue", profile["allowed_queues"])
        self.assertNotIn("upload_review", profile["allowed_queues"])
        self.assertTrue(admin_control_service.admin_control_action_allowed(current_user, "generate_entitlement"))
        self.assertFalse(admin_control_service.admin_control_action_allowed(current_user, "queue_for_mint_review"))
        self.assertTrue(admin_control_service.admin_control_bulk_action_allowed(current_user, "repair-missing-entitlements"))
        self.assertFalse(admin_control_service.admin_control_bulk_action_allowed(current_user, "refresh-mint-readiness"))

    def test_marketing_profile_is_marketing_queue_only(self):
        current_user = {
            "role": "marketing",
            "_access_context": {
                "role_codes": ["marketing_admin"],
                "permissions": [
                    "admin.analytics.read",
                    "admin.marketing.content.read",
                ],
            },
        }

        profile = admin_control_service.admin_control_access_profile(current_user)

        self.assertIn("traffic_awareness", profile["allowed_queues"])
        self.assertIn("marketing_reports", profile["allowed_queues"])
        self.assertEqual(profile["allowed_actions"], [])
        self.assertEqual(profile["allowed_bulk_actions"], [])

    def test_officer_role_takes_precedence_over_generic_admin_role(self):
        current_user = {
            "role": "admin",
            "access_tier": "finance_admin",
            "_access_context": {
                "role_codes": ["admin", "finance_admin"],
                "permissions": ["admin.control.view", "admin.control.billing"],
            },
        }
        profile = admin_control_service.admin_control_access_profile(current_user)
        self.assertEqual(profile["role_key"], "finance_admin")

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

    def test_cfo_profile_excludes_operations_and_mint_menus(self):
        current_user = {
            "role": "admin",
            "access_tier": "cfo_admin",
            "_access_context": {
                "role_codes": ["finance_admin"],
                "permissions": ["admin.control.view", "admin.control.billing", "admin.orders.read"],
            },
        }
        profile = admin_control_service.admin_control_access_profile(current_user)
        self.assertIn("money_now", profile["allowed_queues"])
        self.assertIn("reports_exports", profile["allowed_queues"])
        self.assertNotIn("customer_cases", profile["allowed_queues"])
        self.assertNotIn("mint_queue", profile["allowed_queues"])
        self.assertNotIn("upload_review", profile["allowed_queues"])

    def test_cmo_profile_exposes_marketing_only_scope(self):
        current_user = {
            "role": "admin",
            "access_tier": "cmo_admin",
            "_access_context": {
                "role_codes": ["marketing_admin"],
                "permissions": ["admin.marketing.content.read", "admin.analytics.read"],
            },
        }
        profile = admin_control_service.admin_control_access_profile(current_user)
        self.assertEqual(
            profile["allowed_queues"],
            [
                "traffic_awareness",
                "funnel_conversion",
                "package_demand",
                "campaign_performance",
                "content_performance",
                "marketing_reports",
            ],
        )
        self.assertEqual(profile["allowed_tabs"], ["marketing_dashboard"])
        self.assertEqual(profile["allowed_actions"], [])
        self.assertEqual(profile["allowed_bulk_actions"], [])

    def test_coo_profile_has_operations_without_billing_controls(self):
        current_user = {
            "role": "admin",
            "access_tier": "coo_admin",
            "_access_context": {
                "role_codes": ["operations_admin"],
                "permissions": [
                    "admin.access",
                    "admin.control.view",
                    "admin.control.write",
                    "admin.control.mint.readiness",
                    "admin.audit.read",
                    "admin.intake.review",
                    "admin.intake.write",
                    "uploads.admin.review",
                    "verification.review",
                ],
            },
        }
        profile = admin_control_service.admin_control_access_profile(current_user)
        self.assertEqual(
            profile["allowed_queues"],
            [
                "intake_onboarding",
                "verification_upload_review",
                "workspace_access_invites",
                "build_fulfillment",
                "exceptions_escalations",
                "ops_reports",
            ],
        )
        self.assertIn("project", profile["allowed_tabs"])
        self.assertIn("mint_readiness", profile["allowed_tabs"])
        self.assertIn("uploads_verification", profile["allowed_tabs"])
        self.assertNotIn("orders_billing", profile["allowed_tabs"])
        self.assertIn("repair_record", profile["allowed_actions"])
        self.assertIn("queue_for_mint_review", profile["allowed_actions"])
        self.assertNotIn("generate_entitlement", profile["allowed_actions"])
        self.assertNotIn("refresh-mint-readiness", profile["allowed_bulk_actions"])
        self.assertNotIn("money_now", profile["allowed_queues"])
        self.assertNotIn("marketing_reports", profile["allowed_queues"])

    def test_executive_tech_profile_includes_control_center_and_audit(self):
        current_user = {
            "role": "admin",
            "department_role": "executive_tech_admin",
            "_access_context": {
                "role_codes": ["executive_tech_admin"],
                "permissions": [
                    "admin.control.view",
                    "admin.control.write",
                    "admin.control.mint",
                    "admin.audit.read",
                ],
            },
        }
        profile = admin_control_service.admin_control_access_profile(current_user)
        self.assertIn("overview", profile["allowed_queues"])
        self.assertIn("mint_queue", profile["allowed_queues"])
        self.assertIn("audit", profile["allowed_queues"])


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

    def test_user_case_workspace_logs_sensitive_access_audit(self):
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
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "write_audit_log") as write_audit_log,
        ):
            admin_control_service.customer_case_workspace(
                f"user:{customer_id}",
                current_user={"_id": ObjectId(), "email": "k.goffigan@tomboflight.com"},
            )
        self.assertTrue(write_audit_log.called)
        self.assertEqual(
            write_audit_log.call_args.kwargs.get("action"),
            "admin_control_center.operations.sensitive_record_access",
        )

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


class SuperAdminControlsTests(unittest.TestCase):
    def test_super_admin_update_user_updates_profile_fields(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "before@example.com",
                        "full_name": "Before Name",
                        "role": "user",
                        "status": "active",
                    }
                ]
            }
        )

        with patch.object(admin_control_service, "get_database", return_value=db):
            result = admin_control_service.super_admin_update_user(
                user_id=str(user_id),
                payload={
                    "email": "after@example.com",
                    "full_name": "After Name",
                    "phone_number": "555-0101",
                    "mailing_address": "123 Main St",
                    "birthday": "1980-01-02",
                    "status": "suspended",
                    "role": "super_admin",
                },
                actor={"_id": ObjectId(), "email": "ceo@example.com"},
            )

        self.assertEqual(result["before"]["email"], "before@example.com")
        self.assertEqual(result["after"]["email"], "after@example.com")
        self.assertEqual(result["after"]["full_name"], "After Name")
        self.assertEqual(result["after"]["status"], "suspended")
        self.assertEqual(result["after"]["role"], "super_admin")

    def test_super_admin_package_change_preview_and_apply(self):
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
                        "package_name": "Legacy Snapshot",
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
                        "package_name": "Legacy Snapshot",
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
                    "order": {"package_code": "legacy_plus", "status": "complete"},
                    "entitlement": {"package_code": "legacy_plus", "package_lane": "household"},
                },
            ),
        ):
            preview = admin_control_service.super_admin_preview_package_change(
                project_id=str(project_id),
                package_code="legacy_plus",
                project_lane="household",
                order_status="complete",
            )
            applied = admin_control_service.super_admin_apply_package_change(
                project_id=str(project_id),
                package_code="legacy_plus",
                project_lane="household",
                order_status="complete",
                actor={"_id": ObjectId(), "email": "ceo@example.com"},
            )

        self.assertTrue(preview["changes"])
        self.assertEqual(preview["validation"]["target_lane"], "household")
        self.assertEqual(applied["after"]["project"]["package_code"], "legacy_plus")
        self.assertEqual(applied["after"]["order"]["status"], "complete")
        self.assertEqual(applied["after"]["entitlement"]["package_lane"], "household")

    def test_super_admin_repair_case_requires_reason(self):
        with self.assertRaisesRegex(ValueError, "repair reason is required"):
            admin_control_service.super_admin_repair_case_action(
                case_id="project-1",
                action="repair_package_lane",
                payload={},
                actor={"_id": ObjectId(), "email": "super@example.com", "role": "super_admin"},
            )

    def test_super_admin_repair_case_logs_audit_and_returns_alert_diff(self):
        actor = {"_id": ObjectId(), "email": "super@example.com", "role": "super_admin"}
        with (
            patch.object(admin_control_service, "_resolve_case_project_order", return_value=("project-1", "order-1")),
            patch.object(
                admin_control_service,
                "customer_case_workspace",
                side_effect=[{"alerts": ["before"]}, {"alerts": ["after"]}],
            ),
            patch.object(
                admin_control_service,
                "_super_admin_repair_invite",
                return_value={
                    "target_type": "household_invite",
                    "target_id": "invite-1",
                    "before": {"status": "expired"},
                    "after": {"status": "pending"},
                    "project_id": "project-1",
                },
            ),
            patch.object(admin_control_service, "write_audit_log") as write_audit_log,
        ):
            result = admin_control_service.super_admin_repair_case_action(
                case_id="project-1",
                action="resend_invite",
                payload={"reason": "Fix broken invite", "invite_id": "invite-1"},
                actor=actor,
            )
        self.assertEqual(result["status"], "repaired")
        self.assertEqual(result["before_workspace_alerts"], ["before"])
        self.assertEqual(result["after_workspace_alerts"], ["after"])
        self.assertTrue(write_audit_log.called)


class AdminConsoleOverviewTests(unittest.TestCase):
    def test_admin_overview_includes_postmark_runtime_configuration_flags(self):
        db = FakeDatabase(
            {
                "users": [],
                "projects": [],
                "orders": [],
                "project_entitlements": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service.settings, "postmark_server_token", "token-123"),
            patch.object(admin_control_service.settings, "postmark_from_email", "noreply@example.com"),
        ):
            payload = admin_control_service.admin_console_overview(limit=5)

        self.assertEqual(
            payload["system_health"]["postmark"],
            {
                "token_configured": True,
                "from_address_configured": True,
            },
        )

    def test_finance_sections_use_consistent_keys_and_explicit_non_live_states(self):
        db = FakeDatabase(
            {
                "users": [],
                "projects": [],
                "orders": [],
                "project_entitlements": [],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            payload = admin_control_service.admin_console_overview(limit=5)
        sections = payload["finance_sections"]
        self.assertIn("subscriptions_maintenance", sections)
        self.assertIn("reports_exports", sections)
        self.assertNotIn("subscriptions_and_maintenance", sections)
        self.assertNotIn("reports_and_exports", sections)
        self.assertFalse(sections["payroll"]["write_pipeline_live"])
        self.assertEqual(sections["payroll"]["snapshot_mode"], "read_only")
        self.assertFalse(sections["reports_exports"]["export_generation_live"])
        self.assertNotIn("monthly_finance_export", sections["reports_exports"])

    def test_overview_backfills_typed_finance_events(self):
        order_id = ObjectId()
        project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [],
                "projects": [],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "jenn.wood@tomboflight.com",
                        "project_id": project_id,
                        "status": "refunded",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 199,
                        "refund_amount": 50,
                        "credit_amount": 20,
                        "adjustment_amount": -10,
                    }
                ],
                "project_entitlements": [],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            admin_control_service.admin_console_overview(limit=5)
        event_types = {
            item.get("event_type")
            for item in db["finance_events"].documents
        }
        self.assertIn("refund_recorded", event_types)
        self.assertIn("credit_recorded", event_types)
        self.assertIn("billing_adjustment", event_types)


class CfoScopeAndFinanceHistoryTests(unittest.TestCase):
    def test_finance_admin_workspace_filters_non_finance_tabs_and_sections(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": ObjectId(),
                        "email": "jenn.wood@tomboflight.com",
                        "full_name": "Jennifer Wood",
                        "role": "finance_admin",
                        "status": "active",
                    }
                ],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "jenn.wood@tomboflight.com",
                        "owner_user_id": str(ObjectId()),
                        "name": "Jennifer Finance Project",
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
                        "email": "jenn.wood@tomboflight.com",
                        "project_id": project_id,
                        "status": "refunded",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 200,
                        "refund_amount": 50,
                    }
                ],
                "project_entitlements": [],
                "uploaded_files": [
                    {
                        "_id": ObjectId(),
                        "project_id": project_id,
                        "filename": "private-upload.jpg",
                        "category": "member_photo",
                        "status": "received",
                    }
                ],
                "audit_logs": [],
                "families": [],
                "households": [],
                "finance_events": [],
            }
        )
        finance_user = {
            "role": "finance",
            "_access_context": {
                "role_codes": ["finance_admin"],
                "permissions": [
                    "admin.control.view",
                    "admin.control.billing",
                    "admin.orders.read",
                    "admin.entitlements.read",
                    "admin.audit.read",
                ],
            },
        }
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(
                admin_control_service,
                "run_readiness_check",
                return_value={
                    "mint_review_ready": True,
                    "mint_eligible": False,
                    "mint_already_completed": False,
                    "blocking_reasons": ["mint_blocked"],
                    "package_synced": True,
                    "lane_assigned": True,
                    "order_linked": True,
                    "entitlement_exists": False,
                    "summary": "Finance case summary",
                },
            ),
            patch.object(admin_control_service, "_mint_record_snapshot", return_value={"current_status": "queued"}),
        ):
            workspace = admin_control_service.customer_case_workspace(
                str(project_id),
                current_user=finance_user,
            )
        self.assertNotIn("uploads", workspace)
        self.assertNotIn("uploads_verification", workspace["tabs"])
        self.assertNotIn("mint_readiness", workspace["tabs"])
        self.assertNotIn("uploads_summary", workspace["tabs"]["project"])
        self.assertIn("finance_history", workspace["tabs"]["orders_billing"])
        self.assertNotIn("mint_blocked", workspace["alerts"])
        self.assertNotIn("upload_review_pending", workspace["alerts"])

    def test_finance_admin_case_list_filters_actions_to_finance_scope(self):
        project_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "jenn.wood@tomboflight.com",
                        "owner_user_id": str(ObjectId()),
                        "name": "Finance Queue Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "email": "jenn.wood@tomboflight.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    }
                ],
                "project_entitlements": [],
                "uploaded_files": [],
                "audit_logs": [],
                "users": [],
                "families": [],
                "mint_records": [],
            }
        )
        finance_user = {
            "role": "finance",
            "_access_context": {
                "role_codes": ["finance_admin"],
                "permissions": [
                    "admin.control.view",
                    "admin.control.billing",
                    "admin.orders.read",
                    "admin.entitlements.read",
                    "admin.audit.read",
                ],
            },
        }
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
            patch.object(admin_control_service, "count_workspace_uploads", return_value=0),
        ):
            payload = admin_control_service.list_customer_cases(
                queue="money_now",
                limit=5,
                current_user=finance_user,
            )
        self.assertTrue(payload["items"])
        quick_actions = set(payload["items"][0]["quick_actions"])
        self.assertIn("generate_entitlement", quick_actions)
        self.assertNotIn("queue_for_mint_review", quick_actions)

    def test_overview_includes_marketing_sections_with_live_and_unavailable_flags(self):
        project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "marquis.l.floyd@tomboflight.com",
                        "owner_user_id": str(ObjectId()),
                        "name": "Marketing Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                    }
                ],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "email": "marquis.l.floyd@tomboflight.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "campaign": "spring_launch",
                        "source": "direct",
                        "promo_code": "SPRING25",
                    }
                ],
                "project_entitlements": [],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
                "analytics_events": [
                    {
                        "_id": ObjectId(),
                        "event_type": "page_view",
                        "page_path": "/",
                        "source": "direct",
                        "campaign": "spring_launch",
                    },
                    {
                        "_id": ObjectId(),
                        "event_type": "cta_click",
                        "cta_location": "hero",
                    },
                ],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(
                admin_control_service,
                "run_readiness_check",
                return_value={
                    "mint_review_ready": False,
                    "mint_eligible": False,
                    "mint_already_completed": False,
                    "package_synced": True,
                    "lane_assigned": True,
                    "order_linked": True,
                    "entitlement_exists": False,
                    "summary": "ok",
                    "blocking_reasons": [],
                },
            ),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
        ):
            payload = admin_control_service.admin_console_overview(limit=5)

        sections = payload.get("marketing_sections") or {}
        self.assertIn("traffic_awareness", sections)
        self.assertIn("funnel_conversion", sections)
        self.assertIn("package_demand", sections)
        self.assertIn("campaign_performance", sections)
        self.assertIn("content_performance", sections)
        self.assertIn("marketing_reports", sections)
        self.assertTrue(sections["traffic_awareness"]["visitors"]["live"])
        self.assertTrue(sections["funnel_conversion"]["purchases_completed"]["live"])
        self.assertFalse(sections["content_performance"]["page_dropoff_points"]["live"])

    def test_overview_includes_operations_sections_and_ops_report_export(self):
        db = FakeDatabase(
            {
                "users": [],
                "projects": [],
                "orders": [],
                "project_entitlements": [],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
                "verification_records": [],
                "uploaded_files": [],
                "household_invites": [],
                "project_members": [],
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            overview = admin_control_service.admin_console_overview(limit=5)
            exported = admin_control_service.export_operations_report()
        self.assertIn("operations_sections", overview)
        self.assertIn("intake_onboarding", overview["operations_sections"])
        self.assertIn("ops_reports", overview["operations_sections"])
        self.assertFalse(overview["operations_sections"]["ops_reports"]["sla_turnaround_indicators"]["live"])
        self.assertEqual(exported["report_type"], "operations_control_center")
        self.assertEqual(exported["format"], "json")
        self.assertIn("ops_reports", exported["sections"])

    def test_larry_inherits_cfo_scope_through_superadmin_and_executive_tech(self):
        larry_user = {
            "role": "admin",
            "department_role": "executive_tech_admin",
            "_access_context": {
                "role_codes": ["super_admin", "executive_tech_admin", "finance_admin"],
                "permissions": ["*"],
            },
        }
        profile = admin_control_service.admin_control_access_profile(larry_user)
        self.assertIn("money_now", profile["allowed_queues"])
        self.assertIn("payroll", profile["allowed_queues"])
        self.assertIn("reports_exports", profile["allowed_queues"])
        self.assertIn("mint_queue", profile["allowed_queues"])
        self.assertTrue(admin_control_service.admin_control_queue_allowed(larry_user, "reports_exports"))

    def test_larry_inherits_cmo_scope_through_superadmin_and_executive_tech(self):
        larry_user = {
            "role": "admin",
            "department_role": "executive_tech_admin",
            "_access_context": {
                "role_codes": ["super_admin", "executive_tech_admin", "marketing_admin"],
                "permissions": ["*"],
            },
        }
        profile = admin_control_service.admin_control_access_profile(larry_user)
        self.assertIn("traffic_awareness", profile["allowed_queues"])
        self.assertIn("marketing_reports", profile["allowed_queues"])
        self.assertIn("mint_queue", profile["allowed_queues"])
        self.assertTrue(admin_control_service.admin_control_queue_allowed(larry_user, "marketing_reports"))

    def test_larry_inherits_coo_scope_through_superadmin_and_executive_tech(self):
        larry_user = {
            "role": "admin",
            "department_role": "executive_tech_admin",
            "_access_context": {
                "role_codes": ["super_admin", "executive_tech_admin", "operations_admin"],
                "permissions": ["*"],
            },
        }
        profile = admin_control_service.admin_control_access_profile(larry_user)
        self.assertIn("intake_onboarding", profile["allowed_queues"])
        self.assertIn("verification_upload_review", profile["allowed_queues"])
        self.assertIn("workspace_access_invites", profile["allowed_queues"])
        self.assertIn("ops_reports", profile["allowed_queues"])
        self.assertIn("mint_queue", profile["allowed_queues"])
        self.assertTrue(admin_control_service.admin_control_queue_allowed(larry_user, "ops_reports"))

    def test_sync_package_persists_canonical_order_lane_fields(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "name": "Package Sync Project",
                        "package_code": "legacy_plus",
                        "package_slug": "legacy_plus",
                        "project_lane": "household",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                    }
                ],
                "project_entitlements": [],
                "finance_events": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
        ):
            result = admin_control_service.sync_package(project_id=str(project_id))
        self.assertEqual(result["order"]["package_code"], "legacy_plus")
        self.assertEqual(result["order"]["lane"], "household")
        stored_order = db["orders"].find_one({"_id": order_id}) or {}
        self.assertEqual(stored_order.get("package_code"), "legacy_plus")
        self.assertEqual(stored_order.get("package_slug"), "legacy_plus")
        self.assertEqual(stored_order.get("lane"), "household")
        self.assertEqual(stored_order.get("package_lane"), "household")


if __name__ == "__main__":
    unittest.main()
