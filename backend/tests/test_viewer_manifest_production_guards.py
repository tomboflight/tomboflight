import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routes import viewer_manifest
from app.services import viewer_manifest_service


class ViewerManifestProductionGuardsTests(unittest.TestCase):
    def test_service_requires_project_or_family_context(self):
        with patch.object(viewer_manifest_service, "get_database", return_value={}):
            with self.assertRaises(ValueError) as exc:
                viewer_manifest_service.build_viewer_manifest(
                    current_user={"id": "user-1", "email": "owner@example.com"},
                    project_id="",
                    family_id="",
                )

        self.assertEqual(
            str(exc.exception),
            "No approved viewer manifest is available for this project yet.",
        )

    def test_route_returns_safe_404_when_manifest_is_unavailable(self):
        with (
            patch.object(viewer_manifest, "require_any_package_capability"),
            patch.object(
                viewer_manifest,
                "build_viewer_manifest",
                side_effect=ValueError(
                    "No approved viewer manifest is available for this project yet."
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as exc:
                viewer_manifest.get_viewer_manifest(
                    project_id="",
                    family_id="",
                    current_user={"id": "user-1", "email": "owner@example.com"},
                )

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(
            exc.exception.detail,
            "No approved viewer manifest is available for this project yet.",
        )


if __name__ == "__main__":
    unittest.main()
