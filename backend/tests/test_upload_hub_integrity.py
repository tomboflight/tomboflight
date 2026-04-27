import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_HREF_PATTERN = re.compile(
    r'href\s*=\s*"(#|javascript:void\(0\)|)"', re.IGNORECASE
)
EMPTY_DATA_ACTION_PATTERN = re.compile(r'data-action\s*=\s*""', re.IGNORECASE)


class UploadHubIntegrityTests(unittest.TestCase):
    """Verify the Upload Hub and vault upload pages ship without placeholder links
    and route correctly to the three real production upload destinations."""

    def _read(self, filename: str) -> str:
        return (REPO_ROOT / filename).read_text(encoding="utf-8")

    def test_upload_hub_has_no_placeholder_links(self):
        contents = self._read("upload-hub.html")
        self.assertFalse(
            PLACEHOLDER_HREF_PATTERN.search(contents),
            "upload-hub.html contains a placeholder href",
        )
        self.assertFalse(
            EMPTY_DATA_ACTION_PATTERN.search(contents),
            "upload-hub.html contains an empty data-action",
        )

    def test_vault_upload_has_no_placeholder_links(self):
        contents = self._read("vault-upload.html")
        self.assertFalse(
            PLACEHOLDER_HREF_PATTERN.search(contents),
            "vault-upload.html contains a placeholder href",
        )
        self.assertFalse(
            EMPTY_DATA_ACTION_PATTERN.search(contents),
            "vault-upload.html contains an empty data-action",
        )

    def test_upload_hub_routes_to_portrait_upload(self):
        contents = self._read("upload-hub.html")
        self.assertIn(
            'href="portrait-upload.html"',
            contents,
            "Upload Hub must link to portrait-upload.html",
        )

    def test_upload_hub_routes_to_verification_upload(self):
        contents = self._read("upload-hub.html")
        self.assertIn(
            'href="verification-upload.html"',
            contents,
            "Upload Hub must link to verification-upload.html",
        )

    def test_upload_hub_routes_to_vault_upload(self):
        contents = self._read("upload-hub.html")
        self.assertIn(
            'href="vault-upload.html"',
            contents,
            "Upload Hub must link to vault-upload.html",
        )

    def test_upload_hub_describes_all_three_categories(self):
        contents = self._read("upload-hub.html")
        self.assertIn(
            "portrait",
            contents.lower(),
            "Upload Hub must describe portrait/photo uploads",
        )
        self.assertIn(
            "verification",
            contents.lower(),
            "Upload Hub must describe verification document uploads",
        )
        self.assertIn(
            "vault",
            contents.lower(),
            "Upload Hub must describe vault file uploads",
        )

    def test_upload_hub_explains_intake_plan_is_not_upload(self):
        contents = self._read("upload-hub.html")
        # Must distinguish the intake planning step from actual uploads
        self.assertIn(
            "intake-uploads.html",
            contents,
            "Upload Hub must reference the intake upload plan page",
        )
        self.assertRegex(
            contents,
            r"does not upload|planning only|plan.*not upload",
            "Upload Hub must clarify the intake plan step does not upload files",
        )

    def test_upload_hub_shows_customer_status_key(self):
        contents = self._read("upload-hub.html")
        for status in [
            "pending review",
            "approved",
            "saved to vault",
            "rejected",
            "needs correction",
        ]:
            self.assertIn(
                status,
                contents,
                f"Upload Hub must explain the '{status}' customer status",
            )

    def test_intake_uploads_page_no_longer_reads_as_upload_page(self):
        """The intake upload plan page must clarify it is planning only."""
        contents = self._read("intake-uploads.html")
        self.assertIn(
            "Upload Plan",
            contents,
            "intake-uploads.html heading must say 'Upload Plan'",
        )
        self.assertRegex(
            contents,
            r"does not upload|planning only|planning and scope|scope only",
            "intake-uploads.html must make clear this step does not upload files",
        )
        self.assertIn(
            "upload-hub.html",
            contents,
            "intake-uploads.html must link to the Upload Hub for actual uploads",
        )

    def test_vault_upload_uses_private_media_backend_route(self):
        """vault-upload.js must POST to the real /uploads/private-media backend route."""
        contents = self._read("vault-upload.js")
        self.assertIn(
            "/uploads/private-media",
            contents,
            "vault-upload.js must POST to /uploads/private-media backend route",
        )

    def test_vault_upload_enforces_entitlement_check_ui(self):
        """vault-upload.js must check entitlements and disable the form when not entitled."""
        contents = self._read("vault-upload.js")
        self.assertIn(
            "can_upload",
            contents,
            "vault-upload.js must check can_upload entitlements",
        )
        self.assertIn(
            "disabled",
            contents,
            "vault-upload.js must disable the form when the user lacks entitlement",
        )

    def test_vault_upload_uses_correct_asset_types(self):
        """vault-upload.js must only submit the two backend-allowed asset types."""
        contents = self._read("vault-upload.js")
        self.assertIn(
            "private_voice_message",
            contents,
            "vault-upload.js must use the 'private_voice_message' asset type",
        )
        self.assertIn(
            "private_video_message",
            contents,
            "vault-upload.js must use the 'private_video_message' asset type",
        )

    def test_portrait_upload_js_shows_customer_status(self):
        """portrait-upload.js must display a customer-facing upload status label."""
        contents = self._read("portrait-upload.js")
        self.assertIn(
            "uploadStatusLabel",
            contents,
            "portrait-upload.js must define uploadStatusLabel for customer-facing status",
        )
        self.assertIn(
            "approved for cinematic use",
            contents,
            "portrait-upload.js must include 'approved for cinematic use' status",
        )

    def test_verification_upload_js_shows_customer_status(self):
        """verification-upload.js must display a customer-facing upload status label."""
        contents = self._read("verification-upload.js")
        self.assertIn(
            "uploadStatusLabel",
            contents,
            "verification-upload.js must define uploadStatusLabel",
        )
        self.assertIn(
            "approved for verification",
            contents,
            "verification-upload.js must include 'approved for verification' status",
        )


if __name__ == "__main__":
    unittest.main()
