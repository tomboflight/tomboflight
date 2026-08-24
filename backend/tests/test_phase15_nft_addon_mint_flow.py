import asyncio
import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bson import ObjectId

from app.core.admin_permission_registry import CEO_MASTER_ADMIN_EMAIL
from app.core.package_catalog import (
    NFT_ADDON_CODES,
    get_addon,
    get_package_catalog,
    get_package_control_profile,
)
from app.services import (
    mint_fee_service,
    mint_job_service,
    mint_policy_service,
    mint_record_service,
    mint_worker_service,
    nft_addon_service,
    nft_checkout_service,
    order_service,
)
from app.services.nft_addon_service import (
    ACTIVE_MINT_RECORD_STATUSES,
    ADDITIONAL_MINT_ADDON_CODE,
    INITIAL_MINT_ADDON_CODE,
    METADATA_REVISION_ADDON_CODE,
    MINT_ADDON_CODES,
    profile_is_complete,
    purchase_runtime_is_ready,
    reserve_paid_mint_addon,
    validate_nft_addon_purchase_target,
)


def checkout_session(*, code: str, name: str, cents: int) -> dict:
    return {
        "id": "cs_phase15",
        "status": "complete",
        "payment_status": "paid",
        "amount_total": cents,
        "currency": "usd",
        "customer_details": {"email": "customer@example.com"},
        "client_reference_id": f"tol:v=1&u=507f1f77bcf86cd799439011&p=507f1f77bcf86cd799439012&k={code}&t=addon&b=one_time",
        "line_items": {
            "data": [
                {
                    "quantity": 1,
                    "description": name,
                    "price": {
                        "id": "price_phase15",
                        "unit_amount": cents,
                        "currency": "usd",
                        "product": {
                            "id": "prod_phase15",
                            "name": name,
                            "metadata": {"addon_code": code},
                        },
                    },
                }
            ]
        },
    }


class Phase15CatalogPolicyTests(unittest.TestCase):
    def test_every_base_package_is_addon_only(self):
        for package_code in get_package_catalog():
            with self.subTest(package_code=package_code):
                policy = get_package_control_profile(package_code)["mint_policy"]
                self.assertFalse(policy["product_includes_onchain_anchor"])
                self.assertFalse(policy["minting_included"])
                self.assertFalse(policy["auto_mint_enabled"])
                self.assertEqual(policy["included_anchor_count"], 0)
                self.assertTrue(policy["requires_paid_nft_addon"])
                self.assertTrue(policy["checkout_never_triggers_mint"])

    def test_nft_addon_catalog_matches_live_prices(self):
        self.assertEqual(get_addon(INITIAL_MINT_ADDON_CODE)["price_usd"], 499)
        self.assertEqual(get_addon(ADDITIONAL_MINT_ADDON_CODE)["price_usd"], 399)
        self.assertEqual(get_addon(METADATA_REVISION_ADDON_CODE)["price_usd"], 149)
        self.assertEqual(set(NFT_ADDON_CODES), {
            INITIAL_MINT_ADDON_CODE,
            ADDITIONAL_MINT_ADDON_CODE,
            METADATA_REVISION_ADDON_CODE,
        })
        self.assertNotIn(METADATA_REVISION_ADDON_CODE, MINT_ADDON_CODES)

    def test_profile_must_be_delivered_not_merely_build_ready(self):
        self.assertFalse(profile_is_complete({"status": "build_ready", "phase": "client_review"}))
        self.assertTrue(profile_is_complete({"status": "delivered"}))
        self.assertTrue(profile_is_complete({"phase": "delivery_complete"}))

    def test_organization_checkout_requires_organization_mint_runtime(self):
        project = {
            "package_code": "command_structure_network",
            "status": "delivered",
        }
        with (
            patch.object(nft_addon_service.settings, "nft_mint_enabled", True),
            patch.object(nft_addon_service.settings, "nft_mint_worker_enabled", True),
            patch.object(nft_addon_service.settings, "nft_auto_mint_on_review_enabled", False),
            patch.object(nft_addon_service.settings, "nft_org_mint_enabled", False),
        ):
            self.assertFalse(purchase_runtime_is_ready(project))

    def test_production_checkout_requires_legacy_links_disabled_confirmation(self):
        project = {
            "package_code": "digital_legacy_portrait",
            "status": "delivered",
        }
        with (
            patch.object(nft_addon_service.settings, "environment", "production"),
            patch.object(nft_addon_service.settings, "nft_mint_enabled", True),
            patch.object(nft_addon_service.settings, "nft_mint_worker_enabled", True),
            patch.object(nft_addon_service.settings, "nft_auto_mint_on_review_enabled", False),
            patch.object(
                nft_addon_service.settings,
                "nft_legacy_payment_links_disabled",
                False,
            ),
        ):
            self.assertFalse(purchase_runtime_is_ready(project))


class Phase15StripeVerificationTests(unittest.TestCase):
    def test_exact_first_mint_addon_is_verified(self):
        purchase = order_service._extract_verified_catalog_purchase_from_session(
            checkout_session(
                code=INITIAL_MINT_ADDON_CODE,
                name="Add-On — NFT Lineage Record",
                cents=49900,
            )
        )
        self.assertEqual(purchase["item_type"], "addon")
        self.assertEqual(purchase["addon_code"], INITIAL_MINT_ADDON_CODE)
        self.assertEqual(purchase["amount_cents"], 49900)

    def test_wrong_nft_addon_price_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "do not match"):
            order_service._extract_verified_catalog_purchase_from_session(
                checkout_session(
                    code=INITIAL_MINT_ADDON_CODE,
                    name="Add-On — NFT Lineage Record",
                    cents=39900,
                )
            )

    def test_metadata_revision_never_becomes_mint_credit(self):
        purchase = order_service._extract_verified_catalog_purchase_from_session(
            checkout_session(
                code=METADATA_REVISION_ADDON_CODE,
                name="Add-On — NFT Metadata Revision",
                cents=14900,
            )
        )
        self.assertEqual(purchase["addon_code"], METADATA_REVISION_ADDON_CODE)
        self.assertNotIn(purchase["addon_code"], MINT_ADDON_CODES)

    def test_product_name_and_requested_code_must_agree(self):
        with self.assertRaisesRegex(ValueError, "not an approved"):
            order_service._extract_verified_catalog_purchase_from_session(
                checkout_session(
                    code=INITIAL_MINT_ADDON_CODE,
                    name="Add-On — Additional NFT Copy / Mint",
                    cents=49900,
                )
            )

    def test_checkout_must_contain_exactly_one_addon(self):
        session = checkout_session(
            code=INITIAL_MINT_ADDON_CODE,
            name="Add-On — NFT Lineage Record",
            cents=49900,
        )
        session["line_items"]["data"].append(session["line_items"]["data"][0])
        with self.assertRaisesRegex(ValueError, "exactly one item"):
            order_service._extract_verified_catalog_purchase_from_session(session)


class Phase15AuthenticatedCheckoutTests(unittest.TestCase):
    def test_price_resolver_requires_one_exact_active_product_and_amount(self):
        stripe_price = {
            "id": "price_nft_lineage",
            "active": True,
            "unit_amount": 49900,
            "currency": "usd",
            "recurring": None,
            "product": {
                "id": "prod_nft_lineage",
                "name": "Add-On — NFT Lineage Record",
                "active": True,
            },
        }
        with (
            patch.object(nft_checkout_service.settings, "stripe_secret_key", "sk_test_phase15"),
            patch.object(
                nft_checkout_service.settings,
                "stripe_nft_lineage_record_price_id",
                "",
            ),
            patch.object(
                nft_checkout_service.stripe.Price,
                "list",
                return_value={"data": [stripe_price]},
            ),
        ):
            price_id = nft_checkout_service.resolve_nft_addon_price_id(
                INITIAL_MINT_ADDON_CODE
            )
        self.assertEqual(price_id, "price_nft_lineage")

    def test_server_creates_checkout_only_after_authenticated_validation(self):
        user_id = ObjectId("507f1f77bcf86cd799439011")
        project_id = ObjectId("507f1f77bcf86cd799439012")
        user = {"_id": user_id, "email": "customer@example.com"}
        validated_project = {
            "_id": project_id,
            "_nft_credit_slot": "mint:1",
        }
        with (
            patch.object(
                nft_checkout_service,
                "validate_nft_addon_purchase_target",
                return_value=validated_project,
            ) as validate_target,
            patch.object(
                nft_checkout_service,
                "resolve_nft_addon_price_id",
                return_value="price_nft_lineage",
            ),
            patch.object(nft_checkout_service.settings, "stripe_secret_key", "sk_test_phase15"),
            patch.object(
                nft_checkout_service.settings,
                "nft_default_external_url",
                "https://tomboflight.com",
            ),
            patch.object(
                nft_checkout_service.stripe.checkout.Session,
                "create",
                return_value={
                    "id": "cs_phase15_server",
                    "url": "https://checkout.stripe.com/c/pay/cs_phase15_server",
                    "expires_at": 123456789,
                },
            ) as create_session,
        ):
            payload = nft_checkout_service.create_nft_addon_checkout_session(
                user=user,
                project_id=str(project_id),
                addon_code=INITIAL_MINT_ADDON_CODE,
            )

        validate_target.assert_called_once()
        params = create_session.call_args.kwargs
        self.assertEqual(params["line_items"], [{"price": "price_nft_lineage", "quantity": 1}])
        self.assertEqual(params["metadata"]["project_id"], str(project_id))
        self.assertEqual(params["metadata"]["checkout_never_triggers_mint"], "true")
        self.assertIn("idempotency_key", params)
        self.assertNotIn("payment_link", params)
        self.assertTrue(payload["checkout_creates_credit_only"])
        self.assertTrue(payload["checkout_never_triggers_mint"])

    def test_public_frontend_contains_no_nft_payment_link_bypass(self):
        root = Path(__file__).resolve().parents[2]
        config_source = (root / "config.js").read_text(encoding="utf-8")
        dashboard_source = (root / "dashboard-intake.js").read_text(encoding="utf-8")
        for addon_code in (
            INITIAL_MINT_ADDON_CODE,
            ADDITIONAL_MINT_ADDON_CODE,
            METADATA_REVISION_ADDON_CODE,
        ):
            self.assertRegex(
                config_source,
                re.compile(
                    rf'slug:\s*"{addon_code}"[\s\S]{{0,180}}checkoutUrl:\s*""'
                ),
            )
        self.assertIn(
            "/nft-addons/${encodeURIComponent(code)}/checkout-session",
            dashboard_source,
        )


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _OrdersCollection:
    def __init__(self):
        self.documents = []

    def find_one(self, query):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    def insert_one(self, document):
        saved = dict(document)
        saved.setdefault("_id", ObjectId())
        self.documents.append(saved)
        return _InsertResult(saved["_id"])


class Phase15StripeOrderTests(unittest.TestCase):
    def test_paid_checkout_creates_credit_only_and_replay_is_idempotent(self):
        user_id = ObjectId("507f1f77bcf86cd799439011")
        project_id = ObjectId("507f1f77bcf86cd799439012")
        session = checkout_session(
            code=INITIAL_MINT_ADDON_CODE,
            name="Add-On — NFT Lineage Record",
            cents=49900,
        )
        orders = _OrdersCollection()
        validated_project = {
            "_id": project_id,
            "package_code": "digital_legacy_portrait",
            "_nft_credit_slot": "mint:1",
            "_nft_credit_slot_key": f"{project_id}:mint:1",
        }
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": session["id"]}},
        }
        with (
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
            patch.object(
                order_service,
                "_get_user_by_email",
                return_value={"_id": user_id, "email": "customer@example.com"},
            ),
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(
                order_service,
                "validate_nft_addon_purchase_target",
                return_value=validated_project,
            ) as validate_target,
            patch.object(order_service, "_trigger_package_provisioning") as provision,
        ):
            first = order_service.upsert_order_from_stripe_event(event)
            second = order_service.upsert_order_from_stripe_event(event)

        self.assertFalse(first["existing"])
        self.assertTrue(second["existing"])
        self.assertEqual(validate_target.call_count, 1)
        provision.assert_not_called()
        self.assertEqual(len(orders.documents), 1)
        saved = orders.documents[0]
        self.assertTrue(saved["nft_addon_verified"])
        self.assertEqual(saved["nft_credit_status"], "available")
        self.assertEqual(saved["nft_credit_slot"], "mint:1")
        self.assertTrue(saved["nft_addon_checkout_does_not_auto_mint"])
        self.assertNotIn("mint_status", saved)
        self.assertNotIn("mint_record_id", saved)


class _ReserveOrdersCollection:
    def __init__(self):
        self.query = None
        self.update = None

    def find_one_and_update(self, query, update, **_kwargs):
        self.query = query
        self.update = update
        return {"_id": ObjectId(), "addon_code": INITIAL_MINT_ADDON_CODE}


class Phase15CreditTests(unittest.TestCase):
    def test_reservation_is_atomic_and_accepts_only_verified_stripe_credit(self):
        orders = _ReserveOrdersCollection()
        with patch.object(nft_addon_service, "_db", return_value={"orders": orders}):
            reservation = reserve_paid_mint_addon(
                "507f1f77bcf86cd799439012",
                required_addon_code=INITIAL_MINT_ADDON_CODE,
            )
        self.assertEqual(reservation["addon_code"], INITIAL_MINT_ADDON_CODE)
        self.assertTrue(orders.query["nft_addon_verified"])
        self.assertNotIn("admin_manual", orders.query["source"]["$in"])
        self.assertEqual(orders.update["$set"]["nft_credit_status"], "reserved")

    def test_metadata_revision_can_never_be_reserved_for_mint(self):
        with self.assertRaisesRegex(ValueError, "mint-authorizing"):
            reserve_paid_mint_addon(
                "507f1f77bcf86cd799439012",
                required_addon_code=METADATA_REVISION_ADDON_CODE,
            )

    def test_failed_record_keeps_paid_credit_bound_for_recovery(self):
        self.assertIn("failed", ACTIVE_MINT_RECORD_STATUSES)

    def test_duplicate_credit_state_blocks_another_checkout(self):
        project_id = "507f1f77bcf86cd799439012"
        project = {
            "_id": ObjectId(project_id),
            "owner_user_id": ObjectId("507f1f77bcf86cd799439011"),
            "status": "delivered",
        }
        status = {
            "mint_count": 0,
            "purchase_options": {
                INITIAL_MINT_ADDON_CODE: {
                    "eligible": False,
                    "reason": "mint_credit_already_purchased",
                }
            },
        }
        with (
            patch.object(nft_addon_service, "_project", return_value=project),
            patch.object(nft_addon_service, "_user_can_purchase_for_project", return_value=True),
            patch.object(nft_addon_service, "get_nft_addon_status", return_value=status),
            patch.object(nft_addon_service.settings, "nft_mint_enabled", True),
            patch.object(nft_addon_service.settings, "nft_mint_worker_enabled", True),
            patch.object(nft_addon_service.settings, "nft_auto_mint_on_review_enabled", False),
        ):
            with self.assertRaisesRegex(ValueError, "already paid"):
                validate_nft_addon_purchase_target(
                    user={"_id": ObjectId("507f1f77bcf86cd799439011")},
                    project_id=project_id,
                    addon_code=INITIAL_MINT_ADDON_CODE,
                )


class Phase15ApprovalBoundaryTests(unittest.TestCase):
    def test_manual_paid_or_waived_flags_cannot_replace_checkout(self):
        with self.assertRaisesRegex(ValueError, "exact verified NFT add-on price"):
            mint_fee_service.quote_mint_fee(
                "project",
                {"email": CEO_MASTER_ADMIN_EMAIL},
                {},
            )
        with self.assertRaisesRegex(ValueError, "verified NFT add-on"):
            mint_fee_service.mark_mint_fee_paid("project", {"email": CEO_MASTER_ADMIN_EMAIL})
        with self.assertRaisesRegex(ValueError, "cannot be waived"):
            mint_fee_service.waive_mint_fee("project", {"email": CEO_MASTER_ADMIN_EMAIL})
        with self.assertRaisesRegex(ValueError, "Network execution"):
            mint_fee_service.refresh_network_quote(
                "project",
                {"email": CEO_MASTER_ADMIN_EMAIL},
                {},
            )

    def test_non_ceo_cannot_final_approve_or_queue_through_legacy_services(self):
        with self.assertRaisesRegex(ValueError, "CEO master account"):
            mint_record_service.approve_admin_mint_record(
                "mint-record",
                approved_by_email="operations@tomboflight.com",
            )
        with self.assertRaisesRegex(ValueError, "CEO master account"):
            mint_job_service.queue_mint_pipeline(
                "project",
                "mint-record",
                queued_by="operations@tomboflight.com",
            )


class Phase15EligibilityTests(unittest.TestCase):
    def test_paid_addon_and_delivered_profile_are_both_required(self):
        project = {
            "_id": "project-15",
            "package_code": "digital_legacy_portrait",
            "status": "delivered",
            "public_safe_approved": True,
            "delivery_manifest_finalized": True,
            "mint_collectible_preparing": True,
        }
        addon_status = {
            "profile_complete": True,
            "mint_credit_satisfied": True,
            "required_mint_addon_code": INITIAL_MINT_ADDON_CODE,
            "purchase_options": {},
        }
        with (
            patch.object(mint_policy_service, "_runtime_enabled", return_value=True),
            patch.object(mint_policy_service.settings, "nft_mint_worker_enabled", True),
            patch(
                "app.services.nft_addon_service.get_nft_addon_status",
                return_value=addon_status,
            ),
        ):
            payload = mint_policy_service.describe_project_mint_eligibility(project)
        self.assertTrue(payload["eligible"])
        self.assertTrue(payload["ready_for_mint_preparation"])


class Phase15WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_runs_only_when_explicitly_enabled(self):
        stop = asyncio.Event()
        with patch.object(mint_worker_service, "mint_worker_enabled", return_value=False), patch.object(
            mint_worker_service, "run_next_job"
        ) as run_next:
            await mint_worker_service.run_controlled_mint_worker(stop)
        run_next.assert_not_called()

    async def test_worker_processes_prequeued_jobs_not_checkout_events(self):
        stop = asyncio.Event()

        async def stop_after_one(_fn, _worker_id):
            stop.set()
            return {"status": "completed"}

        with patch.object(mint_worker_service, "mint_worker_enabled", return_value=True), patch.object(
            asyncio, "to_thread", new=AsyncMock(side_effect=stop_after_one)
        ) as to_thread:
            await mint_worker_service.run_controlled_mint_worker(stop)
        self.assertEqual(to_thread.await_count, 1)


if __name__ == "__main__":
    unittest.main()
