import re
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

    def update_one(self, query, update, upsert=False):
        updated = 0
        for document in self.documents:
            if self._matches(document, query):
                for key, value in (update.get("$set") or {}).items():
                    document[key] = value
                for key, value in (update.get("$setOnInsert") or {}).items():
                    document.setdefault(key, value)
                updated = 1
                break
        upserted_id = None
        if not updated and upsert:
            inserted = dict(query)
            for key, value in (update.get("$setOnInsert") or {}).items():
                inserted[key] = value
            for key, value in (update.get("$set") or {}).items():
                inserted[key] = value
            inserted.setdefault("_id", ObjectId())
            self.documents.append(inserted)
            updated = 1
            upserted_id = inserted["_id"]
        return type(
            "Result",
            (),
            {"matched_count": 0 if upserted_id else updated, "modified_count": updated if not upserted_id else 0, "upserted_id": upserted_id},
        )()

    def update_many(self, query, update):
        modified = 0
        for document in self.documents:
            if self._matches(document, query):
                for key, value in (update.get("$set") or {}).items():
                    document[key] = value
                modified += 1
        return type("Result", (), {"modified_count": modified})()

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
            if key == "$and":
                if not all(self._matches(document, option) for option in expected):
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
                elif "$nin" in expected:
                    values = expected["$nin"]
                    if isinstance(actual, list):
                        if any(item in values for item in actual):
                            return False
                    elif actual in values:
                        return False
                elif "$regex" in expected:
                    pattern = expected.get("$regex")
                    flags = re.IGNORECASE if "i" in str(expected.get("$options") or "") else 0
                    if not re.search(str(pattern), str(actual or ""), flags):
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

    def test_ceo_profile_falls_back_to_role_permissions_when_access_context_permissions_are_empty(self):
        current_user = {
            "role": "admin",
            "access_tier": "ceo_master_admin",
            "_access_context": {
                "role_codes": ["ceo_master_admin", "executive_tech_admin"],
                "permissions": [],
            },
        }

        profile = admin_control_service.admin_control_access_profile(current_user)

        self.assertTrue(profile["is_wildcard"])
        self.assertEqual(profile["role_key"], "ceo_master_admin")
        self.assertIn("overview", profile["allowed_queues"])
        self.assertIn("users", profile["allowed_queues"])
        self.assertIn("mint_queue", profile["allowed_queues"])
        self.assertIn("audit", profile["allowed_queues"])

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


class AdminControlDiagnosticsTests(unittest.TestCase):
    def test_ceo_master_admin_diagnostics_report_wildcard_scope(self):
        current_user = {
            "id": "user-larry-1",
            "role": "admin",
            "access_tier": "ceo_master_admin",
            "_access_context": {
                "role_codes": ["ceo_master_admin"],
                "permissions": ["*"],
            },
        }
        db = FakeDatabase({"projects": [{"_id": "proj-1"}]})
        with patch.object(admin_control_service, "get_database", return_value=db):
            diagnostics = admin_control_service.admin_control_diagnostics(current_user)

        self.assertEqual(diagnostics["user_id"], "user-larry-1")
        self.assertEqual(diagnostics["role_key"], "ceo_master_admin")
        self.assertTrue(diagnostics["is_ceo_master_admin"])
        self.assertTrue(diagnostics["is_wildcard"])
        self.assertEqual(diagnostics["queue_scope_mode"], "wildcard_all_queues")
        self.assertEqual(diagnostics["bootstrap_endpoint_status"], "ok")
        self.assertEqual(diagnostics["search_endpoint_status"], "ok")
        self.assertTrue(diagnostics["frontend_revision"])
        self.assertTrue(diagnostics["backend_revision"])
        for forbidden_key in ("token", "cookie", "password", "secret", "credential"):
            self.assertNotIn(forbidden_key, str(diagnostics).lower())

    def test_ordinary_admin_diagnostics_are_allowlist_scoped(self):
        current_user = {
            "id": "user-officer-1",
            "role": "admin",
            "access_tier": "operations_admin",
            "_access_context": {
                "role_codes": ["operations_admin"],
                "permissions": ["admin.control.view"],
            },
        }
        db = FakeDatabase({"projects": [{"_id": "proj-1"}]})
        with patch.object(admin_control_service, "get_database", return_value=db):
            diagnostics = admin_control_service.admin_control_diagnostics(current_user)

        self.assertFalse(diagnostics["is_ceo_master_admin"])
        self.assertFalse(diagnostics["is_wildcard"])
        self.assertEqual(diagnostics["queue_scope_mode"], "allowlist")

    def test_diagnostics_report_unavailable_endpoints_when_database_unreachable(self):
        current_user = {
            "id": "user-larry-1",
            "role": "admin",
            "access_tier": "ceo_master_admin",
            "_access_context": {
                "role_codes": ["ceo_master_admin"],
                "permissions": ["*"],
            },
        }
        with patch.object(admin_control_service, "get_database", side_effect=RuntimeError("db down")):
            diagnostics = admin_control_service.admin_control_diagnostics(current_user)

        self.assertEqual(diagnostics["bootstrap_endpoint_status"], "unavailable")
        self.assertEqual(diagnostics["search_endpoint_status"], "unavailable")
        # Even with the database unreachable, CEO wildcard scope must still
        # be recognized from role/permission data alone.
        self.assertTrue(diagnostics["is_ceo_master_admin"])
        self.assertEqual(diagnostics["queue_scope_mode"], "wildcard_all_queues")


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
                    # role intentionally omitted here; testing non-role updates
                },
                actor={"_id": ObjectId(), "email": "ceo@example.com"},
            )

        self.assertEqual(result["before"]["email"], "before@example.com")
        self.assertEqual(result["after"]["email"], "after@example.com")
        self.assertEqual(result["after"]["full_name"], "After Name")
        self.assertEqual(result["after"]["status"], "suspended")

    def test_super_admin_can_promote_existing_admin_to_super_admin(self):
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

    def test_super_admin_cannot_promote_customer_to_super_admin(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "customer@example.com",
                        "full_name": "Customer",
                        "role": "user",
                        "status": "active",
                    }
                ]
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "super_admin role can only be granted to existing internal admin accounts"):
                admin_control_service.super_admin_update_user(
                    user_id=str(user_id),
                    payload={"role": "super_admin"},
                    actor={"_id": ObjectId(), "email": "ceo@tomboflight.com"},
                )

    def test_ceo_master_admin_role_is_singleton_to_larry_identity(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "someone.else@tomboflight.com",
                        "full_name": "Someone Else",
                        "role": "operations_admin",
                        "status": "active",
                    }
                ]
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            with self.assertRaisesRegex(
                ValueError,
                "ceo_master_admin role can only be assigned to Larry Robinson's canonical identity",
            ):
                admin_control_service.super_admin_update_user(
                    user_id=str(user_id),
                    payload={"role": "ceo_master_admin"},
                    actor={"_id": ObjectId(), "email": "ceo@tomboflight.com"},
                )

    def test_impersonation_session_lifecycle_readonly_to_editing_to_stop(self):
        actor_id = ObjectId()
        customer_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": customer_id,
                        "email": "rakim@example.com",
                        "full_name": "Rakim Robinson",
                        "role": "user",
                        "status": "active",
                    }
                ],
                "admin_impersonation_sessions": [],
            }
        )

        with patch.object(admin_control_service, "get_database", return_value=db):
            started = admin_control_service.start_admin_impersonation(
                case_id=f"user:{customer_id}",
                reason="Support walkthrough",
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            self.assertTrue(started["active"])
            self.assertFalse(started["editing_enabled"])

            with self.assertRaisesRegex(ValueError, "active impersonation session already exists"):
                admin_control_service.start_admin_impersonation(
                    case_id=f"user:{customer_id}",
                    reason="Second session should fail",
                    actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
                )

            enabled = admin_control_service.enable_admin_impersonation_editing(
                session_id=started["session_id"],
                reason="Need to correct customer profile field",
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            self.assertTrue(enabled["editing_enabled"])

            active = admin_control_service.active_admin_impersonation(
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            self.assertTrue(active["active"])
            self.assertEqual(active["impersonated_customer_name"], "Rakim Robinson")

            stopped = admin_control_service.stop_admin_impersonation(
                session_id=started["session_id"],
                reason="Finished assistance",
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            self.assertFalse(stopped["active"])
            self.assertEqual(stopped["status"], "stopped")

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
    def test_overview_summary_counts_customer_and_admin_users_separately(self):
        db = FakeDatabase(
            {
                "users": [
                    {"_id": ObjectId(), "email": "l.robinson@tomboflight.com", "account_type": "business_admin"},
                    {"_id": ObjectId(), "email": "customer-paid@example.com", "account_type": "customer"},
                    {"_id": ObjectId(), "email": "customer-unpaid@example.com", "account_type": "customer"},
                ],
                "projects": [],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "email": "customer-paid@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                    }
                ],
                "project_entitlements": [],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
                "uploaded_files": [],
                "verification_records": [],
                "household_invites": [],
                "project_members": [],
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            payload = admin_control_service.admin_console_overview(limit=5)
        summary = payload["summary"]
        self.assertEqual(summary["total_users"], 3)
        self.assertEqual(summary["total_business_admin_users"], 1)
        self.assertEqual(summary["total_customer_users"], 2)
        self.assertEqual(summary["paid_customer_users"], 1)
        self.assertEqual(summary["signed_up_no_purchase_users"], 1)

    def test_overview_counts_mixed_case_seed_statuses_and_matches_case_visibility(self):
        project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {"_id": ObjectId(), "email": "customer@example.com", "account_type": "customer"},
                ],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "owner_user_id": str(ObjectId()),
                        "name": "Visible Project",
                        "package_code": "legacy_plus",
                        "package_slug": "legacy_plus",
                        "project_lane": "household",
                        "status": "BUILD_READY",
                        "phase": "INTAKE_APPROVED",
                    }
                ],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "PAID",
                        "item_type": "package",
                        "package_code": "legacy_plus",
                        "package_slug": "legacy_plus",
                    }
                ],
                "project_entitlements": [],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
                "uploaded_files": [],
                "verification_records": [],
                "household_invites": [],
                "project_members": [],
                "users_role_assignments": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(
                admin_control_service,
                "get_project_entitlement",
                return_value={
                    "package_code": "legacy_plus",
                    "package_lane": "household",
                    "maintenance_plan": "monthly",
                    "maintenance_status": "active",
                    "resolved_entitlements": {"can_use_household_vault": True, "can_use_viewer": True},
                    "active_addons": ["extra_storage"],
                },
            ),
            patch.object(
                admin_control_service,
                "run_readiness_check",
                return_value={
                    "mint_review_ready": True,
                    "mint_eligible": True,
                    "mint_already_completed": False,
                    "package_synced": False,
                    "lane_assigned": True,
                    "order_linked": True,
                    "entitlement_exists": False,
                    "summary": "repair needed",
                    "blocking_reasons": [],
                },
            ),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(admin_control_service, "count_workspace_uploads", return_value=1),
        ):
            overview = admin_control_service.admin_console_overview(limit=10)
            cases = admin_control_service.list_customer_cases(limit=10)
        summary = overview["summary"]
        self.assertGreaterEqual(summary["total_active_projects"], 1)
        self.assertGreaterEqual(summary["paid_orders"], 1)
        self.assertGreaterEqual(summary["missing_entitlements"], 1)
        self.assertGreaterEqual(summary["projects_with_data_mismatch"], 1)
        self.assertTrue(cases["items"])

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
                "get_project_entitlement",
                return_value={
                    "package_code": "legacy_plus",
                    "package_lane": "household",
                    "maintenance_plan": "monthly",
                    "maintenance_status": "active",
                    "resolved_entitlements": {"can_use_household_vault": True, "can_use_viewer": True},
                    "active_addons": ["extra_storage"],
                },
            ),
            patch.object(
                admin_control_service,
                "resolve_canonical_mint_status",
                return_value={
                    "project_id": str(project_id),
                    "current_status": "not_started",
                    "minted": False,
                    "records": [],
                },
            ),
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


class MasterAdminCompletionTests(unittest.TestCase):
    def test_account_360_workspace_exposes_required_tabs(self):
        project_id = ObjectId()
        order_id = ObjectId()
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [{"_id": user_id, "email": "rakim@example.com", "full_name": "Rakim Robinson", "role": "user", "status": "active"}],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "rakim@example.com",
                        "owner_user_id": str(user_id),
                        "name": "Rakim Legacy Project",
                        "project_lane": "household",
                        "package_code": "legacy_plus",
                        "package_slug": "legacy_plus",
                        "package_name": "Legacy Plus",
                        "status": "in_production",
                        "phase": "build_started",
                        "family_id": str(ObjectId()),
                        "household_id": str(ObjectId()),
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "rakim@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_plus",
                        "package_slug": "legacy_plus",
                        "stripe_session_id": "cs_test_123",
                    }
                ],
                "project_entitlements": [
                    {
                        "_id": ObjectId(),
                        "project_id": project_id,
                        "user_id": user_id,
                        "package_code": "legacy_plus",
                        "package_lane": "household",
                        "maintenance_plan": "monthly",
                        "maintenance_status": "active",
                        "resolved_entitlements": {"can_use_household_vault": True, "can_use_viewer": True},
                        "active_addons": ["extra_storage"],
                    }
                ],
                "uploaded_files": [],
                "audit_logs": [],
                "families": [],
                "households": [],
                "vault_items": [],
                "vault_collections": [],
                "vault_access_grants": [],
                "vault_release_rules": [],
                "vault_audit_events": [],
                "mint_records": [],
                "finance_events": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(
                admin_control_service,
                "get_project_entitlement",
                return_value={
                    "package_code": "legacy_plus",
                    "package_lane": "household",
                    "maintenance_plan": "monthly",
                    "maintenance_status": "active",
                    "resolved_entitlements": {"can_use_household_vault": True, "can_use_viewer": True},
                    "active_addons": ["extra_storage"],
                },
            ),
            patch.object(
                admin_control_service,
                "resolve_canonical_mint_status",
                return_value={
                    "project_id": str(project_id),
                    "current_status": "not_started",
                    "minted": False,
                    "records": [],
                },
            ),
            patch.object(
                admin_control_service,
                "run_readiness_check",
                return_value={
                    "mint_review_ready": True,
                    "mint_eligible": False,
                    "mint_already_completed": False,
                    "package_synced": True,
                    "lane_assigned": True,
                    "order_linked": True,
                    "entitlement_exists": True,
                    "blocking_reasons": ["upload_review_pending"],
                    "summary": "Ready for review",
                },
            ),
        ):
            workspace = admin_control_service.customer_case_workspace(str(project_id))
        tabs = workspace.get("tabs") or {}
        for key in (
            "overview",
            "package_services",
            "family_household",
            "production",
            "uploads",
            "vault_metadata",
            "billing",
            "mint",
            "audit_history",
        ):
            self.assertIn(key, tabs)

    def test_master_search_supports_order_stripe_and_workflow_identifiers(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "rakim@example.com",
                        "owner_user_id": str(ObjectId()),
                        "name": "Rakim Search Project",
                        "family_id": str(ObjectId()),
                        "household_id": str(ObjectId()),
                        "package_code": "legacy_plus",
                        "project_lane": "household",
                        "status": "client_review",
                        "phase": "client_review",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "project_id": project_id,
                        "email": "rakim@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_plus",
                        "stripe_session_id": "cs_test_search",
                        "stripe_payment_intent_id": "pi_test_search",
                        "stripe_customer_id": "cus_test_search",
                    }
                ],
                "project_entitlements": [],
                "uploaded_files": [],
                "audit_logs": [],
                "users": [],
                "families": [],
                "households": [],
                "mint_records": [],
            }
        )
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(
                admin_control_service,
                "run_readiness_check",
                return_value={"mint_review_ready": False, "mint_eligible": False, "mint_already_completed": False, "blocking_reasons": []},
            ),
            patch.object(admin_control_service, "count_workspace_uploads", return_value=1),
        ):
            by_order_id = admin_control_service.list_customer_cases(search=str(order_id), limit=10)
            by_stripe = admin_control_service.list_customer_cases(search="cs_test_search", limit=10)
            by_workflow = admin_control_service.list_customer_cases(search="client_review", limit=10)
        self.assertTrue(by_order_id["items"])
        self.assertTrue(by_stripe["items"])
        self.assertTrue(by_workflow["items"])

    def test_service_controls_preview_and_apply_preserve_stripe_purchase_record(self):
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "rakim@example.com",
                        "owner_user_id": str(ObjectId()),
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "package_name": "Legacy Snapshot",
                        "project_lane": "portrait",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "email": "rakim@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "package_name": "Legacy Snapshot",
                        "stripe_session_id": "cs_test_preserve",
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
            before_order = dict(db["orders"].find_one({"_id": order_id}) or {})
            preview = admin_control_service.super_admin_preview_service_controls(
                project_id=str(project_id),
                payload={
                    "operation": "upgrade",
                    "package_code": "legacy_plus",
                    "add_addons": ["extra_storage"],
                    "storage_adjustment_gb": 1.0,
                    "maintenance_state": "active",
                },
            )
            after_preview_order = dict(db["orders"].find_one({"_id": order_id}) or {})
            applied = admin_control_service.super_admin_apply_service_controls(
                project_id=str(project_id),
                payload={
                    "operation": "upgrade",
                    "package_code": "legacy_plus",
                    "add_addons": ["extra_storage"],
                    "storage_adjustment_gb": 1.0,
                    "maintenance_state": "active",
                },
                actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
        self.assertEqual(before_order.get("status"), after_preview_order.get("status"))
        self.assertEqual(before_order.get("stripe_session_id"), after_preview_order.get("stripe_session_id"))
        self.assertTrue(preview["validation"]["stripe_purchase_record_preserved"])
        self.assertTrue(applied["stripe_purchase_record_preserved"])
        stored_order = db["orders"].find_one({"_id": order_id}) or {}
        self.assertEqual(stored_order.get("status"), "paid")
        self.assertEqual(stored_order.get("stripe_session_id"), "cs_test_preserve")

    def test_officer_permission_management_targets_only_named_officers(self):
        jenn_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": jenn_id,
                        "email": "jenn.wood@tomboflight.com",
                        "full_name": "Jennifer Wood",
                        "role": "admin",
                        "access_tier": "finance_admin",
                        "department_role": "finance_admin",
                        "status": "active",
                    }
                ],
                "user_role_assignments": [],
                "user_permission_overrides": [],
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            officers = admin_control_service.super_admin_list_officers()
            preview = admin_control_service.super_admin_preview_officer_permissions(
                officer_email="jenn.wood@tomboflight.com",
                role_assignments=["finance_admin"],
                grant_permissions=["admin.audit.read"],
            )
            applied = admin_control_service.super_admin_apply_officer_permissions(
                officer_email="jenn.wood@tomboflight.com",
                role_assignments=["finance_admin"],
                grant_permissions=["admin.audit.read"],
                actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
        self.assertTrue(officers["items"])
        self.assertIn("admin.audit.read", preview["proposed_after"]["permission_overrides"])
        self.assertIn("admin.audit.read", applied["after"]["permission_overrides"])
        self.assertTrue(db["user_permission_overrides"].documents)

    def test_rakim_read_only_acceptance_path_no_production_writes(self):
        actor_id = ObjectId()
        customer_id = ObjectId()
        project_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": customer_id,
                        "email": "rakim@example.com",
                        "full_name": "Rakim Robinson",
                        "role": "user",
                        "status": "active",
                    }
                ],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "rakim@example.com",
                        "owner_user_id": str(customer_id),
                        "name": "Rakim Household",
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "project_lane": "household",
                        "status": "in_production",
                    }
                ],
                "orders": [
                    {
                        "_id": order_id,
                        "project_id": project_id,
                        "email": "rakim@example.com",
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "package_slug": "legacy_snapshot",
                        "stripe_session_id": "cs_test_rakim",
                    }
                ],
                "project_entitlements": [],
                "admin_impersonation_sessions": [],
                "audit_logs": [],
                "uploaded_files": [],
                "families": [],
                "households": [],
                "mint_records": [],
                "vault_items": [],
                "vault_collections": [],
                "vault_access_grants": [],
                "vault_release_rules": [],
                "vault_audit_events": [],
                "finance_events": [],
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
                    "summary": "ready",
                    "blocking_reasons": [],
                },
            ),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(
                admin_control_service,
                "resolve_canonical_mint_status",
                return_value={
                    "project_id": str(project_id),
                    "current_status": "not_started",
                    "minted": False,
                    "records": [],
                },
            ),
        ):
            cases = admin_control_service.list_customer_cases(search="Rakim", queue="users", limit=10)
            workspace = admin_control_service.customer_case_workspace(str(project_id))
            project_before = dict(db["projects"].find_one({"_id": project_id}) or {})
            order_before = dict(db["orders"].find_one({"_id": order_id}) or {})
            preview = admin_control_service.super_admin_preview_service_controls(
                project_id=str(project_id),
                payload={"operation": "upgrade", "package_code": "legacy_plus"},
            )
            project_after_preview = dict(db["projects"].find_one({"_id": project_id}) or {})
            order_after_preview = dict(db["orders"].find_one({"_id": order_id}) or {})
            started = admin_control_service.start_admin_impersonation(
                case_id=str(project_id),
                reason="Read-only acceptance verification",
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            active = admin_control_service.active_admin_impersonation(
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            stopped = admin_control_service.stop_admin_impersonation(
                session_id=started["session_id"],
                reason="Acceptance complete",
                actor={"_id": actor_id, "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
        self.assertTrue(cases["items"])
        self.assertIn("overview", workspace.get("tabs") or {})
        self.assertTrue(preview["changes"])
        self.assertEqual(project_before.get("package_code"), project_after_preview.get("package_code"))
        self.assertEqual(order_before.get("package_code"), order_after_preview.get("package_code"))
        self.assertEqual(order_before.get("stripe_session_id"), order_after_preview.get("stripe_session_id"))
        self.assertTrue(active["active"])
        self.assertFalse(stopped["active"])
        self.assertEqual(stopped["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
