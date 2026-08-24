from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from bson import ObjectId

from app.services import viewer_manifest_service as service


class _Cursor(list):
    def sort(self, key, direction):
        reverse = direction < 0
        return _Cursor(
            sorted(
                self,
                key=lambda document: str(document.get(key) or ""),
                reverse=reverse,
            )
        )


class _Collection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    @staticmethod
    def _matches(document, query):
        for key, expected in (query or {}).items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query=None):
        return _Cursor(
            deepcopy(document)
            for document in self.documents
            if self._matches(document, query or {})
        )

    def find_one(self, query, sort=None):
        matches = list(self.find(query))
        if sort:
            for key, direction in reversed(sort):
                matches.sort(
                    key=lambda document: str(document.get(key) or ""),
                    reverse=direction < 0,
                )
        return matches[0] if matches else None


class _Database:
    def __init__(self, collections=None):
        self.collections = {
            name: _Collection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        return self.collections.setdefault(name, _Collection())


def _approved_upload(project_id: str, family_id: str, member_id: str) -> dict:
    upload_id = ObjectId()
    return {
        "_id": upload_id,
        "category": "member_photo",
        "project_id": project_id,
        "family_id": family_id,
        "member_id": member_id,
        "relative_path": f"private/{upload_id}.jpg",
        "scan_status": "clean",
        "quarantined": False,
        "approved_for_cinematic": True,
        "verification_status": "approved",
        "consent_status": "approved",
        "consent_attested": True,
        "authority_attested": True,
        "created_at": "2026-08-24T00:00:00+00:00",
    }


class Phase16ViewerManifestIntegrationTests(unittest.TestCase):
    def test_pending_deletion_portrait_is_not_cinematic_ready(self):
        member_id = str(ObjectId())
        upload = _approved_upload("project-1", "family-1", member_id)
        self.assertTrue(
            service._upload_is_cinematic_ready(
                upload,
                project_id="project-1",
                family_id="family-1",
                member_id=member_id,
            )
        )
        upload["deletion_status"] = "pending"
        self.assertFalse(
            service._upload_is_cinematic_ready(
                upload,
                project_id="project-1",
                family_id="family-1",
                member_id=member_id,
            )
        )

    def test_approved_household_portraits_compile_into_complete_versioned_tour(self):
        project_id = "project-household"
        family_id = "family-household"
        parent_id = str(ObjectId())
        anchor_id = str(ObjectId())
        child_id = str(ObjectId())
        sibling_id = str(ObjectId())
        member_specs = [
            (parent_id, "Parent", 0, "placed"),
            (anchor_id, "Anchor", 1, "placed"),
            (sibling_id, "Sibling", 1, "placed"),
            (child_id, "Child", 2, "placed"),
        ]
        uploads = [
            _approved_upload(project_id, family_id, member_id)
            for member_id, _name, _generation, _status in member_specs
        ]
        upload_by_member = {
            upload["member_id"]: str(upload["_id"]) for upload in uploads
        }
        members = [
            {
                "_id": ObjectId(member_id),
                "family_id": family_id,
                "display_name": name,
                "generation": generation,
                "placement_status": placement_status,
                "approved_photo_upload_id": upload_by_member[member_id],
            }
            for member_id, name, generation, placement_status in member_specs
        ]
        relationships = [
            {
                "family_id": family_id,
                "source_member_id": parent_id,
                "target_member_id": anchor_id,
                "relationship_type": "biological_parent",
                "relationship_mode": "verified",
                "status_marker": "verified",
            },
            {
                "family_id": family_id,
                "source_member_id": parent_id,
                "target_member_id": sibling_id,
                "relationship_type": "biological_parent",
                "relationship_mode": "verified",
                "status_marker": "verified",
            },
            {
                "family_id": family_id,
                "source_member_id": anchor_id,
                "target_member_id": child_id,
                "relationship_type": "biological_parent",
                "relationship_mode": "verified",
                "status_marker": "verified",
            },
        ]
        project = {
            "_id": project_id,
            "project_name": "Household",
            "package_code": "household_foundation",
            "package_name": "Household Foundation",
        }
        family = {"_id": family_id, "family_name": "Family"}
        primary = next(member for member in members if str(member["_id"]) == anchor_id)
        db = _Database(
            {
                "family_members": members,
                "uploaded_files": uploads,
                "relationships": relationships,
            }
        )

        def _publish(manifest, **_kwargs):
            published = deepcopy(manifest)
            published["manifest_version"] = {"persisted": True}
            return published

        with (
            patch.object(service, "get_database", return_value=db),
            patch.object(service, "resolve_project_for_viewer", return_value=project),
            patch.object(service, "_find_submission_for_project", return_value=None),
            patch.object(
                service,
                "load_project_workspace_anchor",
                return_value=(family, primary, project),
            ),
            patch.object(
                service,
                "_resolve_viewer_entitlements",
                return_value={"max_zoom_layers": 2, "can_use_narration": False},
            ),
            patch.object(
                service,
                "publish_private_cinematic_manifest",
                side_effect=_publish,
            ) as publish_mock,
        ):
            manifest = service.build_viewer_manifest(
                current_user={"id": "user-1", "email": "owner@example.com"},
                project_id=project_id,
            )

        state_ids = {state["id"] for state in manifest["states"]}
        self.assertEqual(len(state_ids), 4)
        self.assertEqual(set(manifest["auto_advance_state_ids"]), state_ids)
        self.assertTrue(manifest["cinema_compiler"]["validation"]["complete"])
        self.assertEqual(manifest["navigation_mode"], "graph")
        self.assertTrue(manifest["controls"]["allow_auto_advance"])
        self.assertFalse(manifest["controls"]["allow_narration_auto_advance"])
        self.assertIn(f"member-{sibling_id}", {
            option["target_state_id"]
            for option in manifest["branch_options_by_state"][f"member-{anchor_id}"]
        })
        self.assertTrue(manifest["manifest_version"]["persisted"])
        publish_mock.assert_called_once()

    def test_network_manifest_uses_only_privacy_filtered_linked_nodes_and_edges(self):
        project_id = "project-network"
        family_id = "family-root"
        anchor_id = str(ObjectId())
        linked_id = str(ObjectId())
        unaligned_id = str(ObjectId())
        anchor_upload_id = str(ObjectId())
        linked_upload_id = str(ObjectId())
        unaligned_upload_id = str(ObjectId())
        project = {
            "_id": project_id,
            "project_name": "Estate Network",
            "package_code": "family_estate_concierge",
            "package_name": "Family Estate Concierge",
        }
        family = {"_id": family_id, "family_name": "Root Family"}
        primary = {
            "_id": ObjectId(anchor_id),
            "display_name": "Root Anchor",
            "generation": 1,
        }
        network = {
            "nodes": [
                {
                    "id": anchor_id,
                    "display_name": "Root Anchor",
                    "aligned_generation": 1,
                    "placement_status": "placed",
                    "approved_photo_upload_id": anchor_upload_id,
                    "source_household_id": "household-root",
                    "source_household_name": "Root Household",
                    "source_project_id": project_id,
                    "visibility_scope": "household",
                },
                {
                    "id": linked_id,
                    "display_name": "Shared Relative",
                    "aligned_generation": 2,
                    "placement_status": "placed",
                    "approved_photo_upload_id": linked_upload_id,
                    "source_household_id": "household-linked",
                    "source_household_name": "Linked Household",
                    "source_project_id": "project-linked",
                    "visibility_scope": "linked",
                },
                {
                    "id": unaligned_id,
                    "display_name": "Unaligned Relative",
                    "aligned_generation": None,
                    "local_generation": 4,
                    "placement_status": "unplaced",
                    "approved_photo_upload_id": unaligned_upload_id,
                    "source_household_id": "household-unaligned",
                    "source_household_name": "Unaligned Household",
                    "source_project_id": "project-unaligned",
                    "visibility_scope": "linked",
                },
            ],
            "edges": [
                {
                    "id": "household-bridge::1",
                    "source_member_id": anchor_id,
                    "target_member_id": linked_id,
                    "relationship_type": "biological_parent",
                    "relationship_mode": "verified",
                    "status_marker": "verified",
                    "privacy_scope": "linked_family_shared",
                    "is_household_bridge": True,
                }
            ],
        }
        db = _Database({"family_members": []})

        with (
            patch.object(service, "get_database", return_value=db),
            patch.object(service, "resolve_project_for_viewer", return_value=project),
            patch.object(service, "_find_submission_for_project", return_value=None),
            patch.object(
                service,
                "load_project_workspace_anchor",
                return_value=(family, primary, project),
            ),
            patch.object(
                service,
                "_resolve_viewer_entitlements",
                return_value={
                    "max_zoom_layers": 999,
                    "can_use_narration": True,
                    "can_link_households": True,
                },
            ),
            patch.object(service, "build_linked_network", return_value=network) as network_mock,
            patch.object(
                service,
                "publish_private_cinematic_manifest",
                side_effect=lambda manifest, **_kwargs: manifest,
            ),
        ):
            manifest = service.build_viewer_manifest(
                current_user={"id": "user-1", "email": "owner@example.com"},
                project_id=project_id,
            )

        self.assertEqual(len(manifest["states"]), 2)
        linked_state = next(
            state for state in manifest["states"] if state["member_id"] == linked_id
        )
        self.assertEqual(linked_state["source_household_name"], "Linked Household")
        self.assertEqual(linked_state["privacy_scope"], "linked")
        self.assertIn(
            "viewer_project_id=project-network", linked_state["image"]
        )
        self.assertEqual(
            manifest["relationship_edges"][0]["privacy_scope"],
            "linked_family_shared",
        )
        self.assertEqual(
            set(manifest["auto_advance_state_ids"]),
            {f"member-{anchor_id}", f"member-{linked_id}"},
        )
        self.assertEqual(
            manifest["network_alignment"]["status"],
            "partial_unaligned_excluded",
        )
        self.assertEqual(
            manifest["network_alignment"]["excluded_unaligned_member_count"], 1
        )
        network_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
