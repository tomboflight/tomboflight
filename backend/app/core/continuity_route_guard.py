"""HTTP boundary for legacy admin mutation routes.

The Continuity Kernel delegates directly to domain services. Consequently,
covered legacy HTTP mutation routes have no legitimate execution caller and
must fail closed so they cannot bypass approval, idempotency, the kill switch,
or evidence recording.
"""

from __future__ import annotations

import re

from app.config import settings


KERNEL_EXECUTION_PATH = "/admin/control-center/kernel/execute"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# These legacy endpoints historically performed privileged writes outside the
# Continuity Kernel. They remain callable in non-production development so
# domain tests and migration tooling can exercise them, but production fails
# closed until each operation has a registered Kernel adapter.
PRODUCTION_LEGACY_PRIVILEGED_MUTATION_PATTERNS = (
    re.compile(r"^/mint-jobs/run-next$"),
    re.compile(r"^/projects/[^/]+/mint-fees/(?:quote|mark-paid)$"),
    re.compile(r"^/households$"),
    re.compile(r"^/admin/mint-records/maintenance/backfill$"),
    re.compile(r"^/projects/[^/]+/(?:mint-records/prepare|digital-collectible/prepare)$"),
    re.compile(
        r"^/projects/[^/]+/mint-records/[^/]+/"
        r"(?:approve-admin|approve-customer-admin|queue)$"
    ),
    re.compile(r"^/mint-records/[^/]+/sync$"),
    re.compile(
        r"^/(?:lineage-nodes|identity-links|household-links|family-networks|"
        r"narrative-records|canonical-persons)$"
    ),
    re.compile(r"^/match-candidates/[^/]+/(?:approve|reject)$"),
    re.compile(r"^/match-generation/scan$"),
    re.compile(r"^/admin/maintenance(?:/.*)?$"),
    re.compile(r"^/intake-submissions/[^/]+/status$"),
)


def _is_production_legacy_privileged_mutation(path: str) -> bool:
    if not settings.is_production_environment:
        return False
    return any(
        pattern.fullmatch(path)
        for pattern in PRODUCTION_LEGACY_PRIVILEGED_MUTATION_PATTERNS
    )


def requires_continuity_kernel(method: str, path: str) -> bool:
    normalized_method = str(method or "").strip().upper()
    normalized_path = "/" + str(path or "").strip().lstrip("/")
    normalized_path = normalized_path.rstrip("/") or "/"
    if normalized_method not in UNSAFE_METHODS:
        return False

    if (
        normalized_path == "/admin/control-center/kernel"
        or normalized_path.startswith("/admin/control-center/kernel/")
    ):
        return False

    if normalized_path.startswith("/admin/control-center"):
        # Preview requests do not mutate business data and remain available so
        # the CEO can inspect exact before/after state.
        if normalized_path.endswith("/preview"):
            return False
        return True

    if normalized_path.startswith("/admin/stripe-ops"):
        return True

    if normalized_path.startswith("/auth/admin/users/"):
        return True

    if _is_production_legacy_privileged_mutation(normalized_path):
        return True

    return normalized_path in {
        "/orders/admin/manual-order",
        "/orders/admin/repair-paid-package-access",
        "/project-entitlements/apply",
        "/users",
    }
