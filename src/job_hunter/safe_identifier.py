import re

SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


def safe_identifier(value: object) -> str:
    if not isinstance(value, str):
        return "invalid"

    if not SAFE_IDENTIFIER.fullmatch(value):
        return "invalid"

    return value