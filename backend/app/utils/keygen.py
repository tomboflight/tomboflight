import secrets
import string


def generate_key(prefix: str, length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    value = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}-{value}"
