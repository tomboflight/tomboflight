import random
import string


def generate_key(prefix: str, length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    value = "".join(random.choices(alphabet, k=length))
    return f"{prefix}-{value}"