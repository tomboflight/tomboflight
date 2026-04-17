from __future__ import annotations

PROJECT_STATUSES = frozenset(
    {
        "draft",
        "purchased",
        "build_ready",
        "in_production",
        "qa_review",
        "client_review",
        "delivered",
        "archived",
    }
)

PROJECT_PHASES = frozenset(
    {
        "created",
        "checkout_completed",
        "intake_approved",
        "build_started",
        "quality_review",
        "client_review",
        "delivery_complete",
        "archived",
    }
)

WORKFLOW_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "": {"draft", "purchased", "build_ready"},
    "draft": {"purchased", "build_ready"},
    "purchased": {"build_ready"},
    "build_ready": {"in_production", "archived"},
    "in_production": {"qa_review", "client_review", "archived"},
    "qa_review": {"client_review", "in_production", "archived"},
    "client_review": {"delivered", "in_production", "archived"},
    "delivered": {"archived"},
    "archived": set(),
}

WORKFLOW_PHASE_BY_STATE: dict[str, str] = {
    "draft": "created",
    "purchased": "checkout_completed",
    "build_ready": "intake_approved",
    "in_production": "build_started",
    "qa_review": "quality_review",
    "client_review": "client_review",
    "delivered": "delivery_complete",
    "archived": "archived",
}


def is_valid_transition(from_state: str, to_state: str) -> bool:
    normalized_from = str(from_state or "").strip().lower()
    normalized_to = str(to_state or "").strip().lower()
    return normalized_to in WORKFLOW_ALLOWED_TRANSITIONS.get(normalized_from, set())
