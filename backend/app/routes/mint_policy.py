from __future__ import annotations

from fastapi import APIRouter

from app.services.mint_policy_service import list_package_mint_policies

router = APIRouter(prefix="/mint-policy", tags=["Mint Policy"])


@router.get("/packages")
def get_package_mint_policy_list():
    return {
        "packages": list_package_mint_policies(),
    }
