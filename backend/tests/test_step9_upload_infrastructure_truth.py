from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_protected_upload_surfaces_use_hardened_shared_assets():
    for path in (
        "upload-hub.html",
        "portrait-upload.html",
        "verification-upload.html",
        "vault-upload.html",
    ):
        html = _read(path)
        assert "app.js?v=20260907-auth-hardening" in html
        assert "auth.js?v=20260907-auth-hardening" in html

    assert "upload-hub.js?v=20260909-step9" in _read("upload-hub.html")
    assert "portrait-upload.js?v=20260909-step9" in _read("portrait-upload.html")
    assert "verification-upload.js?v=20260909-step9" in _read("verification-upload.html")
    # Vault source was not changed in this slice, so its asset identity remains asset-specific.
    assert "vault-upload.js?v=20260829-phase22" in _read("vault-upload.html")


def _labeler(path: str) -> str:
    source = _read(path)
    start = source.index("function uploadStatusLabel(upload)")
    end = source.index("function uploadResponseState", start)
    return source[start:end]


def test_portrait_inventory_security_state_precedes_review_state():
    labeler = _labeler("portrait-upload.js")
    assert 'const scanStatus = normalizeValue(upload.scan_status)' in labeler
    assert 'scanStatus === "infected"' in labeler
    assert 'scanStatus === "error" || scanStatus === "skipped"' in labeler
    assert 'scanStatus !== "clean"' in labeler
    assert labeler.index('scanStatus === "error"') < labeler.index('const vs = normalizeValue')
    assert labeler.index('scanStatus !== "clean"') < labeler.index('vs === "pending"')
    assert 'blocked — security review required' in labeler
    assert 'security scan in progress' in labeler


def test_verification_inventory_security_state_precedes_review_state():
    labeler = _labeler("verification-upload.js")
    assert 'const scanStatus = normalizeValue(upload.scan_status)' in labeler
    assert 'scanStatus === "infected"' in labeler
    assert 'scanStatus === "error" || scanStatus === "skipped"' in labeler
    assert 'scanStatus !== "clean"' in labeler
    assert labeler.index('scanStatus === "error"') < labeler.index('const vs = normalizeValue')
    assert labeler.index('scanStatus !== "clean"') < labeler.index('vs === "pending"')
    assert 'blocked — security review required' in labeler
    assert 'security scan in progress' in labeler


def test_upload_hub_reads_authorized_inventory_without_mutating_files():
    source = _read("upload-hub.js")

    assert '/users/me/workspace-context' in source
    assert '/uploads/family/' in source
    assert '/uploads/vault/project/' in source
    assert 'category=member_photo' in source
    assert 'category=verification_evidence' in source
    assert 'category=private_media' in source
    assert 'method: "GET"' in source
    assert 'method: "POST"' not in source
    assert 'method: "DELETE"' not in source
    assert 'method: "PATCH"' not in source
    assert 'method: "PUT"' not in source


def test_upload_hub_fails_closed_and_never_converts_unknown_state_to_zero():
    source = _read("upload-hub.js")
    security_start = source.index("function securityState(record)")
    security_end = source.index("function stateLabel", security_start)
    security = source[security_start:security_end]

    assert 'record && record.quarantined' in security
    assert '["infected", "error", "skipped"].includes(scanStatus)' in security
    assert 'scanStatus !== "clean"' in security
    assert security.index('["infected", "error", "skipped"]') < security.index('verification_status')
    assert 'Status unavailable' in source
    assert 'No unavailable lane is reported as empty.' in source
    assert 'Unable to confirm the live upload inventory' in source


def test_step9_browser_contract_covers_real_counts_failures_and_mobile_width():
    source = _read("browser-tests/upload-hub-step9.spec.mjs")

    assert "reports real lane counts and security state before review state" in source
    assert "a failed lane is unavailable and is never converted to a fake zero" in source
    assert "workspace failure fails closed without fabricated file cards" in source
    assert "mobile Upload Hub overview stays within the viewport" in source
    assert "Security blocked" in source
    assert "0 current files" in source
    assert "width: 390" in source
    assert "width: 960" in source


def test_legacy_cache_contracts_recognize_step9_asset_revisions():
    phase9 = _read("backend/tests/contracts/test_continuity_kernel_phase9_control_surface_security.py")
    phase13 = _read("backend/tests/contracts/test_phase13_family_operating_machine.py")
    phase18 = _read("backend/tests/contracts/test_phase18_ceo_fulfillment_review_control.py")
    integrity = _read("backend/tests/test_dashboard_and_client_security_integrity.py")
    recovery = _read("backend/tests/test_phase21_1_mobile_account_recovery.py")

    for page in (
        "upload-hub.html",
        "portrait-upload.html",
        "verification-upload.html",
        "vault-upload.html",
    ):
        assert f'"{page}": "20260907-auth-hardening"' in phase9
        assert f'("{page}", "app.js"): "20260907-auth-hardening"' in recovery
        assert f'("{page}", "auth.js"): "20260907-auth-hardening"' in recovery

    assert '("portrait-upload.html", "portrait-upload.js", "20260909-step9")' in phase13
    assert '"20260909-step9"\n                    if asset == "portrait-upload.js"' in phase18
    assert '"portrait-upload.js": "20260909-step9"' in integrity
    assert '"verification-upload.js": "20260909-step9"' in integrity
    assert '"vault-upload.js": "20260829-phase22"' in integrity
