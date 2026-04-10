from datetime import date, datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.relationship_catalog import (
    ALLOWED_RELATIONSHIP_TYPE_SET,
    ALLOWED_RELATIONSHIP_TYPES,
    ANCESTRY_RELATIONSHIP_TYPES,
    BIOLOGICAL_PARENT_RELATIONSHIP_TYPE,
    SYMMETRIC_RELATIONSHIP_TYPES,
    normalize_relationship_type,
)
from app.schemas.relationship import RelationshipCreate

MIN_PARENT_CHILD_AGE_GAP = 12


def normalize_mongo_doc(document: dict[str, Any]) -> dict[str, Any]:
    if not document:
        return document
    if "_id" in document:
        document["_id"] = str(document["_id"])
    return document


class RelationshipGuardrailService:
    def __init__(self, db):
        self.db = db
        self.relationships = db["relationships"]
        self.family_members = db["family_members"]
        self.families = db["families"]

    def ensure_indexes(self) -> None:
        try:
            self.relationships.create_index(
                [
                    ("family_id", 1),
                    ("source_member_id", 1),
                    ("target_member_id", 1),
                    ("relationship_type", 1),
                ],
                name="idx_relationships_edge_unique",
                unique=True,
            )
        except Exception as e:
            print(f"Warning: could not create relationship index: {e}")

    def validate_relationship_payload(self, payload: RelationshipCreate) -> None:
        normalized_relationship_type = normalize_relationship_type(
            payload.relationship_type
        )
        if normalized_relationship_type not in ALLOWED_RELATIONSHIP_TYPE_SET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid relationship_type '{payload.relationship_type}'. "
                    f"Allowed values: {sorted(ALLOWED_RELATIONSHIP_TYPES)}"
                ),
            )
        payload.relationship_type = normalized_relationship_type

        if payload.source_member_id == payload.target_member_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Self links are not allowed. source_member_id and target_member_id must differ.",
            )

        family = self.families.find_one({"_id": self._to_object_id_or_raw(payload.family_id)})
        if not family:
            family = self.families.find_one({"family_id": payload.family_id})

        if not family:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Family '{payload.family_id}' was not found.",
            )

        source_member = self._find_member(payload.source_member_id)
        target_member = self._find_member(payload.target_member_id)

        if not source_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source member '{payload.source_member_id}' was not found.",
            )

        if not target_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target member '{payload.target_member_id}' was not found.",
            )

        source_family_id = self._extract_member_family_id(source_member)
        target_family_id = self._extract_member_family_id(target_member)

        if source_family_id != payload.family_id or target_family_id != payload.family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cross-family links are not allowed. "
                    "Both members must belong to the same family_id as the relationship payload."
                ),
            )

        if source_family_id != target_family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cross-family links are not allowed. Members belong to different families.",
            )

        duplicate = self._find_duplicate(payload)
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate relationship edge already exists.",
            )

        if payload.relationship_type in ANCESTRY_RELATIONSHIP_TYPES:
            self._validate_no_ancestry_cycle(payload)

        self._validate_relationship_rules(payload, source_member, target_member)

    def create_relationship(self, payload: RelationshipCreate) -> dict[str, Any]:
        self.ensure_indexes()
        self.validate_relationship_payload(payload)

        document = {
            "family_id": payload.family_id,
            "source_member_id": payload.source_member_id,
            "target_member_id": payload.target_member_id,
            "relationship_type": payload.relationship_type,
            "notes": payload.notes,
            "created_by": payload.created_by,
            "created_at": datetime.now(timezone.utc),
        }

        result = self.relationships.insert_one(document)
        created = self.relationships.find_one({"_id": result.inserted_id})
        return normalize_mongo_doc(created)

    def _find_member(self, member_id: str):
        member = self.family_members.find_one({"_id": self._to_object_id_or_raw(member_id)})
        if member:
            return member

        member = self.family_members.find_one({"member_id": member_id})
        return member

    def _find_duplicate(self, payload: RelationshipCreate):
        exact_match = self.relationships.find_one(
            {
                "family_id": payload.family_id,
                "source_member_id": payload.source_member_id,
                "target_member_id": payload.target_member_id,
                "relationship_type": payload.relationship_type,
            }
        )
        if exact_match:
            return exact_match

        if payload.relationship_type in SYMMETRIC_RELATIONSHIP_TYPES:
            reverse_match = self.relationships.find_one(
                {
                    "family_id": payload.family_id,
                    "source_member_id": payload.target_member_id,
                    "target_member_id": payload.source_member_id,
                    "relationship_type": payload.relationship_type,
                }
            )
            if reverse_match:
                return reverse_match

        return None

    def _validate_no_ancestry_cycle(self, payload: RelationshipCreate) -> None:
        parent_id = payload.source_member_id
        child_id = payload.target_member_id

        descendants_of_child = self._collect_descendants(
            family_id=payload.family_id,
            start_member_id=child_id,
        )

        if parent_id in descendants_of_child:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Ancestry cycle detected. This relationship would create a circular "
                    "parent-child lineage."
                ),
            )

    def _collect_descendants(self, family_id: str, start_member_id: str) -> set[str]:
        visited: set[str] = set()
        stack: list[str] = [start_member_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            cursor = self.relationships.find(
                {
                    "family_id": family_id,
                    "source_member_id": current,
                    "relationship_type": {"$in": list(ANCESTRY_RELATIONSHIP_TYPES)},
                }
            )

            for rel in cursor:
                next_member = rel.get("target_member_id")
                if next_member and next_member not in visited:
                    stack.append(str(next_member))

        return visited

    def _validate_relationship_rules(
        self,
        payload: RelationshipCreate,
        source_member: dict[str, Any],
        target_member: dict[str, Any],
    ) -> None:
        self._validate_pair_conflicts(payload)
        self._validate_biological_parent_limit(payload)
        self._validate_parent_child_age_gap(payload, source_member, target_member)
        self._validate_reverse_ancestry_conflict(payload)

    def _validate_pair_conflicts(self, payload: RelationshipCreate) -> None:
        source_id = payload.source_member_id
        target_id = payload.target_member_id
        family_id = payload.family_id
        rel_type = payload.relationship_type

        pair_relationships = self._get_pair_relationships(family_id, source_id, target_id)

        if rel_type == "spouse":
            forbidden = {"sibling"} | ANCESTRY_RELATIONSHIP_TYPES
            if any(r["relationship_type"] in forbidden for r in pair_relationships):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Invalid spouse relationship. This pair already has a conflicting "
                        "sibling or ancestry relationship."
                    ),
                )

        elif rel_type == "sibling":
            forbidden = {"spouse"} | ANCESTRY_RELATIONSHIP_TYPES
            if any(r["relationship_type"] in forbidden for r in pair_relationships):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Invalid sibling relationship. This pair already has a conflicting "
                        "spouse or ancestry relationship."
                    ),
                )

        elif rel_type in ANCESTRY_RELATIONSHIP_TYPES:
            forbidden = {"spouse", "sibling"}
            if any(r["relationship_type"] in forbidden for r in pair_relationships):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Invalid ancestry relationship. This pair already has a conflicting "
                        "spouse or sibling relationship."
                    ),
                )

    def _validate_biological_parent_limit(self, payload: RelationshipCreate) -> None:
        if payload.relationship_type != BIOLOGICAL_PARENT_RELATIONSHIP_TYPE:
            return

        biological_parent_count = self.relationships.count_documents(
            {
                "family_id": payload.family_id,
                "target_member_id": payload.target_member_id,
                "relationship_type": BIOLOGICAL_PARENT_RELATIONSHIP_TYPE,
            }
        )

        if biological_parent_count >= 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Biological parent limit exceeded. A member cannot have more than "
                    "2 biological parent_child relationships."
                ),
            )

    def _validate_parent_child_age_gap(
        self,
        payload: RelationshipCreate,
        source_member: dict[str, Any],
        target_member: dict[str, Any],
    ) -> None:
        if payload.relationship_type not in ANCESTRY_RELATIONSHIP_TYPES:
            return

        source_birth_date = self._extract_birth_date(source_member)
        target_birth_date = self._extract_birth_date(target_member)

        if not source_birth_date or not target_birth_date:
            return

        if source_birth_date >= target_birth_date:
            age_gap = self._calculate_year_gap(source_birth_date, target_birth_date)
            if age_gap < MIN_PARENT_CHILD_AGE_GAP:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid parent-child age gap. Parent/guardian relationships require at least "
                        f"{MIN_PARENT_CHILD_AGE_GAP} years difference when birth dates are available."
                    ),
                )
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ancestry relationship. Parent/guardian cannot be younger than child.",
        )

    def _validate_reverse_ancestry_conflict(self, payload: RelationshipCreate) -> None:
        if payload.relationship_type not in ANCESTRY_RELATIONSHIP_TYPES:
            return

        reverse_conflict = self.relationships.find_one(
            {
                "family_id": payload.family_id,
                "source_member_id": payload.target_member_id,
                "target_member_id": payload.source_member_id,
                "relationship_type": {"$in": list(ANCESTRY_RELATIONSHIP_TYPES)},
            }
        )

        if reverse_conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid ancestry relationship. Reverse parent/child style relationship "
                    "already exists for this pair."
                ),
            )

    def _get_pair_relationships(
        self,
        family_id: str,
        source_member_id: str,
        target_member_id: str,
    ) -> list[dict[str, Any]]:
        cursor = self.relationships.find(
            {
                "family_id": family_id,
                "$or": [
                    {
                        "source_member_id": source_member_id,
                        "target_member_id": target_member_id,
                    },
                    {
                        "source_member_id": target_member_id,
                        "target_member_id": source_member_id,
                    },
                ],
            }
        )
        return list(cursor)

    def _extract_member_family_id(self, member: dict[str, Any]) -> Optional[str]:
        family_id = member.get("family_id")
        if family_id is not None:
            return str(family_id)

        if "familyId" in member:
            return str(member["familyId"])

        return None

    def _extract_birth_date(self, member: dict[str, Any]) -> Optional[date]:
        possible_fields = [
            member.get("birth_date"),
            member.get("date_of_birth"),
            member.get("dob"),
        ]

        for value in possible_fields:
            parsed = self._parse_date(value)
            if parsed:
                return parsed

        return None

    def _parse_date(self, value: Any) -> Optional[date]:
        if value is None:
            return None

        if isinstance(value, date) and not isinstance(value, datetime):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None

            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            except ValueError:
                pass

            try:
                return date.fromisoformat(raw)
            except ValueError:
                return None

        return None

    def _calculate_year_gap(self, older_birth_date: date, younger_birth_date: date) -> int:
        years = younger_birth_date.year - older_birth_date.year
        before_birthday = (younger_birth_date.month, younger_birth_date.day) < (
            older_birth_date.month,
            older_birth_date.day,
        )
        return years - (1 if before_birthday else 0)

    def _to_object_id_or_raw(self, value: str):
        try:
            return ObjectId(value)
        except Exception:
            return value
