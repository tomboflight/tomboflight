import unittest

from app.services import maintenance_subscription_service


class MaintenanceSubscriptionCheckoutContextTests(unittest.TestCase):
    def test_metadata_project_id_reads_client_reference_context(self):
        payload = {
            "client_reference_id": "tol:v=1&u=user-1&p=project-ctx-1&k=legacy_plus&t=maintenance&b=monthly&c=LIGHT_NEVER_DIES"
        }
        self.assertEqual(
            maintenance_subscription_service._metadata_project_id(payload),
            "project-ctx-1",
        )


if __name__ == "__main__":
    unittest.main()
