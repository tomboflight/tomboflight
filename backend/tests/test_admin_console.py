import hashlib
import re
import unittest
from datetime import datetime, timedelta, timezone
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

    def test_noncanonical_super_admin_label_never_grants_admin_or_wildcard_access(self):
        user_id = ObjectId()
        user = {
            "_id": user_id,
            "email": "legacy-super@example.com",
            "role": "super_admin",
            "status": "active",
        }
        db = FakeDatabase(
            {
                "user_role_assignments": [
                    {
                        "user_id": str(user_id),
                        "role_code": "super_admin",
                        "status": "active",
                    }
                ],
                "role_capabilities": [],
                "role_permissions": [],
                "user_permission_overrides": [
                    {
                        "user_id": str(user_id),
                        "permission_code": "*",
                        "status": "active",
                    }
                ],
                "projects": [],
                "workflow_events": [],
            }
        )

        with (
            patch.object(auth_dependencies, "_load_user_by_id", return_value=user),
            patch.object(auth_dependencies, "_db", return_value=db),
            patch.object(auth_dependencies, "list_user_project_entitlements", return_value=[]),
            patch.object(auth_dependencies, "list_accessible_project_ids", return_value=[]),
        ):
            context = auth_dependencies.resolve_access_context(str(user_id))

        self.assertFalse(auth_dependencies.has_internal_admin_access(user))
        self.assertNotIn("super_admin", context["role_codes"])
        self.assertNotIn("*", context["capabilities"])
        self.assertNotIn("*", context["permissions"])

    def test_canonical_ceo_remains_the_single_wildcard_admin_identity(self):
        user_id = ObjectId()
        user = {
            "_id": user_id,
            "email": "l.robinson@tomboflight.com",
            "role": "user",
            "status": "active",
        }
        db = FakeDatabase(
            {
                "user_role_assignments": [],
                "role_capabilities": [],
                "role_permissions": [],
                "user_permission_overrides": [],
                "projects": [],
                "workflow_events": [],
            }
        )

        with (
            patch.object(auth_dependencies, "_load_user_by_id", return_value=user),
            patch.object(auth_dependencies, "_db", return_value=db),
            patch.object(auth_dependencies, "list_user_project_entitlements", return_value=[]),
        ):
            context = auth_dependencies.resolve_access_context(str(user_id))

        self.assertTrue(auth_dependencies.has_internal_admin_access(user))
        self.assertIn("ceo_master_admin", context["role_codes"])
        self.assertIn("*", context["capabilities"])
        self.assertIn("*", context["permissions"])


class AdminControlAccessProfileTests(unittest.TestCase):
    def test_overview_payload_is_reduced_to_each_officers_authorized_domain(self):
        payload = {
            "summary": {"gross_revenue": 100, "total_users": 19},
            "finance_sections": {"money_now": {"gross_revenue": 100}},
            "marketing_sections": {"traffic_awareness": {"visitors": 10}},
            "operations_sections": {"intake_onboarding": {"intake_started": 2}},
            "priority_repairs": {
                "paid_order_without_project_link": [
                    {"email": "private@example.com", "order_id": "order-1"}
                ]
            },
            "mismatches": [{"project_id": "project-1"}],
            "system_health": {"postmark": {"token_configured": True}},
        }
        role_payloads = {
            "finance_admin": ("finance_sections", "money_now"),
            "operations_admin": ("operations_sections", "intake_onboarding"),
            "marketing_admin": ("marketing_sections", "traffic_awareness"),
        }

        for role_code, (allowed_section, allowed_key) in role_payloads.items():
            with self.subTest(role_code=role_code):
                filtered = admin_control_service.filter_admin_console_overview_for_access(
                    payload,
                    {
                        "role": role_code,
                        "_access_context": {
                            "role_codes": [role_code],
                            "permissions": [
                                "admin.control.view",
                                "admin.control.billing",
                                "admin.analytics.read",
                            ],
                        },
                    },
                )
                self.assertIn(allowed_key, filtered[allowed_section])
                self.assertEqual(filtered["summary"], {})
                self.assertEqual(filtered["priority_repairs"], {})
                self.assertEqual(filtered["mismatches"], [])
                self.assertEqual(filtered["system_health"], {})
                for section_name in {
                    "finance_sections",
                    "marketing_sections",
                    "operations_sections",
                } - {allowed_section}:
                    self.assertEqual(filtered[section_name], {})

    def test_wildcard_overview_payload_remains_complete(self):
        payload = {"summary": {"total_users": 19}, "finance_sections": {"money_now": {}}}
        filtered = admin_control_service.filter_admin_console_overview_for_access(
            payload,
            {
                "role": "ceo_master_admin",
                "_access_context": {
                    "role_codes": ["ceo_master_admin"],
                    "permissions": ["*"],
                },
            },
        )
        self.assertIs(filtered, payload)

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
                "role_codes": ["ceo_master_admin", "super_admin"],
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

    def test_diagnostics_prefer_deployed_git_commit_for_backend_revision(self):
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
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.dict(admin_control_service.os.environ, {"RENDER_GIT_COMMIT": "render-sha-123"}, clear=False),
        ):
            diagnostics = admin_control_service.admin_control_diagnostics(current_user)

        self.assertEqual(diagnostics["backend_revision"], "render-sha-123")

    def test_diagnostics_falls_back_to_app_version_when_deployment_sha_missing(self):
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
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.dict(
                admin_control_service.os.environ,
                {
                    "RENDER_GIT_COMMIT": "",
                    "RELEASE_SHA": "",
                    "GIT_COMMIT": "",
                    "COMMIT_SHA": "",
                    "VERCEL_GIT_COMMIT_SHA": "",
                },
                clear=False,
            ),
        ):
            diagnostics = admin_control_service.admin_control_diagnostics(current_user)

        self.assertEqual(diagnostics["backend_revision"], admin_control_service.settings.app_version)
        self.assertNotEqual(diagnostics["backend_revision"], "super-secret-token")

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
    def test_create_customer_can_provision_complimentary_package_atomically(self):
        db = FakeDatabase({"users": [], "projects": [], "admin_package_assignments": [], "audit_logs": []})
        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "ensure_project_owner_membership", return_value={"status": "active"}) as membership,
            patch.object(
                admin_control_service,
                "upsert_project_entitlement",
                return_value={"status": "active", "package_code": "digital_legacy_portrait"},
            ) as entitlement,
        ):
            result = admin_control_service.super_admin_create_customer(
                payload={
                    "email": "new.customer@example.com",
                    "full_name": "New Customer",
                    "package_code": "digital_legacy_portrait",
                    "project_name": "New Customer Legacy Build",
                    "package_grant_type": "complimentary_package",
                    "reason": "CEO-approved customer package grant",
                },
                actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com"},
            )

        self.assertTrue(result["package_granted"])
        self.assertEqual(result["package_code"], "digital_legacy_portrait")
        self.assertEqual(result["entitlement_status"], "active")
        self.assertFalse(result["payment_record_created"])
        self.assertEqual(len(db["users"].documents), 1)
        self.assertEqual(len(db["projects"].documents), 1)
        self.assertEqual(db["projects"].documents[0]["owner_user_id"], result["user_id"])
        self.assertEqual(db["projects"].documents[0]["status"], "intake_pending")
        self.assertEqual(db["admin_package_assignments"].documents[0]["billing_classification"], "complimentary_package")
        membership.assert_called_once()
        entitlement.assert_called_once()

    def test_account_close_archives_owned_workspaces_and_preserves_financial_history(self):
        user_id = ObjectId()
        project_id = ObjectId()
        family_id = ObjectId()
        household_id = ObjectId()
        order_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "departed@example.com",
                        "full_name": "Departed Customer",
                        "role": "user",
                        "status": "active",
                        "session_token_version": 4,
                    }
                ],
                "projects": [{"_id": project_id, "owner_user_id": str(user_id), "status": "build_ready"}],
                "families": [{"_id": family_id, "owner_user_id": str(user_id), "status": "active"}],
                "households": [{"_id": household_id, "owner_user_id": str(user_id), "status": "active"}],
                "project_entitlements": [
                    {"_id": ObjectId(), "project_id": project_id, "user_id": user_id, "status": "active"}
                ],
                "project_members": [
                    {"_id": ObjectId(), "project_id": str(project_id), "user_id": str(user_id), "status": "active"}
                ],
                "household_invites": [
                    {"_id": ObjectId(), "household_id": str(household_id), "status": "pending"}
                ],
                "intake_submissions": [
                    {"_id": ObjectId(), "user_id": user_id, "email": "departed@example.com", "status": "submitted"}
                ],
                "orders": [{"_id": order_id, "user_id": user_id, "status": "paid", "amount": 79900}],
                "user_role_assignments": [],
                "user_permission_overrides": [],
                "audit_logs": [],
            }
        )

        with patch.object(admin_control_service, "get_database", return_value=db):
            blocked = admin_control_service.super_admin_preview_account_lifecycle(
                user_id=str(user_id), action="archive"
            )
            applied = admin_control_service.super_admin_apply_account_lifecycle(
                user_id=str(user_id),
                action="archive",
                reason="Customer and former staff separation",
                archive_owned_records=True,
                actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com"},
            )

        self.assertTrue(blocked["blocked"])
        self.assertFalse(applied["blocked"])
        self.assertTrue(applied["sessions_revoked"])
        self.assertEqual(db["users"].documents[0]["status"], "archived")
        self.assertFalse(db["users"].documents[0]["login_enabled"])
        self.assertEqual(db["users"].documents[0]["session_token_version"], 5)
        self.assertEqual(db["projects"].documents[0]["status"], "archived")
        self.assertEqual(db["families"].documents[0]["status"], "archived")
        self.assertEqual(db["households"].documents[0]["status"], "archived")
        self.assertEqual(db["project_entitlements"].documents[0]["status"], "archived")
        self.assertEqual(db["project_members"].documents[0]["status"], "inactive")
        self.assertEqual(db["household_invites"].documents[0]["status"], "cancelled")
        self.assertEqual(db["intake_submissions"].documents[0]["status"], "archived")
        self.assertEqual(db["orders"].documents[0]["status"], "paid")
        self.assertEqual(db["orders"].documents[0]["amount"], 79900)

    def test_canonical_ceo_account_cannot_be_archived_by_routine_control(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "l.robinson@tomboflight.com",
                        "role": "ceo_master_admin",
                        "status": "active",
                    }
                ],
                "projects": [],
                "families": [],
                "households": [],
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            preview = admin_control_service.super_admin_preview_account_lifecycle(
                user_id=str(user_id), action="archive", archive_owned_records=True
            )
            with self.assertRaisesRegex(ValueError, "canonical CEO Master Administrator"):
                admin_control_service.super_admin_apply_account_lifecycle(
                    user_id=str(user_id),
                    action="archive",
                    reason="Accidental self-removal attempt",
                    archive_owned_records=True,
                    actor={"_id": user_id, "email": "l.robinson@tomboflight.com"},
                )

        self.assertTrue(preview["blocked"])
        self.assertEqual(db["users"].documents[0]["status"], "active")

    def test_billing_hold_is_recoverable_and_restore_clears_the_hold(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "past.due@example.com",
                        "full_name": "Past Due Customer",
                        "role": "user",
                        "status": "active",
                        "session_token_version": 1,
                    }
                ],
                "projects": [],
                "families": [],
                "households": [],
                "audit_logs": [],
            }
        )
        actor = {"_id": ObjectId(), "email": "l.robinson@tomboflight.com"}

        with patch.object(admin_control_service, "get_database", return_value=db):
            held = admin_control_service.super_admin_apply_account_lifecycle(
                user_id=str(user_id),
                action="billing_hold",
                reason="Monthly maintenance payment is past due",
                actor=actor,
            )
            restored = admin_control_service.super_admin_apply_account_lifecycle(
                user_id=str(user_id),
                action="restore",
                reason="Billing balance resolved",
                actor=actor,
            )

        user = db["users"].documents[0]
        self.assertTrue(held["proposed_after"]["billing_hold"])
        self.assertEqual(held["proposed_after"]["status"], "suspended")
        self.assertEqual(restored["proposed_after"]["status"], "active")
        self.assertEqual(user["status"], "active")
        self.assertTrue(user["login_enabled"])
        self.assertIsNone(user["billing_hold_at"])
        self.assertIsNone(user["billing_hold_reason"])
        self.assertEqual(user["session_token_version"], 3)

    def test_permanent_deletion_erases_identity_closes_access_and_writes_mongodb_receipt(self):
        user_id = ObjectId()
        project_id = ObjectId()
        family_id = ObjectId()
        household_id = ObjectId()
        original_email = "departed.permanent@example.com"
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": original_email,
                        "full_name": "Departed Permanent",
                        "phone_number": "757-555-0100",
                        "mailing_address": "Protected address",
                        "password_hash": "hashed-password",
                        "mfa_enabled": True,
                        "mfa_secret_encrypted": "encrypted-secret",
                        "role": "user",
                        "status": "archived",
                        "login_enabled": False,
                        "session_token_version": 4,
                    }
                ],
                "projects": [
                    {"_id": project_id, "owner_user_id": str(user_id), "owner_email": original_email, "status": "archived"}
                ],
                "families": [
                    {"_id": family_id, "owner_user_id": str(user_id), "owner_email": original_email, "status": "archived"}
                ],
                "households": [
                    {"_id": household_id, "owner_user_id": str(user_id), "owner_email": original_email, "status": "archived"}
                ],
                "project_entitlements": [
                    {
                        "_id": ObjectId(),
                        "project_id": project_id,
                        "user_id": user_id,
                        "status": "archived",
                        "maintenance_status": "active",
                        "maintenance_stripe_status": "active",
                        "maintenance_stripe_subscription_id": "sub_permanent_delete_test",
                    },
                    {
                        "_id": ObjectId(),
                        "project_id": project_id,
                        "user_id": user_id,
                        "status": "archived",
                        "maintenance_status": "active",
                        "maintenance_stripe_status": "active",
                        "maintenance_stripe_subscription_id": "sub_permanent_delete_second",
                    },
                ],
                "project_members": [
                    {"_id": ObjectId(), "project_id": str(project_id), "user_id": str(user_id), "status": "inactive"}
                ],
                "household_invites": [
                    {"_id": ObjectId(), "household_id": str(household_id), "status": "cancelled"}
                ],
                "household_links": [
                    {"_id": ObjectId(), "source_household_id": str(household_id), "target_household_id": "other-household", "link_status": "approved"}
                ],
                "intake_submissions": [
                    {"_id": ObjectId(), "user_id": user_id, "email": original_email, "status": "archived"}
                ],
                "uploaded_files": [
                    {
                        "_id": ObjectId(),
                        "project_id": str(project_id),
                        "uploaded_by_user_id": str(user_id),
                        "uploaded_by": original_email,
                    }
                ],
                "vault_items": [
                    {"_id": "vault-item-1", "project_id": str(project_id), "owner_user_id": str(user_id), "access_enabled": True}
                ],
                "vault_access_grants": [
                    {"_id": ObjectId(), "vault_item_id": "vault-item-1", "grantee_user_id": str(user_id), "status": "active"}
                ],
                "vault_collections": [
                    {"_id": ObjectId(), "project_id": str(project_id), "owner_user_id": str(user_id), "status": "active"}
                ],
                "vault_release_rules": [
                    {"_id": ObjectId(), "vault_item_id": "vault-item-1", "created_by_user_id": str(user_id), "status": "scheduled"}
                ],
                "organization_admin_invites": [
                    {"_id": ObjectId(), "project_id": str(project_id), "email": original_email, "status": "pending"}
                ],
                "project_link_keys": [
                    {"_id": ObjectId(), "project_id": str(project_id), "issuer_user_id": str(user_id), "status": "active"}
                ],
                "link_requests": [
                    {"_id": ObjectId(), "source_project_id": str(project_id), "requested_by_user_id": str(user_id), "status": "pending"}
                ],
                "experience_sessions": [
                    {"_id": ObjectId(), "project_id": str(project_id), "user_id": str(user_id), "status": "active"}
                ],
                "admin_impersonation_sessions": [
                    {
                        "_id": ObjectId(),
                        "impersonated_user_id": str(user_id),
                        "impersonated_email": original_email,
                        "status": "active",
                        "editing_enabled": True,
                    }
                ],
                "mint_jobs": [
                    {"_id": ObjectId(), "project_id": str(project_id), "status": "queued"}
                ],
                "mint_approvals": [
                    {"_id": ObjectId(), "project_id": str(project_id), "status": "approved"}
                ],
                "user_role_assignments": [
                    {"_id": ObjectId(), "user_id": user_id, "status": "active", "role_code": "marketing_admin"}
                ],
                "user_permission_overrides": [
                    {"_id": ObjectId(), "user_id": str(user_id), "status": "active", "permission": "admin.control_center"}
                ],
                "orders": [{"_id": ObjectId(), "user_id": user_id, "email": original_email, "status": "paid", "amount": 79900}],
                "account_deletion_tombstones": [],
                "audit_logs": [],
            }
        )

        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "write_audit_log", return_value="audit-delete-1"),
            patch.object(
                admin_control_service.stripe_admin_operations_service,
                "cancel_subscription",
                return_value={"subscription_id": "sub_permanent_delete_test", "status": "canceled"},
            ) as cancel_subscription,
        ):
            result = admin_control_service.super_admin_apply_account_permanent_deletion(
                user_id=str(user_id),
                reason_category="customer_request",
                reason="Verified written request to permanently close the account",
                confirmation_email=original_email,
                initial_confirmation=True,
                final_confirmation="PERMANENTLY DELETE",
                final_acknowledgement=True,
                continuity_operation_id="ckop_test_permanent_delete",
                actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com", "full_name": "Larry Robinson"},
            )
            restore_preview = admin_control_service.super_admin_preview_account_lifecycle(
                user_id=str(user_id), action="restore"
            )
            with self.assertRaisesRegex(ValueError, "permanently deleted"):
                admin_control_service.super_admin_update_user(
                    user_id=str(user_id), payload={"status": "active"}
                )

        self.assertEqual(cancel_subscription.call_count, 2)
        self.assertEqual(
            {
                call.kwargs["subscription_id"]
                for call in cancel_subscription.call_args_list
            },
            {"sub_permanent_delete_test", "sub_permanent_delete_second"},
        )
        self.assertEqual(
            len(
                {
                    call.kwargs["idempotency_key"]
                    for call in cancel_subscription.call_args_list
                }
            ),
            2,
        )
        for call in cancel_subscription.call_args_list:
            self.assertFalse(call.kwargs["at_period_end"])
            self.assertTrue(call.kwargs["confirm"])

        user = db["users"].documents[0]
        tombstone = db["account_deletion_tombstones"].documents[0]
        self.assertTrue(result["permanent"])
        self.assertFalse(result["restorable"])
        self.assertEqual(user["status"], "permanently_deleted")
        self.assertEqual(user["account_type"], "deleted_tombstone")
        self.assertFalse(user["login_enabled"])
        self.assertIsNone(user["password_hash"])
        self.assertIsNone(user["mfa_secret_encrypted"])
        self.assertIsNone(user["phone_number"])
        self.assertNotEqual(user["email"], original_email)
        self.assertEqual(user["session_token_version"], 5)
        self.assertTrue(restore_preview["blocked"])
        self.assertEqual(db["projects"].documents[0]["status"], "deleted")
        self.assertEqual(db["families"].documents[0]["status"], "deleted")
        self.assertEqual(db["households"].documents[0]["status"], "deleted")
        self.assertEqual(db["project_entitlements"].documents[0]["status"], "deleted")
        self.assertEqual(db["project_entitlements"].documents[0]["maintenance_status"], "canceled")
        self.assertEqual(db["project_members"].documents[0]["status"], "removed")
        self.assertEqual(db["uploaded_files"].documents[0]["uploaded_by"], user["email"])
        self.assertFalse(db["vault_items"].documents[0]["access_enabled"])
        self.assertEqual(db["vault_access_grants"].documents[0]["status"], "revoked")
        self.assertEqual(db["vault_collections"].documents[0]["status"], "closed")
        self.assertEqual(db["vault_release_rules"].documents[0]["status"], "revoked")
        self.assertEqual(db["project_link_keys"].documents[0]["status"], "revoked")
        self.assertEqual(db["link_requests"].documents[0]["status"], "cancelled")
        self.assertEqual(db["household_links"].documents[0]["link_status"], "revoked")
        self.assertEqual(db["organization_admin_invites"].documents[0]["status"], "cancelled")
        self.assertEqual(db["experience_sessions"].documents[0]["status"], "closed")
        self.assertEqual(db["admin_impersonation_sessions"].documents[0]["status"], "stopped")
        self.assertFalse(db["admin_impersonation_sessions"].documents[0]["editing_enabled"])
        self.assertEqual(db["mint_jobs"].documents[0]["status"], "obsolete")
        self.assertEqual(db["mint_approvals"].documents[0]["status"], "revoked")
        self.assertEqual(db["user_role_assignments"].documents[0]["status"], "revoked")
        self.assertEqual(db["user_permission_overrides"].documents[0]["status"], "revoked")
        self.assertEqual(db["orders"].documents[0]["status"], "paid")
        self.assertEqual(db["orders"].documents[0]["amount"], 79900)
        self.assertEqual(tombstone["status"], "completed")
        self.assertEqual(tombstone["continuity_operation_id"], "ckop_test_permanent_delete")
        self.assertEqual(tombstone["original_email_sha256"], hashlib.sha256(original_email.encode()).hexdigest())
        self.assertNotIn(original_email, str(tombstone))
        self.assertEqual(
            result["deletion_receipt"]["mongo_evidence"]["tombstone_collection"],
            "account_deletion_tombstones",
        )

    def test_permanent_deletion_requires_exact_email_phrase_and_never_deletes_ceo(self):
        target_id = ObjectId()
        ceo_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {"_id": target_id, "email": "target@example.com", "full_name": "Target", "role": "user", "status": "active"},
                    {"_id": ceo_id, "email": "l.robinson@tomboflight.com", "full_name": "Larry Robinson", "role": "ceo_master_admin", "status": "active"},
                ],
                "projects": [],
                "families": [],
                "households": [],
                "account_deletion_tombstones": [],
            }
        )
        common = {
            "user_id": str(target_id),
            "reason_category": "policy_violation",
            "reason": "Documented policy violation",
            "actor": {"_id": ceo_id, "email": "l.robinson@tomboflight.com"},
            "continuity_operation_id": "ckop_test_validation",
        }

        with patch.object(admin_control_service, "get_database", return_value=db):
            with self.assertRaisesRegex(PermissionError, "canonical CEO"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    user_id=str(target_id),
                    reason_category="policy_violation",
                    reason="Documented policy violation",
                    confirmation_email="target@example.com",
                    initial_confirmation=True,
                    final_confirmation="PERMANENTLY DELETE",
                    final_acknowledgement=True,
                    actor={"_id": ObjectId(), "email": "operations@example.com"},
                )
            with self.assertRaisesRegex(ValueError, "correct target account"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    **common,
                    confirmation_email="target@example.com",
                    initial_confirmation=False,
                    final_confirmation="PERMANENTLY DELETE",
                    final_acknowledgement=True,
                )
            with self.assertRaisesRegex(ValueError, "final permanent-closure"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    **common,
                    confirmation_email="target@example.com",
                    initial_confirmation=True,
                    final_confirmation="PERMANENTLY DELETE",
                    final_acknowledgement=False,
                )
            with self.assertRaisesRegex(ValueError, "confirmation email"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    **common,
                    confirmation_email="wrong@example.com",
                    initial_confirmation=True,
                    final_confirmation="PERMANENTLY DELETE",
                    final_acknowledgement=True,
                )
            with self.assertRaisesRegex(ValueError, "PERMANENTLY DELETE"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    **common,
                    confirmation_email="target@example.com",
                    initial_confirmation=True,
                    final_confirmation="delete",
                    final_acknowledgement=True,
                )
            with self.assertRaisesRegex(ValueError, "Invalid account status"):
                admin_control_service.super_admin_update_user(
                    user_id=str(target_id), payload={"status": "permanently_deleted"}
                )
            ceo_preview = admin_control_service.super_admin_preview_account_permanent_deletion(
                user_id=str(ceo_id), reason_category="company_authorized"
            )
            with self.assertRaisesRegex(ValueError, "blocked"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    user_id=str(ceo_id),
                    reason_category="company_authorized",
                    reason="Attempted CEO deletion",
                    confirmation_email="l.robinson@tomboflight.com",
                    initial_confirmation=True,
                    final_confirmation="PERMANENTLY DELETE",
                    final_acknowledgement=True,
                    continuity_operation_id="ckop_test_ceo_protection",
                    actor={"_id": ceo_id, "email": "l.robinson@tomboflight.com"},
                )

        self.assertTrue(ceo_preview["blocked"])
        self.assertEqual(db["users"].documents[0]["status"], "active")
        self.assertEqual(db["users"].documents[1]["status"], "active")
        self.assertEqual(db["account_deletion_tombstones"].documents, [])

    def test_permanent_deletion_failure_leaves_resumable_identity_lock_and_tombstone(self):
        user_id = ObjectId()
        project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "subscribed@example.com",
                        "full_name": "Subscribed Customer",
                        "role": "user",
                        "status": "active",
                        "login_enabled": True,
                    }
                ],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_user_id": str(user_id),
                        "owner_email": "subscribed@example.com",
                        "status": "active",
                    }
                ],
                "families": [],
                "households": [],
                "project_entitlements": [
                    {
                        "_id": ObjectId(),
                        "project_id": str(project_id),
                        "user_id": str(user_id),
                        "status": "active",
                        "maintenance_status": "active",
                        "maintenance_stripe_subscription_id": "sub_cancel_failure",
                    }
                ],
                "account_deletion_tombstones": [],
            }
        )

        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(
                admin_control_service.stripe_admin_operations_service,
                "cancel_subscription",
                side_effect=RuntimeError("Stripe cancellation unavailable"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Stripe cancellation unavailable"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    user_id=str(user_id),
                    reason_category="customer_request",
                    reason="Verified deletion request",
                    confirmation_email="subscribed@example.com",
                    initial_confirmation=True,
                    final_confirmation="PERMANENTLY DELETE",
                    final_acknowledgement=True,
                    continuity_operation_id="ckop_stripe_failure",
                    actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com"},
                )

        self.assertEqual(db["users"].documents[0]["status"], "deletion_in_progress")
        self.assertFalse(db["users"].documents[0]["login_enabled"])
        self.assertEqual(db["projects"].documents[0]["status"], "active")
        tombstone = db["account_deletion_tombstones"].documents[0]
        self.assertEqual(tombstone["status"], "failed_retryable")
        self.assertEqual(tombstone["phase"], "subscription_cancellation")
        self.assertEqual(tombstone["continuity_operation_id"], "ckop_stripe_failure")

    def test_permanent_deletion_resumes_audit_closure_without_recreating_identity(self):
        user_id = ObjectId()
        original_email = "audit-resume@example.com"
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": original_email,
                        "full_name": "Audit Resume",
                        "role": "user",
                        "status": "active",
                        "login_enabled": True,
                        "session_token_version": 2,
                    }
                ],
                "projects": [],
                "families": [],
                "households": [],
                "account_deletion_tombstones": [],
            }
        )
        common = {
            "user_id": str(user_id),
            "reason_category": "customer_request",
            "reason": "Verified written deletion request",
            "confirmation_email": original_email,
            "initial_confirmation": True,
            "final_confirmation": "PERMANENTLY DELETE",
            "final_acknowledgement": True,
            "continuity_operation_id": "ckop_audit_resume",
            "actor": {
                "_id": ObjectId(),
                "email": "l.robinson@tomboflight.com",
            },
        }

        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(
                admin_control_service,
                "write_audit_log",
                side_effect=[RuntimeError("audit unavailable"), "audit-delete-resumed"],
            ) as write_audit,
            patch.object(
                admin_control_service.stripe_admin_operations_service,
                "cancel_subscription",
            ) as cancel_subscription,
        ):
            with self.assertRaisesRegex(RuntimeError, "audit evidence is still pending"):
                admin_control_service.super_admin_apply_account_permanent_deletion(
                    **common
                )
            deletion_id = db["account_deletion_tombstones"].documents[0]["deletion_id"]
            resumed = admin_control_service.super_admin_apply_account_permanent_deletion(
                **common
            )

        user = db["users"].documents[0]
        tombstone = db["account_deletion_tombstones"].documents[0]
        self.assertEqual(user["status"], "permanently_deleted")
        self.assertEqual(user["permanent_deletion_id"], deletion_id)
        self.assertNotEqual(user["email"], original_email)
        self.assertTrue(resumed["resumed"])
        self.assertEqual(resumed["deletion_receipt"]["deletion_id"], deletion_id)
        self.assertEqual(tombstone["status"], "completed")
        self.assertTrue(tombstone["audit_event_created"])
        self.assertEqual(write_audit.call_count, 2)
        cancel_subscription.assert_not_called()

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

    def test_non_ceo_identity_cannot_be_promoted_to_super_admin(self):
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
            with self.assertRaisesRegex(ValueError, "Wildcard administrator roles"):
                admin_control_service.super_admin_update_user(
                    user_id=str(user_id),
                    payload={"role": "super_admin"},
                    actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com"},
                )
        self.assertEqual(db["users"].documents[0]["role"], "operations_admin")

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
            with self.assertRaisesRegex(ValueError, "Wildcard administrator roles"):
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
                "Wildcard administrator roles can only be assigned to Larry Robinson's canonical identity",
            ):
                admin_control_service.super_admin_update_user(
                    user_id=str(user_id),
                    payload={"role": "ceo_master_admin"},
                    actor={"_id": ObjectId(), "email": "ceo@tomboflight.com"},
                )

    def test_canonical_ceo_identity_and_master_roles_are_immutable(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "l.robinson@tomboflight.com",
                        "full_name": "Larry Robinson",
                        "role": "ceo_master_admin",
                        "access_tier": "ceo_master_admin",
                        "department_role": "executive_tech_admin",
                        "status": "active",
                    }
                ]
            }
        )
        with patch.object(admin_control_service, "get_database", return_value=db):
            for field, value in (
                ("email", "attacker@example.com"),
                ("status", "suspended"),
                ("role", "user"),
                ("access_tier", "operations_admin"),
                ("department_role", "finance_admin"),
            ):
                with self.subTest(field=field):
                    with self.assertRaisesRegex(ValueError, "immutable"):
                        admin_control_service.super_admin_update_user(
                            user_id=str(user_id),
                            payload={field: value},
                            actor={
                                "_id": user_id,
                                "email": "l.robinson@tomboflight.com",
                            },
                        )

        user = db["users"].documents[0]
        self.assertEqual(user["email"], "l.robinson@tomboflight.com")
        self.assertEqual(user["status"], "active")
        self.assertEqual(user["role"], "ceo_master_admin")

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
                reason="CEO-authorized controlled test assignment",
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
                    {
                        "_id": ObjectId(),
                        "email": "deleted-fixture@deleted.tomboflight.invalid",
                        "account_type": "deleted_tombstone",
                        "status": "permanently_deleted",
                    },
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
        self.assertEqual(summary["permanently_deleted_users"], 1)
        self.assertEqual(summary["user_identity_records_retained"], 4)
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

    def test_overview_normalizes_mixed_datetimes_and_does_not_write_metrics(self):
        month_start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        before_month = month_start - timedelta(seconds=1)
        naive_month_boundary = datetime(2026, 7, 1, 0, 0, 0)
        aware_month_boundary = datetime(2026, 6, 30, 20, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
        z_boundary = "2026-07-01T00:00:00Z"
        offset_boundary = "2026-07-01T02:00:00+02:00"
        malformed_value = "not-a-timestamp"

        project_id = ObjectId()
        second_project_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {"_id": ObjectId(), "email": "admin@example.com", "account_type": "business_admin"},
                    {"_id": ObjectId(), "email": "customer@example.com", "account_type": "customer"},
                ],
                "projects": [
                    {
                        "_id": project_id,
                        "owner_email": "customer@example.com",
                        "name": "Boundary Project",
                        "package_code": "legacy_snapshot",
                        "project_lane": "portrait",
                        "status": "build_ready",
                        "phase": "intake_approved",
                        "created_at": naive_month_boundary,
                        "updated_at": aware_month_boundary,
                    },
                    {
                        "_id": second_project_id,
                        "owner_email": "customer@example.com",
                        "name": "Prior Project",
                        "package_code": "legacy_plus",
                        "project_lane": "household",
                        "status": "archived",
                        "phase": "intake_approved",
                        "created_at": before_month,
                        "updated_at": before_month,
                    },
                ],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 10,
                        "created_at": naive_month_boundary,
                    },
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 20,
                        "created_at": aware_month_boundary,
                    },
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 30,
                        "created_at": z_boundary,
                    },
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 40,
                        "created_at": offset_boundary,
                    },
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 50,
                        "created_at": before_month,
                    },
                    {
                        "_id": ObjectId(),
                        "email": "customer@example.com",
                        "project_id": project_id,
                        "status": "paid",
                        "item_type": "package",
                        "package_code": "legacy_snapshot",
                        "amount": 60,
                        "created_at": malformed_value,
                    },
                ],
                "project_entitlements": [
                    {"_id": ObjectId(), "project_id": project_id, "status": "active"}
                ],
                "audit_logs": [],
                "payroll_runs": [],
                "finance_events": [],
                "uploaded_files": [{"_id": ObjectId(), "project_id": project_id, "status": "received"}],
                "verification_records": [],
                "household_invites": [],
                "project_members": [],
            }
        )
        before_finance_docs = list(db["finance_events"].documents)
        readiness_map = {
            str(project_id): {
                "mint_review_ready": True,
                "mint_eligible": True,
                "mint_already_completed": False,
                "package_synced": True,
                "lane_assigned": True,
                "order_linked": True,
                "entitlement_exists": True,
                "summary": "ready",
                "blocking_reasons": [],
            },
            str(second_project_id): {
                "mint_review_ready": False,
                "mint_eligible": False,
                "mint_already_completed": False,
                "package_synced": False,
                "lane_assigned": False,
                "order_linked": False,
                "entitlement_exists": False,
                "summary": "blocked",
                "blocking_reasons": ["missing_entitlement"],
            },
        }

        def _fake_readiness_check(*, project_id, order_id=""):
            del order_id
            return readiness_map[project_id]

        with (
            patch.object(admin_control_service, "get_database", return_value=db),
            patch.object(admin_control_service, "_now", return_value=datetime(2026, 7, 15, tzinfo=timezone.utc)),
            patch.object(admin_control_service, "run_readiness_check", side_effect=_fake_readiness_check),
            patch.object(admin_control_service, "get_project_entitlement", return_value=None),
            patch.object(admin_control_service, "count_workspace_uploads", return_value=1),
        ):
            payload = admin_control_service.admin_console_overview(limit=24)

        summary = payload["summary"]
        self.assertEqual(summary["total_users"], 2)
        self.assertEqual(summary["total_active_projects"], 1)
        self.assertEqual(summary["paid_orders"], 6)
        self.assertEqual(summary["missing_entitlements"], 1)
        self.assertEqual(summary["mint_ready_projects"], 1)
        self.assertEqual(summary["projects_with_data_mismatch"], 1)
        self.assertEqual(summary["collected_month"], 100.0)
        self.assertEqual(db["finance_events"].documents, before_finance_docs)

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

    def test_overview_does_not_backfill_typed_finance_events(self):
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
        self.assertEqual(db["finance_events"].documents, [])


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
                role_assignments=["operations_admin"],
                grant_permissions=["admin.audit.read"],
            )
            applied = admin_control_service.super_admin_apply_officer_permissions(
                officer_email="jenn.wood@tomboflight.com",
                role_assignments=["operations_admin"],
                grant_permissions=["admin.audit.read"],
                actor={"_id": ObjectId(), "email": "l.robinson@tomboflight.com", "role": "ceo_master_admin"},
            )
            with self.assertRaisesRegex(ValueError, "job-scoped officer role"):
                admin_control_service.super_admin_preview_officer_permissions(
                    officer_email="jenn.wood@tomboflight.com",
                    role_assignments=["ceo_master_admin"],
                )
        self.assertTrue(officers["items"])
        self.assertTrue(officers["ceo_identity"]["immutable"])
        self.assertEqual(officers["ceo_identity"]["role_code"], "ceo_master_admin")
        self.assertNotIn("ceo_master_admin", officers["role_templates"])
        self.assertEqual(
            officers["role_templates"]["finance_admin"]["allowed_queues"],
            admin_control_service.FINANCE_QUEUE_ALLOWLIST,
        )
        self.assertEqual(
            officers["role_templates"]["operations_admin"]["allowed_queues"],
            admin_control_service.OPERATIONS_QUEUE_ALLOWLIST,
        )
        self.assertIn("admin.audit.read", preview["proposed_after"]["permission_overrides"])
        self.assertIn("admin.audit.read", applied["after"]["permission_overrides"])
        self.assertTrue(db["user_permission_overrides"].documents)
        updated_user = db["users"].find_one({"_id": jenn_id}) or {}
        self.assertEqual(updated_user.get("access_tier"), "operations_admin")
        self.assertEqual(updated_user.get("department_role"), "operations_admin")
        self.assertEqual(updated_user.get("managed_role_code"), "operations_admin")
        active_roles = sorted(
            item.get("role_code")
            for item in db["user_role_assignments"].documents
            if item.get("status") == "active"
        )
        self.assertEqual(active_roles, ["operations_admin"])

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
