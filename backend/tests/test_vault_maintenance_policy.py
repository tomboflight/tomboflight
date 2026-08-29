import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.routes import uploads as upload_routes
from app.routes import vault as vault_routes
from app.services import project_entitlement_service
from app.services.workspace_access_service import (
    require_workspace_maintenance_write_access,
    resolve_maintenance_access_state,
)


class VaultMaintenancePolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)

    def test_active_maintenance_allows_vault_writes(self):
        state = resolve_maintenance_access_state(
            {"maintenance_status": "active"},
            now=self.now,
        )

        self.assertTrue(state["write_allowed"])
        self.assertFalse(state["read_only"])

    def test_lapsed_maintenance_has_thirty_day_write_grace(self):
        state = resolve_maintenance_access_state(
            {
                "maintenance_status": "past_due",
                "maintenance_lapsed_at": self.now - timedelta(days=20),
            },
            now=self.now,
        )

        self.assertTrue(state["write_allowed"])
        self.assertTrue(state["in_grace"])
        self.assertFalse(state["read_only"])

    def test_lapsed_maintenance_becomes_read_only_after_grace(self):
        state = resolve_maintenance_access_state(
            {
                "maintenance_status": "canceled",
                "maintenance_lapsed_at": self.now - timedelta(days=31),
            },
            now=self.now,
        )

        self.assertFalse(state["write_allowed"])
        self.assertFalse(state["in_grace"])
        self.assertTrue(state["read_only"])

    def test_lapsed_maintenance_without_timestamp_fails_closed_for_writes(self):
        state = resolve_maintenance_access_state(
            {"maintenance_status": "past_due"},
            now=self.now,
        )

        self.assertFalse(state["write_allowed"])
        self.assertTrue(state["read_only"])

    def test_read_only_policy_returns_payment_required_for_mutations(self):
        context = {
            "maintenance_access": {"write_allowed": False},
            "is_admin": False,
        }

        with self.assertRaises(HTTPException) as denied:
            require_workspace_maintenance_write_access(context, feature_name="Vault")

        self.assertEqual(denied.exception.status_code, 402)
        self.assertIn("read-only", str(denied.exception.detail))
        self.assertIn("view and download", str(denied.exception.detail))

    def test_internal_admin_bypasses_maintenance_write_gate(self):
        context = {
            "maintenance_access": {"write_allowed": False},
            "is_admin": True,
        }

        self.assertIs(
            require_workspace_maintenance_write_access(context),
            context,
        )

    def test_vault_role_check_applies_maintenance_only_to_mutations(self):
        context = {
            "member_role": "billing_owner",
            "maintenance_access": {"write_allowed": False},
            "is_admin": False,
        }

        vault_routes._require_vault_role(context)
        with self.assertRaises(HTTPException) as denied:
            vault_routes._require_vault_role(context, sensitive=True, mutation=True)

        self.assertEqual(denied.exception.status_code, 402)

    def test_private_vault_permissions_keep_reads_and_hide_mutations(self):
        record = {
            "_id": "upload-1",
            "category": "private_media",
            "content_type": "application/pdf",
            "original_filename": "record.pdf",
            "storage_provider": "r2",
            "storage_key": "private/record.pdf",
            "scan_status": "clean",
            "is_current_version": True,
        }
        context = {
            "maintenance_access": {"write_allowed": False},
            "is_admin": False,
        }

        with (
            patch.object(upload_routes, "_can_access_upload_record", return_value=True),
            patch.object(upload_routes, "_can_manage_upload_record", return_value=True),
            patch.object(upload_routes, "_context_has_any_capability", return_value=True),
            patch.object(upload_routes, "_can_change_linked_vault_privacy", return_value=True),
            patch.object(upload_routes, "_upload_scan_blocks_download", return_value=False),
            patch.object(upload_routes, "_upload_has_durable_private_storage", return_value=True),
        ):
            payload = upload_routes._public_upload_record(
                record,
                context=context,
                current_user={"id": "owner-1"},
            )

        self.assertTrue(payload["permissions"]["can_preview"])
        self.assertTrue(payload["permissions"]["can_download"])
        self.assertFalse(payload["permissions"]["can_replace"])
        self.assertFalse(payload["permissions"]["can_delete"])
        self.assertFalse(payload["permissions"]["can_change_privacy"])

    def test_first_lapsed_maintenance_update_records_lapse_time(self):
        collection = MagicMock()
        existing = {
            "_id": "entitlement-1",
            "project_id": "project-1",
            "package_code": "legacy_plus",
            "maintenance_status": "active",
        }
        collection.find_one.side_effect = [existing, existing]

        with patch.object(
            project_entitlement_service,
            "_collection",
            return_value=collection,
        ):
            project_entitlement_service.update_project_entitlement_maintenance(
                project_id="project-1",
                maintenance_status="past_due",
            )

        update = collection.update_one.call_args.args[1]
        self.assertIn("maintenance_lapsed_at", update["$set"])

    def test_recovered_maintenance_clears_lapse_time(self):
        collection = MagicMock()
        existing = {
            "_id": "entitlement-1",
            "project_id": "project-1",
            "package_code": "legacy_plus",
            "maintenance_status": "past_due",
            "maintenance_lapsed_at": self.now - timedelta(days=5),
        }
        collection.find_one.side_effect = [existing, existing]

        with patch.object(
            project_entitlement_service,
            "_collection",
            return_value=collection,
        ):
            project_entitlement_service.update_project_entitlement_maintenance(
                project_id="project-1",
                maintenance_status="active",
            )

        update = collection.update_one.call_args.args[1]
        self.assertEqual(update["$unset"]["maintenance_lapsed_at"], "")


if __name__ == "__main__":
    unittest.main()
