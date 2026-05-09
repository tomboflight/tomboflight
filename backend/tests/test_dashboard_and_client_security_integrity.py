import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.routes import workspace_access
from app.services import household_access_service


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_CACHE_VERSION = "20260509-audit"
AUDITED_PORTAL_PAGES = [
    "dashboard.html",
    "upload-hub.html",
    "portrait-upload.html",
    "verification-upload.html",
    "vault-upload.html",
    "household-access.html",
    "link-keys.html",
    "tree-view.html",
    "lineage-certificate.html",
    "intake-review.html",
    "intake-uploads.html",
    "billing.html",
    "account-security.html",
    "digital-collectible.html",
]


class _FakeCursor(list):
    def sort(self, *_args, **_kwargs):
        return self


class _FakeMembersCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    def find(self, query):
        project_id = query.get("project_id")
        return _FakeCursor(
            [document for document in self.documents if document.get("project_id") == project_id]
        )


class CustomerDashboardIntegrityTests(unittest.TestCase):
    def test_customer_dashboard_has_single_package_access_block(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("data-package-access-panel"), 1)

    def test_customer_dashboard_has_single_legacy_anchor_panel(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("data-legacy-anchor-proof"), 1)

    def test_customer_dashboard_has_single_primary_action_row(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("data-workspace-action-bar"), 1)
        self.assertNotIn("portal-outputs-panel", source)

    def test_customer_dashboard_upload_center_and_next_step_are_present(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("Tomb of Light Continuity OS", source)
        self.assertIn("What To Do Next", source)
        self.assertIn("Upload Hub", source)
        self.assertIn("Upload Photos &amp; Family Records", source)
        self.assertIn("Upload Verification Documents", source)
        self.assertIn("View Intake", source)
        self.assertIn("Portrait / Family Photos", source)
        self.assertIn("Family Records / Documents", source)
        self.assertIn("Verification Documents", source)
        self.assertIn("Optional Narration / Story Materials", source)
        self.assertIn("Private Vault Files", source)
        self.assertIn("Lineage Certificate", source)
        self.assertIn("Members &amp; Access", source)
        self.assertIn("Billing &amp; Cards", source)
        self.assertIn("Account Security", source)
        self.assertIn("Help Center", source)

    def test_customer_dashboard_link_keys_follow_resolved_entitlements(self):
        source = (REPO_ROOT / "dashboard-intake.js").read_text(encoding="utf-8")
        self.assertIn("canUseLinkKeyTools", source)
        self.assertIn("can_manage_link_keys", source)
        self.assertNotIn('showLinkKeys: canUseLinkKeys || packageCode === "legacy_plus"', source)
        self.assertNotIn('navLinkKeys: canUseLinkKeys || packageCode === "legacy_plus"', source)

    def test_household_access_keeps_forbidden_workspace_errors_in_portal(self):
        source = (REPO_ROOT / "household-access.js").read_text(encoding="utf-8")
        self.assertIn("Members & Access is not included in your active package.", source)
        self.assertIn("No active workspace found. Return to Dashboard or contact support.", source)
        self.assertIn("Members & Access is unavailable for this workspace.", source)
        self.assertIn("isSessionInvalidError", source)
        self.assertIn('requestUrl.includes("/auth/me")', source)
        self.assertNotIn("statusCode === 401 || (statusCode === 403", source)
        self.assertRegex(source, r"if \(statusCode === 403\) \{[\s\S]{0,300}setLockedWorkspaceState")

    def test_shared_auth_does_not_classify_every_403_as_auth_failure(self):
        source = (REPO_ROOT / "auth.js").read_text(encoding="utf-8")
        is_auth_failure_body = source.split("function isAuthFailure(error)", 1)[1].split(
            "function sleep", 1
        )[0]
        self.assertIn("statusCode === 403 && isAuthEndpoint", is_auth_failure_body)
        self.assertNotIn('message.includes("forbidden")', is_auth_failure_body)
        self.assertNotIn('message.includes("403") ||', is_auth_failure_body)

    def test_audited_portal_pages_use_audit_css_and_auth_cache_versions(self):
        for page in AUDITED_PORTAL_PAGES:
            with self.subTest(page=page):
                source = (REPO_ROOT / page).read_text(encoding="utf-8")
                self.assertIn(f"styles.css?v={AUDIT_CACHE_VERSION}", source)
                self.assertIn(f"auth.js?v={AUDIT_CACHE_VERSION}", source)

    def test_changed_page_scripts_use_audit_cache_versions(self):
        expected_scripts = {
            "dashboard.html": "dashboard-intake.js",
            "household-access.html": "household-access.js",
            "link-keys.html": "link-keys.js",
            "portrait-upload.html": "portrait-upload.js",
            "verification-upload.html": "verification-upload.js",
            "vault-upload.html": "vault-upload.js",
            "tree-view.html": "tree-view.js",
            "lineage-certificate.html": "lineage-certificate.js",
        }
        for page, script in expected_scripts.items():
            with self.subTest(page=page):
                source = (REPO_ROOT / page).read_text(encoding="utf-8")
                self.assertIn(f"{script}?v={AUDIT_CACHE_VERSION}", source)

    def test_dashboard_members_access_link_points_to_household_access(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('href="household-access.html" data-dashboard-tool="household"', source)
        self.assertNotIn('href="#"', source)
        self.assertNotIn('javascript:void(0)', source)

    def test_customer_portal_has_no_false_included_or_admin_exposure(self):
        customer_sources = "\n".join(
            (REPO_ROOT / page).read_text(encoding="utf-8")
            for page in (
                "dashboard.html",
                "household-access.html",
                "link-keys.html",
                "portrait-upload.html",
                "verification-upload.html",
                "vault-upload.html",
                "tree-view.html",
                "lineage-certificate.html",
            )
        )
        self.assertNotIn(">Included<", customer_sources)
        self.assertNotIn("admin@tomboflight.com", customer_sources)
        self.assertNotIn("SUPERADMIN", customer_sources)
        self.assertNotIn("bulk repair", customer_sources)
        self.assertNotIn("entitlement repair", customer_sources)
        self.assertNotIn("admin-control", customer_sources)
        self.assertNotIn("mint queue", customer_sources)
        self.assertNotIn("repair record", customer_sources)

    def test_household_access_has_customer_nav_and_no_admin_controls(self):
        source = (REPO_ROOT / "household-access.html").read_text(encoding="utf-8")
        self.assertIn('href="dashboard.html">Dashboard</a>', source)
        self.assertIn('href="link-keys.html">Link Keys</a>', source)
        self.assertIn('data-logout-btn', source)
        self.assertNotIn("admin-control", source)
        self.assertNotIn("SUPERADMIN", source)

    def test_household_member_service_returns_only_active_members(self):
        documents = [
            {
                "_id": "member-owner",
                "project_id": "project-robinson",
                "email": "owner@example.com",
                "member_role": "billing_owner",
                "status": "active",
            },
            {
                "_id": "member-spouse",
                "project_id": "project-robinson",
                "email": "spouse@example.com",
                "member_role": "co_owner",
                "relationship_scope": "spouse",
                "status": "active",
            },
            {
                "_id": "member-revoked",
                "project_id": "project-robinson",
                "email": "former@example.com",
                "member_role": "viewer",
                "status": "revoked",
            },
        ]
        with (
            patch.object(household_access_service, "ensure_owner_membership"),
            patch.object(
                household_access_service,
                "_members",
                return_value=_FakeMembersCollection(documents),
            ),
        ):
            members = household_access_service.list_project_members("project-robinson")

        self.assertEqual([member["email"] for member in members], ["owner@example.com", "spouse@example.com"])
        self.assertEqual(members[1]["member_role"], "co_owner")

    def test_workspace_members_route_preserves_active_co_owner_without_user_id(self):
        member = {
            "_id": "member-spouse",
            "project_id": "project-robinson",
            "email": "spouse@example.com",
            "member_role": "co_owner",
            "relationship_scope": "spouse",
            "status": "active",
        }
        with (
            patch.object(workspace_access, "_assert_project_access"),
            patch.object(workspace_access, "_assert_household_management_enabled"),
            patch.object(workspace_access, "list_project_members", return_value=[member]),
            patch.object(workspace_access, "_with_member_identity_fields", side_effect=lambda items: items),
        ):
            payload = workspace_access.get_project_members(
                "project-robinson",
                current_user={"id": "owner-1", "email": "larrycr27@gmail.com"},
            )

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["member_role"], "co_owner")
        self.assertEqual(payload["items"][0]["status"], "active")
        self.assertEqual(payload["items"][0]["email"], "spouse@example.com")
        self.assertIsNone(payload["items"][0]["user_id"])

    def test_workspace_invites_route_keeps_pending_and_historical_invites_separate(self):
        invites = [
            {
                "_id": "invite-pending",
                "project_id": "project-robinson",
                "email": "pending@example.com",
                "member_role": "co_owner",
                "status": "pending",
            },
            {
                "_id": "invite-accepted",
                "project_id": "project-robinson",
                "email": "accepted@example.com",
                "member_role": "viewer",
                "status": "accepted",
            },
            {
                "_id": "invite-expired",
                "project_id": "project-robinson",
                "email": "expired@example.com",
                "member_role": "viewer",
                "status": "expired",
            },
            {
                "_id": "invite-revoked",
                "project_id": "project-robinson",
                "email": "revoked@example.com",
                "member_role": "viewer",
                "status": "revoked",
            },
        ]
        with (
            patch.object(workspace_access, "_assert_project_access"),
            patch.object(workspace_access, "_assert_household_management_enabled"),
            patch.object(workspace_access, "list_project_invites", return_value=invites),
        ):
            payload = workspace_access.get_project_invites(
                "project-robinson",
                current_user={"id": "owner-1", "email": "owner@example.com"},
            )

        statuses = {item["email"]: item["status"] for item in payload["items"]}
        self.assertEqual(statuses["pending@example.com"], "pending")
        self.assertEqual(statuses["accepted@example.com"], "accepted")
        self.assertEqual(statuses["expired@example.com"], "expired")
        self.assertEqual(statuses["revoked@example.com"], "revoked")

    def test_package_gated_household_access_is_forbidden_not_auth_failure(self):
        with patch.object(
            workspace_access,
            "resolve_workspace_context",
            return_value={"resolved_entitlements": {"can_build_household": False}},
        ):
            with self.assertRaises(HTTPException) as exc:
                workspace_access._assert_household_management_enabled(
                    "project-robinson",
                    {"id": "owner-1", "email": "owner@example.com"},
                )

        self.assertEqual(exc.exception.status_code, 403)
        self.assertIn("does not include household", exc.exception.detail)


class ClientPrivilegeElevationTests(unittest.TestCase):
    def test_admin_control_center_does_not_use_local_or_session_storage_for_permissions(self):
        source = (REPO_ROOT / "admin-control-center.js").read_text(encoding="utf-8")
        self.assertNotIn(".localStorage", source)
        self.assertNotIn(".sessionStorage", source)
        self.assertIn('"/admin/control-center/access-profile"', source)

    def test_thank_you_page_does_not_activate_entitlements_from_query_params(self):
        source = (REPO_ROOT / "thank-you.js").read_text(encoding="utf-8")
        self.assertIn("getParam(", source)
        self.assertNotIn("/project-entitlements", source)
        self.assertNotIn("/admin/control-center", source)
        self.assertNotIn("generate_entitlement", source)
        self.assertNotIn("upsert_project_entitlement", source)


if __name__ == "__main__":
    unittest.main()
