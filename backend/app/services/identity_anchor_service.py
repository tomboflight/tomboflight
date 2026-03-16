import datetime
import hashlib
from typing import Any, Dict

from app.database import get_database


def create_identity_anchor(person_id: str, family_id: str) -> Dict[str, Any]:
    db = get_database()
    if db is None:
        return {
            "success": False,
            "error": "Database connection is not available.",
        }

    timestamp = datetime.datetime.utcnow().isoformat()
    payload = f"{person_id}:{family_id}:{timestamp}"
    anchor_hash = hashlib.sha256(payload.encode()).hexdigest()

    record = {
        "person_id": person_id,
        "family_id": family_id,
        "timestamp": timestamp,
        "anchor_hash": anchor_hash,
        "verified": False,
    }

    db["identity_anchors"].insert_one(record)

    return {
        "success": True,
        "anchor": record,
    }


def get_identity_anchor(person_id: str) -> Dict[str, Any]:
    db = get_database()
    if db is None:
        return {
            "success": False,
            "error": "Database connection is not available.",
        }

    record = db["identity_anchors"].find_one({"person_id": person_id})

    if not record:
        return {
            "success": False,
            "message": "Anchor not found",
        }

    record["_id"] = str(record["_id"])

    return {
        "success": True,
        "anchor": record,
    }