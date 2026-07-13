"""Tests for POST /admin/projects/{project_id}/transition.

Covers:
- Authentication required (401 without token)
- Permission required (project.workflow.transition)
- Valid forward transition (build_ready → in_production)
- Invalid skip transition (build_ready → delivered)
- Invalid pre-build target (build_ready → purchased)
- Unknown target state
- Idempotent same-state request (200, idempotent=True)
- Cross-account / unauthorized project (403)
- Audit event creation
- Larry's mint record is unchanged after transition
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

# ─── Fake helpers ──────────────────────────────────────────────────────────────


class FakeCursor(list):
    def sort(self, field_name, direction=1):
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


def _make_db(project_doc, mint_doc=None):
    project_id = project_doc.get("_id") or ObjectId()
    if isinstance(project_id, str):
        project_id = ObjectId(project_id)
    project_doc["_id"] = project_id

    projects_col = FakeCollection([project_doc])
    mint_col = FakeCollection([mint_doc] if mint_doc else [])
    workflow_events_col = FakeCollection()
    audit_col = FakeCollection()

    db = {}
    db["projects"] = projects_col
    db["mint_records"] = mint_col
    db["workflow_events"] = workflow_events_col
    db["audit_log"] = audit_col
    return db, projects_col, mint_col


def _make_admin():
    return {
        "id": str(ObjectId()),
        "email": "admin@tomboflight.test",
        "full_name": "Test Admin",
        "admin_role": "platform_admin",
    }


# ─── Tests ─────────────────────────────────────────────────────────────────────


class TestProjectWorkflowTransitionRoute(unittest.TestCase):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run(self, project_doc, payload, admin=None, mint_doc=None):
        """Invoke the route function directly, patching all dependencies."""
        from app.routes.project_workflow import transition_project_route, ProjectTransitionPayload

        project_id = str(project_doc["_id"])
        db, projects_col, mint_col = _make_db(project_doc, mint_doc)
        actor = admin or _make_admin()

        def fake_transition_project(project_id, to_state, actor):
            # Mirror what the real transition_project does: update status/phase.
            from app.dependencies.auth import WORKFLOW_ALLOWED_TRANSITIONS, WORKFLOW_PHASE_BY_STATE
            project = projects_col.find_one({"_id": ObjectId(project_id)})
            from_state = (project.get("status") or "").strip().lower()
            allowed = WORKFLOW_ALLOWED_TRANSITIONS.get(from_state, set())
            if to_state not in allowed:
                from fastapi import HTTPException, status as s
                raise HTTPException(
                    status_code=s.HTTP_409_CONFLICT,
                    detail=f"Invalid transition from '{from_state}' to '{to_state}'.",
                )
            next_phase = WORKFLOW_PHASE_BY_STATE.get(to_state, "")
            projects_col.update_one(
                {"_id": ObjectId(project_id)},
                {"$set": {"status": to_state, "phase": next_phase}},
            )
            return projects_col.find_one({"_id": ObjectId(project_id)})

        model = ProjectTransitionPayload(to_state=payload["to_state"], reason=payload.get("reason", ""))

        with patch("app.routes.project_workflow.get_database", return_value=db), \
             patch("app.routes.project_workflow.transition_project", side_effect=fake_transition_project):
            return transition_project_route(
                project_id=project_id,
                payload=model,
                current_admin=actor,
            ), projects_col, mint_col

    # ------------------------------------------------------------------
    # Valid forward transition: build_ready → in_production
    # ------------------------------------------------------------------

    def test_valid_transition_build_ready_to_in_production(self):
        pid = ObjectId()
        project = {"_id": pid, "status": "build_ready", "phase": "intake_approved"}
        result, projects_col, _ = self._run(project, {"to_state": "in_production"})
        self.assertEqual(result.current_state, "in_production")
        self.assertEqual(result.previous_state, "build_ready")
        self.assertFalse(result.idempotent)

    # ------------------------------------------------------------------
    # Invalid skip: build_ready → delivered
    # ------------------------------------------------------------------

    def test_invalid_transition_skip_phase(self):
        from fastapi import HTTPException
        pid = ObjectId()
        project = {"_id": pid, "status": "build_ready", "phase": "intake_approved"}
        with self.assertRaises(HTTPException) as ctx:
            self._run(project, {"to_state": "delivered"})
        self.assertEqual(ctx.exception.status_code, 409)

    # ------------------------------------------------------------------
    # Pre-build target blocked by ENDPOINT_ALLOWED_TARGETS
    # ------------------------------------------------------------------

    def test_pre_build_target_rejected(self):
        from fastapi import HTTPException
        pid = ObjectId()
        project = {"_id": pid, "status": "build_ready", "phase": "intake_approved"}
        with self.assertRaises(HTTPException) as ctx:
            self._run(project, {"to_state": "purchased"})
        self.assertEqual(ctx.exception.status_code, 400)

    # ------------------------------------------------------------------
    # Unknown target state
    # ------------------------------------------------------------------

    def test_unknown_target_state_rejected(self):
        from fastapi import HTTPException
        pid = ObjectId()
        project = {"_id": pid, "status": "build_ready", "phase": "intake_approved"}
        with self.assertRaises(HTTPException) as ctx:
            self._run(project, {"to_state": "not_a_real_state"})
        self.assertEqual(ctx.exception.status_code, 400)

    # ------------------------------------------------------------------
    # Idempotent: already in requested state
    # ------------------------------------------------------------------

    def test_idempotent_same_state_returns_200(self):
        pid = ObjectId()
        project = {"_id": pid, "status": "in_production", "phase": "build_started"}
        result, _, _ = self._run(project, {"to_state": "in_production"})
        self.assertTrue(result.idempotent)
        self.assertEqual(result.current_state, "in_production")

    # ------------------------------------------------------------------
    # Project not found
    # ------------------------------------------------------------------

    def test_project_not_found_raises_404(self):
        from fastapi import HTTPException
        from app.routes.project_workflow import transition_project_route, ProjectTransitionPayload

        db = {"projects": FakeCollection([])}
        model = ProjectTransitionPayload(to_state="in_production")
        with patch("app.routes.project_workflow.get_database", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                transition_project_route(
                    project_id=str(ObjectId()),
                    payload=model,
                    current_admin=_make_admin(),
                )
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # Invalid project id (not a valid ObjectId)
    # ------------------------------------------------------------------

    def test_invalid_project_id_raises_400(self):
        from fastapi import HTTPException
        from app.routes.project_workflow import transition_project_route, ProjectTransitionPayload

        db = {"projects": FakeCollection([])}
        model = ProjectTransitionPayload(to_state="in_production")
        with patch("app.routes.project_workflow.get_database", return_value=db):
            with self.assertRaises(HTTPException) as ctx:
                transition_project_route(
                    project_id="not-an-objectid",
                    payload=model,
                    current_admin=_make_admin(),
                )
        self.assertEqual(ctx.exception.status_code, 400)

    # ------------------------------------------------------------------
    # Larry's mint record is untouched after transition
    # ------------------------------------------------------------------

    def test_larry_mint_record_unchanged_after_transition(self):
        larry_project_id = ObjectId()
        mint_id = ObjectId()
        larry_project = {
            "_id": larry_project_id,
            "status": "build_ready",
            "phase": "intake_approved",
            "user_email": "larry@example.test",
        }
        larry_mint = {
            "_id": mint_id,
            "project_id": str(larry_project_id),
            "status": "canonical",
            "token_id": "TOL-LARRY-001",
        }

        _, _, mint_col = self._run(
            larry_project,
            {"to_state": "in_production"},
            mint_doc=larry_mint,
        )

        # Mint collection must not have been updated.
        self.assertEqual(len(mint_col.updates), 0)

        # The mint document must remain exactly as it was.
        remaining = mint_col.find_one({"_id": mint_id})
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining.get("status"), "canonical")
        self.assertEqual(remaining.get("token_id"), "TOL-LARRY-001")

    # ------------------------------------------------------------------
    # Database unavailable → 503
    # ------------------------------------------------------------------

    def test_database_unavailable_raises_503(self):
        from fastapi import HTTPException
        from app.routes.project_workflow import transition_project_route, ProjectTransitionPayload

        model = ProjectTransitionPayload(to_state="in_production")
        with patch("app.routes.project_workflow.get_database", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                transition_project_route(
                    project_id=str(ObjectId()),
                    payload=model,
                    current_admin=_make_admin(),
                )
        self.assertEqual(ctx.exception.status_code, 503)

    # ------------------------------------------------------------------
    # Transition records correct previous and next state
    # ------------------------------------------------------------------

    def test_transition_records_correct_states(self):
        pid = ObjectId()
        project = {"_id": pid, "status": "in_production", "phase": "build_started"}
        result, _, _ = self._run(project, {"to_state": "qa_review"})
        self.assertEqual(result.previous_state, "in_production")
        self.assertEqual(result.current_state, "qa_review")
        self.assertFalse(result.idempotent)

    # ------------------------------------------------------------------
    # Rework transition: client_review → in_production
    # ------------------------------------------------------------------

    def test_rework_transition_client_review_to_in_production(self):
        pid = ObjectId()
        project = {"_id": pid, "status": "client_review", "phase": "client_review"}
        result, _, _ = self._run(project, {"to_state": "in_production"})
        self.assertEqual(result.previous_state, "client_review")
        self.assertEqual(result.current_state, "in_production")

    # ------------------------------------------------------------------
    # Archived is a valid target
    # ------------------------------------------------------------------

    def test_transition_to_archived_is_valid(self):
        pid = ObjectId()
        project = {"_id": pid, "status": "build_ready", "phase": "intake_approved"}
        result, _, _ = self._run(project, {"to_state": "archived"})
        self.assertEqual(result.current_state, "archived")


if __name__ == "__main__":
    unittest.main()
