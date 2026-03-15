from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

import app.database as database
from app.services.lineage_certificate_service import LineageCertificateService


class IssuedCertificateService:
    """
    Persists lineage certificates into MongoDB.

    Capabilities:
    - issue and save a certificate for a family
    - list saved certificates
    - fetch a saved certificate by record id
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

    def issue_certificate(
        self,
        family_id: str,
        issued_by: str = "system",
        notes: str | None = None,
    ) -> dict:
        db = self._get_db()

        certificate_result = self.lineage_certificate_service.build_certificate(family_id)
        certificate_payload = certificate_result["certificate"]

        certificate_record = {
            "certificate_type": certificate_payload.get("certificate_type"),
            "certificate_version": certificate_payload.get("certificate_version"),
            "certificate_id": certificate_payload.get("certificate_id"),
            "family_id": certificate_payload.get("family", {}).get("id"),
            "family_name": certificate_payload.get("family", {}).get("family_name"),
            "status": certificate_payload.get("status"),
            "integrity_hash": certificate_payload.get("integrity_hash"),
            "issued_at": certificate_payload.get("issued_at"),
            "issued_by": issued_by,
            "notes": notes,
            "certificate_payload": certificate_payload,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        insert_result = db["issued_certificates"].insert_one(certificate_record)

        saved_record = db["issued_certificates"].find_one({"_id": insert_result.inserted_id})

        return {
            "success": True,
            "message": "Certificate issued and saved successfully.",
            "issued_certificate": self._serialize_value(saved_record),
        }

    def list_certificates(self, limit: int = 50) -> dict:
        db = self._get_db()

        documents = list(
            db["issued_certificates"]
            .find({})
            .sort("created_at", -1)
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