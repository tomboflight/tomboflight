from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.admin_permission_registry import CEO_MASTER_ADMIN_EMAIL
from app.database import DatabaseUnavailableError
from app.routes import admin_continuity_runtime as route_module


def _client_for_actor(actor: dict) -> TestClient:
    app = FastAPI()
    app.include_router(route_module.router)
    for route in route_module.router.routes:
        for dependency in route.dependant.dependencies:
            app.dependency_overrides[dependency.call] = lambda actor=actor: actor
    return TestClient(app)


class TestContinuityRuntimeRoute(unittest.TestCase):
    def setUp(self) -> None:
        self.ceo = {
            "_id": "ceo-user-1",
            "email": CEO_MASTER_ADMIN_EMAIL,
            "full_name": "CEO Operator",
            "role_codes": ["ceo_master_admin"],
        }

    def test_status_is_actor_aware_without_exposing_write_capability_to_other_roles(self) -> None:
        client = _client_for_actor(self.ceo)
        with patch.object(
            route_module,
            "runtime_status",
            return_value={"runtime_version": "8.0.0", "execution_enabled": True, "action_count": 27},
        ):
            response = client.get("/admin/control-center/kernel/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_actor_role"], "SUPERADMIN")
        self.assertTrue(response.json()["one_step_execution_allowed"])

    def test_canonical_ceo_route_delegates_to_governed_execution_service(self) -> None:
        client = _client_for_actor(self.ceo)
        expected = {"operation_id": "ckop-1", "state": "apply_executed"}
        with patch.object(route_module, "execute_governed_action", return_value=expected) as execute:
            response = client.post(
                "/admin/control-center/kernel/execute",
                json={
                    "action": "package_change",
                    "target": {"project_id": "project-1"},
                    "parameters": {"package_code": "legacy_portrait"},
                    "reason": "Reconcile canonical package state",
                    "idempotency_key": "kernel-route-idempotency-1",
                    "confirmed": True,
                    "solo_founder_override_acknowledged": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(execute.call_args.kwargs["actor"], self.ceo)

    def test_noncanonical_super_admin_cannot_use_ceo_one_step_execution(self) -> None:
        other_super_admin = {
            "_id": "admin-user-2",
            "email": "other-admin@example.com",
            "role_codes": ["super_admin"],
        }
        client = _client_for_actor(other_super_admin)
        with patch.object(route_module, "execute_governed_action") as execute:
            response = client.post(
                "/admin/control-center/kernel/execute",
                json={
                    "action": "package_change",
                    "target": {"project_id": "project-1"},
                    "parameters": {"package_code": "legacy_portrait"},
                    "reason": "Reconcile canonical package state",
                    "idempotency_key": "kernel-route-idempotency-2",
                    "confirmed": True,
                    "solo_founder_override_acknowledged": True,
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(execute.call_count, 0)

    def test_database_unavailable_maps_to_service_unavailable(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            route_module._raise_service_error(DatabaseUnavailableError("database unavailable"))

        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
