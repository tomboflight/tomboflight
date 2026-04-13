from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.package_catalog import (
    PACKAGE_CATALOG,
    PACKAGE_CODE_ALIASES,
    PACKAGE_CONTROL_POLICY,
)
from app.core.package_type_catalog import normalize_package_type


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_slug(value: Any) -> str:
    return _normalize(value).lower().replace("_", "-").replace(" ", "-")


def _normalize_code(value: Any) -> str:
    return _normalize(value).lower().replace("-", "_").replace(" ", "_")


def _code_to_slug_map() -> dict[str, str]:
    return {
        package_code: package_code.replace("_", "-")
        for package_code in PACKAGE_CATALOG.keys()
    }


def _slug_to_code_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for alias, package_code in PACKAGE_CODE_ALIASES.items():
        alias_slug = _normalize_slug(alias)
        if alias_slug:
            mapping[alias_slug] = package_code
        alias_code = _normalize_code(alias)
        if alias_code:
            mapping[alias_code.replace("_", "-")] = package_code
    for package_code, package_slug in _code_to_slug_map().items():
        mapping[package_slug] = package_code
        mapping[package_code.replace("_", "-")] = package_code
    return mapping


def translate_package_slug_to_code(value: Any) -> str:
    raw = _normalize(value)
    if not raw:
        return ""
    lowered = raw.lower()
    direct = PACKAGE_CODE_ALIASES.get(lowered)
    if direct:
        return direct
    return _slug_to_code_map().get(_normalize_slug(raw), _normalize_code(raw))


def translate_package_code_to_slug(value: Any) -> str:
    code = translate_package_slug_to_code(value)
    if not code:
        return ""
    return _code_to_slug_map().get(code, code.replace("_", "-"))


def normalize_package_code(value: Any) -> str:
    return translate_package_slug_to_code(value)


def normalize_package_slug(value: Any) -> str:
    code = translate_package_slug_to_code(value)
    if not code:
        return _normalize_slug(value)
    return translate_package_code_to_slug(code)


def resolve_package_identity(value: Any) -> dict[str, Any]:
    raw_value = _normalize(value)
    package_code = normalize_package_code(raw_value)
    package_slug = normalize_package_slug(raw_value)
    package = PACKAGE_CATALOG.get(package_code)
    policy = deepcopy(PACKAGE_CONTROL_POLICY.get(package_code) or {})
    mint_policy = dict(policy.get("mint_policy") or {})

    if not package:
        return {
            "known": False,
            "raw_value": raw_value,
            "package_slug": package_slug,
            "package_code": package_code,
            "display_name": raw_value or package_slug or package_code,
            "package_name": raw_value or package_slug or package_code,
            "lane": "",
            "package_lane": "",
            "anchor_type": None,
            "mint_policy": {},
            "maintenance_default": "monthly",
            "normalization_status": "missing" if not raw_value else "unknown",
        }

    canonical_slug = translate_package_code_to_slug(package_code)
    normalized_lane = normalize_package_type(package.get("package_lane"))
    status = "canonical"
    lowered_raw = raw_value.lower()
    if lowered_raw and lowered_raw not in {canonical_slug, package_code}:
        status = "alias_mapped"

    return {
        "known": True,
        "raw_value": raw_value,
        "package_slug": canonical_slug,
        "package_code": package_code,
        "display_name": package.get("display_name"),
        "package_name": package.get("display_name"),
        "lane": normalized_lane,
        "package_lane": normalized_lane,
        "anchor_type": policy.get("anchor_type"),
        "mint_policy": mint_policy,
        "maintenance_default": str(policy.get("maintenance_default") or "monthly"),
        "normalization_status": status,
    }


def get_canonical_package_map() -> dict[str, Any]:
    packages: dict[str, dict[str, Any]] = {}
    for package_code, package in PACKAGE_CATALOG.items():
        identity = resolve_package_identity(package_code)
        packages[identity["package_slug"]] = {
            "slug": identity["package_slug"],
            "display_name": package.get("display_name"),
            "entitlement_code": package_code,
            "lane": identity["lane"],
            "anchor_type": identity["anchor_type"],
            "mint_policy": identity["mint_policy"],
            "maintenance_default": identity["maintenance_default"],
        }
    return {
        "packages": packages,
        "code_to_slug": _code_to_slug_map(),
        "slug_to_code": _slug_to_code_map(),
    }

