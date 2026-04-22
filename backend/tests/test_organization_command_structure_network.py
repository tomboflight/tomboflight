from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unittest.mock import patch

import pytest
from pymongo.errors import DuplicateKeyError

from app.routes import organizations
from app.services import organization_service


@dataclass
class _InsertResult:
    inserted_id: str


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.unique_indexes: list[tuple[str, ...]] = []

    def create_index(self, fields, unique=False, name=None):
        if unique:
            self.unique_indexes.append(tuple(field for field, _ in fields))

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                if doc.get(key) not in value["$in"]:
                    return False
            elif isinstance(value, dict) and "$in" not in value:
                if key == "status" and isinstance(value.get("$in"), list):
                    if doc.get("status") not in value["$in"]:
                        return False
                else:
                    return False
            else:
                if doc.get(key) != value:
                    return False
        return True

    def count_documents(self, query: dict) -> int:
        return len([d for d in self.docs if self._matches(d, query)])

    def find_one(self, query: dict, sort=None):
        docs = self.docs
        if sort:
            key, direction = sort[0]
            docs = sorted(docs, key=lambda item: item.get(key), reverse=direction < 0)
        for doc in docs:
            if self._matches(doc, query):
                return doc
        return None

    def find(self, query: dict):
        return [d for d in self.docs if self._matches(d, query)]

    def insert_one(self, doc: dict):
        for keys in self.unique_indexes:
            for existing in self.docs:
                if all(existing.get(k) == doc.get(k) for k in keys):
                    raise DuplicateKeyError("duplicate")
        materialized = dict(doc)
        materialized.setdefault("_id", f"id-{len(self.docs)+1}")
        self.docs.append(materialized)
        return _InsertResult(inserted_id=materialized["_id"])

    def update_one(self, query: dict, update: dict):
        target = self.find_one(query)
        if target is None:
            return
        if "$set" in update:
            target.update(update["$set"])


class FakeDB(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = FakeCollection()
        return dict.__getitem__(self, key)


def _setup_fake_db():
    db = FakeDB()
    with patch("app.services.organization_service.get_database", return_value=db):
        organization_service.ensure_organization_indexes()
    return db


def _seed_org_graph(db: FakeDB) -> None:
    with patch("app.services.organization_service.get_database", return_value=db):
        organization_service.upsert_organization_profile(
            {
                "organization_id": "org1",
                "project_id": "proj1",
                "organization_name": "Joint Task Force",
                "organization_type": "military",
            },
            actor_user_id="u1",
        )
        organization_service.create_organization_node("org1", {"node_key": "n1", "node_name": "Command", "node_type": "command"}, actor_user_id="u1")
        organization_service.create_role_seat("org1", {"node_id": "n1", "role_key": "r1", "role_name": "Commander"}, actor_user_id="u1")
        organization_service.create_person("org1", {"person_id": "p1", "full_name": "Alex Prime", "status": "active"}, actor_user_id="u1")
        organization_service.create_person("org1", {"person_id": "p2", "full_name": "Bailey Former", "status": "former"}, actor_user_id="u1")
        organization_service.create_assignment(
            "org1",
            {
                "assignment_id": "a1",
                "node_id": "n1",
                "role_seat_id": "r1",
                "person_id": "p2",
                "start_date": "2019-01-01",
                "end_date": "2021-01-01",
                "status": "completed",
                "acting_or_interim": False,
            },
            actor_user_id="u1",
        )
        organization_service.create_assignment(
            "org1",
            {
                "assignment_id": "a2",
                "node_id": "n1",
                "role_seat_id": "r1",
                "person_id": "p1",
                "start_date": "2021-01-02",
                "end_date": None,
                "status": "active",
                "acting_or_interim": False,
            },
            actor_user_id="u1",
        )


def test_family_or_household_lane_cannot_access_org_routes():
    with patch("app.routes.organizations.require_package_capability", side_effect=Exception("blocked")):
        with pytest.raises(Exception):
            organizations._require_org_lane({"id": "u1"})


def test_command_structure_network_can_access_org_routes():
    with patch("app.routes.organizations.require_package_capability", return_value={"id": "u1"}):
        organizations._require_org_lane({"id": "u1"})


def test_duplicate_node_and_role_seat_are_blocked():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        organization_service.create_organization_node("org1", {"node_key": "bde", "node_name": "Brigade", "node_type": "brigade"}, actor_user_id="u1")
        with pytest.raises(ValueError):
            organization_service.create_organization_node("org1", {"node_key": "bde", "node_name": "Brigade 2", "node_type": "brigade"}, actor_user_id="u1")

        organization_service.create_role_seat("org1", {"node_id": "n1", "role_key": "commander", "role_name": "Commander"}, actor_user_id="u1")
        with pytest.raises(ValueError):
            organization_service.create_role_seat("org1", {"node_id": "n1", "role_key": "commander", "role_name": "Commander"}, actor_user_id="u1")


def test_replacing_leader_creates_new_assignment_and_preserves_old_assignment():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        organization_service.create_assignment("org1", {
            "assignment_id": "a1",
            "node_id": "n1",
            "role_seat_id": "r1",
            "person_id": "p1",
            "start_date": "2020-01-01",
            "end_date": None,
            "status": "active",
            "acting_or_interim": False,
        }, actor_user_id="u1")
        result = organization_service.replace_role_seat_assignment("org1", "r1", {
            "assignment_id": "a2",
            "node_id": "n1",
            "person_id": "p2",
            "title_at_time": "Commander",
            "rank_at_time": "COL",
            "start_date": "2021-01-01",
            "acting_or_interim": False,
        }, actor_user_id="u2")

        assert result["new_assignment"]["assignment_id"] == "a2"
        old = db["organization_assignments"].find_one({"assignment_id": "a1"})
        assert old["status"] == "ended"
        assert old["person_id"] == "p1"


def test_ending_term_preserves_person_record():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        organization_service.create_person("org1", {"person_id": "p1", "full_name": "Alex"}, actor_user_id="u1")
        organization_service.create_assignment("org1", {
            "assignment_id": "a1", "node_id": "n1", "role_seat_id": "r1", "person_id": "p1", "start_date": "2020-01-01", "end_date": None, "status": "active", "acting_or_interim": False,
        }, actor_user_id="u1")
        organization_service.end_assignment("org1", "a1", end_date="2022-01-01", status="ended", notes=None, actor_user_id="u1")
        assert db["organization_people"].find_one({"person_id": "p1"}) is not None


def test_duplicate_current_assignment_blocked_except_acting_or_interim():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        organization_service.create_assignment("org1", {
            "assignment_id": "a1", "node_id": "n1", "role_seat_id": "r1", "person_id": "p1", "start_date": "2020-01-01", "end_date": None, "status": "active", "acting_or_interim": False,
        }, actor_user_id="u1")
        with pytest.raises(ValueError):
            organization_service.create_assignment("org1", {
                "assignment_id": "a2", "node_id": "n1", "role_seat_id": "r1", "person_id": "p2", "start_date": "2021-01-01", "end_date": None, "status": "active", "acting_or_interim": False,
            }, actor_user_id="u1")
        created = organization_service.create_assignment("org1", {
            "assignment_id": "a3", "node_id": "n1", "role_seat_id": "r1", "person_id": "p3", "start_date": "2021-01-01", "end_date": None, "status": "interim", "acting_or_interim": True,
        }, actor_user_id="u1")
        assert created["assignment_id"] == "a3"


def test_support_record_attachment_link_and_caps_enforced_without_family_side_effects():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        support = organization_service.create_support_record("org1", {
            "support_record_id": "s1", "target_type": "assignment", "target_id": "a1", "upload_id": "u1", "privacy_level": "confidential",
        }, actor_user_id="u1")
        assert support["target_type"] == "assignment"

        link = organization_service.create_linked_organization("org1", {
            "linked_organization_id": "org2", "link_type": "subordinate_command"
        }, actor_user_id="u1")
        assert link["link_type"] == "subordinate_command"
        assert db["family_links"].count_documents({}) == 0

        for idx in range(2, 26):
            organization_service.create_support_record("org1", {
                "support_record_id": f"s{idx}", "target_type": "organization", "target_id": "org1", "upload_id": f"u{idx}", "privacy_level": "private",
            }, actor_user_id="u1")
        with pytest.raises(ValueError):
            organization_service.create_support_record("org1", {
                "support_record_id": "s26", "target_type": "organization", "target_id": "org1", "upload_id": "u26", "privacy_level": "private",
            }, actor_user_id="u1")


def test_node_cap_and_sensitive_audit_log_written():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        for idx in range(1, 16):
            organization_service.create_organization_node("org1", {"node_key": f"n{idx}", "node_name": f"N{idx}", "node_type": "custom"}, actor_user_id="u1")
        with pytest.raises(ValueError):
            organization_service.create_organization_node("org1", {"node_key": "overflow", "node_name": "Overflow", "node_type": "custom"}, actor_user_id="u1")

    payload = organizations.SupportRecordCreate(
        support_record_id="s1",
        target_type="assignment",
        target_id="a1",
        upload_id="u1",
        privacy_level="confidential",
        sensitive=True,
    )
    with patch("app.routes.organizations.require_package_capability", return_value={"id": "u1"}), patch(
        "app.routes.organizations.create_support_record",
        return_value={"support_record_id": "s1"},
    ), patch("app.routes.organizations.write_audit_log") as audit_mock:
        organizations.post_support_records(
            "org1",
            payload,
            current_user={"id": "u1", "email": "u1@example.com"},
        )
        assert audit_mock.call_count >= 2


def test_command_structure_button_matrix_has_all_phase4_buttons_and_no_family_wording():
    with patch("app.routes.organizations.require_package_capability", return_value={"id": "u1"}):
        payload = organizations.get_command_structure_button_matrix(current_user={"id": "u1"})

    buttons = payload["buttons"]
    labels = {item["button"] for item in buttons}
    assert len(labels) == 23
    expected = {
        "Create Organization Profile",
        "Choose Organization Template",
        "Add Organization Node",
        "Add Role Seat",
        "Add Person / Officer",
        "Assign Person to Role",
        "End Term / Mark Former",
        "Replace Leader / Officer",
        "Mark Retired / Emeritus / Transferred / Deceased",
        "Add Transition Event",
        "Upload Support Record",
        "Verify Support Record",
        "Open Leadership Viewer",
        "View Current Command Structure",
        "View Historical Date",
        "View Succession Timeline",
        "View Officer Wall",
        "Link Organization",
        "Review Link Request",
        "Export Command Roster",
        "Invite Admin Seat",
        "Add Ops / Support Note",
        "Request White-Glove Review",
    }
    assert labels == expected

    for item in buttons:
        assert item["status"] in {"live", "hidden", "unavailable"}
        blob = " ".join(str(value).lower() for value in item.values())
        assert "family" not in blob
        assert "spouse" not in blob
        assert "child" not in blob
        assert "parent" not in blob
        assert "household" not in blob


def test_command_structure_button_matrix_unavailable_buttons_are_clearly_marked():
    with patch("app.routes.organizations.require_package_capability", return_value={"id": "u1"}):
        payload = organizations.get_command_structure_button_matrix(current_user={"id": "u1"})
    buttons = payload["buttons"]
    by_name = {item["button"]: item for item in buttons}

    assert by_name["Verify Support Record"]["status"] == "live"
    assert by_name["View Historical Date"]["status"] == "live"
    assert by_name["View Succession Timeline"]["status"] == "live"
    assert by_name["View Officer Wall"]["status"] == "live"
    assert by_name["Export Command Roster"]["status"] == "live"
    assert by_name["Invite Admin Seat"]["status"] == "live"
    assert by_name["Add Ops / Support Note"]["status"] == "live"
    assert by_name["Request White-Glove Review"]["status"] == "live"


def test_historical_snapshot_and_succession_timeline_are_assignment_based():
    db = _setup_fake_db()
    _seed_org_graph(db)
    with patch("app.services.organization_service.get_database", return_value=db):
        historical = organization_service.get_historical_snapshot("org1", snapshot_date=date.fromisoformat("2020-06-01"))
        roles = historical["nodes"][0]["role_seats"]
        assert roles[0]["filled"] is True
        assert roles[0]["person"]["person_id"] == "p2"

        succession = organization_service.get_role_seat_succession("org1", "r1")
        assert [item["assignment_id"] for item in succession] == ["a1", "a2"]


def test_officer_wall_support_verification_export_and_notes_white_glove_are_live():
    db = _setup_fake_db()
    _seed_org_graph(db)
    with patch("app.services.organization_service.get_database", return_value=db):
        wall = organization_service.get_officer_wall("org1")
        assert {item["person"]["person_id"] for item in wall} == {"p1", "p2"}
        assert "former" in {item["status"] for item in wall}

        organization_service.create_support_record(
            "org1",
            {
                "support_record_id": "s1",
                "target_type": "assignment",
                "target_id": "a2",
                "upload_id": "u1",
            },
            actor_user_id="u1",
        )
        verified = organization_service.verify_support_record("org1", "s1", verification_status="verified", note="ok", actor_user_id="u1")
        assert verified["verification_status"] == "verified"

        roster = organization_service.export_command_roster("org1")
        assert len(roster) == 1
        assert roster[0]["person"] == "Alex Prime"

        invite = organization_service.create_admin_invite(
            "org1",
            {"project_id": "proj1", "email": "admin@example.com", "role": "organization_admin"},
            actor_user_id="u1",
        )
        invite_dup = organization_service.create_admin_invite(
            "org1",
            {"project_id": "proj1", "email": "admin@example.com", "role": "organization_admin"},
            actor_user_id="u1",
        )
        assert invite["_id"] == invite_dup["_id"]

        note = organization_service.create_organization_note(
            "org1",
            {"project_id": "proj1", "note": "internal check", "visibility": "internal"},
            actor_user_id="u1",
        )
        assert note["visibility"] == "internal"

        request = organization_service.create_white_glove_request(
            "org1",
            {"project_id": "proj1", "note": "assist"},
            actor_user_id="u1",
        )
        request_dup = organization_service.create_white_glove_request(
            "org1",
            {"project_id": "proj1", "note": "assist"},
            actor_user_id="u1",
        )
        assert request_dup["status"] == "requested"
        assert request_dup["_id"] == request["_id"]


def test_transition_duplicate_protection_is_retry_safe():
    db = _setup_fake_db()
    with patch("app.services.organization_service.get_database", return_value=db):
        created = organization_service.create_transition(
            "org1",
            {"transition_id": "t1", "event_type": "appointed", "event_date": "2024-01-01"},
            actor_user_id="u1",
        )
        assert created["transition_id"] == "t1"
        with pytest.raises(ValueError):
            organization_service.create_transition(
                "org1",
                {"transition_id": "t1", "event_type": "appointed", "event_date": "2024-01-01"},
                actor_user_id="u1",
            )
        created2 = organization_service.create_transition(
            "org1",
            {"transition_id": "t2", "event_type": "appointed", "event_date": "2024-01-01"},
            actor_user_id="u1",
        )
        assert created2["transition_id"] == "t2"
