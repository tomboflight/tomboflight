"""Continuity Kernel feature-flag helpers.

This module is isolated.
This module does not wire runtime routes.
This module does not create apply mode.
This module does not execute repairs.
This module does not write to the database.
This module does not queue mint work.
This module does not mutate certificates.
This module does not alter customer records.

Missing flag values evaluate false/off.
Invalid flag values evaluate false/off.
"""

from __future__ import annotations

import os

CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED = "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED"
DEFAULT_CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED = False

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def normalize_bool_flag(value: object) -> bool:
    """Normalize mixed input to a fail-closed boolean value."""
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES or normalized == "":
            return False
        return False
    return False


def is_readonly_admin_preview_enabled(env: dict | None = None) -> bool:
    """Return whether the read-only admin preview flag is explicitly enabled."""
    environment = env if env is not None else os.environ
    raw_value = environment.get(CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED)
    if raw_value is None:
        return DEFAULT_CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED
    return normalize_bool_flag(raw_value)


def feature_flag_status(env: dict | None = None) -> dict:
    """Return diagnostic metadata for the read-only admin preview feature flag."""
    source = "provided_env" if env is not None else "os.environ"
    return {
        "flag_name": CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED,
        "enabled": is_readonly_admin_preview_enabled(env=env),
        "default": DEFAULT_CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED,
        "source": source,
        "fail_closed": True,
    }
