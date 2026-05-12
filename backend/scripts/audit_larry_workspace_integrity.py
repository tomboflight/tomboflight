#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database

def _object_id_or_none(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    normalized = str(value or "").strip()
    if ObjectId.is_valid(normalized):
        return ObjectId(normalized)
    return None


def _id_candidates(value: Any) -> list[Any]:
    normalized = str(value or "").strip()
    if not normalized:
        return []
    candidates: list[Any] = [normalized]
    oid = _object_id_or_none(normalized)
    if oid is not None and oid != normalized:
        candidates.append(oid)
    return candidates


def _project_query_candidates(project_id: Any, user_id: Any, email: str) -> list[dict[str, Any]]:
    normalized_email = str(email or "").strip().lower()
    project_candidates = _id_candidates(project_id)
    user_candidates = _id_candidates(user_id)

    queries: list[dict[str, Any]] = []
    for candidate in project_candidates:
        queries.extend(
            [
                {"_id": candidate},
                {"id": candidate},
                {"project_id": candidate},
            ]
        )
    for candidate in user_candidates:
        queries.extend(
            [
                {"owner_user_id": candidate},
                {"owner_id": candidate},
                {"user_id": candidate},
            ]
        )
    if normalized_email:
        queries.extend([{"owner_email": normalized_email}, {"email": normalized_email}])
    return _dedupe_queries(queries)


def _dedupe_queries(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in queries:
        marker = repr(query)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(query)
    return deduped


def _first_matching_document(
    db: Database,
    collection_name: str,
    queries: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if collection_name not in set(db.list_collection_names()):
        return None, None
    collection = db[collection_name]
    for query in queries:
        doc = collection.find_one(query, sort=[("updated_at", -1), ("created_at", -1)])
        if doc is not None:
            return doc, query
    return None, None


def _string(value: Any) -> str:
    return str(value or "").strip()


def _email_candidates(*values: Any) -> list[str]:
    seen: set[str] = set()
    emails: list[str] = []
    for value in values:
        email = _string(value).lower()
        if email and email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


def _merge_id_candidates(*values: Any) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for value in values:
        for candidate in _id_candidates(value):
            marker = repr(candidate)
            if marker in seen:
                continue
            seen.add(marker)
            merged.append(candidate)
    return merged


def _context_query_candidates(
    project_ids: list[Any],
    user_ids: list[Any],
    family_ids: list[Any],
    emails: list[str],
    *,
    include_id_fields: bool = False,
) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for candidate in project_ids:
        queries.append({"project_id": candidate})
    for candidate in user_ids:
        queries.extend([{"user_id": candidate}, {"owner_user_id": candidate}, {"owner_id": candidate}])
    for candidate in family_ids:
        queries.extend([{"family_id": candidate}, {"family_root_id": candidate}, {"household_id": candidate}])
        if include_id_fields:
            queries.extend([{"_id": candidate}, {"id": candidate}])
    for email in emails:
        queries.extend([{"email": email}, {"owner_email": email}, {"uploaded_by": email}])
    return _dedupe_queries(queries)


def _print_primary_project_fields(project: dict[str, Any]) -> None:
    print("Project found (primary fields):")
    print(f"  _id: {project.get('_id')}")
    print(f"  owner_id: {project.get('owner_id')}")
    print(f"  owner_user_id: {project.get('owner_user_id')}")
    print(f"  user_id: {project.get('user_id')}")
    print(f"  owner_email: {project.get('owner_email')}")
    print(f"  family_id: {project.get('family_id')}")
    print(f"  family_root_id: {project.get('family_root_id')}")
    print(f"  household_id: {project.get('household_id')}")
    print(f"  package_code: {project.get('package_code')}")
    print(f"  package_slug: {project.get('package_slug')}")
    print(f"  project_lane: {project.get('project_lane')}")
    print(f"  lane: {project.get('lane')}")
    print(f"  status: {project.get('status')}")


def _print_missing_project_dry_run_plan(expected_project_id: str, expected_user_id: str, email: str) -> None:
    print("FAIL: Project document still not found with ObjectId-aware lookup.")
    print("Dry-run repair plan (no writes):")
    print(f"  1) Reconfirm canonical IDs from orders/intake for project_id={expected_project_id}, user_id={expected_user_id}, email={email}.")
    print("  2) Enumerate all project-like records by owner_user_id/owner_id/user_id/email across projects, orders, and intake_submissions.")
    print("  3) If a project exists under an alternate ID type/field, map canonical project_id and dependent references (families, entitlements, members, uploads, certificates, manifests).")
    print("  4) If no project exists, draft a separate explicit repair script in dry-run mode first, then review before any apply step.")
    print("  5) Validate post-repair read-only workspace audit and portal route access checks before any production deploy.")


def _mongo_timeout_ms() -> int:
    raw = os.getenv("MONGO_TIMEOUT_MS", "15000")
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 15000
    return max(1000, parsed)


def run_audit(*, mongo_uri: str, mongo_db_name: str, expected_email: str, expected_user_id: str, expected_project_id: str) -> int:
    timeout_ms = _mongo_timeout_ms()
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=timeout_ms,
        connectTimeoutMS=timeout_ms,
        socketTimeoutMS=timeout_ms,
    )
    db = client[mongo_db_name]

    try:
        print("Running read-only workspace integrity audit (no writes).")
        print(f"Database: {mongo_db_name}")
        print(f"Expected email={expected_email}, user_id={expected_user_id}, project_id={expected_project_id}")

        user_queries = [{"email": expected_email.lower()}]
        user_doc, user_query = _first_matching_document(db, "users", user_queries)
        if user_doc is not None:
            print(f"User exists: _id={user_doc.get('_id')} (query={user_query})")
            print(f"User role/account_type: {user_doc.get('role')}/{user_doc.get('account_type')}")
        else:
            print("FAIL: User not found.")

        order_queries = _dedupe_queries(
            [{"email": expected_email.lower()}]
            + [{"user_id": candidate} for candidate in _id_candidates(expected_user_id)]
            + [{"project_id": candidate} for candidate in _id_candidates(expected_project_id)]
        )
        order_doc, order_query = _first_matching_document(db, "orders", order_queries)
        if order_doc is not None:
            print(f"Paid order found: _id={order_doc.get('_id')} (query={order_query})")
            print(f"Order status/package_code/project_id: {order_doc.get('status')}/{order_doc.get('package_code')}/{order_doc.get('project_id')}")
        else:
            print("FAIL: Paid order not found by email/user/project candidates.")

        intake_queries = _dedupe_queries(
            [{"email": expected_email.lower()}]
            + [{"user_id": candidate} for candidate in _id_candidates(expected_user_id)]
            + [{"project_id": candidate} for candidate in _id_candidates(expected_project_id)]
        )
        intake_doc, intake_query = _first_matching_document(db, "intake_submissions", intake_queries)
        if intake_doc is not None:
            print(f"Intake found: _id={intake_doc.get('_id')} (query={intake_query})")
            print(f"Intake status/approval: {intake_doc.get('status')}/{intake_doc.get('approved')}")
        else:
            print("WARN: Intake submission not found by email/user/project candidates.")

        billing_doc, billing_query = _first_matching_document(
            db,
            "billing_customers",
            _dedupe_queries(
                [{"email": expected_email.lower()}]
                + [{"user_id": candidate} for candidate in _id_candidates(expected_user_id)]
            ),
        )
        if billing_doc is not None:
            print(
                f"Billing customer found: _id={billing_doc.get('_id')} "
                f"stripe_id={billing_doc.get('stripe_customer_id')} (query={billing_query})"
            )
        else:
            print("WARN: Billing customer not found by email/user candidates.")

        project_doc, project_query = _first_matching_document(
            db,
            "projects",
            _project_query_candidates(expected_project_id, expected_user_id, expected_email),
        )

        if project_doc is None:
            _print_missing_project_dry_run_plan(expected_project_id, expected_user_id, expected_email)
            return 1

        print(f"Project found in projects collection (query={project_query}).")
        _print_primary_project_fields(project_doc)

        project_ids = _merge_id_candidates(expected_project_id, project_doc.get("_id"), project_doc.get("id"), project_doc.get("project_id"))
        user_ids = _merge_id_candidates(
            expected_user_id,
            user_doc.get("_id") if user_doc else None,
            project_doc.get("owner_user_id"),
            project_doc.get("owner_id"),
            project_doc.get("user_id"),
        )
        family_ids = _merge_id_candidates(project_doc.get("family_id"), project_doc.get("family_root_id"), project_doc.get("household_id"))
        emails = _email_candidates(expected_email, (user_doc or {}).get("email"), project_doc.get("owner_email"), project_doc.get("email"))

        checks: list[tuple[str, str, list[dict[str, Any]]]] = [
            ("families", "Family linkage", _context_query_candidates(project_ids, user_ids, family_ids, emails, include_id_fields=True)),
            ("project_entitlements", "Entitlement linkage", _context_query_candidates(project_ids, user_ids, family_ids, emails)),
            ("project_members", "Project member linkage", _context_query_candidates(project_ids, user_ids, family_ids, emails)),
            ("uploaded_files", "Upload linkage", _context_query_candidates(project_ids, user_ids, family_ids, emails)),
            ("issued_certificates", "Issued certificate linkage", _context_query_candidates(project_ids, user_ids, family_ids, emails)),
            ("public_metadata_manifests", "Viewer manifest linkage", _context_query_candidates(project_ids, user_ids, family_ids, emails)),
        ]

        for collection_name, label, queries in checks:
            doc, query = _first_matching_document(db, collection_name, queries)
            if doc is None:
                print(f"WARN: {label} not found in {collection_name}.")
            else:
                print(f"OK: {label} found in {collection_name}: _id={doc.get('_id')} via {query}")

        print("Read-only audit complete.")
        return 0
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MongoDB workspace integrity audit that validates user/project and related "
            "collection linkages using string/ObjectId lookup candidates. No writes are performed."
        )
    )
    parser.add_argument("--email", default=os.getenv("AUDIT_EMAIL", ""))
    parser.add_argument("--user-id", default=os.getenv("AUDIT_USER_ID", ""))
    parser.add_argument("--project-id", default=os.getenv("AUDIT_PROJECT_ID", ""))
    args = parser.parse_args()

    mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
    mongo_db_name = os.getenv("MONGO_DB_NAME") or os.getenv("MONGODB_DB_NAME") or ""
    if not mongo_uri:
        print("ERROR: MONGO_URI or MONGODB_URI is required.", file=sys.stderr)
        return 2
    if not _string(mongo_db_name):
        print("ERROR: MONGO_DB_NAME or MONGODB_DB_NAME is required.", file=sys.stderr)
        return 2
    if not _string(args.email) or not _string(args.user_id) or not _string(args.project_id):
        print(
            "ERROR: --email, --user-id, and --project-id are required (or set AUDIT_EMAIL/AUDIT_USER_ID/AUDIT_PROJECT_ID).",
            file=sys.stderr,
        )
        return 2

    return run_audit(
        mongo_uri=mongo_uri,
        mongo_db_name=mongo_db_name,
        expected_email=_string(args.email).lower(),
        expected_user_id=_string(args.user_id),
        expected_project_id=_string(args.project_id),
    )


if __name__ == "__main__":
    raise SystemExit(main())
