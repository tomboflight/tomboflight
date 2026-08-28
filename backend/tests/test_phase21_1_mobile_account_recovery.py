from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.services import auth_service


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REVISION = "20260828-phase21-1"


class _Users:
    def __init__(self, user):
        self.user = user

    def find_one(self, query):
        del query
        return self.user


class Phase211AccountRecoveryTests(TestCase):
    def _database(self, user):
        return SimpleNamespace(users=_Users(user))

    def test_pending_identity_receives_activation_without_public_state_disclosure(self):
        activation_delivery = {
            "success": True,
            "delivery_sent": True,
            "delivery_provider": "postmark",
        }
        with (
            patch.object(
                auth_service,
                "_get_database_or_none",
                return_value=self._database(
                    {
                        "email": "pending@example.test",
                        "status": "pending_activation",
                        "account_type": "customer",
                    }
                ),
            ),
            patch.object(
                auth_service,
                "request_account_activation",
                return_value=activation_delivery,
            ) as activation,
            patch.object(auth_service, "request_password_reset") as password_reset,
        ):
            public_result = auth_service.request_account_recovery(
                "Pending@Example.Test"
            )

        activation.assert_called_once_with(
            "pending@example.test",
            include_delivery_status=False,
        )
        password_reset.assert_not_called()
        self.assertEqual(
            public_result,
            {
                "success": True,
                "message": (
                    "If this email is connected to an account, the appropriate "
                    "secure access link has been sent."
                ),
                "delivery_mode": "email",
            },
        )

    def test_active_identity_receives_password_reset(self):
        reset_delivery = {
            "success": True,
            "delivery_sent": True,
            "delivery_provider": "postmark",
        }
        with (
            patch.object(
                auth_service,
                "_get_database_or_none",
                return_value=self._database(
                    {
                        "email": "active@example.test",
                        "status": "active",
                        "account_type": "customer",
                    }
                ),
            ),
            patch.object(auth_service, "request_account_activation") as activation,
            patch.object(
                auth_service,
                "request_password_reset",
                return_value=reset_delivery,
            ) as password_reset,
        ):
            result = auth_service.request_account_recovery(
                "active@example.test",
                include_delivery_status=True,
            )

        activation.assert_not_called()
        password_reset.assert_called_once_with(
            "active@example.test",
            include_delivery_status=True,
        )
        self.assertEqual(result["recovery_mode"], "password_reset")
        self.assertTrue(result["delivery_sent"])

    def test_unknown_suspended_and_deleted_identities_do_not_receive_credentials(self):
        identities = [
            None,
            {
                "email": "suspended@example.test",
                "status": "disabled",
                "account_type": "customer",
            },
            {
                "email": "deleted@example.test",
                "status": "permanently_deleted",
                "account_type": "deleted_tombstone",
            },
        ]
        public_messages = []
        for identity in identities:
            with (
                self.subTest(identity=identity),
                patch.object(
                    auth_service,
                    "_get_database_or_none",
                    return_value=self._database(identity),
                ),
                patch.object(auth_service, "request_account_activation") as activation,
                patch.object(auth_service, "request_password_reset") as password_reset,
            ):
                result = auth_service.request_account_recovery(
                    "private@example.test"
                )
                activation.assert_not_called()
                password_reset.assert_not_called()
                public_messages.append(result)

        self.assertEqual(public_messages[0], public_messages[1])
        self.assertEqual(public_messages[1], public_messages[2])


class Phase211FrontendContractTests(TestCase):
    def test_customer_recovery_and_mobile_unlock_are_wired(self):
        auth_js = (REPOSITORY_ROOT / "auth.js").read_text(encoding="utf-8")
        security_js = (REPOSITORY_ROOT / "account-security.js").read_text(
            encoding="utf-8"
        )
        app_js = (REPOSITORY_ROOT / "app.js").read_text(encoding="utf-8")
        styles = (REPOSITORY_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn('"/auth/account-recovery/request"', auth_js)
        self.assertIn('"/auth/account-recovery/request"', security_js)
        self.assertIn('window.addEventListener("pageshow", closeMenu)', app_js)
        self.assertIn("if (window.innerWidth > 1180)", app_js)
        self.assertIn("API_DISCOVERY_TIMEOUT_MS = 15000", app_js)
        self.assertIn("No account change was completed", app_js)
        self.assertIn("body.menu-open .site-header", styles)
        self.assertIn("overflow-y: auto", styles)

    def test_every_shared_asset_reference_uses_the_phase21_1_revision(self):
        html_files = list(REPOSITORY_ROOT.glob("*.html"))
        html_files.extend((REPOSITORY_ROOT / "reviews").glob("*.html"))
        html_files.extend((REPOSITORY_ROOT / "viewer").glob("*.html"))

        stale = []
        for path in html_files:
            source = path.read_text(encoding="utf-8")
            for asset in ("styles.css", "config.js", "app.js", "auth.js"):
                marker = f"{asset}?v="
                if marker in source and f"{marker}{REVISION}" not in source:
                    stale.append(f"{path.relative_to(REPOSITORY_ROOT)}:{asset}")

        self.assertEqual(stale, [])
