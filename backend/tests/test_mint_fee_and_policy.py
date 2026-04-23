import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.core.package_catalog import get_package_control_profile, get_public_package_catalog
from app.routes import mint_records
from app.services import mint_fee_service, mint_policy_service


class MintFeeCatalogTests(unittest.TestCase):
    def test_package_control_profile_exposes_mint_fee_fields(self):
        profile = get_package_control_profile("digital_legacy_portrait")
        assert profile is not None
        mint_policy = profile["mint_policy"]
        self.assertIn("mint_fee_model", mint_policy)
        self.assertIn("minting_included", mint_policy)
        self.assertIn("minting_service_fee_usd", mint_policy)
        self.assertIn("default_network_fee_policy", mint_policy)
        self.assertIn("additional_mint_service_fee_usd", mint_policy)
        self.assertIn("remint_service_fee_usd", mint_policy)

    def test_public_catalog_exposes_minting_fee_copy(self):
        packages = {item["package_code"]: item for item in get_public_package_catalog()}
        sample = packages["digital_legacy_portrait"]
        self.assertIn("minting_copy", sample)
        self.assertIn("separate one-time production step", sample["minting_copy"])
        self.assertIn("Private vault materials are not minted by default", sample["minting_copy"])


class MintReadinessTests(unittest.TestCase):
    def test_mint_policy_blocks_when_public_safe_or_manifest_missing(self):
        project = {
            "_id": "project-1",
            "package_code": "digital_legacy_portrait",
            "status": "build_ready",
            "phase": "intake_approved",
            "public_safe_approved": False,
            "delivery_manifest_finalized": False,
            "mint_collectible_preparing": False,
        }
        with patch.object(mint_policy_service, "_runtime_enabled", return_value=True):
            payload = mint_policy_service.describe_project_mint_eligibility(project)

        self.assertFalse(payload["eligible"])
        self.assertIn("public_safe_approval_incomplete", payload["reasons"])
        self.assertIn("delivery_manifest_not_finalized", payload["reasons"])
        self.assertIn("collectible_not_preparing", payload["reasons"])

    def test_mint_fee_satisfied_for_included_credit(self):
        project = {
            "_id": "p1",
            "package_code": "digital_legacy_portrait",
            "mints_used_count": 0,
            "mint_fee_status": "not_required",
        }
        with patch.object(mint_fee_service, "describe_project_mint_eligibility", return_value={"mint_policy": {"included_anchor_count": 1, "minting_included": True, "mint_fee_model": "flat_included"}}):
            ok, reason = mint_fee_service.mint_fee_satisfied(project)
        self.assertTrue(ok)
        self.assertIsNone(reason)


class MintQueueFeeGateTests(unittest.TestCase):
    def test_queue_route_blocks_when_fee_not_ready(self):
        with patch.object(mint_records, "_project_for_request", return_value={"_id": "p1"}), patch.object(
            mint_records, "_require_project_match", return_value={"id": "m1"}
        ), patch.object(
            mint_records, "build_mint_status", return_value={"current_status": "approved", "current_mint_record_id": "m1"}
        ), patch.object(
            mint_records, "describe_project_mint_eligibility", return_value={"eligible": True, "reasons": []}
        ), patch.object(
            mint_records, "get_project_mint_readiness", return_value={"ready_for_mint_execution": False, "blocking_reasons": ["mint_fee_unpaid_or_unwaived"]}
        ):
            with self.assertRaises(HTTPException) as ctx:
                mint_records.queue_project_mint_record("p1", "m1", {"email": "admin@test.com"})

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("mint_fee_unpaid_or_unwaived", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
