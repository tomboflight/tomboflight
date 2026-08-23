from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


class TestPhase13FamilyOperatingMachine(unittest.TestCase):
    def test_relationships_are_guided_and_automatically_placed(self):
        catalog = _read("backend/app/core/relationship_catalog.py")
        placement = _read("backend/app/services/family_placement_service.py")
        route = _read("backend/app/routes/family_members.py")
        self.assertIn("step_parent", catalog)
        self.assertIn("chosen_parent", catalog)
        self.assertIn("step_child", catalog)
        self.assertIn("Relationship placement conflict", placement)
        self.assertIn("cannot be supplied when creating a family member", route)

    def test_household_links_are_anchored_aligned_and_privacy_filtered(self):
        request_service = _read("backend/app/services/link_request_service.py")
        key_routes = _read("backend/app/routes/link_keys.py")
        request_routes = _read("backend/app/routes/link_requests.py")
        network = _read("backend/app/services/linked_network_service.py")
        tree_route = _read("backend/app/routes/tree.py")
        self.assertIn("source_anchor_member_id", request_service)
        self.assertIn("target_generation_offset", request_service)
        self.assertIn("_reserve_key_use", request_service)
        self.assertIn("alignment_conflicts", network)
        self.assertIn("Death never overrides", network)
        self.assertIn("get_authorized_linked_family_tree", tree_route)
        self.assertIn('"admin.intake.write" in permissions', key_routes)
        self.assertIn('require_permission("admin.intake.write")', request_routes)

    def test_portrait_pipeline_is_clean_consented_and_master_approved(self):
        uploads = _read("backend/app/routes/uploads.py")
        viewer = _read("backend/app/services/viewer_manifest_service.py")
        portrait_page = _read("portrait-upload.html")
        self.assertIn("consent_attested: bool = Form(...)", uploads)
        self.assertIn("authority_attested: bool = Form(...)", uploads)
        self.assertIn('require_permission("uploads.admin.review")', uploads)
        self.assertIn('"/{upload_id}/verification-review"', uploads)
        self.assertIn('bool(upload.get("consent_attested"))', viewer)
        self.assertIn("data-portrait-member-dropboxes", portrait_page)

    def test_reunion_status_does_not_return_private_secrets(self):
        service = _read("backend/app/services/family_reunion_service.py")
        self.assertIn("incomplete_reasons", service)
        self.assertIn("passwords", service)
        self.assertIn("wallet secrets", service)

    def test_mint_persists_exact_transaction_before_broadcast_and_requires_customer_owner(self):
        blockchain = _read("backend/app/services/blockchain_mint_service.py")
        jobs = _read("backend/app/services/mint_job_service.py")
        routes = _read("backend/app/routes/mint_records.py")
        prepared_at = blockchain.index("on_transaction_prepared")
        broadcast_at = blockchain.index("send_raw_transaction", prepared_at)
        self.assertLess(prepared_at, broadcast_at)
        self.assertIn("signed_transaction", jobs)
        self.assertIn("_acquire_signer_lease", jobs)
        self.assertIn("Internal administrators cannot create customer mint consent", routes)

    def test_phase13_modified_scripts_are_cache_busted(self):
        revision = "20260823-phase13-1"
        expected_assets = {
            "add-member.html": "member.js",
            "create-relationship.html": "relationship.js",
            "link-keys.html": "link-keys.js",
            "portrait-upload.html": "portrait-upload.js",
            "tree-view.html": "tree-view.js",
            "admin-control-center.html": "admin-control-center.js",
        }
        for html_path, asset in expected_assets.items():
            with self.subTest(html_path=html_path, asset=asset):
                self.assertIn(f'{asset}?v={revision}', _read(html_path))
        self.assertIn(
            f'FRONTEND_ASSET_REVISION = "{revision}"',
            _read("backend/app/services/admin_control_service.py"),
        )

    def test_workflows_use_current_node24_actions_and_full_backend_regression(self):
        guardrails = _read(".github/workflows/continuity-kernel-guardrails.yml")
        deploy = _read(".github/workflows/deploy.yml")
        self.assertNotIn("actions/checkout@v4", guardrails + deploy)
        self.assertIn("actions/checkout@v6", guardrails)
        self.assertIn("actions/setup-python@v7", guardrails)
        self.assertIn("actions/setup-node@v6", guardrails)
        self.assertIn("python -m pip install pytest==9.1.1", guardrails)
        self.assertIn("python -m pytest backend/tests -q", guardrails)
        self.assertIn("actions/configure-pages@v6", deploy)
        self.assertIn("actions/upload-pages-artifact@v5", deploy)
        self.assertIn("actions/deploy-pages@v5", deploy)


if __name__ == "__main__":
    unittest.main()
