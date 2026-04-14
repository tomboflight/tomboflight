import unittest
from unittest.mock import patch

from app.routes import asset_delivery


class AssetDeliveryRouteTests(unittest.TestCase):
    def test_delivery_payload_uses_customer_wallet_fallback(self):
        current_user = {"id": "user-1", "email": "customer@example.com"}
        project = {
            "_id": "69c0402387082765345cff8c",
            "project_name": "Test Workspace",
            "created_at": "2026-04-14T00:00:00Z",
        }

        mint_status = {
            "mint_enabled": True,
            "current_status": "minted",
            "latest": {
                "customer_wallet": "0xabc123",
                "public_token_id": "tol-token-1",
            },
        }

        with (
            patch.object(asset_delivery, "_project_for_request", return_value=project),
            patch.object(asset_delivery, "get_project_entitlement", return_value={}),
            patch.object(asset_delivery, "_resolve_order_for_project", return_value={}),
            patch.object(asset_delivery, "build_mint_status", return_value=mint_status),
        ):
            payload = asset_delivery.get_digital_collectible_delivery(
                project_id=project["_id"],
                current_user=current_user,
            )

        self.assertEqual(payload["wallet"], "0xabc123")
        self.assertEqual(payload["customer_wallet"], "0xabc123")


if __name__ == "__main__":
    unittest.main()
