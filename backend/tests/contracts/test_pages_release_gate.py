from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = (
    REPOSITORY_ROOT
    / ".github"
    / "workflows"
    / "continuity-kernel-guardrails.yml"
)
LEGACY_DEPLOY_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "deploy.yml"
PLAYWRIGHT_CONFIG_PATH = REPOSITORY_ROOT / "playwright.config.mjs"


def _job_block(workflow: str, job_id: str) -> str:
    lines = workflow.splitlines()
    header = f"  {job_id}:"
    try:
        start_index = lines.index(header) + 1
    except ValueError as exc:
        raise AssertionError(f"Workflow job is missing: {job_id}") from exc

    end_index = len(lines)
    for index in range(start_index, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end_index = index
            break

    return "\n".join(lines[start_index:end_index])


class PagesReleaseGateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_independent_pages_deployment_workflow_is_removed(self) -> None:
        self.assertFalse(
            LEGACY_DEPLOY_PATH.exists(),
            "Pages must not deploy from a workflow that bypasses validation.",
        )

    def test_pages_artifact_waits_for_every_validation_job(self) -> None:
        build_block = _job_block(self.workflow, "build-pages-artifact")
        required_jobs = (
            "continuity-kernel-guardrails",
            "continuity-kernel-runtime-route-test-env",
            "dependency-security-audit",
            "admin-control-center-browser-execution",
        )

        self.assertIn("needs:", build_block)
        for job_id in required_jobs:
            self.assertIn(job_id, build_block)

        self.assertIn("github.ref == 'refs/heads/main'", build_block)
        self.assertIn("actions/upload-pages-artifact@v5", build_block)

    def test_pages_deployment_consumes_only_the_validated_artifact(self) -> None:
        deploy_block = _job_block(self.workflow, "deploy-pages")

        self.assertIn("needs: build-pages-artifact", deploy_block)
        self.assertIn("github.ref == 'refs/heads/main'", deploy_block)
        self.assertIn("pages: write", deploy_block)
        self.assertIn("id-token: write", deploy_block)
        self.assertIn("actions/deploy-pages@v5", deploy_block)
        self.assertIn("artifact_name: ${{ env.PAGES_ARTIFACT_NAME }}", deploy_block)

    def test_browser_gate_includes_webkit_and_mobile_profiles(self) -> None:
        browser_block = _job_block(
            self.workflow,
            "admin-control-center-browser-execution",
        )
        playwright_config = PLAYWRIGHT_CONFIG_PATH.read_text(encoding="utf-8")

        self.assertIn("chromium webkit", browser_block)
        self.assertIn('name: "chromium-desktop-full"', playwright_config)
        self.assertIn('name: "webkit-desktop-critical"', playwright_config)
        self.assertIn('name: "webkit-mobile-critical"', playwright_config)
        self.assertIn("critical-cross-browser", playwright_config)


if __name__ == "__main__":
    unittest.main()
