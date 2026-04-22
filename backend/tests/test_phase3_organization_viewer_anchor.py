from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from bson import ObjectId

from app.services import intake_pipeline_service, viewer_manifest_service


@dataclass
class _InsertResult:
    inserted_id: ObjectId


class _Cursor(list):
    def sort(self, key, direction):
        reverse = int(direction) < 0
        return _Cursor(sorted(self, key=lambda doc: doc.get(key), reverse=reverse))


class _Collection:
    def __init__(self, docs=None):
        self.docs = [dict(doc) for doc in (docs or [])]

    def find_one(self, query=None, sort=None):
        query = query or {}
        matches = [doc for doc in self.docs if self._matches(doc, query)]
        if sort and matches:
            key, direction = sort[0]
            reverse = int(direction) < 0
            matches.sort(key=lambda doc: doc.get(key), reverse=reverse)
        return dict(matches[0]) if matches else None

    def find(self, query=None):
        query = query or {}
        return _Cursor([dict(doc) for doc in self.docs if self._matches(doc, query)])

    def insert_one(self, doc):
        materialized = dict(doc)
        materialized.setdefault("_id", ObjectId())
        self.docs.append(materialized)
        return _InsertResult(inserted_id=materialized["_id"])

    def update_one(self, query, update):
        target = None
        for doc in self.docs:
            if self._matches(doc, query):
                target = doc
                break
        if target is None:
            return
        if "$set" in update:
            target.update(update["$set"])
        if "$unset" in update:
            for key in update["$unset"]:
                target.pop(key, None)

    @staticmethod
    def _matches(doc, query):
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                if doc.get(key) not in value["$in"]:
                    return False
            else:
                if doc.get(key) != value:
                    return False
        return True


class _FakeDB(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = _Collection()
        return dict.__getitem__(self, key)


def test_command_structure_network_provisioning_does_not_create_family_or_member_records():
    submission_id = ObjectId()
    now = datetime.now(timezone.utc)
    db = _FakeDB(
        {
            "intake_submissions": _Collection(
                [
                    {
                        "_id": submission_id,
                        "status": "approved",
                        "email": "commander@example.com",
                        "package_code": "command_structure_network",
                        "package_name": "Command Structure Network",
                        "household": {
                            "household_name": "Joint Task Force",
                            "primary_contact_name": "Commander Prime",
                            "project_scope": "Command graph setup",
                        },
                        "family_map": {},
                        "consent": {},
                        "review": {},
                        "created_at": now,
                        "updated_at": now,
                    }
                ]
            ),
            "families": _Collection(),
            "family_members": _Collection(),
            "households": _Collection(),
            "projects": _Collection(),
            "organization_profiles": _Collection(),
            "organization_people": _Collection(),
        }
    )

    with (
        patch.object(intake_pipeline_service, "get_database", return_value=db),
        patch.object(viewer_manifest_service, "get_database", return_value=db),
        patch.object(
            intake_pipeline_service,
            "transition_project",
            side_effect=lambda project_id, _phase, _actor: db["projects"].find_one(
                {"_id": ObjectId(project_id)}
            ),
        ),
    ):
        intake_pipeline_service.provision_build_from_submission(
            submission_id=str(submission_id),
            provisioned_by="admin@example.com",
            provisioned_by_user_id="admin-1",
        )

    assert db["families"].docs == []
    assert db["family_members"].docs == []
    project = db["projects"].docs[0]
    assert project["project_lane"] == "organization"
    assert project["family_id"] is None


def test_command_structure_network_manifest_uses_organization_command_mode_and_org_controls():
    project = {
        "_id": "org-project-1",
        "project_lane": "organization",
        "project_name": "Joint Task Force",
        "package_code": "command_structure_network",
        "package_name": "Command Structure Network",
        "organization_id": "org-1",
    }
    db = _FakeDB(
        {
            "organization_profiles": _Collection(
                [
                    {
                        "organization_id": "org-1",
                        "display_name": "Joint Task Force",
                        "description": "Operational command view",
                    }
                ]
            ),
            "organization_people": _Collection(),
            "uploaded_files": _Collection(),
        }
    )

    with (
        patch.object(viewer_manifest_service, "get_database", return_value=db),
        patch.object(viewer_manifest_service, "resolve_project_for_viewer", return_value=project),
        patch.object(viewer_manifest_service, "_find_submission_for_project", return_value=None),
    ):
        manifest = viewer_manifest_service.build_viewer_manifest(
            current_user={"id": "user-1", "email": "owner@example.com"},
            project_id="org-project-1",
        )

    assert manifest["mode"] == "organization_command"
    assert manifest.get("family") is None
    controls = manifest["controls"]
    assert "allow_lineage_navigation" not in controls
    assert "allow_branch_navigation" not in controls
    assert controls["allow_command_navigation"] is True
    assert controls["allow_role_navigation"] is True

    mode_map = {item["id"]: bool(item["available"]) for item in manifest.get("viewer_modes", [])}
    assert mode_map == {
        "current_command_view": True,
        "historical_date_view": False,
        "succession_timeline": False,
        "officer_wall": False,
        "continuity_map": False,
        "linked_organization_view": False,
    }
    assert "organization command portraits" in manifest["instructions"].lower()


def test_household_manifest_keeps_family_viewer_controls():
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
            return_value=_FakeDB({"family_members": _Collection()}),
        ),
        patch.object(viewer_manifest_service, "resolve_project_for_viewer", return_value=project),
        patch.object(viewer_manifest_service, "_find_submission_for_project", return_value=None),
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

    assert manifest["mode"] == "dynamic"
    controls = manifest["controls"]
    assert controls["allow_lineage_navigation"] is True
    assert controls["allow_branch_navigation"] is True
    assert "viewer_modes" not in manifest
