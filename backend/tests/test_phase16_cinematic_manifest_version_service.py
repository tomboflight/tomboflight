from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from app.services import cinematic_version_service as service


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _Collection:
    def __init__(self, name: str, log: list[str], *, fail_update: bool = False):
        self.name = name
        self.log = log
        self.fail_update = fail_update
        self.docs: list[dict] = []
        self.indexes: list[tuple] = []

    def find_one(self, query):
        return next(
            (
                deepcopy(document)
                for document in self.docs
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )

    def insert_one(self, document):
        self.log.append(f"insert:{self.name}")
        stored = deepcopy(document)
        stored["_id"] = f"version-{len(self.docs) + 1}"
        self.docs.append(stored)
        return _InsertResult(stored["_id"])

    def update_one(self, query, update, upsert=False):
        self.log.append(f"update:{self.name}")
        if self.fail_update:
            raise RuntimeError("pointer write failed")
        existing = next(
            (
                document
                for document in self.docs
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )
        if existing is None:
            if not upsert:
                return None
            existing = dict(query)
            self.docs.append(existing)
            existing.update(deepcopy(update.get("$setOnInsert") or {}))
        existing.update(deepcopy(update.get("$set") or {}))
        return None

    def create_index(self, keys, **options):
        self.indexes.append((list(keys), dict(options)))
        return options.get("name")


class _Database:
    def __init__(self, *, fail_active_update: bool = False):
        self.log: list[str] = []
        self.collections = {
            "cinematic_manifest_versions": _Collection(
                "cinematic_manifest_versions", self.log
            ),
            "cinematic_manifest_active": _Collection(
                "cinematic_manifest_active",
                self.log,
                fail_update=fail_active_update,
            ),
        }

    def __getitem__(self, name):
        return self.collections[name]


def _manifest() -> dict:
    return {
        "mode": "dynamic",
        "states": [
            {"id": "member-a", "member_id": "a", "title": "A"},
            {"id": "member-b", "member_id": "b", "title": "B"},
        ],
        "auto_advance_state_ids": ["member-a", "member-b", "member-a"],
        "cinema_compiler": {
            "version": "tol-lineage-cinema-1.0",
            "validation": {"complete": True, "tour_bounded": True},
        },
    }


class Phase16CinematicManifestVersionTests(unittest.TestCase):
    def test_hash_is_canonical_and_excludes_runtime_version_metadata(self):
        first = _manifest()
        second = {
            "cinema_compiler": deepcopy(first["cinema_compiler"]),
            "auto_advance_state_ids": list(first["auto_advance_state_ids"]),
            "states": deepcopy(first["states"]),
            "mode": "dynamic",
            "manifest_version": {"version_id": "old"},
        }

        self.assertEqual(
            service.canonical_manifest_hash(first),
            service.canonical_manifest_hash(second),
        )

    def test_version_is_inserted_before_atomic_active_pointer_swap(self):
        db = _Database()
        with patch.object(service, "get_database", return_value=db):
            published = service.publish_private_cinematic_manifest(
                _manifest(), project_id="project-1", family_id="family-1"
            )

        self.assertEqual(
            db.log,
            [
                "insert:cinematic_manifest_versions",
                "update:cinematic_manifest_active",
            ],
        )
        self.assertTrue(published["manifest_version"]["persisted"])
        self.assertEqual(
            db.collections["cinematic_manifest_active"].docs[0]["active_version_id"],
            "version-1",
        )

    def test_identical_manifest_reuses_immutable_version(self):
        db = _Database()
        with patch.object(service, "get_database", return_value=db):
            first = service.publish_private_cinematic_manifest(
                _manifest(), project_id="project-1"
            )
            second = service.publish_private_cinematic_manifest(
                _manifest(), project_id="project-1"
            )

        self.assertEqual(
            len(db.collections["cinematic_manifest_versions"].docs), 1
        )
        self.assertEqual(
            first["manifest_version"]["version_id"],
            second["manifest_version"]["version_id"],
        )

    def test_pointer_failure_does_not_return_unactivated_manifest(self):
        db = _Database(fail_active_update=True)
        with (
            patch.object(service, "get_database", return_value=db),
            self.assertRaisesRegex(RuntimeError, "pointer write failed"),
        ):
            service.publish_private_cinematic_manifest(
                _manifest(), project_id="project-1"
            )

        self.assertEqual(
            len(db.collections["cinematic_manifest_versions"].docs), 1
        )
        self.assertEqual(db.collections["cinematic_manifest_active"].docs, [])

    def test_incomplete_manifest_fails_before_any_database_write(self):
        db = _Database()
        manifest = _manifest()
        manifest["cinema_compiler"]["validation"]["complete"] = False
        with (
            patch.object(service, "get_database", return_value=db),
            self.assertRaisesRegex(RuntimeError, "incomplete"),
        ):
            service.publish_private_cinematic_manifest(
                manifest, project_id="project-1"
            )

        self.assertEqual(db.log, [])

    def test_empty_workspace_manifest_can_replace_a_previous_active_version(self):
        db = _Database()
        manifest = {
            "mode": "dynamic",
            "states": [{"id": "workspace-anchor", "image": ""}],
            "auto_advance_state_ids": [],
            "cinema_compiler": {
                "version": "tol-lineage-cinema-1.0",
                "validation": {"complete": True, "tour_bounded": True},
            },
        }
        with patch.object(service, "get_database", return_value=db):
            published = service.publish_private_cinematic_manifest(
                manifest, project_id="project-1"
            )

        self.assertTrue(published["manifest_version"]["persisted"])
        self.assertEqual(
            db.collections["cinematic_manifest_active"].docs[0]["content_hash"],
            published["manifest_version"]["content_hash"],
        )

    def test_startup_indexes_enforce_one_version_key_and_active_pointer(self):
        db = _Database()
        with patch.object(service, "get_database", return_value=db):
            service.ensure_cinematic_manifest_indexes()

        versions = db.collections["cinematic_manifest_versions"].indexes
        active = db.collections["cinematic_manifest_active"].indexes
        self.assertTrue(
            any(options.get("unique") for _keys, options in versions)
        )
        self.assertTrue(any(options.get("unique") for _keys, options in active))


if __name__ == "__main__":
    unittest.main()
