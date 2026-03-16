from datetime import datetime, UTC

from app.database import get_database
from app.schemas.project import ProjectCreate


def list_projects() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.projects.find().sort("created_at", -1))


def create_project(payload: ProjectCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-project-preview"
        return data

    result = db.projects.insert_one(data)
    data["_id"] = result.inserted_id
    return data
