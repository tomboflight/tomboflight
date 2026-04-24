from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.core.package_catalog import (
    get_addon_catalog,
    get_package_identifier_map,
    get_package_catalog,
    get_public_package_catalog,
    list_package_control_profiles,
)
from app.core.organization_template_catalog import get_organization_template_catalog
from app.core.package_mapping import get_canonical_package_map
from app.services.entitlement_service import (
    can_purchase_addon,
    compute_upgrade_quote,
    resolve_project_entitlements,
)
from app.core.entitlement_conformance_matrix import get_entitlement_conformance_matrix

router = APIRouter(prefix="/packages", tags=["Packages"])


@router.get("/catalog")
def get_package_catalog_route():
    return {
        "packages": get_package_catalog(),
        "addons": get_addon_catalog(),
        "package_map": get_canonical_package_map(),
        "package_identifier_map": get_package_identifier_map(),
        "control_profiles": list_package_control_profiles(),
        "organization_templates": get_organization_template_catalog(),
    }


@router.get("/organization-templates")
def get_organization_templates_route():
    return get_organization_template_catalog()


@router.get("/conformance-matrix")
def get_package_conformance_matrix_route():
    return get_entitlement_conformance_matrix()


@router.get("/entitlements/{package_code}")
def get_package_entitlements_route(
    package_code: str,
    addons: str | None = Query(default=None),
):
    addon_codes = [value.strip() for value in str(addons or "").split(",") if value.strip()]
    try:
        entitlements = resolve_project_entitlements(package_code, addon_codes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "package_code": package_code,
        "entitlements": entitlements,
    }


@router.get("/upgrades/{from_package_code}/{to_package_code}")
def get_upgrade_quote_route(from_package_code: str, to_package_code: str):
    try:
        quote = compute_upgrade_quote(from_package_code, to_package_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return quote


@router.get("/addons/{package_code}/{addon_code}")
def check_addon_compatibility_route(package_code: str, addon_code: str):
    try:
        allowed = can_purchase_addon(package_code, addon_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "package_code": package_code,
        "addon_code": addon_code,
        "allowed": allowed,
    }


@router.get("/public")
def get_public_package_catalog_route():
    return {"packages": get_public_package_catalog()}
