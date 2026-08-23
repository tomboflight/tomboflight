import base64
import hashlib
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PATH = REPO_ROOT / "backend" / "app" / "services" / "continuity_runtime_service.py"
AUTH_PATH = REPO_ROOT / "backend" / "app" / "services" / "auth_service.py"
DEPENDENCY_PATH = REPO_ROOT / "backend" / "app" / "dependencies" / "auth.py"
CONTROL_JS_PATH = REPO_ROOT / "admin-control-center.js"
APP_JS_PATH = REPO_ROOT / "app.js"
AUTH_JS_PATH = REPO_ROOT / "auth.js"


class TestContinuityKernelPhase9ControlSurfaceSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        cls.auth = AUTH_PATH.read_text(encoding="utf-8")
        cls.dependencies = DEPENDENCY_PATH.read_text(encoding="utf-8")
        cls.control_js = CONTROL_JS_PATH.read_text(encoding="utf-8")
        cls.app_js = APP_JS_PATH.read_text(encoding="utf-8")
        cls.auth_js = AUTH_JS_PATH.read_text(encoding="utf-8")

    def test_01_runtime_registers_complete_control_surface_actions(self) -> None:
        self.assertIn('RUNTIME_VERSION = "11.0.0"', self.runtime)
        for action in (
            "manual_fulfillment",
            "stripe_operation",
            "customer_account_create",
            "user_profile_update",
            "user_password_reset",
            "project_ownership_transfer",
            "impersonation_start",
            "impersonation_stop",
        ):
            self.assertIn(f'"{action}": ActionSpec(', self.runtime)

    def test_02_control_center_has_no_direct_business_write_endpoints(self) -> None:
        for forbidden in (
            "/fulfillment/orders/${",
            "/admin/stripe-ops/customers/ensure",
            "/admin/stripe-ops/payment-links",
            "/admin/stripe-ops/invoices",
            "/admin/stripe-ops/subscriptions",
            "/admin/stripe-ops/payment-method-update-link",
            "/super-admin/users/${encodeURIComponent(userId)}`",
            "/transfer-ownership`,",
            "/super-admin/impersonation/start",
            "data-admin-impersonation-enable-editing",
            "Enable Admin Editing",
        ):
            self.assertNotIn(forbidden, self.control_js)
        self.assertIn("submitGovernedOperation", self.control_js)

    def test_03_authentication_fails_closed_and_mfa_is_account_opt_in(self) -> None:
        self.assertNotIn('"status": "authenticated", "access_token": token', self.auth)
        self.assertNotIn("_requires_internal_admin_mfa", self.auth)
        self.assertNotIn("mfa_enrollment_required", self.auth)
        self.assertNotIn("MFA enrollment is required for internal administrator accounts", self.dependencies)
        self.assertIn('if bool(normalized_user.get("mfa_enabled")):', self.dependencies)
        self.assertIn("MFA verification is required for this session", self.dependencies)

    def test_04_bearer_and_user_context_are_tab_scoped(self) -> None:
        self.assertIn("sessionStorage.setItem(TOKEN_KEY, token)", self.app_js)
        self.assertIn("sessionStorage.setItem(USER_KEY", self.app_js)
        self.assertNotIn("localStorage.setItem(TOKEN_KEY, token)", self.app_js)
        self.assertNotIn("localStorage.setItem(USER_KEY", self.app_js)

    def test_05_sensitive_surfaces_ship_a_restrictive_csp(self) -> None:
        for relative_path in (
            "signin.html",
            "dashboard.html",
            "admin-control-center.html",
            "account-security.html",
            "vault-upload.html",
            "verification-upload.html",
        ):
            source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn('http-equiv="Content-Security-Policy"', source)
            self.assertIn("object-src 'none'", source)
            self.assertIn("script-src 'self'", source)

    def test_06_every_control_center_button_is_referenced_by_a_loaded_script(self) -> None:
        html = (REPO_ROOT / "admin-control-center.html").read_text(encoding="utf-8")
        combined_scripts = self.control_js + "\n" + self.app_js + "\n" + self.auth_js
        button_sources = html + "\n" + self.control_js
        buttons = re.findall(r"<button\b[^>]*>", button_sources, flags=re.IGNORECASE | re.DOTALL)
        self.assertGreaterEqual(len(buttons), 30)
        for button in buttons:
            attributes = re.findall(r"\b(data-[\w-]+)(?:=|\s|>)", button)
            if attributes:
                self.assertTrue(
                    any(attribute in combined_scripts for attribute in attributes),
                    f"Control button has no script reference: {button[:160]}",
                )
            else:
                self.assertIn("menu-toggle", button)
                self.assertIn(".menu-toggle", combined_scripts)

    def test_07_app_pages_have_csp_valid_inline_hashes_and_current_cache_revision(self) -> None:
        app_pages = []
        separately_managed_commercial_pages = {
            "bridge-paint.html",
            "bridge-taste.html",
            "pricing.html",
        }
        for path in sorted(REPO_ROOT.glob("*.html")):
            source = path.read_text(encoding="utf-8")
            if "app.js?v=" not in source:
                continue
            if path.name in separately_managed_commercial_pages:
                continue
            app_pages.append(path.name)
            expected_revision = "20260821-phase10-1" if path.name == "admin-control-center.html" else "20260821-phase9"
            self.assertIn(f"app.js?v={expected_revision}", source, path.name)
            csp_match = re.search(
                r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"',
                source,
            )
            self.assertIsNotNone(csp_match, path.name)
            csp = csp_match.group(1) if csp_match else ""
            script_src = re.search(r"script-src\s+([^;]+)", csp)
            self.assertIsNotNone(script_src, path.name)
            self.assertNotIn("'unsafe-inline'", script_src.group(1) if script_src else "")
            inline_scripts = re.findall(
                r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                source,
                flags=re.IGNORECASE | re.DOTALL,
            )
            for inline_script in inline_scripts:
                digest = base64.b64encode(
                    hashlib.sha256(inline_script.encode("utf-8")).digest()
                ).decode("ascii")
                self.assertIn(f"'sha256-{digest}'", csp, path.name)
        self.assertGreaterEqual(len(app_pages), 49)

    def test_08_fail_closed_upload_defaults_are_aligned_with_deployment_example(self) -> None:
        config = (REPO_ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
        env_example = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
        self.assertIn("upload_scan_fail_closed: bool", config)
        self.assertIn("default=True", config)
        self.assertIn('UPLOAD_SCAN_FAIL_CLOSED="true"', env_example)


if __name__ == "__main__":
    unittest.main()
