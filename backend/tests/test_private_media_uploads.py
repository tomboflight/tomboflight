import asyncio
import io
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.routes import uploads as upload_routes


def _upload_file(*, filename: str, content_type: str, payload: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _workspace_context(*, allowed_asset_types: list[str]):
    return {
        "project": {"_id": "project-1"},
        "family": {"_id": "family-1"},
        "member": {"_id": "member-1", "family_id": "family-1"},
        "resolved_entitlements": {
            "can_upload_verification_docs": True,
            "allowed_asset_types": allowed_asset_types,
        },
        "is_admin": False,
    }


class PrivateMediaUploadTests(unittest.TestCase):
    def test_allowed_package_private_voice_upload_succeeds(self):
        async def _run():
            upload = _upload_file(
                filename="legacy-voice.mp3",
                content_type="audio/mpeg",
                payload=b"voice-bytes",
            )
            with (
                patch.object(upload_routes, "require_workspace_capability", return_value=_workspace_context(allowed_asset_types=["private_voice_message"])),
                patch.object(upload_routes, "require_workspace_member_role"),
                patch.object(upload_routes, "get_database", return_value={"uploaded_files": object()}),
                patch.object(
                    upload_routes,
                    "store_private_media_upload",
                    return_value={
                        "id": "upload-1",
                        "family_id": "family-1",
                        "member_id": "member-1",
                        "asset_type": "private_voice_message",
                    },
                ),
                patch.object(upload_routes, "_scan_and_quarantine_upload", side_effect=lambda **kwargs: kwargs["upload_record"]),
                patch.object(upload_routes, "_enforce_workspace_upload_limit"),
                patch.object(upload_routes, "_enforce_workspace_storage_limit"),
            ):
                return await upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="member-1",
                    asset_type="private_voice_message",
                    privacy_scope="private_to_owner",
                    file=upload,
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        payload = asyncio.run(_run())
        self.assertEqual(payload["message"], "Private media uploaded successfully.")
        self.assertEqual(payload["upload"]["asset_type"], "private_voice_message")

    def test_disallowed_package_private_video_upload_fails(self):
        async def _run():
            upload = _upload_file(
                filename="legacy-video.mp4",
                content_type="video/mp4",
                payload=b"video-bytes",
            )
            with (
                patch.object(upload_routes, "require_workspace_capability", return_value=_workspace_context(allowed_asset_types=["document"])),
                patch.object(upload_routes, "require_workspace_member_role"),
                patch.object(upload_routes, "get_database", return_value={"uploaded_files": object()}),
            ):
                return await upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="member-1",
                    asset_type="private_video_message",
                    privacy_scope="private_to_owner",
                    file=upload,
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_run())
        self.assertEqual(ctx.exception.status_code, 403)

    def test_private_media_invalid_privacy_scope_rejected(self):
        async def _run():
            upload = _upload_file(
                filename="legacy-voice.mp3",
                content_type="audio/mpeg",
                payload=b"voice-bytes",
            )
            with (
                patch.object(upload_routes, "require_workspace_capability", return_value=_workspace_context(allowed_asset_types=["private_voice_message"])),
                patch.object(upload_routes, "require_workspace_member_role"),
                patch.object(upload_routes, "get_database", return_value={"uploaded_files": object()}),
            ):
                return await upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="member-1",
                    asset_type="private_voice_message",
                    privacy_scope="public_memorial",
                    file=upload,
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_run())
        self.assertEqual(ctx.exception.status_code, 400)

    def test_private_media_storage_limit_enforced(self):
        async def _run():
            upload = _upload_file(
                filename="legacy-voice.mp3",
                content_type="audio/mpeg",
                payload=b"voice-bytes",
            )
            with (
                patch.object(upload_routes, "require_workspace_capability", return_value=_workspace_context(allowed_asset_types=["private_voice_message"])),
                patch.object(upload_routes, "require_workspace_member_role"),
                patch.object(upload_routes, "get_database", return_value={"uploaded_files": object()}),
                patch.object(upload_routes, "_enforce_workspace_upload_limit"),
                patch.object(
                    upload_routes,
                    "_enforce_workspace_storage_limit",
                    side_effect=HTTPException(status_code=409, detail="Limit exceeded for 'vault_storage_bytes'."),
                ),
            ):
                return await upload_routes.upload_private_media(
                    family_id="family-1",
                    member_id="member-1",
                    asset_type="private_voice_message",
                    privacy_scope="private_to_owner",
                    file=upload,
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_run())
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
