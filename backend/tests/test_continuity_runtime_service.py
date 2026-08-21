from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.core.admin_permission_registry import CEO_MASTER_ADMIN_EMAIL
from app.services import continuity_runtime_service as runtime


def _value_at(document: dict, dotted_key: str):
    value = document
    for part in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = _value_at(document, key)
        if isinstance(expected, dict):
            if "$nin" in expected and actual in expected["$nin"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class _FakeCursor:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def sort(self, key: str, direction: int):
        del direction
        self.documents.sort(key=lambda item: str(_value_at(item, key) or ""), reverse=True)
        return self

    def limit(self, limit: int):
        self.documents = self.documents[:limit]
        return self

    def __iter__(self):
        return iter(deepcopy(self.documents))


class _FakeCollection:
    def __init__(self):
        self.documents: list[dict] = []
        self.indexes: list[tuple] = []

    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))
        return kwargs.get("name", "index")

    def insert_one(self, document: dict):
        stored = deepcopy(document)
        stored.setdefault("_id", f"fake-{len(self.documents) + 1}")
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def find_one(self, query: dict, *args, **kwargs):
        del args, kwargs
        for document in self.documents:
            if _matches(document, query):
                return deepcopy(document)
        return None

    def update_one(self, query: dict, update: dict, *args, **kwargs):
        del args, kwargs
        for document in self.documents:
            if not _matches(document, query):
                continue
            document.update(deepcopy(update.get("$set") or {}))
            for key, value in (update.get("$push") or {}).items():
                document.setdefault(key, []).append(deepcopy(value))
            return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    def find(self, query: dict):
        return _FakeCursor([deepcopy(item) for item in self.documents if _matches(item, query)])

    def count_documents(self, query: dict):
        return sum(1 for item in self.documents if _matches(item, query))


class _FakeDatabase(dict):
    def __getitem__(self, key: str):
        if key not in self:
            self[key] = _FakeCollection()
        return super().__getitem__(key)


class TestContinuityRuntimeService(unittest.TestCase):
    def setUp(self) -> None:
        self.database = _FakeDatabase()
        self.actor = {
            "_id": "ceo-user-1",
            "email": CEO_MASTER_ADMIN_EMAIL,
            "full_name": "CEO Operator",
            "role_codes": ["ceo_master_admin"],
        }
        self.executor = Mock(return_value={"changed": True})
        self.patches = [
            patch.object(runtime, "get_database", return_value=self.database),
            patch.object(runtime, "write_audit_log", return_value="audit-1"),
            patch.object(runtime, "_snapshot_for_action", return_value={"state": "canonical"}),
            patch.object(runtime, "_preview_action", return_value={"state": "proposed"}),
            patch.object(runtime, "_invoke_action", self.executor),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def _execute(self, *, idempotency_key: str = "kernel-idempotency-0001") -> dict:
        return runtime.execute_governed_action(
            action="package_change",
            target={"project_id": "project-1"},
            parameters={"package_code": "legacy_portrait"},
            reason="Reconcile the canonical package state",
            idempotency_key=idempotency_key,
            actor=self.actor,
            confirmed=True,
            solo_founder_override_acknowledged=True,
        )

    def test_high_risk_ceo_execution_records_the_full_state_machine(self) -> None:
        operation = self._execute()

        self.assertEqual(operation["state"], "apply_executed")
        self.assertEqual(operation["execution_outcome"], "success")
        self.assertTrue(operation["validator_result"]["passed"])
        self.assertEqual(operation["structured_override"]["override_type"], "SUPERADMIN_EMERGENCY_OVERRIDE")
        self.assertEqual(
            [item["next_state"] for item in operation["transitions"]],
            ["review_requested", "officer_reviewing", "approved_for_apply", "apply_scheduled", "apply_executed"],
        )
        self.assertEqual(self.executor.call_count, 1)
        self.assertEqual(len(self.database[runtime.EVENTS_COLLECTION].documents), 4)

    def test_idempotency_replay_returns_the_existing_execution(self) -> None:
        first = self._execute()
        second = self._execute()

        self.assertEqual(second["operation_id"], first["operation_id"])
        self.assertEqual(second["state"], "apply_executed")
        self.assertEqual(self.executor.call_count, 1)

    def test_successful_execution_can_be_audit_closed(self) -> None:
        operation = self._execute(idempotency_key="kernel-idempotency-close")
        closed = runtime.close_operation(operation["operation_id"], actor=self.actor)

        self.assertEqual(operation["evidence_recording_status"], "complete")
        self.assertEqual(closed["state"], "audit_closed")

    def test_idempotency_key_cannot_be_rebound_to_a_different_target(self) -> None:
        self._execute(idempotency_key="kernel-idempotency-conflict")

        with self.assertRaisesRegex(ValueError, "different Continuity operation"):
            runtime.request_operation(
                action="package_change",
                target={"project_id": "project-2"},
                parameters={"package_code": "legacy_portrait"},
                reason="Reconcile the canonical package state",
                idempotency_key="kernel-idempotency-conflict",
                actor=self.actor,
            )

    def test_high_risk_same_actor_fails_closed_without_acknowledged_override(self) -> None:
        operation = runtime.request_operation(
            action="package_change",
            target={"project_id": "project-1"},
            parameters={"package_code": "legacy_portrait"},
            reason="Reconcile the canonical package state",
            idempotency_key="kernel-idempotency-0002",
            actor=self.actor,
        )

        with self.assertRaises(PermissionError):
            runtime.approve_operation(
                operation["operation_id"],
                approval_reason="Reconcile the canonical package state",
                actor=self.actor,
                solo_founder_override_acknowledged=False,
            )

        persisted = runtime.get_operation(operation["operation_id"])
        self.assertEqual(persisted["state"], "review_requested")
        self.assertEqual(self.executor.call_count, 0)

    def test_executor_exception_is_persisted_as_apply_failed(self) -> None:
        self.executor.side_effect = RuntimeError("domain adapter failed")

        with self.assertRaisesRegex(RuntimeError, "domain adapter failed"):
            self._execute(idempotency_key="kernel-idempotency-0003")

        operations = self.database[runtime.OPERATIONS_COLLECTION].documents
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["state"], "apply_failed")
        self.assertEqual(operations[0]["execution_error"], "domain adapter failed")

    def test_post_execution_evidence_failure_does_not_relabel_the_domain_write(self) -> None:
        operation = runtime.request_operation(
            action="package_change",
            target={"project_id": "project-1"},
            parameters={"package_code": "legacy_portrait"},
            reason="Reconcile the canonical package state",
            idempotency_key="kernel-idempotency-evidence-warning",
            actor=self.actor,
        )
        runtime.approve_operation(
            operation["operation_id"],
            approval_reason="Reconcile the canonical package state",
            actor=self.actor,
            solo_founder_override_acknowledged=True,
        )
        original_record_event = runtime._record_event

        def record_event_with_failure(current_operation, *, event_type, actor, details=None):
            if event_type == "operation_executed":
                raise RuntimeError("event ledger unavailable")
            return original_record_event(current_operation, event_type=event_type, actor=actor, details=details)

        with patch.object(runtime, "_record_event", side_effect=record_event_with_failure):
            executed = runtime.execute_operation(operation["operation_id"], actor=self.actor)

        self.assertEqual(executed["state"], "apply_executed")
        self.assertEqual(executed["execution_outcome"], "success")
        self.assertEqual(executed["evidence_recording_status"], "incomplete")
        self.assertIn("continuity_event:event ledger unavailable", executed["evidence_recording_errors"])
        with self.assertRaisesRegex(ValueError, "evidence must be complete"):
            runtime.close_operation(operation["operation_id"], actor=self.actor)

    def test_bulk_partial_failure_is_not_reported_as_full_success(self) -> None:
        self.executor.return_value = {"repaired": 3, "failed": 2}

        operation = self._execute(idempotency_key="kernel-idempotency-0004")

        self.assertEqual(operation["state"], "apply_executed")
        self.assertEqual(operation["execution_outcome"], "partial_failure")
        self.assertEqual(operation["execution_failure_count"], 2)
        self.assertIn("EXECUTION_PARTIAL_FAILURE", operation["transitions"][-1]["reason_codes"])
        with self.assertRaisesRegex(ValueError, "remediation"):
            runtime.close_operation(operation["operation_id"], actor=self.actor)

    def test_preview_blocker_fails_closed_before_approval(self) -> None:
        runtime._preview_action.return_value = {
            "blocked": True,
            "warnings": ["Active paid-order cancellation workflow is required."],
        }
        operation = runtime.request_operation(
            action="package_revoke",
            target={"project_id": "project-1"},
            parameters={},
            reason="Revoke the inactive package assignment",
            idempotency_key="kernel-idempotency-blocked",
            actor=self.actor,
        )

        self.assertEqual(operation["blocked_reasons"], ["ACTION_PREVIEW_BLOCKED"])
        with self.assertRaisesRegex(ValueError, "preflight blockers"):
            runtime.approve_operation(
                operation["operation_id"],
                approval_reason="Revoke the inactive package assignment",
                actor=self.actor,
                solo_founder_override_acknowledged=True,
            )

    def test_action_preview_before_state_is_preserved_for_rollback_review(self) -> None:
        runtime._preview_action.return_value = {"before": {"status": "active"}, "proposed_after": {"status": "disabled"}}
        operation = runtime.request_operation(
            action="account_lifecycle",
            target={"user_id": "user-2"},
            parameters={"lifecycle_action": "disable"},
            reason="Disable the compromised customer account",
            idempotency_key="kernel-idempotency-before-state",
            actor=self.actor,
        )

        self.assertEqual(operation["before_snapshot"]["action_before"], {"status": "active"})
        self.assertEqual(operation["before_snapshot"]["operational_snapshot"], {"state": "canonical"})

    def test_kill_switch_disables_execution_only_when_explicitly_set(self) -> None:
        self.assertTrue(runtime.execution_enabled(env={}))
        for value in ("1", "true", "yes", "on", "enabled"):
            with self.subTest(value=value):
                self.assertFalse(runtime.execution_enabled(env={runtime.EXECUTION_KILL_SWITCH: value}))

    def test_officer_role_can_be_resolved_from_authenticated_access_context(self) -> None:
        actor = {"_id": "officer-2", "email": "officer@example.com", "_access_context": {"role_codes": ["finance_admin"]}}
        self.assertEqual(runtime.canonical_officer_role(actor), "finance_admin")

    def test_runtime_indexes_cover_operation_and_event_identity(self) -> None:
        runtime.ensure_continuity_runtime_indexes()

        operation_indexes = self.database[runtime.OPERATIONS_COLLECTION].indexes
        event_indexes = self.database[runtime.EVENTS_COLLECTION].indexes
        self.assertTrue(any(item[1].get("name") == "continuity_operation_id_unique" for item in operation_indexes))
        self.assertTrue(any(item[1].get("name") == "continuity_idempotency_unique" for item in operation_indexes))
        self.assertTrue(any(item[1].get("name") == "continuity_event_id_unique" for item in event_indexes))


if __name__ == "__main__":
    unittest.main()
