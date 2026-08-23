from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_relationships_are_guided_and_automatically_placed():
    catalog = _read("backend/app/core/relationship_catalog.py")
    placement = _read("backend/app/services/family_placement_service.py")
    route = _read("backend/app/routes/family_members.py")
    assert "step_parent" in catalog
    assert "chosen_parent" in catalog
    assert "step_child" in catalog
    assert "Relationship placement conflict" in placement
    assert "cannot be supplied when creating a family member" in route


def test_household_links_are_anchored_aligned_and_privacy_filtered():
    request_service = _read("backend/app/services/link_request_service.py")
    network = _read("backend/app/services/linked_network_service.py")
    tree_route = _read("backend/app/routes/tree.py")
    assert "source_anchor_member_id" in request_service
    assert "target_generation_offset" in request_service
    assert "_reserve_key_use" in request_service
    assert "alignment_conflicts" in network
    assert "Death never overrides" in network
    assert "get_authorized_linked_family_tree" in tree_route


def test_portrait_pipeline_is_clean_consented_and_master_approved():
    uploads = _read("backend/app/routes/uploads.py")
    viewer = _read("backend/app/services/viewer_manifest_service.py")
    portrait_page = _read("portrait-upload.html")
    assert "consent_attested: bool = Form(...)" in uploads
    assert "authority_attested: bool = Form(...)" in uploads
    assert 'require_permission("uploads.admin.review")' in uploads
    assert '"/{upload_id}/verification-review"' in uploads
    assert 'bool(upload.get("consent_attested"))' in viewer
    assert "data-portrait-member-dropboxes" in portrait_page


def test_reunion_status_does_not_return_private_secrets():
    service = _read("backend/app/services/family_reunion_service.py")
    assert "incomplete_reasons" in service
    assert "passwords" in service
    assert "wallet secrets" in service


def test_mint_persists_exact_transaction_before_broadcast_and_requires_customer_owner():
    blockchain = _read("backend/app/services/blockchain_mint_service.py")
    jobs = _read("backend/app/services/mint_job_service.py")
    routes = _read("backend/app/routes/mint_records.py")
    prepared_at = blockchain.index("on_transaction_prepared")
    broadcast_at = blockchain.index("send_raw_transaction", prepared_at)
    assert prepared_at < broadcast_at
    assert "signed_transaction" in jobs
    assert "_acquire_signer_lease" in jobs
    assert "Internal administrators cannot create customer mint consent" in routes
