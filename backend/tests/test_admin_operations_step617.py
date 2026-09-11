from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_control_center_is_case_first_and_never_auto_opens_first_result():
    html = read("admin-control-center.html")
    js = read("admin-control-center.js")
    guide = read("admin-control-center-guide.js")

    assert 'data-admin-case-search' in html
    assert 'data-admin-clear-case' in html
    assert 'admin-control-center-step617.css?v=20260909-step617' in html
    assert 'admin-control-center-guide.js?v=20260909-step617' in html
    assert 'admin-control-center.js?v=20260909-step617' in html
    assert 'state.cases[0].case_id' not in js
    assert 'searchFirstQueue = ["overview", "customer_cases"].includes(state.queue)' in js
    assert 'getSearchValue().length < 2' in js
    assert 'function clearSelectedCase()' in js
    assert 'state.selectedCaseId = "";' in js
    assert 'No customer record is open.' in guide
    assert 'No default profile' in guide


def test_every_case_and_bulk_command_has_operator_help():
    html = read("admin-control-center.html")
    guide = read("admin-control-center-guide.js")

    case_actions = set(re.findall(r'data-admin-case-action="([^"]+)"', html))
    bulk_actions = set(re.findall(r'data-admin-bulk-action="([^"]+)"', html))

    assert case_actions, "Control Center must expose case-scoped actions."
    assert bulk_actions, "Control Center must expose explicitly separated bulk actions."
    for action in sorted(case_actions):
        assert f'{action}:' in guide, f"Missing plain-language help for case action {action}"
    for action in sorted(bulk_actions):
        assert f'"{action}":' in guide, f"Missing plain-language help for bulk action {action}"

    assert 'Bulk actions affect more than one record' in read("admin-control-center-step617.css")


def test_active_admin_pages_use_hardened_shared_auth_assets():
    pages = (
        "admin-control-center.html",
        "admin-intake-queue.html",
        "admin-intake-review.html",
        "admin-family-manager.html",
        "admin-portrait-review.html",
        "admin-verification-review.html",
        "account-security.html",
    )
    for page in pages:
        source = read(page)
        assert 'app.js?v=20260907-auth-hardening' in source, page
        assert 'auth.js?v=20260907-auth-hardening' in source, page


def test_internal_account_security_does_not_use_customer_profile_endpoints():
    script = read("customer-account-step5.js")
    html = read("account-security.html")

    assert 'me.is_admin === true' in script
    assert 'renderInternalAccountSummary' in script
    assert 'Internal Operations' in script
    assert 'Administrator Workspace' in script
    assert 'Optional · Disabled' in script
    assert 'if (internalAdmin)' in script
    assert 'loadCustomerAccountDetails(me)' in script
    assert 'Account Security' in html


def test_family_manager_requires_explicit_family_context_and_secure_inline_preview():
    html = read("admin-family-manager.html")
    js = read("admin-family-manager.js")

    assert 'No family selected' in html
    assert 'No family record opens automatically' in html
    assert 'admin-specialist-workbench.css?v=20260909-step617' in html
    assert 'admin-family-manager.js?v=20260909-step617' in html
    assert 'function clearFamilyContext(' in js
    assert 'setFamilyScopedControlsEnabled(false)' in js
    assert 'The family selection changed. Choose Load Family' in js
    assert '/admin-preview' in js
    assert 'data-secure-preview-upload-id' in js
    assert 'data-download-upload-id' not in js
    assert '/download' not in re.sub(r'"Delete Upload"', '', js)


def test_review_workbenches_are_inline_and_fail_closed():
    portrait_html = read("admin-portrait-review.html")
    portrait_js = read("admin-portrait-review.js")
    evidence_html = read("admin-verification-review.html")
    evidence_js = read("admin-verification-review.js")

    for html in (portrait_html, evidence_html):
        assert 'admin-specialist-workbench.css?v=20260909-step617' in html
        assert 'app.js?v=20260907-auth-hardening' in html
        assert 'auth.js?v=20260907-auth-hardening' in html
        assert 'Return to Control Center' in html

    assert 'Prepare Secure Preview' in portrait_js
    assert '/admin-preview' in portrait_js
    assert 'object-fit:contain' in portrait_js.replace(' ', '')
    assert 'window.prompt' not in portrait_js
    assert 'item.consent_attested' in portrait_js
    assert 'item.authority_attested' in portrait_js
    assert 'item.durable_private_storage' in portrait_js

    assert 'Prepare Secure Preview' in evidence_js
    assert '/admin-preview' in evidence_js
    assert 'document.createElement("iframe")' in evidence_js
    assert 'document.createElement("img")' in evidence_js
    assert 'window.open(' not in evidence_js
    assert 'window.prompt' not in evidence_js
    assert 'item.durable_private_storage' in evidence_js


def test_operational_health_explains_scanner_storage_and_release_truth():
    html = read("admin-control-center.html")
    script = read("admin-operational-health.js")

    assert 'admin-operational-health.js?v=20260909-operational-health' in html
    assert '"/health/operational"' in script
    for label in (
        "Security Scanner",
        "Private R2",
        "Staging Disk",
        "Legacy Upload Migration",
        "Backend Release",
    ):
        assert label in script


def test_temporary_step617_patch_workflows_are_not_persistent():
    workflows = ROOT / ".github" / "workflows"
    forbidden = (
        "admin-step617-core-patch.yml",
        "admin-step617-family-patch.yml",
        "admin-workbench-asset-alignment.yml",
    )
    for name in forbidden:
        assert not (workflows / name).exists(), f"temporary staging workflow survived: {name}"


def test_case_finder_has_explicit_search_status_and_accessible_open_action():
    html = read("admin-control-center.html")
    js = read("admin-control-center.js")

    assert 'role="search"' in html
    assert "data-admin-run-search" in html
    assert "data-admin-case-search-status" in html
    assert 'aria-describedby="admin-case-search-help admin-case-search-status"' in html
    assert "data-admin-run-search" in js
    assert "Nothing is open until you choose Open case." in js
    assert 'aria-label="Open ${escapeHtml(item.name || "customer")} case"' in js


def test_user_case_summary_uses_open_workspace_relationship_truth_and_flags_unmapped_privileged_roles():
    service = read("backend/app/services/admin_control_service.py")
    ownership = service[service.index("def _user_owns_project"):service.index("def _user_has_pending_verified_purchase")]
    serializer = service[service.index("def _serialize_user_case"):service.index("def _finance_admin_profile")]
    workspace = service[service.index("def _build_user_workspace_payload"):service.index("def list_customer_cases")]

    assert '"owner_user_id"' in ownership
    assert '"owner_email"' in ownership
    assert "related_projects = _related_projects_for_user(user)" in serializer
    assert '"project": (' in serializer
    assert '"package_name": package_name or "No Package Assigned"' in serializer
    assert "privileged_identity_review_required" in serializer
    assert '"account_type": account_type' in workspace
    assert "privileged_identity_review_required" in workspace
    assert '"Account Classification"' in read("admin-control-center.js")