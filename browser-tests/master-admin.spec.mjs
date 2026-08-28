import { expect, test } from "@playwright/test";

const OFFICER_A = { _id: "officer-a", id: "officer-a", email: "officer.a@tomboflight.test", role: "admin", access_tier: "ceo_master_admin", department_role: "executive_tech_admin", role_codes: ["ceo_master_admin", "executive_tech_admin"] };
const OFFICER_B = { _id: "officer-b", id: "officer-b", email: "officer.b@tomboflight.test", role: "admin", access_tier: "operations_admin", department_role: "operations_admin", role_codes: ["operations_admin"] };
const TABS = ["overview", "package_services", "family_household", "production", "uploads", "vault_metadata", "billing", "maintenance", "certificates", "delivery", "mint", "roles_access", "audit_history"];

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function makeCase(seed) {
  return {
    case_id: seed.case_id,
    project_id: seed.project_id,
    order_id: seed.order_id,
    name: seed.name,
    email: seed.email,
    role: seed.role,
    project: seed.project,
    package: seed.package,
    package_name: seed.package_name,
    package_code: seed.package_code,
    lane: seed.lane,
    status: seed.status,
    alerts: seed.alerts || [],
    operator_guidance: seed.operator_guidance || [],
    tags: seed.tags || [],
    quick_actions: ["sync_package", "repair_record", "run_readiness_check"],
    search_index: seed.search_index || [],
  };
}

function workspacePayload(seed) {
  const now = new Date().toISOString();
  const isNonPaymentGrant = seed.case_id === "case-internal-validation";
  return {
    case_id: seed.case_id,
    project: { id: seed.project_id, project_id: seed.project_id, name: seed.project, status: seed.status, payment_required: !isNonPaymentGrant, package_assignment_source: isNonPaymentGrant ? "internal_validation_account" : null },
    package: { package_code: seed.package_code, package_name: seed.package_name, package_lane: seed.lane, payment_required: !isNonPaymentGrant, acquisition_source: isNonPaymentGrant ? "internal_validation_account" : "paid_order" },
    readiness: { mint_review_ready: false, mint_eligible: false, payment_required: !isNonPaymentGrant, acquisition_source: isNonPaymentGrant ? "internal_validation_account" : "paid_order", acquisition_satisfied: true, order_linked: !isNonPaymentGrant, blocking_reasons: ["upload_review_pending"] },
    alerts: seed.alerts || [],
    tabs: {
      overview: { customer_type: seed.role, workflow_state: seed.status, warnings: [] },
      package_services: { package_name: seed.package_name, package_code: seed.package_code, project_lane: seed.lane, maintenance_state: "active" },
      family_household: { family_id: `fam-${seed.case_id}`, household_id: `house-${seed.case_id}` },
      production: { build_status: seed.status, phase: "client_review", delivery_state: "in_progress" },
      uploads: { uploaded_files: 2, review_status: "pending", verification_readiness: "waiting_for_uploads", items: [{ id: "upload-1", filename: "lineage.pdf", category: "verification", status: "pending", created_at: now }] },
      vault_metadata: { collection_count: 2, release_rule_count: 1, warnings: ["private vault contents hidden by default"] },
      billing: { order_status: "paid", stripe_session_id: "cs_test_fixture_only", payment_link_id: "plink_fixture", billing_history_impact: "no historical mutation" },
      mint: { eligibility: "blocked", approvals: { mint_review_ready: false }, blocking_reasons: ["upload_review_pending"] },
      audit_history: [{ action: "workspace_opened", target_type: "project", target_id: seed.project_id, actor_email: OFFICER_A.email, result: "success", timestamp: now }],
      identity: {
        user_id: seed.case_id.replace("case-", "user-"),
        full_name: seed.name,
        email: seed.email,
        role: seed.role,
        status: seed.status,
        admin_user_relationship: seed.role,
      },
      package_lane: { package_name: seed.package_name, package_code: seed.package_code, project_lane: seed.lane, package_normalization_status: "normalized", payment_required: !isNonPaymentGrant, acquisition_source: isNonPaymentGrant ? "internal_validation_account" : "paid_order", source: "fixture", raw_value: seed.package_code },
      project: {
        project_name: seed.project,
        project_id: seed.project_id,
        build_status: seed.status,
        phase: "client_review",
        intake_readiness: "ready",
        linked_family: { family_id: `fam-${seed.case_id}`, family_name: `${seed.name} Family`, household_id: `house-${seed.case_id}`, household_name: `${seed.name} Household` },
      },
      uploads_verification: { uploaded_files: 2, review_status: "pending", verification_readiness: "waiting_for_uploads", file_categories: ["verification"], items: [{ id: "upload-1", filename: "lineage.pdf", category: "verification", status: "pending", created_at: now }] },
      entitlements: { maintenance_status: "active", access_scope: "standard", private_vault_contents: "hidden" },
      orders_billing: isNonPaymentGrant
        ? { order_status: null, package_name: seed.package_name, package_code: seed.package_code, lane: seed.lane, paid: false, payment_required: false, acquisition_source: "internal_validation_account", acquisition_satisfied: true, stripe_session_id: null, payment_link_id: null, project_link_status: "not_required_non_payment_grant", maintenance_state: "not_applicable_to_non_payment_grant", next_charge_date: null, primary_order: null, related_orders: [] }
        : { order_status: "paid", package_name: seed.package_name, package_code: seed.package_code, lane: seed.lane, paid: true, payment_required: true, acquisition_source: "paid_order", acquisition_satisfied: true, stripe_session_id: "cs_test_fixture_only", payment_link_id: "plink_fixture", project_link_status: "linked", maintenance_state: "active", next_charge_date: now, primary_order: { id: seed.order_id, status: "paid", package_name: seed.package_name }, related_orders: [] },
      mint_readiness: { current_state: "blocked", eligibility: "blocked", approvals: { mint_review_ready: false }, queue_status: "pending", blocking_reasons: ["upload_review_pending"], guidance: [{ severity: "warning", title: "Uploads pending", next_action: "Review uploads" }] },
      audit_timeline: [{ action: "workspace_opened", target_type: "project", target_id: seed.project_id, actor_email: OFFICER_A.email, result: "success", timestamp: now }],
    },
  };
}

function createMockEnvironment() {
  const cases = [
    makeCase({
      case_id: "case-customer",
      project_id: "proj-customer",
      order_id: "order-customer",
      name: "Customer Fixture",
      email: "customer.fixture@tomboflight.test",
      role: "customer",
      project: "Customer Legacy Project",
      package: "legacy_plus",
      package_name: "Legacy Plus",
      package_code: "legacy_plus",
      lane: "household",
      status: "client_review",
      tags: ["customer"],
      search_index: ["customer fixture", "customer.fixture@tomboflight.test", "user-customer", "proj-customer", "fam-customer", "house-customer", "order-customer", "cs_fixture_customer", "legacy_plus", "client_review"],
    }),
    makeCase({
      case_id: "case-officer",
      project_id: "proj-officer",
      order_id: "order-officer",
      name: "Officer Fixture",
      email: "officer.fixture@tomboflight.test",
      role: "officer",
      project: "Officer Oversight",
      package: "legacy_snapshot",
      package_name: "Legacy Snapshot",
      package_code: "legacy_snapshot",
      lane: "portrait",
      status: "active",
      tags: ["officer"],
      search_index: ["officer fixture", "officer.fixture@tomboflight.test"],
    }),
    makeCase({
      case_id: "case-internal-validation",
      project_id: "proj-internal-validation",
      order_id: "order-internal-validation",
      name: "Internal Validation Account",
      email: "validation.fixture@tomboflight.test",
      role: "internal_validation_account",
      project: "Validation Sandbox",
      package: "legacy_snapshot",
      package_name: "Legacy Snapshot",
      package_code: "legacy_snapshot",
      lane: "portrait",
      status: "active",
      tags: ["internal validation account"],
      search_index: ["internal validation account"],
    }),
    makeCase({
      case_id: "case-prototype-genesis",
      project_id: "proj-genesis",
      order_id: "order-genesis",
      name: "Genesis Prototype",
      email: "genesis.prototype@tomboflight.test",
      role: "prototype",
      project: "Genesis Prototype",
      package: "heirloom_legacy_tree",
      package_name: "Heirloom Legacy Tree",
      package_code: "heirloom_legacy_tree",
      lane: "household",
      status: "prototype",
      tags: ["prototype"],
      search_index: ["genesis prototype", "prototype"],
    }),
    makeCase({
      case_id: "case-larry-personal",
      project_id: "proj-larry-personal",
      order_id: "order-larry-personal",
      name: "Larry Personal Project",
      email: "larry.personal.fixture@tomboflight.test",
      role: "customer",
      project: "Larry Personal Project",
      package: "legacy_plus",
      package_name: "Legacy Plus",
      package_code: "legacy_plus",
      lane: "household",
      status: "delivered_project",
      tags: ["delivered project"],
      search_index: ["larry personal project", "delivered project"],
    }),
    makeCase({
      case_id: "case-suspended",
      project_id: "proj-suspended",
      order_id: "order-suspended",
      name: "Suspended Fixture",
      email: "suspended.fixture@tomboflight.test",
      role: "customer",
      project: "Suspended Account Project",
      package: "legacy_snapshot",
      package_name: "Legacy Snapshot",
      package_code: "legacy_snapshot",
      lane: "portrait",
      status: "suspended_account",
      tags: ["suspended account"],
      search_index: ["suspended account", "suspended.fixture@tomboflight.test"],
    }),
    makeCase({
      case_id: "case-rakim-no-project",
      project_id: "",
      order_id: "",
      name: "Rakim Robinson",
      email: "rakim.j.robinson@gmail.com",
      role: "customer",
      project: "",
      package: "",
      package_name: "",
      package_code: "",
      lane: "",
      status: "active",
      tags: ["customer", "no project"],
      search_index: ["rakim robinson", "rakim.j.robinson@gmail.com", "user-rakim-no-project"],
    }),
  ];

  const stats = {
    packageApplyWrites: 0,
    serviceApplyWrites: 0,
    officerApplyWrites: 0,
    previewWrites: 0,
    stripeMutations: 0,
    blockchainOps: 0,
    productionWrites: 0,
    impersonationAuditEvents: 0,
    financeExports: [],
    kernelExecutions: [],
  };

  const state = {
    activeImpersonation: null,
    officerPermissions: {
      "jenn.wood@tomboflight.com": { role_assignments: ["finance_admin"], permission_overrides: [] },
      "k.goffigan@tomboflight.com": { role_assignments: ["operations_admin"], permission_overrides: [] },
    },
  };

  return { cases, stats, state };
}

async function installApiRoutes(page, env) {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (!path.startsWith("/auth/") && !path.startsWith("/admin/") && !path.startsWith("/packages/")) {
      return route.continue();
    }

    const json = (payload, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });

    if (method === "GET" && path === "/auth/me") {
      return json(OFFICER_A);
    }
    if (method === "POST" && path === "/auth/logout") {
      return json({ ok: true });
    }
    if (method === "GET" && path === "/packages/catalog") {
      return json({ packages: { legacy_snapshot: { display_name: "Legacy Snapshot" }, legacy_plus: { display_name: "Legacy Plus" }, heirloom_legacy_tree: { display_name: "Heirloom Legacy Tree" } } });
    }
    if (method === "GET" && path === "/admin/control-center/access-profile") {
      return json({
        role_key: "ceo_master_admin",
        is_super_admin: true,
        allowed_queues: ["overview", "manual_fulfillment", "money_now", "subscriptions_maintenance", "package_revenue", "finance_integrity", "payroll", "reports_exports", "customer_cases", "users", "orders", "projects", "entitlements", "mint_queue", "upload_review", "billing_maintenance", "audit", "system_health"],
        allowed_tabs: ["identity", "package_lane", "project", "uploads_verification", "entitlements", "orders_billing", "mint_readiness", "audit_timeline", "overview", "package_services", "family_household", "production", "uploads", "vault_metadata", "billing", "mint", "audit_history"],
        allowed_actions: ["sync_package", "repair_record", "run_readiness_check", "refresh_case_data"],
        allowed_bulk_actions: ["repair-selected-records", "repair-all-safe-records", "repair-missing-entitlements"],
      });
    }
    if (method === "GET" && path === "/admin/control-center/overview") {
      return json({
        summary: { total_users: 6, total_active_projects: 6, paid_orders: 6, missing_entitlements: 0, mint_ready_projects: 0, projects_with_data_mismatch: 0 },
        priority_repairs: { paid_order_without_project_link: [], project_without_entitlement: [], package_without_lane: [], mint_eligible_blocked: [] },
        finance_sections: {
          payroll: {
            write_pipeline_live: true,
            bank_transfer_integration: false,
            recent_runs: [
              { payroll_run_id: "payroll-fixture-review", status: "review", period_start: "2026-08-01", period_end: "2026-08-31", total_amount: 1250, external_reference: null },
              { payroll_run_id: "payroll-fixture-approved", status: "approved", period_start: "2026-07-01", period_end: "2026-07-31", total_amount: 1100, external_reference: null },
            ],
          },
          reports_exports: {
            export_generation_live: true,
            status_note: "Protected JSON exports are generated on demand from current finance records.",
            available_exports: ["monthly_finance_export", "tax_export", "refund_report", "subscription_report", "payroll_report", "package_performance_report"],
          },
        },
      });
    }
    if (method === "GET" && path === "/admin/control-center/kernel/status") {
      return json({
        runtime_version: "13.0.0",
        action_count: 47,
        execution_enabled: true,
        one_step_execution_allowed: true,
      });
    }
    if (method === "GET" && path === "/admin/control-center/kernel/operations") {
      return json({ items: [] });
    }
    if (method === "POST" && path === "/admin/control-center/kernel/execute") {
      const body = JSON.parse(request.postData() || "{}");
      env.stats.kernelExecutions.push(body);
      if (body.action === "service_controls") env.stats.serviceApplyWrites += 1;
      if (body.action === "package_change") env.stats.packageApplyWrites += 1;
      if (body.action === "stripe_operation" || body.action === "billing_adjustment") env.stats.stripeMutations += 1;
      if (body.action === "impersonation_start") {
        env.state.activeImpersonation = {
          active: true,
          session_id: "imp-session-1",
          banner: "Viewing Tomb of Light as Customer",
          case_id: body.target.case_id,
          project_id: "proj-customer",
          editing_enabled: false,
          expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
        };
        env.stats.impersonationAuditEvents += 1;
      }
      if (body.action === "impersonation_stop") {
        env.state.activeImpersonation = null;
        env.stats.impersonationAuditEvents += 1;
      }
      const operation = {
        operation_id: `kernel-operation-${env.stats.kernelExecutions.length}`,
        state: "apply_executed",
        execution_outcome: "success",
        evidence_recording_status: "complete",
        execution_result: body.action === "account_permanent_delete"
          ? {
              applied: true,
              permanent: true,
              deletion_receipt: {
                deletion_id: "acctdel-browser-fixture",
                user_id: body.target.user_id,
                deleted_at: new Date().toISOString(),
                reason_category: body.parameters.reason_category,
                restorable: false,
                records_closed: { projects: 1, project_entitlements: 1, project_members: 1, vault_access_grants_revoked: 1 },
                records_preserved: ["orders", "billing_history", "audit_logs", "continuity_evidence"],
                mongo_evidence: {
                  tombstone_collection: "account_deletion_tombstones",
                  audit_collection: "audit_logs",
                  continuity_operation_collection: "continuity_operations",
                  continuity_event_collection: "continuity_events",
                },
              },
            }
            : body.action === "orphan_identity_reconciliation"
            ? {
                applied: true,
                governed_deletion_observed: false,
                reconciliation_receipt: {
                  reconciliation_id: "orphanrec-browser-fixture",
                  resolved_user_id: body.parameters.known_user_id || "former-user-fixture",
                  records_closed: {
                    role_assignments: 1,
                    permission_overrides: 1,
                    project_memberships: 0,
                  },
                  records_preserved: [
                    "orders",
                    "billing_history",
                    "corporate_ownership_records",
                    "audit_logs",
                    "continuity_evidence",
                  ],
                },
              }
            : body.action === "stripe_operation" && body.parameters.stripe_action === "addon_checkout"
              ? {
                  session_id: "cs_phase19_addon",
                  checkout_url: "https://checkout.stripe.com/c/pay/cs_phase19_addon",
                  project_id: body.parameters.project_id,
                  addon_code: body.parameters.addon_code,
                  payment_activation: "stripe_webhook_then_manual_fulfillment",
                }
              : body.action === "billing_adjustment"
                ? {
                    billing_action: body.parameters.billing_action,
                    order_id: body.target.order_id,
                    finance_event_id: "fin_phase19_fixture",
                    access_result: { revoked: body.parameters.billing_action === "refund" },
                  }
                : body.action === "payroll_control"
                  ? {
                      payroll_action: body.parameters.payroll_action,
                      payroll_run: { payroll_run_id: body.target.payroll_run_id, status: "draft" },
                      bank_transfer_initiated: false,
                    }
            : { applied: true },
      };
      if (body.action === "account_permanent_delete") env.state.lastDeletionOperation = operation;
      return json(operation);
    }
    if (method === "POST" && /\/admin\/control-center\/kernel\/operations\/[^/]+\/close$/.test(path)) {
      if (!env.state.lastDeletionOperation) return json({ detail: "Operation not found." }, 404);
      env.state.lastDeletionOperation = { ...env.state.lastDeletionOperation, state: "audit_closed" };
      return json(env.state.lastDeletionOperation);
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/users/preview") {
      const body = JSON.parse(request.postData() || "{}");
      return json({
        before: { account_exists: false, project_exists: false, entitlement_exists: false },
        proposed_after: {
          email: body.email,
          full_name: body.full_name,
          role: "user",
          status: "pending_activation",
          package_code: body.package_code || null,
          package_name: body.package_code === "legacy_plus" ? "Legacy Plus" : null,
          project_name: body.project_name || null,
          project_lane: body.package_code ? "household" : null,
          package_grant_type: body.package_grant_type || null,
        },
        records_to_write: body.package_code
          ? ["users", "projects", "project_members", "project_entitlements", "audit_logs"]
          : ["users", "audit_logs"],
        warnings: body.package_code ? ["This grant does not create or alter a Stripe transaction."] : [],
      });
    }
    if (
      method === "POST" &&
      /\/admin\/control-center\/super-admin\/users\/[^/]+\/package-provision\/preview$/.test(path)
    ) {
      const body = JSON.parse(request.postData() || "{}");
      return json({
        before: { account_exists: true, active_project_count: 0, entitlement_exists: false },
        proposed_after: {
          customer_name: "Rakim Robinson",
          customer_email: "rakim.j.robinson@gmail.com",
          package_code: body.package_code,
          package_name: body.package_code === "legacy_plus" ? "Legacy Plus" : body.package_code,
          project_name: body.project_name,
          project_lane: body.package_code === "legacy_plus" ? "household" : "portrait",
          package_grant_type: body.package_grant_type,
        },
        blocked: false,
        blocked_reasons: [],
        payment_record_created: false,
        stripe_payment_mutated: false,
      });
    }
    if (method === "POST" && path.includes("/status-action/preview")) {
      const body = JSON.parse(request.postData() || "{}");
      return json({
        action: body.action,
        before: { status: "active", session_token_version: 0 },
        proposed_after: {
          status: body.action === "archive" ? "archived" : body.action,
          login_enabled: !["suspend", "disable", "archive"].includes(body.action),
          archive_owned_records: Boolean(body.archive_owned_records),
        },
        ownership_dependencies: { projects: 1, families: 1, households: 0, entitlements: 1, memberships: 1, invites: 0 },
        records_to_archive: body.archive_owned_records ? { projects: 1, families: 1, entitlements: 1, memberships: 1 } : {},
        records_preserved: ["orders", "billing_history", "uploads", "vault_metadata", "certificates", "delivery_records", "audit_logs"],
        blocked: body.action === "archive" && !body.archive_owned_records,
        warnings: body.action === "archive" && !body.archive_owned_records
          ? ["Use Archive Account & Workspaces because this account owns active records."]
          : [],
      });
    }
    if (method === "POST" && path.includes("/permanent-deletion/preview")) {
      return json({
        action: "account_permanent_delete",
        target_account: {
          user_id: "user-customer",
          email: "customer.fixture@tomboflight.test",
          full_name: "Customer Fixture",
        },
        before: { status: "archived", login_enabled: false, session_token_version: 1 },
        proposed_after: {
          status: "permanently_deleted",
          login_enabled: false,
          restorable: false,
          personal_profile_erased: true,
          owned_workspace_access_permanently_closed: true,
        },
        ownership_dependencies: { projects: 1, families: 1, households: 0 },
        external_service_impact: { stripe_subscriptions_cancelled_immediately: 1 },
        records_erased_or_deidentified: ["authentication_credentials", "mfa_secrets", "personal_profile_fields"],
        records_permanently_closed: ["projects", "entitlements", "memberships", "vault_access"],
        records_preserved: ["orders", "billing_history", "corporate_ownership_records", "audit_logs", "continuity_evidence"],
        blocked: false,
        warnings: ["Permanent deletion cannot be undone or restored."],
        confirmation_phrase: "PERMANENTLY DELETE",
        irreversible: true,
      });
    }
    if (
      method === "POST" &&
      path === "/admin/control-center/super-admin/orphan-identity/reconciliation/preview"
    ) {
      const body = JSON.parse(request.postData() || "{}");
      return json({
        action: "orphan_identity_reconciliation",
        identity_email: body.identity_email,
        identity_document_present: false,
        governed_deletion_observed: false,
        resolved_user_id: body.known_user_id || "former-user-fixture",
        ownership_dependencies: { projects: 0, families: 0, households: 0 },
        direct_access_dependencies: {
          role_assignments: 1,
          permission_overrides: 1,
          project_memberships: 0,
        },
        external_service_impact: {
          stripe_subscriptions_cancelled_immediately: 0,
        },
        records_preserved: [
          "orders",
          "billing_history",
          "corporate_ownership_records",
          "audit_logs",
          "continuity_evidence",
        ],
        warnings: [
          "The original removal was not observed by the governed deletion workflow.",
        ],
        confirmation_phrase: "RECONCILE MANUAL REMOVAL",
        blocked: false,
      });
    }
    if (method === "GET" && path === "/admin/control-center/cases") {
      const search = normalize(url.searchParams.get("search"));
      const queue = normalize(url.searchParams.get("queue") || "overview");
      if (queue === "users" && search === "permission-denied") return json({ detail: "Permission denied." }, 403);
      if (queue === "users" && search === "backend-error") return json({ detail: "Backend error." }, 500);
      const items = env.cases.filter((item) => {
        if (!search) return true;
        return item.search_index.some((entry) => normalize(entry).includes(search));
      });
      return json({ items });
    }
    if (method === "GET" && path === "/admin/control-center/fulfillment/queue") {
      return json({
        items: [{
          order_id: "order-addon-fixture",
          customer_name: "Customer Fixture",
          email: "customer.fixture@tomboflight.test",
          package_name: "Extra Storage",
          package_code: "legacy_plus",
          item_type: "addon",
          addon_code: "extra_storage",
          amount_label: "250.00",
          currency: "usd",
          stripe_session_id: "cs_phase19_addon",
          stripe_payment_intent_id: "pi_phase19_addon",
          payment_status: "paid",
          payment_verified: true,
          fulfillment_status: "pending_manual_fulfillment",
          linked_project_id: "proj-customer",
          entitlement_status: "active",
          next_required_action: "activate_paid_addon",
        }],
      });
    }
    if (method === "GET" && /\/admin\/control-center\/finance\/reports\/[^/]+\/export$/.test(path)) {
      const reportType = decodeURIComponent(path.split("/").at(-2) || "");
      env.stats.financeExports.push(reportType);
      return json({ generated_at: new Date().toISOString(), report_type: reportType, format: "json", summary: { record_count: 1 }, records: [{ fixture: true }], status: "live" });
    }
    if (method === "GET" && path.startsWith("/admin/control-center/cases/")) {
      const caseId = decodeURIComponent(path.split("/").pop() || "");
      if (caseId === "case-permission-denied") return json({ detail: "Permission denied." }, 403);
      if (caseId === "case-backend-error") return json({ detail: "Workspace retrieval failed." }, 500);
      const found = env.cases.find((item) => item.case_id === caseId) || env.cases[0];
      const payload = workspacePayload(found);
      if (caseId === "case-empty") {
        payload.tabs.uploads = { uploaded_files: 0, review_status: "empty", verification_readiness: "no_files", items: [] };
        payload.tabs.audit_history = [];
      }
      return json(payload);
    }
    if (method === "GET" && path === "/admin/control-center/super-admin/impersonation/active") {
      if (!env.state.activeImpersonation) return json({ active: false });
      return json({ ...env.state.activeImpersonation, active: true });
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/impersonation/start") {
      const body = JSON.parse(request.postData() || "{}");
      if (!normalize(body.reason)) return json({ detail: "A reason is required." }, 422);
      if (env.state.activeImpersonation) return json({ detail: "active impersonation session already exists" }, 400);
      env.state.activeImpersonation = {
        session_id: "imp-session-1",
        banner: "Viewing Tomb of Light as Customer",
        project_id: "proj-customer",
        editing_enabled: false,
        expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
      };
      env.stats.impersonationAuditEvents += 1;
      return json({ ...env.state.activeImpersonation, active: true });
    }
    if (method === "POST" && path.endsWith("/enable-editing")) {
      const body = JSON.parse(request.postData() || "{}");
      if (!normalize(body.reason)) return json({ detail: "A reason is required to enable editing." }, 422);
      if (!env.state.activeImpersonation) return json({ detail: "No active session." }, 400);
      env.state.activeImpersonation.editing_enabled = true;
      env.stats.impersonationAuditEvents += 1;
      return json({ ...env.state.activeImpersonation, active: true });
    }
    if (method === "POST" && path.endsWith("/stop")) {
      env.state.activeImpersonation = null;
      env.stats.impersonationAuditEvents += 1;
      return json({ active: false, status: "stopped" });
    }
    if (method === "POST" && path.includes("/package-change/preview")) {
      env.stats.previewWrites += 0;
      return json({
        changes: [{ scope: "project", field: "package_code", before: "legacy_snapshot", after: "legacy_plus" }],
        before: { order: { package_code: "legacy_snapshot", stripe_session_id: "cs_checkout_history" }, project: { package_code: "legacy_snapshot" } },
        proposed_after: { project: { package_code: "legacy_plus" } },
        validation: { stripe_purchase_record_preserved: true },
        summary: {
          original_purchase: "Legacy Snapshot",
          current_package: "Legacy Snapshot",
          proposed_package: "Legacy Plus",
          services_added: ["narration"],
          services_removed: [],
          entitlement_changes: ["viewer_access_enabled: true"],
          access_impact: "Expanded",
          billing_history_impact: "No Stripe mutation",
          reason: "Fixture reason",
          authorization_source: "ceo_master_admin",
          effective_date: new Date().toISOString(),
        },
      });
    }
    if (method === "POST" && path.includes("/package-change/apply")) {
      env.stats.packageApplyWrites += 1;
      return json({ changed: true, stripe_purchase_record_preserved: true, changes: [{ scope: "project", field: "package_code", before: "legacy_snapshot", after: "legacy_plus" }] });
    }
    if (method === "POST" && path.includes("/service-controls/preview")) {
      return json({
        changes: [{ scope: "service_controls", field: "vault_enabled", before: false, after: true }],
        validation: { stripe_purchase_record_preserved: true },
        summary: {
          original_purchase: "Legacy Snapshot",
          current_package: "Legacy Snapshot",
          proposed_package: "Legacy Plus",
          services_added: ["vault", "scheduled_reveal"],
          services_removed: ["none"],
          entitlement_changes: ["max_storage_gb: +10"],
          access_impact: "Expanded",
          billing_history_impact: "No Stripe mutation",
          reason: "Fixture reason",
          authorization_source: "ceo_master_admin",
          effective_date: new Date().toISOString(),
        },
      });
    }
    if (method === "POST" && path.includes("/service-controls/apply")) {
      env.stats.serviceApplyWrites += 1;
      return json({ changed: true, stripe_purchase_record_preserved: true, idempotent: true, changes: [{ scope: "service_controls", field: "vault_enabled", before: false, after: true }] });
    }
    if (method === "GET" && path === "/admin/control-center/super-admin/officers") {
      return json({
        items: [
          { full_name: "Jennifer Wood", business_title: "CFO", officer_email: "jenn.wood@tomboflight.com", current_role: "finance_admin", status: "active", role_assignments: env.state.officerPermissions["jenn.wood@tomboflight.com"].role_assignments, permission_overrides: env.state.officerPermissions["jenn.wood@tomboflight.com"].permission_overrides },
          { full_name: "Keith Goffigan", business_title: "COO", officer_email: "k.goffigan@tomboflight.com", current_role: "operations_admin", status: "active", role_assignments: env.state.officerPermissions["k.goffigan@tomboflight.com"].role_assignments, permission_overrides: env.state.officerPermissions["k.goffigan@tomboflight.com"].permission_overrides },
        ],
        ceo_identity: { email: "l.robinson@tomboflight.com", role_code: "ceo_master_admin", immutable: true },
        role_templates: {
          finance_admin: {
            role_code: "finance_admin",
            name: "Chief Financial Officer",
            description: "Finance dashboards, billing, and reconciliation controls.",
            permissions: ["admin.control.billing", "admin.orders.read"],
            allowed_queues: ["money_now", "finance_integrity"],
            allowed_actions: ["link_order_to_project", "refresh_case_data"],
            allowed_bulk_actions: ["link-unlinked-paid-orders"],
          },
          operations_admin: {
            role_code: "operations_admin",
            name: "Chief Operating Officer",
            description: "Operational intake, fulfillment, and support controls.",
            permissions: ["admin.control.view", "admin.intake.review"],
            allowed_queues: ["intake_onboarding", "build_fulfillment"],
            allowed_actions: ["sync_package", "run_readiness_check"],
            allowed_bulk_actions: ["repair-selected-records"],
          },
        },
      });
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/officers/permissions/preview") {
      const body = JSON.parse(request.postData() || "{}");
      if ((body.role_assignments || []).some((role) => normalize(role) === "ceo_master_admin")) return json({ detail: "ceo_master_admin cannot be assigned through officer management." }, 400);
      return json({
        officer_email: body.officer_email,
        before: env.state.officerPermissions[body.officer_email] || { role_assignments: [], permission_overrides: [] },
        proposed_after: { role_assignments: body.role_assignments || [], permission_overrides: body.grant_permissions || [] },
        changes: [{ scope: "officer", field: "permission_overrides", before: [], after: body.grant_permissions || [] }],
      });
    }
    if (method === "POST" && path === "/admin/control-center/super-admin/officers/permissions/apply") {
      const body = JSON.parse(request.postData() || "{}");
      if (!normalize(body.reason)) return json({ detail: "A reason is required for officer-permissions apply to maintain audit traceability." }, 422);
      if ((body.role_assignments || []).some((role) => normalize(role) === "ceo_master_admin")) return json({ detail: "ceo_master_admin cannot be assigned through officer management." }, 400);
      env.stats.officerApplyWrites += 1;
      env.state.officerPermissions[body.officer_email] = {
        role_assignments: body.role_assignments || [],
        permission_overrides: body.grant_permissions || [],
      };
      return json({ applied: true, after: env.state.officerPermissions[body.officer_email], audit_event_created: true });
    }

    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 404);
  });
}

async function bootstrap(page, user = OFFICER_A) {
  await page.addInitScript(({ userPayload }) => {
    localStorage.setItem("tol_access_token", "fixture-token");
    localStorage.setItem("tol_user", JSON.stringify(userPayload));
    localStorage.setItem("tol_api_base_url", window.location.origin);
  }, { userPayload: user });
}

async function openAppearancePanel(page) {
  await page.getByRole("button", { name: "Appearance" }).click();
  await expect(page.locator("[data-admin-appearance-panel]")).toBeVisible();
}

async function setAppearance(page, { theme, large }) {
  await openAppearancePanel(page);
  if (theme) await page.locator(`[data-admin-appearance-theme-option="${theme}"]`).click();
  await page.locator("[data-admin-appearance-large-text]").setChecked(Boolean(large));
}

test.beforeEach(async ({ page }) => {
  const env = createMockEnvironment();
  test.info().annotations.push({ type: "mock-env", description: JSON.stringify(env.stats) });
  await installApiRoutes(page, env);
  await bootstrap(page);
  await page.goto("/admin-control-center.html");
  await expect(page.locator("[data-admin-control-title]")).toContainText("CEO Master Administrator");
  await expect(page.locator("[data-open-case]").first()).toBeVisible();
  page.__env = env;
});

test("[appearance] is temporarily disabled and forces standard light mode", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Appearance" })).toHaveCount(0);
  await expect(page.locator("[data-admin-appearance-panel]")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("data-admin-theme", "light");
  await expect(page.locator("html")).toHaveAttribute("data-admin-text-scale", "normal");
});

test("[account controls] creates an account with a package and closes owned workspaces through the Kernel", async ({ page }) => {
  const env = page.__env;
  await page.locator("[data-super-admin-create-account]").click();
  await expect(page.locator("[data-admin-create-dialog]")).toBeVisible();
  await page.locator('[data-admin-create-field="full_name"]').fill("New Customer");
  await page.locator('[data-admin-create-field="email"]').fill("new.customer@tomboflight.test");
  await page.locator('[data-admin-create-field="package_code"]').selectOption("legacy_plus");
  await page.locator('[data-admin-create-field="project_name"]').fill("New Customer Legacy Build");
  await page.locator('[data-admin-create-field="reason"]').fill("CEO-approved package grant");
  await page.locator("[data-admin-create-preview-action]").click();
  await expect(page.locator("[data-admin-create-preview]")).toContainText("Ready for confirmation");
  await page.locator("[data-admin-create-confirm]").check();
  await page.locator("[data-admin-create-execute]").click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("customer_account_create");
  expect(env.stats.kernelExecutions[0].parameters.user_payload.package_code).toBe("legacy_plus");
  expect(env.stats.kernelExecutions[0].parameters.user_payload.project_name).toBe("New Customer Legacy Build");

  await page.locator('[data-admin-case-tab="overview"]').click();
  await expect(page.locator('[data-super-admin-archive-owned="true"]')).toBeVisible();
  await page.locator('[data-super-admin-archive-owned="true"]').click();
  await expect(page.locator("[data-admin-lifecycle-dialog]")).toBeVisible();
  await expect(page.locator("[data-admin-lifecycle-preview]")).toContainText("Business and evidence records preserved");
  await page.locator("[data-admin-lifecycle-reason]").fill("Former customer closure");
  await page.locator("[data-admin-lifecycle-typed-confirm]").fill("customer.fixture@tomboflight.test");
  await page.locator("[data-admin-lifecycle-confirm]").check();
  await page.locator("[data-admin-lifecycle-execute]").click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(2);
  expect(env.stats.kernelExecutions[1].action).toBe("account_lifecycle");
  expect(env.stats.kernelExecutions[1].parameters.lifecycle_action).toBe("archive");
  expect(env.stats.kernelExecutions[1].parameters.archive_owned_records).toBe(true);
});

test("[permanent deletion] requires two confirmations and returns MongoDB evidence", async ({ page }) => {
  const env = page.__env;
  await expect(page.locator("[data-super-admin-permanent-delete]")).toBeVisible();
  await page.locator("[data-super-admin-permanent-delete]").click();

  const reviewDialog = page.locator("[data-admin-permanent-delete-dialog]");
  await expect(reviewDialog).toBeVisible();
  await expect(page.locator("[data-admin-permanent-delete-preview]")).toContainText("Permanent deletion cannot be undone");
  await expect(page.locator("[data-admin-permanent-delete-preview]")).toContainText("Stripe subscriptions cancelled immediately: 1");
  await page.locator("[data-admin-permanent-delete-category]").selectOption("customer_request");
  await page.locator("[data-admin-permanent-delete-reason]").fill("Verified written request for permanent account closure");
  await page.locator("[data-admin-permanent-delete-email]").fill("wrong@tomboflight.test");
  await page.locator("[data-admin-permanent-delete-confirm]").check();
  await expect(page.locator("[data-admin-permanent-delete-continue]")).toBeDisabled();
  await expect(page.locator("[data-admin-permanent-delete-email-status]")).toContainText("Email does not match");

  await page.locator("[data-admin-permanent-delete-email]").fill("customer.fixture@tomboflight.test");
  await expect(page.locator("[data-admin-permanent-delete-continue]")).toBeEnabled();
  await page.locator("[data-admin-permanent-delete-continue]").click();

  const finalDialog = page.locator("[data-admin-permanent-delete-final-dialog]");
  await expect(finalDialog).toBeVisible();
  await expect(finalDialog).toContainText("This account will be permanently closed");
  await page.locator("[data-admin-permanent-delete-phrase]").fill("DELETE");
  await page.locator("[data-admin-permanent-delete-final-confirm]").check();
  await expect(page.locator("[data-admin-permanent-delete-execute]")).toBeDisabled();
  await page.locator("[data-admin-permanent-delete-phrase]").fill("PERMANENTLY DELETE");
  await expect(page.locator("[data-admin-permanent-delete-execute]")).toBeEnabled();
  await page.locator("[data-admin-permanent-delete-execute]").click();

  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("account_permanent_delete");
  expect(env.stats.kernelExecutions[0].parameters.reason_category).toBe("customer_request");
  expect(env.stats.kernelExecutions[0].parameters.confirmation_email).toBe("customer.fixture@tomboflight.test");
  expect(env.stats.kernelExecutions[0].parameters.initial_confirmation).toBe(true);
  expect(env.stats.kernelExecutions[0].parameters.final_confirmation).toBe("PERMANENTLY DELETE");
  expect(env.stats.kernelExecutions[0].parameters.final_acknowledgement).toBe(true);

  const receiptDialog = page.locator("[data-admin-deletion-receipt-dialog]");
  await expect(receiptDialog).toBeVisible();
  await expect(page.locator("[data-admin-deletion-receipt]")).toContainText("acctdel-browser-fixture");
  await expect(page.locator("[data-admin-deletion-receipt]")).toContainText("MongoDB records closed");
  await expect(page.locator("[data-admin-deletion-receipt-close-audit]")).toBeVisible();
  await page.locator("[data-admin-deletion-receipt-close-audit]").click();
  await expect(page.locator("[data-admin-deletion-receipt]")).toContainText("Audit Closed");
});

test("[manual removal] previews and records a truthful post-hoc reconciliation through the Kernel", async ({ page }) => {
  const env = page.__env;
  await expect(page.locator("[data-super-admin-reconcile-orphan]")).toBeVisible();
  await page.locator("[data-super-admin-reconcile-orphan]").click();

  const dialog = page.locator("[data-admin-orphan-reconciliation-dialog]");
  await expect(dialog).toBeVisible();
  await page.locator('[data-admin-orphan-field="identity_email"]').fill("former.officer@tomboflight.test");
  await page.locator('[data-admin-orphan-field="known_user_id"]').fill("former-user-fixture");
  await page.locator('[data-admin-orphan-field="reason_category"]').selectOption("manual_database_removal");
  await page.locator("[data-admin-orphan-preview-action]").click();

  await expect(page.locator("[data-admin-orphan-preview]")).toContainText("Governed deletion observed");
  await expect(page.locator("[data-admin-orphan-preview]")).toContainText("No");
  await expect(page.locator("[data-admin-orphan-preview]")).toContainText("Role Assignments: 1");

  await page.locator('[data-admin-orphan-field="reason"]').fill("Reconcile the prior CEO-authorized manual database removal");
  await page.locator('[data-admin-orphan-field="confirmation_phrase"]').fill("RECONCILE MANUAL REMOVAL");
  await page.locator("[data-admin-orphan-confirm]").check();
  await expect(page.locator("[data-admin-orphan-execute]")).toBeEnabled();

  page.once("dialog", (confirmation) => confirmation.accept());
  await page.locator("[data-admin-orphan-execute]").click();

  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("orphan_identity_reconciliation");
  expect(env.stats.kernelExecutions[0].target.identity_email).toBe("former.officer@tomboflight.test");
  expect(env.stats.kernelExecutions[0].parameters.final_confirmation).toBe("RECONCILE MANUAL REMOVAL");
  expect(env.stats.kernelExecutions[0].parameters.final_acknowledgement).toBe(true);
  await expect(page.locator("[data-admin-orphan-preview]")).toContainText("orphanrec-browser-fixture");
  await expect(page.locator("[data-admin-orphan-preview]")).toContainText("does not claim the original deletion was Kernel-governed");
});

test("[theme] ignores stored admin appearance while disabled", async ({ page }) => {
  await page.evaluate(() => {
    localStorage.setItem("tol_admin_appearance_default", JSON.stringify({ theme: "high-contrast", textScale: "large" }));
  });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-admin-theme", "light");
  await expect(page.locator("html")).toHaveAttribute("data-admin-text-scale", "normal");
  await expect(page.locator("[data-admin-appearance-theme-option]")).toHaveCount(0);
});

test("[keyboard] validates keyboard-only navigation reachability and no trap", async ({ page }) => {
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").focus();
  await expect(page.locator(":focus")).toHaveAttribute("data-admin-case-search", "");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.getByRole("tab", { name: "Package & Services" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-workspace]")).toContainText("Package");
  await expect(page.locator("[data-super-admin-package-preview]")).toBeVisible();
  await page.locator("[data-super-admin-package-preview]").focus();
  await page.keyboard.press("Enter");
  await page.locator("[data-super-admin-preview-cancel]").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-control-action-status]")).toContainText(
    /Preview canceled with no write|Package-change preview ready/,
  );
  await page.locator("[data-admin-impersonation-start]").focus();
  await expect(page.locator(":focus")).toHaveAttribute("data-admin-impersonation-start", /case-/);
  const activeElementTag = await page.evaluate(() => document.activeElement?.tagName || "");
  expect(activeElementTag.length).toBeGreaterThan(0);
});

test("[responsive] keeps the CEO command center compact and readable at 960px", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 1000 });
  await expect(page.locator("[data-admin-control-title]")).toContainText("CEO Master Administrator");
  await expect(page.locator("[data-super-admin-create-account]")).toBeVisible();
  await expect(page.locator("[data-super-admin-manage-team-access]")).toBeVisible();
  await expect(page.locator("[data-admin-rail-toggle]")).toBeVisible();
  await expect(page.locator("[data-admin-rail-toggle]")).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#admin-operations-navigation")).not.toBeVisible();
  await expect(page.locator("[data-admin-nav-group]")).toHaveCount(4);
  await expect(page.locator('[data-admin-nav-group="workflow"]')).toHaveAttribute("open", "");
  await expect(page.locator('[data-admin-nav-group="finance"]')).not.toHaveAttribute("open", "");
  const compactLayout = await page.evaluate(() => ({
    railPosition: window.getComputedStyle(document.querySelector(".admin-case-rail")).position,
    caseColumns: window.getComputedStyle(document.querySelector(".admin-case-center")).gridTemplateColumns,
    railBottom: document.querySelector(".admin-case-rail").getBoundingClientRect().bottom,
    caseTop: document.querySelector(".admin-case-center").getBoundingClientRect().top,
  }));
  expect(compactLayout.railPosition).toBe("static");
  expect(compactLayout.caseColumns.trim().split(/\s+/)).toHaveLength(1);
  expect(compactLayout.railBottom).toBeLessThanOrEqual(compactLayout.caseTop + 1);
  const overflow = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(overflow.content).toBeLessThanOrEqual(overflow.viewport + 1);
  await expect(page.locator("[data-open-case]").first()).toBeVisible();
  await expect(page.locator("[data-admin-case-workspace]")).toContainText("Identity");
});

test("[responsive] keeps portrait and landscape admin actions reachable", async ({ page }) => {
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    const railToggle = page.locator("[data-admin-rail-toggle]");
    await expect(railToggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#admin-operations-navigation")).not.toBeVisible();

    await railToggle.click();
    await expect(railToggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator("#admin-operations-navigation")).toBeVisible();
    await page.locator('[data-admin-nav-group="finance"] summary').click();
    await expect(page.locator('[data-admin-nav-group="workflow"]')).not.toHaveAttribute("open", "");
    await expect(page.locator('[data-admin-nav-group="finance"]')).toHaveAttribute("open", "");
    await page.locator('[data-admin-nav-group="workflow"] summary').click();

    await page.locator('[data-case-queue="manual_fulfillment"]').click();
    await expect(railToggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#admin-operations-navigation")).not.toBeVisible();
    await expect(page.locator("[data-admin-active-queue]")).toContainText("Paid");

    const layout = await page.evaluate(() => ({
      viewportWidth: document.documentElement.clientWidth,
      contentWidth: document.documentElement.scrollWidth,
      railPosition: window.getComputedStyle(document.querySelector(".admin-case-rail")).position,
      caseColumns: window.getComputedStyle(document.querySelector(".admin-case-center")).gridTemplateColumns,
      pageScrollHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight,
    }));
    expect(layout.contentWidth).toBeLessThanOrEqual(layout.viewportWidth + 1);
    expect(layout.railPosition).toBe("static");
    expect(layout.caseColumns.trim().split(/\s+/)).toHaveLength(1);
    expect(layout.pageScrollHeight).toBeGreaterThan(layout.viewportHeight);

    await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  }
});

test("[contrast] validates WCAG AA contrast thresholds for key selectors", async ({ page }) => {
  const failures = await page.evaluate(() => {
    function parseRgb(value) {
      const m = String(value || "").match(/rgba?\(([^)]+)\)/i);
      if (!m) return null;
      const parts = m[1].split(",").map((p) => Number.parseFloat(p.trim()));
      if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) return null;
      return { r: parts[0], g: parts[1], b: parts[2], a: Number.isFinite(parts[3]) ? parts[3] : 1 };
    }
    function srgb(v) {
      const n = v / 255;
      return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
    }
    function luminance(rgb) {
      return 0.2126 * srgb(rgb.r) + 0.7152 * srgb(rgb.g) + 0.0722 * srgb(rgb.b);
    }
    function ratio(fg, bg) {
      const l1 = luminance(fg);
      const l2 = luminance(bg);
      const light = Math.max(l1, l2);
      const dark = Math.min(l1, l2);
      return (light + 0.05) / (dark + 0.05);
    }
    function effectiveBg(node) {
      let cur = node;
      while (cur) {
        const color = parseRgb(getComputedStyle(cur).backgroundColor);
        if (color && color.a > 0.95) return color;
        cur = cur.parentElement;
      }
      return { r: 255, g: 255, b: 255, a: 1 };
    }
    const targets = [
      { selector: "body", required: 4.5 },
      { selector: ".card-copy", required: 4.5 },
      { selector: ".site-nav a", required: 4.5 },
      { selector: ".btn", required: 4.5 },
      { selector: ".admin-status-chip", required: 3.0 },
      { selector: "label", required: 4.5 },
      { selector: "input", required: 4.5 },
      { selector: "[data-state='error']", required: 4.5 },
      { selector: "[data-state='warning']", required: 4.5 },
      { selector: "[data-state='success']", required: 4.5 },
      { selector: "[data-admin-impersonation-banner]", required: 4.5 },
      { selector: ".site-nav a[aria-current='page']", required: 4.5 },
      { selector: ":focus-visible", required: 3.0 },
    ];
    const problems = [];
    for (const target of targets) {
      const el = document.querySelector(target.selector);
      if (!el) continue;
      const style = getComputedStyle(el);
      const fg = parseRgb(style.color);
      const bg = effectiveBg(el);
      if (!fg || !bg) continue;
      const value = ratio(fg, bg);
      if (value + 1e-6 < target.required) {
        problems.push({
          selector: target.selector,
          ratio: Number(value.toFixed(2)),
          required: target.required,
          foreground: style.color,
          background: getComputedStyle(el).backgroundColor,
        });
      }
    }
    return problems;
  });
  expect(failures).toEqual([]);
  await page.screenshot({ path: "browser-screenshots/wcag-contrast.png", fullPage: true });
});

test("[account360] validates all tabs + loading/empty/denied/error states and sensitive-data guards", async ({ page }) => {
  for (const tabLabel of ["Overview", "Package & Services", "Family / Household", "Production", "Uploads", "Vault Metadata", "Billing", "Mint", "Audit History"]) {
    await page.getByRole("tab", { name: tabLabel }).click();
  }
  await expect(page.locator("[data-admin-case-workspace]")).toContainText("workspace_opened");

  const deniedStatus = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/cases?queue=users&limit=80&search=permission-denied`);
    return res.status;
  });
  expect(deniedStatus).toBe(403);

  const backendErrorStatus = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/cases?queue=users&limit=80&search=backend-error`);
    return res.status;
  });
  expect(backendErrorStatus).toBe(500);

  await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").fill("case-empty");
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-list]")).toContainText("No case results");

  await expect(page.locator("body")).not.toContainText("sk_live_");
  await expect(page.locator("body")).not.toContainText("private_key");
  await expect(page.locator("body")).not.toContainText("token=");
  await expect(page.locator("body")).not.toContainText("password_hash");
  await expect(page.locator("body")).not.toContainText("password=");
});

test("[phase19.1 acquisition] renders governed grants without unpaid-order or maintenance claims", async ({ page }) => {
  const search = page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate");
  await search.fill("internal validation account");
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-list]")).toContainText("Internal Validation Account");
  await page.locator('[data-open-case="case-internal-validation"]').click();
  await page.getByRole("tab", { name: "Billing" }).click();

  const workspace = page.locator("[data-admin-case-workspace]");
  await expect(workspace).toContainText("Package Acquisition");
  await expect(workspace).toContainText("Internal Validation Account");
  await expect(workspace).toContainText("Not Required Non Payment Grant");
  await expect(workspace).toContainText("Not Applicable To Non Payment Grant");
  await expect(workspace).not.toContainText("Paid order is not linked");
});

test("[errors] backend case-search failures include actionable code + retry guidance", async ({ page }) => {
  await page.locator('[data-admin-nav-group="governance"] summary').click();
  await page.locator('[data-case-queue="users"]').click();
  await page
    .getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate")
    .fill("backend-error");
  await page.keyboard.press("Enter");
  await expect
    .poll(async () => {
      return page.evaluate(() => document.documentElement.dataset.adminLastStatus || "");
    })
    .toContain("ACC-SEARCH-FAILED");
  await expect(page.locator("[data-admin-refresh-cases]")).toBeVisible();
  await expect(page.locator("[data-admin-control-status]")).toContainText("All permitted operational queues");
});

test("[search] validates multi-identifier search and badge distinctions", async ({ page }) => {
  const terms = [
    "customer fixture",
    "customer.fixture@tomboflight.test",
    "proj-customer",
    "order-customer",
    "fam-customer",
    "house-customer",
    "cs_fixture_customer",
    "legacy_plus",
    "client_review",
  ];
  for (const term of terms) {
    await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").fill(term);
    await page.keyboard.press("Enter");
    await expect(page.locator("[data-admin-case-list]")).toContainText("Customer Fixture");
  }
  await page.getByPlaceholder("Name, email, birthday, package, project, family, last4, order, session, wallet, token, certificate").fill("genesis prototype");
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-admin-case-list]")).toContainText("Genesis Prototype");
  await expect(page.locator("[data-admin-case-list]")).not.toContainText("Larry Personal Project");
});

test("[package-service] validates preview/cancel/apply/idempotent and no Stripe or blockchain mutation", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => dialog.accept());
  await page.getByRole("tab", { name: "Package & Services" }).click();
  await expect(page.locator("[data-super-admin-package-field='reason']")).toBeVisible();
  await page.locator("[data-super-admin-package-field='reason']").fill("Fixture package update");
  await page.locator("[data-super-admin-service-field='operation']").selectOption("upgrade");
  await expect(page.locator("[data-super-admin-service-field='add_addons']")).toHaveCount(0);
  await page.locator("[data-super-admin-package-preview]").click();
  await expect(page.locator("[data-super-admin-package-preview-output]")).toContainText("Project");
  const beforeCancelWrites = env.stats.packageApplyWrites + env.stats.serviceApplyWrites;
  await page.locator("[data-super-admin-preview-cancel]").click();
  expect(env.stats.packageApplyWrites + env.stats.serviceApplyWrites).toBe(beforeCancelWrites);
  await page.locator("[data-super-admin-service-preview]").click();
  await page.locator("[data-super-admin-service-apply]").click();
  await expect.poll(() => env.stats.serviceApplyWrites).toBe(1);
  await expect(page.locator("[data-admin-control-action-status]")).toContainText("Service controls applied");
  await page.locator("[data-super-admin-package-field='reason']").fill("Fixture package update after service refresh");
  await page.locator("[data-super-admin-package-apply]").click();
  await expect.poll(() => env.stats.packageApplyWrites).toBeGreaterThanOrEqual(1);
  expect(env.stats.kernelExecutions.filter((item) => item.action === "service_controls")).toHaveLength(1);
  expect(env.stats.kernelExecutions.filter((item) => item.action === "package_change").length).toBeGreaterThanOrEqual(1);
  expect(env.stats.stripeMutations).toBe(0);
  expect(env.stats.blockchainOps).toBe(0);
});

test("[phase19 billing] binds add-ons to the selected project and governs refund, credit, and discount actions", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => dialog.accept());
  await page.getByRole("tab", { name: "Billing" }).click();
  await expect(page.locator("[data-stripe-ops-card]")).toBeVisible();
  await expect(page.locator('[data-stripe-ops-field="project_id"]')).toHaveValue("proj-customer");

  await page.locator('[data-stripe-ops-field="reason"]').fill("Customer approved paid storage add-on");
  await page.locator('[data-stripe-ops-field="price_id"]').fill("price_extra_storage_fixture");
  await page.locator('[data-stripe-ops-field="addon_code"]').fill("extra_storage");
  await page.locator('[data-stripe-ops-action="addon_checkout"]').click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("stripe_operation");
  expect(env.stats.kernelExecutions[0].parameters.stripe_action).toBe("addon_checkout");
  expect(env.stats.kernelExecutions[0].parameters.project_id).toBe("proj-customer");
  expect(env.stats.kernelExecutions[0].parameters.addon_code).toBe("extra_storage");

  await page.locator('[data-stripe-ops-field="reason"]').fill("Verified pre-production customer refund");
  await page.locator('[data-billing-adjustment-action="refund"]').click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(2);
  expect(env.stats.kernelExecutions[1].action).toBe("billing_adjustment");
  expect(env.stats.kernelExecutions[1].parameters.billing_action).toBe("refund");
  expect(env.stats.kernelExecutions[1].target.order_id).toBe("order-customer");

  await page.locator('[data-stripe-ops-field="reason"]').fill("Approved customer balance credit");
  await page.locator('[data-stripe-ops-field="adjustment_amount_cents"]').fill("5000");
  await page.locator('[data-billing-adjustment-action="customer_credit"]').click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(3);
  expect(env.stats.kernelExecutions[2].parameters.billing_action).toBe("customer_credit");
  expect(env.stats.kernelExecutions[2].parameters.amount_cents).toBe(5000);

  await page.locator('[data-stripe-ops-field="reason"]').fill("Approved retention discount");
  await page.locator('[data-stripe-ops-field="subscription_id"]').fill("sub_customer_fixture");
  await page.locator('[data-stripe-ops-field="coupon_id"]').fill("coupon_retention_fixture");
  await page.locator('[data-billing-adjustment-action="subscription_discount"]').click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(4);
  expect(env.stats.kernelExecutions[3].parameters.billing_action).toBe("subscription_discount");
  expect(env.stats.kernelExecutions[3].parameters.coupon_id).toBe("coupon_retention_fixture");
  expect(env.stats.stripeMutations).toBe(4);
});

test("[phase19 fulfillment] activates only the verified paid add-on action from the manual queue", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => {
    if (dialog.type() === "prompt") return dialog.accept("Verified paid add-on fulfillment");
    return dialog.accept();
  });
  await page.locator('[data-case-queue="manual_fulfillment"]').click();
  await expect(page.locator("[data-admin-case-list]")).toContainText("extra_storage");
  await expect(page.locator('[data-fulfillment-action="activate_paid_addon"]')).toBeVisible();
  await expect(page.locator('[data-fulfillment-action="assign_package"]')).toHaveCount(0);
  await page.locator('[data-fulfillment-action="activate_paid_addon"]').click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("manual_fulfillment");
  expect(env.stats.kernelExecutions[0].target.order_id).toBe("order-addon-fixture");
  expect(env.stats.kernelExecutions[0].parameters.fulfillment_action).toBe("activate_paid_addon");
});

test("[phase19 finance] runs the governed payroll ledger and protected report exports without initiating transfers", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => {
    if (dialog.type() === "prompt") {
      const answer = dialog.message().includes("bank or payroll-provider")
        ? "provider-batch-fixture-77"
        : "CEO finance fixture approval";
      return dialog.accept(answer);
    }
    return dialog.accept();
  });
  await page.locator('[data-admin-nav-group="finance"] summary').click();
  await page.locator('[data-case-queue="payroll"]').click();
  await expect(page.locator("[data-payroll-create-card]")).toBeVisible();
  await expect(page.locator("[data-payroll-create-card]")).toContainText("never initiates a bank transfer");
  await page.locator('[data-payroll-field="payroll_run_id"]').fill("payroll-phase19-browser");
  await page.locator('[data-payroll-field="period_start"]').fill("2026-08-01");
  await page.locator('[data-payroll-field="period_end"]').fill("2026-08-31");
  await page.locator('[data-payroll-field="total_amount_cents"]').fill("125000");
  await page.locator("[data-payroll-create]").click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("payroll_control");
  expect(env.stats.kernelExecutions[0].parameters.payroll_action).toBe("create_draft");

  await page.locator('[data-payroll-action="mark_processed"][data-payroll-run-id="payroll-fixture-approved"]').click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(2);
  expect(env.stats.kernelExecutions[1].parameters.payroll_action).toBe("mark_processed");
  expect(env.stats.kernelExecutions[1].parameters.external_reference).toBe("provider-batch-fixture-77");

  await page.locator('[data-case-queue="reports_exports"]').click();
  await expect(page.locator("[data-finance-export-card]")).toBeVisible();
  await expect(page.locator("[data-finance-export-type]")).toHaveCount(6);
  await expect(page.locator("[data-finance-export-card]")).toContainText("reviewed by the company tax professional");
  const downloadPromise = page.waitForEvent("download");
  await page.locator('[data-finance-export-type="monthly_finance_export"]').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("tomb-of-light-monthly_finance_export.json");
  await expect.poll(() => env.stats.financeExports).toContain("monthly_finance_export");
});

test("[first package] provisions an existing no-project customer only through the CEO Kernel grant path", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => dialog.accept());
  await page.locator('[data-open-case="case-rakim-no-project"]').click();
  await page.getByRole("tab", { name: "Package & Services" }).click();
  await expect(page.locator("[data-customer-package-provision-card]")).toBeVisible();
  await page.locator('[data-super-admin-provision-field="package_code"]').selectOption("legacy_plus");
  await page.locator('[data-super-admin-provision-field="project_name"]').fill("Rakim Robinson Legacy Project");
  await page.locator('[data-super-admin-provision-field="reason"]').fill("CEO-approved complimentary package grant");
  await page.locator("[data-super-admin-provision-preview]").click();
  await expect(page.locator("[data-super-admin-package-preview-output]")).toContainText("Ready for governed execution");
  await page.locator("[data-super-admin-provision-apply]").click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("customer_package_provision");
  expect(env.stats.kernelExecutions[0].target.user_id).toBe("user-rakim-no-project");
  expect(env.stats.kernelExecutions[0].parameters.package_code).toBe("legacy_plus");
  expect(env.stats.kernelExecutions[0].parameters.package_grant_type).toBe("complimentary_package");
  expect(env.stats.stripeMutations).toBe(0);
});

test("[officer] applies an exact job template through the visible CEO Team Access workflow", async ({ page }) => {
  const env = page.__env;
  await page.locator("[data-super-admin-manage-team-access]").click();
  await expect(page.locator("[data-admin-team-dialog]")).toBeVisible();
  await expect(page.locator("[data-admin-team-ceo-identity]")).toHaveText("l.robinson@tomboflight.com");
  await page.locator('[data-admin-team-field="officer_email"]').selectOption("k.goffigan@tomboflight.com");
  await page.locator('[data-admin-team-field="role_template"]').selectOption("operations_admin");
  await expect(page.locator("[data-admin-team-scope]")).toContainText("Chief Operating Officer");
  await expect(page.locator("[data-admin-team-scope]")).toContainText("Build & Fulfillment");
  await page.locator('[data-admin-team-field="reason"]').fill("COO operations responsibility confirmed");
  await page.locator("[data-admin-team-preview-action]").click();
  await expect(page.locator("[data-admin-team-preview]")).toContainText("exact job scope");
  await page.locator("[data-admin-team-confirm]").check();
  await page.locator("[data-admin-team-execute]").click();
  await expect.poll(() => env.stats.kernelExecutions.length).toBe(1);
  expect(env.stats.kernelExecutions[0].action).toBe("officer_permissions");
  expect(env.stats.kernelExecutions[0].target.officer_email).toBe("k.goffigan@tomboflight.com");
  expect(env.stats.kernelExecutions[0].parameters.role_assignments).toEqual(["operations_admin"]);

  const ceoReject = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/officers/permissions/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        officer_email: "jenn.wood@tomboflight.com",
        role_assignments: ["ceo_master_admin"],
      }),
    });
    return res.status;
  });
  expect(ceoReject).toBe(400);
});

test("[impersonation] validates read-only start, reason requirements, banner, stop, and nested rejection", async ({ page }) => {
  const env = page.__env;
  page.on("dialog", async (dialog) => {
    if (dialog.type() === "prompt") {
      await dialog.accept("Operator exited preview");
      return;
    }
    await dialog.accept();
  });
  await expect(page.locator("[data-admin-impersonation-start]")).toBeVisible();
  await page.locator("[data-admin-impersonation-start]").click();
  await expect(page.locator("[data-admin-control-action-status]")).toContainText("reason is required");
  await page.locator("[data-admin-impersonation-start-reason]").fill("Read-only customer verification");
  await page.locator("[data-admin-impersonation-start]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toContainText("read-only");
  await page.locator('[data-open-case="case-rakim-no-project"]').click();
  await expect(page.locator("[data-admin-case-context]")).toContainText("Different Customer Preview Active");
  await page.locator("[data-admin-open-impersonated-case]").click();
  await expect(page.locator("[data-admin-case-heading]")).toContainText("Customer Fixture");
  await expect(page.locator("[data-admin-control-action-status]")).toContainText("preview remains read-only");
  const nested = await page.evaluate(async () => {
    const res = await fetch(`${window.location.origin}/admin/control-center/super-admin/impersonation/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: "case-customer", reason: "Second start should fail" }),
    });
    return res.status;
  });
  expect(nested).toBe(400);
  await expect(page.locator("[data-admin-impersonation-enable-editing]")).toHaveCount(0);
  await page.locator("[data-admin-impersonation-stop]").click();
  await expect(page.locator("[data-admin-impersonation-banner]")).toBeHidden();
  expect(env.stats.impersonationAuditEvents).toBeGreaterThanOrEqual(2);
});
