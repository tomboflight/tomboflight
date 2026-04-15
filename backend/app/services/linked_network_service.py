from __future__ import annotations

from collections import deque
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database
from app.services.entitlement_service import resolve_project_entitlements


MAX_DEPTH = 5


def _col(name: str) -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db[name])


def _str_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return str(value or "").strip()


def _get_project_entitlement(project_id: str) -> dict[str, Any] | None:
    col = _col("project_entitlements")
    candidates: list[Any] = [project_id]
    if ObjectId.is_valid(project_id):
        candidates.append(ObjectId(project_id))
    return col.find_one({"project_id": {"$in": candidates}})


def build_linked_network(
    project_id: str,
    current_user_id: str,
) -> dict[str, Any]:
    entitlement = _get_project_entitlement(project_id)
    if not entitlement:
        raise ValueError("Project entitlement not found.")

    package_code = str(entitlement.get("package_code") or "").strip()
    active_addons = list(entitlement.get("active_addons") or [])

    try:
        resolved = resolve_project_entitlements(package_code, active_addons)
    except Exception as exc:
        raise ValueError(f"Could not resolve entitlements: {exc}") from exc

    if not resolved.get("can_link_households", False):
        raise PermissionError(
            "Your package does not include linked household network access."
        )

    households_col = _col("households")
    links_col = _col("household_links")
    families_col = _col("families")
    members_col = _col("family_members")
    relationships_col = _col("relationships")

    # Find all households for the starting project
    pid_candidates: list[Any] = [project_id]
    if ObjectId.is_valid(project_id):
        pid_candidates.append(ObjectId(project_id))
    seed_households = list(
        households_col.find({"project_id": {"$in": pid_candidates}})
    )

    visited_household_ids: set[str] = set()
    all_households: list[dict[str, Any]] = []

    queue: deque[tuple[str, int]] = deque()
    for hh in seed_households:
        hid = _str_id(hh.get("_id"))
        if hid not in visited_household_ids:
            visited_household_ids.add(hid)
            all_households.append(hh)
            queue.append((hid, 0))

    # BFS traversal via household_links
    while queue:
        current_hid, depth = queue.popleft()
        if depth >= MAX_DEPTH:
            continue

        links = list(
            links_col.find({
                "$or": [
                    {"source_household_id": current_hid, "link_status": "approved"},
                    {"target_household_id": current_hid, "link_status": "approved"},
                ]
            })
        )

        for link in links:
            src = _str_id(link.get("source_household_id"))
            tgt = _str_id(link.get("target_household_id"))
            neighbor_id = tgt if src == current_hid else src

            if neighbor_id and neighbor_id not in visited_household_ids:
                visited_household_ids.add(neighbor_id)
                neighbor_hh = households_col.find_one({"_id": ObjectId(neighbor_id) if ObjectId.is_valid(neighbor_id) else neighbor_id})
                if neighbor_hh:
                    all_households.append(neighbor_hh)
                    queue.append((neighbor_id, depth + 1))

    # Determine the requesting user's household_id (for visibility)
    user_household_ids: set[str] = {_str_id(hh.get("_id")) for hh in seed_households}

    # For each household, collect family + members + relationships
    all_nodes: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    household_summaries: list[dict[str, Any]] = []
    seen_member_ids: set[str] = set()
    seen_relationship_ids: set[str] = set()

    for hh in all_households:
        hh_id = _str_id(hh.get("_id"))
        hh_project_id = _str_id(hh.get("project_id") or "")
        hh_name = str(hh.get("household_name") or hh.get("name") or hh_id)
        is_own_household = hh_id in user_household_ids

        # Find associated family by project_id
        family = None
        if hh_project_id:
            family = families_col.find_one({"project_id": hh_project_id})
        if not family and hh_project_id:
            oid = ObjectId(hh_project_id) if ObjectId.is_valid(hh_project_id) else None
            if oid:
                family = families_col.find_one({"project_id": oid})

        family_id: str | None = None
        if family:
            family_id = _str_id(family.get("_id"))

        # Fetch members
        member_query: dict[str, Any] = {}
        if family_id:
            member_query["family_id"] = family_id
        elif hh_project_id:
            member_query["project_id"] = hh_project_id

        members: list[dict[str, Any]] = []
        if member_query:
            members = list(members_col.find(member_query))

        # Fetch relationships
        rel_query: dict[str, Any] = {}
        if family_id:
            rel_query["family_id"] = family_id
        elif hh_project_id:
            rel_query["project_id"] = hh_project_id

        relationships: list[dict[str, Any]] = []
        if rel_query:
            relationships = list(relationships_col.find(rel_query))

        household_summaries.append({
            "household_id": hh_id,
            "household_name": hh_name,
            "project_id": hh_project_id,
            "family_id": family_id,
            "member_count": len(members),
            "is_own_household": is_own_household,
        })

        # Apply visibility rules and add provenance
        for member in members:
            mid = _str_id(member.get("_id"))
            if mid in seen_member_ids:
                continue

            member_household_id = _str_id(member.get("household_id") or hh_id)
            visibility_scope = str(member.get("visibility_scope") or "").strip().lower()
            is_deceased = bool(member.get("is_deceased", False))
            approved_cross_branch = bool(
                member.get("approved_cross_branch")
                or member.get("share_with_linked_families")
                or visibility_scope in {"linked_family_shared", "branch_shared", "public_memorial", "memorial"}
            )

            # Visibility logic
            if member_household_id not in user_household_ids and not (
                is_deceased
                or approved_cross_branch
            ):
                continue

            if is_deceased or visibility_scope in {"memorial", "public_memorial"}:
                effective_scope = "memorial"
            elif member_household_id in user_household_ids or visibility_scope in {"household", "household_private"}:
                effective_scope = "household"
            else:
                effective_scope = "linked"

            seen_member_ids.add(mid)
            all_nodes.append({
                "id": mid,
                "first_name": member.get("first_name"),
                "last_name": member.get("last_name"),
                "display_name": member.get("display_name"),
                "birth_year": member.get("birth_year"),
                "generation": member.get("generation"),
                "bio": member.get("bio"),
                "is_deceased": is_deceased,
                "source_project_id": hh_project_id,
                "source_household_id": hh_id,
                "source_household_name": hh_name,
                "visibility_scope": effective_scope,
                "is_verified": bool(member.get("is_verified", False)),
            })

        for rel in relationships:
            rid = _str_id(rel.get("_id"))
            if rid in seen_relationship_ids:
                continue
            source_member_id = _str_id(rel.get("source_member_id") or "")
            target_member_id = _str_id(rel.get("target_member_id") or "")
            if source_member_id not in seen_member_ids or target_member_id not in seen_member_ids:
                continue
            seen_relationship_ids.add(rid)
            all_edges.append({
                "id": rid,
                "source_member_id": source_member_id,
                "target_member_id": target_member_id,
                "relationship_type": rel.get("relationship_type"),
                "notes": rel.get("notes"),
                "source_project_id": hh_project_id,
                "source_household_id": hh_id,
            })

    return {
        "network_summary": {
            "total_households": len(all_households),
            "total_members": len(all_nodes),
            "total_relationships": len(all_edges),
            "root_project_id": project_id,
        },
        "households": household_summaries,
        "nodes": all_nodes,
        "edges": all_edges,
        "link_count": len(all_households) - len(seed_households),
    }
