# Entitlement Conformance Matrix (Phase 1)

Source of truth implementation: `backend/app/core/entitlement_conformance_matrix.py`.

This matrix defines package conformance for all lanes and packages.

## Global workspace behavior

- Default workspace member roles: `billing_owner`, `co_owner`, `family_manager`, `contributor`, `viewer`, `minor_viewer`, `linked_relative`, `legacy_executor`.
- Visibility/access precedence:
  1. `project_members` membership records
  2. owner fallback (`owner_user_id` / `owner_email`)
  3. internal admin override
  4. family visibility fallback only when owner markers are absent
- Access boundary: project-scoped access only; no cross-project visibility without explicit membership/owner/admin path.

## Global lifecycle behavior

- Upgrades: only package `upgrade_targets` are valid.
- Downgrades: blocked in current purchase flow.
- Maintenance: tracked separately; does not revoke package capability flags.
- Inactive entitlement status: membership/owner checks still govern workspace visibility paths.

## Portrait lane

| Package | Uploads | Storage (GB) | Members | Households | Org Nodes | Zoom Layers | Family Tree | Org Chart | Verification Docs | Family Intake | Org Intake | Certificate | Narration | Link Keys |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| legacy_snapshot | 3 | 0.25 | 1 | 0 | 0 | 0 | No | No | Yes | No | No | No | No | No |
| legacy_portrait_intro | 5 | 0.5 | 1 | 0 | 0 | 0 | No | No | Yes | No | No | No | No | No |
| digital_legacy_portrait | 10 | 1 | 1 | 0 | 0 | 0 | No | No | Yes | No | No | No | No | Yes |

## Household lane

| Package | Uploads | Storage (GB) | Members | Households | Org Nodes | Zoom Layers | Family Tree | Org Chart | Verification Docs | Family Intake | Org Intake | Certificate | Narration | Link Keys |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| household_foundation | 20 | 3 | 6 | 1 | 0 | 2 | Yes | No | Yes | Yes | No | Yes | No | Yes |
| heirloom_legacy_tree | 50 | 10 | 15 | 1 | 0 | 4 | Yes | No | Yes | Yes | No | Yes | Yes | Yes |
| legacy_plus | 100 | 25 | 30 | 1 | 0 | 5 | Yes | No | Yes | Yes | No | Yes | Yes | Yes |

## Network lane

| Package | Uploads | Storage (GB) | Members | Households | Org Nodes | Zoom Layers | Family Tree | Org Chart | Verification Docs | Family Intake | Org Intake | Certificate | Narration | Link Keys |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| family_estate_concierge | 250 | 50 | 999 | 3 | 0 | 999 | Yes | No | Yes | Yes | No | Yes | Yes | Yes |

## Organization lane

| Package | Uploads | Storage (GB) | Members | Households | Org Nodes | Zoom Layers | Family Tree | Org Chart | Verification Docs | Family Intake | Org Intake | Certificate | Narration | Link Keys |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| command_structure_network | 25 | 5 | 0 | 0 | 15 | 2 | No | Yes | Yes | No | Yes | No | No | No |

## Package lifecycle map (upgrade targets)

- `legacy_snapshot` -> `legacy_portrait_intro`, `digital_legacy_portrait`, `household_foundation`, `heirloom_legacy_tree`, `legacy_plus`, `family_estate_concierge`
- `legacy_portrait_intro` -> `digital_legacy_portrait`, `household_foundation`, `heirloom_legacy_tree`, `legacy_plus`, `family_estate_concierge`
- `digital_legacy_portrait` -> `household_foundation`, `heirloom_legacy_tree`, `legacy_plus`, `family_estate_concierge`
- `household_foundation` -> `heirloom_legacy_tree`, `legacy_plus`, `family_estate_concierge`
- `heirloom_legacy_tree` -> `legacy_plus`, `family_estate_concierge`
- `legacy_plus` -> `family_estate_concierge`
- `family_estate_concierge` -> _(none)_
- `command_structure_network` -> `family_estate_concierge`
