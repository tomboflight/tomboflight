import unittest
from bson import ObjectId
from unittest.mock import patch

from app.routes import asset_delivery


class _FakeOrderCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeOrdersCollection:
    def __init__(self, docs):
        self._docs = list(docs)
        self.last_query = None

    def find(self, query):
        self.last_query = query
        return _FakeOrderCursor(self._docs)


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

    def test_resolve_order_for_project_prefers_project_orders_for_shared_workspace(self):
        project_id = "507f1f77bcf86cd799439011"
        paid_order_id = ObjectId("507f1f77bcf86cd799439099")
        fake_orders = _FakeOrdersCollection(
            [
                {
                    "_id": ObjectId("507f1f77bcf86cd799439055"),
                    "project_id": ObjectId(project_id),
                    "item_type": "package",
                    "status": "pending",
                },
                {
                    "_id": paid_order_id,
                    "project_id": ObjectId(project_id),
                    "item_type": "package",
                    "status": "paid",
                },
            ]
        )

        with (
            patch.object(asset_delivery, "get_database", return_value={"orders": fake_orders}),
            patch.object(asset_delivery, "get_orders_for_user", return_value=[]),
        ):
            order = asset_delivery._resolve_order_for_project(
                current_user={"id": "invitee-1", "email": "invitee@example.com"},
                project_id=project_id,
            )

        self.assertIsNotNone(order)
        assert order is not None
        self.assertEqual(order.get("status"), "paid")
        self.assertEqual(order.get("id"), str(paid_order_id))
        self.assertIn("project_id", order)

    def test_resolve_order_for_project_falls_back_to_user_orders_when_project_link_missing(self):
        with (
            patch.object(asset_delivery, "get_database", return_value={"orders": _FakeOrdersCollection([])}),
            patch.object(
                asset_delivery,
                "get_orders_for_user",
                return_value=[
                    {"id": "order-1", "item_type": "package", "status": "paid"},
                    {"id": "order-2", "item_type": "addon", "status": "paid"},
                ],
            ),
        ):
            order = asset_delivery._resolve_order_for_project(
                current_user={"id": "owner-1", "email": "owner@example.com"},
                project_id="project-without-order-link",
            )

        self.assertIsNotNone(order)
        assert order is not None
        self.assertEqual(order.get("id"), "order-1")


if __name__ == "__main__":
    unittest.main()
