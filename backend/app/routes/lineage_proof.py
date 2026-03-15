from fastapi import APIRouter, Query

from app.services.lineage_proof_service import generate_lineage_proof

router = APIRouter(
    prefix="/lineage-proof",
    tags=["Lineage Proof"],
)


@router.get("/")
def get_lineage_proof(
    family_id: str = Query(...),
    ancestor_id: str = Query(...),
    descendant_id: str = Query(...),
):
    return generate_lineage_proof(
        family_id=family_id,
        ancestor_id=ancestor_id,
        descendant_id=descendant_id,
    )