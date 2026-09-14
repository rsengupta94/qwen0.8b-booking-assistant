"""extract_phone: 10 digits that appear in the user's text. Used at ASK_PHONE.

The digits must occur in the user's own message (after stripping non-digits). A number the
model produced but the user never typed is rejected.
"""

import re

VERSION = "1"
PHONE_RE = re.compile(r"^\d{10}$")
MAX_TOKENS = 24


def schema(context: dict) -> dict:
    return {
        "type": "object",
        "properties": {"digits": {"type": "string", "pattern": "^[0-9]{0,12}$"}},
        "required": ["digits"],
        "additionalProperties": False,
    }


def _normalise(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits


def validate(output: dict | None, context: dict) -> tuple[dict, bool, str]:
    if not isinstance(output, dict) or not isinstance(output.get("digits"), str):
        return fallback(context), False, "not_string"
    digits = _normalise(output["digits"])
    if digits == "":
        return {"digits": ""}, True, "ok"  # model says no number present; state machine re-asks
    if not PHONE_RE.match(digits):
        return fallback(context), False, "not_ten_digits"
    if digits not in _normalise(context.get("user_text", "")):
        return fallback(context), False, "digits_not_in_text"
    return {"digits": digits}, True, "ok"


def fallback(context: dict) -> dict:
    return {"digits": ""}
