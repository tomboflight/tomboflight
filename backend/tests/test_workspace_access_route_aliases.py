import unittest
from pathlib import Path


ROUTES_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "routes" / "workspace_access.py"
)


class WorkspaceAccessRouteAliasTests(unittest.TestCase):
    def test_legacy_workspace_access_aliases_cover_memberships_and_lifecycle_actions(self):
        source = ROUTES_PATH.read_text(encoding="utf-8")
        expected_aliases = [
            '/workspace_access/my-memberships',
            '/household-access/my-memberships',
            '/workspace_access/invites/accept',
            '/household-access/invites/accept',
            '/workspace_access/invites/{invite_id}/revoke',
            '/household-access/invites/{invite_id}/revoke',
            '/workspace_access/invites/{invite_id}/resend',
            '/household-access/invites/{invite_id}/resend',
            '/workspace_access/project/{project_id}/members/{membership_id}/role',
            '/household-access/project/{project_id}/members/{membership_id}/role',
            '/workspace_access/project/{project_id}/members/{membership_id}/revoke',
            '/household-access/project/{project_id}/members/{membership_id}/revoke',
        ]
        for alias in expected_aliases:
            self.assertIn(alias, source)


if __name__ == "__main__":
    unittest.main()
