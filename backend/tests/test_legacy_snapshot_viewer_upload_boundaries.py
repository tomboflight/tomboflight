import inspect
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId

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

    def test_non_legacy_portrait_manifest_honors_zero_zoom_layers(self):
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
        self.assertFalse(bool((manifest.get("controls") or {}).get("allow_zoom")))
        self.assertTrue(
            bool((manifest.get("controls") or {}).get("allow_lineage_navigation"))
        )

    def test_household_foundation_manifest_exposes_two_zoom_layers(self):
        project = {
            "_id": "project-household",
            "project_name": "Household Workspace",
            "package_code": "household_foundation",
            "package_name": "Household Foundation",
        }
        family = {"_id": "family-household", "family_name": "Household Family"}
        primary_member = {"_id": "member-household", "generation": 1}

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
                project_id="project-household",
            )

        controls = manifest.get("controls") or {}
        self.assertEqual(manifest.get("mode"), "dynamic")
        self.assertTrue(bool(controls.get("allow_zoom")))
        self.assertEqual(controls.get("max_zoom_layers"), 2)
        self.assertFalse(bool(controls.get("allow_narration_auto_advance")))

    def test_heirloom_manifest_limits_zoom_and_disables_narration_playback(self):
        project = {
            "_id": "project-heirloom",
            "project_name": "Heirloom Workspace",
            "package_code": "heirloom_legacy_tree",
            "package_name": "Heirloom Legacy Tree",
        }
        family = {"_id": "family-heirloom", "family_name": "Heirloom Family"}
        primary_member = {"_id": "member-heirloom", "generation": 1}

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
                project_id="project-heirloom",
            )

        controls = manifest.get("controls") or {}
        self.assertEqual(manifest.get("mode"), "dynamic")
        self.assertTrue(bool(controls.get("allow_zoom")))
        self.assertEqual(controls.get("max_zoom_layers"), 4)
        self.assertFalse(bool(controls.get("allow_narration_auto_advance")))

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
        self.assertIn("!canBuildFamilyTree", portrait_source)

        self.assertIn("loadLegacySnapshotMembersFromManifest", verification_source)
        self.assertIn("resolveMembersFromManifest", verification_source)
        self.assertRegex(verification_source, required_pattern)
        self.assertIn(
            'normalizeValue(manifest?.mode) === "secure_share"',
            verification_source,
        )
        self.assertIn("!canBuildFamilyTree", verification_source)

    def test_viewer_manifest_upload_resolution_enforces_project_family_member_scope(self):
        class _UploadCursor:
            def __init__(self, docs):
                self._docs = list(docs)

            def sort(self, *_args, **_kwargs):
                return self

            def __iter__(self):
                return iter(self._docs)

        class _UploadsCollection:
            def __init__(self, docs):
                self._docs = list(docs)

            def find(self, query):
                def _matches(doc):
                    return all(doc.get(key) == value for key, value in query.items())

                return _UploadCursor([doc for doc in self._docs if _matches(doc)])

            def find_one(self, query):
                target_id = query.get("_id")
                for doc in self._docs:
                    if doc.get("_id") == target_id:
                        return doc
                return None

        class _FakeUploadDB:
            def __init__(self, docs):
                self._uploads = _UploadsCollection(docs)

            def __getitem__(self, name):
                if name == "uploaded_files":
                    return self._uploads
                raise KeyError(name)

        upload_foreign = {
            "_id": ObjectId(),
            "category": "member_photo",
            "project_id": "project-foreign",
            "family_id": "family-foreign",
            "member_id": "member-foreign",
            "relative_path": "uploads/foreign.jpg",
        }
        upload_valid = {
            "_id": ObjectId(),
            "category": "member_photo",
            "project_id": "project-1",
            "family_id": "family-1",
            "member_id": "member-1",
            "relative_path": "uploads/member-1.jpg",
        }
        db = _FakeUploadDB([upload_foreign, upload_valid])

        blocked = viewer_manifest_service._resolve_member_photo_upload(
            db=db,
            member={"_id": "member-1", "photo_upload_id": str(upload_foreign["_id"])},
            project_id="project-1",
            family_id="family-1",
        )
        self.assertIsNone(blocked)

        allowed = viewer_manifest_service._resolve_member_photo_upload(
            db=db,
            member={"_id": "member-1", "photo_upload_id": str(upload_valid["_id"])},
            project_id="project-1",
            family_id="family-1",
        )
        self.assertEqual(allowed, upload_valid)


if __name__ == "__main__":
    unittest.main()
