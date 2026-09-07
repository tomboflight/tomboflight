from __future__ import annotations

from copy import deepcopy

import pytest
from bson import ObjectId

from app.services import intake_pipeline_service as pipeline_service
from app.services import intake_submission_service as submission_service


def _safe_submission(*, status: str = "submitted") -> dict:
    return {
        "_id": ObjectId(),
        "user_id": ObjectId(),
        "email": "intake.safety@example.test",
        "package_slug": "legacy_plus",
        "package_name": "Legacy Plus",
        "status": status,
        "review_locked": True,
        "household": {
            "household_name": "Safety Family",
            "primary_contact_name": "Safety Customer",
            "primary_contact_email": "intake.safety@example.test",
        },
        "family_map": {"family_branch_name": "Safety Family"},
        "uploads": {
            "primary_asset_type": "mixed",
            "uploads_rights_confirmed": True,
            "uploads_minimization_confirmed": True,
        },
        "consent": {
            "consent_process": True,
            "consent_store": True,
            "consent_authority": True,
            "consent_review_disclaimer": True,
            "visibility_preference": "private",
        },
        "review": {"confirm_accuracy": True},
    }


class FakeCollection:
    def __init__(self, document: dict | None = None):
        self.document = deepcopy(document) if document is not None else None
        self.update_calls: list[tuple[dict, dict]] = []
        self.insert_calls: list[dict] = []

    def find_one(self, query: dict, *args, **kwargs):
        if self.document is None:
            return None
        requested_id = query.get("_id")
        if requested_id is not None and requested_id != self.document.get("_id"):
            return None
        return deepcopy(self.document)

    def update_one(self, query: dict, update: dict):
        self.update_calls.append((deepcopy(query), deepcopy(update)))
        if self.document is not None:
            for key, value in update.get("$set", {}).items():
                self.document[key] = value
            for key in update.get("$unset", {}):
                self.document.pop(key, None)
        return object()

    def insert_one(self, payload: dict):
        self.insert_calls.append(deepcopy(payload))
        result = type("InsertResult", (), {})()
        result.inserted_id = ObjectId()
        return result


class FakeDatabase:
    def __init__(self, intake_document: dict):
        self.collections = {
            "intake_submissions": FakeCollection(intake_document),
            "families": FakeCollection(),
            "households": FakeCollection(),
            "projects": FakeCollection(),
            "family_members": FakeCollection(),
        }

    def __getitem__(self, name: str):
        return self.collections.setdefault(name, FakeCollection())


def test_approval_requirements_identify_every_required_confirmation():
    submission = _safe_submission()
    submission["uploads"]["uploads_rights_confirmed"] = False
    submission["uploads"]["uploads_minimization_confirmed"] = False
    submission["consent"]["consent_process"] = False
    submission["consent"]["consent_store"] = False
    submission["consent"]["consent_authority"] = False
    submission["consent"]["consent_review_disclaimer"] = False
    submission["review"]["confirm_accuracy"] = False

    errors = submission_service.get_approval_requirement_errors(submission)

    assert errors == [
        "Upload rights confirmation is required.",
        "Upload minimization confirmation is required.",
        "Consent to process is required.",
        "Consent to store is required.",
        "Authority confirmation is required.",
        "Review disclaimer acknowledgment is required.",
        "Intake accuracy confirmation is required.",
    ]


def test_admin_approval_fails_closed_when_required_attestation_is_false(monkeypatch):
    submission = _safe_submission()
    submission["uploads"]["uploads_rights_confirmed"] = False
    submission["consent"]["consent_authority"] = False
    collection = FakeCollection(submission)
    monkeypatch.setattr(submission_service, "_collection", lambda: collection)

    with pytest.raises(ValueError) as exc_info:
        submission_service.update_status(
            submission_id=str(submission["_id"]),
            new_status="approved",
            reviewed_by="ceo@example.test",
        )

    message = str(exc_info.value)
    assert message.startswith("Intake approval blocked:")
    assert "Upload rights confirmation is required." in message
    assert "Authority confirmation is required." in message
    assert collection.update_calls == []


def test_incomplete_intake_can_enter_review_without_becoming_approved(monkeypatch):
    submission = _safe_submission()
    submission["consent"]["consent_review_disclaimer"] = False
    collection = FakeCollection(submission)
    monkeypatch.setattr(submission_service, "_collection", lambda: collection)

    updated = submission_service.update_status(
        submission_id=str(submission["_id"]),
        new_status="in_review",
        reviewed_by="reviewer@example.test",
    )

    assert updated["status"] == "in_review"
    assert len(collection.update_calls) == 1


def test_complete_intake_can_be_approved(monkeypatch):
    submission = _safe_submission()
    collection = FakeCollection(submission)
    monkeypatch.setattr(submission_service, "_collection", lambda: collection)

    updated = submission_service.update_status(
        submission_id=str(submission["_id"]),
        new_status="approved",
        reviewed_by="ceo@example.test",
        approval_notes="Verified complete.",
    )

    assert updated["status"] == "approved"
    assert updated["review_locked"] is True
    assert len(collection.update_calls) == 1


def test_previously_approved_unsafe_record_cannot_be_provisioned(monkeypatch):
    submission = _safe_submission(status="approved")
    submission["uploads"]["uploads_minimization_confirmed"] = False
    fake_db = FakeDatabase(submission)
    monkeypatch.setattr(pipeline_service, "get_database", lambda: fake_db)

    with pytest.raises(ValueError) as exc_info:
        pipeline_service.provision_build_from_submission(
            submission_id=str(submission["_id"]),
            provisioned_by="ceo@example.test",
            provisioned_by_user_id=str(ObjectId()),
        )

    assert "Intake approval blocked:" in str(exc_info.value)
    assert "Upload minimization confirmation is required." in str(exc_info.value)
    assert fake_db["families"].insert_calls == []
    assert fake_db["households"].insert_calls == []
    assert fake_db["projects"].insert_calls == []
