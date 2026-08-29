import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.routes import legacy_messages as legacy_message_routes
from app.schemas.legacy_message import LegacyMessageCreate, LegacyMessageUpdate
from app.services import legacy_message_service
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, matched_count=0, modified_count=0):
        self.matched_count = matched_count
        self.modified_count = modified_count


class FakeDeleteResult:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count


class FakeCursor(list):
    def sort(self, key, direction):
        reverse = int(direction) < 0
        return FakeCursor(
            sorted(self, key=lambda item: str(item.get(key) or ""), reverse=reverse)
        )


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = [dict(document) for document in (documents or [])]

    @staticmethod
    def _matches(document, query):
        return all(
            document.get(key) == expected for key, expected in (query or {}).items()
        )

    def find_one(self, query=None):
        return next(
            (
                document
                for document in self.documents
                if self._matches(document, query or {})
            ),
            None,
        )

    def find(self, query=None):
        return FakeCursor(
            document
            for document in self.documents
            if self._matches(document, query or {})
        )

    def insert_one(self, document):
        stored = dict(document)
        stored["_id"] = stored.get("_id") or ObjectId()
        self.documents.append(stored)
        return FakeInsertResult(stored["_id"])

    def update_one(self, query, update):
        document = self.find_one(query)
        if document is None:
            return FakeUpdateResult()
        before = dict(document)
        document.update(update.get("$set", {}))
        return FakeUpdateResult(
            matched_count=1,
            modified_count=1 if document != before else 0,
        )

    def delete_one(self, query):
        document = self.find_one(query)
        if document is None:
            return FakeDeleteResult()
        self.documents.remove(document)
        return FakeDeleteResult(1)


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


def _message_document(
    *,
    message_id=None,
    project_id="project-a",
    owner_user_id="owner-1",
    status="active",
    release_trigger="on_date",
    release_value="2099-01-01T00:00:00+00:00",
    recipient_scope="named_list",
    named_recipients=None,
):
    return {
        "_id": message_id or ObjectId(),
        "project_id": project_id,
        "owner_user_id": owner_user_id,
        "title": "For later",
        "content": "Private legacy message",
        "message_type": "letter",
        "status": status,
        "release_trigger": release_trigger,
        "release_value": release_value,
        "recipient_scope": recipient_scope,
        "named_recipients": list(named_recipients or ["recipient-1"]),
    }


class LegacyMessageSchemaTests(unittest.TestCase):
    def test_on_date_requires_release_value(self):
        with self.assertRaises(ValidationError):
            LegacyMessageCreate(
                project_id="project-a",
                title="Later",
                content="Content",
                release_trigger="on_date",
                recipient_scope="named_list",
                named_recipients=["recipient-1"],
            )

    def test_update_rejects_unknown_trigger(self):
        with self.assertRaises(ValidationError):
            LegacyMessageUpdate(release_trigger="whenever")

    def test_named_recipient_ids_are_normalized_and_deduplicated(self):
        payload = LegacyMessageCreate(
            project_id="project-a",
            title="Now",
            content="Content",
            release_trigger="immediate",
            recipient_scope="named_list",
            named_recipients=[" recipient-1 ", "recipient-1", "recipient-2"],
        )
        self.assertEqual(payload.named_recipients, ["recipient-1", "recipient-2"])


class LegacyMessageServiceSecurityTests(unittest.TestCase):
    def test_2099_message_cannot_be_read_now(self):
        document = _message_document()
        db = FakeDatabase({"legacy_messages": [document]})
        fixed_now = datetime(2026, 8, 29, tzinfo=timezone.utc)
        with (
            patch.object(legacy_message_service, "get_database", return_value=db),
            patch.object(legacy_message_service, "_utcnow", return_value=fixed_now),
            patch.object(legacy_message_service, "create_audit_log") as audit,
        ):
            with self.assertRaisesRegex(PermissionError, "not been released"):
                legacy_message_service.get_legacy_message(
                    str(document["_id"]),
                    "recipient-1",
                    authorized_project_id="project-a",
                )

        self.assertEqual(document["status"], "active")
        audit.assert_not_called()

    def test_future_date_fails_closed_even_if_row_claims_released(self):
        document = _message_document(status="released")
        db = FakeDatabase({"legacy_messages": [document]})
        with (
            patch.object(legacy_message_service, "get_database", return_value=db),
            patch.object(
                legacy_message_service,
                "_utcnow",
                return_value=datetime(2026, 8, 29, tzinfo=timezone.utc),
            ),
        ):
            with self.assertRaisesRegex(PermissionError, "not been released"):
                legacy_message_service.get_legacy_message(
                    str(document["_id"]),
                    "recipient-1",
                    authorized_project_id="project-a",
                )

    def test_non_recipient_cannot_read_released_message(self):
        document = _message_document(
            status="released",
            release_trigger="immediate",
            release_value=None,
        )
        db = FakeDatabase({"legacy_messages": [document]})
        with patch.object(legacy_message_service, "get_database", return_value=db):
            with self.assertRaisesRegex(PermissionError, "Access denied"):
                legacy_message_service.get_legacy_message(
                    str(document["_id"]),
                    "intruder-1",
                    authorized_project_id="project-a",
                )

    def test_cross_project_read_is_denied_even_to_owner(self):
        document = _message_document()
        db = FakeDatabase({"legacy_messages": [document]})
        with patch.object(legacy_message_service, "get_database", return_value=db):
            with self.assertRaisesRegex(PermissionError, "active workspace"):
                legacy_message_service.get_legacy_message(
                    str(document["_id"]),
                    "owner-1",
                    authorized_project_id="project-b",
                )

    def test_due_date_transitions_once_and_records_release_audit(self):
        document = _message_document(release_value="2025-01-01T00:00:00+00:00")
        db = FakeDatabase({"legacy_messages": [document]})
        fixed_now = datetime(2026, 8, 29, tzinfo=timezone.utc)
        with (
            patch.object(legacy_message_service, "get_database", return_value=db),
            patch.object(legacy_message_service, "_utcnow", return_value=fixed_now),
            patch.object(legacy_message_service, "create_audit_log") as audit,
        ):
            first = legacy_message_service.get_legacy_message(
                str(document["_id"]),
                "recipient-1",
                authorized_project_id="project-a",
            )
            second = legacy_message_service.get_legacy_message(
                str(document["_id"]),
                "recipient-1",
                authorized_project_id="project-a",
            )

        self.assertEqual(first["status"], "released")
        self.assertEqual(second["status"], "released")
        self.assertEqual(first["release_source"], "scheduled_date")
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[0], "legacy_message_released")
        self.assertIsNone(audit.call_args.args[1])

    def test_scheduled_activation_arms_without_releasing_and_audits_activation(self):
        document = _message_document(status="draft")
        db = FakeDatabase({"legacy_messages": [document]})
        fixed_now = datetime(2026, 8, 29, tzinfo=timezone.utc)
        with (
            patch.object(legacy_message_service, "get_database", return_value=db),
            patch.object(legacy_message_service, "_utcnow", return_value=fixed_now),
            patch.object(legacy_message_service, "create_audit_log") as audit,
        ):
            activated = legacy_message_service.activate_legacy_message(
                str(document["_id"]),
                "owner-1",
                authorized_project_id="project-a",
            )
            with self.assertRaisesRegex(PermissionError, "not been released"):
                legacy_message_service.get_legacy_message(
                    str(document["_id"]),
                    "recipient-1",
                    authorized_project_id="project-a",
                )

        self.assertEqual(activated["status"], "active")
        self.assertIsNone(activated.get("released_at"))
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[0], "legacy_message_activated")

    def test_immediate_activation_records_activation_and_release(self):
        document = _message_document(
            status="draft",
            release_trigger="immediate",
            release_value=None,
        )
        db = FakeDatabase({"legacy_messages": [document]})
        with (
            patch.object(legacy_message_service, "get_database", return_value=db),
            patch.object(
                legacy_message_service,
                "_utcnow",
                return_value=datetime(2026, 8, 29, tzinfo=timezone.utc),
            ),
            patch.object(legacy_message_service, "create_audit_log") as audit,
        ):
            activated = legacy_message_service.activate_legacy_message(
                str(document["_id"]),
                "owner-1",
                authorized_project_id="project-a",
            )

        self.assertEqual(activated["status"], "released")
        self.assertEqual(activated["release_source"], "activation_immediate")
        self.assertEqual(
            [call.args[0] for call in audit.call_args_list],
            ["legacy_message_activated", "legacy_message_released"],
        )
        self.assertEqual(audit.call_args_list[0].args[4]["from_status"], "draft")
        self.assertEqual(audit.call_args_list[0].args[4]["to_status"], "active")
        self.assertEqual(audit.call_args_list[1].args[4]["from_status"], "active")
        self.assertEqual(audit.call_args_list[1].args[4]["to_status"], "released")

    def test_manual_message_requires_explicit_release_and_audits_it(self):
        document = _message_document(
            status="draft",
            release_trigger="manual",
            release_value=None,
        )
        db = FakeDatabase({"legacy_messages": [document]})
        with (
            patch.object(legacy_message_service, "get_database", return_value=db),
            patch.object(
                legacy_message_service,
                "_utcnow",
                return_value=datetime(2026, 8, 29, tzinfo=timezone.utc),
            ),
            patch.object(legacy_message_service, "create_audit_log") as audit,
        ):
            activated = legacy_message_service.activate_legacy_message(
                str(document["_id"]),
                "owner-1",
                authorized_project_id="project-a",
            )
            with self.assertRaisesRegex(PermissionError, "not been released"):
                legacy_message_service.get_legacy_message(
                    str(document["_id"]),
                    "recipient-1",
                    authorized_project_id="project-a",
                )
            released = legacy_message_service.release_legacy_message(
                str(document["_id"]),
                "owner-1",
                authorized_project_id="project-a",
            )

        self.assertEqual(activated["status"], "active")
        self.assertEqual(released["status"], "released")
        self.assertEqual(released["release_source"], "manual_owner_release")
        self.assertEqual(
            [call.args[0] for call in audit.call_args_list],
            ["legacy_message_activated", "legacy_message_released"],
        )

    def test_activation_rejects_unverifiable_recipient_scope(self):
        document = _message_document(
            status="draft",
            release_trigger="immediate",
            release_value=None,
            recipient_scope="descendants",
            named_recipients=[],
        )
        db = FakeDatabase({"legacy_messages": [document]})
        with patch.object(legacy_message_service, "get_database", return_value=db):
            with self.assertRaisesRegex(ValueError, "named_list"):
                legacy_message_service.activate_legacy_message(
                    str(document["_id"]),
                    "owner-1",
                    authorized_project_id="project-a",
                )
        self.assertEqual(document["status"], "draft")


class LegacyMessageRouteSecurityTests(unittest.TestCase):
    @staticmethod
    def _context(*, scheduled=True, household=True, project_id="project-a"):
        return {
            "project": {"_id": project_id},
            "resolved_entitlements": {
                "can_use_future_message_vault": True,
                "can_use_household_vault": household,
                "can_use_scheduled_reveal": scheduled,
            },
            "member_role": "viewer",
            "is_admin": False,
        }

    def test_blank_authenticated_identity_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            legacy_message_routes._current_user_id({"id": "   "})
        self.assertEqual(caught.exception.status_code, 401)

    def test_context_enforces_future_vault_capability_and_membership_role(self):
        context = self._context()
        with (
            patch.object(
                legacy_message_routes,
                "require_workspace_capability",
                return_value=context,
            ) as capability,
            patch.object(
                legacy_message_routes,
                "require_workspace_member_role",
            ) as role,
        ):
            project_id = legacy_message_routes._resolve_legacy_message_context(
                {"id": "recipient-1"},
                project_id="project-a",
                scheduled_reveal=True,
                write=False,
            )

        self.assertEqual(project_id, "project-a")
        self.assertEqual(
            capability.call_args.kwargs["capabilities"],
            ("can_use_future_message_vault",),
        )
        self.assertIn("viewer", role.call_args.kwargs["allowed_roles"])

    def test_context_rejects_missing_scheduled_reveal_entitlement(self):
        with (
            patch.object(
                legacy_message_routes,
                "require_workspace_capability",
                return_value=self._context(scheduled=False),
            ),
            patch.object(legacy_message_routes, "require_workspace_member_role"),
        ):
            with self.assertRaises(HTTPException) as caught:
                legacy_message_routes._resolve_legacy_message_context(
                    {"id": "owner-1"},
                    project_id="project-a",
                    scheduled_reveal=True,
                    write=True,
                )
        self.assertEqual(caught.exception.status_code, 403)

    def test_context_rejects_missing_household_vault_entitlement(self):
        with (
            patch.object(
                legacy_message_routes,
                "require_workspace_capability",
                return_value=self._context(household=False),
            ),
            patch.object(legacy_message_routes, "require_workspace_member_role"),
        ):
            with self.assertRaises(HTTPException) as caught:
                legacy_message_routes._resolve_legacy_message_context(
                    {"id": "owner-1"},
                    project_id="project-a",
                    scheduled_reveal=False,
                    write=True,
                )
        self.assertEqual(caught.exception.status_code, 403)

    def test_get_route_passes_canonical_workspace_to_service(self):
        with (
            patch.object(
                legacy_message_routes,
                "get_legacy_message_access_descriptor",
                return_value={
                    "id": "message-1",
                    "project_id": "project-a",
                    "release_trigger": "on_date",
                    "status": "active",
                },
            ),
            patch.object(
                legacy_message_routes,
                "_resolve_legacy_message_context",
                return_value="project-a",
            ) as context,
            patch.object(
                legacy_message_routes,
                "get_legacy_message",
                return_value={"id": "message-1", "status": "active"},
            ) as get_message,
        ):
            result = legacy_message_routes.get_legacy_message_route(
                "message-1",
                current_user={"id": "recipient-1"},
            )

        self.assertEqual(result["id"], "message-1")
        self.assertTrue(context.call_args.kwargs["scheduled_reveal"])
        get_message.assert_called_once_with(
            "message-1",
            "recipient-1",
            authorized_project_id="project-a",
        )


if __name__ == "__main__":
    unittest.main()
