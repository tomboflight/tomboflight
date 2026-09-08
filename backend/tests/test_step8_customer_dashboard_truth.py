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
    assert "portal-section.html?section=project" in source
    assert "portal-section.html?section=family" in source
    assert "portal-section.html?section=deliverables" in source
    assert "portal-section.html?section=account" in source
    assert "portal-section.html?section=support" in source
    assert "isInternalContext" in source
    assert "Upload your production materials" in source
    assert "getIntakeStatus" in source
    assert "resolveProgress" in source
    assert "can_link_households" in source

    assert "grid-template-columns: var(--tol-rail-width) minmax(0, 1fr)" in css
    assert "body.tol-layered-app .page-sections" in css
    assert "display: none !important" in css
    assert "@media (min-width: 900px)" in css
    assert "@media (max-width: 899px)" in css
    assert "@media (max-width: 620px)" in css


def test_step81_section_hub_is_hardened_and_keeps_domain_truth_separate():
    html = _read("portal-section.html")
    source = _read("portal-section.js")
    css = _read("portal-section.css")

    assert 'app.js?v=20260907-auth-hardening' in html
    assert 'auth.js?v=20260907-auth-hardening' in html
    assert 'portal-section.js?v=20260907-step8-1' in html
    assert 'portal-section.css?v=20260907-step8-1' in html
    assert "object-src 'none'" in html
    assert "script-src 'self'" in html

    assert "can_link_households" in source
    assert '"Household Link Keys"' in source
    assert '"Pending production"' in source
    assert 'latestMint.mint_status || latestMint.status' in source
    assert '"Status unavailable"' in source
    assert "throw error" in source
    assert "portal-section.html?section=deliverables" in source

    assert "@media (min-width: 900px)" in css
    assert "@media (max-width: 899px)" in css
    assert "grid-template-columns: var(--tol-rail-width) minmax(0, 1fr)" in css


def test_dashboard_browser_contract_no_longer_treats_generic_link_keys_as_branch_access():
    source = _read("browser-tests/dashboard-customer-phase20.spec.mjs")

    assert "can_link_households: false" in source
    assert "Link Keys" in source
    assert "toHaveCount(0)" in source
    assert 'acquisitionSource: "paid_order"' in source
    assert "uses the layered customer Home instead of the legacy accordion stack" in source


def test_step81_browser_contract_covers_live_contradictions_and_responsive_shell():
    dashboard_source = _read("browser-tests/dashboard-step8-truth.spec.mjs")
    hub_source = _read("browser-tests/portal-section-step8-1.spec.mjs")

    assert "Family Estate uses domain navigation instead of exposing raw tool catalog on Home" in dashboard_source
    assert "CEO-governed grant stays accessible without becoming a paid package" in dashboard_source
    assert "approved intake moves Home to production materials instead of asking for final submission" in dashboard_source
    assert "maintenance grace is visible" in dashboard_source
    assert "read-only maintenance makes Billing the Home next action" in dashboard_source
    assert "desktop shows persistent application rail and no long dashboard stack" in dashboard_source

    assert "Legacy Plus Family hub never promotes generic Link Keys as household branch linking" in hub_source
    assert "Deliverables separates package inclusion from readiness while preserving minted Anchor proof" in hub_source
    assert "approved Project hub never asks the customer to finalize or resubmit intake" in hub_source
    assert "mobile section navigation stays domain-based and scroll-safe" in hub_source
    assert "intake API failure is shown as unavailable instead of false Not started state" in hub_source
    assert "width: 960" in hub_source
