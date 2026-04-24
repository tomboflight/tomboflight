from __future__ import annotations

from fastapi import APIRouter

from app.core.package_catalog import get_public_package_catalog

router = APIRouter(tags=["Package Catalog"])


@router.get("/package-catalog/public")
def get_public_package_catalog_route():
    return {"packages": get_public_package_catalog()}
