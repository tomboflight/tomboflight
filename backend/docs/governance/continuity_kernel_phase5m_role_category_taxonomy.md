## Continuity Kernel Phase 5M: Role/Category Taxonomy Hardening

Phase 5M hardens isolated Continuity Kernel role/category classification to explicit taxonomy constants and fail-closed mapping behavior.

### Canonical officer roles

- SUPERADMIN
- EXECUTIVE_TECH_ADMIN
- operations_admin
- finance_admin
- marketing_admin
- CMO

### Canonical repair categories

- missing_entitlement_repair
- package_lane_normalization
- workspace_membership_repair
- upload_readiness_repair
- viewer_readiness_repair
- certificate_issuance_consistency_repair
- mint_readiness_repair
- admin_repair_safety
- billing_order_payment_repair
- audit_record_correction_metadata

### Category groups

- technical_categories:
  - missing_entitlement_repair
  - package_lane_normalization
  - certificate_issuance_consistency_repair
  - mint_readiness_repair
  - audit_record_correction_metadata
- operations_categories:
  - workspace_membership_repair
  - upload_readiness_repair
  - viewer_readiness_repair
- finance_categories:
  - billing_order_payment_repair
- marketing_categories:
  - none (marketing_admin and CMO cannot approve repair execution or view repair execution preview actions)
- superadmin_only_categories:
  - admin_repair_safety
- read_only_preview_categories:
  - missing_entitlement_repair
  - package_lane_normalization
  - workspace_membership_repair
  - upload_readiness_repair
  - viewer_readiness_repair
  - certificate_issuance_consistency_repair
  - mint_readiness_repair
  - admin_repair_safety
  - billing_order_payment_repair
  - audit_record_correction_metadata

### Approval mapping

- SUPERADMIN can approve all categories.
- EXECUTIVE_TECH_ADMIN can approve technical_categories except finance_categories unless structured CEO/SUPERADMIN override exists.
- operations_admin can approve operations_categories only.
- finance_admin can approve finance_categories only.
- marketing_admin and CMO cannot approve repair execution.
- unknown roles fail closed.
- unknown categories fail closed.

### Preview visibility mapping

- SUPERADMIN can view all preview categories.
- EXECUTIVE_TECH_ADMIN can view technical_categories.
- operations_admin can view operations_categories.
- finance_admin can view finance_categories.
- marketing_admin and CMO cannot view repair execution preview actions.
- unknown roles should receive no actions by default.
- unknown categories should receive no actions by default.

### Fail-closed taxonomy rules

- no substring matching for authorization
- no keyword guessing for role/category approval
- no unknown role fallback to permissive actions
- no unknown category fallback to permissive actions
- marketing_admin/CMO always blocked from approval
- prohibited actions remain prohibited regardless of role/category

### Non-operational guardrail

- Phase 5M does not wire any module into runtime routes.
- Phase 5M does not create apply mode.
- Phase 5M does not create repair scripts.
- Phase 5M does not touch live data.
- Phase 5M only hardens isolated taxonomy and tests.
