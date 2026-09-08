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


def test_step81_customer_application_shell_is_layered_and_customer_only():
    source = _read("dashboard-step8.js")
    css = _read("dashboard-step8-1.css")

    assert "tol-layered-app" in source
    assert "tol-app-rail" in source
    assert "tol-home-shell" in source
    assert "My Project" in source
    assert "Deliverables" in source
    assert "isInternalContext" in source
    assert "Upload your production materials" in source
    assert "getIntakeStatus" in source
    assert "resolveProgress" in source
    assert "can_link_households" in source

    assert "grid-template-columns: var(--tol-rail-width) minmax(0, 1fr)" in css
    assert "body.tol-layered-app .page-sections" in css
    assert "display: none !important" in css
    assert "@media (max-width: 1039px)" in css
    assert "@media (max-width: 620px)" in css


def test_dashboard_browser_contract_no_longer_treats_generic_link_keys_as_branch_access():
    source = _read("browser-tests/dashboard-customer-phase20.spec.mjs")

    assert "can_link_households: false" in source
    assert "Link Keys" in source
    assert "toHaveCount(0)" in source
    assert 'acquisitionSource: "paid_order"' in source
    assert "uses the layered customer Home instead of the legacy accordion stack" in source


def test_step81_browser_contract_covers_live_contradictions_and_responsive_shell():
    source = _read("browser-tests/dashboard-step8-truth.spec.mjs")

    assert "Family Estate uses domain navigation instead of exposing raw tool catalog on Home" in source
    assert "CEO-governed grant stays accessible without becoming a paid package" in source
    assert "approved intake moves Home to production materials instead of asking for final submission" in source
    assert "maintenance grace is visible" in source
    assert "read-only maintenance makes Billing the Home next action" in source
    assert "desktop shows persistent application rail and no long dashboard stack" in source
