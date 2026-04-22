import inspect
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from app.routes import viewer_manifest
from app.services import viewer_manifest_service


class _FakeCollection:
    def __init__(self, docs=None):
        self._docs = list(docs or [])

    def find(self, _query=None):
        return list(self._docs)


class _FakeDatabase:
    def __init__(self, collections=None):
        self._collections = {
            name: _FakeCollection(docs)
            for name, docs in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


class LegacySnapshotViewerBoundariesTests(unittest.TestCase):
    def test_viewer_manifest_route_uses_secure_share_capability_not_upload_or_tree_caps(self):
        source = inspect.getsource(viewer_manifest.get_viewer_manifest)
        self.assertIn('"can_use_viewer"', source)
        self.assertIn('"can_use_secure_share_viewer"', source)
        self.assertNotIn('"can_upload_portraits"', source)
        self.assertNotIn('"can_build_family_tree"', source)
        self.assertNotIn('"can_build_org_chart"', source)

    def test_legacy_snapshot_manifest_is_secure_share_mode(self):
        project = {
            "_id": "project-legacy",
            "project_name": "Legacy Workspace",
            "package_code": "legacy_snapshot",
            "package_name": "Legacy Snapshot",
        }
        family = {"_id": "family-legacy", "family_name": "Legacy Family"}
        primary_member = {"_id": "member-legacy", "generation": 1}

        with (
            patch.object(
                viewer_manifest_service,
                "get_database",
                return_value=_FakeDatabase({"family_members": []}),
            ),
            patch.object(
                viewer_manifest_service,
                "resolve_project_for_viewer",
                return_value=project,
            ),
            patch.object(
                viewer_manifest_service,
                "_find_submission_for_project",
                return_value=None,
            ),
            patch.object(
                viewer_manifest_service,
                "load_project_workspace_anchor",
                return_value=(family, primary_member, project),
            ),
        ):
            manifest = viewer_manifest_service.build_viewer_manifest(
                current_user={"id": "user-1", "email": "owner@example.com"},
                project_id="project-legacy",
            )

        self.assertEqual(manifest.get("mode"), "secure_share")
        self.assertFalse(bool((manifest.get("controls") or {}).get("allow_zoom")))
        self.assertFalse(
            bool((manifest.get("controls") or {}).get("allow_lineage_navigation"))
        )
        self.assertFalse(
            bool((manifest.get("controls") or {}).get("allow_branch_navigation"))
        )
        self.assertIn("secure share", str(manifest.get("instructions", "")).lower())
        self.assertNotIn("hold c", str(manifest.get("instructions", "")).lower())

    def test_non_legacy_portrait_manifest_remains_dynamic(self):
        project = {
            "_id": "project-portrait",
            "project_name": "Portrait Workspace",
            "package_code": "digital_legacy_portrait",
            "package_name": "Digital Legacy Portrait",
        }
        family = {"_id": "family-portrait", "family_name": "Portrait Family"}
        primary_member = {"_id": "member-portrait", "generation": 1}

        with (
            patch.object(
                viewer_manifest_service,
                "get_database",
                return_value=_FakeDatabase({"family_members": []}),
            ),
            patch.object(
                viewer_manifest_service,
                "resolve_project_for_viewer",
                return_value=project,
            ),
            patch.object(
                viewer_manifest_service,
                "_find_submission_for_project",
                return_value=None,
            ),
            patch.object(
                viewer_manifest_service,
                "load_project_workspace_anchor",
                return_value=(family, primary_member, project),
            ),
        ):
            manifest = viewer_manifest_service.build_viewer_manifest(
                current_user={"id": "user-1", "email": "owner@example.com"},
                project_id="project-portrait",
            )

        self.assertEqual(manifest.get("mode"), "dynamic")
        self.assertTrue(bool((manifest.get("controls") or {}).get("allow_zoom")))
        self.assertTrue(
            bool((manifest.get("controls") or {}).get("allow_lineage_navigation"))
        )

    def test_legacy_portrait_intro_manifest_is_secure_share_mode(self):
        project = {
            "_id": "project-portrait-intro",
            "project_name": "Portrait Intro Workspace",
            "package_code": "legacy_portrait_intro",
            "package_name": "Legacy Portrait Intro",
        }
        family = {"_id": "family-portrait-intro", "family_name": "Portrait Intro Family"}
        primary_member = {"_id": "member-portrait-intro", "generation": 1}

        with (
            patch.object(
                viewer_manifest_service,
                "get_database",
                return_value=_FakeDatabase({"family_members": []}),
            ),
            patch.object(
                viewer_manifest_service,
                "resolve_project_for_viewer",
                return_value=project,
            ),
            patch.object(
                viewer_manifest_service,
                "_find_submission_for_project",
                return_value=None,
            ),
            patch.object(
                viewer_manifest_service,
                "load_project_workspace_anchor",
                return_value=(family, primary_member, project),
            ),
        ):
            manifest = viewer_manifest_service.build_viewer_manifest(
                current_user={"id": "user-1", "email": "owner@example.com"},
                project_id="project-portrait-intro",
            )

        self.assertEqual(manifest.get("mode"), "secure_share")
        self.assertFalse(bool((manifest.get("controls") or {}).get("allow_zoom")))
        self.assertFalse(
            bool((manifest.get("controls") or {}).get("allow_lineage_navigation"))
        )


class LegacySnapshotUploadBoundariesTests(unittest.TestCase):
    def test_upload_pages_have_legacy_snapshot_manifest_member_fallback(self):
        root = Path(__file__).resolve().parents[2]
        portrait_source = (root / "portrait-upload.js").read_text(encoding="utf-8")
        verification_source = (root / "verification-upload.js").read_text(
            encoding="utf-8"
        )

        required_pattern = re.compile(
            r"if\s*\(isLegacySnapshotContext\(currentContext\)\)\s*\{\s*members\s*=\s*await\s*loadLegacySnapshotMembersFromManifest\(familyId\);",
            re.MULTILINE,
        )

        self.assertIn("loadLegacySnapshotMembersFromManifest", portrait_source)
        self.assertIn("resolveMembersFromManifest", portrait_source)
        self.assertRegex(portrait_source, required_pattern)
        self.assertIn('normalizeValue(manifest?.mode) === "secure_share"', portrait_source)

        self.assertIn("loadLegacySnapshotMembersFromManifest", verification_source)
        self.assertIn("resolveMembersFromManifest", verification_source)
        self.assertRegex(verification_source, required_pattern)
        self.assertIn(
            'normalizeValue(manifest?.mode) === "secure_share"',
            verification_source,
        )


if __name__ == "__main__":
    unittest.main()
