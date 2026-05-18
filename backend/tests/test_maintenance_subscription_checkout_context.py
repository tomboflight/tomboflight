import unittest
from pathlib import Path

from app.services import maintenance_subscription_service

REPO_ROOT = Path(__file__).resolve().parents[2]


class MaintenanceSubscriptionCheckoutContextTests(unittest.TestCase):
    def test_metadata_project_id_reads_client_reference_context(self):
        payload = {
            "client_reference_id": "tol:v=1&u=user-1&p=project-ctx-1&k=legacy_plus&t=maintenance&b=monthly&c=LIGHT_NEVER_DIES"
        }
        self.assertEqual(
            maintenance_subscription_service._metadata_project_id(payload),
            "project-ctx-1",
        )

    def test_maintenance_subscription_service_keeps_single_checkout_context_parser(self):
        source = (
            REPO_ROOT / "backend" / "app" / "services" / "maintenance_subscription_service.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(source.count("def _metadata_project_id("), 1)


if __name__ == "__main__":
    unittest.main()
