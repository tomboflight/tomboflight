from __future__ import annotations

from pathlib import Path
import re

import pytest

from app.core.commercial_catalog_overlay import COMMERCIAL_ADDON_SKUS
from app.core.package_catalog import get_addon, get_addon_catalog, get_package
from app.services import entitlement_service, order_service


REPO_ROOT = Path(__file__).resolve().parents[2]


def _published_checkout_addons() -> dict[str, dict[str, str]]:
    source = (REPO_ROOT / "config.js").read_text(encoding="utf-8")
    start = source.index("addons: [")
    end = source.index("maintenance: [", start)
    section = source[start:end]
    products: dict[str, dict[str, str]] = {}
    for block in re.findall(r"\{\s*category:.*?\n\s*\},", section, flags=re.DOTALL):
        slug_match = re.search(r'slug:\s*"([^"]+)"', block)
        name_match = re.search(r'name:\s*"([^"]+)"', block)
        price_match = re.search(r'priceLabel:\s*"([^"]+)"', block)
        checkout_match = re.search(r'checkoutUrl:\s*"([^"]*)"', block)
        if not slug_match or not name_match or not price_match or not checkout_match:
            continue
        if not checkout_match.group(1).strip():
            continue
        products[slug_match.group(1)] = {
            "name": name_match.group(1),
            "price_label": price_match.group(1),
            "checkout_url": checkout_match.group(1),
        }
    return products


def _first_dollar_amount(label: str) -> float:
    match = re.search(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)", label)
    assert match, f"Missing published dollar amount: {label}"
    return float(match.group(1).replace(",", ""))


def _checkout_session(*, code: str, name: str, dollars: float, interval: str = "") -> dict:
    recurring = {"interval": interval} if interval else {}
    return {
        "id": f"cs_{code}",
        "status": "complete",
        "payment_status": "paid",
        "amount_total": int(round(dollars * 100)),
        "currency": "usd",
        "metadata": {"item_type": "addon", "addon_code": code},
        "line_items": {
            "data": [
                {
                    "quantity": 1,
                    "description": name,
                    "price": {
                        "id": f"price_{code}",
                        "unit_amount": int(round(dollars * 100)),
                        "currency": "usd",
                        "recurring": recurring,
                        "product": {
                            "id": f"prod_{code}",
                            "name": name,
                            "metadata": {"addon_code": code},
                        },
                    },
                }
            ]
        },
    }


def test_every_published_paid_addon_has_exact_server_catalog_name_and_price():
    published = _published_checkout_addons()
    catalog = get_addon_catalog()
    missing = sorted(set(published) - set(catalog))
    assert missing == []

    mismatches: list[str] = []
    for sku, public in published.items():
        addon = get_addon(sku) or {}
        public_price = _first_dollar_amount(public["price_label"])
        if str(addon.get("display_name") or "") != public["name"]:
            mismatches.append(
                f"{sku}: name public={public['name']!r} backend={addon.get('display_name')!r}"
            )
        if float(addon.get("price_usd") or 0) != public_price:
            mismatches.append(
                f"{sku}: price public={public_price} backend={addon.get('price_usd')!r}"
            )
    assert mismatches == []


def test_overlay_contains_every_published_non_nft_checkout_sku():
    published = _published_checkout_addons()
    assert set(published).issubset(set(COMMERCIAL_ADDON_SKUS))


def test_stripe_verifier_accepts_current_portrait_polish_price_and_rejects_stale_price():
    purchase = order_service._extract_verified_catalog_purchase_from_session(
        _checkout_session(code="portrait_polish", name="Portrait Polish", dollars=99)
    )
    assert purchase["addon_code"] == "portrait_polish"
    assert purchase["amount_cents"] == 9900

    with pytest.raises(ValueError, match="do not match"):
        order_service._extract_verified_catalog_purchase_from_session(
            _checkout_session(code="portrait_polish", name="Portrait Polish", dollars=79)
        )


def test_stripe_verifier_accepts_recurring_storage_and_admin_seat_skus():
    storage = order_service._extract_verified_catalog_purchase_from_session(
        _checkout_session(
            code="extra_storage_10gb_monthly",
            name="Extra Storage +10GB Monthly",
            dollars=15,
            interval="month",
        )
    )
    assert storage["addon_code"] == "extra_storage_10gb_monthly"
    assert storage["billing_plan"] == "monthly"

    admin_seat = order_service._extract_verified_catalog_purchase_from_session(
        _checkout_session(
            code="extra_admin_seat_yearly",
            name="Extra Admin Seat Annual",
            dollars=190,
            interval="year",
        )
    )
    assert admin_seat["addon_code"] == "extra_admin_seat_yearly"
    assert admin_seat["billing_plan"] == "yearly"


def test_family_estate_paid_expansion_skus_are_allowed_and_expand_scope():
    package = get_package("family_estate_concierge") or {}
    assert "extra_linked_household" in (package.get("allowed_addons") or [])
    assert "extra_branch" in (package.get("allowed_addons") or [])
    assert entitlement_service.can_purchase_addon(
        "family_estate_concierge", "extra_linked_household"
    )
    assert entitlement_service.can_purchase_addon("family_estate_concierge", "extra_branch")

    resolved = entitlement_service.resolve_project_entitlements(
        "family_estate_concierge",
        ["extra_linked_household", "extra_branch"],
    )
    assert resolved["max_households"] == 5
    assert resolved["max_family_branches"] == 4
    assert resolved["can_link_households"] is True


def test_command_extra_node_is_allowed_and_expands_node_limit():
    package = get_package("command_structure_network") or {}
    assert "extra_org_node" in (package.get("allowed_addons") or [])
    assert entitlement_service.can_purchase_addon(
        "command_structure_network", "extra_org_node"
    )
    resolved = entitlement_service.resolve_project_entitlements(
        "command_structure_network", ["extra_org_node"]
    )
    assert resolved["max_org_nodes"] == 16


def test_storage_variants_apply_the_purchased_capacity_not_a_generic_ten_gb():
    resolved = entitlement_service.resolve_project_entitlements(
        "family_estate_concierge", ["vault_expansion_50gb_yearly"]
    )
    assert resolved["max_storage_gb"] == 100.0


def test_package_specific_rush_sku_cannot_cross_package_boundaries():
    assert entitlement_service.can_purchase_addon(
        "legacy_plus", "rush_delivery_legacy_plus"
    )
    assert not entitlement_service.can_purchase_addon(
        "heirloom_legacy_tree", "rush_delivery_legacy_plus"
    )


def test_manual_service_skus_are_lane_scoped_without_fabricating_capacity():
    assert entitlement_service.can_purchase_addon(
        "legacy_plus", "family_correction_cycle"
    )
    assert not entitlement_service.can_purchase_addon(
        "command_structure_network", "family_correction_cycle"
    )
    resolved = entitlement_service.resolve_project_entitlements(
        "legacy_plus", ["family_correction_cycle"]
    )
    assert "family_correction_cycle" in resolved["active_addons"]
    assert resolved["max_members"] == 30
    assert resolved["max_storage_gb"] == 25
