import unittest
from unittest.mock import patch

from app.routes import project_entitlements
from app.services import project_entitlement_service


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeEntitlementCollection:
    def __init__(self, docs):
        self._docs = list(docs)
        self.last_query = None

    def find(self, query):
        self.last_query = query
        return _FakeCursor(self._docs)


class ProjectEntitlementAccessTests(unittest.TestCase):
    def test_service_uses_email_memberships_when_listing_user_entitlements(self):
        fake_collection = _FakeEntitlementCollection(
            [
                {
                    "_id": "entitlement-1",
                    "project_id": "project-123",
                    "user_id": "owner-1",
                    "package_code": "legacy_plus",
                    "package_name": "Legacy Plus",
                    "package_lane": "household",
                    "status": "active",
                    "active_addons": [],
                    "created_at": "2026-04-16T00:00:00Z",
                    "updated_at": "2026-04-16T00:00:00Z",
                }
            ]
        )

        with (
            patch.object(
                project_entitlement_service,
                "_collection",
                return_value=fake_collection,
            ),
            patch.object(
                project_entitlement_service,
                "list_accessible_project_ids",
                return_value=["project-123"],
            ) as project_ids_mock,
        ):
            items = project_entitlement_service.list_user_project_entitlements(
                "invitee-1",
                email="invitee@example.com",
                active_only=True,
            )

        project_ids_mock.assert_called_once_with(
            user_id="invitee-1",
            email="invitee@example.com",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("project_id"), "project-123")
        self.assertEqual(items[0].get("package_code"), "legacy_plus")

    def test_route_passes_current_user_email_to_entitlement_service(self):
        with patch.object(
            project_entitlements,
            "list_user_project_entitlements",
            return_value=[],
        ) as service_mock:
            payload = project_entitlements.list_my_project_entitlements(
                current_user={"id": "invitee-1", "email": "Invitee@Example.com"},
            )

        service_mock.assert_called_once_with(
            "invitee-1",
            email="invitee@example.com",
            active_only=True,
        )
        self.assertEqual(payload, {"items": []})


if __name__ == "__main__":
    unittest.main()
