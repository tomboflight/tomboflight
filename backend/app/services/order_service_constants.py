"""Shared order-state constants without importing the full order service."""

AUTHORITATIVE_ORDER_SOURCES = frozenset({"stripe_webhook", "stripe_verified"})
PAID_ORDER_STATUSES = frozenset({"paid", "complete", "completed", "succeeded"})
FULFILLMENT_PENDING = "pending_manual_fulfillment"
FULFILLMENT_IN_PROGRESS = "fulfillment_in_progress"
FULFILLMENT_COMPLETE = "fulfillment_complete"
FULFILLMENT_ESCALATED = "payment_mismatch_escalated"
FULFILLMENT_AUTO = "auto_provisioned"
OPEN_FULFILLMENT_STATUSES = frozenset(
    {FULFILLMENT_PENDING, FULFILLMENT_IN_PROGRESS, FULFILLMENT_ESCALATED}
)
