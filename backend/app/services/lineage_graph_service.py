from app.database import get_database


def build_lineage_graph(family_id: str):
    db = get_database()

    if db is None:
        return {"nodes": [], "links": []}

    members = list(db.family_members.find({"family_id": family_id}))

    nodes = []
    links = []

    for m in members:
        node = {
            "id": str(m.get("_id")),
            "name": m.get("name"),
            "gender": m.get("gender"),
            "birth_year": m.get("birth_year"),
        }

        nodes.append(node)

        parent_id = m.get("parent_id")

        if parent_id:
            links.append(
                {
                    "source": str(parent_id),
                    "target": str(m.get("_id")),
                    "relationship": "parent",
                }
            )

    return {
        "nodes": nodes,
        "links": links,
    }