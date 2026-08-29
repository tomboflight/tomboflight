import asyncio
import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.routes import uploads as upload_routes
from app.services import vault_service
from app.services.upload_service import serialize_upload_record


class FakeWriteResult:
    def __init__(self, *, matched_count=0, modified_count=0, deleted_count=0, inserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.deleted_count = deleted_count
        self.inserted_id = inserted_id


class FakeCursor(list):
    def sort(self, field_name, direction):
        reverse = int(direction) < 0
        return FakeCursor(
            sorted(self, key=lambda item: str(item.get(field_name) or ""), reverse=reverse)
        )

    def limit(self, value):
        return FakeCursor(self[: int(value)])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.update_calls = []
        self.delete_calls = []
        self.insert_calls = []

    @classmethod
    def _matches(cls, document, query):
        for key, expected in (query or {}).items():
            if key == "$or":
                if not any(cls._matches(document, branch) for branch in expected):
                    return False
                continue
            if key == "$and":
                if not all(cls._matches(document, branch) for branch in expected):
                    return False
                continue

            actual = document.get(key)
            if not isinstance(expected, dict):
                if actual != expected:
                    return False
                continue

            for operator, operand in expected.items():
                if operator == "$in":
                    if isinstance(actual, list):
                        if not any(value in operand for value in actual):
                            return False
                    elif actual not in operand:
                        return False
                elif operator == "$nin":
                    if isinstance(actual, list):
                        if any(value in operand for value in actual):
                            return False
                    elif actual in operand:
                        return False
                elif operator == "$ne":
                    if actual == operand:
                        return False
                elif operator == "$exists":
                    if (key in document) is not bool(operand):
                        return False
                else:
                    return False
        return True

    def find_one(self, query=None, *args, **kwargs):
        del args, kwargs
        for document in self.documents:
            if self._matches(document, query or {}):
                return document
        return None

    def find(self, query=None, *args, **kwargs):
        del args, kwargs
        return FakeCursor(
            [document for document in self.documents if self._matches(document, query or {})]
        )

    def insert_one(self, document):
        self.insert_calls.append(document)
        if document.get("_id") is None:
            document["_id"] = ObjectId()
        self.documents.append(document)
        return FakeWriteResult(inserted_id=document["_id"])

    def update_one(self, query, update, *args, **kwargs):
        del args, kwargs
        self.update_calls.append((query, update))
        document = self.find_one(query)
        if document is None:
            return FakeWriteResult()
        for key, value in (update.get("$set") or {}).items():
            document[key] = value
        for key in (update.get("$unset") or {}):
            document.pop(key, None)
        for key, value in (update.get("$inc") or {}).items():
            document[key] = document.get(key, 0) + value
        return FakeWriteResult(matched_count=1, modified_count=1)

    def delete_one(self, query):
        self.delete_calls.append(query)
        document = self.find_one(query)
        if document is None:
            return FakeWriteResult()
        self.documents.remove(document)
        return FakeWriteResult(deleted_count=1)


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


def upload_file(*, filename, content_type, payload):
    return UploadFile(
        file=io.BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def workspace_context(*, role="billing_owner", user_id="owner-1", is_admin=False):
    return {
        "project": {"_id": "project-1", "owner_user_id": user_id},
        "family": {"_id": "family-1"},
        "member": {"_id": "member-1", "family_id": "family-1"},
        "member_role": role,
        "relationship_scope": "household_member",
        "link_status": "active",
        "resolved_entitlements": {
            "can_upload_portraits": True,
            "can_upload_verification_docs": True,
            "can_use_personal_vault": True,
            "can_use_household_vault": True,
            "can_use_linked_household_vault": True,
            "can_link_households": True,
            "can_use_scheduled_reveal": True,
            "allowed_asset_types": [
                "portrait_photo",
                "document",
                "private_voice_message",
                "private_video_message",
            ],
        },
        "is_admin": is_admin,
    }


def private_upload_record(**overrides):
    upload_id = overrides.pop("_id", ObjectId())
    record = {
        "_id": upload_id,
        "id": str(upload_id),
        "project_id": "project-1",
        "family_id": "family-1",
        "member_id": "member-1",
        "category": "private_media",
        "asset_type": "vault_photo",
        "uploaded_by_user_id": "owner-1",
        "uploaded_by": "owner@example.com",
        "customer_visible": False,
        "internal_only": False,
        "vault_scope": "household",
        "visibility_scope": "private_to_owner",
        "privacy_scope": "private_to_owner",
        "privacy_classification": "private_to_owner",
        "account_access_enabled": True,
        "owner_account_deleted": False,
        "scan_status": "clean",
        "quarantined": False,
        "storage_provider": "r2",
        "storage_key": f"private-uploads/v1/private_media/{upload_id}/photo.jpg",
        "content_type": "image/jpeg",
        "original_filename": "portrait.jpg",
        "version": 1,
        "version_group_id": str(upload_id),
        "replacement_status": "current",
        "is_current_version": True,
        "created_at": "2026-08-29T10:00:00+00:00",
    }
    record.update(overrides)
    return record


def linked_relative_context(*, link_status="active", include_membership=True):
    context = workspace_context(role="linked_relative", user_id="project-owner")
    context["relationship_scope"] = "linked_relative"
    # Keep the historical top-level optimistic value so a missing canonical
    # membership proves that linked access still fails closed.
    context["link_status"] = "active"
    context["access_snapshot"] = {
        "membership": ({"link_status": link_status} if include_membership else {})
    }
    return context


def linked_vault_fixture(*, release_state="released"):
    item_id = ObjectId()
    upload = private_upload_record(
        vault_scope="linked_family",
        vault_item_id=str(item_id),
        visibility_scope="linked_family_shared",
        privacy_scope="linked_family_shared",
        privacy_classification="linked_family_shared",
        customer_visible=True,
        share_with_linked_families=True,
        release_state=release_state,
        reveal_at="2999-01-01T00:00:00+00:00" if release_state == "scheduled" else None,
    )
    item = {
        "_id": item_id,
        "project_id": upload["project_id"],
        "family_id": upload["family_id"],
        "owner_user_id": upload["uploaded_by_user_id"],
        "vault_scope": "linked_family",
        "privacy": "all_linked",
        "release_state": release_state,
        "reveal_at": upload.get("reveal_at"),
        "status": "active",
        "access_enabled": True,
        "current_upload_id": str(upload["_id"]),
        "asset_version": 1,
        "asset_versions": [{"upload_id": str(upload["_id"]), "version": 1}],
    }
    db = FakeDatabase(
        {
            "uploaded_files": [upload],
            "vault_items": [item],
            "vault_access_grants": [],
            "vault_release_rules": [],
            "vault_audit_events": [],
        }
    )
    return upload, item, db


def linked_viewer_context():
    context = workspace_context(role="billing_owner", user_id="viewer-user")
    context["project"] = {
        "_id": "viewer-project",
        "owner_user_id": "viewer-user",
    }
    context["family"] = {"_id": "viewer-family"}
    context["member"] = {
        "_id": "viewer-member",
        "family_id": "viewer-family",
    }
    return context


def linked_viewer_fixture(*, release_state="released", explicitly_shared=True, with_prior=False):
    upload, item, db = linked_vault_fixture(release_state=release_state)
    upload.update(
        {
            "project_id": "source-project",
            "family_id": "source-family",
            "member_id": "source-member",
            "share_with_linked_families": bool(explicitly_shared),
        }
    )
    item.update(
        {
            "project_id": "source-project",
            "family_id": "source-family",
            "member_id": "source-member",
            "share_with_linked_families": bool(explicitly_shared),
        }
    )
    prior = None
    if with_prior:
        prior = private_upload_record(
            vault_scope="linked_family",
            vault_item_id=str(item["_id"]),
            project_id="source-project",
            family_id="source-family",
            member_id="source-member",
            visibility_scope="linked_family_shared",
            privacy_scope="linked_family_shared",
            privacy_classification="linked_family_shared",
            customer_visible=True,
            share_with_linked_families=True,
            release_state="released",
            version=1,
            is_current_version=False,
            replacement_status="superseded",
        )
        upload.update(
            {
                "version": 2,
                "version_group_id": str(prior["_id"]),
                "replaces_upload_id": str(prior["_id"]),
            }
        )
        prior["version_group_id"] = str(prior["_id"])
        prior["superseded_by_upload_id"] = str(upload["_id"])
        item.update(
            {
                "asset_version": 2,
                "asset_versions": [
                    {"version": 1, "upload_id": str(prior["_id"])},
                    {
                        "version": 2,
                        "upload_id": str(upload["_id"]),
                        "replaces_upload_id": str(prior["_id"]),
                    },
                ],
            }
        )
        db["uploaded_files"].documents.insert(0, prior)
    return upload, prior, item, db


class UploadLifecycleSecurityTests(unittest.TestCase):
    def test_family_manager_cannot_mutate_another_uploaders_owner_only_file(self):
        record = private_upload_record(uploaded_by_user_id="private-owner")
        db = FakeDatabase({"uploaded_files": [record]})
        actor = {"id": "manager-1", "email": "manager@example.com"}
        context = workspace_context(role="family_manager", user_id="project-owner")

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(upload_routes, "resolve_workspace_context", return_value=context),
        ):
            with self.assertRaises(HTTPException) as raised:
                upload_routes.update_upload_privacy(
                    str(record["_id"]),
                    upload_routes.UploadPrivacyUpdatePayload(
                        visibility_scope="household_private",
                        privacy_classification="household_private",
                    ),
                    current_user=actor,
                )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(db["uploaded_files"].update_calls, [])

    def test_account_disabled_upload_blocks_read_and_management(self):
        record = private_upload_record(account_access_enabled=False)
        db = FakeDatabase({"uploaded_files": [record]})
        actor = {"id": "owner-1", "email": "owner@example.com"}
        context = workspace_context()

        with (
            patch.object(upload_routes, "create_audit_log"),
            patch.object(upload_routes, "require_workspace_capability") as capability,
        ):
            with self.assertRaises(HTTPException) as read_error:
                upload_routes._require_upload_access(
                    str(record["_id"]),
                    db,
                    actor,
                    detail="test",
                )
        self.assertEqual(read_error.exception.status_code, 403)
        capability.assert_not_called()

        with patch.object(upload_routes, "resolve_workspace_context", return_value=context):
            with self.assertRaises(HTTPException) as management_error:
                upload_routes._require_upload_management_access(
                    str(record["_id"]),
                    db,
                    actor,
                    action="change privacy for",
                )
        self.assertEqual(management_error.exception.status_code, 403)

    def test_owner_account_deleted_marker_also_disables_access(self):
        record = private_upload_record(owner_account_deleted=True)
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}

        public = upload_routes._public_upload_record(
            record,
            context=context,
            current_user=actor,
        )

        self.assertFalse(public["account_access_enabled"])
        self.assertEqual(
            public["permissions"],
            {
                "can_preview": False,
                "can_download": False,
                "can_replace": False,
                "can_delete": False,
                "can_change_privacy": False,
                "can_manage": False,
            },
        )

    def test_legacy_upload_without_account_flag_remains_accessible(self):
        record = private_upload_record()
        record.pop("account_access_enabled")
        record.pop("owner_account_deleted")
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}

        with patch.object(
            upload_routes,
            "get_database",
            return_value=FakeDatabase({"vault_items": []}),
        ):
            self.assertTrue(
                upload_routes._can_access_upload_record(
                    upload_record=record,
                    context=context,
                    current_user=actor,
                )
            )

    def test_linked_draft_and_scheduled_vault_uploads_are_owner_only_in_helper_and_list(self):
        relative = {"id": "relative-1", "email": "relative@example.com"}
        owner = {"id": "owner-1", "email": "owner@example.com"}
        relative_context = linked_relative_context(link_status="accepted")
        owner_context = workspace_context()

        for release_state in ("draft", "scheduled"):
            with self.subTest(release_state=release_state):
                upload, _item, db = linked_vault_fixture(release_state=release_state)
                with patch.object(vault_service, "get_database", return_value=db):
                    with self.assertRaisesRegex(ValueError, "not released"):
                        vault_service.authorize_vault_upload_access(
                            str(upload["_id"]),
                            relative["id"],
                            authorized_project_id=upload["project_id"],
                            requesting_workspace_role="linked_relative",
                            relationship_scope="linked_relative",
                            link_status="accepted",
                            require_current=True,
                        )
                    owner_item = vault_service.authorize_vault_upload_access(
                        str(upload["_id"]),
                        owner["id"],
                        authorized_project_id=upload["project_id"],
                        requesting_workspace_role="billing_owner",
                        relationship_scope="household_member",
                        link_status="active",
                        require_current=True,
                    )

                    with (
                        patch.object(upload_routes, "get_database", return_value=db),
                        patch.object(
                            upload_routes,
                            "_resolve_upload_list_context",
                            return_value=relative_context,
                        ),
                    ):
                        relative_list = upload_routes.list_family_vault_items(
                            upload["family_id"],
                            include_linked_families=False,
                            vault_scope=None,
                            visibility_scope=None,
                            current_user=relative,
                        )
                    with (
                        patch.object(upload_routes, "get_database", return_value=db),
                        patch.object(
                            upload_routes,
                            "_resolve_upload_list_context",
                            return_value=owner_context,
                        ),
                    ):
                        owner_list = upload_routes.list_family_vault_items(
                            upload["family_id"],
                            include_linked_families=False,
                            vault_scope=None,
                            visibility_scope=None,
                            current_user=owner,
                        )

                self.assertEqual(owner_item["owner_user_id"], owner["id"])
                self.assertEqual(relative_list["count"], 0)
                self.assertEqual(owner_list["count"], 1)
                self.assertEqual(owner_list["items"][0]["id"], str(upload["_id"]))

    def test_linked_draft_and_scheduled_download_denies_relative_but_allows_owner(self):
        relative = {"id": "relative-1", "email": "relative@example.com"}
        owner = {"id": "owner-1", "email": "owner@example.com"}

        for release_state in ("draft", "scheduled"):
            with self.subTest(release_state=release_state):
                upload, _item, db = linked_vault_fixture(release_state=release_state)
                with (
                    patch.object(vault_service, "get_database", return_value=db),
                    patch.object(upload_routes, "get_database", return_value=db),
                    patch.object(
                        upload_routes,
                        "require_workspace_capability",
                        return_value=linked_relative_context(link_status="accepted"),
                    ),
                    patch.object(upload_routes, "create_audit_log"),
                    patch.object(
                        upload_routes,
                        "download_private_bytes",
                    ) as relative_object_read,
                ):
                    with self.assertRaises(HTTPException) as denied:
                        upload_routes.download_upload(
                            str(upload["_id"]),
                            admin_override=False,
                            viewer_project_id="",
                            current_user=relative,
                        )
                self.assertEqual(denied.exception.status_code, 403)
                relative_object_read.assert_not_called()

                with (
                    patch.object(vault_service, "get_database", return_value=db),
                    patch.object(upload_routes, "get_database", return_value=db),
                    patch.object(
                        upload_routes,
                        "require_workspace_capability",
                        return_value=workspace_context(),
                    ),
                    patch.object(
                        upload_routes,
                        "download_private_bytes",
                        return_value=b"owner-download",
                    ) as owner_object_read,
                ):
                    response = upload_routes.download_upload(
                        str(upload["_id"]),
                        admin_override=False,
                        viewer_project_id="",
                        current_user=owner,
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.body, b"owner-download")
                self.assertIn("attachment", response.headers["content-disposition"])
                self.assertNotIn("location", response.headers)
                owner_object_read.assert_called_once()

    def test_failed_modern_vault_link_cannot_bypass_draft_or_scheduled_release(self):
        relative = {"id": "relative-1", "email": "relative@example.com"}
        owner = {"id": "owner-1", "email": "owner@example.com"}
        relative_context = linked_relative_context(link_status="accepted")
        owner_context = workspace_context()

        for release_state in ("draft", "scheduled"):
            with self.subTest(release_state=release_state):
                record = private_upload_record(
                    vault_scope="linked_family",
                    vault_item_id=None,
                    vault_link_status="failed",
                    vault_link_error="temporary_link_failure",
                    visibility_scope="linked_family_shared",
                    privacy_scope="linked_family_shared",
                    privacy_classification="linked_family_shared",
                    customer_visible=True,
                    share_with_linked_families=True,
                    release_state=release_state,
                    reveal_at=(
                        "2999-01-01T00:00:00+00:00"
                        if release_state == "scheduled"
                        else None
                    ),
                )
                db = FakeDatabase({"uploaded_files": [record], "vault_items": []})

                with patch.object(upload_routes, "get_database", return_value=db):
                    self.assertFalse(
                        upload_routes._can_access_linked_vault_upload(
                            upload_record=record,
                            context=relative_context,
                            current_user=relative,
                            require_current=True,
                        )
                    )
                    self.assertTrue(
                        upload_routes._can_access_linked_vault_upload(
                            upload_record=record,
                            context=owner_context,
                            current_user=owner,
                            require_current=True,
                        )
                    )

                    with patch.object(
                        upload_routes,
                        "_resolve_upload_list_context",
                        return_value=relative_context,
                    ):
                        relative_list = upload_routes.list_family_vault_items(
                            record["family_id"],
                            include_linked_families=False,
                            vault_scope=None,
                            visibility_scope=None,
                            current_user=relative,
                        )
                    with patch.object(
                        upload_routes,
                        "_resolve_upload_list_context",
                        return_value=owner_context,
                    ):
                        owner_list = upload_routes.list_family_vault_items(
                            record["family_id"],
                            include_linked_families=False,
                            vault_scope=None,
                            visibility_scope=None,
                            current_user=owner,
                        )

                    with (
                        patch.object(
                            upload_routes,
                            "require_workspace_capability",
                            return_value=relative_context,
                        ),
                        patch.object(upload_routes, "create_audit_log"),
                        patch.object(
                            upload_routes,
                            "download_private_bytes",
                        ) as relative_object_read,
                    ):
                        with self.assertRaises(HTTPException) as denied:
                            upload_routes.download_upload(
                                str(record["_id"]),
                                admin_override=False,
                                viewer_project_id="",
                                current_user=relative,
                            )
                    relative_object_read.assert_not_called()

                    with (
                        patch.object(
                            upload_routes,
                            "require_workspace_capability",
                            return_value=owner_context,
                        ),
                        patch.object(
                            upload_routes,
                            "download_private_bytes",
                            return_value=b"owner-recovery",
                        ) as owner_object_read,
                    ):
                        owner_response = upload_routes.download_upload(
                            str(record["_id"]),
                            admin_override=False,
                            viewer_project_id="",
                            current_user=owner,
                        )

                self.assertEqual(relative_list["count"], 0)
                self.assertEqual(owner_list["count"], 1)
                self.assertEqual(denied.exception.status_code, 403)
                self.assertEqual(owner_response.status_code, 200)
                self.assertEqual(owner_response.body, b"owner-recovery")
                owner_object_read.assert_called_once()

    def test_approved_link_status_allows_released_linked_relative(self):
        relative = {"id": "relative-1", "email": "relative@example.com"}
        context = linked_relative_context(link_status="approved")
        upload, _item, db = linked_vault_fixture(release_state="released")

        with patch.object(vault_service, "get_database", return_value=db):
            item = vault_service.authorize_vault_upload_access(
                str(upload["_id"]),
                relative["id"],
                authorized_project_id=upload["project_id"],
                requesting_workspace_role="linked_relative",
                relationship_scope="linked_relative",
                link_status="approved",
                require_current=True,
            )
            with (
                patch.object(upload_routes, "get_database", return_value=db),
                patch.object(
                    upload_routes,
                    "require_workspace_capability",
                    return_value=context,
                ),
                patch.object(
                    upload_routes,
                    "download_private_bytes",
                    return_value=b"approved-relative",
                ) as object_read,
            ):
                response = upload_routes.download_upload(
                    str(upload["_id"]),
                    admin_override=False,
                    viewer_project_id="",
                    current_user=relative,
                )

        self.assertEqual(item["id"], str(_item["_id"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"approved-relative")
        object_read.assert_called_once()

    def test_linked_viewer_preview_proxies_authorized_r2_bytes_inline(self):
        upload, _prior, _item, db = linked_viewer_fixture()
        viewer = {"id": "viewer-user", "email": "viewer@example.com"}
        body = b"linked-viewer-private-bytes"

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "require_workspace_capability",
                return_value=linked_viewer_context(),
            ) as capability,
            patch.object(
                upload_routes,
                "list_linked_family_ids",
                return_value=["viewer-family", "source-family"],
            ) as linked_families,
            patch.object(
                upload_routes,
                "download_private_bytes",
                return_value=body,
            ) as object_read,
        ):
            response = upload_routes.preview_upload(
                str(upload["_id"]),
                viewer_project_id="viewer-project",
                current_user=viewer,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, body)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertNotIn("location", response.headers)
        capability.assert_called_once()
        self.assertEqual(capability.call_args.kwargs["project_id"], "viewer-project")
        self.assertEqual(
            capability.call_args.kwargs["capabilities"],
            (upload_routes.LINKED_FAMILY_VAULT_CAPABILITY,),
        )
        linked_families.assert_called_once_with("viewer-family")
        object_read.assert_called_once_with(
            key=upload["storage_key"],
            max_bytes=upload_routes.EVIDENCE_MAX_BYTES,
        )

    def test_linked_viewer_download_streams_authorized_r2_bytes(self):
        upload, _prior, _item, db = linked_viewer_fixture()
        viewer = {"id": "viewer-user", "email": "viewer@example.com"}
        body = b"linked-viewer-download"

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "require_workspace_capability",
                return_value=linked_viewer_context(),
            ),
            patch.object(
                upload_routes,
                "list_linked_family_ids",
                return_value=["viewer-family", "source-family"],
            ),
            patch.object(
                upload_routes,
                "download_private_bytes",
                return_value=body,
            ) as object_read,
        ):
            response = upload_routes.download_upload(
                str(upload["_id"]),
                admin_override=False,
                viewer_project_id="viewer-project",
                current_user=viewer,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, body)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertNotIn("location", response.headers)
        object_read.assert_called_once_with(
            key=upload["storage_key"],
            max_bytes=upload_routes.EVIDENCE_MAX_BYTES,
        )

    def test_linked_viewer_versions_returns_only_current_with_read_only_permissions(self):
        current, prior, _item, db = linked_viewer_fixture(with_prior=True)
        viewer = {"id": "viewer-user", "email": "viewer@example.com"}

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "require_workspace_capability",
                return_value=linked_viewer_context(),
            ),
            patch.object(
                upload_routes,
                "list_linked_family_ids",
                return_value=["viewer-family", "source-family"],
            ),
            patch.object(upload_routes, "create_audit_log"),
            patch.object(upload_routes, "download_private_bytes") as object_read,
        ):
            payload = upload_routes.list_upload_versions(
                str(current["_id"]),
                viewer_project_id="viewer-project",
                current_user=viewer,
            )

        self.assertIsNotNone(prior)
        self.assertEqual(payload["root_upload_id"], str(prior["_id"]))
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["versions"][0]["id"], str(current["_id"]))
        self.assertNotEqual(payload["versions"][0]["id"], str(prior["_id"]))
        self.assertEqual(
            payload["versions"][0]["permissions"],
            {
                "can_preview": True,
                "can_download": True,
                "can_replace": False,
                "can_delete": False,
                "can_change_privacy": False,
                "can_manage": False,
            },
        )
        object_read.assert_not_called()

    def test_linked_viewer_unreleased_or_unshared_upload_never_reaches_storage(self):
        viewer = {"id": "viewer-user", "email": "viewer@example.com"}
        cases = (
            ("draft", "draft", True),
            ("scheduled", "scheduled", True),
            ("share_disabled", "released", False),
        )

        for label, release_state, explicitly_shared in cases:
            with self.subTest(policy=label):
                upload, _prior, _item, db = linked_viewer_fixture(
                    release_state=release_state,
                    explicitly_shared=explicitly_shared,
                )
                with (
                    patch.object(upload_routes, "get_database", return_value=db),
                    patch.object(vault_service, "get_database", return_value=db),
                    patch.object(
                        upload_routes,
                        "require_workspace_capability",
                        return_value=linked_viewer_context(),
                    ),
                    patch.object(
                        upload_routes,
                        "list_linked_family_ids",
                        return_value=["viewer-family", "source-family"],
                    ),
                    patch.object(upload_routes, "create_audit_log"),
                    patch.object(upload_routes, "download_private_bytes") as object_read,
                ):
                    with self.assertRaises(HTTPException) as preview_denied:
                        upload_routes.preview_upload(
                            str(upload["_id"]),
                            viewer_project_id="viewer-project",
                            current_user=viewer,
                        )
                    with self.assertRaises(HTTPException) as download_denied:
                        upload_routes.download_upload(
                            str(upload["_id"]),
                            admin_override=False,
                            viewer_project_id="viewer-project",
                            current_user=viewer,
                        )

                self.assertEqual(preview_denied.exception.status_code, 403)
                self.assertEqual(download_denied.exception.status_code, 403)
                object_read.assert_not_called()

    def test_scheduled_upload_with_nonexistent_vault_item_denies_nonowner_before_storage(self):
        missing_item_id = ObjectId()
        record = private_upload_record(
            vault_scope="linked_family",
            vault_item_id=str(missing_item_id),
            vault_link_status="failed",
            visibility_scope="linked_family_shared",
            privacy_scope="linked_family_shared",
            privacy_classification="linked_family_shared",
            customer_visible=True,
            share_with_linked_families=True,
            release_state="scheduled",
            reveal_at="2999-01-01T00:00:00+00:00",
        )
        db = FakeDatabase({"uploaded_files": [record], "vault_items": []})
        relative = {"id": "relative-1", "email": "relative@example.com"}
        context = linked_relative_context(link_status="accepted")

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
        ):
            self.assertFalse(
                upload_routes._can_access_upload_record(
                    upload_record=record,
                    context=context,
                    current_user=relative,
                )
            )
            with (
                patch.object(
                    upload_routes,
                    "require_workspace_capability",
                    return_value=context,
                ),
                patch.object(upload_routes, "create_audit_log"),
                patch.object(upload_routes, "download_private_bytes") as object_read,
            ):
                with self.assertRaises(HTTPException) as denied:
                    upload_routes.download_upload(
                        str(record["_id"]),
                        admin_override=False,
                        viewer_project_id="",
                        current_user=relative,
                    )

        self.assertEqual(denied.exception.status_code, 403)
        object_read.assert_not_called()

    def test_missing_or_pending_membership_link_denies_linked_relative(self):
        relative = {"id": "relative-1", "email": "relative@example.com"}
        synthesized_missing_context = linked_relative_context(include_membership=False)
        synthesized_missing_context["relationship_scope"] = "household_member"
        cases = (
            ("missing", linked_relative_context(include_membership=False), ""),
            ("missing_with_synthesized_relationship", synthesized_missing_context, ""),
            ("pending", linked_relative_context(link_status="pending"), "pending"),
        )

        for label, context, canonical_link_status in cases:
            with self.subTest(link_status=label):
                upload, _item, db = linked_vault_fixture(release_state="released")
                self.assertEqual(
                    upload_routes._context_link_status(context),
                    canonical_link_status,
                )
                with patch.object(vault_service, "get_database", return_value=db):
                    with self.assertRaisesRegex(ValueError, "Access denied"):
                        vault_service.authorize_vault_upload_access(
                            str(upload["_id"]),
                            relative["id"],
                            authorized_project_id=upload["project_id"],
                            requesting_workspace_role="linked_relative",
                            relationship_scope="linked_relative",
                            link_status=canonical_link_status,
                            require_current=True,
                        )
                    with patch.object(
                        upload_routes,
                        "require_workspace_capability",
                        return_value=context,
                    ):
                        with self.assertRaises(HTTPException) as denied:
                            upload_routes._require_upload_access(
                                str(upload["_id"]),
                                db,
                                relative,
                                detail="test linked access",
                            )
                self.assertEqual(denied.exception.status_code, 403)

    def test_customer_preview_proxies_r2_bytes_with_private_response_headers(self):
        record = private_upload_record(
            storage_key="private-uploads/v1/private_media/preview/photo.jpg",
            size_bytes=128,
        )
        db = FakeDatabase({"uploaded_files": [record]})
        actor = {"id": "owner-1", "email": "owner@example.com"}
        body = b"private-r2-image-bytes"

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                return_value=(record, workspace_context()),
            ),
            patch.object(
                upload_routes,
                "download_private_bytes",
                return_value=body,
            ) as object_read,
        ):
            response = upload_routes.preview_upload(
                str(record["_id"]),
                current_user=actor,
            )

        self.assertEqual(response.body, body)
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("inline", response.headers["content-disposition"])
        object_read.assert_called_once()

    def test_private_content_disposition_supports_unicode_without_header_injection(self):
        header = upload_routes._private_content_disposition(
            'family\r\nrecord-Élodie.pdf',
            disposition="attachment",
        )

        self.assertTrue(header.startswith("attachment;"))
        self.assertNotIn("\r", header)
        self.assertNotIn("\n", header)
        self.assertIn("filename*=UTF-8''", header)

    def test_customer_preview_denial_happens_before_private_object_read(self):
        record = private_upload_record()
        db = FakeDatabase({"uploaded_files": [record]})
        actor = {"id": "relative-1", "email": "relative@example.com"}

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                side_effect=HTTPException(status_code=403, detail="denied"),
            ),
            patch.object(upload_routes, "download_private_bytes") as object_read,
        ):
            with self.assertRaises(HTTPException) as denied:
                upload_routes.preview_upload(
                    str(record["_id"]),
                    current_user=actor,
                )

        self.assertEqual(denied.exception.status_code, 403)
        object_read.assert_not_called()

    def test_internal_admin_cannot_use_generic_customer_preview_for_owner_private_file(self):
        record = private_upload_record(uploaded_by_user_id="customer-owner")
        db = FakeDatabase({"uploaded_files": [record], "vault_items": []})
        admin = {"id": "admin-1", "email": "admin@example.com", "role": "admin"}
        admin_context = workspace_context(user_id="customer-owner", is_admin=True)

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "require_workspace_capability",
                return_value=admin_context,
            ),
            patch.object(upload_routes, "create_audit_log"),
            patch.object(upload_routes, "download_private_bytes") as object_read,
        ):
            with self.assertRaises(HTTPException) as denied:
                upload_routes.preview_upload(
                    str(record["_id"]),
                    current_user=admin,
                )

        self.assertEqual(denied.exception.status_code, 403)
        object_read.assert_not_called()

    def test_admin_preview_restricts_categories_and_requires_audit_before_read(self):
        admin = {"id": "admin-1", "email": "admin@example.com", "role": "admin"}
        admin_context = workspace_context(is_admin=True)

        vault_file = private_upload_record()
        vault_db = FakeDatabase({"uploaded_files": [vault_file]})
        with (
            patch.object(upload_routes, "get_database", return_value=vault_db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(vault_file, admin_context),
            ),
            patch.object(upload_routes, "write_audit_log") as vault_audit,
            patch.object(upload_routes, "download_private_bytes") as vault_object_read,
        ):
            with self.assertRaises(HTTPException) as category_denied:
                upload_routes.preview_upload_for_admin_review(
                    str(vault_file["_id"]),
                    current_user=admin,
                )
        self.assertEqual(category_denied.exception.status_code, 403)
        vault_audit.assert_not_called()
        vault_object_read.assert_not_called()

        evidence = private_upload_record(
            category="verification_evidence",
            asset_type="verification_document",
            verification_type="government_id",
            evidence_kind="government_id",
            content_type="application/pdf",
            original_filename="identity.pdf",
        )
        evidence_db = FakeDatabase({"uploaded_files": [evidence]})
        with (
            patch.object(upload_routes, "get_database", return_value=evidence_db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(evidence, admin_context),
            ),
            patch.object(
                upload_routes,
                "write_audit_log",
                side_effect=RuntimeError("audit unavailable"),
            ) as evidence_audit,
            patch.object(upload_routes, "download_private_bytes") as evidence_object_read,
        ):
            with self.assertRaises(HTTPException) as audit_denied:
                upload_routes.preview_upload_for_admin_review(
                    str(evidence["_id"]),
                    current_user=admin,
                )
        self.assertEqual(audit_denied.exception.status_code, 503)
        evidence_audit.assert_called_once()
        evidence_object_read.assert_not_called()

    def test_government_id_verification_cannot_be_reclassified_public(self):
        record = private_upload_record(
            category="verification_evidence",
            asset_type="verification_document",
            verification_type="government_id",
            evidence_kind="government_id",
        )
        db = FakeDatabase({"uploaded_files": [record]})
        actor = {"id": "owner-1", "email": "owner@example.com"}

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "resolve_workspace_context",
                return_value=workspace_context(),
            ),
        ):
            with self.assertRaises(HTTPException) as denied:
                upload_routes.update_upload_privacy(
                    str(record["_id"]),
                    upload_routes.UploadPrivacyUpdatePayload(
                        visibility_scope="public_memorial",
                        privacy_classification="public_memorial",
                    ),
                    current_user=actor,
                )

        self.assertEqual(denied.exception.status_code, 403)
        self.assertEqual(db["uploaded_files"].update_calls, [])

    def test_admin_cannot_reclassify_government_id_verification_public(self):
        record = private_upload_record(
            category="verification_evidence",
            asset_type="verification_document",
            verification_type="government_id",
            evidence_kind="government_id",
        )
        db = FakeDatabase({"uploaded_files": [record]})
        admin = {"id": "admin-1", "email": "admin@example.com", "role": "admin"}

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "resolve_workspace_context",
                return_value=workspace_context(is_admin=True),
            ),
        ):
            with self.assertRaises(HTTPException) as denied:
                upload_routes.update_upload_privacy(
                    str(record["_id"]),
                    upload_routes.UploadPrivacyUpdatePayload(
                        visibility_scope="public_memorial",
                        privacy_classification="public_memorial",
                        customer_visible=True,
                    ),
                    current_user=admin,
                )

        self.assertEqual(denied.exception.status_code, 403)
        self.assertEqual(db["uploaded_files"].update_calls, [])

    def test_pdf_bytes_disguised_as_jpeg_are_rejected(self):
        forged = upload_file(
            filename="forged.jpg",
            content_type="image/jpeg",
            payload=b"%PDF-1.7\nnot-a-jpeg",
        )

        with self.assertRaises(HTTPException) as raised:
            upload_routes._validate_upload_file(
                forged,
                allowed_content_types=upload_routes.PHOTO_ALLOWED_CONTENT_TYPES,
                allowed_extensions=upload_routes.PHOTO_ALLOWED_EXTENSIONS,
                max_bytes=upload_routes.PHOTO_MAX_BYTES,
                label="Vault photo",
            )

        self.assertEqual(raised.exception.status_code, 400)

    def test_arbitrary_bytes_disguised_as_pdf_are_rejected(self):
        forged = upload_file(
            filename="forged.pdf",
            content_type="application/pdf",
            payload=b"this is not a PDF document",
        )

        with self.assertRaises(HTTPException) as raised:
            upload_routes._validate_upload_file(
                forged,
                allowed_content_types=upload_routes.EVIDENCE_ALLOWED_CONTENT_TYPES,
                allowed_extensions=upload_routes.EVIDENCE_ALLOWED_EXTENSIONS,
                max_bytes=upload_routes.EVIDENCE_MAX_BYTES,
                label="Vault document",
            )

        self.assertEqual(raised.exception.status_code, 400)

    def test_upload_status_reports_ready_processing_quarantine_and_blocked_truthfully(self):
        cases = (
            (private_upload_record(), "ready", True),
            (private_upload_record(scan_status="pending"), "processing", False),
            (
                private_upload_record(scan_status="infected", quarantined=True),
                "quarantined",
                False,
            ),
            (private_upload_record(account_access_enabled=False), "blocked", False),
        )

        with patch.object(upload_routes.settings, "environment", "development"):
            for record, expected_state, download_ready in cases:
                with self.subTest(expected_state=expected_state):
                    payload = upload_routes._upload_status_payload(record)
                    self.assertEqual(payload["state"], expected_state)
                    self.assertEqual(payload["download_ready"], download_ready)
                    if expected_state in {"quarantined", "blocked"}:
                        self.assertNotIn("success", payload["message"].lower())

    def test_clean_review_upload_reports_pending_review_not_completed(self):
        record = private_upload_record(
            category="verification_evidence",
            asset_type="verification_document",
            verification_status="pending",
        )

        with patch.object(upload_routes.settings, "environment", "development"):
            payload = upload_routes._upload_status_payload(record)

        self.assertEqual(payload["state"], "pending_review")
        self.assertTrue(payload["download_ready"])

    def test_quarantined_vault_create_uses_security_status_as_top_level_message(self):
        quarantined = private_upload_record(
            scan_status="infected",
            quarantined=True,
        )
        db = FakeDatabase({"uploaded_files": []})
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}
        file = upload_file(
            filename="portrait.jpg",
            content_type="image/jpeg",
            payload=b"\xff\xd8\xff\xe0vault-image",
        )

        with (
            patch.object(upload_routes, "require_workspace_capability", return_value=context),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(upload_routes, "_enforce_workspace_upload_limit"),
            patch.object(upload_routes, "_enforce_workspace_storage_limit"),
            patch.object(
                upload_routes,
                "_begin_upload_idempotency",
                return_value=("key-hash", "fingerprint", None),
            ),
            patch.object(
                upload_routes,
                "store_private_media_upload",
                AsyncMock(return_value=quarantined),
            ),
            patch.object(
                upload_routes,
                "_scan_and_quarantine_upload",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(
                upload_routes,
                "_ensure_upload_vault_linkage",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(upload_routes, "_finish_upload_idempotency"),
            patch.object(upload_routes.settings, "environment", "production"),
        ):
            response = asyncio.run(
                upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="member-1",
                    project_id="project-1",
                    asset_type="vault_photo",
                    privacy_scope="private_to_owner",
                    vault_scope="household",
                    vault_item_id="",
                    release_state="released",
                    reveal_at="",
                    consent_attested=True,
                    authority_attested=True,
                    file=file,
                    idempotency_key="vault-idempotency-key",
                    current_user=actor,
                )
            )

        self.assertEqual(response["upload_status"]["state"], "quarantined")
        self.assertEqual(response["message"], response["upload_status"]["message"])
        self.assertNotIn("success", response["message"].lower())

    def test_linked_family_create_persists_scope_visibility_and_share_policy(self):
        linked_upload = private_upload_record(
            vault_scope="linked_family",
            visibility_scope="linked_family_shared",
            privacy_scope="linked_family_shared",
            privacy_classification="linked_family_shared",
            customer_visible=True,
            share_with_linked_families=True,
            release_state="released",
        )
        db = FakeDatabase({"uploaded_files": []})
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}
        file = upload_file(
            filename="linked-family.jpg",
            content_type="image/jpeg",
            payload=b"\xff\xd8\xff\xe0linked-family-image",
        )
        store = AsyncMock(return_value=linked_upload)

        with (
            patch.object(upload_routes, "require_workspace_capability", return_value=context),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "list_linked_family_ids",
                return_value=["family-1", "family-2"],
            ),
            patch.object(upload_routes, "_enforce_workspace_upload_limit"),
            patch.object(upload_routes, "_enforce_workspace_storage_limit"),
            patch.object(
                upload_routes,
                "_begin_upload_idempotency",
                return_value=("linked-key-hash", "linked-fingerprint", None),
            ),
            patch.object(upload_routes, "store_private_media_upload", store),
            patch.object(
                upload_routes,
                "_scan_and_quarantine_upload",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(
                upload_routes,
                "_ensure_upload_vault_linkage",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(upload_routes, "_finish_upload_idempotency"),
        ):
            response = asyncio.run(
                upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="member-1",
                    project_id="project-1",
                    asset_type="vault_photo",
                    privacy_scope="linked_family_shared",
                    vault_scope="linked_family",
                    vault_item_id="",
                    release_state="released",
                    reveal_at="",
                    consent_attested=True,
                    authority_attested=True,
                    file=file,
                    idempotency_key="linked-family-create-key",
                    current_user=actor,
                )
            )

        store.assert_awaited_once()
        stored_fields = store.await_args.kwargs
        self.assertEqual(stored_fields["vault_scope"], "linked_family")
        self.assertEqual(stored_fields["privacy_scope"], "linked_family_shared")
        self.assertTrue(stored_fields["share_with_linked_families"])
        self.assertEqual(response["upload"]["vault_scope"], "linked_family")
        self.assertEqual(response["upload"]["privacy_classification"], "linked_family_shared")
        self.assertTrue(response["upload"]["share_with_linked_families"])

    def test_linked_family_create_rejects_non_shared_visibility_before_store(self):
        db = FakeDatabase({"uploaded_files": []})
        actor = {"id": "owner-1", "email": "owner@example.com"}
        file = upload_file(
            filename="not-shared.jpg",
            content_type="image/jpeg",
            payload=b"\xff\xd8\xff\xe0not-shared-image",
        )
        store = AsyncMock()

        with (
            patch.object(
                upload_routes,
                "require_workspace_capability",
                return_value=workspace_context(),
            ),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(upload_routes, "store_private_media_upload", store),
        ):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(
                    upload_routes.upload_private_media(
                        family_id="family-1",
                        member_id="member-1",
                        project_id="project-1",
                        asset_type="vault_photo",
                        privacy_scope="household_private",
                        vault_scope="linked_family",
                        vault_item_id="",
                        release_state="released",
                        reveal_at="",
                        consent_attested=True,
                        authority_attested=True,
                        file=file,
                        idempotency_key="linked-family-policy-key",
                        current_user=actor,
                    )
                )

        self.assertEqual(denied.exception.status_code, 400)
        store.assert_not_awaited()

    def test_linked_family_create_requires_independent_household_link_entitlement(self):
        db = FakeDatabase({"uploaded_files": []})
        context = workspace_context()
        context["resolved_entitlements"]["can_link_households"] = False
        actor = {"id": "owner-1", "email": "owner@example.com"}
        file = upload_file(
            filename="linked-family.jpg",
            content_type="image/jpeg",
            payload=b"\xff\xd8\xff\xe0linked-family-image",
        )
        store = AsyncMock()

        with (
            patch.object(upload_routes, "require_workspace_capability", return_value=context),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "list_linked_family_ids",
                return_value=["family-1", "family-2"],
            ) as linked_families,
            patch.object(upload_routes, "store_private_media_upload", store),
        ):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(
                    upload_routes.upload_private_media(
                        family_id="family-1",
                        member_id="member-1",
                        project_id="project-1",
                        asset_type="vault_photo",
                        privacy_scope="linked_family_shared",
                        vault_scope="linked_family",
                        vault_item_id="",
                        release_state="released",
                        reveal_at="",
                        consent_attested=True,
                        authority_attested=True,
                        file=file,
                        idempotency_key="missing-link-entitlement-key",
                        current_user=actor,
                    )
                )

        self.assertEqual(denied.exception.status_code, 403)
        linked_families.assert_not_called()
        store.assert_not_awaited()

    def test_linked_family_create_requires_an_accepted_household_link(self):
        db = FakeDatabase({"uploaded_files": []})
        actor = {"id": "owner-1", "email": "owner@example.com"}
        file = upload_file(
            filename="linked-family.jpg",
            content_type="image/jpeg",
            payload=b"\xff\xd8\xff\xe0linked-family-image",
        )
        store = AsyncMock()

        with (
            patch.object(
                upload_routes,
                "require_workspace_capability",
                return_value=workspace_context(),
            ),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "list_linked_family_ids",
                return_value=["family-1"],
            ) as linked_families,
            patch.object(upload_routes, "store_private_media_upload", store),
        ):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(
                    upload_routes.upload_private_media(
                        family_id="family-1",
                        member_id="member-1",
                        project_id="project-1",
                        asset_type="vault_photo",
                        privacy_scope="linked_family_shared",
                        vault_scope="linked_family",
                        vault_item_id="",
                        release_state="released",
                        reveal_at="",
                        consent_attested=True,
                        authority_attested=True,
                        file=file,
                        idempotency_key="missing-accepted-link-key",
                        current_user=actor,
                    )
                )

        self.assertEqual(denied.exception.status_code, 403)
        linked_families.assert_called_once_with("family-1")
        store.assert_not_awaited()

    def test_household_vault_document_create_allows_family_without_member(self):
        document_record = private_upload_record(
            member_id="",
            asset_type="vault_document",
            vault_scope="household",
            visibility_scope="household_private",
            privacy_scope="household_private",
            privacy_classification="household_private",
            customer_visible=True,
            content_type="application/pdf",
            original_filename="family-record.pdf",
        )
        db = FakeDatabase({"uploaded_files": []})
        context = workspace_context()
        context["member"] = None
        actor = {"id": "owner-1", "email": "owner@example.com"}
        file = upload_file(
            filename="family-record.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nfamily household record",
        )
        store = AsyncMock(return_value=document_record)

        with (
            patch.object(upload_routes, "require_workspace_capability", return_value=context),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(upload_routes, "_enforce_workspace_upload_limit"),
            patch.object(upload_routes, "_enforce_workspace_storage_limit"),
            patch.object(
                upload_routes,
                "_begin_upload_idempotency",
                return_value=("household-doc-key", "household-doc-fingerprint", None),
            ),
            patch.object(upload_routes, "store_private_media_upload", store),
            patch.object(
                upload_routes,
                "_scan_and_quarantine_upload",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(
                upload_routes,
                "_ensure_upload_vault_linkage",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(upload_routes, "_finish_upload_idempotency"),
        ):
            response = asyncio.run(
                upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="",
                    project_id="project-1",
                    asset_type="vault_document",
                    privacy_scope="household_private",
                    vault_scope="household",
                    vault_item_id="",
                    release_state="released",
                    reveal_at="",
                    consent_attested=True,
                    authority_attested=True,
                    file=file,
                    idempotency_key="household-document-create-key",
                    current_user=actor,
                )
            )

        store.assert_awaited_once()
        self.assertEqual(store.await_args.kwargs["family_id"], "family-1")
        self.assertEqual(store.await_args.kwargs["member_id"], "")
        self.assertEqual(store.await_args.kwargs["asset_type"], "vault_document")
        self.assertIsNone(response["member_id"])
        self.assertEqual(response["family_id"], "family-1")

    def test_public_record_exposes_version_fields_and_owner_permissions(self):
        root_id = ObjectId()
        prior_id = ObjectId()
        record = private_upload_record(
            version=3,
            version_group_id=str(root_id),
            replaces_upload_id=str(prior_id),
            replacement_status="current",
            relative_path="private/internal/path.jpg",
            scan_detail="internal scanner detail",
            idempotency_key_hash="must-not-leak",
            idempotency_fingerprint="must-not-leak",
        )
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}

        with (
            patch.object(upload_routes.settings, "environment", "production"),
            patch.object(
                upload_routes,
                "get_database",
                return_value=FakeDatabase({"vault_items": []}),
            ),
        ):
            public = upload_routes._public_upload_record(
                record,
                context=context,
                current_user=actor,
            )

        self.assertEqual(public["version"], 3)
        self.assertEqual(public["version_group_id"], str(root_id))
        self.assertEqual(public["root_upload_id"], str(root_id))
        self.assertEqual(public["replaces_upload_id"], str(prior_id))
        self.assertTrue(public["is_current_version"])
        self.assertEqual(
            public["permissions"],
            {
                "can_preview": True,
                "can_download": True,
                "can_replace": True,
                "can_delete": True,
                # Privacy changes require a canonical Vault item even though
                # the uploader retains delete/replace recovery permissions.
                "can_change_privacy": False,
                "can_manage": True,
            },
        )
        self.assertNotIn("relative_path", public)
        self.assertNotIn("scan_detail", public)
        self.assertNotIn("idempotency_key_hash", public)
        self.assertNotIn("idempotency_fingerprint", public)

    def test_legacy_public_version_fields_default_to_version_one_and_own_root(self):
        record = private_upload_record()
        record.pop("version")
        record.pop("version_group_id")
        serialized = serialize_upload_record(record)

        self.assertEqual(serialized["version"], 1)
        self.assertEqual(serialized["version_group_id"], str(record["_id"]))
        self.assertEqual(serialized["root_upload_id"], str(record["_id"]))
        self.assertTrue(serialized["is_current_version"])

    def test_superseded_or_pending_replacement_disables_another_replacement(self):
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}
        cases = (
            private_upload_record(
                is_current_version=False,
                replacement_status="superseded",
                superseded_by_upload_id=str(ObjectId()),
            ),
            private_upload_record(pending_replacement_upload_id=str(ObjectId())),
        )

        with (
            patch.object(upload_routes.settings, "environment", "production"),
            patch.object(
                upload_routes,
                "get_database",
                return_value=FakeDatabase({"vault_items": []}),
            ),
        ):
            for record in cases:
                with self.subTest(replacement_status=record.get("replacement_status")):
                    permissions = upload_routes._public_upload_record(
                        record,
                        context=context,
                        current_user=actor,
                    )["permissions"]
                    self.assertFalse(permissions["can_replace"])
                    self.assertTrue(permissions["can_delete"])

    def test_replacement_claim_is_compare_and_set(self):
        prior = private_upload_record()
        db = FakeDatabase({"uploaded_files": [prior]})

        upload_routes._claim_upload_replacement(
            db=db,
            upload_record=prior,
            claim_token="claim-one",
        )
        self.assertEqual(prior["replacement_claim_token"], "claim-one")

        with self.assertRaises(HTTPException) as raised:
            upload_routes._claim_upload_replacement(
                db=db,
                upload_record=prior,
                claim_token="claim-two",
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(prior["replacement_claim_token"], "claim-one")

    def test_ready_vault_replacement_atomically_marks_prior_superseded(self):
        prior = private_upload_record(replacement_claim_token="claim-one")
        replacement = private_upload_record(
            uploaded_by_user_id="owner-1",
            version=2,
            version_group_id=prior["version_group_id"],
            replaces_upload_id=str(prior["_id"]),
            replacement_status="pending",
            is_current_version=False,
        )
        db = FakeDatabase({"uploaded_files": [prior, replacement]})

        with patch.object(upload_routes.settings, "environment", "production"):
            result = upload_routes._apply_replacement_state(
                db=db,
                prior_upload=prior,
                replacement=replacement,
                claim_token="claim-one",
            )

        self.assertFalse(prior["is_current_version"])
        self.assertEqual(prior["replacement_status"], "superseded")
        self.assertEqual(prior["superseded_by_upload_id"], str(replacement["_id"]))
        self.assertIsNone(prior["replacement_claim_token"])
        self.assertTrue(replacement["is_current_version"])
        self.assertEqual(replacement["replacement_status"], "current")
        self.assertEqual(str(result["_id"]), str(replacement["_id"]))

    def test_quarantined_replacement_does_not_supersede_current_version(self):
        prior = private_upload_record(replacement_claim_token="claim-one")
        replacement = private_upload_record(
            version=2,
            version_group_id=prior["version_group_id"],
            replaces_upload_id=str(prior["_id"]),
            replacement_status="pending",
            is_current_version=False,
            scan_status="infected",
            quarantined=True,
        )
        db = FakeDatabase({"uploaded_files": [prior, replacement]})

        with patch.object(upload_routes.settings, "environment", "production"):
            result = upload_routes._apply_replacement_state(
                db=db,
                prior_upload=prior,
                replacement=replacement,
                claim_token="claim-one",
            )

        self.assertTrue(prior["is_current_version"])
        self.assertNotIn("superseded_by_upload_id", prior)
        self.assertIsNone(prior["replacement_claim_token"])
        self.assertFalse(replacement["is_current_version"])
        self.assertEqual(replacement["replacement_status"], "blocked")
        self.assertEqual(str(result["_id"]), str(replacement["_id"]))

    def test_delete_linked_current_version_tombstones_before_r2_and_promotes_prior(self):
        item_id = ObjectId()
        prior_id = ObjectId()
        current_id = ObjectId()
        prior = private_upload_record(
            _id=prior_id,
            vault_item_id=str(item_id),
            version=1,
            version_group_id=str(prior_id),
            is_current_version=False,
            replacement_status="superseded",
            superseded_by_upload_id=str(current_id),
            replaced_by_upload_id=str(current_id),
        )
        current = private_upload_record(
            _id=current_id,
            vault_item_id=str(item_id),
            version=2,
            version_group_id=str(prior_id),
            replaces_upload_id=str(prior_id),
            is_current_version=True,
            replacement_status="current",
        )
        item = {
            "_id": item_id,
            "project_id": current["project_id"],
            "family_id": current["family_id"],
            "member_id": current["member_id"],
            "owner_user_id": "owner-1",
            "privacy": "private_owner",
            "release_state": "released",
            "status": "active",
            "access_enabled": True,
            "upload_id": str(current_id),
            "current_upload_id": str(current_id),
            "asset_version": 2,
            "asset_versions": [
                {"version": 1, "upload_id": str(prior_id)},
                {
                    "version": 2,
                    "upload_id": str(current_id),
                    "replaces_upload_id": str(prior_id),
                },
            ],
        }
        db = FakeDatabase(
            {
                "uploaded_files": [prior, current],
                "vault_items": [item],
                "vault_access_grants": [],
                "vault_release_rules": [],
                "vault_audit_events": [],
                "upload_deletion_tombstones": [],
            }
        )
        actor = {"id": "owner-1", "email": "owner@example.com"}
        context = workspace_context()
        events = []
        real_tombstone = vault_service.tombstone_vault_upload_version
        real_metadata_delete = db["uploaded_files"].delete_one

        def instrumented_tombstone(*args, **kwargs):
            events.append("vault_tombstone")
            return real_tombstone(*args, **kwargs)

        def instrumented_r2_delete(*, key):
            self.assertEqual(key, current["storage_key"])
            events.append("r2_delete")

        def instrumented_metadata_delete(query):
            events.append("metadata_delete")
            return real_metadata_delete(query)

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(current, context),
            ),
            patch.object(
                vault_service,
                "tombstone_vault_upload_version",
                side_effect=instrumented_tombstone,
            ) as core_tombstone,
            patch.object(
                upload_routes,
                "delete_private_object",
                side_effect=instrumented_r2_delete,
            ) as r2_delete,
            patch.object(
                db["uploaded_files"],
                "delete_one",
                side_effect=instrumented_metadata_delete,
            ) as metadata_delete,
            patch.object(upload_routes, "write_audit_log"),
        ):
            response = upload_routes.delete_upload(
                str(current_id),
                current_user=actor,
            )

        promoted = db["uploaded_files"].find_one({"_id": prior_id})
        stored_item = db["vault_items"].find_one({"_id": item_id})
        deletion_tombstone = db["upload_deletion_tombstones"].find_one(
            {"_id": upload_routes._deletion_tombstone_id(str(current_id))}
        )
        deleted_version = next(
            entry
            for entry in stored_item["asset_versions"]
            if entry["upload_id"] == str(current_id)
        )

        self.assertEqual(response["status"], "deleted")
        self.assertEqual(events, ["vault_tombstone", "r2_delete", "metadata_delete"])
        core_tombstone.assert_called_once()
        r2_delete.assert_called_once_with(key=current["storage_key"])
        metadata_delete.assert_called_once_with({"_id": current_id})
        self.assertIsNone(db["uploaded_files"].find_one({"_id": current_id}))
        self.assertTrue(promoted["is_current_version"])
        self.assertEqual(promoted["replacement_status"], "current")
        self.assertIsNone(promoted["superseded_by_upload_id"])
        self.assertIsNone(promoted["replaced_by_upload_id"])
        self.assertEqual(promoted["version"], 1)
        self.assertEqual(stored_item["current_upload_id"], str(prior_id))
        self.assertEqual(stored_item["asset_version"], 1)
        self.assertEqual(deleted_version["deletion_status"], "deleted")
        self.assertTrue(deletion_tombstone["vault_version_tombstoned"])
        self.assertEqual(deletion_tombstone["vault_promoted_upload_id"], str(prior_id))
        self.assertEqual(deletion_tombstone["status"], "complete")

    def test_linked_vault_tombstone_denial_prevents_every_physical_and_metadata_delete(self):
        item_id = ObjectId()
        record = private_upload_record(
            vault_item_id=str(item_id),
            relative_path="private/staging/file.jpg",
            quarantine_path="quarantine/file.jpg",
        )
        item = {
            "_id": item_id,
            "project_id": record["project_id"],
            "family_id": record["family_id"],
            "member_id": record["member_id"],
            "owner_user_id": "different-owner",
            "privacy": "private_owner",
            "release_state": "released",
            "status": "active",
            "access_enabled": True,
            "current_upload_id": str(record["_id"]),
            "asset_versions": [{"version": 1, "upload_id": str(record["_id"])}],
        }
        db = FakeDatabase(
            {
                "uploaded_files": [record],
                "vault_items": [item],
                "upload_deletion_tombstones": [],
            }
        )
        actor = {"id": "owner-1", "email": "owner@example.com"}
        local_file = MagicMock()
        quarantine_file = MagicMock()

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(vault_service, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(record, workspace_context()),
            ),
            patch.object(
                vault_service,
                "preview_vault_upload_version_deletion",
                return_value={"allowed": True},
            ) as core_preview,
            patch.object(
                vault_service,
                "tombstone_vault_upload_version",
                side_effect=PermissionError("vault delete denied"),
            ) as core_tombstone,
            patch.object(upload_routes, "delete_private_object") as r2_delete,
            patch.object(upload_routes, "_absolute_upload_path", return_value=local_file),
            patch.object(
                upload_routes,
                "_absolute_quarantine_path",
                return_value=quarantine_file,
            ),
        ):
            with self.assertRaises(HTTPException) as denied:
                upload_routes.delete_upload(
                    str(record["_id"]),
                    current_user=actor,
                )

        self.assertEqual(denied.exception.status_code, 403)
        core_preview.assert_called_once()
        core_tombstone.assert_called_once()
        r2_delete.assert_not_called()
        local_file.unlink.assert_not_called()
        quarantine_file.unlink.assert_not_called()
        self.assertIs(db["uploaded_files"].find_one({"_id": record["_id"]}), record)
        self.assertEqual(db["uploaded_files"].delete_calls, [])

    def test_version_history_route_returns_newest_first_with_public_permissions(self):
        root = private_upload_record(version=1, is_current_version=False, replacement_status="superseded")
        current = private_upload_record(
            version=2,
            version_group_id=str(root["_id"]),
            replaces_upload_id=str(root["_id"]),
        )
        root["version_group_id"] = str(root["_id"])
        root["superseded_by_upload_id"] = str(current["_id"])
        db = FakeDatabase({"uploaded_files": [root, current]})
        context = workspace_context()
        actor = {"id": "owner-1", "email": "owner@example.com"}

        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_access",
                return_value=(current, context),
            ),
            patch.object(upload_routes.settings, "environment", "production"),
        ):
            payload = upload_routes.list_upload_versions(
                str(current["_id"]),
                current_user=actor,
            )

        self.assertEqual(payload["count"], 2)
        self.assertEqual([item["version"] for item in payload["versions"]], [2, 1])
        self.assertTrue(payload["versions"][0]["permissions"]["can_replace"])
        self.assertFalse(payload["versions"][1]["permissions"]["can_replace"])
        self.assertEqual(payload["root_upload_id"], str(root["_id"]))

    def test_replace_route_at_upload_limit_creates_version_without_count_enforcement(self):
        prior = private_upload_record()
        db = FakeDatabase({"uploaded_files": [prior]})
        context = workspace_context()
        context["resolved_entitlements"]["max_uploads"] = 1
        actor = {"id": "owner-1", "email": "owner@example.com"}
        replacement_file = upload_file(
            filename="replacement.jpg",
            content_type="image/jpeg",
            payload=b"\xff\xd8\xff\xe0replacement-image",
        )

        async def store_replacement(**kwargs):
            replacement = private_upload_record(
                version=kwargs["version"],
                version_group_id=kwargs["version_group_id"],
                replaces_upload_id=kwargs["replaces_upload_id"],
                replacement_status="pending",
                is_current_version=False,
                original_filename="replacement.jpg",
            )
            db["uploaded_files"].documents.append(replacement)
            return replacement

        store = AsyncMock(side_effect=store_replacement)
        with (
            patch.object(upload_routes, "get_database", return_value=db),
            patch.object(
                upload_routes,
                "_require_upload_management_access",
                return_value=(prior, context),
            ),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(
                upload_routes,
                "_enforce_workspace_upload_limit",
                side_effect=HTTPException(status_code=413, detail="upload limit reached"),
            ) as upload_count_enforcement,
            patch.object(upload_routes, "_enforce_workspace_storage_limit"),
            patch.object(
                upload_routes,
                "_begin_upload_idempotency",
                return_value=("key-hash", "fingerprint", None),
            ),
            patch.object(upload_routes, "store_private_media_upload", store),
            patch.object(
                upload_routes,
                "_scan_and_quarantine_upload",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(
                upload_routes,
                "_ensure_upload_vault_linkage",
                side_effect=lambda **kwargs: kwargs["upload_record"],
            ),
            patch.object(upload_routes, "_finish_upload_idempotency") as finish,
            patch.object(upload_routes.settings, "environment", "production"),
        ):
            payload = asyncio.run(
                upload_routes.replace_upload(
                    str(prior["_id"]),
                    file=replacement_file,
                    consent_attested=True,
                    authority_attested=True,
                    privacy_scope="private_to_owner",
                    vault_item_id="",
                    release_state="",
                    reveal_at="",
                    idempotency_key="replace-idempotency-key",
                    current_user=actor,
                )
            )

        replacement = db["uploaded_files"].find_one(
            {"_id": ObjectId(payload["replacement"]["id"])}
        )
        self.assertEqual(payload["upload_status"]["state"], "ready")
        self.assertNotIn("success", payload["message"].lower())
        self.assertFalse(payload["idempotency_replayed"])
        self.assertEqual(payload["replacement"]["version"], 2)
        self.assertEqual(payload["replacement"]["root_upload_id"], str(prior["_id"]))
        self.assertFalse(prior["is_current_version"])
        self.assertEqual(prior["superseded_by_upload_id"], str(replacement["_id"]))
        self.assertTrue(replacement["is_current_version"])
        self.assertEqual(replacement["replacement_status"], "current")
        store.assert_awaited_once()
        store_call = store.await_args.kwargs
        self.assertEqual(store_call["version"], 2)
        self.assertEqual(store_call["version_group_id"], str(prior["_id"]))
        self.assertEqual(store_call["replaces_upload_id"], str(prior["_id"]))
        upload_count_enforcement.assert_not_called()
        finish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
