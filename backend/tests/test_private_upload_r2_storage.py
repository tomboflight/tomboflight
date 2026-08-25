import io
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import uploads as upload_routes
from app.services import poster_asset_service, r2_storage_service, upload_scan_service


class FakeUpdateResult:
    def __init__(self, matched_count=0):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    def update_one(self, query, update):
        document = self.find_one(query)
        if document is None:
            return FakeUpdateResult()
        document.update(update.get("$set", {}))
        return FakeUpdateResult(matched_count=1)

    def delete_one(self, query):
        document = self.find_one(query)
        if document is not None:
            self.documents.remove(document)


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class FakeS3Client:
    def __init__(self):
        self.put_request = None
        self.deleted = None
        self.head_bucket_name = None

    def put_object(self, **kwargs):
        self.put_request = {
            **kwargs,
            "Body": kwargs["Body"].read(),
        }

    def delete_object(self, **kwargs):
        self.deleted = kwargs

    def head_bucket(self, **kwargs):
        self.head_bucket_name = kwargs["Bucket"]

    def get_object(self, **_kwargs):
        return {
            "ContentLength": len(b"private-pdf"),
            "Body": io.BytesIO(b"private-pdf"),
        }

    def generate_presigned_url(self, *_args, **_kwargs):
        return "https://private-download.example/signed"


class PrivateUploadPromotionTests(unittest.TestCase):
    def _upload_fixture(self, upload_root: Path):
        upload_id = ObjectId()
        relative_path = "member_photos/family-1/member-1/photo.jpg"
        source = upload_root / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"clean-photo")
        record = {
            "_id": upload_id,
            "id": str(upload_id),
            "project_id": "project-1",
            "family_id": "family-1",
            "member_id": "member-1",
            "category": "member_photo",
            "stored_filename": "photo.jpg",
            "relative_path": relative_path,
            "content_type": "image/jpeg",
            "storage_provider": "local_disk",
            "scan_status": "pending",
            "quarantined": False,
        }
        return upload_id, source, record

    def _enter_settings(
        self,
        stack: ExitStack,
        upload_root: Path,
        quarantine_root: Path,
    ) -> None:
        patches = (
            patch.object(upload_routes.settings, "render_disk_mount_path", ""),
            patch.object(upload_routes.settings, "upload_storage_dir", str(upload_root)),
            patch.object(
                upload_routes.settings,
                "upload_quarantine_dir",
                str(quarantine_root),
            ),
        )
        for settings_patch in patches:
            stack.enter_context(settings_patch)

    def test_clean_upload_promotes_to_private_r2_and_removes_staging_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "uploads"
            quarantine_root = Path(tmpdir) / "quarantine"
            upload_id, source, record = self._upload_fixture(upload_root)
            db = FakeDatabase({"uploaded_files": [record]})
            upload_result = {
                "storage_provider": "r2",
                "bucket": "private-bucket",
            }
            with ExitStack() as stack:
                self._enter_settings(stack, upload_root, quarantine_root)
                scan_file = stack.enter_context(
                    patch.object(upload_routes, "scan_uploaded_file")
                )
                stack.enter_context(
                    patch.object(
                        upload_routes,
                        "private_storage_is_configured",
                        return_value=True,
                    )
                )
                upload_private = stack.enter_context(
                    patch.object(
                        upload_routes,
                        "upload_private_file",
                        return_value=upload_result,
                    )
                )
                scan_file.return_value = SimpleNamespace(
                    status="clean",
                    detail="clamav_clean",
                )
                updated = upload_routes._scan_and_quarantine_upload(
                    db=db,
                    upload_record={
                        "id": str(upload_id),
                        "relative_path": record["relative_path"],
                    },
                )

            self.assertEqual(updated["storage_provider"], "r2")
            self.assertEqual(updated["scan_status"], "clean")
            self.assertEqual(updated["storage_promotion_status"], "complete")
            self.assertTrue(updated["storage_key"].startswith("private-uploads/v1/"))
            self.assertFalse(source.exists())
            upload_private.assert_called_once()

    def test_infected_upload_is_quarantined_and_never_sent_to_r2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "uploads"
            quarantine_root = Path(tmpdir) / "quarantine"
            upload_id, source, record = self._upload_fixture(upload_root)
            db = FakeDatabase({"uploaded_files": [record]})
            with ExitStack() as stack:
                self._enter_settings(stack, upload_root, quarantine_root)
                scan_file = stack.enter_context(
                    patch.object(upload_routes, "scan_uploaded_file")
                )
                stack.enter_context(
                    patch.object(
                        upload_routes,
                        "private_storage_is_configured",
                        return_value=True,
                    )
                )
                upload_private = stack.enter_context(
                    patch.object(upload_routes, "upload_private_file")
                )
                scan_file.return_value = SimpleNamespace(
                    status="infected",
                    detail="clamav_detected:test-signature",
                )
                updated = upload_routes._scan_and_quarantine_upload(
                    db=db,
                    upload_record={
                        "id": str(upload_id),
                        "relative_path": record["relative_path"],
                    },
                )

            self.assertEqual(updated["scan_status"], "infected")
            self.assertTrue(updated["quarantined"])
            self.assertFalse(source.exists())
            self.assertTrue(Path(updated["quarantine_path"]).is_file())
            upload_private.assert_not_called()

    def test_skipped_scan_is_quarantined_and_never_promoted_to_r2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "uploads"
            quarantine_root = Path(tmpdir) / "quarantine"
            upload_id, source, record = self._upload_fixture(upload_root)
            db = FakeDatabase({"uploaded_files": [record]})
            with ExitStack() as stack:
                self._enter_settings(stack, upload_root, quarantine_root)
                scan_file = stack.enter_context(
                    patch.object(upload_routes, "scan_uploaded_file")
                )
                stack.enter_context(
                    patch.object(
                        upload_routes,
                        "private_storage_is_configured",
                        return_value=True,
                    )
                )
                upload_private = stack.enter_context(
                    patch.object(upload_routes, "upload_private_file")
                )
                scan_file.return_value = SimpleNamespace(
                    status="skipped",
                    detail="scanner_unavailable",
                )
                updated = upload_routes._scan_and_quarantine_upload(
                    db=db,
                    upload_record={
                        "id": str(upload_id),
                        "relative_path": record["relative_path"],
                    },
                )

            self.assertEqual(updated["scan_status"], "skipped")
            self.assertTrue(updated["quarantined"])
            self.assertFalse(source.exists())
            upload_private.assert_not_called()

    def test_r2_promotion_failure_is_quarantined_and_blocks_access(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "uploads"
            quarantine_root = Path(tmpdir) / "quarantine"
            upload_id, source, record = self._upload_fixture(upload_root)
            db = FakeDatabase({"uploaded_files": [record]})
            with ExitStack() as stack:
                self._enter_settings(stack, upload_root, quarantine_root)
                scan_file = stack.enter_context(
                    patch.object(upload_routes, "scan_uploaded_file")
                )
                stack.enter_context(
                    patch.object(
                        upload_routes,
                        "private_storage_is_configured",
                        return_value=True,
                    )
                )
                stack.enter_context(
                    patch.object(
                        upload_routes,
                        "upload_private_file",
                        side_effect=RuntimeError("provider unavailable"),
                    )
                )
                delete_partial = stack.enter_context(
                    patch.object(upload_routes, "delete_private_object")
                )
                scan_file.return_value = SimpleNamespace(
                    status="clean",
                    detail="clamav_clean",
                )
                updated = upload_routes._scan_and_quarantine_upload(
                    db=db,
                    upload_record={
                        "id": str(upload_id),
                        "relative_path": record["relative_path"],
                    },
                )

            self.assertEqual(updated["scan_status"], "error")
            self.assertTrue(updated["quarantined"])
            self.assertTrue(upload_routes._upload_scan_blocks_download(updated))
            self.assertFalse(source.exists())
            self.assertTrue(
                delete_partial.call_args.kwargs["key"].startswith(
                    "private-uploads/v1/"
                )
            )


class PrivateUploadAccessTests(unittest.TestCase):
    def _record(self):
        upload_id = ObjectId()
        return {
            "_id": upload_id,
            "id": str(upload_id),
            "category": "private_media",
            "storage_provider": "r2",
            "storage_key": (
                "private-uploads/v1/private_media/family/member/"
                f"{upload_id}/filemp4"
            ),
            "relative_path": "private_media/family/member/file.mp4",
            "scan_status": "clean",
            "quarantined": False,
            "content_type": "video/mp4",
            "original_filename": "message.mp4",
        }

    def test_production_approval_requires_durable_private_r2_key(self):
        with patch.object(upload_routes.settings, "environment", "production"):
            self.assertFalse(
                upload_routes._upload_has_durable_private_storage(
                    {"storage_provider": "local_disk"}
                )
            )
            self.assertFalse(
                upload_routes._upload_has_durable_private_storage(
                    {"storage_provider": "r2", "storage_key": ""}
                )
            )
            self.assertTrue(
                upload_routes._upload_has_durable_private_storage(
                    {
                        "storage_provider": "r2",
                        "storage_key": "private-uploads/v1/member/id/photo",
                    }
                )
            )

    def test_admin_review_queue_deduplicates_only_shared_storage_records(self):
        first = self._record()
        duplicate_id = ObjectId()
        duplicate = {
            **first,
            "_id": duplicate_id,
            "id": str(duplicate_id),
            "original_filename": "migration-copy.mp4",
        }
        separate_id = ObjectId()
        separate = {
            **first,
            "_id": separate_id,
            "id": str(separate_id),
            "storage_key": (
                "private-uploads/v1/private_media/family/member/"
                f"{separate_id}/filemp4"
            ),
        }

        records, suppressed = upload_routes._deduplicate_admin_review_records(
            [first, duplicate, separate]
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(suppressed, 1)
        self.assertIs(records[0], first)
        self.assertIs(records[1], separate)

    def test_distinct_duplicate_looking_uploads_remain_visible_and_are_flagged(self):
        first = self._record()
        first.update(
            {
                "member_id": "member-1",
                "original_filename": "government-id.pdf",
                "file_size": 12345,
            }
        )
        second_id = ObjectId()
        second = {
            **first,
            "_id": second_id,
            "id": str(second_id),
            "storage_key": f"private-uploads/v1/evidence/{second_id}/government-id",
        }

        records, suppressed = upload_routes._deduplicate_admin_review_records(
            [first, second]
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(suppressed, 0)
        self.assertEqual(first["_possible_duplicate_count"], 2)
        self.assertEqual(second["_possible_duplicate_count"], 2)

    def test_admin_review_serialization_explains_preview_blockers_before_open(self):
        record = self._record()
        record.update(
            {
                "scan_status": "pending",
                "storage_provider": "local_disk",
                "storage_key": "",
            }
        )
        db = FakeDatabase(
            {"projects": [], "families": [], "family_members": []}
        )

        with patch.object(upload_routes.settings, "environment", "production"):
            serialized = upload_routes._serialize_admin_upload_review(
                record,
                db=db,
            )

        self.assertFalse(serialized["preview_available"])
        self.assertEqual(
            serialized["preview_blockers"],
            ["security_scan_not_clean", "durable_private_storage_missing"],
        )
        self.assertIn("clean verdict", serialized["preview_blocker_message"])
        self.assertIn("Private storage migration", serialized["preview_blocker_message"])

    def test_unknown_scan_state_fails_closed_for_admin_preview(self):
        self.assertTrue(upload_routes._upload_scan_blocks_download({}))

    def test_admin_rescan_recovers_pending_private_r2_upload(self):
        record = self._record()
        record.update(
            {
                "scan_status": "pending",
                "quarantined": True,
                "storage_promotion_status": "blocked",
            }
        )
        db = FakeDatabase({"uploaded_files": [record], "audit_logs": []})
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(upload_routes.settings, "render_disk_mount_path", ""),
                patch.object(upload_routes.settings, "upload_storage_dir", tmpdir),
                patch.object(upload_routes, "get_database", return_value=db),
                patch.object(
                    upload_routes,
                    "download_private_bytes",
                    return_value=b"clean-private-file",
                ) as download,
                patch.object(
                    upload_routes,
                    "scan_uploaded_file",
                    return_value=SimpleNamespace(status="clean", detail="clamav_clean"),
                ) as scan,
                patch.object(upload_routes, "write_audit_log") as audit,
            ):
                result = upload_routes.admin_rescan_upload(
                    upload_id=str(record["_id"]),
                    current_user={
                        "_id": ObjectId(),
                        "email": "l.robinson@tomboflight.com",
                    },
                )

        self.assertEqual(result["upload"]["scan_status"], "clean")
        self.assertFalse(record["quarantined"])
        self.assertEqual(record["storage_promotion_status"], "complete")
        download.assert_called_once_with(key=record["storage_key"], max_bytes=upload_routes.EVIDENCE_MAX_BYTES)
        scan.assert_called_once()
        audit.assert_called_once()

    def test_admin_preview_proxies_private_r2_bytes_without_signed_redirect(self):
        record = self._record()
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(record, {"is_admin": True}),
            ),
            patch.object(
                upload_routes,
                "download_private_bytes",
                return_value=b"private-preview",
            ),
        ):
            response = upload_routes.preview_upload_for_admin_review(
                str(record["_id"]),
                current_user={"_id": ObjectId(), "email": "l.robinson@tomboflight.com"},
            )

        self.assertEqual(response.body, b"private-preview")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(response.headers["content-disposition"].startswith("inline;"))

    def test_orphaned_upload_references_block_portrait_placement(self):
        record = self._record()
        record.update(
            {
                "category": "member_photo",
                "project_id": str(ObjectId()),
                "family_id": str(ObjectId()),
                "member_id": str(ObjectId()),
                "consent_attested": True,
                "authority_attested": True,
            }
        )
        db = FakeDatabase(
            {
                "uploaded_files": [record],
                "projects": [],
                "families": [],
                "family_members": [],
            }
        )
        with patch.object(upload_routes, "get_database", return_value=db):
            preview = upload_routes.preview_admin_upload_action(
                upload_id=str(record["_id"]),
                action="portrait_review",
                decision="approved",
            )

        self.assertTrue(preview["blocked"])
        self.assertIn("orphaned_project_reference", preview["blocked_reasons"])
        self.assertIn("orphaned_family_reference", preview["blocked_reasons"])
        self.assertIn("orphaned_member_reference", preview["blocked_reasons"])

    def test_customer_can_recover_old_portrait_attestations_but_admin_cannot_impersonate_consent(self):
        record = self._record()
        record.update(
            {
                "category": "member_photo",
                "uploaded_by_user_id": "customer-1",
                "consent_attested": False,
                "authority_attested": False,
            }
        )
        db = FakeDatabase({"uploaded_files": [record], "audit_logs": []})
        owner_context = {
            "is_admin": False,
            "project": {"owner_user_id": "customer-1"},
        }
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(record, owner_context),
            ),
            patch.object(upload_routes, "write_audit_log"),
        ):
            result = upload_routes.attest_existing_portrait_upload(
                str(record["_id"]),
                upload_routes.UploadPortraitAttestationPayload(
                    consent_attested=True,
                    authority_attested=True,
                ),
                current_user={"_id": "customer-1", "email": "customer@example.com"},
            )

        self.assertTrue(result["upload"]["consent_attested"])
        self.assertTrue(result["upload"]["authority_attested"])

        record["consent_attested"] = False
        record["authority_attested"] = False
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(
                    record,
                    {"is_admin": True, "project": {"owner_user_id": "customer-1"}},
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                upload_routes.attest_existing_portrait_upload(
                    str(record["_id"]),
                    upload_routes.UploadPortraitAttestationPayload(
                        consent_attested=True,
                        authority_attested=True,
                    ),
                    current_user={"_id": "admin-1", "email": "admin@example.com"},
                )
        self.assertEqual(raised.exception.status_code, 403)

    def test_r2_download_uses_short_lived_redirect(self):
        record = self._record()
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                return_value=(record, {}),
            ),
            patch.object(
                upload_routes,
                "generate_private_download_url",
                return_value="https://private-download.example/signed",
            ) as signed_url,
        ):
            response = upload_routes.download_upload(
                str(record["_id"]),
                current_user={"id": "owner-1", "email": "owner@example.com"},
            )

        self.assertEqual(response.status_code, 307)
        self.assertEqual(
            response.headers["location"],
            "https://private-download.example/signed",
        )
        self.assertEqual(response.headers["cache-control"], "no-store")
        signed_url.assert_called_once_with(
            key=record["storage_key"],
            expires_seconds=120,
        )

    def test_r2_download_with_missing_key_fails_closed(self):
        record = self._record()
        record["storage_key"] = ""
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                return_value=(record, {}),
            ),
            patch.object(upload_routes, "generate_private_download_url") as signed_url,
        ):
            with self.assertRaises(HTTPException) as raised:
                upload_routes.download_upload(
                    str(record["_id"]),
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        self.assertEqual(raised.exception.status_code, 409)
        signed_url.assert_not_called()

    def test_production_download_blocks_legacy_local_upload_pending_migration(self):
        record = self._record()
        record["storage_provider"] = "local_disk"
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes.settings, "environment", "production"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                return_value=(record, {}),
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                upload_routes.download_upload(
                    str(record["_id"]),
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        self.assertEqual(raised.exception.status_code, 503)

    def test_deletion_pending_cannot_be_bypassed_by_admin_override(self):
        record = self._record()
        record["deletion_status"] = "pending"
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes.settings, "upload_allow_admin_quarantine_override", True),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                return_value=(record, {}),
            ),
            patch.object(upload_routes, "_is_admin", return_value=True),
            patch.object(upload_routes, "generate_private_download_url") as signed_url,
        ):
            with self.assertRaises(HTTPException) as raised:
                upload_routes.download_upload(
                    str(record["_id"]),
                    admin_override=True,
                    current_user={"id": "admin-1", "email": "admin@example.com"},
                )

        self.assertEqual(raised.exception.status_code, 403)
        signed_url.assert_not_called()

    def test_r2_deletion_removes_object_before_database_record(self):
        record = self._record()
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(record, {}),
            ),
            patch.object(upload_routes, "delete_private_object") as delete_private,
        ):
            result = upload_routes.delete_upload(
                str(record["_id"]),
                current_user={"id": "owner-1", "email": "owner@example.com"},
            )

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(db["uploaded_files"].documents, [])
        delete_private.assert_called_once_with(key=record["storage_key"])

    def test_r2_deletion_failure_retains_blocked_record_for_retry(self):
        record = self._record()
        db = FakeDatabase({"uploaded_files": [record]})
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(record, {}),
            ),
            patch.object(
                upload_routes,
                "delete_private_object",
                side_effect=RuntimeError("provider unavailable"),
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                upload_routes.delete_upload(
                    str(record["_id"]),
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(len(db["uploaded_files"].documents), 1)
        self.assertEqual(record["deletion_status"], "failed")
        self.assertTrue(upload_routes._upload_scan_blocks_download(record))

    def test_deleting_quarantined_upload_removes_quarantine_file(self):
        record = self._record()
        record["storage_provider"] = "local_disk"
        record["scan_status"] = "infected"
        record["quarantined"] = True
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "uploads"
            quarantine_root = Path(tmpdir) / "quarantine"
            quarantine_root.mkdir(parents=True)
            quarantine_file = quarantine_root / "infected-item"
            quarantine_file.write_bytes(b"infected")
            record["quarantine_path"] = str(quarantine_file)
            db = FakeDatabase({"uploaded_files": [record]})
            with (
                patch.object(upload_routes.settings, "render_disk_mount_path", ""),
                patch.object(upload_routes.settings, "upload_storage_dir", str(upload_root)),
                patch.object(
                    upload_routes.settings,
                    "upload_quarantine_dir",
                    str(quarantine_root),
                ),
                patch.object(upload_routes, "get_database", return_value=db),
                patch.object(
                    upload_routes,
                    "_require_upload_management_access",
                    return_value=(record, {}),
                ),
            ):
                upload_routes.delete_upload(
                    str(record["_id"]),
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

            self.assertFalse(quarantine_file.exists())
            self.assertEqual(db["uploaded_files"].documents, [])

    def test_deleting_active_portrait_clears_all_member_references(self):
        record = self._record()
        record["category"] = "member_photo"
        member_id = ObjectId()
        record["member_id"] = str(member_id)
        upload_id = str(record["_id"])
        member = {
            "_id": member_id,
            "pending_photo_upload_id": upload_id,
            "approved_photo_upload_id": upload_id,
            "photo_upload_id": upload_id,
            "photo_path": "old/path.jpg",
            "photo_submission_status": "approved",
        }
        db = FakeDatabase(
            {"uploaded_files": [record], "family_members": [member]}
        )
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(record, {}),
            ),
            patch.object(upload_routes, "delete_private_object"),
        ):
            upload_routes.delete_upload(
                upload_id,
                current_user={"id": "owner-1", "email": "owner@example.com"},
            )

        self.assertIsNone(member["pending_photo_upload_id"])
        self.assertIsNone(member["approved_photo_upload_id"])
        self.assertIsNone(member["photo_upload_id"])
        self.assertIsNone(member["photo_path"])
        self.assertEqual(member["photo_submission_status"], "not_submitted")


class PrivateR2ServiceTests(unittest.TestCase):
    def _enter_configuration(self, stack: ExitStack) -> None:
        patches = (
            patch.object(r2_storage_service.settings, "r2_access_key_id", "access-key"),
            patch.object(
                r2_storage_service.settings,
                "r2_secret_access_key",
                "secret-key",
            ),
            patch.object(
                r2_storage_service.settings,
                "r2_endpoint_url",
                "https://account.r2.cloudflarestorage.com",
            ),
            patch.object(
                r2_storage_service.settings,
                "r2_private_bucket",
                "private-bucket",
            ),
        )
        for configuration_patch in patches:
            stack.enter_context(configuration_patch)

    def test_private_file_stream_health_download_and_delete(self):
        client = FakeS3Client()
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "upload.pdf"
            source.write_bytes(b"private-pdf")
            with ExitStack() as stack:
                self._enter_configuration(stack)
                stack.enter_context(
                    patch.object(
                        r2_storage_service,
                        "_lazy_s3_client",
                        return_value=client,
                    )
                )
                result = r2_storage_service.upload_private_file(
                    key="private-uploads/v1/evidence/family/member/upload/file.pdf",
                    path=source,
                    content_type="application/pdf",
                )
                health = r2_storage_service.get_private_storage_health(
                    check_provider=True
                )
                signed_url = r2_storage_service.generate_private_download_url(
                    key=result["key"]
                )
                downloaded = r2_storage_service.download_private_bytes(
                    key=result["key"],
                    max_bytes=100,
                )
                r2_storage_service.delete_private_object(key=result["key"])

        self.assertEqual(client.put_request["Body"], b"private-pdf")
        self.assertEqual(client.put_request["CacheControl"], "private, no-store")
        self.assertEqual(client.head_bucket_name, "private-bucket")
        self.assertTrue(health["available"])
        self.assertEqual(signed_url, "https://private-download.example/signed")
        self.assertEqual(downloaded, b"private-pdf")
        self.assertEqual(client.deleted["Key"], result["key"])

    def test_generic_bucket_does_not_satisfy_private_bucket_requirement(self):
        with (
            patch.object(r2_storage_service.settings, "r2_access_key_id", "access-key"),
            patch.object(r2_storage_service.settings, "r2_secret_access_key", "secret-key"),
            patch.object(
                r2_storage_service.settings,
                "r2_endpoint_url",
                "https://account.r2.cloudflarestorage.com",
            ),
            patch.object(r2_storage_service.settings, "r2_bucket", "public-bucket"),
            patch.object(r2_storage_service.settings, "r2_private_bucket", ""),
        ):
            self.assertFalse(r2_storage_service.private_storage_is_configured())

    def test_approved_r2_portrait_can_be_exported_as_public_poster(self):
        portrait = {
            "storage_provider": "r2",
            "storage_key": "private-uploads/v1/member_photo/family/member/id/photojpg",
            "content_type": "image/jpeg",
            "stored_filename": "photo.jpg",
        }
        with (
            patch.object(
                poster_asset_service,
                "_best_uploaded_portrait",
                return_value=portrait,
            ),
            patch.object(
                poster_asset_service,
                "download_private_bytes",
                return_value=b"approved-photo",
            ) as download_private,
            patch.object(
                poster_asset_service,
                "upload_bytes",
                return_value={
                    "storage_provider": "r2",
                    "bucket": "poster-bucket",
                    "key": "v1/token-approved-poster.jpg",
                },
            ) as upload_poster,
        ):
            result = poster_asset_service.export_approved_public_poster(
                "project-1",
                1,
                "token",
            )

        download_private.assert_called_once_with(
            key=portrait["storage_key"],
            max_bytes=poster_asset_service.settings.upload_max_image_bytes,
        )
        self.assertEqual(upload_poster.call_args.kwargs["body"], b"approved-photo")
        self.assertEqual(result["poster_storage_provider"], "r2")

    def test_approved_poster_never_silently_substitutes_abstract_art(self):
        with patch.object(
            poster_asset_service,
            "_best_uploaded_portrait",
            return_value=None,
        ):
            with self.assertRaisesRegex(RuntimeError, "no eligible approved portrait"):
                poster_asset_service.export_approved_public_poster(
                    "project-1",
                    1,
                    "token",
                )

    def test_production_approved_poster_rejects_legacy_local_source(self):
        with (
            patch.object(
                poster_asset_service.settings,
                "environment",
                "production",
            ),
            patch.object(
                poster_asset_service,
                "_read_local_upload_bytes",
                return_value=(b"local-photo", "image/jpeg", ".jpg"),
            ) as read_local,
        ):
            source = poster_asset_service._read_approved_upload_bytes(
                {"storage_provider": "local_disk"}
            )

        self.assertIsNone(source)
        read_local.assert_not_called()

    def test_scanner_health_uses_provider_healthcheck(self):
        configuration = upload_scan_service.UploadScannerConfiguration(
            configured=True,
            detail="clamav_configured",
        )
        module = SimpleNamespace(
            healthcheck=lambda: {
                "configured": True,
                "available": True,
                "detail": "clamav_ready",
            }
        )
        with (
            patch.object(
                upload_scan_service,
                "get_upload_scanner_configuration",
                return_value=configuration,
            ),
            patch.object(
                upload_scan_service.settings,
                "upload_scan_hook",
                "scanner.module:scan",
            ),
            patch.object(
                upload_scan_service.importlib,
                "import_module",
                return_value=module,
            ),
        ):
            health = upload_scan_service.get_upload_scanner_health()

        self.assertTrue(health["available"])
        self.assertEqual(health["detail"], "clamav_ready")


if __name__ == "__main__":
    unittest.main()
