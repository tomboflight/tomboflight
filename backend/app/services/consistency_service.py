from datetime import datetime
from bson import ObjectId

from app.database import get_database


def run_consistency_check() -> list[dict]:
    db = get_database()
    issues = []

    if db is None:
        return issues

    members = list(db.family_members.find())

    # --- check duplicate names and birthdates
    seen = {}

    for member in members:
        key = (
            member.get("first_name"),
            member.get("last_name"),
            member.get("birthdate"),
        )

        if key in seen:
            issues.append(
                {
                    "type": "duplicate_person",
                    "severity": "warning",
                    "description": f"Possible duplicate person: {key}",
                    "entity_id": str(member["_id"]),
                }
            )
        else:
            seen[key] = member["_id"]

    # --- check impossible parent-child ages
    for member in members:
        birthdate = member.get("birthdate")

        parent_id = member.get("parent_id")

        if not birthdate or not parent_id:
            continue

        parent = db.family_members.find_one({"_id": ObjectId(parent_id)})

        if not parent:
            continue

        parent_birth = parent.get("birthdate")

        if not parent_birth:
            continue

        try:
            child_year = int(birthdate.split("-")[0])
            parent_year = int(parent_birth.split("-")[0])

            if child_year - parent_year < 12:
                issues.append(
                    {
                        "type": "impossible_parent_age",
                        "severity": "critical",
                        "description": "Parent appears too young for child.",
                        "entity_id": str(member["_id"]),
                    }
                )
        except Exception:
            continue

    return issues