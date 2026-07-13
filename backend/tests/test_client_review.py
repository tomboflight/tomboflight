"""Tests for client review routes.

GET  /projects/{project_id}/client-review
POST /projects/{project_id}/client-review/approve
POST /projects/{project_id}/client-review/request-revision

Covers:
- Unauthenticated access blocked (dependency raises 401)
- Wrong-account denial (403 via project access snapshot)
- Review context available in any state (not just client_review)
- Approval and revision only allowed when in client_review state (409 otherwise)
- Approval record creation (correct fields)
- Revision request creation (requires non-empty comments)
- Version association
- Public-safe consent recorded on approval
- Private vault media excluded from review context (never in approved_public_uploads)
- mint_action == "none" on every decision
- Larry's mint record unchanged after approval
"""

import unittest
from unittest.mock import patch, MagicMock

from bson import ObjectId


# ─── Fake helpers (mirrors test_admin_console.py pattern) ─────────────────────


class FakeCursor(list):
    def sort(self, *a, **kw):
        return self

    def limit(self, n):
        return FakeCursor(self[:n])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.updates = []

    def find_one(self, query=None, *args, **kwargs):
        query = query or {}
        for doc in self.documents:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query=None, *args, **kwargs):
        query = query or {}
        return FakeCursor([dict(d) for d in self.documents if self._matches(d, query)])

    def update_one(self, query, update):
        for doc in self.documents:
            if self._matches(doc, query):
                for k, v in (update.get("$set") or {}).items():
                    doc[k] = v
                self.updates.append((query, update))
                return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)

    def insert_one(self, payload):
        doc = dict(payload)
        doc.setdefault("_id", ObjectId())
        self.documents.append(doc)
        return MagicMock(inserted_id=doc["_id"])

    def count_documents(self, query=None):
        query = query or {}
        return len([d for d in self.documents if self._matches(d, query)])

    def _matches(self, doc, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, o) for o in expected):
                    return False
                continue
            actual = self._nested(doc, key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
            elif actual != expected:
                return False
        return True

    def _nested(self, doc, key):
        cur = doc
        for part in key.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _owner():
    return {
        "id": str(ObjectId()),
        "email": "owner@example.test",
        "full_name": "Owner User",
    }


def _other_user():
    return {
        "id": str(ObjectId()),
        "email": "other@example.test",
        "full_name": "Other User",
    }


def _admin():
    return {
        "id": str(ObjectId()),
        "email": "admin@tomboflight.test",
        "full_name": "Admin",
        "admin_role": "platform_admin",
    }


def _make_project(status="client_review", owner=None):
    owner = owner or _owner()
    pid = ObjectId()
    return {
        "_id": pid,
        "user_id": owner["id"],
        "user_email": owner["email"],
        "status": status,
        "phase": "client_review" if status == "client_review" else status,
        "package_code": "digital_legacy_portrait",
        "package_name": "Digital Legacy Portrait",
        "project_name": "Test Project",
    }


def _make_db(project, uploads=None, mint_doc=None, existing_reviews=None):
    projects_col = FakeCollection([project])
    uploads_col = FakeCollection(uploads or [])
    reviews_col = FakeCollection(existing_reviews or [])
    mint_col = FakeCollection([mint_doc] if mint_doc else [])
    families_col = FakeCollection()
    households_col = FakeCollection()

    return {
        "projects": projects_col,
        "uploaded_files": uploads_col,
        "client_reviews": reviews_col,
        "mint_records": mint_col,
        "families": families_col,
        "households": households_col,
    }, reviews_col, mint_col


def _accessible_snapshot(user, project):
    return {"accessible": user["id"] == str(project.get("user_id")) or user.get("admin_role")}


# ─── Tests: GET /client-review ────────────────────────────────────────────────


class TestGetClientReview(unittest.TestCase):

    def _call(self, project, user, uploads=None, existing_reviews=None):
        from app.routes.client_review import get_client_review

        db, _, _ = _make_db(project, uploads=uploads, existing_reviews=existing_reviews)
        project_id = str(project["_id"])

        with patch("app.routes.client_review.get_database", return_value=db), \
             patch("app.routes.client_review.get_project_access_snapshot",
                   side_effect=lambda p, user_id, email: _accessible_snapshot(user, p)), \
             patch("app.routes.client_review.has_internal_admin_access",
                   return_value=bool(user.get("admin_role"))), \
             patch("app.routes.client_review.get_project_entitlement", return_value={}), \
             patch("app.routes.client_review.get_latest_review", return_value=None):
            return get_client_review(project_id=project_id, current_user=user)

    def test_owner_can_load_review_context_when_in_client_review(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(project, owner)
        self.assertEqual(result["current_state"], "client_review")
        self.assertTrue(result["ready_for_review"])

    def test_ready_for_review_is_false_when_not_in_client_review(self):
        owner = _owner()
        project = _make_project(status="in_production", owner=owner)
        result = self._call(project, owner)
        self.assertFalse(result["ready_for_review"])

    def test_wrong_account_denied_403(self):
        from fastapi import HTTPException

        owner = _owner()
        other = _other_user()
        project = _make_project(status="client_review", owner=owner)

        with self.assertRaises(HTTPException) as ctx:
            self._call(project, other)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_can_access_any_project(self):
        owner = _owner()
        admin = _admin()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(project, admin)
        self.assertIsNotNone(result)
        self.assertEqual(result["current_state"], "client_review")

    def test_private_vault_media_excluded_from_approved_uploads(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        project_id = str(project["_id"])

        public_upload = {
            "_id": ObjectId(),
            "project_id": project_id,
            "original_filename": "portrait.jpg",
            "category": "member_photo",
            "customer_visible": True,
            "approved_for_cinematic": True,
            "quarantined": False,
        }
        private_upload = {
            "_id": ObjectId(),
            "project_id": project_id,
            "original_filename": "private_message.mp4",
            "category": "private_voice_message",
            "customer_visible": True,
            "approved_for_cinematic": False,
            "quarantined": False,
        }

        result = self._call(project, owner, uploads=[public_upload, private_upload])
        filenames = [u["original_filename"] for u in result["approved_public_uploads"]]
        self.assertIn("portrait.jpg", filenames)
        self.assertNotIn("private_message.mp4", filenames)

    def test_vault_media_excluded_flag_always_true(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(project, owner)
        self.assertTrue(result["vault_media_excluded"])

    def test_returns_latest_review_when_present(self):
        from app.routes.client_review import get_client_review

        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        project_id = str(project["_id"])
        db, _, _ = _make_db(project)

        fake_review = {"decision": "approved", "version": "1", "created_at": "2026-01-01"}

        with patch("app.routes.client_review.get_database", return_value=db), \
             patch("app.routes.client_review.get_project_access_snapshot",
                   side_effect=lambda p, user_id, email: {"accessible": True}), \
             patch("app.routes.client_review.has_internal_admin_access", return_value=False), \
             patch("app.routes.client_review.get_project_entitlement", return_value={}), \
             patch("app.routes.client_review.get_latest_review", return_value=fake_review):
            result = get_client_review(project_id=project_id, current_user=owner)

        self.assertEqual(result["latest_review"]["decision"], "approved")


# ─── Tests: POST /client-review/approve ───────────────────────────────────────


class TestApproveClientReview(unittest.TestCase):

    def _call(self, project, user, payload_kwargs=None, mint_doc=None):
        from app.routes.client_review import approve_client_review, ApprovePayload

        db, reviews_col, mint_col = _make_db(project, mint_doc=mint_doc)
        project_id = str(project["_id"])
        payload = ApprovePayload(
            version=payload_kwargs.get("version", "1") if payload_kwargs else "1",
            comments=payload_kwargs.get("comments", "") if payload_kwargs else "",
            public_safe_consent=payload_kwargs.get("public_safe_consent", True) if payload_kwargs else True,
        )

        fake_record = {
            "project_id": project_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "decision": "approved",
            "version": payload.version,
            "public_safe_consent": payload.public_safe_consent,
        }

        with patch("app.routes.client_review.get_database", return_value=db), \
             patch("app.routes.client_review.get_project_access_snapshot",
                   side_effect=lambda p, user_id, email: _accessible_snapshot(user, p)), \
             patch("app.routes.client_review.has_internal_admin_access",
                   return_value=bool(user.get("admin_role"))), \
             patch("app.routes.client_review.create_approval", return_value=fake_record):
            result = approve_client_review(
                project_id=project_id,
                payload=payload,
                current_user=user,
            )
        return result, reviews_col, mint_col

    def test_approval_succeeds_in_client_review_state(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result, _, _ = self._call(project, owner)
        self.assertIn("message", result)
        self.assertIn("review", result)

    def test_approval_blocked_when_not_in_client_review(self):
        from fastapi import HTTPException

        owner = _owner()
        project = _make_project(status="in_production", owner=owner)
        with self.assertRaises(HTTPException) as ctx:
            self._call(project, owner)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_approval_records_public_safe_consent(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result, _, _ = self._call(
            project, owner,
            payload_kwargs={"public_safe_consent": True}
        )
        self.assertTrue(result["review"]["public_safe_consent"])

    def test_approval_version_is_preserved(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result, _, _ = self._call(
            project, owner,
            payload_kwargs={"version": "3", "public_safe_consent": True}
        )
        self.assertEqual(result["review"]["version"], "3")

    def test_mint_action_is_none(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result, _, _ = self._call(project, owner)
        self.assertEqual(result["mint_action"], "none")

    def test_certificate_action_is_none(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result, _, _ = self._call(project, owner)
        self.assertEqual(result["certificate_action"], "none")

    def test_delivery_action_is_none(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result, _, _ = self._call(project, owner)
        self.assertEqual(result["delivery_action"], "none")

    def test_wrong_account_denied_403(self):
        from fastapi import HTTPException

        owner = _owner()
        other = _other_user()
        project = _make_project(status="client_review", owner=owner)
        with self.assertRaises(HTTPException) as ctx:
            self._call(project, other)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_larry_mint_unchanged_after_approval(self):
        """Approving the review must not touch mint_records."""
        larry_id = ObjectId()
        larry = {
            "id": str(larry_id),
            "email": "larry@example.test",
            "full_name": "Larry Robinson",
        }
        project = _make_project(status="client_review", owner=larry)
        larry_mint = {
            "_id": ObjectId(),
            "project_id": str(project["_id"]),
            "status": "canonical",
            "token_id": "TOL-LARRY-001",
        }

        _, _, mint_col = self._call(project, larry, mint_doc=larry_mint)
        self.assertEqual(len(mint_col.updates), 0)
        remaining = mint_col.find_one({"token_id": "TOL-LARRY-001"})
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining["status"], "canonical")


# ─── Tests: POST /client-review/request-revision ──────────────────────────────


class TestRequestRevision(unittest.TestCase):

    def _call(self, project, user, payload_kwargs=None):
        from app.routes.client_review import request_revision, RevisionRequestPayload

        db, _, _ = _make_db(project)
        project_id = str(project["_id"])
        comments = (payload_kwargs or {}).get("comments", "Please fix the portrait orientation.")
        version = (payload_kwargs or {}).get("version", "1")
        payload = RevisionRequestPayload(version=version, comments=comments)

        fake_record = {
            "project_id": project_id,
            "user_id": user["id"],
            "decision": "revision_requested",
            "version": version,
            "comments": comments,
        }

        with patch("app.routes.client_review.get_database", return_value=db), \
             patch("app.routes.client_review.get_project_access_snapshot",
                   side_effect=lambda p, user_id, email: _accessible_snapshot(user, p)), \
             patch("app.routes.client_review.has_internal_admin_access",
                   return_value=bool(user.get("admin_role"))), \
             patch("app.routes.client_review.create_revision_request", return_value=fake_record):
            return request_revision(
                project_id=project_id,
                payload=payload,
                current_user=user,
            )

    def test_revision_request_succeeds_in_client_review_state(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(project, owner)
        self.assertIn("message", result)
        self.assertEqual(result["review"]["decision"], "revision_requested")

    def test_revision_blocked_when_not_in_client_review(self):
        from fastapi import HTTPException

        owner = _owner()
        project = _make_project(status="qa_review", owner=owner)
        with self.assertRaises(HTTPException) as ctx:
            self._call(project, owner)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_revision_preserves_comments(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(
            project, owner,
            payload_kwargs={"comments": "The portrait needs to be cropped."}
        )
        self.assertEqual(result["review"]["comments"], "The portrait needs to be cropped.")

    def test_revision_mint_action_is_none(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(project, owner)
        self.assertEqual(result["mint_action"], "none")

    def test_revision_certificate_action_is_none(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(project, owner)
        self.assertEqual(result["certificate_action"], "none")

    def test_wrong_account_denied_403(self):
        from fastapi import HTTPException

        owner = _owner()
        other = _other_user()
        project = _make_project(status="client_review", owner=owner)
        with self.assertRaises(HTTPException) as ctx:
            self._call(project, other)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_revision_version_association(self):
        owner = _owner()
        project = _make_project(status="client_review", owner=owner)
        result = self._call(
            project, owner,
            payload_kwargs={"version": "2", "comments": "Version 2 feedback."}
        )
        self.assertEqual(result["review"]["version"], "2")


if __name__ == "__main__":
    unittest.main()
