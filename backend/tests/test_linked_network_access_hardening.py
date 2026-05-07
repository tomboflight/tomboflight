import unittest
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.routes import linked_network as linked_network_routes
from app.services import workspace_access_service


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction):
        reverse = direction < 0
        self._docs.sort(key=lambda item: str(item.get(key) or ""), reverse=reverse)
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, docs=None):
        self._docs = list(docs or [])

    def find_one(self, query=None, sort=None):
        query = query or {}
        candidates = [item for item in self._docs if self._matches(item, query)]
        if sort and candidates:
            key, direction = sort[0]
            candidates.sort(key=lambda item: str(item.get(key) or ""), reverse=direction < 0)
        return candidates[0] if candidates else None

    def find(self, query=None):
        query = query or {}
        return _FakeCursor([item for item in self._docs if self._matches(item, query)])

    def _matches(self, item, query):
        if "$or" in query:
            return any(self._matches(item, candidate) for candidate in query["$or"])
        for key, expected in query.items():
            if key == "$or":
                continue
            value = item.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if value not in expected["$in"]:
                        return False
                else:
                    return False
            elif value != expected:
                return False
        return True


class _FakeDatabase:
    def __init__(self, collections=None):
        self._collections = {
            name: _FakeCollection(docs)
            for name, docs in (collections or {}).items()
        }

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection())


class StrictEntitlementResolverTests(unittest.TestCase):
    def test_strict_resolver_requires_paid_order(self):
        project_id = str(ObjectId())
        db = _FakeDatabase(
            {
                "project_entitlements": [
                    {
                        "project_id": project_id,
                        "status": "active",
                        "package_code": "family_estate_concierge",
                    }
                ],
                "orders": [],
            }
        )
        with patch.object(workspace_access_service, "get_database", return_value=db):
            with self.assertRaises(PermissionError):
                workspace_access_service.resolve_strict_paid_active_project_entitlement(
                    project_id
                )

    def test_strict_resolver_denies_mismatched_package_and_audits(self):
        project_id = str(ObjectId())
        db = _FakeDatabase(
            {
                "project_entitlements": [
                    {
                        "project_id": project_id,
                        "status": "active",
                        "package_code": "family_estate_concierge",
                        "package_lane": "network",
                    }
                ],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "project_id": project_id,
                        "item_type": "package",
                        "status": "paid",
                        "package_code": "legacy_plus",
                        "package_lane": "household",
                    }
                ],
            }
        )
        with (
            patch.object(workspace_access_service, "get_database", return_value=db),
            patch.object(workspace_access_service, "create_audit_log") as audit_log_mock,
        ):
            with self.assertRaises(PermissionError):
                workspace_access_service.resolve_strict_paid_active_project_entitlement(
                    project_id
                )
        audit_log_mock.assert_called()

    def test_strict_resolver_returns_resolved_entitlements_when_records_match(self):
        project_id = str(ObjectId())
        db = _FakeDatabase(
            {
                "project_entitlements": [
                    {
                        "project_id": project_id,
                        "status": "active",
                        "package_code": "family_estate_concierge",
                        "active_addons": [],
                        "package_lane": "network",
                    }
                ],
                "orders": [
                    {
                        "_id": ObjectId(),
                        "project_id": project_id,
                        "item_type": "package",
                        "status": "paid",
                        "package_code": "family_estate_concierge",
                        "package_lane": "network",
                    }
                ],
            }
        )
        with patch.object(workspace_access_service, "get_database", return_value=db):
            resolved = workspace_access_service.resolve_strict_paid_active_project_entitlement(
                project_id
            )
        self.assertEqual(resolved.get("package_code"), "family_estate_concierge")
        self.assertTrue(
            bool((resolved.get("resolved_entitlements") or {}).get("can_link_households"))
        )


class LinkedNetworkRouteHardeningTests(unittest.TestCase):
    def test_route_requires_workspace_capability_before_network_build(self):
        project_id = str(ObjectId())
        context = {
            "project": {"_id": project_id},
            "resolved_entitlements": {"can_link_households": True},
        }
        with (
            patch.object(
                linked_network_routes,
                "require_workspace_capability",
                return_value=context,
            ) as capability_mock,
            patch.object(
                linked_network_routes,
                "build_linked_network",
                return_value={"network_summary": {"root_project_id": project_id}},
            ) as build_mock,
        ):
            payload = linked_network_routes.get_linked_network(
                project_id,
                current_user={"id": "user-1", "email": "user@example.com"},
            )
        capability_mock.assert_called_once()
        build_mock.assert_called_once_with(
            project_id,
            "user-1",
            workspace_context=context,
        )
        self.assertEqual(payload["network_summary"]["root_project_id"], project_id)

    def test_route_denies_cross_workspace_project_id_guess(self):
        project_id = str(ObjectId())
        with patch.object(
            linked_network_routes,
            "require_workspace_capability",
            side_effect=HTTPException(status_code=403, detail="Not authorized to access this workspace."),
        ):
            with self.assertRaises(HTTPException) as error:
                linked_network_routes.get_linked_network(
                    project_id,
                    current_user={"id": "attacker", "email": "attacker@example.com"},
                )
        self.assertEqual(error.exception.status_code, 403)


class WorkspaceCapabilityStrictEntitlementTests(unittest.TestCase):
    def test_workspace_capability_denies_when_linked_network_entitlement_missing(self):
        project_oid = ObjectId()
        db = _FakeDatabase(
            {
                "projects": [
                    {
                        "_id": project_oid,
                        "owner_user_id": "owner-1",
                        "owner_email": "owner@example.com",
                    }
                ],
                "project_entitlements": [],
                "orders": [],
            }
        )
        with (
            patch.object(workspace_access_service, "get_database", return_value=db),
            patch.object(
                workspace_access_service,
                "get_project_access_snapshot",
                return_value={"accessible": True, "membership": {}},
            ),
        ):
            with self.assertRaises(HTTPException) as error:
                workspace_access_service.require_workspace_capability(
                    {"id": "owner-1", "email": "owner@example.com"},
                    project_id=str(project_oid),
                    capabilities=("can_link_households",),
                    detail="Your package does not include linked household network access.",
                )
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
