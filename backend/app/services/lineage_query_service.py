from collections import defaultdict, deque
from typing import Any


ANCESTRY_RELATIONSHIP_TYPES = {
    "parent_child",
    "adoptive_parent_child",
    "step_parent_child",
}


class LineageQueryService:
    def __init__(self, db):
        self.db = db
        self.relationships = db["relationships"]
        self.family_members = db["family_members"]
        self.families = db["families"]

    def get_member_by_id(self, member_id: str) -> dict[str, Any] | None:
        member = self.family_members.find_one({"_id": self._to_object_id_or_raw(member_id)})
        if member:
            member["_id"] = str(member["_id"])
            return member

        member = self.family_members.find_one({"member_id": member_id})
        if member:
            member["_id"] = str(member["_id"])
            return member

        return None

    def get_family_by_id(self, family_id: str) -> dict[str, Any] | None:
        family = self.families.find_one({"_id": self._to_object_id_or_raw(family_id)})
        if family:
            family["_id"] = str(family["_id"])
            return family

        family = self.families.find_one({"family_id": family_id})
        if family:
            family["_id"] = str(family["_id"])
            return family

        return None

    def get_ancestors(self, member_id: str) -> dict[str, Any]:
        start_member = self.get_member_by_id(member_id)
        if not start_member:
            return {
                "member_id": member_id,
                "count": 0,
                "ancestors": [],
            }

        visited: set[str] = set()
        queue = deque([(member_id, 0)])
        ancestors: list[dict[str, Any]] = []

        while queue:
            current_member_id, depth = queue.popleft()

            parent_relationships = list(
                self.relationships.find(
                    {
                        "target_member_id": current_member_id,
                        "relationship_type": {"$in": list(ANCESTRY_RELATIONSHIP_TYPES)},
                    }
                )
            )

            for rel in parent_relationships:
                source_member_id = rel.get("source_member_id")
                if not source_member_id or source_member_id in visited:
                    continue

                visited.add(source_member_id)
                parent_member = self.get_member_by_id(source_member_id)

                ancestors.append(
                    {
                        "depth": depth + 1,
                        "relationship_type": rel.get("relationship_type"),
                        "member": parent_member,
                    }
                )

                queue.append((source_member_id, depth + 1))

        return {
            "member_id": member_id,
            "count": len(ancestors),
            "ancestors": ancestors,
        }

    def get_descendants(self, member_id: str) -> dict[str, Any]:
        start_member = self.get_member_by_id(member_id)
        if not start_member:
            return {
                "member_id": member_id,
                "count": 0,
                "descendants": [],
            }

        visited: set[str] = set()
        queue = deque([(member_id, 0)])
        descendants: list[dict[str, Any]] = []

        while queue:
            current_member_id, depth = queue.popleft()

            child_relationships = list(
                self.relationships.find(
                    {
                        "source_member_id": current_member_id,
                        "relationship_type": {"$in": list(ANCESTRY_RELATIONSHIP_TYPES)},
                    }
                )
            )

            for rel in child_relationships:
                target_member_id = rel.get("target_member_id")
                if not target_member_id or target_member_id in visited:
                    continue

                visited.add(target_member_id)
                child_member = self.get_member_by_id(target_member_id)

                descendants.append(
                    {
                        "depth": depth + 1,
                        "relationship_type": rel.get("relationship_type"),
                        "member": child_member,
                    }
                )

                queue.append((target_member_id, depth + 1))

        return {
            "member_id": member_id,
            "count": len(descendants),
            "descendants": descendants,
        }

    def get_tree(self, member_id: str) -> dict[str, Any]:
        member = self.get_member_by_id(member_id)
        if not member:
            return {
                "member_id": member_id,
                "member": None,
                "ancestors": [],
                "descendants": [],
            }

        ancestors = self.get_ancestors(member_id)
        descendants = self.get_descendants(member_id)

        return {
            "member_id": member_id,
            "member": member,
            "ancestors": ancestors["ancestors"],
            "descendants": descendants["descendants"],
        }

    def get_family_graph(self, family_id: str) -> dict[str, Any]:
        family = self.get_family_by_id(family_id)
        if not family:
            return {
                "family_id": family_id,
                "family": None,
                "nodes": [],
                "edges": [],
            }

        members = list(self.family_members.find({"family_id": family_id}))
        relationships = list(self.relationships.find({"family_id": family_id}))

        nodes = []
        for member in members:
            member["_id"] = str(member["_id"])
            nodes.append(
                {
                    "id": member["_id"],
                    "label": member.get("full_name")
                    or member.get("name")
                    or member.get("display_name")
                    or member["_id"],
                    "data": member,
                }
            )

        edges = []
        for rel in relationships:
            rel["_id"] = str(rel["_id"])
            edges.append(
                {
                    "id": rel["_id"],
                    "source": rel.get("source_member_id"),
                    "target": rel.get("target_member_id"),
                    "relationship_type": rel.get("relationship_type"),
                    "notes": rel.get("notes"),
                    "created_by": rel.get("created_by"),
                    "created_at": rel.get("created_at"),
                }
            )

        return {
            "family_id": family_id,
            "family": family,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    def get_member_neighbors(self, member_id: str) -> dict[str, Any]:
        member = self.get_member_by_id(member_id)
        if not member:
            return {
                "member_id": member_id,
                "member": None,
                "neighbors": [],
            }

        relationships = list(
            self.relationships.find(
                {
                    "$or": [
                        {"source_member_id": member_id},
                        {"target_member_id": member_id},
                    ]
                }
            )
        )

        neighbors = []
        for rel in relationships:
            rel["_id"] = str(rel["_id"])
            source_id = rel.get("source_member_id")
            target_id = rel.get("target_member_id")

            neighbor_id = target_id if source_id == member_id else source_id
            neighbor_member = self.get_member_by_id(neighbor_id)

            neighbors.append(
                {
                    "relationship_id": rel["_id"],
                    "relationship_type": rel.get("relationship_type"),
                    "neighbor": neighbor_member,
                    "direction": "outgoing" if source_id == member_id else "incoming",
                }
            )

        return {
            "member_id": member_id,
            "member": member,
            "count": len(neighbors),
            "neighbors": neighbors,
        }

    def _to_object_id_or_raw(self, value: str):
        try:
            from bson import ObjectId
            return ObjectId(value)
        except Exception:
            return value