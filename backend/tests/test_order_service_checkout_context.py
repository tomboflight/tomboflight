import unittest

from app.services import order_service


class OrderServiceCheckoutContextTests(unittest.TestCase):
    def test_extract_checkout_context_parses_tol_reference(self):
        session = {
            "client_reference_id": "tol:v=1&u=user-1&p=project-1&k=legacy_plus&t=maintenance&b=monthly&c=light_never_dies"
        }
        context = order_service._extract_checkout_context(session)
        self.assertEqual(context.get("user_id"), "user-1")
        self.assertEqual(context.get("project_id"), "project-1")
        self.assertEqual(context.get("package_code"), "legacy_plus")
        self.assertEqual(context.get("item_type"), "maintenance")
        self.assertEqual(context.get("billing_interval"), "monthly")
        self.assertEqual(context.get("campaign"), "LIGHT_NEVER_DIES")

    def test_extract_target_project_id_falls_back_to_checkout_context(self):
        session = {
            "client_reference_id": "tol:v=1&p=project-abc&k=legacy_snapshot&t=package&b=one_time"
        }
        self.assertEqual(order_service._extract_target_project_id(session), "project-abc")

    def test_infer_purchase_fields_prefers_checkout_context_when_metadata_missing(self):
        session = {
            "client_reference_id": "tol:v=1&k=legacy_portrait_intro&t=maintenance&b=monthly&c=LIGHT_NEVER_DIES",
            "line_items": {"data": []},
        }
        item_type, package_code, _package_name, _price_label, billing_plan = (
            order_service._infer_purchase_fields(session)
        )
        self.assertEqual(item_type, "maintenance")
        self.assertEqual(package_code, "legacy_portrait_intro")
        self.assertEqual(billing_plan, "monthly")


if __name__ == "__main__":
    unittest.main()
