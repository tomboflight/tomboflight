from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_dashboard_truth_layer_load_order_and_cache_identity():
    html = _read("dashboard.html")

    auth = 'auth.js?v=20260907-auth-hardening'
    truth = 'dashboard-step8.js?v=20260907-step8'
    intake = 'dashboard-intake.js?v=20260829-vault-ready'

    assert 'app.js?v=20260907-auth-hardening' in html
    assert auth in html
    assert truth in html
    assert intake in html
    assert 'dashboard-admin.js?v=20260713-livefix3' in html

    assert html.index(auth) < html.index(truth) < html.index(intake)


def test_dashboard_truth_layer_enforces_step8_invariants():
    source = _read("dashboard-step8.js")

    assert "can_link_households" in source
    assert 'acquisitionSource === "paid_order"' in source
    assert 'acquisitionSource === "governed_grant"' in source
    assert "context.hasPaidPackage = hasVerifiedPaidPackage" in source
    assert "context.paidOrder = null" in source
    assert "state.read_only === true" in source
    assert "state.in_grace === true" in source
    assert "write_allowed" in source
    assert "Restore Maintenance Billing" in source
    assert "These indicators describe workflow status, not a file inventory" in source


def test_dashboard_browser_contract_no_longer_treats_generic_link_keys_as_branch_access():
    source = _read("browser-tests/dashboard-customer-phase20.spec.mjs")

    assert "can_link_households: false" in source
    assert "toBeHidden()" in source
    assert "acquisitionSource: \"paid_order\"" in source


def test_step8_browser_contract_covers_grants_branch_links_and_maintenance():
    source = _read("browser-tests/dashboard-step8-truth.spec.mjs")

    assert "Family Estate exposes household branch Link Keys" in source
    assert "CEO-governed grant stays accessible without becoming a paid package" in source
    assert "maintenance grace is visible" in source
    assert "read-only maintenance makes billing the next action" in source
    assert "desktop layout stays within the viewport" in source
