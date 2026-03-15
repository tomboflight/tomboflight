from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_create_metadata(data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    now = utc_now()
    data["created_at"] = now
    data["updated_at"] = now

    if user_id:
        data["created_by"] = user_id
        data["updated_by"] = user_id

    return data


def apply_update_metadata(data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    data["updated_at"] = utc_now()

    if user_id:
        data["updated_by"] = user_id

    return data