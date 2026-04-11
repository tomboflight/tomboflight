import re

_PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 12 characters and include at least 1 uppercase letter, "
    "1 lowercase letter, 1 number, and 1 special character."
)

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password_strength(password: str) -> None:
    """Raise ValueError if *password* does not meet the Tomb of Light policy."""
    password = str(password or "")
    if len(password) < 12:
        raise ValueError(_PASSWORD_POLICY_MESSAGE)
    if not _UPPER.search(password):
        raise ValueError(_PASSWORD_POLICY_MESSAGE)
    if not _LOWER.search(password):
        raise ValueError(_PASSWORD_POLICY_MESSAGE)
    if not _DIGIT.search(password):
        raise ValueError(_PASSWORD_POLICY_MESSAGE)
    if not _SPECIAL.search(password):
        raise ValueError(_PASSWORD_POLICY_MESSAGE)
