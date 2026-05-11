import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId

from app.core.package_catalog import get_package
from app.core.package_mapping import resolve_package_identity
from app.services import billing_service, workspace_access_service
from app.services.entitlement_service import resolve_project_entitlements


REPO_ROOT = Path(__file__).resolve().parents[2]


def _extract_package_profile_block(source: str, package_code: str) -> str:
    match = re.search(
        rf"{re.escape(package_code)}:\s*\{{(?P<body>.*?)\n\s*\}},",
        source,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"Missing PACKAGE_PROFILES block for {package_code}")
    return match.group("body")


def _extract_bool(block: str, key: str) -> bool:
    match = re.search(rf"{re.escape(key)}:\s*(true|false)", block)
    if not match:
        raise AssertionError(f"Missing {key} in profile block")
    return match.group(1) == "true"


def _extract_text(block: str, key: str) -> str:
    match = re.search(rf'{re.escape(key)}:\s*"([^"]+)"', block)
    if not match:
        raise AssertionError(f"Missing {key} in profile block")
    return match.group(1).strip()


class _FakeCursor(list):
    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, amount):
        return _FakeCursor(self[:amount])


class _FakeCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    def _matches(self, document, query):
        if "$or" in query:
            return any(self._matches(document, entry) for entry in query["$or"])
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                if document.get(key) not in value["$in"]:
                    return False
            elif document.get(key) != value:
                return False
        return True

    def find(self, query):
        return _FakeCursor([doc for doc in self.documents if self._matches(doc, query)])

    def find_one(self, query, sort=None):  # noqa: ARG002
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc is None:
            return
        for key, value in (update.get("$set") or {}).items():
            doc[key] = value

    def insert_one(self, doc):
        entry = dict(doc)
        entry["_id"] = entry.get("_id") or f"ent-{len(self.documents) + 1}"
        self.documents.append(entry)
        return SimpleNamespace(inserted_id=entry["_id"])


class PR465BackendPortalAuditTests(unittest.TestCase):
    def test_frontend_backend_package_profile_parity(self):
        app_source = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
        package_codes = [
            "legacy_snapshot",
            "legacy_portrait_intro",
            "digital_legacy_portrait",
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
            "command_structure_network",
        ]
        parity_flags = [
            "can_build_household",
            "can_build_family_tree",
            "can_upload_portraits",
            "can_upload_verification_docs",
            "can_use_viewer",
            "can_use_narration",
            "can_use_lineage_certificate",
            "can_open_family_intake",
            "can_open_org_intake",
            "can_use_link_keys",
            "can_manage_link_keys",
        ]

        for code in package_codes:
            with self.subTest(package_code=code):
                block = _extract_package_profile_block(app_source, code)
                frontend_lane = _extract_text(block, "package_lane")
                backend_package = get_package(code)
                self.assertIsNotNone(backend_package)
                assert backend_package is not None

                self.assertEqual(frontend_lane, str(backend_package.get("package_lane")))
                for flag in parity_flags:
                    self.assertEqual(
                        _extract_bool(block, flag),
                        bool(backend_package.get(flag)),
                        f"Drift on {code}.{flag}",
                    )

        legacy_snapshot_block = _extract_package_profile_block(app_source, "legacy_snapshot")
        legacy_plus_block = _extract_package_profile_block(app_source, "legacy_plus")
        self.assertFalse(_extract_bool(legacy_snapshot_block, "can_use_link_keys"))
        self.assertFalse(_extract_bool(legacy_snapshot_block, "can_manage_link_keys"))
        self.assertTrue(_extract_bool(legacy_plus_block, "can_use_link_keys"))
        self.assertTrue(_extract_bool(legacy_plus_block, "can_manage_link_keys"))

    def test_larry_legacy_plus_workspace_context_snapshot(self):
        current_user = {
            "id": "larry-user-id",
            "email": "larrycr27@gmail.com",
            "role": "customer",
        }
        project_id = "69c0402387082765345cff8c"
        family_id = "69bf98b54c5cb5a4236446dd"
        household_id = "69c0402387082765345cff8b"
        resolved = resolve_project_entitlements("legacy_plus", [])
        paid_order = {
            "project_id": project_id,
            "package_code": "legacy_plus",
            "package_slug": "legacy-plus",
            "package_name": "Legacy Plus",
            "package_lane": "household",
            "status": "paid",
        }
        with (
            patch.object(workspace_access_service, "_latest_ready_intake_for_user", return_value={"household_id": household_id}),
            patch.object(
                workspace_access_service,
                "_get_paid_package_order_for_user",
                return_value=paid_order,
            ),
            patch.object(
                workspace_access_service,
                "_resolve_active_project_for_user",
                return_value={
                    "_id": project_id,
                    "family_id": family_id,
                    "household_id": household_id,
                    "project_lane": "household",
                },
            ),
            patch.object(
                workspace_access_service,
                "_resolve_active_family_for_workspace",
                return_value={"_id": family_id, "project_id": project_id},
            ),
            patch.object(
                workspace_access_service,
                "get_project_access_snapshot",
                return_value={"accessible": True, "member_role": "billing_owner", "via": ""},
            ),
            patch.object(
                workspace_access_service,
                "_get_paid_package_order_for_project",
                return_value=paid_order,
            ),
            patch.object(
                workspace_access_service,
                "_resolve_project_entitlement_map",
                return_value={
                    "package_code": "legacy_plus",
                    "active_addons": [],
                    "resolved_entitlements": resolved,
                    "entitlement": {"status": "active"},
                    "paid_order": paid_order,
                },
            ),
            patch.object(workspace_access_service, "_billing_blocking_reason", return_value=None),
        ):
            payload = workspace_access_service.build_workspace_context_snapshot(current_user)

        self.assertEqual(payload["status"], "active")
        self.assertIsNone(payload["blocking_reason"])
        self.assertEqual(payload["user"]["email"], "larrycr27@gmail.com")
        self.assertEqual(payload["user"]["role"], "customer")
        self.assertEqual(payload["workspace"]["project_id"], project_id)
        self.assertEqual(payload["workspace"]["family_id"], family_id)
        self.assertEqual(payload["workspace"]["household_id"], household_id)
        self.assertEqual(payload["workspace"]["lane"], "household")
        self.assertEqual(payload["package"]["code"], "legacy_plus")
        self.assertEqual(payload["package"]["display_name"], "Legacy Plus")
        self.assertEqual(payload["package"]["lane"], "household")
        self.assertEqual(payload["package"]["status"], "paid")
        self.assertTrue(payload["entitlements"]["can_build_household"])
        self.assertTrue(payload["entitlements"]["can_build_family_tree"])
        self.assertTrue(payload["entitlements"]["can_upload_portraits"])
        self.assertTrue(payload["entitlements"]["can_upload_verification_docs"])
        self.assertTrue(payload["entitlements"]["can_use_viewer"])
        self.assertTrue(payload["entitlements"]["can_use_narration"])
        self.assertTrue(payload["entitlements"]["can_use_lineage_certificate"])
        self.assertTrue(payload["entitlements"]["can_open_family_intake"])
        self.assertTrue(payload["entitlements"]["can_use_link_keys"])
        self.assertTrue(payload["entitlements"]["can_manage_link_keys"])
        self.assertEqual(payload["entitlements"]["max_members"], 30)
        self.assertEqual(payload["entitlements"]["max_uploads"], 100)
        self.assertEqual(payload["entitlements"]["max_storage_gb"], 25)
        self.assertEqual(payload["entitlements"]["max_zoom_layers"], 5)
        self.assertEqual(payload["membership"]["member_role"], "billing_owner")
        self.assertEqual(payload["membership"]["access_via"], "owner_fallback_or_project_member")

    def test_workspace_context_blocks_foreign_project_id(self):
        foreign_project_id = "69c0402387082765345cffff"
        with (
            patch.object(
                workspace_access_service,
                "_latest_ready_intake_for_user",
                return_value=None,
            ),
            patch.object(
                workspace_access_service,
                "_get_paid_package_order_for_user",
                return_value={"project_id": foreign_project_id},
            ),
            patch.object(
                workspace_access_service,
                "_resolve_active_project_for_user",
                return_value={"_id": foreign_project_id},
            ),
            patch.object(
                workspace_access_service,
                "_resolve_active_family_for_workspace",
                return_value=None,
            ),
            patch.object(
                workspace_access_service,
                "get_project_access_snapshot",
                return_value={"accessible": False},
            ),
            patch.object(workspace_access_service, "_resolve_project_entitlement_map") as entitlement_map_mock,
            patch.object(workspace_access_service, "repair_workspace_entitlements_for_user") as repair_mock,
        ):
            payload = workspace_access_service.build_workspace_context_snapshot(
                {"id": "user-a", "email": "a@example.com", "role": "customer"},
                project_id=foreign_project_id,
            )

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["blocking_reason"], "account_not_associated_with_project")
        entitlement_map_mock.assert_not_called()
        repair_mock.assert_not_called()

    def test_entitlement_repair_idempotent(self):
        project_id = "69c0402387082765345cff8c"
        email = "larrycr27@gmail.com"
        orders = _FakeCollection(
            [
                {
                    "_id": "order-1",
                    "owner_email": email,
                    "email": email,
                    "project_id": project_id,
                    "package_code": "legacy_plus",
                    "package_slug": "legacy-plus",
                    "package_lane": "household",
                    "status": "paid",
                    "item_type": "package",
                    "created_at": "2026-05-10T00:00:00Z",
                }
            ]
        )
        projects = _FakeCollection([{"_id": ObjectId(project_id), "owner_email": email}])
        entitlements = _FakeCollection([])
        fake_db = {
            "orders": orders,
            "projects": projects,
            "project_entitlements": entitlements,
        }

        def fake_identity(value):
            identity = resolve_package_identity(value)
            return {
                "package_code": identity.get("package_code"),
                "package_lane": identity.get("package_lane") or identity.get("lane"),
            }

        with (
            patch.object(workspace_access_service, "_require_database", return_value=fake_db),
            patch.object(workspace_access_service, "_find_project_by_id", return_value=projects.documents[0]),
            patch.object(workspace_access_service, "_get_paid_package_order_for_project", return_value=orders.documents[0]),
            patch.object(workspace_access_service, "resolve_package_identity", side_effect=fake_identity),
            patch.object(workspace_access_service, "create_audit_log") as audit_mock,
        ):
            first = workspace_access_service.repair_workspace_entitlements_for_user(
                email,
                project_id=project_id,
                dry_run=False,
            )
            second = workspace_access_service.repair_workspace_entitlements_for_user(
                email,
                project_id=project_id,
                dry_run=False,
            )

        self.assertEqual(len(first["repaired"]), 1)
        self.assertEqual(len(second["repaired"]), 1)
        self.assertEqual(len(entitlements.documents), 1)
        self.assertGreaterEqual(audit_mock.call_count, 1)

    def test_workspace_context_objectid_string_compatibility(self):
        project_id = "69c0402387082765345cff8c"
        family_id = "69bf98b54c5cb5a4236446dd"
        project_oid = ObjectId(project_id)
        family_oid = ObjectId(family_id)
        projects = _FakeCollection([{"_id": project_oid, "family_id": family_id}])
        families = _FakeCollection([{"_id": family_oid, "project_id": project_oid}])
        fake_db = {"projects": projects, "families": families}
        with patch.object(workspace_access_service, "_require_database", return_value=fake_db):
            resolved_project = workspace_access_service._find_project_by_id(project_id)
            resolved_family = workspace_access_service._find_family_for_project({"_id": project_id})
        self.assertIsNotNone(resolved_project)
        self.assertIsNotNone(resolved_family)
        assert resolved_family is not None
        self.assertEqual(str(resolved_family.get("_id")), family_id)

    def test_private_portal_links(self):
        dashboard = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        dashboard_js = (REPO_ROOT / "dashboard-intake.js").read_text(encoding="utf-8")
        self.assertIn('href="portal-help.html" data-dashboard-tool="help_center"', dashboard)
        self.assertIn('href="portal-review.html" data-portal-review-link', dashboard)
        self.assertIn(
            'href="portal-upgrade.html?target_package=family_estate_concierge"',
            dashboard,
        )
        self.assertIn("withFamilyId(\"portal-help.html\", context)", dashboard_js)
        self.assertIn("withFamilyId(\"portal-review.html\", context)", dashboard_js)
        self.assertIn(
            '"portal-upgrade.html?target_package=family_estate_concierge"',
            dashboard_js,
        )
        self.assertTrue((REPO_ROOT / "portal-help.html").exists())
        self.assertTrue((REPO_ROOT / "portal-review.html").exists())
        self.assertTrue((REPO_ROOT / "portal-upgrade.html").exists())
        self.assertNotIn('href="faq.html"', dashboard)
        self.assertNotIn("how-it-works.html", dashboard)
        self.assertNotIn("index.html#pricing", dashboard)

    def test_billing_empty_states(self):
        with (
            patch.object(billing_service, "_require_stripe_secret_key", return_value="key"),
            patch.object(billing_service, "_get_user_document", return_value={"_id": "user-1"}),
        ):
            overview = billing_service.get_billing_overview({"id": "user-1"})
        self.assertEqual(overview.get("error_code"), "billing_profile_missing")
        self.assertEqual(overview.get("payment_methods"), [])
        self.assertEqual(overview.get("subscriptions"), [])

        billing_js = (REPO_ROOT / "billing.js").read_text(encoding="utf-8")
        self.assertIn("No saved cards are on file yet.", billing_js)
        self.assertIn("No active or historical subscriptions found.", billing_js)
        self.assertIn("Billing profile has not been created yet.", billing_js)
        self.assertIn("Billing portal is not configured yet.", billing_js)
        self.assertIn("billing_profile_missing", billing_js)
        self.assertIn("stripe_portal_not_configured", billing_js)

        with patch.object(
            billing_service.settings,
            "stripe_billing_portal_configuration_id",
            "",
        ):
            with self.assertRaisesRegex(ValueError, "stripe_portal_not_configured"):
                billing_service.create_billing_portal_session_for_user({"id": "user-1"})

    def test_setup_intent_creates_customer_when_missing(self):
        with (
            patch.object(billing_service, "_require_stripe_secret_key", return_value="key"),
            patch.object(
                billing_service,
                "_ensure_stripe_customer_for_user",
                return_value={"id": "cus_123"},
            ) as ensure_customer_mock,
            patch.object(
                billing_service,
                "_list_payment_methods",
                return_value=[],
            ),
            patch.object(
                billing_service.stripe.SetupIntent,
                "create",
                return_value={"client_secret": "seti_secret"},
            ) as create_setup_mock,
        ):
            payload = billing_service.create_setup_intent_for_user({"id": "user-1"})
        self.assertEqual(payload["customer_id"], "cus_123")
        ensure_customer_mock.assert_called_once()
        create_setup_mock.assert_called_once()

    def test_moreland_homepage_full_preview(self):
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        required_names = [
            "Clara Moreland",
            "Elias Moreland",
            "Julian Moreland",
            "Malik Moreland",
            "Naomi Moreland",
            "Selah Carter",
            "Andre Carter",
            "Eli Moreland",
            "Imani Moreland / Imani Benton",
            "Marcus Benton",
            "Zara Benton",
            "Camille Carter",
            "Micah Benton",
        ]
        for name in required_names:
            with self.subTest(name=name):
                self.assertIn(name, homepage)
        self.assertIn("Family Estate Concierge", homepage)
        self.assertIn("Network Lane demonstration", homepage)
        self.assertIn("Family Keys connect households", homepage)
        self.assertIn("separate privacy, permissions, records, and consent", homepage)
        self.assertNotIn("larrycr27@gmail.com", homepage.lower())

    def test_moreland_viewer_demo_public(self):
        homepage = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        viewer_html = (REPO_ROOT / "viewer/index.html").read_text(encoding="utf-8")
        viewer_script = (REPO_ROOT / "viewer/js/script.js").read_text(encoding="utf-8")
        manifest = (REPO_ROOT / "viewer/js/genesis-prototype-manifest.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('href="/viewer/?demo=malik-moreland"', homepage)
        self.assertIn("DEFAULT_PUBLIC_DEMO_KEY = \"malik-moreland\"", viewer_script)
        self.assertIn("if (DEMO_MODE)", viewer_script)
        self.assertIn("resolvePublicDemoManifest(DEMO_KEY)", viewer_script)
        self.assertIn("if (!app.getToken || !app.getToken()) return null;", viewer_script)
        self.assertIn("Demo Data", manifest)
        self.assertIn("Private viewer locked", viewer_html)
        self.assertNotIn("Private viewer locked", manifest)


if __name__ == "__main__":
    unittest.main()
