import unittest
import ast
from pathlib import Path


ROUTES_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "routes" / "workspace_access.py"
)


class WorkspaceAccessRouteAliasTests(unittest.TestCase):
    def test_legacy_route_aliases_exist(self):
        source = ROUTES_PATH.read_text(encoding="utf-8")
        module = ast.parse(source)
        discovered_aliases = set()

        for node in module.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name):
                    continue
                if decorator.func.value.id != "legacy_router":
                    continue
                if decorator.func.attr not in {"get", "post", "delete"}:
                    continue
                if not decorator.args:
                    continue
                first_arg = decorator.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    discovered_aliases.add(first_arg.value)

        expected_aliases = [
            '/workspace_access/my-memberships',
            '/household-access/my-memberships',
            '/workspace_access/invites/accept',
            '/household-access/invites/accept',
            '/workspace_access/invites/{invite_id}/revoke',
            '/household-access/invites/{invite_id}/revoke',
            '/workspace_access/invites/{invite_id}/resend',
            '/household-access/invites/{invite_id}/resend',
            '/workspace_access/invites/{invite_id}',
            '/household-access/invites/{invite_id}',
            '/workspace_access/project/{project_id}/members/{membership_id}/role',
            '/household-access/project/{project_id}/members/{membership_id}/role',
            '/workspace_access/project/{project_id}/members/{membership_id}/revoke',
            '/household-access/project/{project_id}/members/{membership_id}/revoke',
        ]
        for alias in expected_aliases:
            self.assertIn(alias, discovered_aliases)


if __name__ == "__main__":
    unittest.main()
