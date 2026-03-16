from fastapi import APIRouter, HTTPException

from app.services.tree_service import get_family_tree, get_filtered_family_tree

router = APIRouter(prefix="/tree", tags=["Tree"])


@router.get("/{family_id}")
def get_tree(family_id: str):
    tree = get_family_tree(family_id)

    if not tree["members"] and not tree["nodes"] and not tree["relationships"]:
        raise HTTPException(status_code=404, detail="Family tree not found.")

    return tree


@router.get("/{family_id}/verified")
def get_verified_tree(family_id: str):
    tree = get_filtered_family_tree(family_id, "verified")
    return tree


@router.get("/{family_id}/narrative")
def get_narrative_tree(family_id: str):
    tree = get_filtered_family_tree(family_id, "narrative")
    return tree


@router.get("/{family_id}/private")
def get_private_tree(family_id: str):
    tree = get_filtered_family_tree(family_id, "private")
    return tree