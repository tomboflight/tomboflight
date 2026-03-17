from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

import app.database as database


class LineageCertificateService:
    """
    Builds an executive lineage certificate payload from existing Tomb of Light records.

    - reads family data
    - reads family members
    - reads relationships
    - reads verification records
    - produces deterministic integrity hash
    - computes executive fields so the certificate stops showing "not available"
    """

    @staticmethod
    def _get_db():
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
            return {k: LineageCertificateService._serialize_value(v) for k, v in value.items()}
        return value

    @staticmethod
    def _normalize_document(document: dict | None) -> dict:
        if not document:
            return {}
        return LineageCertificateService._serialize_value(document)

    @staticmethod
    def _normalize_documents(documents: list[dict]) -> list[dict]:
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

    def _find_family(self, family_id: str) -> dict | None:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        family = db["families"].find_one({"_id": family_lookup})
        if family:
            return family

        family = db["families"].find_one({"family_id": family_id})
        if family:
            return family

        return None

    def _find_family_members(self, family_id: str) -> list[dict]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        members = list(db["family_members"].find({"family_id": family_id}))
        if members:
            return members

        members = list(db["family_members"].find({"family_id": family_lookup}))
        if members:
            return members

        return []

    def _find_relationships(self, family_id: str) -> list[dict]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        relationships = list(db["relationships"].find({"family_id": family_id}))
        if relationships:
            return relationships

        relationships = list(db["relationships"].find({"family_id": family_lookup}))
        if relationships:
            return relationships

        return []

    def _find_verification_records(self, family_id: str) -> list[dict]:
        db = self._get_db()
        family_lookup = self._safe_object_id(family_id)

        records = list(db["verification_records"].find({"family_id": family_id}))
        if records:
            return records

        records = list(db["verification_records"].find({"family_id": family_lookup}))
        if records:
            return records

        return []

    @staticmethod
    def _display_name(member: dict) -> str:
        full_name = member.get("full_name")
        if full_name:
            return str(full_name)

        first_name = str(member.get("first_name", "") or "").strip()
        last_name = str(member.get("last_name", "") or "").strip()
        joined = f"{first_name} {last_name}".strip()

        return joined or "Unknown"

    def _member_summary(self, member: dict) -> dict:
        return {
            "id": str(member.get("_id", "")),
            "full_name": self._display_name(member),
            "role": member.get("role"),
            "relationship_type": member.get("relationship_type"),
            "generation": self._to_int(member.get("generation")),
            "gender": member.get("gender"),
            "birth_date": self._serialize_value(member.get("birth_date")),
            "is_verified": bool(member.get("is_verified", False)),
            "canonical_person_id": self._serialize_value(member.get("canonical_person_id")),
        }

    @staticmethod
    def _relationship_summary(relationship: dict) -> dict:
        return {
            "id": str(relationship.get("_id", "")),
            "person_1_id": LineageCertificateService._serialize_value(relationship.get("person_1_id")),
            "person_2_id": LineageCertificateService._serialize_value(relationship.get("person_2_id")),
            "relationship_type": relationship.get("relationship_type"),
            "status": relationship.get("status"),
        }

    @staticmethod
    def _verification_summary(record: dict) -> dict:
        return {
            "id": str(record.get("_id", "")),
            "verification_type": record.get("verification_type"),
            "status": record.get("status"),
            "reviewed_by": record.get("reviewed_by"),
            "created_at": LineageCertificateService._serialize_value(record.get("created_at")),
            "updated_at": LineageCertificateService._serialize_value(record.get("updated_at")),
        }

    @staticmethod
    def _calculate_integrity_hash(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _compute_generation_count(member_summaries: list[dict]) -> int:
        gens = [m.get("generation") for m in member_summaries if isinstance(m.get("generation"), int)]
        if not gens:
            return 0
        return max(gens) - min(gens) + 1

    @staticmethod
    def _compute_executive_fields(member_summaries: list[dict], record_integrity: str) -> dict:
        gens = [m.get("generation") for m in member_summaries if isinstance(m.get("generation"), int)]
        min_gen = min(gens) if gens else None
        max_gen = max(gens) if gens else None

        founders = []
        if min_gen is not None:
            founders = [m["full_name"] for m in member_summaries if m.get("generation") == min_gen and m.get("full_name")]

        latest = []
        if max_gen is not None:
            latest = [m["full_name"] for m in member_summaries if m.get("generation") == max_gen and m.get("full_name")]

        verified_count = sum(1 for m in member_summaries if m.get("is_verified"))

        ordered = sorted(
            [m for m in member_summaries if m.get("full_name")],
            key=lambda m: (
                m.get("generation") if isinstance(m.get("generation"), int) else 9999,
                str(m.get("full_name", "")).lower(),
            ),
        )
        key_path = [m["full_name"] for m in ordered[:10]]

        return {
            "record_integrity": record_integrity,
            "founding_line": f"Founding generation: {' + '.join(founders)}" if founders else "Founding lineage not available.",
            "verified_branches": f"Verified members: {verified_count} / {len(member_summaries)}" if member_summaries else "No verified branches recorded.",
            "key_lineage_path": key_path,
            "descendant_summary": f"Latest generation recorded: {', '.join(latest)}" if latest else "No descendant records summarized on this certificate.",
        }

    def build_certificate(self, family_id: str) -> dict:
        family = self._find_family(family_id)
        if not family:
            raise ValueError(f"Family not found for family_id: {family_id}")

        members = self._find_family_members(family_id)
        relationships = self._find_relationships(family_id)
        verification_records = self._find_verification_records(family_id)

        normalized_family = self._normalize_document(family)

        member_summaries = [self._member_summary(m) for m in self._normalize_documents(members)]
        relationship_summaries = [self._relationship_summary(r) for r in self._normalize_documents(relationships)]
        verification_summaries = [self._verification_summary(v) for v in self._normalize_documents(verification_records)]

        verified_member_count = sum(1 for m in member_summaries if m.get("is_verified"))
        verification_pass_count = sum(
            1
            for v in verification_summaries
            if str(v.get("status", "")).lower() in {"verified", "approved", "passed"}
        )

        family_record_id = str(normalized_family.get("_id", family_id))
        family_name = normalized_family.get("family_name") or normalized_family.get("name") or "Unnamed Family"
        created_by = normalized_family.get("created_by") or normalized_family.get("owner") or "Unknown"

        generation_count = self._compute_generation_count(member_summaries)

        overall_status = "Verified" if verification_pass_count > 0 else "Recorded"
        executive = self._compute_executive_fields(member_summaries, overall_status)

        certificate_core = {
            "certificate_type": "lineage_certificate",
            "certificate_version": "1.0.0",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "family": {
                "id": family_record_id,
                "family_name": family_name,
                "project_id": normalized_family.get("project_id"),
                "status": normalized_family.get("status"),
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
                "status": overall_status.lower(),  # frontend can title-case if needed
                "integrity_hash": integrity_hash,
            },
        }