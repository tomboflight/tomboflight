from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional, cast

from bson import ObjectId

import app.database as database


class LineageCertificateService:
    """
    Builds an executive lineage certificate payload from existing Tomb of Light records.

    This version is hardened to:
    - resolve family/project records safely
    - normalize Mongo ObjectIds and datetimes
    - read relationship docs using source_member_id / target_member_id
    - compute a fuller key lineage path instead of truncating to 10 names
    - expose the real project_id from the projects collection
    """

    ANCESTRY_RELATIONSHIP_TYPES = {
        "parent_child",
        "adoptive_parent_child",
        "step_parent_child",
    }

    @staticmethod
    def _get_db() -> Any:
        if database.db is None:
            raise RuntimeError("Database connection is not initialized.")
        return database.db

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [LineageCertificateService._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {
                k: LineageCertificateService._serialize_value(v)
                for k, v in value.items()
            }
        return value

    @staticmethod
    def _normalize_document(document: Optional[dict[str, Any]]) -> dict[str, Any]:
        if not document:
            return {}
        return cast(dict[str, Any], LineageCertificateService._serialize_value(document))

    @staticmethod
    def _normalize_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [LineageCertificateService._normalize_document(doc) for doc in documents]

    @staticmethod
    def _safe_object_id(value: str) -> Any:
        try:
            return ObjectId(value)
        except Exception:
            return value

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            if isinstance(value, int):
                return value
            s = str(value).strip()
            if not s:
                return None
            return int(s)
        except Exception:
            return None

    @staticmethod
    def _to_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip()

    def _find_family(self, family_id: str) -> Optional[dict[str, Any]]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        family = db["families"].find_one({"_id": family_lookup})
        if family:
            return cast(dict[str, Any], family)

        family = db["families"].find_one({"family_id": family_id})
        if family:
            return cast(dict[str, Any], family)

        return None

    def _find_project(self, family_id: str) -> Optional[dict[str, Any]]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        project = db["projects"].find_one(
            {"family_id": family_id},
            sort=[("created_at", -1)],
        )
        if project:
            return cast(dict[str, Any], project)

        project = db["projects"].find_one(
            {"family_id": family_lookup},
            sort=[("created_at", -1)],
        )
        if project:
            return cast(dict[str, Any], project)

        return None

    def _find_family_members(self, family_id: str) -> list[dict[str, Any]]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        members = list(db["family_members"].find({"family_id": family_id}))
        if members:
            return cast(list[dict[str, Any]], members)

        members = list(db["family_members"].find({"family_id": family_lookup}))
        if members:
            return cast(list[dict[str, Any]], members)

        return []

    def _find_relationships(self, family_id: str) -> list[dict[str, Any]]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        relationships = list(db["relationships"].find({"family_id": family_id}))
        if relationships:
            return cast(list[dict[str, Any]], relationships)

        relationships = list(db["relationships"].find({"family_id": family_lookup}))
        if relationships:
            return cast(list[dict[str, Any]], relationships)

        return []

    def _find_verification_records(self, family_id: str) -> list[dict[str, Any]]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        records = list(db["verification_records"].find({"family_id": family_id}))
        if records:
            return cast(list[dict[str, Any]], records)

        records = list(db["verification_records"].find({"family_id": family_lookup}))
        if records:
            return cast(list[dict[str, Any]], records)

        return []

    @staticmethod
    def _display_name(member: dict[str, Any]) -> str:
        full_name = member.get("full_name")
        if full_name:
            return str(full_name)

        first_name = str(member.get("first_name", "") or "").strip()
        last_name = str(member.get("last_name", "") or "").strip()
        joined = f"{first_name} {last_name}".strip()

        return joined or "Unknown"

    def _member_summary(self, member: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(member.get("_id", "")),
            "full_name": self._display_name(member),
            "role": member.get("role"),
            "relationship_type": member.get("relationship_type"),
            "generation": self._to_int(member.get("generation")),
            "gender": member.get("gender"),
            "birth_date": self._serialize_value(member.get("birth_date")),
            "birth_year": self._to_int(member.get("birth_year")),
            "is_verified": bool(member.get("is_verified", False)),
            "canonical_person_id": self._serialize_value(member.get("canonical_person_id")),
        }

    @staticmethod
    def _relationship_summary(relationship: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(relationship.get("_id", "")),
            "source_member_id": LineageCertificateService._serialize_value(
                relationship.get("source_member_id") or relationship.get("person_1_id")
            ),
            "target_member_id": LineageCertificateService._serialize_value(
                relationship.get("target_member_id") or relationship.get("person_2_id")
            ),
            "relationship_type": relationship.get("relationship_type"),
            "status": relationship.get("status")
            or relationship.get("relationship_mode")
            or relationship.get("status_marker"),
            "notes": relationship.get("notes"),
        }

    @staticmethod
    def _verification_summary(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(record.get("_id", "")),
            "verification_type": record.get("verification_type"),
            "status": record.get("status"),
            "reviewed_by": record.get("reviewed_by"),
            "created_at": LineageCertificateService._serialize_value(record.get("created_at")),
            "updated_at": LineageCertificateService._serialize_value(record.get("updated_at")),
        }

    @staticmethod
    def _calculate_integrity_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _compute_generation_count(member_summaries: list[dict[str, Any]]) -> int:
        gens: list[int] = [
            int(m["generation"])
            for m in member_summaries
            if isinstance(m.get("generation"), int)
        ]

        if not gens:
            return 0

        return max(gens) - min(gens) + 1

    @staticmethod
    def _sort_member_ids(member_ids: list[str], members_by_id: dict[str, dict[str, Any]]) -> list[str]:
        return sorted(
            member_ids,
            key=lambda mid: (
                members_by_id.get(mid, {}).get("generation")
                if isinstance(members_by_id.get(mid, {}).get("generation"), int)
                else 9999,
                str(members_by_id.get(mid, {}).get("full_name", "")).lower(),
            ),
        )

    def _compute_key_lineage_path(
        self,
        member_summaries: list[dict[str, Any]],
        relationship_summaries: list[dict[str, Any]],
    ) -> list[str]:
        members_by_id = {
            str(m["id"]): m for m in member_summaries if self._to_str(m.get("id"))
        }

        children_by_parent: dict[str, list[str]] = defaultdict(list)
        spouses_by_member: dict[str, list[str]] = defaultdict(list)

        for rel in relationship_summaries:
            source_id = self._to_str(rel.get("source_member_id"))
            target_id = self._to_str(rel.get("target_member_id"))
            rel_type = self._to_str(rel.get("relationship_type")).lower()

            if not source_id or not target_id:
                continue

            if rel_type in self.ANCESTRY_RELATIONSHIP_TYPES:
                children_by_parent[source_id].append(target_id)

            if rel_type == "spouse":
                spouses_by_member[source_id].append(target_id)
                spouses_by_member[target_id].append(source_id)

        generation_values = [
            int(m["generation"])
            for m in member_summaries
            if isinstance(m.get("generation"), int)
        ]
        if not generation_values:
            return []

        min_generation = min(generation_values)

        root_ids = self._sort_member_ids(
            [
                str(m["id"])
                for m in member_summaries
                if m.get("generation") == min_generation and self._to_str(m.get("id"))
            ],
            members_by_id,
        )

        visited: set[str] = set()
        ordered_names: list[str] = []

        def visit_member(member_id: str) -> None:
            if member_id in visited:
                return
            member = members_by_id.get(member_id)
            if not member:
                return

            visited.add(member_id)
            ordered_names.append(str(member.get("full_name", "Unknown")))

            spouse_ids = self._sort_member_ids(
                list({sid for sid in spouses_by_member.get(member_id, []) if sid in members_by_id}),
                members_by_id,
            )
            for spouse_id in spouse_ids:
                spouse = members_by_id.get(spouse_id)
                if (
                    spouse_id not in visited
                    and spouse
                    and spouse.get("generation") == member.get("generation")
                ):
                    visited.add(spouse_id)
                    ordered_names.append(str(spouse.get("full_name", "Unknown")))

            child_ids = self._sort_member_ids(
                list({cid for cid in children_by_parent.get(member_id, []) if cid in members_by_id}),
                members_by_id,
            )
            for child_id in child_ids:
                visit_member(child_id)

        for root_id in root_ids:
            visit_member(root_id)

        remaining_ids = self._sort_member_ids(
            [mid for mid in members_by_id if mid not in visited],
            members_by_id,
        )
        for remaining_id in remaining_ids:
            visit_member(remaining_id)

        return ordered_names

    def _compute_executive_fields(
        self,
        member_summaries: list[dict[str, Any]],
        relationship_summaries: list[dict[str, Any]],
        record_integrity: str,
    ) -> dict[str, Any]:
        gens: list[int] = [
            int(m["generation"])
            for m in member_summaries
            if isinstance(m.get("generation"), int)
        ]

        min_gen: Optional[int] = min(gens) if gens else None
        max_gen: Optional[int] = max(gens) if gens else None

        founders: list[str] = []
        if min_gen is not None:
            founders = [
                str(m["full_name"])
                for m in member_summaries
                if m.get("generation") == min_gen and m.get("full_name")
            ]

        latest: list[str] = []
        if max_gen is not None:
            latest = [
                str(m["full_name"])
                for m in member_summaries
                if m.get("generation") == max_gen and m.get("full_name")
            ]

        verified_count = sum(1 for m in member_summaries if m.get("is_verified"))
        key_path = self._compute_key_lineage_path(
            member_summaries=member_summaries,
            relationship_summaries=relationship_summaries,
        )

        return {
            "record_integrity": record_integrity,
            "founding_line": (
                f"Founding generation: {' + '.join(founders)}"
                if founders
                else "Founding lineage not available."
            ),
            "verified_branches": (
                f"Verified members: {verified_count} / {len(member_summaries)}"
                if member_summaries
                else "No verified branches recorded."
            ),
            "key_lineage_path": key_path,
            "descendant_summary": (
                f"Latest generation recorded: {', '.join(latest)}"
                if latest
                else "No descendant records summarized on this certificate."
            ),
        }

    def build_certificate(self, family_id: str) -> dict[str, Any]:
        family = self._find_family(family_id)
        if not family:
            raise ValueError(f"Family not found for family_id: {family_id}")

        project = self._find_project(family_id)
        members = self._find_family_members(family_id)
        relationships = self._find_relationships(family_id)
        verification_records = self._find_verification_records(family_id)

        normalized_family = self._normalize_document(family)
        normalized_project = self._normalize_document(project)

        member_summaries = [
            self._member_summary(m) for m in self._normalize_documents(members)
        ]
        relationship_summaries = [
            self._relationship_summary(r)
            for r in self._normalize_documents(relationships)
        ]
        verification_summaries = [
            self._verification_summary(v)
            for v in self._normalize_documents(verification_records)
        ]

        verified_member_count = sum(1 for m in member_summaries if m.get("is_verified"))
        verification_pass_count = sum(
            1
            for v in verification_summaries
            if str(v.get("status", "")).lower() in {"verified", "approved", "passed"}
        )

        family_record_id = str(normalized_family.get("_id", family_id))
        family_name = str(
            normalized_family.get("family_name")
            or normalized_family.get("name")
            or "Unnamed Family"
        )
        created_by = str(
            normalized_family.get("created_by")
            or normalized_family.get("owner")
            or normalized_family.get("owner_email")
            or "Unknown"
        )

        project_id = str(normalized_project.get("_id", "")) or normalized_project.get("project_id")
        project_name = normalized_project.get("name")
        project_status = normalized_project.get("status")
        family_status = normalized_family.get("status") or project_status

        generation_count = self._compute_generation_count(member_summaries)

        overall_status = "Verified" if verification_pass_count > 0 else "Recorded"
        executive = self._compute_executive_fields(
            member_summaries=member_summaries,
            relationship_summaries=relationship_summaries,
            record_integrity=overall_status,
        )

        certificate_core: dict[str, Any] = {
            "certificate_type": "lineage_certificate",
            "certificate_version": "1.0.0",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "family": {
                "id": family_record_id,
                "family_name": family_name,
                "project_id": project_id or None,
                "project_name": project_name,
                "project_status": project_status,
                "status": family_status,
                "created_by": created_by,
            },
            "summary": {
                "member_count": len(member_summaries),
                "relationship_count": len(relationship_summaries),
                "verification_record_count": len(verification_summaries),
                "verified_member_count": verified_member_count,
                "verification_pass_count": verification_pass_count,
                "generation_count": generation_count,
            },
            "executive": executive,
            "members": member_summaries,
            "relationships": relationship_summaries,
            "verification_records": verification_summaries,
        }

        integrity_hash = self._calculate_integrity_hash(certificate_core)

        return {
            "success": True,
            "certificate": {
                **certificate_core,
                "certificate_id": f"LC-{family_record_id}",
                "status": overall_status.lower(),
                "integrity_hash": integrity_hash,
            },
        }