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

    assert "portrait-upload.js?v=20260909-step9" in _read("portrait-upload.html")
    assert "verification-upload.js?v=20260909-step9" in _read("verification-upload.html")
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
