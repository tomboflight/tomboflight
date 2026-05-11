"""
Read-only dry-run audit script for Larry Robinson's workspace integrity.

Usage:
    MONGO_URI="mongodb+srv://..." PYTHONPATH=backend python backend/scripts/audit_larry_workspace_integrity.py

Environment variables:
    MONGO_URI        MongoDB connection string (required)
    MONGO_DB_NAME    Database name (default: tomboflight)
    DRY_RUN          Set to "false" to allow future repair extensions (default: true — always read-only here)

This script performs NO writes. It is strictly read-only.
All findings are reported as PASS / FAIL / WARNING with evidence and suggested fixes.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TARGET_EMAIL = "larrycr27@gmail.com"
EXPECTED_PROJECT_ID = "69c0402387082765345cff8c"
EXPECTED_FAMILY_ROOT_ID = "69bf98b54c5cb5a4236446dd"
EXPECTED_HOUSEHOLD_ID = "69c0402387082765345cff8b"
EXPECTED_INTAKE_ID = "69bf55189e86117b345ec516"
EXPECTED_PACKAGE_CODE = "legacy_plus"
EXPECTED_LANE = "household"
EXPECTED_ROLE = "customer"

REQUIRED_ENTITLEMENTS_TRUE = [
    "can_build_household",
    "can_build_family_tree",
    "can_upload_portraits",
    "can_upload_verification_docs",
    "can_use_viewer",
    "can_use_narration",
    "can_use_lineage_certificate",
    "can_open_family_intake",
    "can_use_link_keys",
    "can_manage_link_keys",
]

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

_results: list[dict[str, str]] = []


def _record(
    status: str,
    check: str,
    evidence: str,
    collection: str,
    suggested_fix: str = "",
) -> None:
    _results.append(
        {
            "STATUS": status,
            "CHECK": check,
            "EVIDENCE": evidence,
            "COLLECTION / FILE": collection,
            "SUGGESTED FIX": suggested_fix,
        }
    )
    icon = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️"}.get(status, "ℹ️")
    print(f"  {icon} [{status}] {check}")
    if status != "PASS":
        print(f"       Evidence: {evidence}")
        if suggested_fix:
            print(f"       Suggested fix: {suggested_fix}")


def _pass(check: str, evidence: str, collection: str) -> None:
    _record("PASS", check, evidence, collection)


def _fail(check: str, evidence: str, collection: str, suggested_fix: str = "") -> None:
    _record("FAIL", check, evidence, collection, suggested_fix)


def _warn(check: str, evidence: str, collection: str, suggested_fix: str = "") -> None:
    _record("WARNING", check, evidence, collection, suggested_fix)


# ---------------------------------------------------------------------------
# ObjectId / string helpers
# ---------------------------------------------------------------------------

def _str_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _ids_match(a: Any, b: Any) -> bool:
    return _str_id(a) == _str_id(b) and _str_id(a) != ""


# ---------------------------------------------------------------------------
# MongoDB connection
# ---------------------------------------------------------------------------

def _connect() -> Any:
    try:
        from pymongo import MongoClient  # type: ignore[import-untyped]
    except ImportError:
        print("ERROR: pymongo is not installed. Install with: pip install pymongo")
        sys.exit(1)

    mongo_uri = os.environ.get("MONGO_URI", "")
    if not mongo_uri:
        print("ERROR: MONGO_URI environment variable is not set.")
        print("  Usage: MONGO_URI='mongodb+srv://...' python audit_larry_workspace_integrity.py")
        sys.exit(1)

    db_name = os.environ.get("MONGO_DB_NAME", "tomboflight")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    try:
        client.server_info()
    except Exception as exc:
        print(f"ERROR: Cannot connect to MongoDB: {exc}")
        sys.exit(1)

    return client[db_name]


# ---------------------------------------------------------------------------
# Audit functions
# ---------------------------------------------------------------------------

def audit_user(db: Any) -> dict[str, Any] | None:
    print("\n--- USERS ---")
    users = db["users"]
    user = users.find_one({"email": TARGET_EMAIL})
    if user is None:
        _fail("User document exists", f"No user found with email={TARGET_EMAIL}", "users",
              "Verify email spelling; check if user registered under different address")
        return None

    user_id = _str_id(user.get("_id") or user.get("id"))
    _pass("User document exists", f"_id={user_id}", "users")

    role = user.get("role") or user.get("access_tier") or ""
    if role.lower() in (EXPECTED_ROLE, "user"):
        _pass("User role is customer", f"role={role!r}", "users")
    else:
        _fail("User role is customer", f"role={role!r} — expected 'customer'", "users",
              "Do NOT elevate role. Investigate why role is set incorrectly.")

    for admin_flag in ("is_admin", "is_superadmin", "super_admin", "is_staff"):
        if user.get(admin_flag):
            _fail(f"User does not have admin flag {admin_flag!r}",
                  f"{admin_flag}={user.get(admin_flag)!r}", "users",
                  "Remove admin flag from user document — customer must remain customer-only")

    return user


def audit_orders(db: Any, user: dict[str, Any]) -> dict[str, Any] | None:
    print("\n--- ORDERS ---")
    orders = db["orders"]
    user_id = _str_id(user.get("_id") or user.get("id"))
    email = user.get("email", "")

    paid_orders = list(orders.find(
        {"$or": [{"user_id": user_id}, {"email": email}], "status": "paid"}
    ))

    if not paid_orders:
        _fail("Paid order exists for user", f"No paid orders found for user_id={user_id} / email={email}",
              "orders",
              "If order exists with wrong user_id, link it. If order is pending, confirm payment with Stripe.")
        return None

    if len(paid_orders) > 1:
        legacy_plus_orders = [o for o in paid_orders if (o.get("package_code") or o.get("package_slug") or "").replace("-", "_") == EXPECTED_PACKAGE_CODE]
        if len(legacy_plus_orders) > 1:
            _warn("No duplicate paid orders for same package",
                  f"Found {len(legacy_plus_orders)} paid orders with package_code=legacy_plus",
                  "orders",
                  "Deduplicate orders if multiple exist for same project; keep only canonical order")
        else:
            _pass("No duplicate paid orders for same package",
                  f"Found {len(paid_orders)} total paid orders, 1 legacy_plus order", "orders")

    order = paid_orders[0]
    order_id = _str_id(order.get("_id"))
    package_code = (order.get("package_code") or order.get("package_slug") or "").replace("-", "_")

    if package_code == EXPECTED_PACKAGE_CODE:
        _pass("Order package code is legacy_plus", f"package_code={package_code!r}", "orders")
    else:
        _fail("Order package code is legacy_plus", f"package_code={package_code!r}", "orders",
              f"Update order document: set package_code='legacy_plus' (current: {package_code!r})")

    order_project_id = _str_id(order.get("project_id"))
    if _ids_match(order_project_id, EXPECTED_PROJECT_ID):
        _pass("Order links to correct project_id", f"order.project_id={order_project_id}", "orders")
    elif order_project_id:
        _warn("Order project_id matches expected",
              f"order.project_id={order_project_id!r} ≠ expected={EXPECTED_PROJECT_ID!r}",
              "orders",
              "Verify which project is canonical for Larry; update order.project_id if mismatched")
    else:
        _warn("Order has project_id", "order.project_id is missing", "orders",
              "Set order.project_id to link order to Larry's project")

    return order


def audit_project(db: Any, user: dict[str, Any], order: dict[str, Any] | None) -> dict[str, Any] | None:
    print("\n--- PROJECTS ---")
    projects = db["projects"]
    user_id = _str_id(user.get("_id") or user.get("id"))

    project = projects.find_one({"_id": EXPECTED_PROJECT_ID}) or \
              projects.find_one({"id": EXPECTED_PROJECT_ID}) or \
              projects.find_one({"owner_id": user_id})

    if project is None:
        _fail("Project document exists", f"No project found for project_id={EXPECTED_PROJECT_ID} or owner_id={user_id}",
              "projects",
              "Verify project was created during intake; check if project_id is stored as ObjectId vs string")
        return None

    project_id = _str_id(project.get("_id") or project.get("id"))
    _pass("Project document exists", f"project._id={project_id}", "projects")

    if _ids_match(project_id, EXPECTED_PROJECT_ID):
        _pass("Project ID matches expected", f"project_id={project_id}", "projects")
    else:
        _warn("Project ID matches expected",
              f"Found project_id={project_id!r} — expected {EXPECTED_PROJECT_ID!r}",
              "projects",
              "Verify which project_id is authoritative; update workspace references if needed")

    owner_id = _str_id(project.get("owner_id") or project.get("user_id"))
    if _ids_match(owner_id, user_id):
        _pass("Project owner matches user", f"project.owner_id={owner_id}", "projects")
    else:
        _warn("Project owner matches user",
              f"project.owner_id={owner_id!r} vs user._id={user_id!r}",
              "projects",
              "Verify co-owner/member access; Larry may be a member rather than direct owner")

    household_id = _str_id(project.get("household_id"))
    if _ids_match(household_id, EXPECTED_HOUSEHOLD_ID):
        _pass("Project household_id matches expected", f"household_id={household_id}", "projects")
    elif household_id:
        _warn("Project household_id matches expected",
              f"project.household_id={household_id!r} ≠ expected={EXPECTED_HOUSEHOLD_ID!r}",
              "projects",
              "Verify household was correctly linked during provisioning")
    else:
        _warn("Project has household_id", "project.household_id is missing", "projects",
              "Set project.household_id during workspace provisioning")

    return project


def audit_family(db: Any, project: dict[str, Any] | None) -> dict[str, Any] | None:
    print("\n--- FAMILIES ---")
    families = db["families"]
    if project is None:
        _warn("Family audit skipped", "No project found; skipping family audit", "families")
        return None

    family = families.find_one({"_id": EXPECTED_FAMILY_ROOT_ID}) or \
              families.find_one({"id": EXPECTED_FAMILY_ROOT_ID})

    if family is None:
        project_family_id = _str_id(project.get("family_id"))
        if project_family_id:
            family = families.find_one({"_id": project_family_id}) or \
                     families.find_one({"id": project_family_id})

    if family is None:
        _fail("Family document exists", f"No family found for family_root_id={EXPECTED_FAMILY_ROOT_ID}",
              "families",
              "Verify family was created during intake; check family_id linkage in project document")
        return None

    family_id = _str_id(family.get("_id") or family.get("id"))
    _pass("Family document exists", f"family._id={family_id}", "families")

    project_family_id = _str_id(project.get("family_id"))
    if _ids_match(family_id, project_family_id) or _ids_match(family_id, EXPECTED_FAMILY_ROOT_ID):
        _pass("Family links to project", f"family_id={family_id}", "families")
    else:
        _warn("Family links to project",
              f"family._id={family_id!r} vs project.family_id={project_family_id!r}",
              "families",
              "Update project.family_id or family.project_id to ensure consistent linkage")

    return family


def audit_entitlements(db: Any, project: dict[str, Any] | None) -> None:
    print("\n--- PROJECT_ENTITLEMENTS ---")
    if project is None:
        _warn("Entitlement audit skipped", "No project found; skipping entitlement audit",
              "project_entitlements")
        return

    project_id = _str_id(project.get("_id") or project.get("id"))
    entitlements_coll = db["project_entitlements"]

    ent = entitlements_coll.find_one(
        {"$or": [
            {"project_id": project_id},
            {"project_id": EXPECTED_PROJECT_ID},
        ], "status": "active"}
    )

    if ent is None:
        _fail("Active project_entitlements record exists",
              f"No active entitlement for project_id={project_id}",
              "project_entitlements",
              "Run entitlement provisioning for this project; do NOT use bulk repair — scope to this project only")
        return

    ent_id = _str_id(ent.get("_id"))
    _pass("Active project_entitlements record exists", f"entitlement._id={ent_id}", "project_entitlements")

    package_code = (ent.get("package_code") or ent.get("package_slug") or "").replace("-", "_")
    if package_code == EXPECTED_PACKAGE_CODE:
        _pass("Entitlement package_code is legacy_plus", f"package_code={package_code!r}",
              "project_entitlements")
    else:
        _fail("Entitlement package_code is legacy_plus",
              f"package_code={package_code!r} — expected 'legacy_plus'",
              "project_entitlements",
              "Update entitlement.package_code to 'legacy_plus'; dry-run first")

    for flag in REQUIRED_ENTITLEMENTS_TRUE:
        val = ent.get(flag)
        if val is True:
            _pass(f"Entitlement {flag} is true", f"{flag}=True", "project_entitlements")
        elif val is False:
            _fail(f"Entitlement {flag} is true",
                  f"{flag}=False",
                  "project_entitlements",
                  f"Set {flag}=True in entitlement record for legacy_plus; dry-run first")
        else:
            _warn(f"Entitlement {flag} present",
                  f"{flag} is missing or null: {val!r}",
                  "project_entitlements",
                  f"Set {flag}=True in entitlement record for legacy_plus")

    household_vault = ent.get("can_use_household_vault")
    if household_vault is True:
        _pass("Entitlement can_use_household_vault is true", "can_use_household_vault=True",
              "project_entitlements")
    else:
        _warn("Entitlement can_use_household_vault",
              f"can_use_household_vault={household_vault!r}",
              "project_entitlements",
              "Ensure vault entitlement is provisioned for legacy_plus")


def audit_intake(db: Any, user: dict[str, Any]) -> None:
    print("\n--- INTAKE_SUBMISSIONS ---")
    user_id = _str_id(user.get("_id") or user.get("id"))
    email = user.get("email", "")
    intake_coll = db["intake_submissions"]

    intake = intake_coll.find_one({"_id": EXPECTED_INTAKE_ID}) or \
             intake_coll.find_one({"id": EXPECTED_INTAKE_ID}) or \
             intake_coll.find_one({"$or": [{"user_id": user_id}, {"email": email}]})

    if intake is None:
        _warn("Intake submission exists",
              f"No intake submission found for id={EXPECTED_INTAKE_ID} or user_id={user_id}",
              "intake_submissions",
              "Verify intake was submitted; check if intake_id references are correct")
        return

    intake_id = _str_id(intake.get("_id") or intake.get("id"))
    _pass("Intake submission exists", f"intake._id={intake_id}", "intake_submissions")

    intake_status = intake.get("status") or intake.get("review_status") or ""
    approved_statuses = ("approved", "completed", "delivered", "active", "provisioned")
    if intake_status.lower() in approved_statuses:
        _pass("Intake status is approved/completed", f"status={intake_status!r}", "intake_submissions")
    else:
        _warn("Intake status is approved/completed",
              f"status={intake_status!r}",
              "intake_submissions",
              "Review intake status; must be approved/completed for full workspace access")


def audit_members(db: Any, project: dict[str, Any] | None, user: dict[str, Any]) -> None:
    print("\n--- PROJECT_MEMBERS ---")
    if project is None:
        _warn("Project member audit skipped", "No project", "project_members")
        return

    project_id = _str_id(project.get("_id") or project.get("id"))
    user_id = _str_id(user.get("_id") or user.get("id"))
    email = user.get("email", "")
    members_coll = db["project_members"]

    members = list(members_coll.find(
        {"$or": [{"project_id": project_id}, {"project_id": EXPECTED_PROJECT_ID}]}
    ))
    _pass(f"Project members found ({len(members)} records)",
          f"project_id={project_id}, member count={len(members)}", "project_members")

    larry_member = next(
        (m for m in members if _str_id(m.get("user_id")) == user_id or m.get("email") == email),
        None
    )
    if larry_member:
        role = larry_member.get("role") or larry_member.get("member_role") or "unknown"
        _pass("Larry is a project member", f"member.role={role!r}", "project_members")
    else:
        _warn("Larry is a project member",
              f"Larry not found in project_members for project_id={project_id}",
              "project_members",
              "Add Larry as billing_owner member; verify owner access uses fallback path")

    active_members = [m for m in members if (m.get("status") or "active").lower() in ("active", "co_owner", "member", "billing_owner", "owner")]
    _pass(f"Active member count ({len(active_members)})",
          f"{len(active_members)} active member(s)", "project_members")


def audit_uploads(db: Any, project: dict[str, Any] | None, user: dict[str, Any]) -> None:
    print("\n--- UPLOADS ---")
    if project is None:
        _warn("Upload audit skipped", "No project", "uploads")
        return

    project_id = _str_id(project.get("_id") or project.get("id"))
    user_id = _str_id(user.get("_id") or user.get("id"))
    uploads_coll = db["uploads"]

    all_uploads = list(uploads_coll.find(
        {"$or": [{"project_id": project_id}, {"uploader_id": user_id}]}
    ))
    by_category: dict[str, int] = {}
    for u in all_uploads:
        cat = u.get("upload_type") or u.get("category") or u.get("file_category") or "unknown"
        by_category[cat] = by_category.get(cat, 0) + 1

    _pass(f"Upload count ({len(all_uploads)} total)", str(by_category), "uploads")

    vault_uploads = by_category.get("vault", 0) + by_category.get("private_media", 0) + by_category.get("household_vault", 0)
    _pass(f"Vault upload count ({vault_uploads})", f"vault/private_media uploads: {vault_uploads}", "uploads")


def audit_certificates(db: Any, project: dict[str, Any] | None) -> None:
    print("\n--- ISSUED_CERTIFICATES ---")
    if project is None:
        _warn("Certificate audit skipped", "No project", "issued_certificates")
        return

    project_id = _str_id(project.get("_id") or project.get("id"))
    certs_coll = db["issued_certificates"]
    certs = list(certs_coll.find({"project_id": {"$in": [project_id, EXPECTED_PROJECT_ID]}}))
    _pass(f"Certificate count ({len(certs)})", f"{len(certs)} certificate(s) on file", "issued_certificates")


def audit_billing(db: Any, user: dict[str, Any]) -> None:
    print("\n--- BILLING / STRIPE ---")
    billing_customer_id = user.get("billing_customer_id") or user.get("stripe_customer_id")
    if billing_customer_id:
        _pass("Billing customer_id present on user", f"billing_customer_id={billing_customer_id!r}", "users")
    else:
        _warn("Billing customer_id present on user",
              "billing_customer_id is not set on user document",
              "users",
              "This is not a blocker for portal access. Stripe customer is created on first setup-intent call. "
              "If billing page shows errors, check that billing_service.py creates customer on setup-intent.")


def audit_objectid_string_risks(db: Any, project: dict[str, Any] | None, order: dict[str, Any] | None) -> None:
    print("\n--- OBJECTID / STRING INTEROPERABILITY ---")
    if project is None:
        _warn("ObjectId audit skipped", "No project document to check", "projects")
        return

    project_id_raw = project.get("_id")
    project_id_str = _str_id(project_id_raw)

    if project is not None and order is not None:
        order_project_id = _str_id(order.get("project_id"))
        if _ids_match(project_id_str, order_project_id):
            _pass("Order project_id matches project._id (ObjectId/string safe)",
                  f"order.project_id={order_project_id!r} matches project._id={project_id_str!r}",
                  "orders → projects")
        else:
            _warn("Order project_id matches project._id",
                  f"order.project_id={order_project_id!r} vs project._id={project_id_str!r}",
                  "orders → projects",
                  "Ensure workspace_access_service._project_id_candidates() handles both ObjectId and string forms")


def audit_viewer_manifest(db: Any, project: dict[str, Any] | None) -> None:
    print("\n--- VIEWER_MANIFESTS ---")
    if project is None:
        _warn("Viewer manifest audit skipped", "No project", "viewer_manifests")
        return

    project_id = _str_id(project.get("_id") or project.get("id"))
    try:
        manifests_coll = db["viewer_manifests"]
        manifests = list(manifests_coll.find({"project_id": {"$in": [project_id, EXPECTED_PROJECT_ID]}}))
        _pass(f"Viewer manifest count ({len(manifests)})",
              f"{len(manifests)} manifest(s) on file", "viewer_manifests")
    except Exception:
        _warn("Viewer manifests collection", "viewer_manifests collection not accessible or missing",
              "viewer_manifests", "Not a blocker; manifests are optional for private viewer")


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report() -> None:
    print("\n")
    print("=" * 120)
    print("LARRY ROBINSON WORKSPACE INTEGRITY AUDIT — DRY-RUN REPORT")
    print(f"Target email: {TARGET_EMAIL}")
    print("=" * 120)
    print(f"{'STATUS':<10} {'CHECK':<65} {'COLLECTION / FILE':<25} {'EVIDENCE'}")
    print("-" * 120)
    for row in _results:
        status = row["STATUS"]
        icon = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️"}.get(status, "ℹ️")
        print(f"{icon} {status:<8} {row['CHECK']:<65} {row['COLLECTION / FILE']:<25} {row['EVIDENCE'][:60]}")

    total = len(_results)
    passes = sum(1 for r in _results if r["STATUS"] == "PASS")
    fails = sum(1 for r in _results if r["STATUS"] == "FAIL")
    warnings = sum(1 for r in _results if r["STATUS"] == "WARNING")

    print("=" * 120)
    print(f"SUMMARY: {total} checks | ✅ {passes} PASS | ❌ {fails} FAIL | ⚠️  {warnings} WARNING")
    print("=" * 120)

    if fails > 0:
        print("\n❌ FAILURES (require action before Larry has full portal access):")
        for row in _results:
            if row["STATUS"] == "FAIL":
                print(f"  • [{row['COLLECTION / FILE']}] {row['CHECK']}")
                print(f"    Evidence: {row['EVIDENCE']}")
                if row["SUGGESTED FIX"]:
                    print(f"    Fix: {row['SUGGESTED FIX']}")

    if warnings > 0:
        print("\n⚠️  WARNINGS (review but may not block access):")
        for row in _results:
            if row["STATUS"] == "WARNING":
                print(f"  • [{row['COLLECTION / FILE']}] {row['CHECK']}")
                if row["SUGGESTED FIX"]:
                    print(f"    Fix: {row['SUGGESTED FIX']}")

    print("\n⚠️  REMINDER: This script is READ-ONLY. No data was modified.")
    print("   To repair data, create a separate dry-run repair script, review it, then apply.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 80)
    print("TOMB OF LIGHT — LARRY ROBINSON WORKSPACE INTEGRITY AUDIT (DRY-RUN)")
    print(f"Target: {TARGET_EMAIL}")
    print("Mode: READ-ONLY — no data will be modified")
    print("=" * 80)

    db = _connect()
    print("✅ Connected to MongoDB")

    user = audit_user(db)
    if user is None:
        _print_report()
        sys.exit(1)

    order = audit_orders(db, user)
    project = audit_project(db, user, order)
    audit_family(db, project)
    audit_entitlements(db, project)
    audit_intake(db, user)
    audit_members(db, project, user)
    audit_uploads(db, project, user)
    audit_certificates(db, project)
    audit_billing(db, user)
    audit_objectid_string_risks(db, project, order)
    audit_viewer_manifest(db, project)

    _print_report()

    fails = sum(1 for r in _results if r["STATUS"] == "FAIL")
    sys.exit(1 if fails > 0 else 0)


if __name__ == "__main__":
    main()
