"""HTTP boundary for legacy admin mutation routes.

The Continuity Kernel delegates directly to domain services. Consequently,
covered legacy HTTP mutation routes have no legitimate execution caller and
must fail closed so they cannot bypass approval, idempotency, the kill switch,
or evidence recording.
"""

from __future__ import annotations


KERNEL_EXECUTION_PATH = "/admin/control-center/kernel/execute"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


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

    return normalized_path in {
        "/orders/admin/manual-order",
        "/orders/admin/repair-paid-package-access",
        "/project-entitlements/apply",
        "/users",
    }
