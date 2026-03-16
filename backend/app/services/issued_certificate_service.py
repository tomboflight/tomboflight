from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

import app.database as database
from app.services.lineage_certificate_service import LineageCertificateService


class IssuedCertificateService:
    """
    Persists immutable lineage certificates into MongoDB with versioning.

    Rules:
    - issued certificates are immutable records
    - issuing again for the same family creates a new version
    - old records remain preserved
    """

    def __init__(self):
        self.lineage_certificate_service = LineageCertificateService()

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
            return [IssuedCertificateService._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {
                k: IssuedCertificateService._serialize_value(v)
                for k, v in value.items()
            }
        return value

    @staticmethod
    def _safe_object_id(value: str) -> Any:
        try:
            return ObjectId(value)
        except Exception:
            return value

    def _get_next_version_number(self, family_id: str) -> int:
        db = self._get_db()

        latest = db["issued_certificates"].find_one(
            {"family_id": family_id},
            sort=[("version", -1)],
        )

        if not latest:
            return 1

        return int(latest.get("version", 0)) + 1

    def issue_certificate(
        self,
        family_id: str,
        issued_by: str = "system",
        notes: str | None = None,
    ) -> dict:
        db = self._get_db()

        certificate_result = self.lineage_certificate_service.build_certificate(family_id)
        certificate_payload = certificate_result["certificate"]

        canonical_family_id = str(certificate_payload.get("family", {}).get("id"))
        family_name = certificate_payload.get("family", {}).get("family_name")
        base_certificate_id = str(certificate_payload.get("certificate_id"))

        version = self._get_next_version_number(canonical_family_id)
        versioned_certificate_id = f"{base_certificate_id}-v{version}"

        now = datetime.now(timezone.utc)

        previous_latest = db["issued_certificates"].find_one(
            {"family_id": canonical_family_id, "is_latest": True},
            sort=[("version", -1)],
        )

        supersedes_certificate_id = None
        if previous_latest:
            supersedes_certificate_id = previous_latest.get("certificate_id")

            db["issued_certificates"].update_one(
                {"_id": previous_latest["_id"]},
                {
                    "$set": {
                        "is_latest": False,
                        "updated_at": now,
                    }
                },
            )

        stored_payload = {
            **certificate_payload,
            "certificate_id": versioned_certificate_id,
            "base_certificate_id": base_certificate_id,
            "version": version,
        }

        certificate_record = {
            "record_type": "issued_lineage_certificate",
            "certificate_type": certificate_payload.get("certificate_type"),
            "certificate_version": certificate_payload.get("certificate_version"),
            "certificate_id": versioned_certificate_id,
            "base_certificate_id": base_certificate_id,
            "version": version,
            "family_id": canonical_family_id,
            "family_name": family_name,
            "status": certificate_payload.get("status"),
            "integrity_hash": certificate_payload.get("integrity_hash"),
            "issued_at": certificate_payload.get("issued_at"),
            "issued_by": issued_by,
            "notes": notes,
            "is_latest": True,
            "is_immutable": True,
            "supersedes_certificate_id": supersedes_certificate_id,
            "certificate_payload": stored_payload,
            "created_at": now,
            "updated_at": now,
        }

        insert_result = db["issued_certificates"].insert_one(certificate_record)
        saved_record = db["issued_certificates"].find_one({"_id": insert_result.inserted_id})

        return {
            "success": True,
            "message": "Immutable certificate issued and saved successfully.",
            "issued_certificate": self._serialize_value(saved_record),
        }

    def list_certificates(self, limit: int = 50) -> dict:
        db = self._get_db()

        documents = list(
            db["issued_certificates"]
            .find({})
            .sort([("created_at", -1), ("version", -1)])
            .limit(limit)
        )

        return {
            "success": True,
            "count": len(documents),
            "issued_certificates": self._serialize_value(documents),
        }

    def get_certificate_by_record_id(self, record_id: str) -> dict:
        db = self._get_db()

        lookup_id = self._safe_object_id(record_id)
        document = db["issued_certificates"].find_one({"_id": lookup_id})

        if not document:
            raise ValueError(f"Issued certificate not found for record_id: {record_id}")

        return {
            "success": True,
            "issued_certificate": self._serialize_value(document),
        }

    def get_certificate_by_certificate_id(self, certificate_id: str) -> dict:
        db = self._get_db()

        document = db["issued_certificates"].find_one({"certificate_id": certificate_id})

        if not document:
            raise ValueError(f"Issued certificate not found for certificate_id: {certificate_id}")

        return {
            "success": True,
            "issued_certificate": self._serialize_value(document),
        }

    def list_family_certificate_versions(self, family_id: str) -> dict:
        db = self._get_db()

        documents = list(
            db["issued_certificates"]
            .find({"family_id": family_id})
            .sort([("version", -1)])
        )

        return {
            "success": True,
            "family_id": family_id,
            "count": len(documents),
            "issued_certificates": self._serialize_value(documents),
        }

    def get_latest_family_certificate(self, family_id: str) -> dict:
        db = self._get_db()

        document = db["issued_certificates"].find_one(
            {"family_id": family_id, "is_latest": True},
            sort=[("version", -1)],
        )

        if not document:
            raise ValueError(f"No issued certificate found for family_id: {family_id}")

        return {
            "success": True,
            "issued_certificate": self._serialize_value(document),
        }

    def ensure_indexes(self) -> dict:
        db = self._get_db()

        db["issued_certificates"].create_index(
            [("certificate_id", 1)],
            unique=True,
            name="uq_certificate_id",
        )
        db["issued_certificates"].create_index(
            [("family_id", 1), ("version", -1)],
            name="idx_family_version",
        )
        db["issued_certificates"].create_index(
            [("family_id", 1), ("is_latest", 1)],
            name="idx_family_latest",
        )
        db["issued_certificates"].create_index(
            [("base_certificate_id", 1)],
            name="idx_base_certificate_id",
        )

        return {
            "success": True,
            "message": "Issued certificate indexes ensured successfully.",
        }